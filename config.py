import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Legacy file paths — used only by migrate_legacy_files_to_sqlite() in stats_repo.
# New data is stored in SQLite at DB_PATH.
CSV_PATH = os.path.join(DATA_DIR, "characters.csv")
DAY_PATH = os.path.join(DATA_DIR, "world_time.json")
BANK_PATH = os.path.join(DATA_DIR, "bank.json")
USERS_CSV = os.path.join(DATA_DIR, "users.csv")

DB_PATH = os.path.join(DATA_DIR, "ashen_world.sqlite3")

# Logging configuration
LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "ashen_world.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT = 3  # Keep 3 backup files

# Load optional .env (local dev). In production, prefer real env vars.
load_dotenv(os.path.join(BASE_DIR, ".env"))

# In-world: 1 year = 90 days
DAYS_PER_YEAR = 90

# WARNING: in Flask debug mode, reloader can spawn twice; start auto-sim with use_reloader=False.
# Backend auto-simulation config
AUTO_SIM_ENABLED = True          # set to False if you ever want to disable auto-run
AUTO_SIM_SECONDS = 1.0           # real seconds per simulated day
# AUTO_SIM_SECONDS = 960.0

ENV_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ENV_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

ENV_FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

MAX_BUILDING_LEVEL = 3   # e.g. Lv1–Lv3
REPAIR_THRESHOLD = 60    # repair if building health < 60%

# NOTE: ID sequencing is managed by villagers.py (preferred). Keep here only if you centralize imports.
_next_villager_id = 0 

ELECTION_INTERVAL_YEARS = 5      # hold election every 5 game years
KING_MAX_TERMS = 3               # max consecutive terms for one villager as King
DYNASTY_BONUS = 30               # extra leadership if same family as previous King
                                  # (was 1000 — so dominant it guaranteed unanimous
                                  # votes for the dynasty candidate every time)

QUEST_INTERVAL_YEARS = 3         # King issues quests every 3 years

MAX_DEAD_YEARS = 25
MAX_GRAVEYARD_YEARS = 200  # Remove from graveyard after 200 years dead

CHILD_MAX_AGE = 16

BIRTH_BASE_P = 0.008          # Base daily probability per eligible couple (before cooldown/decay modifiers).
BIRTH_COOLDOWN_DAYS = 45      # prevents back-to-back births
COUPLE_DECAY = 0.65           # each additional child reduces chance
FAMILY_DECAY = 0.85           # more kids under same father family -> lower chance

# Weather changes every N days (re-roll on that schedule)
WEATHER_CHANGE_DAYS = 5

WEATHER_RAIN_CHANCE = 0.35

WEATHER_TYPES = ["sunny", "rain"]

# ============================================================================
#  SEASONS
# ============================================================================
# The year is divided into four seasons. day_in_year is 0..DAYS_PER_YEAR-1, so
# each season covers roughly DAYS_PER_YEAR / 4 days (rounded up for the last
# season so the boundaries cover the full year exactly).
#
# Each season is a soft multiplier on production, hunt yield, food consumption,
# weather rain chance, and the festival event's relative weight. The numbers
# are intentionally gentle (±25% range) so a single bad season doesn't crash
# the village, but a string of harsh winters compounds with low stockpiles.
SEASONS = ["spring", "summer", "autumn", "winter"]

# Display metadata for templates / chronicle. Keep slugs lower-case; UI uses
# `.title()` for the friendly label.
SEASON_META = {
    "spring": {"icon": "🌱", "label": "Spring", "tint": "#7ac46a"},
    "summer": {"icon": "☀️",  "label": "Summer", "tint": "#e2b53a"},
    "autumn": {"icon": "🍂", "label": "Autumn", "tint": "#c97a3a"},
    "winter": {"icon": "❄️", "label": "Winter", "tint": "#8aaccc"},
}

# Per-season modifiers. Keys are stable; missing values default to 1.0.
#   farm_mult       — multiplier on Farmer/Shepherd/Beekeeper raw food yields.
#   hunt_food_mult  — multiplier on HUNT_FOOD_PER_KILL meat drops.
#   food_need_mult  — multiplier on village daily food consumption.
#   rain_chance     — overrides WEATHER_RAIN_CHANCE for weather rolls.
#   festival_weight — extra weight added to the FESTIVAL event roll in-season.
SEASON_MODIFIERS = {
    "spring": {
        "farm_mult":       1.15,   # planting yields slightly above baseline
        "hunt_food_mult":  1.00,
        "food_need_mult":  1.00,
        "rain_chance":     0.45,   # rainy season
        "festival_weight": 5,      # small boost — spring fairs
    },
    "summer": {
        "farm_mult":       1.25,   # peak growing season
        "hunt_food_mult":  1.10,
        "food_need_mult":  0.95,   # warmth → slightly lower draw
        "rain_chance":     0.20,   # dry months
        "festival_weight": 15,     # midsummer festivals strongly biased here
    },
    "autumn": {
        "farm_mult":       1.30,   # harvest
        "hunt_food_mult":  1.20,   # game fattened for winter
        "food_need_mult":  1.00,
        "rain_chance":     0.35,   # baseline
        "festival_weight": 10,     # harvest festivals
    },
    "winter": {
        "farm_mult":       0.40,   # fields are fallow
        "hunt_food_mult":  0.70,   # animals scarce / hiding
        "food_need_mult":  1.25,   # villagers need more food to stay warm
        "rain_chance":     0.50,   # rendered as snow in UI
        "festival_weight": 0,      # cold months — festivals are rare
    },
}

NAME_PREFIX = [
    "Aer", "Ael", "Al", "An", "Ar", "Ash", "Aur", "Bel", "Ben", "Bryn", "Cal",
    "Cae", "Cor", "Crae", "Da", "Dar", "Dae", "Dra", "Eir", "El", "Eld", "Ely",
    "Ery", "Faer", "Fen", "Gael", "Gal", "Gar", "Gwyn", "Hal", "Hel", "Il",
    "Ila", "Ira", "Iri", "Is", "Jae", "Jen", "Jor", "Kael", "Kal", "Kar", "Kel",
    "Kor", "Ky", "Lae", "Lar", "Leor", "Lir", "Lor", "Lun", "Lys", "Mael", "Mal",
    "Mor", "Myr", "Nal", "Ner", "Nys", "Nyx", "Or", "Oth", "Pyr", "Quin", "Qir",
    "Rav", "Ren", "Ril", "Ryn", "Sae", "Sar", "Ser", "Shae", "Sil", "Sol", "Syl",
    "Tal", "Tar", "Ther", "Thor", "Tor", "Ty", "Ul", "Ur", "Val", "Var", "Vel",
    "Ver", "Vor", "Wyn", "Wyr", "Xan", "Xil", "Yor", "Yva", "Zae", "Zel", "Zeph",
    "Zor", "Spa", "Adan", "Ari", "Bael", "Bri", "Cael", "Cel", "Cil", "Cir",
    "Ciri", "Cirith", "Cur", "Dael", "Del", "Eael", "Eri", "Fey", "Fir", "Gil",
    "Gyl", "Hael", "Har", "Hath", "Iar", "Jar", "Kir", "Kyl", "Lan", "Mel",
    "Myl", "Nam", "Nes", "Nor", "Nyl", "Oel", "Pel", "Qel", "Rel", "Sel", "Tel",
    "Thal", "Uel", "Wil", "Yal", "Zal", "Zath",
]

NAME_SUFFIX = [
    "a", "ae", "ai", "al", "am", "an", "ar", "as", "ath", "ael", "aen", "aeth",
    "e", "el", "en", "er", "es", "eth", "eon", "eus", "ia", "ian", "ias", "iel",
    "ien", "ies", "ios", "ion", "ir", "is", "ith", "ius", "ix", "in", "ine",
    "ira", "irn", "yn", "yne", "yra", "or", "ora", "oran", "orim", "orin", "orn",
    "os", "oth", "ova", "ul", "ula", "ule", "un", "ur", "us", "uth", "ux", "ys",
    "yse", "yss", "yxa", "yxo", "wyn", "nix", "lyn", "lis", "mir", "dor", "riel",
    "wen", "ron", "anni", "aya", "rian", "var", "beth", "bereth", "berond", "ne",
    "ara", "ari", "elin", "elle", "emar", "mar", "nar", "oel", "sin", "tar",
    "uin", "xar", "yth", "zel", "ber", "beron", "ann", "ay", "ri",
]

TRAITS = [
    "Brave", "Cautious", "Greedy", "Generous", "Loyal", "Deceitful",
    "Stoic", "Hot-headed", "Wise", "Naive", "Diligent", "Lazy",
    "Ambitious", "Protective", "Reckless", "Empathic", "Clever",
    "Strict", "Patient", "Curious",
]

FAMILY_NAMES = [
    # Classic Noble & Elemental
    "Stormborn", "Ironveil", "Dawncrest", "Nightbloom", "Ravenhall", "Wolfsbane",
    "Stoneward", "Silverkeep", "Brightmoor", "Shadowfen", "Emberfall",
    "Thornridge", "Windrider", "Oakshield", "Moonvale", "Ashenford",
    "Frostwhisper", "Goldbrook", "Blackwater", "Hollowmere", "Riverbend",
    "Highridge", "Flintforge", "Starwatch", "Greymantle", "Redwillow",
    "Wintermere", "Sunspire", "Mistwood", "Hawthorne", "Briarhelm",
    "Evergreen", "Seabreak", "Stormwatch", "Ironwood", "Foxglove",
    "Brookstone", "Amberfield", "Wolfpine", "Ravenscar", "Silvershade",
    "Thistlebrook", "Goldenhart", "Marblegate", "Deepwell", "Kingsley",
    "Rowanwake", "Fallowmere", "Hearthstone", "Whisperwind",

    # Realistic / Regional Inspired
    "Plakasa", "Santoro", "Valenko", "Korovin",
    "Maravich", "Kusnadi", "Dewantara", "Rakhman", "Altamir", "Von Aegir",
    "Dragomir", "Targanov", "Marquez", "De Alvar", "Novant", "Kirilov",
    "Volmark", "Havelar", "D’Arion",

    # Mystical / Ancient Tone
    "Zephyros", "Aetherion", "Velithar", "Nocturne", "Elarion", "Solmere",
    "Mystral", "Caelthorn", "Varelis", "Orrinvale", "Nightriver", "Thalorin",
    "Seraphen", "Lunaris", "Graveshade", "Iskaroth", "Ebonvale", "Dravenmoor",
    "Celestir", "Morwynne", "Vaelcrest", "Obsidianreach", "Galeborn",
    "Runebrook", "Duskwright", "Pyrelance",

    # Earthy & Rural
    "Oakenshield", "Farvale", "Greenthorn", "Hillborne", "Dustmere", "Cattail",
    "Fernmere", "Willowfen", "Shademeadow", "Birchwell", "Mapleford", "Elmridge",
    "Pinebrook", "Cloverhollow", "Stonegrove", "Honeywell", "Amberdew",
    "Mossridge", "Rivershade",

    # Maritime & Explorer
    "Wavebreaker", "Saltspire", "Tidewatch", "Coralwyn", "Seawarden", "Driftmoor",
    "Windshore", "Azurefall", "Kelmar", "Deepfathom", "Stormhaven", "Nautilus",
    "Brighttide", "Reefsong", "Harborwyn", "Selmar", "Gullshade",

    # Royal & Heroic
    "Crownspire", "Aldercrest", "Goldhaven", "Brightbane", "Kingsmoor",
    "Valorwind", "Ashbane", "Lioncrest", "Swordmere", "Ironspire", "Dawnsworn",
    "Silverhart", "Valenford", "Rexmere", "Gildenthrone", "Dragonwatch",
    "Halenscar", "Crimsonhall", "Sunhaven", "Oathmoor", "Dream",
]

JOBS = [
    "King", "Queen", "Commander", "Soldier", "Scout", "Captain", "Guard", "Spy",
    "Advisor", "Merchant", "Blacksmith", "Healer", "Priest", "Hunter", "Farmer",
    "Alchemist", "Bard", "Scholar", "Miner", "Sailor",
    "Noble", "Carpenter", "Mason", "Fisher", "Tailor", "Cook", "Herbalist",
    "Scribe", "Engineer", "Trader", "Druid", "Glassblower", "Potter", "Forester",
    "Butcher", "Baker", "Weaver", "Clerk", "Innkeeper", "Brewer", "Shepherd",
    "Tanner", "Jeweler", "Cartwright", "Cobbler", "Woodcutter", "Courier",
    "Beekeeper", "Falconer", "Stablemaster",
    "Wizard", "Sorcerer", "Cleric",
]

# Jobs that primarily use magic (high MP, spells in combat/quests)
MAGIC_JOBS = ["Wizard", "Sorcerer", "Bard", "Cleric", "Druid", "Alchemist"]
# Jobs with minor magic affinity (some MP, occasional spell use)
MINOR_MAGIC_JOBS = ["Priest", "Healer", "Herbalist", "Scholar"]

ENEMY_BASE = [
    "Wolf", "Boar", "Bandit", "Goblin", "Ogre", "Wraith", "Assassin", "Cultist",
    "Raider", "Dire Wolf", "Troll", "Dragonling", "Bandit Captain", "Marauder",
    "Warlock", "Necromancer", "Lichling", "Ghoul", "Skeleton", "Zombie Horde",
    "Harpy", "Manticore", "Giant Spider", "Viper Serpent", "Berserker", "Shade",
    "Griffin", "Wyvern Scout", "Saboteur", "Forest Spirit",
]

BUILDINGS = [
    # Rebalanced: heaviest stone-eaters trimmed; small iron requirements added to
    # several civilian buildings so iron has demand beyond just walls/barracks.
    # Military / industrial iron costs bumped to soak up the iron stockpile
    # that accumulates once Blacksmiths and Miners hit higher levels.
    {"key": "market",      "name": "Marketplace", "cost": 400, "resources": {"wood": 40, "stone": 30}},
    {"key": "library",     "name": "Library",     "cost": 350, "resources": {"wood": 50, "stone": 20}},
    {"key": "barracks",    "name": "Barracks",    "cost": 450, "resources": {"wood": 30, "stone": 50, "iron": 15}},
    {"key": "granary",     "name": "Granary",     "cost": 300, "resources": {"wood": 60, "stone": 20}},
    {"key": "clinic",      "name": "Clinic",      "cost": 320, "resources": {"wood": 40, "stone": 25, "iron": 3}},
    {"key": "walls",       "name": "City Walls",  "cost": 600, "resources": {"stone": 80,  "iron": 25}},
    {"key": "temple",      "name": "Temple",      "cost": 380, "resources": {"wood": 30, "stone": 50, "iron": 3}},
    {"key": "blacksmith",  "name": "Blacksmith",  "cost": 300, "resources": {"wood": 20, "stone": 35, "iron": 18}},
    {"key": "treasury",    "name": "Treasury",    "cost": 500, "resources": {"stone": 60, "iron": 12}},
    {"key": "royal_court", "name": "Royal Court", "cost": 480, "resources": {"wood": 50, "stone": 55, "iron": 5}},
    {"key": "tax_office",  "name": "Tax Office",  "cost": 320, "resources": {"wood": 40, "stone": 25, "iron": 3}},
    {"key": "tavern",      "name": "Tavern",      "cost": 240, "resources": {"wood": 50, "stone": 10, "iron": 2}},
    # Midwife House: shortens the birth-cooldown and raises newborn HP. Effects
    # scale with building level — see family_service._midwife_birth_bonus().
    {"key": "midwife",     "name": "Midwife House", "cost": 290, "resources": {"wood": 45, "stone": 15, "iron": 2}},
    # --- Production buildings (boost specific producer-job yields) ---
    {"key": "farm",        "name": "Farm",        "cost": 280, "resources": {"wood": 50, "stone": 10, "iron": 2}},
    {"key": "lumbermill",  "name": "Lumbermill",  "cost": 260, "resources": {"wood": 80, "iron": 2}},
    {"key": "quarry",      "name": "Quarry",      "cost": 320, "resources": {"wood": 30, "stone": 25, "iron": 3}},
    {"key": "mine",        "name": "Mine",        "cost": 360, "resources": {"wood": 50, "stone": 35, "iron": 5}},
    {"key": "smelter",     "name": "Smelter",     "cost": 340, "resources": {"wood": 30, "stone": 45, "iron": 5}},
]

# Village map layout — hand-picked positions for the top-down map view.
# Viewport: 1000 x 600 SVG. Each entry: x, y are top-left of the building rect.
# Buildings are grouped roughly into zones: production (outskirts),
# civic plaza (center), defense (perimeter), residential (mid-ring).
MAP_VIEWBOX = (1000, 600)
MAP_LAYOUT = {
    # zone: production (top-left)
    "farm":        {"x":  60, "y":  50, "w": 120, "h": 80,  "icon": "🌾", "tint": "#7a8a3f", "zone": "production"},
    "lumbermill":  {"x":  60, "y": 160, "w": 110, "h": 70,  "icon": "🌲", "tint": "#5a6b3a", "zone": "production"},
    # zone: defense (top-right and walls)
    "barracks":    {"x": 800, "y":  50, "w": 130, "h": 80,  "icon": "⚔",  "tint": "#a04848", "zone": "defense"},
    "walls":       {"x": 460, "y":  20, "w": 110, "h": 30,  "icon": "🛡", "tint": "#7a7a7a", "zone": "defense"},
    # zone: mining cluster (right edge)
    "quarry":      {"x": 820, "y": 160, "w": 110, "h": 70,  "icon": "⛏",  "tint": "#7a6e5a", "zone": "production"},
    "mine":        {"x": 820, "y": 250, "w": 110, "h": 70,  "icon": "⛏",  "tint": "#6b5a48", "zone": "production"},
    "smelter":     {"x": 820, "y": 340, "w": 110, "h": 70,  "icon": "🔥", "tint": "#a06a3a", "zone": "production"},
    # zone: civic plaza (center)
    "royal_court": {"x": 430, "y": 230, "w": 160, "h": 90,  "icon": "♔",  "tint": "#c9a227", "zone": "civic"},
    "market":      {"x": 290, "y": 260, "w": 110, "h": 70,  "icon": "₪",  "tint": "#4a9c66", "zone": "civic"},
    "treasury":    {"x": 620, "y": 250, "w": 110, "h": 70,  "icon": "◆",  "tint": "#a0892e", "zone": "civic"},
    "tax_office":  {"x": 620, "y": 340, "w": 100, "h": 60,  "icon": "§",  "tint": "#7a7244", "zone": "civic"},
    # zone: knowledge (left-center)
    "library":     {"x":  60, "y": 270, "w": 110, "h": 70,  "icon": "📚", "tint": "#6a5fa8", "zone": "knowledge"},
    "temple":      {"x":  60, "y": 380, "w": 110, "h": 75,  "icon": "✦",  "tint": "#8e57c0", "zone": "knowledge"},
    # zone: living (bottom mid)
    "housing":     {"x": 200, "y": 380, "w": 100, "h": 65,  "icon": "⌂",  "tint": "#8a7050", "zone": "living"},
    "clinic":      {"x": 200, "y": 470, "w": 110, "h": 65,  "icon": "✚",  "tint": "#c25a8e", "zone": "living"},
    "granary":     {"x": 320, "y": 380, "w": 110, "h": 65,  "icon": "▦",  "tint": "#a0853c", "zone": "living"},
    "tavern":      {"x": 460, "y": 470, "w": 110, "h": 65,  "icon": "♨",  "tint": "#a06a3a", "zone": "living"},
    "midwife":     {"x": 335, "y": 470, "w": 110, "h": 65,  "icon": "✿",  "tint": "#c08aa8", "zone": "living"},
    "blacksmith":  {"x": 600, "y": 470, "w": 110, "h": 65,  "icon": "⚒",  "tint": "#7a5040", "zone": "production"},
}

# Production buildings: each boosts the yield of specific producer jobs.
# Format: building_key -> {job_name: yield_multiplier_per_level}
# At level 1: +25% (multiplier 1.25), level 2: +50%, level 3: +75%.
PRODUCTION_BUILDING_BONUS = {
    "farm":       {"Farmer": 0.25, "Shepherd": 0.20, "Beekeeper": 0.15},
    "lumbermill": {"Woodcutter": 0.30, "Forester": 0.20, "Carpenter": 0.15},
    "quarry":     {"Mason": 0.30, "Miner": 0.15},
    # Mine boost trimmed (was 0.30) so iron doesn't snowball with high-level
    # Miners. Blacksmith bonus removed here — Blacksmith no longer produces
    # raw iron; see BLACKSMITH_IRON_CONSUMPTION below.
    "mine":       {"Miner": 0.20},
    # Smelter now boosts only the Blacksmith conversion (iron → coin); the
    # old Miner +10% double-dipped on raw iron output.
    "smelter":    {"Blacksmith": 0.40},
}

# --- Resources (shared town stockpile) ---
RESOURCE_TYPES = ["food", "wood", "stone", "iron"]

# Per "work" action: raw resource output by job (before level/skill/weather scaling).
# Jobs not listed here produce only coin income, as before.
# Yields are tuned for a 50-villager population where ~1 of each producer job exists:
# avg daily food production should roughly equal adult consumption to keep
# the economy sustainable without trivializing famine events.
JOB_RESOURCE_YIELD = {
    "Farmer":     {"food": 12},   # rain halves this in apply_action
    "Hunter":     {"food": 5},    # plus tier-scaled hunt food on kill
    "Fisher":     {"food": 8},
    "Shepherd":   {"food": 5},
    "Baker":      {"food": 3},
    "Butcher":    {"food": 3},
    "Cook":       {"food": 2},
    "Beekeeper":  {"food": 2},
    "Woodcutter": {"wood": 6},
    "Forester":   {"wood": 4},
    "Carpenter":  {"wood": 2},
    # Stone production boosted: prior ratio (4:1) couldn't keep up with the
    # 10:1 stone-vs-iron building demand, leaving stone permanently stuck
    # while iron accumulated. Mason 6 + Miner stone 5 (was 4).
    "Mason":      {"stone": 6},
    # Miner is now the sole raw-iron producer (Blacksmith was removed: it
    # used to double iron supply with no offsetting sink, so iron piled up).
    # Stone bumped 4 -> 5 so total mining throughput is roughly preserved.
    "Miner":      {"stone": 5, "iron": 1},
    # Blacksmith no longer mines iron — it CONSUMES iron in apply_action's
    # "work" branch to forge tools/weapons for coin. See action_service.py.
}

# Daily town-wide food consumption
FOOD_PER_ADULT_PER_DAY = 1
# Children are fed implicitly by their families; the town stockpile doesn't
# pay for them separately. Set >0 to make a population of dependents more punishing.
FOOD_PER_CHILD_PER_DAY = 0
# Granary lvl ≥ 1 multiplies total food need by this (more efficient storage/distribution)
GRANARY_CONSUMPTION_MULT = 0.75
# Food earned per hunt victory: common=1x, elite=2x, legendary=3x of this base
HUNT_FOOD_PER_KILL = 3

# --- Foreign Trade (King imports resources from outside) ---
# Coin price the village pays per unit when the king imports a resource.
# Food is cheapest (abundant from neighbors), iron is the most expensive.
TRADE_PRICES = {"food": 1, "wood": 2, "stone": 3, "iron": 6}
# Treasury safety floor — the king will never spend below this amount on imports.
TRADE_TREASURY_FLOOR = 300
# Per-purchase order sizes (units bought when the king decides to import).
TRADE_ORDER_SIZE = {"food": 200, "wood": 60, "stone": 40, "iron": 15}
# Stockpile thresholds that trigger an import. Food is population-scaled at
# runtime; the integer here is a fallback if the population is unknown.
TRADE_LOW_STOCK = {"food": 400, "wood": 50, "stone": 30, "iron": 10}
# Hard "emergency" threshold: any food stockpile below this absolute value
# triggers an import regardless of king's trait. With ~75 adults consuming
# 75/day, 1000 = ~13 days buffer — generous but the king should be acting
# proactively, not waiting for the village to starve.
TRADE_EMERGENCY_FOOD_STOCK = 1000
# Target stockpile after an emergency import — the king buys enough to reach
# this level (treasury and floor permitting).
TRADE_EMERGENCY_FOOD_TARGET = 1500

# ----- EXPORT (king sells surplus stockpile back to treasury) -----
# Sell prices are deliberately below TRADE_PRICES (buy-back loss) so the
# village can't arbitrage trade. Realistic: outside merchants pay less than
# they charge. Roughly 50–65% of buy price.
TRADE_SELL_PRICES = {"food": 1, "wood": 1, "stone": 2, "iron": 4}
# Stockpile must EXCEED this floor before the king will consider exporting.
# Food floor is intentionally high: never sell food unless we have weeks
# of supply on hand.
TRADE_EXPORT_FLOOR = {"food": 3000, "wood": 250, "stone": 200, "iron": 40}
# Per-export order sizes — small to medium so a single decision doesn't
# wipe the stockpile. Iron export bumped (was 20) so surplus clears faster.
TRADE_EXPORT_SIZE = {"food": 400, "wood": 100, "stone": 70, "iron": 30}

JOBS_POOL = JOBS
JOBS_NO_ROYAL = [j for j in JOBS if j not in ("King", "Queen")]

# Magical Artifacts: equip slots + starter templates
ARTIFACT_SLOTS = ["weapon", "armor", "ring", "amulet", "tome"]

ARTIFACT_RARITY_ORDER = {"common": 1, "uncommon": 2, "rare": 3, "legendary": 4}

ARTIFACT_TEMPLATES = [
    # ---------- WEAPONS ----------
    {
        "slug": "iron_blade",
        "name": "Iron Blade",
        "slot": "weapon",
        "rarity": "common",
        "stat_mods": {"atk": 2},
        "flavor": "A workmanlike blade. Reliable steel.",
        "binding": "none",
    },
    {
        "slug": "hunting_spear",
        "name": "Hunting Spear",
        "slot": "weapon",
        "rarity": "common",
        "stat_mods": {"atk": 3},
        "flavor": "Long enough to keep beasts at arm's length — most days.",
        "binding": "none",
    },
    {
        "slug": "woodsmans_axe",
        "name": "Woodsman's Axe",
        "slot": "weapon",
        "rarity": "common",
        "stat_mods": {"atk": 3, "def": 1},
        "flavor": "It has felled more trees than men, but knows the difference.",
        "binding": "none",
    },
    {
        "slug": "knights_longsword",
        "name": "Knight's Longsword",
        "slot": "weapon",
        "rarity": "uncommon",
        "stat_mods": {"atk": 5, "def": 2},
        "flavor": "Balanced steel, stamped with a forgotten oath.",
        "binding": "none",
    },
    {
        "slug": "riverstone_maul",
        "name": "Riverstone Maul",
        "slot": "weapon",
        "rarity": "uncommon",
        "stat_mods": {"atk": 6, "hp": 5},
        "flavor": "Heavy as guilt and twice as direct.",
        "binding": "none",
    },
    {
        "slug": "ember_sword",
        "name": "Ember Sword",
        "slot": "weapon",
        "rarity": "rare",
        "stat_mods": {"atk": 5, "mp": 2},
        "flavor": "Forged in the kiln of the first Wizard.",
        "binding": "none",
    },
    {
        "slug": "whisperblade",
        "name": "Whisperblade",
        "slot": "weapon",
        "rarity": "rare",
        "stat_mods": {"atk": 6, "int": 3},
        "flavor": "It is said to know which side of an argument to take.",
        "binding": "none",
    },
    {
        "slug": "stormcleaver",
        "name": "Stormcleaver",
        "slot": "weapon",
        "rarity": "rare",
        "stat_mods": {"atk": 8, "hp": 5},
        "flavor": "It hums when rain is coming.",
        "binding": "none",
    },
    {
        "slug": "fang_of_the_wyrm",
        "name": "Fang of the Wyrm",
        "slot": "weapon",
        "rarity": "legendary",
        "stat_mods": {"atk": 12, "def": 4},
        "flavor": "Drawn from the jaw of the last wyrm to fall in this land.",
        "binding": "none",
    },
    {
        "slug": "skybane",
        "name": "Skybane",
        "slot": "weapon",
        "rarity": "legendary",
        "stat_mods": {"atk": 14, "hp": 20},
        "flavor": "It hates the sky and everything that flies in it.",
        "binding": "soulbound",
    },

    # ---------- ARMOR ----------
    {
        "slug": "acolyte_robes",
        "name": "Acolyte Robes",
        "slot": "armor",
        "rarity": "common",
        "stat_mods": {"mp": 5},
        "flavor": "Woven by initiates of the Tower.",
        "binding": "none",
    },
    {
        "slug": "tanners_vest",
        "name": "Tanner's Vest",
        "slot": "armor",
        "rarity": "common",
        "stat_mods": {"def": 2},
        "flavor": "Smells of smoke and stops a knife once.",
        "binding": "none",
    },
    {
        "slug": "boiled_leather",
        "name": "Boiled Leather",
        "slot": "armor",
        "rarity": "common",
        "stat_mods": {"def": 3, "hp": 5},
        "flavor": "Common kit — the kind a hundred soldiers wore yesterday.",
        "binding": "none",
    },
    {
        "slug": "stoneskin_cuirass",
        "name": "Stoneskin Cuirass",
        "slot": "armor",
        "rarity": "uncommon",
        "stat_mods": {"def": 4, "hp": 20},
        "flavor": "Plate that has turned aside a hundred blows.",
        "binding": "none",
    },
    {
        "slug": "mageweave_robes",
        "name": "Mageweave Robes",
        "slot": "armor",
        "rarity": "uncommon",
        "stat_mods": {"def": 2, "mp": 10, "int": 1},
        "flavor": "Threaded with silver. Hums faintly in candlelight.",
        "binding": "none",
    },
    {
        "slug": "plated_greaves",
        "name": "Plated Greaves",
        "slot": "armor",
        "rarity": "uncommon",
        "stat_mods": {"def": 5, "hp": 10},
        "flavor": "The watchhouse standard. Heavy and unfussy.",
        "binding": "none",
    },
    {
        "slug": "mail_of_watchers",
        "name": "Mail of Watchers",
        "slot": "armor",
        "rarity": "rare",
        "stat_mods": {"def": 7, "hp": 15, "rep": 2},
        "flavor": "Worn by those who stood the long nights.",
        "binding": "none",
    },
    {
        "slug": "robes_of_stars",
        "name": "Robes of Stars",
        "slot": "armor",
        "rarity": "rare",
        "stat_mods": {"def": 3, "mp": 25, "int": 5},
        "flavor": "Stitched with thread the color of a clear midnight.",
        "binding": "none",
    },
    {
        "slug": "aegis_of_the_first_king",
        "name": "Aegis of the First King",
        "slot": "armor",
        "rarity": "legendary",
        "stat_mods": {"def": 10, "hp": 40, "rep": 5},
        "flavor": "Once worn into a fight that ended an age.",
        "binding": "none",
    },
    {
        "slug": "ashen_shroud",
        "name": "Ashen Shroud",
        "slot": "armor",
        "rarity": "legendary",
        "stat_mods": {"def": 8, "hp": 50},
        "flavor": "A burial cloak that refused to lie still.",
        "binding": "soulbound",
    },

    # ---------- RINGS ----------
    {
        "slug": "copper_band",
        "name": "Copper Band",
        "slot": "ring",
        "rarity": "common",
        "stat_mods": {"atk": 1},
        "flavor": "A traveler's keepsake. Tarnished but warm.",
        "binding": "none",
    },
    {
        "slug": "iron_signet",
        "name": "Iron Signet",
        "slot": "ring",
        "rarity": "common",
        "stat_mods": {"def": 1, "rep": 1},
        "flavor": "Stamped with a sigil no one remembers.",
        "binding": "none",
    },
    {
        "slug": "mossbound_ring",
        "name": "Mossbound Ring",
        "slot": "ring",
        "rarity": "uncommon",
        "stat_mods": {"mp": 5, "int": 1},
        "flavor": "Pulled from a river-stone that wouldn't let it go.",
        "binding": "none",
    },
    {
        "slug": "vow_ring",
        "name": "Vow Ring",
        "slot": "ring",
        "rarity": "uncommon",
        "stat_mods": {"hp": 5, "rep": 3},
        "flavor": "A wedding band, given more often than worn.",
        "binding": "none",
    },
    {
        "slug": "ring_of_the_wandering",
        "name": "Ring of the Wandering",
        "slot": "ring",
        "rarity": "rare",
        "stat_mods": {"atk": 3, "def": 3},
        "flavor": "Said to point you toward the next fight, if you let it.",
        "binding": "none",
    },
    {
        "slug": "ring_of_ember",
        "name": "Ring of Ember",
        "slot": "ring",
        "rarity": "rare",
        "stat_mods": {"mp": 20},
        "flavor": "A coal that never cools.",
        "binding": "none",
    },
    {
        "slug": "ring_of_the_veil",
        "name": "Ring of the Veil",
        "slot": "ring",
        "rarity": "rare",
        "stat_mods": {"mp": 15, "int": 5},
        "flavor": "It thins between worlds when worn at dusk.",
        "binding": "none",
    },
    {
        "slug": "crown_bond_ring",
        "name": "Crown-Bond Ring",
        "slot": "ring",
        "rarity": "legendary",
        "stat_mods": {"rep": 10, "mp": 10, "int": 3},
        "flavor": "Given to those who counsel kings and survive.",
        "binding": "none",
    },

    # ---------- AMULETS ----------
    {
        "slug": "bone_charm",
        "name": "Bone Charm",
        "slot": "amulet",
        "rarity": "common",
        "stat_mods": {"hp": 2},
        "flavor": "A child's whittling. Worn for luck.",
        "binding": "none",
    },
    {
        "slug": "traders_pendant",
        "name": "Trader's Pendant",
        "slot": "amulet",
        "rarity": "common",
        "stat_mods": {"rep": 2},
        "flavor": "It opens doors that gold sometimes can't.",
        "binding": "none",
    },
    {
        "slug": "clerics_sigil",
        "name": "Cleric's Sigil",
        "slot": "amulet",
        "rarity": "uncommon",
        "stat_mods": {"mp": 8, "rep": 2},
        "flavor": "Blessed at the temple's threshold.",
        "binding": "none",
    },
    {
        "slug": "beast_tooth_amulet",
        "name": "Beast-Tooth Amulet",
        "slot": "amulet",
        "rarity": "uncommon",
        "stat_mods": {"atk": 3, "hp": 5},
        "flavor": "Pulled from something that bit harder than it should have.",
        "binding": "none",
    },
    {
        "slug": "amulet_of_the_verge",
        "name": "Amulet of the Verge",
        "slot": "amulet",
        "rarity": "rare",
        "stat_mods": {"def": 5, "rep": 8},
        "flavor": "Worn by a captain who never broke at the line.",
        "binding": "none",
    },
    {
        "slug": "heartstone",
        "name": "Heartstone",
        "slot": "amulet",
        "rarity": "rare",
        "stat_mods": {"hp": 30, "rep": 5},
        "flavor": "A pebble that pulses if you hold it long enough.",
        "binding": "none",
    },
    {
        "slug": "amulet_of_kingsblood",
        "name": "Amulet of Kingsblood",
        "slot": "amulet",
        "rarity": "legendary",
        "stat_mods": {"rep": 15},
        "flavor": "Worn only by those who have held the crown.",
        "binding": "none",
    },
    {
        "slug": "amulet_of_eternal_vows",
        "name": "Amulet of Eternal Vows",
        "slot": "amulet",
        "rarity": "legendary",
        "stat_mods": {"rep": 20, "hp": 30},
        "flavor": "Two halves once, joined when the wearer's love died.",
        "binding": "soulbound",
    },
    {
        "slug": "ashen_crown",
        "name": "The Ashen Crown",
        "slot": "amulet",
        "rarity": "legendary",
        "stat_mods": {"rep": 25},
        "flavor": "It chooses its bearer, and it follows them to the grave.",
        "binding": "soulbound",
    },

    # ---------- TOMES ----------
    {
        "slug": "apprentice_notes",
        "name": "Apprentice's Notes",
        "slot": "tome",
        "rarity": "common",
        "stat_mods": {"int": 2},
        "flavor": "Earnest scribblings from someone who is still learning.",
        "binding": "none",
    },
    {
        "slug": "healers_manual",
        "name": "Healer's Manual",
        "slot": "tome",
        "rarity": "common",
        "stat_mods": {"mp": 3, "int": 1},
        "flavor": "Dog-eared at the chapter on bleeding.",
        "binding": "none",
    },
    {
        "slug": "bestiary_fragments",
        "name": "Bestiary Fragments",
        "slot": "tome",
        "rarity": "uncommon",
        "stat_mods": {"atk": 3, "int": 3},
        "flavor": "Half a book. The other half was eaten by what it described.",
        "binding": "none",
    },
    {
        "slug": "tome_of_lesser_wards",
        "name": "Tome of Lesser Wards",
        "slot": "tome",
        "rarity": "uncommon",
        "stat_mods": {"mp": 8, "def": 2},
        "flavor": "Modest spells, well-rehearsed.",
        "binding": "none",
    },
    {
        "slug": "codex_of_echoes",
        "name": "Codex of Echoes",
        "slot": "tome",
        "rarity": "rare",
        "stat_mods": {"int": 6, "mp": 15},
        "flavor": "Whispers a translation when read aloud.",
        "binding": "none",
    },
    {
        "slug": "songbook_of_the_bard",
        "name": "Songbook of the Bard",
        "slot": "tome",
        "rarity": "rare",
        "stat_mods": {"rep": 8, "mp": 10},
        "flavor": "Every verse has been sung in a different tavern.",
        "binding": "none",
    },
    {
        "slug": "tome_of_first_words",
        "name": "Tome of First Words",
        "slot": "tome",
        "rarity": "legendary",
        "stat_mods": {"int": 10, "mp": 30},
        "flavor": "The earliest spells, written before names had shape.",
        "binding": "none",
    },
    {
        "slug": "tome_of_forbidden_names",
        "name": "Tome of Forbidden Names",
        "slot": "tome",
        "rarity": "legendary",
        "stat_mods": {"int": 15, "mp": 50},
        "flavor": "Reading the index alone has driven men to silence.",
        "binding": "soulbound",
    },
]

# Integer columns for SQLite schema and data mapping
INT_FIELDS = [
    "id", "coins", "age", "int", "rep", "level", "exp",
    "atk", "def", "hp", "mp", "hunger", "gen",
    "immigrantGen", "motherId", "fatherId",
    "kingTerms", "consecutiveTerms", "death_day", "spouseId_at_death",
    "spouseId", "spouseSinceDay",
    "born_day", "last_birth_day",
    "huntWins", "huntWinsYear", "questWins",
    "equip_weapon", "equip_armor", "equip_ring", "equip_amulet", "equip_tome",
    "last_forge_day",
    "blue_blood",
    "disease_day",
    # Election politics: how many consecutive elections this villager has
    # placed in the top-3 runners-up without winning. Resets on a win.
    # Drives resentment toward the king and the coup-attempt chance.
    "consecutive_losses",
]

FIELDNAMES = [
    "id", "name", "family", "gender", "job",
    "coins", "age", "int", "rep", "level", "exp",
    "atk", "def", "hp", "mp", "hunger", "traits", "last_action",
    "action_log", "relationships", "achievements", "kingsVotedFor",
    "spouseId", "spouseSinceDay", "spouseId_at_death",
    "alive", "origin", "owner", "gen", "immigrantGen",
    "motherId", "fatherId", "childrenIds", "kingTerms", "consecutiveTerms",
    "death_day", "huntWins", "huntWinsYear", "questWins",
    "born_day", "last_birth_day",
    "skills",
    "equip_weapon", "equip_armor", "equip_ring", "equip_amulet", "equip_tome",
    "last_forge_day",
    "blue_blood",
    # Disease MVP
    "disease", "disease_day", "immunities",
    # Election politics (see INT_FIELDS for description)
    "consecutive_losses",
    # Crime & justice: JSON list of past crimes by this villager. Each entry:
    # {"day": int, "type": "theft|assault|murder", "victim_id": int,
    #  "verdict": "fine|exile|execution"|null, "verdict_day": int|null}
    "crime_record",
]

USERS_FIELDNAMES = ["username", "email", "password_hash"]

# ============================================================================
#  DISEASE / ILLNESS SYSTEM
# ============================================================================
# Persistent per-villager disease state. Each disease has its own transmission
# rate (chance to infect a contact), duration, daily HP drain, and lethality.
# Healer jobs (Healer/Cleric/Herbalist/Priest) can cure with a base chance
# scaled by INT and the Clinic/Temple building levels.

DISEASES = {
    "cough": {
        "name":               "Persistent Cough",
        "transmission_rate":  0.30,   # per close-contact interaction
        "spouse_transmission": 0.45,  # higher between spouses sharing a home
        "duration_days":      6,
        "daily_hp_loss":      (1, 3),
        "lethal_chance":      0.000,  # cough doesn't kill on its own
        "recover_chance":     0.20,   # daily spontaneous recovery
        "cure_chance_base":   0.55,   # base chance per healer attempt
        "icon":               "🤧",
    },
    "fever": {
        "name":               "Fever",
        "transmission_rate":  0.20,
        "spouse_transmission": 0.35,
        "duration_days":      10,
        "daily_hp_loss":      (3, 6),
        "lethal_chance":      0.012,
        "recover_chance":     0.12,
        "cure_chance_base":   0.40,
        "icon":               "🤒",
    },
    "plague": {
        "name":               "Plague Boils",
        "transmission_rate":  0.12,
        "spouse_transmission": 0.20,
        "duration_days":      14,
        "daily_hp_loss":      (5, 9),
        "lethal_chance":      0.045,
        "recover_chance":     0.06,
        "cure_chance_base":   0.25,
        "icon":               "☠️",
    },
}

# Baseline chance per alive villager per day of catching an illness from
# outside (immigrants, traveling merchants, contaminated water).
DISEASE_AMBIENT_CHANCE = 0.0025
# Bias of which disease an ambient case is — same order as DISEASES, weight list
DISEASE_AMBIENT_WEIGHTS = {"cough": 0.65, "fever": 0.27, "plague": 0.08}

# Healer jobs (who can use the `heal_sick` action)
HEALER_JOBS = {"Healer", "Cleric", "Herbalist", "Priest"}

# ============================================================================
#  CRIME & JUSTICE SYSTEM
# ============================================================================
# Villagers can commit crimes (theft / assault / murder). Guards on patrol may
# witness in-progress crimes and create a pending case on the bank. Once per
# day, if any cases are open and there is a sitting King, a trial phase runs
# and the king issues a verdict per case (fine / exile / execution), modulated
# by the king's traits and the crime severity. Outcomes are written to the
# chronicle under the new `justice` category.

# Jobs that can perform the patrol action and act as witnesses with elevated
# detection chance.
GUARD_JOBS = {"Guard", "Captain", "Soldier", "Commander"}

# Per-crime severity scoring used by verdict logic. Higher = harsher.
CRIME_SEVERITY = {
    "theft":   1,
    "assault": 2,
    "murder":  4,
}

# Base witness chance for an in-progress crime when there is at least one
# Guard alive. Scales upward with the number of guards on duty and with
# patrol coverage (any Guard who took the patrol action today).
CRIME_BASE_WITNESS_CHANCE = {
    "theft":   0.10,
    "assault": 0.25,
    "murder":  0.40,
}
CRIME_WITNESS_PER_GUARD     = 0.04   # +chance per alive guard in the village
CRIME_WITNESS_PER_PATROLLER = 0.10   # +chance per guard who patrolled today

# Fine amounts (coins) collected from criminal -> treasury on a `fine` verdict.
# If the criminal can't pay, the shortfall is forgiven (no debt accounting).
CRIME_FINE_AMOUNT = {
    "theft":   30,
    "assault": 60,
    "murder":  150,
}

# Cooldown (days) after a `fine` verdict — used as a soft barrier so the same
# villager doesn't immediately re-offend the same day. Trial phase respects
# this via the `crime_record` timestamps.
CRIME_REPEAT_COOLDOWN_DAYS = 30