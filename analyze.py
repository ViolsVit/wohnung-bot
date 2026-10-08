"""
Логіка фільтрації: з полів і тексту оголошення визначає, чи підходить квартира.
Результат: status = "ok" | "check" (підходить, але є ⚠️) | "reject".
"""
import re
from dataclasses import dataclass, field
from typing import Optional

import config


@dataclass
class Listing:
    source: str                 # willhaben | immoscout | derstandard | wohnnet
    id: str
    url: str
    title: str = ""
    postcode: str = ""
    location: str = ""
    address: str = ""
    # --- гроші (€/міс.)
    rent_net: Optional[float] = None     # Miete без USt і без комуналки
    rent_vat: Optional[float] = None     # USt на Miete, якщо сайт її показує
    rent_gross: Optional[float] = None   # Miete з USt (якщо сайт дає одразу)
    bk: Optional[float] = None           # Betriebskosten — обслуговування будинку (з USt), без опалення/світла
    total_rent: Optional[float] = None   # загальна сума на місяць (усе разом, як на сайті)
    heating: Optional[float] = None      # Heizkosten, якщо сайт показує окремо (у ліміт НЕ входять)
    deposit: Optional[float] = None
    # --- квартира
    area: Optional[float] = None
    rooms: Optional[float] = None
    year: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    image: str = ""
    text: str = ""              # увесь текст оголошення (опис + характеристики)
    features: list = field(default_factory=list)   # явні ознаки з полів (Garage, Terrasse …)
    # --- контакт
    contact_name: str = ""
    contact_company: str = ""
    contact_phone: str = ""
    contact_email: str = ""


@dataclass
class Verdict:
    status: str                  # ok | check | reject
    reasons: list = field(default_factory=list)   # чому відсіяно
    warnings: list = field(default_factory=list)  # що перевірити вручну
    pluses: list = field(default_factory=list)    # ⭐ бонуси
    info: dict = field(default_factory=dict)
    dream: bool = False          # 💚 оренда ≤ TARGET_RENT


# ---------- допоміжні ----------

def eur(v) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def parse_num(s) -> Optional[float]:
    """'4.690,31' -> 4690.31 ; '789,74' -> 789.74 ; '988.0' -> 988.0 ; '3.000' -> 3000 ; '37 227,50' -> 37227.5"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).replace("€", "").replace("EUR", "").replace("\xa0", "").replace(" ", "").replace(" ", "")
    s = s.strip().rstrip(",.-")
    if not s:
        return None
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def monthly_cost(l: Listing) -> Optional[float]:
    """Сума для ліміту: Miete + Betriebskosten з USt, без опалення та інших доплат.
    Якщо сайт дав і складові, і загальну суму, беремо МЕНШЕ з двох:
      - загальна більша → у ній є щось понад Miete+BK (Heizung, Garage, Möbel…) — у ліміт не йде;
      - загальна менша → найчастіше приватний власник без USt, і наш розрахунок +10 % завищений."""
    rent, _ = rent_with_tax(l)
    comps = round(rent + l.bk, 2) if rent is not None and l.bk else None
    total = round(l.total_rent - (l.heating or 0), 2) if l.total_rent else None
    if comps is not None and total is not None:
        return min(comps, total)
    if comps is not None:
        return comps
    if total is not None:
        return max(total, rent or 0)
    return rent


def total_gap(l: Listing) -> float:
    """Різниця між загальною сумою з сайту (без окремо вказаного опалення) і Miete+BK."""
    rent, _ = rent_with_tax(l)
    if not (l.total_rent and rent is not None and l.bk):
        return 0.0
    return round(l.total_rent - (l.heating or 0) - (rent + l.bk), 2)


def rent_with_tax(l: Listing):
    """Повертає (оренда з USt без комуналки, чи_оцінено)."""
    if l.rent_gross:
        return l.rent_gross, False
    if l.rent_net:
        if l.rent_vat is not None:
            return round(l.rent_net + l.rent_vat, 2), False
        return round(l.rent_net * (1 + config.VAT_RATE), 2), True
    return None, False


MONTHS = (r"(?:j[aä]nner|januar|feber|februar|m[aä]rz|april|mai|juni|juli|august|september|oktober|"
          r"november|dezember)")

NUM = r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"

RX = {
    "wohnticket": re.compile(r"wohn\s*-?\s*ticket|vormerkschein", re.I),
    "exclude": re.compile(
        r"wohnungstausch|tauschwohnung|\btausch\b|wg-zimmer|zimmer in (einer )?wg|untermiete|"
        r"kurzzeitmiete|ferienwohnung|studentenheim|studentenapartment|nur für student|"
        r"seniorenwohnung|betreutes wohnen|anlegerwohnung", re.I),
    "ensuite": re.compile(
        r"en[\s-]?suite|schlafzimmer mit (eigenem |integriertem |angrenzendem )?(bad|dusche|badezimmer)|"
        r"(bad|dusche|badezimmer) im schlafzimmer|offene[sr]? (bad|dusche)|bad direkt vom schlafzimmer", re.I),
    "dishwasher": re.compile(r"geschirrsp[üu]l(?!er?-?anschlu|maschinenanschlu)|sp[üu]lmaschine(?!nanschlu)|dishwasher", re.I),
    "dishwasher_conn": re.compile(r"(geschirrsp[üu]l\w*|sp[üu]lmaschinen?)-?anschlu", re.I),
    "no_dishwasher": re.compile(r"(ohne|kein(en)?)\s+(geschirrsp[üu]l|sp[üu]lmaschine)", re.I),
    "garage": re.compile(r"tiefgarage|garage|carport", re.I),
    "parking": re.compile(r"stellpl[aä]tz|parkpl[aä]tz|parking", re.I),
    # Außenflächen: окремо Terrasse / Garten / Balkon / Loggia; спільні (Gemeinschafts-, allgemein) — не рахуємо
    "terrace": re.compile(r"(?<![a-zäöüß])(?:dach|garten|eck|gemeinschafts)?terrass(?:e|en)?\b|\bterrace\b", re.I),
    "garden": re.compile(r"(?<![a-zäöüß])(?:eigen|privat|haus|gemeinschafts)?garten(?:anteil|fläche|nutzung)?\b|\bgarden\b", re.I),
    "balcony": re.compile(r"(?<![a-zäöüß])balkon(?:e)?\b|\bbalcony\b", re.I),
    "loggia": re.compile(r"(?<![a-zäöüß])loggi(?:a|en)\b", re.I),
    "shared": re.compile(r"gemeinschafts|allgemein|gemeinsam|für alle (?:bewohner|mieter)", re.I),
    "altbau": re.compile(r"\baltbau|stilaltbau|gründerzeit|jahrhundertwende|OLD_BUILDING", re.I),
    "neubau": re.compile(r"\bneubau|erstbezug|neu errichtet|NEW_BUILDING", re.I),
    "year": re.compile(r"(?:baujahr|errichtet|erbaut|fertiggestellt)\s*(?:im\s+jahr(?:e)?\s*|:|\s)\s*(1[89]\d\d|20\d\d)", re.I),
    "deposit_months": re.compile(
        r"kaution\s*[:\-]?\s*(?:von\s*|in\s*höhe\s*von\s*)?(\d+(?:[.,]\d+)?)\s*"
        r"(?:brutto|netto|gesamt)?\s*-?\s*(?:monats?-?(?:mieten|miete|gesamtmieten|bruttomieten)|bmm?\b)", re.I),
    "deposit_months2": re.compile(r"(\d+)\s*(?:brutto)?monats?mieten?\s*(?:als\s*)?kaution", re.I),
    "deposit_eur": re.compile(r"kaution\s*[:\-]?\s*(?:von\s*|in\s*höhe\s*von\s*|ca\.\s*)?(?:€|eur(?:o)?)?\s*" + NUM + r"\s*(?:€|eur|euro|,-)?", re.I),
    "energy_extra": re.compile(
        r"kaltmiete|(?:heiz|strom|energie|warmwasser)\w*[^.\n]{0,80}?nicht\s+(?:inkludiert|inbegriffen|enthalten|inkl)|"
        r"(?:zzgl|zuzüglich|exkl|exklusive)\.?\s*(?:der\s+)?(?:heiz|strom|energie|warmwasser)", re.I),
    "energy_incl": re.compile(
        r"warmmiete|(?:inkl|inklusive|einschließlich)\.?\s*(?:der\s+)?(?:heiz|heizung|warmwasser)|"
        r"heiz(?:ung|kosten)[^.\n]{0,40}?(?:inkludiert|inkl\.|inbegriffen|enthalten)", re.I),
    "available": re.compile(
        r"(?:verfügbar(?:keit)?|beziehbar(?:keit)?|bezugsfertig|bezugsfrei|frei|bezug(?:stermin)?|übergabe|"
        r"mietbeginn|einzug(?:stermin)?|available\w*)(?:\s*(?:ab|per|mit|zum|ist|:|-))*\s*"
        r"(ab\s+sofort|sofort|nach\s+(?:vereinbarung|absprache)|\d{4}-\d{2}-\d{2}|"
        r"\d{1,2}\.\s?\d{1,2}\.\s?(?:\d{4}|\d{2})?|"
        r"(?:anfang|mitte|ende)?\s*(?:\d{1,2}\.\s*)?" + MONTHS + r"(?:\s+\d{4})?)", re.I),
    "available_rev": re.compile(r"\b(sofort)\s+(?:beziehbar|bezugsfertig|verfügbar|frei|zu beziehen)", re.I),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I),
    "phone": re.compile(
        r"\b(?:tel(?:efon|\.)?|mobil|handy|phone|t)\s*[.:]?\s*((?:\+|00)?\d[\d\s/()-]{7,18}\d)|"
        r"((?:\+43|0043)[\s/()-]*\d[\d\s/()-]{6,16}\d|\b06\d{2}[\s/-]*\d[\d\s/-]{5,12}\d)", re.I),
    "extra_optional": re.compile(r"optional|anmietbar|zusätzlich|gegen aufpreis|zzgl|zuzüglich|separat|extra", re.I),
    # Газове опалення — позначаємо ❗❗❗ (ви такі квартири оминаєте)
    "gas": re.compile(
        r"(?<![a-zäöüß])(?:erd)?gas[\s-]?(?:etagen|zentral|kombi|brennwert|wand|einzelofen)?[\s-]?"
        r"(?:heizung|therme|heizkessel|kessel|ofen|öfen)|(?<![a-zäöüß])kombitherme|"
        r"(?:heizung|heizungsart|beheizung|energieträger|befeuerung|heizsystem|wärmeerzeugung|heating)\w*"
        r"[^.\n]{0,30}?(?<![a-zäöüß])(?:erd)?gas\b", re.I),
    # Електроопалення (Wärmepumpe не рахуємо — вона економна)
    "electric": re.compile(
        r"(?<![a-zäöüß])(?:elektro|strom|e)[\s-]?(?:direkt|zentral|fußboden|fussboden)?[\s-]?heiz(?:ung|ungen|körper|er|kessel)|"
        r"nachtspeicher(?:ofen|öfen|heizung)?|infrarot[\s-]?(?:heizung|paneel|panele|heizkörper)|"
        r"(?:heizung|heizungsart|beheizung|energieträger|heizsystem|heating)\w*[^.\n]{0,25}?"
        r"(?<![a-zäöüß])(?:strom|elektrisch|elektro)\b|electric heating", re.I),
    # Заборона тварин
    "no_pets": re.compile(
        r"(?<![a-zäöüß])(?:keine|kein|ohne)\s+(?:haus|klein|groß)?(?:tiere|tier|tierhaltung|hunde|hund|katzen)\b|"
        r"(?<![a-zäöüß])(?:haus|klein)?(?:tiere?|tierhaltung|hunde?|hundehaltung|katzen)"
        r"(?:\s+(?:und|oder|bzw\.?)\s+\w+)?\s*(?:sind|ist|:|-)?\s*(?:leider\s+|grundsätzlich\s+|ausdrücklich\s+)?"
        r"(?:nicht\s+(?:erlaubt|gestattet|gewünscht|erwünscht|möglich|zulässig|gestattet)|unerwünscht|untersagt|"
        r"verboten|ausgeschlossen|nein\b)|"
        r"tierhaltung\s+(?:wird\s+)?nicht\s+(?:akzeptiert|geduldet)|nichtraucher\s+(?:und|&)\s+(?:ohne|keine)\s+(?:haus)?tiere|"
        r"\bno\s+(?:pets|dogs|animals)\b|pets\s+(?:are\s+)?not\s+allowed|"
        r"(?:pets?|haustier\w*|tierhaltung)\s*[:=]\s*(?:nein|no|false|nicht\s+erlaubt)\b", re.I),
    "pets_ok": re.compile(
        r"(?<![a-zäöüß])(?:haus|klein)?(?:tiere?|tierhaltung|hunde?)\s+(?:sind\s+|ist\s+)?(?:herzlich\s+)?"
        r"(?:erlaubt|gestattet|willkommen|möglich)|haustierfreundlich|hundefreundlich|"
        r"(?:pets?|haustier\w*|tierhaltung)\s*[:=]\s*(?:ja|yes|true|erlaubt)\b|pets\s+(?:are\s+)?(?:allowed|welcome)", re.I),
    "pets_ask": re.compile(r"(?:haus)?(?:tiere?|tierhaltung|hunde?)[^.\n]{0,25}?(?:nach|auf)\s+(?:absprache|anfrage|vereinbarung)|"
                           r"(?:nach|auf)\s+(?:absprache|anfrage)[^.\n]{0,25}?(?:haus)?tiere?", re.I),
    # Рієлтор приймає запити лише через форму / сайт
    "form_only": re.compile(
        r"(?:anfragen?|kontaktaufnahme|besichtigungsanfragen?|terminanfragen?)[^.\n]{0,60}?(?:ausschlie(?:ß|ss)lich|nur)"
        r"[^.\n]{0,40}?(?:kontaktformular|formular|anfrageformular|über\s+(?:die\s+|unsere\s+)?(?:plattform|website|"
        r"webseite|homepage|willhaben|immoscout|portal|seite))|"
        r"(?:ausschlie(?:ß|ss)lich|nur)\s+(?:über|via|per|mittels)\s+(?:das\s+|unser\s+|dem\s+)?(?:kontakt|anfrage)?formular|"
        r"e-?mail-?anfragen\s+(?:werden|können)\s+(?:leider\s+)?nicht|anfragen\s+per\s+e-?mail\s+(?:werden|können)\s+(?:leider\s+)?nicht|"
        r"bitte\s+(?:nutzen|verwenden|benutzen)\s+sie\s+(?:ausschlie(?:ß|ss)lich\s+|nur\s+)?(?:das|unser)\s+(?:kontakt|anfrage)?formular|"
        r"only\s+(?:via|through)\s+(?:the\s+|our\s+)?(?:contact\s+)?form", re.I),
    "no_gas": re.compile(r"(?:kein|keine|ohne)\s+gas|gasfrei|(?:kein|keine|ohne)\s+gasanschluss", re.I),
    "abloese_free": re.compile(r"(keine|ohne)\s+(möbel|küchen|investitions)?ablöse|ablösefrei", re.I),
    "abloese_eur": re.compile(r"(?:möbel|küchen|investitions|einrichtungs)?abl[öo]se[^\d€\n]{0,40}(?:€|eur(?:o)?)?\s*" + NUM, re.I),
    "abloese_any": re.compile(r"abl[öo]se", re.I),
    "finanz": re.compile(r"(?:finanzierungsbeitrag|eigenmittel(?:anteil)?|baukostenbeitrag|grundkostenbeitrag)[^\d€\n]{0,40}(?:€|eur(?:o)?)?\s*" + NUM, re.I),
}


def quote_around(text: str, m, width: int = 110) -> str:
    """Коротка цитата з оголошення навколо знахідки (у межах речення)."""
    start = max(text.rfind(". ", 0, m.start()) + 1, text.rfind("\n", 0, m.start()), text.rfind("! ", 0, m.start()) + 1) + 1
    ends = [i for i in (text.find(". ", m.end()), text.find("\n", m.end()), text.find("! ", m.end())) if i != -1]
    if text.rstrip().endswith(".") and not ends:
        ends = [len(text.rstrip()) - 1]
    end = min(ends) if ends else len(text)
    pre = ""
    if end - start > width and m.start() - start > 25:     # довге речення — починаємо ближче до знахідки
        start = text.rfind(" ", start, m.start() - 20) + 1
        pre = "… "
    q = " ".join(text[start:end].split())
    if len(q) > width:
        q = q[:width].rsplit(" ", 1)[0] + " …"
    return pre + q


MONTH_NUM = {"jän": 1, "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5, "jun": 6, "jul": 7, "aug": 8,
             "sep": 9, "okt": 10, "nov": 11, "dez": 12}


def move_in_date(avail, today=None):
    """Перетворює «01.11.2026», «Mitte Dezember 2026», «2027-01-01» на дату. «ab sofort» → сьогодні. Невідоме → None."""
    import datetime as _dt
    if not avail:
        return None
    today = today or _dt.date.today()
    a = avail.lower().strip()
    if "sofort" in a:
        return today
    if "vereinbarung" in a or "absprache" in a:
        return None

    def mk(y, mo, d):
        if y is None:
            y = today.year + (1 if mo < today.month - 1 else 0)
        elif y < 100:
            y += 2000
        try:
            return _dt.date(y, mo, max(1, min(d, 28 if mo == 2 else 30)))
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})\.\s?(\d{1,2})\.?\s?(\d{2,4})?", a)
    if m:
        return mk(int(m.group(3)) if m.group(3) else None, int(m.group(2)), int(m.group(1)))
    m = re.search(r"(anfang|mitte|ende)?\s*(?:(\d{1,2})\.\s*)?(j[aä]n|feb|m[aä]r|apr|mai|jun|jul|aug|sep|okt|nov|dez)\w*"
                  r"(?:\s+(\d{4}))?", a)
    if m:
        key = m.group(3).replace("jan", "jan")
        mo = MONTH_NUM.get(key, MONTH_NUM.get(key.replace("a", "ä")))
        day = int(m.group(2)) if m.group(2) else {"anfang": 1, "mitte": 15, "ende": 28}.get(m.group(1), 1)
        return mk(int(m.group(4)) if m.group(4) else None, mo, day)
    return None


def norm_available(s: str) -> str:
    s = " ".join(s.split()).strip(" .,")
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    if re.fullmatch(r"(ab\s+)?sofort", s, re.I):
        return "ab sofort"
    return s


# Додаткові щомісячні витрати понад Miete + Betriebskosten (у ліміт не входять, показуються окремо)
EXTRAS = [
    ("Heizkosten", r"heiz(?:ungs)?kosten(?:\s*-?\s*akonto)?|heizungsakonto|heizung"),
    ("Warmwasser", r"warmwasser(?:kosten)?"),
    ("Strom", r"stromkosten|strom"),
    ("Garage/Stellplatz", r"(?:tief)?garagen(?:stell)?platz|(?:tief)?garage|(?:pkw-?)?stellplatz|parkplatz|carport"),
    ("Möbelmiete", r"möbel(?:miete|nutzung|pauschale)"),
    ("Lift", r"liftkosten|aufzugskosten"),
    ("Internet/TV", r"internet(?:pauschale)?|kabel-?tv"),
]
EXTRA_AMOUNT = re.compile(r"[^\d€\n.;]{0,45}?(?:€|eur(?:o)?)?\s*" + NUM + r"\s*(?:€|eur(?:o)?|,-)?", re.I)


def find_extras(text: str) -> list:
    """[(назва, сума або None, цитата)] — лише те, що прямо написано в оголошенні."""
    out, seen = [], set()
    for name, pat in EXTRAS:
        for m in re.finditer(r"(?<![a-zäöüß])(?:" + pat + r")", text, re.I):
            tail = text[m.end():m.end() + 60]
            am = EXTRA_AMOUNT.match(tail)
            amount = parse_num(am.group(1)) if am else None
            if amount is not None and not (5 <= amount <= 400):
                amount = None                       # не схоже на щомісячну доплату
            if amount is not None and re.search(r"kauf|einmalig|ablöse|m²|m2|qm", text[m.start():m.end() + 70], re.I):
                amount = None
            quote = quote_around(text, m)
            if amount is None and not RX["extra_optional"].search(quote):
                continue                            # просто згадка (напр. «Garage im Haus») — не витрата
            if name in seen:
                continue
            seen.add(name)
            out.append((name, amount, quote))
            break
    return out


def first_amount(rx, text, min_value=50):
    for m in rx.finditer(text):
        v = parse_num(m.group(m.lastindex))
        if v is not None and v >= min_value:
            return v
    return None


def location_ok(postcode: str) -> bool:
    if not postcode or postcode in getattr(config, "EXCLUDED_POSTCODES", ()):
        return False
    if re.fullmatch(r"1[0-2]\d0", postcode) and 1010 <= int(postcode) <= 1230:
        return True
    return postcode in config.NOE_POSTCODES


def fingerprint(l: Listing) -> str:
    """Відбиток для пошуку дублікатів між сайтами: індекс + площа + ціна."""
    price = monthly_cost(l) or 0
    return f"{l.postcode}|{round(l.area or 0)}|{round(price / 25)}"


def quick_reject(l: Listing) -> list:
    """Відсів за даними зі списку результатів (без завантаження сторінки оголошення)."""
    r = []
    if not location_ok(l.postcode):
        r.append("локація")
    if l.rooms is not None and int(round(l.rooms)) not in config.ROOMS:
        r.append("кімнати")
    if l.area is not None and l.area < config.MIN_AREA:
        r.append("площа")
    if l.total_rent is not None and l.total_rent > config.MAX_TOTAL_HARD:
        r.append("ціна")
    head = f"{l.title} {l.contact_company}"
    if RX["wohnticket"].search(head) or RX["exclude"].search(head):
        r.append("заголовок")
    return r


# ---------- головна функція ----------

def evaluate(l: Listing) -> Verdict:
    v = Verdict(status="ok")
    t = l.text or ""

    # --- локація
    if not location_ok(l.postcode):
        v.reasons.append(f"локація {l.postcode or '?'} поза зоною")

    # --- дата заселення (як написано в оголошенні)
    m = RX["available"].search(t) or RX["available_rev"].search(t)
    v.info["available"] = norm_available(m.group(1)) if m else None

    # --- контакти з тексту, якщо сайт не дав їх окремими полями
    if not l.contact_email:
        m = RX["email"].search(t)
        if m and not re.search(r"noreply|no-reply|example", m.group(0), re.I):
            l.contact_email = m.group(0)
    if not l.contact_phone:
        for m in RX["phone"].finditer(t):
            raw = m.group(1) or m.group(2)
            digits = re.sub(r"\D", "", raw)
            if 9 <= len(digits) <= 15:
                l.contact_phone = raw.strip()
                break

    # --- кімнати / площа
    if l.rooms is not None and int(round(l.rooms)) not in config.ROOMS:
        v.reasons.append(f"{l.rooms:g} кімнат")
    if l.area is not None and l.area < config.MIN_AREA:
        v.reasons.append(f"площа {l.area:g} м²")
    if l.area is None:
        v.warnings.append("площа не вказана")

    # --- ціна: Miete (з USt) + Betriebskosten, БЕЗ Heizung / Warmwasser / Strom
    rent, estimated = rent_with_tax(l)
    v.info["rent"], v.info["rent_estimated"] = rent, estimated
    monthly = monthly_cost(l)
    v.info["monthly"] = monthly
    if monthly is not None:
        if monthly > config.MAX_RENT:
            net_basis = (l.rent_net or 0) + (l.bk or 0)
            if estimated and net_basis <= config.MAX_RENT:
                v.warnings.append(f"USt не вказана окремо: з податком ≈ {eur(monthly)}")
            else:
                v.reasons.append(f"Miete + Betriebskosten {eur(monthly)}")
        elif monthly <= config.TARGET_RENT:
            v.dream = True
        if rent is not None and not l.bk and not l.total_rent:
            v.warnings.append("Betriebskosten не вказані — сума буде вищою")
    else:
        v.warnings.append("ціна не вказана")

    # --- опалення / гаряча вода / світло (Betriebskosten їх зазвичай НЕ містять)
    v.info["energy"], v.info["energy_quote"] = None, ""
    for kind in ("extra", "incl"):
        m = RX["energy_" + kind].search(t)
        if m:
            v.info["energy"], v.info["energy_quote"] = kind, quote_around(t, m)
            break

    # --- газове / електричне опалення: ❗❗❗, і відсіюємо, якщо дорожче за TARGET_RENT
    m = RX["gas"].search(t)
    v.info["gas"] = quote_around(t, m) if m and not RX["no_gas"].search(t) else ""
    m = RX["electric"].search(t)
    v.info["electric"] = quote_around(t, m) if m else ""
    kinds = [k for k, key in (("Gasheizung", "gas"), ("Elektroheizung", "electric")) if v.info[key]]
    if kinds and monthly is not None and monthly > config.TARGET_RENT:
        v.reasons.append(f"{' + '.join(kinds)} і дорожче {config.TARGET_RENT} €")

    # --- лише через форму на сайті
    m = RX["form_only"].search(t)
    v.info["form_only"] = quote_around(t, m) if m else ""

    # --- тварини: у вас собака
    m = RX["no_pets"].search(t)
    if m:
        v.info["pets"] = ("no", quote_around(t, m))
        v.reasons.append(f"тварини заборонені: «{m.group(0)}»")
    elif (m := RX["pets_ok"].search(t)):
        v.info["pets"] = ("yes", quote_around(t, m))
    elif (m := RX["pets_ask"].search(t)):
        v.info["pets"] = ("ask", quote_around(t, m))
    else:
        v.info["pets"] = (None, "")

    # --- дата заселення: не пізніше LATEST_MOVE_IN
    latest = getattr(config, "LATEST_MOVE_IN", None)
    when = move_in_date(v.info.get("available"))
    v.info["move_in"] = when
    if latest and when and when > latest:
        v.reasons.append(f"заселення {v.info['available']} — пізніше {latest:%d.%m.%Y}")

    # --- додаткові витрати (не в ліміті) — для уточнення
    v.info["extras"] = find_extras(t)

    # --- виключення за змістом
    if RX["wohnticket"].search(t):
        v.reasons.append("потрібен Wohnticket")
    m = RX["exclude"].search(t + " " + l.contact_company)
    if m:
        v.reasons.append(f"не підходить: «{m.group(0)}»")
    m = RX["ensuite"].search(t)
    if m:
        v.reasons.append(f"санвузол у спальні: «{m.group(0)}»")

    # --- рік будівлі
    year = l.year
    if year is None:
        m = RX["year"].search(t)
        if m:
            year = int(m.group(1))
    if year is not None and not (1800 <= year <= 2035):
        year = None
    v.info["year"] = year
    if year is not None:
        if year < config.MIN_YEAR:
            v.reasons.append(f"будинок {year} р.")
    elif RX["altbau"].search(t) and not RX["neubau"].search(t):
        v.reasons.append("Altbau")
    elif RX["neubau"].search(t):
        v.info["year"] = "новобудова"
    else:
        v.warnings.append("рік будинку не вказаний")

    # --- застава
    base = l.total_rent or ((rent or 0) + (l.bk or 0)) or None
    deposit = l.deposit
    if deposit is not None and deposit < 20:          # «3» = 3 місячні оренди
        deposit = deposit * base if base else None
    if deposit is None:
        m = RX["deposit_months"].search(t) or RX["deposit_months2"].search(t)
        if m:
            months = parse_num(m.group(1))
            if months and base:
                deposit = months * base
    if deposit is None:
        deposit = first_amount(RX["deposit_eur"], t, min_value=100)
    v.info["deposit"] = deposit
    if deposit is not None:
        if deposit > config.MAX_DEPOSIT:
            v.reasons.append(f"застава {eur(deposit)}")
    else:
        v.warnings.append("застава не вказана")

    # --- Ablöse
    if RX["abloese_free"].search(t):
        abloese = 0.0
    else:
        abloese = first_amount(RX["abloese_eur"], t, min_value=100)
        if abloese is None and RX["abloese_any"].search(t):
            v.warnings.append("згадується Ablöse — уточнити суму")
    v.info["abloese"] = abloese
    if abloese and abloese > config.MAX_ABLOESE:
        v.reasons.append(f"Ablöse {eur(abloese)}")

    # --- Genossenschaft: фінансовий внесок
    fin = first_amount(RX["finanz"], t, min_value=500)
    if fin is not None:
        v.info["finanz"] = fin
        if fin > config.MAX_DEPOSIT:
            v.reasons.append(f"внесок у Genossenschaft {eur(fin)}")
        else:
            v.warnings.append(f"внесок у Genossenschaft {eur(fin)}")

    # --- посудомийка
    if RX["no_dishwasher"].search(t):
        v.reasons.append("без посудомийки")
    elif RX["dishwasher"].search(t):
        v.pluses.append("🍽 посудомийка")
    elif RX["dishwasher_conn"].search(t):
        v.warnings.append("є лише підключення для посудомийки")
    else:
        v.warnings.append("посудомийка не згадана")

    # --- бонуси
    feats = " ".join(l.features)
    if RX["garage"].search(feats) or RX["garage"].search(t):
        v.pluses.append("🚗 гараж")
    elif RX["parking"].search(feats) or RX["parking"].search(t):
        v.pluses.append("🅿️ паркомісце")
    for key, label in (("terrace", "🌿 Terrasse"), ("garden", "🌳 Garten"),
                       ("balcony", "☀️ Balkon"), ("loggia", "☀️ Loggia")):
        own = shared = False
        for src in (feats, t):
            for m in RX[key].finditer(src):
                before = re.split(r"[,.;:\n|]", src[max(0, m.start() - 30):m.start()])[-1]
                after = re.split(r"[,.;:\n|]", src[m.end():m.end() + 40])[0]
                ctx = before + " " + after
                if RX["shared"].search(m.group(0)) or RX["shared"].search(ctx):
                    shared = True
                else:
                    own = True
        if own:
            v.pluses.append(label)
        elif shared:
            v.pluses.append(label + " (allgemein)")

    if v.reasons:
        v.status = "reject"
    elif v.warnings:
        v.status = "check"
    return v
