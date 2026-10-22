"""
Налаштування бота. Тут можна міняти критерії без зміни решти коду.
"""

# ---------- Ціна ----------
# Щомісячна сума = Miete (з 10% USt) + Betriebskosten, БЕЗ Heizung / Warmwasser / Strom
# Відень
TARGET_RENT = 850          # € — ідеал: позначка 🎯
MAX_RENT = 1000            # € — звичайна межа у Відні
PREMIUM_MAX_RENT = 1200    # € — виняток у Відні, лише якщо виконано ВСІ умови PREMIUM_* нижче
# Передмістя: лише зі своїм садом на 0 поверсі
SUBURB_MAX_RENT = 950      # €
VAT_RATE = 0.10            # ПДВ на житлову оренду в Австрії
# Швидкий відсів за сумою зі списку результатів (там інколи вже є й опалення, тому з запасом)
MAX_TOTAL_HARD = 1400

# ---------- Квартира ----------
MIN_AREA = 43              # м²
ROOMS = {2, 3}             # 2 = спальня + вітальня з кухнею. Приберіть 3, якщо трикімнатні не цікаві
MIN_YEAR = 2000            # будинок не старіший за цей рік
MAX_DEPOSIT = 6000         # € — застава (Kaution)
MAX_ABLOESE = 4000         # € — викуп меблів/кухні (Ablöse)
EXCLUDED_POSTCODES = {"1210"}

# Заселення: не пізніше цієї дати (рік, місяць, день). «ab sofort» і без дати — пропускаємо
import datetime as _dt
LATEST_MOVE_IN = _dt.date(2026, 12, 5)

# Газове / електричне опалення: True — відсіювати завжди
REJECT_GAS_ELECTRIC = True

# Максимум оголошень, які бот детально перевіряє за один запуск (щоб не навантажувати сайти)
MAX_DETAILS_PER_RUN = 40

# ---------- Географія і дорога ----------
# Час — орієнтовний «від дверей до дверей» громадським транспортом у будній ранок
# (пішки до зупинки + очікування + пересадки), хвилин: (до Wien Hauptbahnhof, до аеропорту VIE).
# Це оцінка, не Google: у кожному повідомленні є посилання на маршрут для перевірки.
STATION = "Wien Hauptbahnhof"
AIRPORT = "Flughafen Wien-Schwechat"
MAX_STATION_MINUTES = 40
MAX_AIRPORT_MINUTES = 60

VIENNA_TRAVEL = {   # індекс: (Hbf, VIE)
    "1010": (25, 40), "1020": (25, 40), "1030": (20, 35), "1040": (15, 35), "1050": (20, 40),
    "1060": (25, 45), "1070": (25, 45), "1080": (30, 50), "1090": (30, 45), "1100": (15, 35),
    "1110": (25, 35), "1120": (20, 40), "1130": (35, 55), "1140": (40, 60), "1150": (25, 45),
    "1160": (35, 55), "1170": (35, 55), "1180": (35, 55), "1190": (40, 55), "1200": (30, 45),
    "1210": (35, 50), "1220": (35, 50), "1230": (30, 50),
}

# Передмістя: індекс → (назва, Hbf, VIE). Бот бере лише ті, де обидва часи в межах лімітів.
SUBURBS = {
    "2340": ("Mödling", 30, 55), "2344": ("Maria Enzersdorf", 35, 60), "2345": ("Brunn am Gebirge", 30, 55),
    "2380": ("Perchtoldsdorf", 35, 60), "2482": ("Münchendorf", 35, 60), "2483": ("Ebreichsdorf", 35, 60),
    "2320": ("Schwechat", 30, 20), "2326": ("Maria-Lanzendorf", 40, 45), "2232": ("Deutsch-Wagram", 40, 60),
    "2100": ("Korneuburg", 40, 55), "2102": ("Bisamberg", 40, 55), "2103": ("Langenzersdorf", 35, 50),
    # нижче — задалеко хоча б до одного пункту (лишено для довідки, бот їх відсіює)
    "2351": ("Wiener Neudorf", 40, 65), "2331": ("Vösendorf", 40, 65), "2353": ("Guntramsdorf", 40, 65),
    "2500": ("Baden", 40, 70), "2700": ("Wiener Neustadt", 45, 60), "2401": ("Fischamend", 45, 15),
    "2460": ("Bruck an der Leitha", 45, 50),
    "2000": ("Stockerau", 45, 65), "3400": ("Klosterneuburg", 45, 70), "3002": ("Purkersdorf", 45, 70),
    "3100": ("St. Pölten", 45, 60), "2230": ("Gänserndorf", 50, 65),
}
NOE_POSTCODES = {pc: name for pc, (name, hbf, vie) in SUBURBS.items()
                 if hbf <= MAX_STATION_MINUTES and vie <= MAX_AIRPORT_MINUTES}

# ---------- Виняток до PREMIUM_MAX_RENT у Відні: потрібні ВСІ умови ----------
PREMIUM_NEW_MIN_YEAR = 2015   # «якісна нова»: Neubau / Erstbezug або будинок від цього року
# «Хороший район» — ваш власний список індексів. За замовчуванням — увесь Відень (крім виключених);
# приберіть зайві, щоб звузити.
PREMIUM_POSTCODES = {pc for pc in VIENNA_TRAVEL if pc not in EXCLUDED_POSTCODES}

# ---------- Джерела ----------
# Основні — перевіряються кожні 20 хв.
# willhaben areaId: 900 Відень, 317 Mödling, 307 Bruck/Leitha (Schwechat), 312 Korneuburg,
# 308 Gänserndorf (Deutsch-Wagram), 306 Baden (Ebreichsdorf)
WILLHABEN_AREAS = [900, 317, 307, 312, 308, 306]

IMMOSCOUT_REGIONS = [                     # (регіон, скільки сторінок по 15 оголошень)
    ("wien/wien", 3),
    ("niederoesterreich/moedling", 1),
    ("niederoesterreich/bruck-an-der-leitha", 1),
    ("niederoesterreich/korneuburg", 1),
    ("niederoesterreich/gaenserndorf", 1),
]

# Додаткові — перевіряються двічі на день (07:30 і 19:30)
DERSTANDARD_REGIONS = []
WOHNNET_REGIONS = [                       # (регіон, сторінок по 20)
    ("wien", 4), ("moedling", 1), ("niederoesterreich", 4),
]

# (старе) маршрут до центру — більше не використовується, див. STATION / AIRPORT
TRANSIT_DESTINATION = "Stephansplatz, 1010 Wien"
