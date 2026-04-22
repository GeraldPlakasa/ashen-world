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
DYNASTY_BONUS = 1000             # extra leadership if same family as previous King

QUEST_INTERVAL_YEARS = 3         # King issues quests every 3 years

MAX_DEAD_YEARS = 25
MAX_GRAVEYARD_YEARS = 200  # Remove from graveyard after 200 years dead

CHILD_MAX_AGE = 16

BIRTH_BASE_P = 0.006          # Base daily probability per eligible couple (before cooldown/decay modifiers).
BIRTH_COOLDOWN_DAYS = 45      # prevents back-to-back births
COUPLE_DECAY = 0.55           # each additional child reduces chance strongly
FAMILY_DECAY = 0.85           # more kids under same father family -> lower chance

# Weather changes every N days (re-roll on that schedule)
WEATHER_CHANGE_DAYS = 5

WEATHER_RAIN_CHANCE = 0.35

WEATHER_TYPES = ["sunny", "rain"]

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
    "Alchemist", "Bard", "Scholar", "Ranger", "Miner", "Archer", "Sailor",
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
    {"key": "market",      "name": "Marketplace", "cost": 400},
    {"key": "library",     "name": "Library",     "cost": 350},
    {"key": "barracks",    "name": "Barracks",    "cost": 450},
    {"key": "granary",     "name": "Granary",     "cost": 300},
    {"key": "clinic",      "name": "Clinic",      "cost": 320},
    {"key": "walls",       "name": "City Walls",  "cost": 600},
    {"key": "temple",      "name": "Temple",      "cost": 380},
    {"key": "blacksmith",  "name": "Blacksmith",  "cost": 300},
    {"key": "treasury",    "name": "Treasury",    "cost": 500},
    {"key": "royal_court", "name": "Royal Court", "cost": 480},
    {"key": "tax_office",  "name": "Tax Office",  "cost": 320},
    {"key": "tavern",      "name": "Tavern",      "cost": 240},
]

JOBS_POOL = JOBS
JOBS_NO_ROYAL = [j for j in JOBS if j not in ("King", "Queen")]

# Integer columns for SQLite schema and data mapping
INT_FIELDS = [
    "id", "coins", "age", "int", "rep", "level", "exp",
    "atk", "def", "hp", "mp", "hunger", "gen",
    "immigrantGen", "motherId", "fatherId",
    "kingTerms", "consecutiveTerms", "death_day", "spouseId_at_death",
    "spouseId", "spouseSinceDay",
    "born_day", "last_birth_day",
    "huntWins", "huntWinsYear", "questWins",
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
]

USERS_FIELDNAMES = ["username", "email", "password_hash"]