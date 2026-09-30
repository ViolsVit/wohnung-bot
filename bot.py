"""
Wohnung-бот: збирає нові оголошення, фільтрує за вашими критеріями і надсилає у Telegram.

  python bot.py           — основні сайти (willhaben, ImmoScout24), запускається кожні 20 хв
  python bot.py --extra   — додаткові сайти (DER STANDARD, wohnnet), двічі на день

Змінні середовища:
  TELEGRAM_BOT_TOKEN   — токен від @BotFather
  TELEGRAM_CHAT_ID     — id чату (можна кілька через кому)
  DRY_RUN=1            — нічого не надсилати, лише друкувати в консоль
  SEND_REJECTED=1      — (для налагодження) надсилати й відсіяні з причиною
"""
import html
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

import config
import sources as S
from analyze import Listing, evaluate, fingerprint, quick_reject, rent_with_tax

STATE_FILE = Path(__file__).parent / "state" / "seen.json"
DRY_RUN = os.getenv("DRY_RUN") == "1"
SEND_REJECTED = os.getenv("SEND_REJECTED") == "1"


def polite_pause():
    time.sleep(random.uniform(1.5, 3.5))


# =====================================================================
# Telegram
# =====================================================================

def tg_send(text: str, preview_url: str = ""):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chats = [c.strip() for c in (os.getenv("TELEGRAM_CHAT_ID") or "").split(",") if c.strip()]
    if DRY_RUN or not token or not chats:
        print("-" * 60 + "\n" + html.unescape(re.sub(r"<[^>]+>", "", text)))
        return
    for chat in chats:
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
        if preview_url:
            payload["link_preview_options"] = {"url": preview_url, "prefer_large_media": True,
                                               "show_above_text": True}
        else:
            payload["link_preview_options"] = {"is_disabled": True}
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=30)
        if not r.ok:
            print("Telegram помилка:", r.status_code, r.text[:300])
        time.sleep(1.1)   # ліміт Telegram ~1 повідомлення/сек у чат


def eur(v):
    return f"{v:,.0f} €".replace(",", " ") if v is not None else "?"


def format_message(l: Listing, v) -> str:
    e = html.escape
    # --- заголовок-статус
    head = []
    if v.dream:
        head.append(f"💚 <b>ДО {config.TARGET_RENT} €</b>")
    head.append({"ok": "✅ <b>Підходить</b>", "check": "⚠️ <b>Підходить, але уточнити</b>",
                 "reject": "❌ <b>Відсіяно</b>"}[v.status])
    out = [" · ".join(head), f"<b>{e(l.title.strip()[:160])}</b>", ""]

    # --- 1. локація: вулиця + номер (якщо сайт дає), індекс, місто/район
    if l.postcode in config.NOE_POSTCODES:
        place = f"{l.postcode} {config.NOE_POSTCODES[l.postcode]}"
    elif l.location and l.postcode and l.postcode in l.location:
        place = l.location
    elif l.location:
        place = f"{l.postcode} {l.location}".strip()
    else:
        place = f"{l.postcode} Wien" if l.postcode.startswith("1") else l.postcode
    addr = (l.address or "").strip(" ,")
    if addr and l.postcode and l.postcode in addr:
        full = addr                                   # сайт уже дав повну адресу
    elif addr and addr.lower() not in place.lower():
        full = f"{addr}, {place}"
    else:
        full = place
    out.append(f"📍 <b>{e(full)}</b>")

    # --- 2. щомісячна сума (Miete + Betriebskosten, з USt)
    rent, est = v.info.get("rent"), v.info.get("rent_estimated")
    monthly = v.info.get("monthly")
    approx = " ≈" if est else ""
    if rent and l.bk:
        detail = f"Miete {eur(rent)}{approx} + Betriebskosten {eur(l.bk)}, inkl. USt"
    elif l.total_rent and rent:
        detail = f"Gesamtmiete; davon Miete {eur(rent)}{approx}, Betriebskosten nicht separat angegeben"
    elif l.total_rent:
        detail = "Gesamtmiete, Aufteilung nicht angegeben"
    elif rent:
        detail = f"nur Miete{approx}, Betriebskosten nicht angegeben"
    else:
        detail = ""
    out.append(f"💶 Щомісяця: <b>{eur(monthly)}</b>" + (f" — {e(detail)}" if detail else ""))
    energy, quote = v.info.get("energy"), v.info.get("energy_quote")
    if energy == "extra":
        out.append(f"      🔥 Heizung/Warmwasser/Strom <b>extra</b>: <i>«{e(quote)}»</i>")
    elif energy == "incl":
        out.append(f"      🔥 Heizung inkludiert: <i>«{e(quote)}»</i>")
    else:
        out.append("      🔥 Heizung/Strom: im Inserat nicht erwähnt")

    # --- 3. застава, 4. Ablöse
    out.append(f"🔐 Kaution: {eur(v.info.get('deposit'))}")
    abl = v.info.get("abloese")
    out.append("🛋 Ablöse: " + ("keine" if abl == 0 else eur(abl) if abl else "—"))

    # --- 5. площа, 6. будинок
    size = [f"{l.area:g} м²"] if l.area else ["площа ?"]
    if l.rooms:
        size.append(f"{l.rooms:g} Zimmer")
    out.append("📐 " + " · ".join(size))
    year = v.info.get("year")
    out.append("🏗 " + ("Neubau" if year == "новобудова" else f"Baujahr {year}" if year else "Baujahr ?"))

    # --- 7. бонуси
    if v.pluses:
        out.append("⭐ " + " · ".join(v.pluses))
    if v.warnings:
        out += ["", "⚠️ <b>Уточнити:</b>"] + [f"• {e(w)}" for w in v.warnings]
    if v.reasons:
        out += ["", "❌ " + e("; ".join(v.reasons))]

    # --- контакт
    who = " — ".join(x for x in (l.contact_name, l.contact_company) if x)
    out += ["", "👤 <b>Контакт</b>"]
    out.append(e(who) if who else "<i>ім'я не вказане</i>")
    if l.contact_phone:
        out.append(f"📞 {e(l.contact_phone)}")
    if l.contact_email:
        out.append(f"✉️ {e(l.contact_email)}")
    if not (l.contact_phone or l.contact_email):
        out.append("<i>телефон/пошта — через форму на сайті</i>")

    # --- посилання
    origin = f"{l.lat},{l.lon}" if l.lat and l.lon else quote_plus(full)
    maps = ("https://www.google.com/maps/dir/?api=1&travelmode=transit"
            f"&origin={origin}&destination={quote_plus(config.TRANSIT_DESTINATION)}")
    out += ["", f'🔗 <a href="{e(l.url)}"><b>Відкрити оголошення ({S.SOURCE_NAMES[l.source]})</b></a>',
            f'🚆 <a href="{e(maps)}">Маршрут до центру</a>',
            "🛁 <i>Гляньте план: санвузол не має бути в спальні</i>"]
    return "\n".join(out)


# =====================================================================
# Стан
# =====================================================================

def load_state():
    st = {}
    if STATE_FILE.exists():
        st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for k in ("seen", "fail", "fp", "retry"):
        st.setdefault(k, {})
    return st


def save_state(state):
    now = time.time()
    keep = 60 * 86400
    state["seen"] = {k: v for k, v in state["seen"].items() if now - v.get("t", now) < keep}
    state["fp"] = {k: v for k, v in state["fp"].items() if now - v.get("t", now) < keep}
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


# =====================================================================
# Головний цикл
# =====================================================================

def jobs_for(mode):
    if mode == "extra":
        j = [("derstandard", r, lambda r=r, p=p: S.derstandard_search(r, p)) for r, p in config.DERSTANDARD_REGIONS]
        j += [("wohnnet", r, lambda r=r, p=p: S.wohnnet_search(r, p)) for r, p in config.WOHNNET_REGIONS]
    else:
        j = [("willhaben", a, lambda a=a: S.willhaben_search(a)) for a in config.WILLHABEN_AREAS]
        j += [("immoscout", r, lambda r=r, p=p: S.immoscout_search(r, p)) for r, p in config.IMMOSCOUT_REGIONS]
    return j


def collect(state, mode) -> list:
    found = []
    for source, label, fn in jobs_for(mode):
        try:
            items = fn()
            print(f"{source} {label}: {len(items)} оголошень")
            found += items
            state["fail"][source] = 0
        except Exception as ex:  # noqa
            print(f"!! {source} {label}: {ex}")
            state["fail"][source] = state["fail"].get(source, 0) + 1
            if state["fail"][source] == 3:
                tg_send(f"🛠 Бот не може прочитати <b>{S.SOURCE_NAMES[source]}</b> уже 3 запуски поспіль. "
                        f"Можливо, сайт змінився або блокує запити.\n<code>{html.escape(str(ex))[:300]}</code>")
        polite_pause()
    uniq = {}
    for l in found:
        uniq.setdefault(f"{l.source}:{l.id}", l)
    return list(uniq.items())


def main():
    mode = "extra" if "--extra" in sys.argv else "main"
    state = load_state()
    if not state["seen"]:
        tg_send("🏠 <b>Бот пошуку квартири запущено!</b>\nЗараз надішлю актуальні варіанти, "
                "далі — лише нові оголошення.\n\n"
                f"💚 — оренда до {config.TARGET_RENT} €\n✅ — підходить за всіма критеріями\n"
                "⚠️ — підходить, але щось треба уточнити")
    items = collect(state, mode)
    new = [(k, l) for k, l in items if k not in state["seen"]]
    print(f"Нових: {len(new)}")

    ready, checked = [], 0
    for key, l in new:
        if quick_reject(l):
            state["seen"][key] = {"t": time.time(), "s": "r"}
            continue
        fp = fingerprint(l)
        dup = state["fp"].get(fp)
        if dup and not dup["k"].startswith(l.source + ":"):
            print(f"  дубль {key} = {dup['k']}")
            state["seen"][key] = {"t": time.time(), "s": "d"}
            continue
        if checked >= config.MAX_DETAILS_PER_RUN:
            continue     # решту перевіримо наступного запуску
        try:
            S.SOURCES[l.source](l)
        except Exception as ex:  # noqa
            print(f"  деталі {key}: {ex}")
            n = state["retry"].get(key, 0) + 1
            state["retry"][key] = n
            if n >= 3:
                state["seen"][key] = {"t": time.time(), "s": "e"}
                state["retry"].pop(key, None)
            continue
        checked += 1
        v = evaluate(l)
        state["seen"][key] = {"t": time.time(), "s": v.status[0]}
        state["fp"][fingerprint(l)] = {"t": time.time(), "k": key}
        print(f"  {v.status:6} {key} {l.title[:60]} {v.reasons or v.warnings}")
        if v.status != "reject" or SEND_REJECTED:
            ready.append((l, v))
        polite_pause()

    # 💚 спершу, потім ✅, потім ⚠️; всередині — дешевші вище
    order = {"ok": 0, "check": 1, "reject": 2}
    ready.sort(key=lambda x: (not x[1].dream, order[x[1].status], x[1].info.get("monthly") or 9999))
    for l, v in ready:
        tg_send(format_message(l, v), l.image or l.url)

    save_state(state)
    print(f"Готово ({mode}): перевірено {checked}, надіслано {len(ready)}. "
          f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    sys.exit(main())
