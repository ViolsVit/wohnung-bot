# 🏠 Wohnung-бот: пошук квартири у Відні → Telegram

| Що | Коли |
|---|---|
| **willhaben.at** + **ImmoScout24** | кожні 20 хв, 06:00–24:00 |
| **DER STANDARD Immobilien** + **wohnnet.at** | двічі на день: 07:30 і 19:30 |

Бот надсилає лише **нові** оголошення, які підходять. Якщо та сама квартира вже прийшла з іншого сайту, повторно її не надішле.

## Приклад повідомлення

```
💚 ДО 850 € · ✅ Підходить
Helle 2-Zimmer-Wohnung mit Loggia

📍 1210 Wien, 21. Bezirk, Floridsdorf · Koloniestraße 35
💶 Оренда з податком: 812 €
      + комуналка 119 € = разом 931 €
📐 47 м² · 2 кімн. · 🏗 2019
🔐 Застава: 3 000 € · 🛋 Ablöse: —
⭐ 🍽 посудомийка · 🚗 гараж · 🌿 тераса

👤 Контакт
Vivienne Spicak — IMV Immobilienmakler
📞 +43 15127690404
✉️ office@…

🔗 Відкрити оголошення (willhaben)
🚆 Маршрут до центру
🛁 Гляньте план: санвузол не має бути в спальні
```
Зверху — фото з оголошення. 💚 спочатку, далі від дешевших до дорожчих.

## Критерії

| Критерій | Як діє |
|---|---|
| **Оренда з податком (Miete + 10 % USt), без комуналки ≤ 1000 €** | ❌ якщо більше. Якщо USt не вказана окремо: ⚠️ з приблизною сумою |
| 💚 Оренда з податком ≤ 850 € | позначка і перше місце в черзі |
| Відень (1010–1230) або найближчі передмістя з S-Bahn | список у `config.py` → `NOE_POSTCODES`. Грац, Баден тощо відсіюються |
| Площа ≥ 41 м², 2–3 кімнати | ❌ якщо ні |
| Будинок 1980 р. або новіший | ❌ Altbau / Baujahr < 1980 · ⚠️ якщо рік невідомий |
| Застава ≤ 6000 € | рахує також «3 BM / 3 Bruttomonatsmieten» |
| Ablöse (меблі/кухня) ≤ 4000 € | ⚠️ якщо згадана без суми |
| Посудомийка | ✅ є · ⚠️ не згадана або лише «Anschluss» · ❌ «ohne Geschirrspüler» |
| Санвузол у спальні | ❌ якщо про це є в тексті. План усе одно гляньте |
| Wohnticket, Wohnungstausch, WG, Untermiete, Kurzzeit | ❌ |
| Внесок у Genossenschaft | ❌ якщо > 6000 € · ⚠️ якщо менше |
| Гараж / паркомісце / тераса | ⭐ бонус |

## Налаштування (~15 хв, один раз)

1. **Бот:** у Telegram → **@BotFather** → `/newbot` → скопіюйте **токен**.
2. **Чат:** створіть групу з хлопцем і додайте туди бота. Напишіть у групу будь-що, потім відкрийте `https://api.telegram.org/bot<ТОКЕН>/getUpdates` і знайдіть `"chat":{"id":-100…`. Це ваш **chat_id**.
3. **GitHub:** github.com → **New repository** → назва `wohnung-bot` → **Public** (див. «Хвилини GitHub» нижче) → Create → **uploading an existing file** → перетягніть усі файли й папки з архіву, включно з прихованою `.github` (на Mac показати її у Finder: `Cmd + Shift + .`) → **Commit changes**.
4. **Секрети:** Settings → Secrets and variables → Actions → New repository secret:
   `TELEGRAM_BOT_TOKEN` та `TELEGRAM_CHAT_ID`.
5. **Дозвіл:** Settings → Actions → General → Workflow permissions → **Read and write** → Save.
6. **Старт:** Actions → «Wohnung-бот (кожні 20 хв)» → **Run workflow**. Потім так само запустіть «додаткові сайти».

> **Оновлюєте попередню версію?** Завантажте всі файли поверх старих, **крім** `state/seen.json`, інакше бот повторно надішле вже бачені оголошення.

## Виправлені посилання для ручного пошуку

У ваших старих посиланнях були помилки. На willhaben стояв обов'язковий фільтр «гараж + сад», тому показувалось лише 8 оголошень, і сортування було за площею, а не від нових. На ImmoScout, крім Відня, був включений Грац, і тільки квартири з садом. Ціна в них рахувалась «разом з комуналкою», тому частина підходящих квартир відсікалась.

Ціну в посиланнях можна виставити лише «разом із комуналкою». Тому межа 1350 €: оренда 1000 € + комуналка. Точний відбір за орендою з податком робить бот.

**willhaben** (від нових):
- Відень: https://www.willhaben.at/iad/immobilien/mietwohnungen/mietwohnung-angebote?areaId=900&sort=1&rows=90&PRICE_TO=1350&ESTATE_SIZE/LIVING_AREA_FROM=41&NO_OF_ROOMS_BUCKET=2X2&NO_OF_ROOMS_BUCKET=3X3
- Відень, лише з гаражем: те саме + `&ESTATE_PREFERENCE=23`
- Mödling (Perchtoldsdorf, Brunn, Vösendorf…): замініть `areaId=900` на `areaId=317`
- Schwechat: `areaId=307` · Klosterneuburg: `areaId=321` · Korneuburg: `areaId=312`

**ImmoScout24:**
- Відень: https://www.immobilienscout24.at/regional/wien/wien/wohnung-mieten/aktualitaet?numberOfRoomsFrom=2&numberOfRoomsTo=3&primaryAreaFrom=41&primaryPriceTo=1350&isSocialHousing=false
- Mödling: https://www.immobilienscout24.at/regional/niederoesterreich/moedling/wohnung-mieten/aktualitaet?numberOfRoomsFrom=2&numberOfRoomsTo=3&primaryAreaFrom=41&primaryPriceTo=1350&isSocialHousing=false

**DER STANDARD:** https://immobilien.derstandard.at/suche/wien/mieten-wohnung?sorting=latest&priceTo=1350&areaFrom=41&roomCountFrom=2

**wohnnet:** https://www.wohnnet.at/immobilien/mietwohnungen/wien?sortierung=neueste-zuerst

## Як змінити критерії
`config.py` на GitHub → олівець ✏️ → Commit. Наприклад: `ROOMS = {2}`, `TARGET_RENT = 800`, додати індекс у `NOE_POSTCODES`.

## Корисно знати
- **Хвилини GitHub:** публічні репозиторії не мають ліміту, тому раджу Public. Токен лежить у секретах, у коді немає нічого особистого. У приватного репозиторію ліміт 2000 хв/міс., а бот із перевіркою кожні 20 хв може його перевищити. Якщо хочете Private, у `.github/workflows/wohnung-bot.yml` замініть `*/20` на `*/30`.
- GitHub іноді запускає бот на 5–15 хв пізніше. Це нормально.
- Якщо сайт змінить структуру або почне блокувати запити, бот сам напише «🛠 не може прочитати …».
- **Пауза:** Actions → потрібний workflow → ⋯ → Disable workflow.
- Телефон показується, коли сайт його віддає: willhaben і ImmoScout24 майже завжди, DER STANDARD іноді, wohnnet лише через форму. Email є, якщо сайт його показує.
