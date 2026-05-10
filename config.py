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
]

USERS_FIELDNAMES = ["username", "email", "password_hash"]