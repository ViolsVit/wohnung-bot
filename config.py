"""
Налаштування бота. Тут можна міняти критерії без зміни решти коду.
"""

# ---------- Ціна ----------
# Оренда З ПОДАТКОМ (Miete + 10% USt), БЕЗ комунальних (Betriebskosten, опалення)
MAX_RENT = 1000            # € — межа
TARGET_RENT = 850          # € — «мрія»: такі оголошення позначаються 💚 і йдуть першими
VAT_RATE = 0.10            # ПДВ на житлову оренду в Австрії
# Якщо сайт показує лише загальну суму (з комуналкою): вище цієї суми — відсіюємо одразу
MAX_TOTAL_HARD = 1400

# ---------- Квартира ----------
MIN_AREA = 41              # м²
ROOMS = {2, 3}             # 2 = спальня + вітальня з кухнею. Приберіть 3, якщо трикімнатні не цікаві
MIN_YEAR = 1980            # будинок не старіший за цей рік
MAX_DEPOSIT = 6000         # € — застава (Kaution)
MAX_ABLOESE = 4000         # € — викуп меблів/кухні (Ablöse)

# Максимум оголошень, які бот детально перевіряє за один запуск (щоб не навантажувати сайти)
MAX_DETAILS_PER_RUN = 40

# ---------- Географія: лише Відень і найближчі передмістя з S-Bahn / U-Bahn / Badner Bahn ----------
# Відень — усі індекси 1010–1230. Плюс ці міста (≈ до 15 км від меж Відня):
NOE_POSTCODES = {
    # Південь
    "2340": "Mödling", "2344": "Maria Enzersdorf", "2345": "Brunn am Gebirge",
    "2351": "Wiener Neudorf", "2353": "Guntramsdorf", "2361": "Laxenburg",
    "2362": "Biedermannsdorf", "2331": "Vösendorf", "2333": "Leopoldsdorf",
    "2380": "Perchtoldsdorf", "2352": "Gumpoldskirchen", "2371": "Hinterbrühl",
    "2384": "Breitenfurt", "2391": "Kaltenleutgeben",
    # Південний схід (S7)
    "2320": "Schwechat", "2322": "Zwölfaxing", "2325": "Himberg", "2326": "Maria-Lanzendorf",
    "2332": "Hennersdorf",
    # Схід / північний схід
    "2301": "Groß-Enzersdorf", "2232": "Deutsch-Wagram", "2201": "Gerasdorf",
    # Північ (S3/S4)
    "2100": "Korneuburg", "2102": "Bisamberg", "2103": "Langenzersdorf",
    # Захід (S40, S50)
    "3400": "Klosterneuburg", "3002": "Purkersdorf", "3003": "Gablitz",
    "3011": "Tullnerbach", "3013": "Pressbaum", "2381": "Laab im Walde",
}

# ---------- Джерела ----------
# Основні — перевіряються кожні 20 хв.
# willhaben areaId: 900 Відень, 317 Mödling, 307 Bruck/Leitha (Schwechat), 312 Korneuburg,
# 308 Gänserndorf, 321 Tulln (Klosterneuburg), 319 St. Pölten-Land (Purkersdorf)
WILLHABEN_AREAS = [900, 317, 307, 312, 308, 321, 319]

IMMOSCOUT_REGIONS = [                     # (регіон, скільки сторінок по 15 оголошень)
    ("wien/wien", 3),
    ("niederoesterreich/moedling", 1),
    ("niederoesterreich/bruck-an-der-leitha", 1),
    ("niederoesterreich/korneuburg", 1),
    ("niederoesterreich/gaenserndorf", 1),
    ("niederoesterreich/tulln", 1),
    ("niederoesterreich/sankt-poelten-land", 1),
]

# Додаткові — перевіряються двічі на день (07:30 і 19:30)
DERSTANDARD_REGIONS = [                   # (регіон, сторінок по ~15)
    ("wien", 4), ("bezirk-moedling", 1), ("schwechat", 1), ("klosterneuburg", 1),
    ("purkersdorf", 1), ("korneuburg", 1), ("perchtoldsdorf", 1),
]
WOHNNET_REGIONS = [                       # (регіон, сторінок по 20)
    ("wien", 4), ("moedling", 1), ("niederoesterreich", 2),
]

# Куди будувати маршрут громадським транспортом у повідомленні
TRANSIT_DESTINATION = "Stephansplatz, 1010 Wien"
