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
from analyze import Listing, evaluate, fingerprint, quick_reject, rent_with_tax, total_gap

STATE_FILE = Path(__file__).parent / "state" / "seen.json"
DRY_RUN = os.getenv("DRY_RUN") == "1"
SEND_REJECTED = os.getenv("SEND_REJECTED") == "1"


def polite_pause():
    time.sleep(random.uniform(1.5, 3.5))


# =====================================================================
# Telegram
# =====================================================================

def listing_buttons(l: Listing) -> dict:
    """Кнопки під оголошенням. «Запит на перегляд» обробляє Cloudflare Worker (папка cloudflare/)."""
    row = []
    if getattr(config, "REQUEST_BUTTON", True):
        row.append({"text": "✉️ Запит на перегляд", "callback_data": "req"})
    row.append({"text": "🔗 Оголошення", "url": l.url})
    return {"inline_keyboard": [row]}


def tg_send(text: str, preview_url: str = "", buttons: dict = None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chats = [c.strip() for c in (os.getenv("TELEGRAM_CHAT_ID") or "").split(",") if c.strip()]
    if DRY_RUN or not token or not chats:
        print("-" * 60 + "\n" + html.unescape(re.sub(r"<[^>]+>", "", text)))
        return
    for chat in chats:
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
        if buttons:
            payload["reply_markup"] = buttons
        if preview_url:
            payload["link_preview_options"] = {"url": preview_url, "prefer_large_media": True,
                                               "show_above_text": True}
        else:
            payload["link_preview_options"] = {"is_disabled": True}
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=30)
        if not r.ok:
            print("Telegram помилка:", r.status_code, r.text[:300])
        time.sleep(1.1)   # ліміт Telegram ~1 повідомлення/сек у чат


def norm_phone_display(p: str) -> str:
    return S.norm_phone(p) if re.fullmatch(r"[\d\s/()+-]+", p or "") else p


def extra_lines(l: Listing, v, gap: float) -> list:
    """Короткий перелік того, що НЕ входить у ліміт: опалення, гараж, меблі …"""
    items, known = [], 0.0
    energy = v.info.get("energy")
    if l.heating:
        items.append(f"🔥 Heizkosten {eur(l.heating)}")
    elif energy == "extra":
        items.append("🔥 Heizung/Strom extra")
    elif energy == "incl":
        items.append("🔥 Heizung inkl.")
    else:
        items.append("🔥 Heizung ?")
    for name, amount, _q in v.info.get("extras") or []:
        if name == "Heizkosten" and (l.heating or energy):
            continue
        known += amount or 0
        items.append(f"{name} {eur(amount) if amount else '(сума ?)'}")
    rest = gap - known
    if rest > 2:
        items.append(f"+{eur(rest)} у Gesamtmiete не розписано")
    return items


def eur(v):
    return f"{v:,.0f} €".replace(",", " ") if v is not None else "?"


def format_message(l: Listing, v) -> str:
    e = html.escape
    out = []
    # --- червоні прапорці (найважливіше — першим)
    if v.info.get("form_only"):
        out += ["🛑🛑🛑 <b>ЛИШЕ ЧЕРЕЗ ФОРМУ НА САЙТІ</b> 🛑🛑🛑", f"<i>«{e(v.info['form_only'])}»</i>"]
    out += [f"❗❗❗ <b>{name}</b>: <i>«{e(v.info[key])}»</i>"
            for name, key in (("Gasheizung", "gas"), ("Elektroheizung", "electric")) if v.info.get(key)]

    head = [f"💚 <b>ДО {config.TARGET_RENT} €</b>"] if v.dream else []
    head.append({"ok": "✅ <b>Підходить</b>", "check": "⚠️ <b>Підходить, але уточнити</b>",
                 "reject": "❌ <b>Відсіяно</b>"}[v.status])
    out += [" · ".join(head), f"🏠 <b>{e(l.title.strip()[:120])}</b>", ""]

    # --- де + маршрут
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
        full = addr
    elif addr and addr.lower() not in place.lower():
        full = f"{addr}, {place}"
    else:
        full = place
    origin = f"{l.lat},{l.lon}" if l.lat and l.lon else quote_plus(full)
    maps = ("https://www.google.com/maps/dir/?api=1&travelmode=transit"
            f"&origin={origin}&destination={quote_plus(config.TRANSIT_DESTINATION)}")
    sub = getattr(config, "SUBURBS", {}).get(l.postcode)
    route = f"🚆 ≈{sub[1]} хв" if sub else "🚆 маршрут"
    out.append(f'📍 <b>{e(full)}</b> · <a href="{e(maps)}">{route}</a>')

    # --- гроші
    rent, est = v.info.get("rent"), v.info.get("rent_estimated")
    monthly = v.info.get("monthly")
    gap = total_gap(l)
    if rent and l.bk:
        if gap < -2:
            detail = f"Miete {eur(monthly - l.bk)} + BK {eur(l.bk)}, ohne USt"
        else:
            detail = f"Miete {eur(rent)}{' ≈' if est else ''} + BK {eur(l.bk)}"
    elif l.total_rent:
        detail = "Gesamtmiete"
    elif rent:
        detail = "лише Miete, BK ?"
    else:
        detail = ""
    out.append(f"💶 <b>{eur(monthly)}</b>" + (f" = {e(detail)}" if detail else ""))
    abl = v.info.get("abloese")
    out.append(f"🔐 Kaution {eur(v.info.get('deposit'))} · 🛋 Ablöse "
               + ("keine" if abl == 0 else eur(abl) if abl else "—"))

    # --- квартира
    year = v.info.get("year")
    flat = [f"{l.area:g} м²" if l.area else "? м²"]
    if l.rooms:
        flat.append(f"{l.rooms:g} Zi")
    flat.append("🏗 " + ("Neubau" if year == "новобудова" else str(year) if year else "?"))
    out.append("📐 " + " · ".join(flat))
    avail = v.info.get("available")
    pets = (v.info.get("pets") or (None, ""))[0]
    out.append(f"📅 {('ab ' + e(avail)) if avail and not avail.startswith('ab') else e(avail) if avail else '?'} · "
               + {"yes": "🐕 <b>erlaubt</b>", "ask": "🐕 nach Absprache", "no": "🚫 Tiere verboten"}.get(pets, "🐕 ?"))
    if v.pluses:
        out.append("⭐ " + " · ".join(v.pluses))

    # --- не в ліміті + що уточнити
    out += ["", "➕ " + e(" · ".join(extra_lines(l, v, gap)))]
    todo = list(v.warnings)
    if pets in (None, "ask"):
        todo.append("собака")
    todo.append("план: санвузол не в спальні")
    out.append("⚠️ " + e(" · ".join(todo)))
    if v.reasons:
        out.append("❌ " + e("; ".join(v.reasons)))

    # --- контакт
    who = " — ".join(x for x in (l.contact_name, l.contact_company) if x)
    out += ["", f"👤 {e(who) if who else '<i>ім' + chr(39) + 'я не вказане</i>'}"]
    contact = []
    if l.contact_phone:
        contact.append(f"📞 {e(norm_phone_display(l.contact_phone))}")
    if l.contact_email:
        contact.append(f"✉️ {e(l.contact_email)}")
    out.append(" · ".join(contact) if contact else "<i>📝 лише форма на сайті</i>")
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
    keep = 180 * 86400        # пам'ятаємо пів року
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
        if dup and dup["k"] != key:           # те саме житло: інший сайт або перевиставлене з новим id
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
        for f in {fp, fingerprint(l)}:       # відбиток і зі списку, і з деталей
            state["fp"][f] = {"t": time.time(), "k": key}
        print(f"  {v.status:6} {key} {l.title[:60]} {v.reasons or v.warnings}")
        if v.status != "reject" or SEND_REJECTED:
            ready.append((l, v))
        polite_pause()

    # 💚 спершу, потім ✅, потім ⚠️; всередині — дешевші вище
    order = {"ok": 0, "check": 1, "reject": 2}
    ready.sort(key=lambda x: (not x[1].dream, order[x[1].status], x[1].info.get("monthly") or 9999))
    for l, v in ready:
        tg_send(format_message(l, v), l.image or l.url, listing_buttons(l) if v.status != "reject" else None)

    save_state(state)
    print(f"Готово ({mode}): перевірено {checked}, надіслано {len(ready)}. "
          f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    sys.exit(main())
