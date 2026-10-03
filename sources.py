"""
Парсери сайтів. Кожне джерело має:
  search(...)  -> list[Listing]   — список з результатів пошуку (дешево)
  details(l)   -> Listing         — догружає сторінку оголошення (ціни, опис, контакти)
"""
import json
import re

import requests
from bs4 import BeautifulSoup

import config
from analyze import Listing, parse_num

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def get(url, **kw):
    import time
    last = None
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30, **kw)
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}"
            if r.status_code in (403, 404, 410):
                break
        except requests.RequestException as e:
            last = str(e)
        time.sleep(3 + attempt * 5)
    raise RuntimeError(f"{last} — {url}")


def strip_html(s: str) -> str:
    return BeautifulSoup(s or "", "html.parser").get_text("\n")


def norm_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"[^\d+]", "", p)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    elif digits.startswith("0"):
        digits = "+43" + digits[1:]
    elif not digits.startswith("+"):
        digits = "+" + digits
    if digits.startswith("+43"):
        return "+43 " + digits[3:]
    return digits


def lines_of(soup_or_text) -> list:
    txt = soup_or_text if isinstance(soup_or_text, str) else soup_or_text.get_text("\n", strip=True)
    return [x.strip() for x in txt.split("\n") if x.strip()]


def value_after(lines, *labels):
    """Значення з рядка, що йде одразу після мітки (наприклад, 'Kaution' -> '3.000 €')."""
    for i, ln in enumerate(lines[:-1]):
        if ln.rstrip(":") in labels:
            return lines[i + 1]
    return None


# =====================================================================
# willhaben.at
# =====================================================================

WH_BASE = "https://www.willhaben.at/iad/immobilien/mietwohnungen/mietwohnung-angebote"


def _wh_next_data(page_html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_html, re.S)
    if not m:
        raise RuntimeError("willhaben: не знайдено __NEXT_DATA__ (змінилась сторінка?)")
    return json.loads(m.group(1))


def _wh_attrs(block):
    return {a["name"]: a.get("values") or [] for a in (block or {}).get("attribute", [])}


def _first(attrs, key):
    v = attrs.get(key)
    return v[0] if v else None


def willhaben_search(area_id: int) -> list:
    params = [("areaId", area_id), ("rows", 90), ("sort", 1),        # sort=1 → найновіші
              ("PRICE_TO", config.MAX_TOTAL_HARD), ("ESTATE_SIZE/LIVING_AREA_FROM", config.MIN_AREA)]
    params += [("NO_OF_ROOMS_BUCKET", f"{r}X{r}") for r in sorted(config.ROOMS)]
    data = _wh_next_data(get(WH_BASE, params=params))
    ads = data["props"]["pageProps"]["searchResult"]["advertSummaryList"]["advertSummary"]
    out = []
    for ad in ads:
        a = _wh_attrs(ad.get("attributes"))
        lat = lon = None
        coords = _first(a, "COORDINATES")
        if coords and "," in coords:
            lat, lon = (float(x) for x in coords.split(","))
        mmo = _first(a, "MMO")
        out.append(Listing(
            source="willhaben", id=str(ad["id"]),
            url="https://www.willhaben.at/iad/" + (_first(a, "SEO_URL") or f"object?adId={ad['id']}"),
            title=_first(a, "HEADING") or ad.get("description", ""),
            postcode=_first(a, "POSTCODE") or "", location=_first(a, "LOCATION") or "",
            address=_first(a, "ADDRESS") or "",
            total_rent=parse_num(_first(a, "PRICE")),
            area=parse_num(_first(a, "ESTATE_SIZE/LIVING_AREA") or _first(a, "ESTATE_SIZE")),
            rooms=parse_num(_first(a, "NUMBER_OF_ROOMS")),
            lat=lat, lon=lon,
            image=f"https://cache.willhaben.at/mmo/{mmo}" if mmo else "",
            features=a.get("FREE_AREA_TYPE_NAME", []),
            contact_company=_first(a, "ORGNAME") or "",
        ))
    return out


def willhaben_details(l: Listing) -> Listing:
    ad = _wh_next_data(get(l.url))["props"]["pageProps"]["advertDetails"]
    a = _wh_attrs(ad.get("attributes"))
    vat = 1 + config.VAT_RATE
    l.rent_net = parse_num(_first(a, "RENTAL_PRICE/PER_MONTH_NET"))          # exkl. USt, exkl. BK
    if l.rent_net:
        l.rent_vat = round(l.rent_net * config.VAT_RATE, 2)                  # willhaben явно пише «exkl. MWSt»
    bk_net = parse_num(_first(a, "RENTAL_PRICE/ADDITIONAL_COST_NET"))
    l.bk = round(bk_net * vat, 2) if bk_net else None
    l.total_rent = parse_num(_first(a, "RENTAL_PRICE/PER_MONTH")) or l.total_rent
    l.area = parse_num(_first(a, "ESTATE_SIZE/LIVING_AREA")) or l.area
    l.rooms = parse_num(_first(a, "NO_OF_ROOMS")) or l.rooms
    l.deposit = parse_num(_first(a, "ADDITIONAL_COST/DEPOSIT"))
    l.features = list(set(l.features + a.get("ESTATE_PREFERENCE", []) + a.get("FREE_AREA/FREE_AREA_TYPE", [])))

    # контакти
    cd = {}
    for block in (ad.get("advertContactDetails") or {}).get("contactDetail", []):
        for f in block.get("contactDetailField", []):
            cd.setdefault(f.get("id"), f.get("value"))
    org = ad.get("organisationDetails") or {}
    seller = ad.get("sellerProfileUserData") or {}
    l.contact_name = (_first(a, "CONTACT/NAME") or cd.get("contactName") or seller.get("name") or "").strip()
    l.contact_company = (_first(a, "CONTACT/COMPANYNAME") or cd.get("companyName") or org.get("orgName")
                         or l.contact_company or "").strip()
    l.contact_phone = norm_phone(_first(a, "CONTACT/PHONE") or cd.get("phoneNo") or cd.get("phoneNo2")
                                 or org.get("orgPhone") or "")
    l.contact_email = (_first(a, "CONTACT/EMAIL") or cd.get("email") or org.get("orgEmail") or "").strip()

    skip = ("CONTACT/", "IMPORT_", "LOCATION/", "SHOW_", "ORG_", "AREA_ID", "REGION_AREA_ID")
    parts = [ad.get("description", "")]
    for k, vals in a.items():
        if not k.startswith(skip):
            parts.append(f"{k}: " + " | ".join(strip_html(v) for v in vals))
    l.text = "\n".join(parts)
    return l


# =====================================================================
# immobilienscout24.at
# =====================================================================

IS_BASE = "https://www.immobilienscout24.at/regional/{region}/wohnung-mieten/aktualitaet{page}"


def _is_state(page_html):
    i = page_html.find("window.__INITIAL_STATE__=")
    if i < 0:
        raise RuntimeError("immoscout: не знайдено __INITIAL_STATE__")
    j = page_html.find("\n", i)
    raw = page_html[i + len("window.__INITIAL_STATE__="):j].strip().rstrip(";")
    raw = re.sub(r":undefined([,}\]])", r":null\1", raw)
    return json.loads(raw)


def immoscout_search(region: str, pages: int) -> list:
    params = {"numberOfRoomsFrom": min(config.ROOMS), "numberOfRoomsTo": max(config.ROOMS),
              "primaryAreaFrom": config.MIN_AREA, "primaryPriceTo": config.MAX_TOTAL_HARD,
              "isSocialHousing": "false"}
    out = []
    for p in range(1, pages + 1):
        url = IS_BASE.format(region=region, page="" if p == 1 else f"/seite-{p}")
        hits = _is_state(get(url, params=params))["reduxAsyncConnect"]["pageData"]["results"].get("hits") or []
        for h in hits:
            addr = h.get("addressString") or ""
            m = re.search(r"\b(\d{4})\b", addr)
            loc = h.get("location") or {}
            rc = h.get("realtorContact") or {}
            badges = [((b.get("details") or {}).get("value") or "") for b in h.get("typedBadges") or []]
            out.append(Listing(
                source="immoscout", id=h["exposeId"],
                url=(h.get("links") or {}).get("absoluteURL") or f"https://www.immobilienscout24.at/expose/{h['exposeId']}",
                title=h.get("headline", ""), postcode=m.group(1) if m else "", address=addr,
                total_rent=parse_num(h.get("primaryPrice")), area=parse_num(h.get("primaryArea")),
                rooms=parse_num(h.get("numberOfRooms")), lat=loc.get("lat"), lon=loc.get("lon"),
                image=(h.get("primaryPictureImageProps") or {}).get("src") or "",
                features=[b.replace("TERRACE", "Terrasse").replace("GARAGE", "Garage") for b in badges],
                contact_name=rc.get("name") or "",
                contact_company="" if (rc.get("company") or "").startswith("Privat") else (rc.get("company") or ""),
            ))
        if len(hits) < 15:
            break
    return out


def immoscout_details(l: Listing) -> Listing:
    page = get(l.url)
    m = re.search(r'"telephone"\s*:\s*"([^"]+)"', page)
    if m:
        l.contact_phone = norm_phone(m.group(1))
    m = re.search(r'"email"\s*:\s*"([^"@\s]+@[^"\s]+)"', page)
    if m:
        l.contact_email = m.group(1)
    soup = BeautifulSoup(page, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    chunks = []
    for sec in soup.find_all("section"):
        txt = sec.get_text("\n", strip=True)
        if txt.startswith(("Gewerblich", "Privat", "Mietwohnungen", "Wohnungen")):
            continue      # блок контакту та «схожі оголошення»
        chunks.append(txt)
    text = "\n".join(chunks) or soup.get_text("\n", strip=True)
    l.text = l.title + "\n" + text

    costs = re.search(r"Laufende Kosten(.*?)(Einmalige Kosten|Merkmale|$)", text, re.S)
    lines = lines_of(costs.group(1) if costs else "")
    tot = parse_num(value_after(lines, "Monatliche Kosten") or "")
    if tot:
        l.total_rent = tot
    if "Betriebskosten" in lines:
        l.rent_net = parse_num(value_after(lines, "Miete") or "")
        l.rent_vat = parse_num(value_after(lines, "USt. Miete") or "")
        bk = parse_num(value_after(lines, "Betriebskosten") or "") or 0
        bk_vat = parse_num(value_after(lines, "USt. Betriebskosten") or "") or 0
        heat = parse_num(value_after(lines, "Heizkosten Netto", "Heizkosten") or "") or 0
        heat_vat = parse_num(value_after(lines, "USt. Heizkosten") or "") or 0
        l.bk = round(bk + bk_vat, 2) or None          # Heizkosten — окремо, у ліміт не входять
        l.heating = round(heat + heat_vat, 2) or None
    elif value_after(lines, "Miete") and not tot:
        l.total_rent = parse_num(value_after(lines, "Miete"))   # приватні: одна сума
    return l


# =====================================================================
# immobilien.derstandard.at  (Next.js RSC)
# =====================================================================

DS_BASE = "https://immobilien.derstandard.at"


def _rsc_text(page_html: str) -> str:
    parts = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', page_html)
    return "".join(json.loads(p) for p in parts)


def _json_objects(s: str, prefix: str):
    """Знаходить у тексті всі JSON-об'єкти, що починаються з prefix."""
    p = 0
    while True:
        p = s.find(prefix, p)
        if p < 0:
            return
        depth, i, in_str = 0, p, False
        while i < len(s):
            c = s[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try:
            yield json.loads(s[p:i + 1])
        except json.JSONDecodeError:
            pass
        p = i + 1


DS_ENTRY = '{"__typename":"PropertyEntryResponse"'


def _ds_apply(l: Listing, e: dict):
    prop = e.get("property") or {}
    loc = prop.get("location") or {}
    l.postcode = loc.get("zipCode") or l.postcode
    l.address = loc.get("street") or l.address
    l.location = loc.get("city") or l.location
    areas = prop.get("areas") or {}
    for d in areas.get("details") or []:
        if d.get("kind") == "ROOM_COUNT":
            l.rooms = d.get("value")
        if d.get("kind") == "LIVING_SPACE":
            l.area = d.get("value")
    l.area = l.area or (areas.get("main") or {}).get("value")
    costs = prop.get("costs") or {}
    c = {d["kind"]: d for d in costs.get("details") or []}
    main = costs.get("main") or {}
    total = None
    for k in ("MONTHLY_COSTS", "TOTAL_RENT", "BASE_RENT_PLUS_UTILITIES", "TOTAL_COSTS"):
        if k in c and c[k].get("gross"):
            total = c[k]["gross"]
            break
    l.total_rent = total or main.get("value") or l.total_rent
    others = [c[k].get("net") or 0 for k in ("OPERATING_COSTS", "HEATING_COSTS", "OTHER_COSTS") if k in c]
    if "SUM_OF_RENT" in c and "OPERATING_COSTS" in c and c["SUM_OF_RENT"].get("net"):
        l.rent_net = round(c["SUM_OF_RENT"]["net"] - sum(others), 2)
        bk_net = sum(c[k].get("net") or 0 for k in ("OPERATING_COSTS", "OTHER_COSTS") if k in c)
        l.bk = round(bk_net * (1 + config.VAT_RATE), 2)
    if "HEATING_COSTS" in c:                  # Heizkosten — окремо, у ліміт не входять
        h = c["HEATING_COSTS"]
        l.heating = h.get("gross") or (round(h["net"] * 1.2, 2) if h.get("net") else None)
    if "DEPOSIT" in c:
        l.deposit = c["DEPOSIT"].get("net") or c["DEPOSIT"].get("gross")
    for k, val in prop.items():             # дата заселення, якщо DER STANDARD її дає
        if "availab" in k.lower() and val:
            val = val.get("date") or val.get("value") or val.get("text") if isinstance(val, dict) else val
            if isinstance(val, (str, int)):
                l.text = (l.text + f"\nVerfügbar ab: {val}").strip()
    free = [d.get("text") for d in c.values() if d.get("text")]
    if free:
        l.text = (l.text + "\n" + "\n".join(free)).strip()
    l.features = list(set(l.features + (prop.get("amenities") or [])))
    imgs = (e.get("media") or {}).get("images") or []
    if imgs and not l.image:
        l.image = imgs[0].get("path", "")
    adv = e.get("advertiser") or {}
    comp = adv.get("company") or {}
    if comp.get("name"):
        l.contact_company = comp["name"]
    cp = adv.get("contactPerson") or {}
    if cp:
        name = " ".join(x for x in (cp.get("firstname"), cp.get("lastname")) if x)
        l.contact_name = name or l.contact_name
        l.contact_company = cp.get("companyName") or l.contact_company
        l.contact_phone = norm_phone(cp.get("phone") or "") or l.contact_phone
        l.contact_email = cp.get("email") or l.contact_email
    cond = prop.get("condition") or {}
    if cond.get("yearOfConstruction"):
        l.year = int(cond["yearOfConstruction"])
    if cond.get("buildingType"):
        l.text += f"\nBauart: {cond['buildingType']}"


def derstandard_search(region: str, pages: int) -> list:
    out = []
    for p in range(1, pages + 1):
        params = {"sorting": "latest", "priceTo": config.MAX_TOTAL_HARD, "areaFrom": config.MIN_AREA,
                  "roomCountFrom": min(config.ROOMS)}
        if p > 1:
            params["page"] = p
        s = _rsc_text(get(f"{DS_BASE}/suche/{region}/mieten-wohnung", params=params))
        for e in _json_objects(s, DS_ENTRY):
            if not e.get("id") or not (e.get("property") or {}).get("location"):
                continue      # групи новобудов без адреси пропускаємо
            l = Listing(source="derstandard", id=str(e["id"]), url=f"{DS_BASE}/detail/{e['id']}",
                        title=e.get("title", ""))
            _ds_apply(l, e)
            out.append(l)
    return out


def derstandard_details(l: Listing) -> Listing:
    s = _rsc_text(get(l.url))
    for e in _json_objects(s, DS_ENTRY):
        if str(e.get("id")) != l.id:
            continue
        _ds_apply(l, e)
        desc = e.get("description") or ""
        if desc.startswith("$"):
            m = re.search(r"(?:^|\n)" + re.escape(desc[1:]) + r":T([0-9a-f]+),", s)
            if m:
                n = int(m.group(1), 16)
                desc = s[m.end():].encode("utf-8")[:n].decode("utf-8", "ignore")
        l.text = f"{l.title}\n{strip_html(desc)}\n{l.text}"
        break
    return l


# =====================================================================
# wohnnet.at  (звичайний HTML)
# =====================================================================

WN_BASE = "https://www.wohnnet.at"


def wohnnet_search(region: str, pages: int) -> list:
    out = []
    for p in range(1, pages + 1):
        params = {"sortierung": "neueste-zuerst"}
        if p > 1:
            params["seite"] = p
        soup = BeautifulSoup(get(f"{WN_BASE}/immobilien/mietwohnungen/{region}", params=params), "html.parser")
        for a in soup.select("a[data-id]"):
            card = a.get_text("\n", strip=True)
            addr = a.select_one(".realty-detail-title-address")
            pc = re.search(r"\b(\d{4})\b", addr.get_text(" ", strip=True) if addr else card)
            area = re.search(r"([\d.,]+)\s*\n?\s*m²", card)
            rooms = re.search(r"(\d+)\s*\n?\s*Zimmer", card)
            price = re.search(r"([\d.,]+)\s*€", card)
            agency = a.select_one(".realty-detail-agency")
            img = a.select_one("img")
            out.append(Listing(
                source="wohnnet", id=a["data-id"], url=WN_BASE + a["href"],
                title=a.get("data-title") or a.get("title") or "",
                postcode=pc.group(1) if pc else "",
                address=addr.get_text(" ", strip=True) if addr else "",
                area=parse_num(area.group(1)) if area else None,
                rooms=parse_num(rooms.group(1)) if rooms else None,
                total_rent=parse_num(price.group(1)) if price else None,
                contact_company=agency.get_text(" ", strip=True) if agency else "",
                image=img["src"] if img and img.get("src", "").startswith("http") else "",
            ))
    return out


def wohnnet_details(l: Listing) -> Listing:
    soup = BeautifulSoup(get(l.url), "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    lines = lines_of(soup)
    # обрізаємо «схожі оголошення»
    if "Ähnliche Objekte" in lines:
        lines = lines[:lines.index("Ähnliche Objekte")]
    l.text = l.title + "\n" + "\n".join(lines)
    # «Mietpreis» на wohnnet = усе разом (оренда + Betriebskosten + MWSt)
    total = parse_num(value_after(lines, "Mietpreis", "Gesamtmiete", "Gesamtbelastung") or "")
    l.total_rent = total or l.total_rent
    bk = parse_num(value_after(lines, "Betriebskosten") or "")
    l.heating = parse_num(value_after(lines, "Heizkosten") or "") or None
    mwst = parse_num(value_after(lines, "MWSt.", "MwSt.", "USt.") or "")
    net = parse_num(value_after(lines, "Nettomiete", "Miete netto", "Hauptmietzins") or "")
    if net:
        l.rent_net = net
    elif total and bk:
        l.rent_net = round(total - bk - (mwst or 0), 2)
    if l.rent_net and mwst:
        l.rent_vat = round(l.rent_net * config.VAT_RATE, 2)
    if bk:
        l.bk = round(bk * (1 + config.VAT_RATE), 2) if mwst else bk
    street = value_after(lines, "Adresse", "Anschrift")
    if street and re.search(r"\d{4}|straße|gasse|weg|platz|allee|ring", street, re.I):
        l.address = street
    dep = parse_num(value_after(lines, "Kaution") or "")
    dep_info = parse_num(value_after(lines, "Kaution Info") or "")
    l.deposit = dep or (dep_info if dep_info and dep_info < 20 else None)
    if "Anbieter" in lines:
        i = lines.index("Anbieter")
        after = [x for x in lines[i + 1:i + 4] if x not in ("Anfrage senden", "Alle Immobilien des Anbieters")]
        if after:
            l.contact_company = after[0]
        if len(after) > 1:
            l.contact_name = after[1]
    return l


SOURCES = {
    "willhaben": willhaben_details,
    "immoscout": immoscout_details,
    "derstandard": derstandard_details,
    "wohnnet": wohnnet_details,
}
SOURCE_NAMES = {"willhaben": "willhaben", "immoscout": "ImmoScout24",
                "derstandard": "DER STANDARD", "wohnnet": "wohnnet"}
