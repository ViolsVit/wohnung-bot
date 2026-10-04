"""
Налаштування бота. Тут можна міняти критерії без зміни решти коду.
"""

# ---------- Ціна ----------
# Щомісячна сума = Miete (з 10% USt) + Betriebskosten, БЕЗ Heizung / Warmwasser / Strom
MAX_RENT = 1000            # € — межа
TARGET_RENT = 850          # € — «мрія»: такі оголошення позначаються 💚 і йдуть першими
VAT_RATE = 0.10            # ПДВ на житлову оренду в Австрії
# Швидкий відсів за сумою зі списку результатів (там інколи вже є й опалення, тому з запасом)
MAX_TOTAL_HARD = 1400

# ---------- Квартира ----------
MIN_AREA = 41              # м²
ROOMS = {2, 3}             # 2 = спальня + вітальня з кухнею. Приберіть 3, якщо трикімнатні не цікаві
MIN_YEAR = 1980            # будинок не старіший за цей рік
MAX_DEPOSIT = 6000         # € — застава (Kaution)
MAX_ABLOESE = 4000         # € — викуп меблів/кухні (Ablöse)
EXCLUDED_POSTCODES = {"1210"}

# Максимум оголошень, які бот детально перевіряє за один запуск (щоб не навантажувати сайти)
MAX_DETAILS_PER_RUN = 40

# ---------- Географія: Відень + передмістя, звідки ≈ до MAX_TRANSIT_MINUTES до центру ----------
# Відень — усі індекси 1010–1230. Передмістя: індекс → (назва, ≈ хвилин громадським транспортом
# від дому до Stephansplatz, з урахуванням дороги до станції). Час орієнтовний — у кожному
# повідомленні є кнопка маршруту для точної перевірки.
MAX_TRANSIT_MINUTES = 65

SUBURBS = {
    # Південь (S1/S2/S3, Badner Bahn, Südbahn)
    "2340": ("Mödling", 30), "2344": ("Maria Enzersdorf", 35), "2345": ("Brunn am Gebirge", 35),
    "2351": ("Wiener Neudorf", 35), "2353": ("Guntramsdorf", 40), "2361": ("Laxenburg", 45),
    "2362": ("Biedermannsdorf", 40), "2331": ("Vösendorf", 35), "2333": ("Leopoldsdorf", 40),
    "2380": ("Perchtoldsdorf", 35), "2352": ("Gumpoldskirchen", 40), "2371": ("Hinterbrühl", 45),
    "2384": ("Breitenfurt", 45), "2391": ("Kaltenleutgeben", 50),
    "2481": ("Achau", 45), "2482": ("Münchendorf", 50), "2483": ("Ebreichsdorf", 45),
    "2500": ("Baden", 45), "2511": ("Pfaffstätten", 50), "2512": ("Tribuswinkel", 55),
    "2514": ("Traiskirchen", 50), "2540": ("Bad Vöslau", 55), "2542": ("Kottingbrunn", 55),
    "2544": ("Leobersdorf", 60), "2700": ("Wiener Neustadt", 55),
    # Південний схід / схід (S7, S60, Ostbahn)
    "2320": ("Schwechat", 25), "2322": ("Zwölfaxing", 35), "2325": ("Himberg", 40),
    "2326": ("Maria-Lanzendorf", 35), "2332": ("Hennersdorf", 40), "2401": ("Fischamend", 40),
    "2432": ("Schwadorf", 50), "2434": ("Götzendorf an der Leitha", 50), "2435": ("Ebergassing", 50),
    "2440": ("Gramatneusiedl", 45), "2460": ("Bruck an der Leitha", 50),
    "7100": ("Neusiedl am See", 60), "7111": ("Parndorf", 55),
    # Північний схід (S1, S2)
    "2301": ("Groß-Enzersdorf", 40), "2232": ("Deutsch-Wagram", 30), "2201": ("Gerasdorf", 35),
    "2230": ("Gänserndorf", 45), "2231": ("Strasshof", 35), "2120": ("Wolkersdorf", 35),
    "2130": ("Mistelbach", 60),
    # Північ (S3, S4)
    "2100": ("Korneuburg", 30), "2102": ("Bisamberg", 30), "2103": ("Langenzersdorf", 30),
    "2104": ("Spillern", 40), "2105": ("Leobendorf", 45), "2000": ("Stockerau", 40),
    # Захід / північний захід (S40, S50, Westbahn)
    "3400": ("Klosterneuburg", 30), "3420": ("Kritzendorf", 35), "3422": ("Greifenstein", 40),
    "3423": ("St. Andrä-Wördern", 40), "3425": ("Langenlebarn", 45), "3430": ("Tulln", 45),
    "3451": ("Michelhausen / Tullnerfeld", 40),
    "3002": ("Purkersdorf", 30), "3003": ("Gablitz", 40), "3011": ("Tullnerbach", 35),
    "3013": ("Tullnerbach-Lawies", 40), "3021": ("Pressbaum", 40), "2381": ("Laab im Walde", 45),
    "3031": ("Rekawinkel", 45), "3032": ("Eichgraben", 50), "3040": ("Neulengbach", 55),
    "3100": ("St. Pölten", 50),
}
# (для сумісності зі старим кодом) лише ті, що вкладаються в ліміт часу
NOE_POSTCODES = {pc: name for pc, (name, mins) in SUBURBS.items() if mins <= MAX_TRANSIT_MINUTES}

# ---------- Джерела ----------
# Основні — перевіряються кожні 20 хв.
# willhaben areaId (= код округу): 900 Відень, 317 Mödling, 307 Bruck/Leitha (Schwechat), 312 Korneuburg,
# 308 Gänserndorf, 321 Tulln (Klosterneuburg), 319 St. Pölten-Land (Purkersdorf), 306 Baden,
# 316 Mistelbach (Wolkersdorf), 302 St. Pölten, 304 Wiener Neustadt, 107 Neusiedl am See
WILLHABEN_AREAS = [900, 317, 307, 312, 308, 321, 319, 306, 316, 302, 304, 107]

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
DERSTANDARD_REGIONS = []
WOHNNET_REGIONS = [                       # (регіон, сторінок по 20)
    ("wien", 4), ("moedling", 1), ("niederoesterreich", 4),
]

# Куди будувати маршрут громадським транспортом у повідомленні
TRANSIT_DESTINATION = "Stephansplatz, 1010 Wien"
