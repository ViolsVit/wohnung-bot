"""Тести на основі реальних оголошень (вересень 2026). Запуск: python -m pytest -q"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import bot  # noqa: E402
import sources as S  # noqa: E402
from analyze import Listing, evaluate, fingerprint, parse_num, quick_reject, rent_with_tax  # noqa: E402


def test_parse_num():
    assert parse_num("4.690,31") == 4690.31
    assert parse_num("789,74") == 789.74
    assert parse_num("988.0") == 988.0
    assert parse_num("3.000") == 3000
    assert parse_num("€ 1.042,29") == 1042.29
    assert parse_num("37 227,50") == 37227.5
    assert parse_num("-") is None


def test_phone():
    assert S.norm_phone("004315127690404") == "+43 15127690404"
    assert S.norm_phone("069916158106") == "+43 69916158106"
    assert S.norm_phone("+4368120566112") == "+43 68120566112"


# ---------- willhaben: реальна квартира Koloniestraße 35, 1210 ----------
WH_ATTRS = {
    "RENTAL_PRICE/PER_MONTH_NET": ["789,74"], "RENTAL_PRICE/ADDITIONAL_COST_NET": ["108,44"],
    "RENTAL_PRICE/PER_MONTH": ["988"],
    "ESTATE_SIZE/LIVING_AREA": ["46,82"], "NO_OF_ROOMS": ["2"], "ADDITIONAL_COST/DEPOSIT": ["3000"],
    "BUILDING_TYPE": ["Neubau"],
    "GENERAL_TEXT_ADVERT/Zusatzinformationen": ["<ul><li>Baujahr: 2019/Neubau</li></ul>"],
    "ESTATE_PREFERENCE": ["Keller", "Garage", "Fahrstuhl", "Abstellraum"],
    "FREE_AREA/FREE_AREA_TYPE": ["Terrasse", "Loggia", "Garten"],
    "DESCRIPTION": ["Moderne Gartenwohnung mit 2 Zimmern ... Garage"],
    "CONTACT/NAME": ["Vivienne Spicak"], "CONTACT/COMPANYNAME": ["IMV Immobilienmakler"],
    "CONTACT/PHONE": ["004315127690404"],
}


def wh_html(attrs):
    nd = {"props": {"pageProps": {"advertDetails": {
        "description": "Helle 2-Zimmer-Wohnung mit Garten",
        "attributes": {"attribute": [{"name": k, "values": v} for k, v in attrs.items()]},
        "advertContactDetails": {"contactDetail": [
            {"id": "contactName", "contactDetailField": [{"id": "contactName", "value": "X"}]}]},
        "organisationDetails": {"orgEmail": "office@imv.co.at"}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script></html>'


def wh_listing(**kw):
    d = dict(source="willhaben", id="1409206528", url="x", title="Helle 2-Zimmer-Wohnung mit Garten",
             postcode="1210", location="Wien, 21. Bezirk, Floridsdorf", address="Koloniestraße 35",
             total_rent=988, area=47, rooms=2)
    d.update(kw)
    return Listing(**d)


def test_willhaben_real(monkeypatch):
    monkeypatch.setattr(S, "get", lambda url, **kw: wh_html(WH_ATTRS))
    l = S.willhaben_details(wh_listing())
    rent, est = rent_with_tax(l)
    assert round(rent, 2) == 868.71 and not est            # 789,74 + 10 % USt
    assert l.bk == 119.28
    assert l.contact_name == "Vivienne Spicak" and l.contact_phone == "+43 15127690404"
    assert l.contact_email == "office@imv.co.at"
    v = evaluate(l)
    assert v.status == "check" and v.warnings == ["посудомийка не згадана"]
    assert not v.dream                                       # 869 > 850
    assert "🚗 гараж" in v.pluses and "🌿 тераса" in v.pluses
    msg = bot.format_message(l, v)
    print(msg)
    assert "869 €" in msg and "Vivienne Spicak — IMV Immobilienmakler" in msg and "Відкрити оголошення" in msg


def test_willhaben_dream_ok(monkeypatch):
    attrs = dict(WH_ATTRS, **{"RENTAL_PRICE/PER_MONTH_NET": ["700"], "DESCRIPTION": ["Küche mit Geschirrspüler"]})
    monkeypatch.setattr(S, "get", lambda url, **kw: wh_html(attrs))
    v = evaluate(S.willhaben_details(wh_listing()))
    assert v.status == "ok" and v.dream


def test_price_rule_with_tax():
    # нетто 950 → з USt 1045 → відсіюємо (ліміт 1000 з податком)
    l = wh_listing(rent_net=950, rent_vat=95, text="Geschirrspüler Baujahr 2010 Kaution 3000")
    assert evaluate(l).status == "reject"
    # нетто 950, USt невідома → лише ⚠️
    l = wh_listing(rent_net=950, text="Geschirrspüler Baujahr 2010 Kaution 3000")
    v = evaluate(l)
    assert v.status == "check" and "USt не вказана" in v.warnings[0]


# ---------- ImmoScout ----------
def is_html(sections, extra=""):
    return "<html><body>" + "".join(f"<section>{s}</section>" for s in sections) + extra + "</body></html>"


def to_lines(*parts):
    return "".join(f"<div>{p}</div>" for p in parts)


IS_ULMENHOF = is_html([
    to_lines("| GARTENWOHNUNG | IM ULMENHOF | 2-ZIMMER WOHNUNG", "746 €", "Kaution", "-",
             "Beschreibung", "hochwertige Küchen samt Backrohren sowie Geschirrspülern",
             "In der hauseigenen Tiefgarage sind 80 PKW Stellplätze vorhanden."),
    to_lines("Laufende Kosten", "Monatliche Kosten", "745,7 €", "Gesamtbelastung Netto", "677,91 €",
             "Miete", "581,07 €", "USt. Miete", "58,11 €", "Betriebskosten", "96,84 €",
             "USt. Betriebskosten", "9,68 €"),
    to_lines("Merkmale", "Baujahr 2017, Unterkellert, Parkett", "1 Terrasse 8,4 m²", "Tiefgarage"),
    to_lines("Gewerblich", "DECUS Immobilien GmbH"),
], extra='<script type="application/ld+json">{"telephone":"+4368120566112"}</script>')


def test_immoscout_ulmenhof(monkeypatch):
    monkeypatch.setattr(S, "get", lambda url, **kw: IS_ULMENHOF)
    l = Listing(source="immoscout", id="a", url="x", title="Gartenwohnung", postcode="2340",
                total_rent=745.7, area=55, rooms=2, contact_name="Michaela Samt", contact_company="DECUS")
    S.immoscout_details(l)
    assert l.rent_net == 581.07 and l.rent_vat == 58.11 and l.bk == 106.52
    assert l.contact_phone == "+43 68120566112"
    v = evaluate(l)
    assert v.dream and v.info["rent"] == 639.18
    assert "🍽 посудомийка" in v.pluses and "🚗 гараж" in v.pluses
    assert v.status == "check" and v.warnings == ["застава не вказана"]
    print(bot.format_message(l, v))


IS_ALTBAU = is_html([
    to_lines("Unbefristete Hauptmietwohnung mit Garten in 1210 Wien", "Kaution", "4.690,31 €"),
    to_lines("Laufende Kosten", "Miete", "1.042,29 €"),
    to_lines("Merkmale", "Baujahr 1899, Gepflegt", "Einbauküche, Badewanne"),
])


def test_immoscout_altbau_rejected(monkeypatch):
    monkeypatch.setattr(S, "get", lambda url, **kw: IS_ALTBAU)
    l = Listing(source="immoscout", id="b", url="x", title="Hauptmietwohnung", postcode="1210",
                total_rent=1042.29, area=77.81, rooms=2)
    v = evaluate(S.immoscout_details(l))
    assert v.status == "reject" and "будинок 1899 р." in v.reasons


IS_BM = is_html([
    to_lines("Erstbezug", "Kaution", "3 BM"),
    to_lines("Laufende Kosten", "Monatliche Kosten", "999 €", "Miete", "770,09 €", "USt. Miete", "77,01 €",
             "Betriebskosten", "138,09 €"),
    to_lines("Merkmale", "Baujahr 2026, Neubau, Erstbezug", "Einbauküche mit Geschirrspüler"),
])


def test_immoscout_deposit_bm(monkeypatch):
    monkeypatch.setattr(S, "get", lambda url, **kw: IS_BM)
    l = Listing(source="immoscout", id="c", url="x", title="Erstbezug", postcode="1030",
                total_rent=999, area=41.57, rooms=2)
    v = evaluate(S.immoscout_details(l))
    assert v.info["deposit"] == 2997 and v.status == "ok" and v.dream


# ---------- DER STANDARD (RSC) ----------
DS_ENTRY = {
    "__typename": "PropertyEntryResponse", "id": "15132288", "title": "WOHNEN NÄHE U4 HÜTTELDORF",
    "description": "$5f",
    "advertiser": {"company": {"name": "FAMILIENWOHNBAU"},
                   "contactPerson": {"firstname": "Anna", "lastname": "Muster", "email": "a@fwb.at", "phone": "01 12345"}},
    "media": {"images": [{"path": "https://ic.ds.at/x.jpg"}]},
    "property": {
        "amenities": ["BALCONY", "PARKING_SPOT"],
        "areas": {"details": [{"kind": "LIVING_SPACE", "value": 51}, {"kind": "ROOM_COUNT", "value": 2}],
                  "main": {"kind": "LIVING_SPACE", "value": 51}},
        "condition": {"buildingType": "NEW_BUILDING", "yearOfConstruction": 2021},
        "costs": {"details": [
            {"kind": "SUM_OF_RENT", "net": 1057.32, "gross": None, "text": None},
            {"kind": "OPERATING_COSTS", "net": 280.0, "gross": None, "text": None},
            {"kind": "DEPOSIT", "net": 3500, "gross": None, "text": None},
            {"kind": "MONTHLY_COSTS", "gross": 1163.05, "net": None, "text": None},
            {"kind": "FREE_TEXT_PRICE", "text": "Finanzierungsbeitrag: € 3 227,50", "net": None, "gross": None}],
            "main": {"value": 1163.05}},
        "location": {"city": "Wien", "street": "Auhofstraße 196/4", "zipCode": "1130"}}}


def ds_html(entry, desc="Küche mit Geschirrspüler. Tiefgarage."):
    rsc = "59:" + json.dumps([entry], ensure_ascii=False, separators=(",", ":")) + f"\n5f:T{len(desc.encode()):x}," + desc
    chunks = [rsc[i:i + 500] for i in range(0, len(rsc), 500)]
    return "".join(f"<script>self.__next_f.push([1,{json.dumps(c)}])</script>" for c in chunks)


def test_derstandard(monkeypatch):
    monkeypatch.setattr(S, "get", lambda url, **kw: ds_html(DS_ENTRY))
    found = S.derstandard_search("wien", 1)
    assert len(found) == 1 and found[0].postcode == "1130"
    l = S.derstandard_details(found[0])
    assert l.rent_net == 777.32 and l.year == 2021 and l.contact_email == "a@fwb.at"
    v = evaluate(l)
    assert round(v.info["rent"]) == 855 and v.info["deposit"] == 3500
    assert "🍽 посудомийка" in v.pluses and "🚗 гараж" in v.pluses
    assert any("Genossenschaft" in w for w in v.warnings)
    print(bot.format_message(l, v))


# ---------- wohnnet (HTML) ----------
WN_LIST = """
<a href="/immobilien/mietwohnung-1100-wien-favoriten-miete-2-zimmer-297000001" data-id="297000001" data-title="Neubau 2 Zimmer">
 <div class="realty-detail-title-address"><p class="h4">Neubau 2 Zimmer</p><i></i> 1100 Wien </div>
 <div class="realty-detail-area-rooms"><div><b>52</b> m²</div><div><b>2</b> Zimmer</div><div><b>920 €</b></div></div>
 <div class="realty-detail-agency"> Muster Immobilien </div></a>"""
WN_DETAIL = to_lines("Neubau 2 Zimmer", "Kosten", "Mietpreis", "899,00 €", "Betriebskosten", "95,89 €",
                     "MWSt.", "81,73 €", "Kaution Info", "3,00", "Eckdaten", "Baujahr", "2019", "Beschreibung", "Erstbezug, Einbauküche mit Geschirrspüler",
                     "Anbieter", "Muster Immobilien", "Max Muster", "Ähnliche Objekte", "Altbauwohnung")


def test_wohnnet(monkeypatch):
    monkeypatch.setattr(S, "get", lambda url, **kw: WN_LIST if "sortierung" in str(kw) else WN_DETAIL)
    found = S.wohnnet_search("wien", 1)
    assert found[0].postcode == "1100" and found[0].area == 52 and found[0].total_rent == 920
    l = S.wohnnet_details(found[0])
    assert l.contact_name == "Max Muster" and l.contact_company == "Muster Immobilien"
    assert l.rent_net == 721.38 and l.bk == 105.48 and l.total_rent == 899
    v = evaluate(l)
    assert round(v.info["rent"]) == 794 and v.dream and v.info["year"] == 2019
    assert v.status == "ok" and v.info["deposit"] == 2697     # 3 × 899; «Altbau» зі схожих оголошень не заважає


# ---------- правила відсіву ----------
def base(**kw):
    d = dict(source="willhaben", id="x", url="u", title="t", postcode="1100", rent_net=800, rent_vat=80,
             total_rent=1000, area=50, rooms=2, deposit=3000, year=2010, text="Geschirrspüler")
    d.update(kw)
    return Listing(**d)


def test_rules():
    assert evaluate(base()).status == "ok"
    assert evaluate(base(rent_net=950, rent_vat=95)).status == "reject"
    assert evaluate(base(area=38)).status == "reject"
    assert evaluate(base(rooms=4)).status == "reject"
    assert evaluate(base(year=1975)).status == "reject"
    assert evaluate(base(deposit=6500)).status == "reject"
    assert evaluate(base(postcode="2500")).status == "reject"           # Baden — поза зоною
    assert evaluate(base(postcode="8045")).status == "reject"           # Graz
    assert evaluate(base(postcode="2340")).status == "ok"               # Mödling
    assert evaluate(base(text="Geschirrspüler. Möbelablöse € 5.500")).status == "reject"
    assert evaluate(base(text="Geschirrspüler. Küchenablöse 2.500 €")).status == "ok"
    assert evaluate(base(text="Geschirrspüler. Nur mit Wiener Wohn-Ticket")).status == "reject"
    assert evaluate(base(text="Geschirrspüler. Schlafzimmer mit eigenem Bad")).status == "reject"
    assert evaluate(base(text="Geschirrspüler. Wohnungstausch gesucht")).status == "reject"
    assert evaluate(base(contact_company="Tauschwohnung GmbH")).status == "reject"
    assert evaluate(base(text="Geschirrspüler. Finanzierungsbeitrag: € 18.000")).status == "reject"
    assert evaluate(base(text="Küche ohne Geschirrspüler")).status == "reject"
    v = evaluate(base(text="Küche mit Geschirrspüleranschluss"))
    assert v.status == "check" and "підключення" in v.warnings[0]
    assert evaluate(base(year=None, text="Geschirrspüler, schöner Altbau")).status == "reject"
    v = evaluate(base(rent_net=None, rent_vat=None, total_rent=1200))
    assert v.status == "check" and "оренда без комуналки не вказана окремо" in v.warnings
    assert evaluate(base(rent_net=700, rent_vat=70)).dream


def test_quick_reject_and_fingerprint():
    assert quick_reject(base()) == []
    assert "локація" in quick_reject(base(postcode="8045"))
    assert "ціна" in quick_reject(base(total_rent=1600))
    a = base(source="willhaben", area=46.82, total_rent=988)
    b = base(source="immoscout", area=47, total_rent=990)
    assert fingerprint(a) == fingerprint(b)


def test_main_flow(monkeypatch, tmp_path):
    """Повний прогін: дубль між сайтами надсилається лише один раз, відсіяне — не надсилається."""
    monkeypatch.setattr(bot, "STATE_FILE", tmp_path / "seen.json")
    monkeypatch.setattr(bot, "polite_pause", lambda: None)
    sent = []
    monkeypatch.setattr(bot, "tg_send", lambda text, preview="": sent.append(text))
    good = base(source="willhaben", id="1", title="Gut", total_rent=988, area=47)
    dup = base(source="immoscout", id="2", title="Gut (дубль)", total_rent=990, area=47)
    bad = base(source="willhaben", id="3", title="Baden", postcode="2500")
    monkeypatch.setattr(bot, "collect", lambda st, mode: [("willhaben:1", good), ("immoscout:2", dup),
                                                          ("willhaben:3", bad)])
    monkeypatch.setitem(S.SOURCES, "willhaben", lambda l: l)
    monkeypatch.setitem(S.SOURCES, "immoscout", lambda l: l)
    bot.main()
    listing_msgs = [m for m in sent if "Відкрити оголошення" in m]
    assert len(listing_msgs) == 1 and "Gut" in listing_msgs[0]
    st = json.loads((tmp_path / "seen.json").read_text())
    assert st["seen"]["immoscout:2"]["s"] == "d" and st["seen"]["willhaben:3"]["s"] == "r"
