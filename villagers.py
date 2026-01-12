import random
import math
import json

from config import (
    NAME_PREFIX,
    NAME_SUFFIX,
    TRAITS,
    FAMILY_NAMES,
    JOBS_POOL,
    JOBS_NO_ROYAL,
    ENEMY_BASE,
    _next_villager_id,
    WEATHER_TYPES
)
from world_utils import (
    clamp,
    pick,
    rand_int,
    pick_weighted,
    exp_to_next_level,
    is_child,
)
from buildings import (
    get_building_level,
    apply_tax_on_income,
)
from villagers_social import (
    # keep app.py imports working
    hold_election,

    _set_spouses,
    sync_queen_to_king_spouse,
    adjust_relationship,
    relationship_label,
    spouse_daily_phase,
    maybe_corrupt_from_bank,
    king_assassination_phase,
    child_daily_phase,
    coming_of_age_phase,
)

from storage import maybe_roll_weather, load_weather

# ---------------------------------------------------------------------------
#  Villager generation
# ---------------------------------------------------------------------------

def next_unique_id():
    """Return a unique integer ID for villagers (auto-increment)."""
    global _next_villager_id
    _next_villager_id += 1
    return _next_villager_id


def unique_full_name(taken: set):
    """
    Generate a unique (given + family) name that is not present in `taken`.
    Returns (full_name, family_name).
    """

    def build_given():
        base = pick(NAME_PREFIX) + pick(NAME_SUFFIX)
        # ~35% chance to have a second given name
        if random.random() < 0.35:
            return base + " " + pick(NAME_PREFIX) + pick(NAME_SUFFIX)
        return base

    attempt = 0
    full = None
    family = None

    while attempt < 2000:
        given = build_given()
        family = pick(FAMILY_NAMES)
        full = f"{given} {family}"
        if full not in taken:
            break
        attempt += 1

    if full in taken:
        full = f"{full} #{rand_int(1000, 9999)}"
    taken.add(full)
    return full, family

def make_row(taken_names: set, jobs_pool=None, forced_gender=None, forced_job=None):
    """
    Create a single villager row (dict).

    - taken_names       : set of already used full names
    - jobs_pool         : list of allowed jobs (defaults to JOBS_POOL)
    - forced_gender/job : if provided, override random choice
    """
    if jobs_pool is None:
        jobs_pool = JOBS_POOL

    id_ = next_unique_id()
    age = rand_int(10, 40)
    coins = rand_int(0, 999)
    int_stat = rand_int(1, 100)
    atk = rand_int(5, 120)
    defense = rand_int(5, 120)
    hp = rand_int(60, 220)
    hunger = rand_int(0, 100)
    rep = rand_int(-100, 100)
    level = 1
    exp = 0
    alive = True

    gender = pick(["Male", "Female"])
    job = pick(jobs_pool)

    if forced_gender is not None:
        gender = forced_gender
    if forced_job is not None:
        job = forced_job

    if forced_job in ("King", "Queen"):
        age = max(age, 18)

    if age <= 16 and forced_job is None:
        job = "Child"
        hunger = 0
        coins = 0

    full, family = unique_full_name(taken_names)
    traits = ", ".join(random.sample(TRAITS, 2))

    return {
        "id": id_,
        "name": full,
        "family": family,
        "job": job,
        "gender": gender,
        "coins": coins,
        "age": age,
        "int": int_stat,
        "rep": rep,
        "level": level,
        "exp": exp,
        "atk": atk,
        "def": defense,
        "hp": hp,
        "hunger": hunger,
        "traits": traits,
        "last_action": "",
        "alive": alive,
        "origin": "npc",
        "owner": "",
        "gen": 1,
        "immigrantGen": 0,
        "motherId": 0,
        "fatherId": 0,
        "childrenIds": [],
        "action_log": "",
        "relationships": {},
        "death_day": 0,
        "spouseId": 0,
        "spouseSinceDay": 0,
        "spouseId_at_death": 0,
        "huntWins": 0,
        "huntWinsYear": 0,
        "born_day": 0,
        "last_birth_day": 0,
    }

def reset_id_from_characters(characters):
    """
    Optional helper so create_character doesn't touch _next_villager_id directly.
    """
    global _next_villager_id
    if characters:
        max_id = max(c.get("id", 0) for c in characters)
        if _next_villager_id < max_id:
            _next_villager_id = max_id

def generate_characters(n: int = 50):
    """
    Generate an initial population of `n` villagers.
    Ensures:
    - 1 King (male)
    - 1 Queen (female)
    - Remaining are non-royal jobs.
    """
    taken_names = set()
    characters = []

    global _next_villager_id
    _next_villager_id = 0

    # 1 King (male)
    if n >= 1:
        king_row = make_row(
            taken_names,
            jobs_pool=JOBS_NO_ROYAL,
            forced_gender="Male",
            forced_job="King",
        )
        characters.append(king_row)

    # 1 Queen (female)
    if n >= 2:
        queen_row = make_row(
            taken_names,
            jobs_pool=JOBS_NO_ROYAL,
            forced_gender="Female",
            forced_job="Queen",
        )
        characters.append(queen_row)

    # After creating king_row and queen_row
    _set_spouses(king_row, queen_row, current_day=0)

    # Ensure Queen title matches rule (Queen = King's spouse)
    sync_queen_to_king_spouse(characters, current_day=0)

    remaining = n - len(characters)
    for _ in range(remaining):
        characters.append(make_row(taken_names, jobs_pool=JOBS_NO_ROYAL))

    return characters

# ---------------------------------------------------------------------------
#  Combat & Action
# ---------------------------------------------------------------------------

def choose_action(villager: dict, bank: dict | None = None, weather: str | None = None) -> str:
    """
    Decide the villager's action for the day based on:
    - traits
    - job
    - hunger level
    - available coins
    Actions include: train, study, work, rest, buy_food, buy_gear,
    hunt, socialize, hangout, steal.
    """
    # Base weights
    weights = {
        "train": 1.0,
        "study": 1.0,
        "work": 1.0,
        "rest": 0.8,
        "buy_food": 0.6,
        "buy_gear": 0.4,
        "hunt": 0.8,
        "socialize": 0.6,
        "hangout": 0.4,
        "steal": 0.2,
    }

    # Building-based adjustments (village-wide passives)
    if bank is not None:
        lvl_market    = get_building_level(bank, "market")
        lvl_library   = get_building_level(bank, "library")
        lvl_barracks  = get_building_level(bank, "barracks")
        lvl_granary   = get_building_level(bank, "granary")
        lvl_clinic    = get_building_level(bank, "clinic")
        lvl_tavern    = get_building_level(bank, "tavern")
        lvl_temple    = get_building_level(bank, "temple")

        if lvl_market > 0:
            weights["work"] += 0.2 * lvl_market

        if lvl_library > 0:
            weights["study"] += 0.2 * lvl_library

        if lvl_barracks > 0:
            weights["train"] += 0.3 * lvl_barracks
            weights["hunt"]  += 0.2 * lvl_barracks

        if lvl_granary > 0:
            # Food security → more comfort to train/work, less panic-buying food
            weights["train"] += 0.1 * lvl_granary
            weights["work"]  += 0.1 * lvl_granary
            weights["buy_food"] -= 0.1 * lvl_granary

        if lvl_clinic > 0:
            # Safer to go out hunting if there is a clinic
            weights["hunt"] += 0.1 * lvl_clinic

        if lvl_tavern > 0:
            weights["rest"] += 0.2 * lvl_tavern
            weights["hangout"] += 0.3 * lvl_tavern
            weights["socialize"] += 0.1 * lvl_tavern

        if lvl_temple > 0:
            weights["study"] += 0.1 * lvl_temple

    traits_str = villager.get("traits", "")
    traits = [t.strip() for t in traits_str.split(",") if t.strip()]
    job = villager.get("job", "")

    # Trait-based adjustments
    for t in traits:
        if t in ("Brave", "Reckless", "Protective"):
            weights["train"] += 0.6
            weights["hunt"] += 0.6
            weights["buy_gear"] += 0.3
        if t == "Cautious":
            weights["study"] += 0.4
            weights["rest"] += 0.2
            weights["hunt"] -= 0.3
            weights["steal"] -= 0.2
        if t == "Greedy":
            weights["work"] += 0.8
            weights["steal"] += 0.5
        if t in ("Generous", "Empathic"):
            weights["buy_food"] += 0.4
            weights["socialize"] += 0.4
            weights["hangout"] += 0.5
            weights["steal"] -= 0.2
        if t in ("Wise", "Curious", "Clever"):
            weights["study"] += 0.8
            weights["socialize"] += 0.4
            weights["hangout"] += 0.3
        if t in ("Diligent", "Ambitious"):
            weights["work"] += 0.6
            weights["train"] += 0.4
            weights["buy_gear"] += 0.3
            weights["socialize"] += 0.2
        if t == "Lazy":
            weights["rest"] += 1.0
            weights["train"] -= 0.4
            weights["work"] -= 0.4
        if t == "Hot-headed":
            weights["train"] += 0.4
            weights["hunt"] += 0.4
            weights["buy_gear"] += 0.2
            weights["steal"] += 0.3
        if t == "Deceitful":
            weights["steal"] += 0.9
            weights["socialize"] -= 0.3

    # Job-based adjustments
    if job in ["Soldier", "Commander", "Guard", "Archer", "Ranger", "Captain"]:
        weights["train"] += 1.0
        weights["hunt"] += 0.5
        weights["buy_gear"] += 0.6
        weights["steal"] -= 0.3
    if job in ["Scholar", "Scribe", "Advisor", "Engineer", "Druid", "Alchemist"]:
        weights["study"] += 1.0
        weights["socialize"] += 0.3
    if job in [
        "Farmer", "Miner", "Merchant", "Blacksmith", "Tailor", "Cook", "Innkeeper",
        "Butcher", "Baker", "Trader", "Carpenter", "Fisher", "Weaver", "Clerk",
        "Brewer", "Shepherd", "Tanner", "Jeweler", "Cartwright", "Cobbler",
        "Woodcutter", "Courier", "Beekeeper", "Stablemaster", "Glassblower",
        "Potter", "Forester",
    ]:
        weights["work"] += 1.0
        weights["socialize"] += 0.2  # talk with customers
        weights["hangout"] += 0.3
    if job in ["King", "Queen", "Noble"]:
        weights["work"] += 0.4
        weights["study"] += 0.4
        weights["rest"] += 0.6
        weights["socialize"] += 0.6
        weights["hangout"] += 0.6
        weights["steal"] -= 0.4
        weights["hunt"] *= 0.15   # only ~15% of whatever it was
        weights["train"] *= 0.7   # still train, but less than soldiers
    if job in ["Spy"]:
        weights["steal"] += 0.8
        weights["socialize"] += 0.3

    # Weather-based adjustments
    w = (weather or "sunny").strip().lower()
    if w not in WEATHER_TYPES:
        w = "sunny"

    if w == "rain":
        # Rain makes outdoor / social actions less likely
        weights["hunt"] *= 0.65
        weights["train"] *= 0.85
        weights["work"] *= 0.90
        weights["socialize"] *= 0.80
        weights["hangout"] *= 0.75

        # Rain increases indoor actions
        weights["study"] *= 1.20
        weights["rest"] *= 1.15

        # Slightly more likely to buy food (people stay in / comfort eat)
        weights["buy_food"] *= 1.10

    # Hunger & coins-based adjustments
    hunger = villager.get("hunger", 50)
    coins = villager.get("coins", 0)

    # Hard rule: if very hungry and has enough coins, must buy food
    if hunger >= 70 and coins >= 10:
        return "buy_food"

    # Else, adjust weights based on hunger/coins
    if hunger > 70:
        weights["rest"] += 0.6
        weights["buy_food"] += 0.8
        weights["hunt"] += 0.3
        weights["train"] -= 0.4
        weights["socialize"] -= 0.2
    elif hunger < 30:
        weights["train"] += 0.2
        weights["work"] += 0.2
        weights["socialize"] += 0.1

    if coins < 20:
        weights["work"] += 0.8
        weights["buy_food"] -= 0.3
        weights["steal"] += 0.4
    elif coins > 150:
        weights["buy_food"] += 0.4
        weights["steal"] -= 0.2

    # Prefer buying gear when not starving and rich enough
    if coins > 200 and hunger < 60:
        weights["buy_gear"] += 0.8
    if coins > 400 and hunger < 50:
        weights["buy_gear"] += 0.8

    if coins < 60:
        weights["buy_gear"] -= 0.4

    # Avoid negative or near-zero weights
    for k in list(weights.keys()):
        if weights[k] < 0.05:
            weights[k] = 0.05

    actions = list(weights.keys())
    probs = [weights[a] for a in actions]
    total = sum(probs)
    probs = [p / total for p in probs]

    return random.choices(actions, probs, k=1)[0]

def handle_level_up(v: dict):
    """
    Apply level-up logic in-place:
    - consume EXP
    - increase level
    - buff stats (ATK, DEF, HP)
    """
    leveled = False

    while v["exp"] >= exp_to_next_level(v["level"]):
        cost = exp_to_next_level(v["level"])
        v["exp"] -= cost
        v["level"] += 1

        # Stat buff per level
        v["atk"] += rand_int(1, 3)
        v["def"] += rand_int(1, 2)
        v["hp"] += rand_int(3, 6)
        leveled = True

    if leveled:
        v["hp"] = clamp(v["hp"], 1, 260)

def create_shop_offer(v: dict) -> dict:
    """
    Create a gear shop offer for a villager.

    Permanent stat items only (type, cost, bonuses) to keep storage stable.
    Adds higher-tier (more expensive) items and level-based tier selection.
    """
    lvl = int(v.get("level", 1) or 1)

    # ----------------------------
    #  Tier 1: common / early
    # ----------------------------
    t1 = [
        {"type": "Weapon",   "cost": rand_int(40, 120) + lvl * 5,
         "bonuses": [{"key": "atk", "amt": rand_int(3, 8)}]},
        {"type": "Armor",    "cost": rand_int(40, 120) + lvl * 5,
         "bonuses": [{"key": "def", "amt": rand_int(3, 8)}]},
        {"type": "Tome",     "cost": rand_int(30, 90) + lvl * 4,
         "bonuses": [{"key": "int", "amt": rand_int(2, 6)}]},
        {"type": "Elixir",   "cost": rand_int(25, 75) + lvl * 3,
         "bonuses": [{"key": "hp",  "amt": rand_int(10, 25)}]},
        {"type": "Ring",     "cost": rand_int(50, 120) + lvl * 4,
         "bonuses": [{"key": "rep", "amt": rand_int(2, 5)},
                     {"key": "int", "amt": rand_int(1, 3)}]},
        {"type": "Shield",   "cost": rand_int(60, 140) + lvl * 5,
         "bonuses": [{"key": "def", "amt": rand_int(5, 12)}]},
        {"type": "Boots",    "cost": rand_int(35, 95) + lvl * 3,
         "bonuses": [{"key": "hp",  "amt": rand_int(8, 18)}]},
        {"type": "Banner",   "cost": rand_int(55, 130) + lvl * 5,
         "bonuses": [{"key": "atk", "amt": rand_int(2, 5)},
                     {"key": "rep", "amt": rand_int(1, 2)}]},
        {"type": "Charm",    "cost": rand_int(40, 110) + lvl * 3,
         "bonuses": [{"key": "rep", "amt": rand_int(3, 8)}]},
        {"type": "Traveler’s Bedroll", "cost": 75 + lvl * 4,
         "bonuses": [{"key": "hp", "amt": rand_int(10, 20)}]},
    ]

    # ----------------------------
    #  Tier 2: rare / midgame
    # ----------------------------
    t2 = [
        {"type": "Vitality Belt",      "cost": 90 + lvl * 6,
         "bonuses": [{"key": "hp", "amt": rand_int(14, 28)}]},
        {"type": "Sturdy Cloak",       "cost": 110 + lvl * 7,
         "bonuses": [{"key": "hp",  "amt": rand_int(12, 22)},
                     {"key": "def", "amt": rand_int(2, 5)}]},
        {"type": "Reinforced Vest",    "cost": 130 + lvl * 8,
         "bonuses": [{"key": "hp",  "amt": rand_int(16, 30)},
                     {"key": "def", "amt": rand_int(3, 7)}]},
        {"type": "Oak Talisman",       "cost": 100 + lvl * 7,
         "bonuses": [{"key": "hp", "amt": rand_int(18, 34)}]},
        {"type": "Stamina Bracers",    "cost": 120 + lvl * 8,
         "bonuses": [{"key": "hp",  "amt": rand_int(20, 36)},
                     {"key": "atk", "amt": rand_int(1, 3)}]},
        {"type": "Ironheart Pendant",  "cost": 150 + lvl * 10,
         "bonuses": [{"key": "hp", "amt": rand_int(24, 44)}]},

        # NEW mid-tier items
        {"type": "Warhorn of Resolve", "cost": 180 + lvl * 11,
         "bonuses": [{"key": "rep", "amt": rand_int(5, 10)},
                     {"key": "atk", "amt": rand_int(2, 4)}]},
        {"type": "Mageweave Robe",     "cost": 170 + lvl * 10,
         "bonuses": [{"key": "int", "amt": rand_int(5, 10)},
                     {"key": "hp",  "amt": rand_int(10, 22)}]},
        {"type": "Knight’s Buckler",   "cost": 190 + lvl * 11,
         "bonuses": [{"key": "def", "amt": rand_int(7, 14)},
                     {"key": "hp",  "amt": rand_int(8, 18)}]},
        {"type": "Duelist Rapier",     "cost": 200 + lvl * 12,
         "bonuses": [{"key": "atk", "amt": rand_int(7, 14)},
                     {"key": "rep", "amt": rand_int(2, 5)}]},
        {"type": "Scholar’s Codex",    "cost": 185 + lvl * 11,
         "bonuses": [{"key": "int", "amt": rand_int(6, 12)},
                     {"key": "rep", "amt": rand_int(2, 4)}]},
    ]

    # ----------------------------
    #  Tier 3: epic/legendary / expensive
    # ----------------------------
    t3 = [
        {"type": "Dragonbone Plate",   "cost": 420 + lvl * 20,
         "bonuses": [{"key": "def", "amt": rand_int(14, 24)},
                     {"key": "hp",  "amt": rand_int(30, 55)}]},
        {"type": "Stormforged Aegis",  "cost": 380 + lvl * 18,
         "bonuses": [{"key": "def", "amt": rand_int(16, 26)},
                     {"key": "rep", "amt": rand_int(4, 8)}]},
        {"type": "Voidsteel Greatblade","cost": 450 + lvl * 22,
         "bonuses": [{"key": "atk", "amt": rand_int(18, 30)},
                     {"key": "hp",  "amt": rand_int(12, 25)}]},
        {"type": "Crown of Counsel",   "cost": 500 + lvl * 24,
         "bonuses": [{"key": "int", "amt": rand_int(14, 24)},
                     {"key": "rep", "amt": rand_int(8, 14)}]},
        {"type": "Relic of the Dawn",  "cost": 520 + lvl * 25,
         "bonuses": [{"key": "hp",  "amt": rand_int(45, 75)},
                     {"key": "rep", "amt": rand_int(6, 12)}]},
        {"type": "Emperor’s Signet",   "cost": 600 + lvl * 28,
         "bonuses": [{"key": "rep", "amt": rand_int(10, 18)},
                     {"key": "atk", "amt": rand_int(6, 10)},
                     {"key": "def", "amt": rand_int(6, 10)}]},
        {"type": "Archmage Focus",     "cost": 580 + lvl * 27,
         "bonuses": [{"key": "int", "amt": rand_int(16, 28)},
                     {"key": "hp",  "amt": rand_int(20, 40)}]},
        {"type": "Titan’s Girdle",     "cost": 540 + lvl * 26,
         "bonuses": [{"key": "hp",  "amt": rand_int(60, 95)},
                     {"key": "def", "amt": rand_int(6, 12)}]},
    ]

    # Level-based tier weights:
    # - low level: mostly t1
    # - mid: more t2
    # - high: t3 can appear
    if lvl <= 3:
        pool = t1 + random.sample(t2, k=min(2, len(t2)))  # sprinkle
    elif lvl <= 8:
        pool = t1 + t2 + random.sample(t3, k=min(2, len(t3)))  # rare epic chance
    else:
        pool = t2 + t3 + random.sample(t1, k=min(3, len(t1)))  # still can see basics

    return random.choice(pool)

def create_enemy_for(v: dict) -> dict:
    """
    Create an enemy for a given villager.
    Enemy stats scale with villager level and random tier (common/elite/legendary).
    """
    lvl = v.get("level", 1)

    if lvl < 20:
        tier_weights = {"common": 0.85, "elite": 0.13, "legendary": 0.02}
    elif lvl < 40:
        tier_weights = {"common": 0.70, "elite": 0.25, "legendary": 0.05}
    elif lvl < 80:
        tier_weights = {"common": 0.60, "elite": 0.30, "legendary": 0.10}
    elif lvl < 160:
        tier_weights = {"common": 0.45, "elite": 0.40, "legendary": 0.15}
    else:
        tier_weights = {"common": 0.45, "elite": 0.35, "legendary": 0.20}

    tier = pick_weighted(tier_weights)
    multiplier = 0.85 if tier == "common" else 1.15 if tier == "elite" else 1.50

    name = random.choice(ENEMY_BASE)
    atk = round((v["atk"] * (0.80 + random.random() * 0.2) + lvl * 4) * multiplier)
    defense = round((v["def"] * (0.80 + random.random() * 0.2) + lvl * 3) * multiplier)
    hp = round((50 + lvl * 8) * multiplier * (0.9 + random.random() * 0.2))

    base_coin = 20 + lvl * 4
    coin_factor = 4.0 if tier == "legendary" else 2.0 if tier == "elite" else 1.5
    coin_reward = round(base_coin * coin_factor * (0.9 + random.random() * 0.6))

    exp_reward = round(
        (18 + lvl * 1.4)
        * (1.6 if tier == "legendary" else 1.3 if tier == "elite" else 1.0)
    )
    rep_reward = round(
        (7 if tier == "legendary" else 5 if tier == "elite" else 3)
        + random.random() * 2
    )

    return {
        "tier": tier,
        "name": name,
        "atk": atk,
        "def": defense,
        "hp": hp,
        "expReward": exp_reward,
        "repReward": rep_reward,
        "coinReward": coin_reward,
    }


def apply_starvation_damage(v: dict, bank: dict | None = None):
    """
    If hunger has reached 100, apply starvation damage to HP.
    Granary & Clinic reduce starvation damage.
    Returns the HP lost (int) if damage is applied, or None if not.
    """
    if is_child(v):
        v["hunger"] = 0
        return None
    
    if not v.get("alive", True):
        return None

    if v.get("hunger", 0) < 100:
        return None

    hp_loss = rand_int(5, 18)

    if bank is not None:
        lvl_granary = get_building_level(bank, "granary")
        lvl_clinic  = get_building_level(bank, "clinic")

        reduction_factor = 1.0 - 0.12 * lvl_granary - 0.20 * lvl_clinic
        reduction_factor = max(0.3, reduction_factor)  # keep at least 30%
        hp_loss = max(1, int(round(hp_loss * reduction_factor)))

    v["hp"] = max(0, v["hp"] - hp_loss)

    if v["hp"] <= 0:
        v["hp"] = 0
        v["alive"] = False

    return hp_loss


def resolve_combat(v: dict, enemy: dict, bank: dict | None = None, weather: str | None = None) -> dict:
    """
    Simplified combat resolution.

    Returns a dict:
    {
      "outcome": "WIN" | "LOSS" | "DEAD",
      "hpLost": int,
      "coinGained": int,
      "enemy": enemy_dict,
      "taxPaid": int (only for WIN, if tax applied)
    }

    Mutates `v` in-place (coins, rep, exp, hp, alive).
    """
    # Base power (character)
    char_power = (
        v["atk"] * 1.15
        + v["def"]
        + v["int"] * 0.6
        + v["level"] * 12
        + v["rep"] * 0.2
        + 20
    )

    # Building-based bonuses
    if bank is not None:
        lvl_barracks = get_building_level(bank, "barracks")
        lvl_walls    = get_building_level(bank, "walls")

        power_mult = 1.0 + 0.06 * lvl_barracks + 0.04 * lvl_walls
        char_power *= power_mult

    # Weather effect (rain makes fights riskier)
    w = (weather or "sunny").strip().lower()
    if w == "rain":
        # slightly reduce effective power
        char_power *= 0.93

    # Optional companions (not yet surfaced in CSV/UI)
    companion = v.get("_companion")
    if companion == "war_beast":
        char_power += 40 + v["level"] * 3
    elif companion == "clockwork_soldier":
        char_power += 55 + v["level"] * 2

    # Enemy power
    enemy_power = (enemy["atk"] * 1.0 + enemy["def"] + enemy["hp"] * 0.18) * 0.9

    # Win probability (logistic curve)
    raw_win_prob = 1.0 / (1.0 + math.exp(-(char_power - enemy_power) / 65.0))
    win_prob = min(0.98, max(0.02, raw_win_prob))  # clamp to 2–98%

    win = random.random() < win_prob

    # Base damage
    dmg_base = max(0, round(enemy["atk"] * 0.45 - v["def"] * 0.25))
    dmg_var = round(dmg_base * (0.8 + random.random() * 0.6))

    if bank is not None:
        lvl_clinic = get_building_level(bank, "clinic")
        if lvl_clinic > 0:
            dmg_var = max(0, int(round(dmg_var * (1 - 0.12 * lvl_clinic))))

    if w == "rain":
        # rain increases damage volatility a bit
        dmg_var = int(round(dmg_var * 1.08))

    result = {
        "enemy": enemy,
        "outcome": None,
        "hpLost": 0,
        "coinGained": 0,
        "taxPaid": 0,
    }

    if win:
        gross_coin = enemy["coinReward"]
        if bank is not None:
            tax_info = apply_tax_on_income(v, gross_coin, bank)
            coin_net = tax_info["net"]
            tax_paid = tax_info["tax"]
        else:
            coin_net = gross_coin
            tax_paid = 0

        rep_gain = enemy["repReward"]
        exp_gain = enemy["expReward"] + rand_int(3, 8)

        if bank is not None:
            lvl_temple   = get_building_level(bank, "temple")
            lvl_barracks = get_building_level(bank, "barracks")
            lvl_market   = get_building_level(bank, "market")

            if lvl_temple > 0:
                rep_gain += lvl_temple
            if lvl_barracks > 0:
                exp_gain = int(round(exp_gain * (1 + 0.10 * lvl_barracks)))
            if lvl_market > 0:
                coin_net = int(round(coin_net * (1 + 0.05 * lvl_market)))

        # Apply rewards first (you still "won" and got the loot)
        v["coins"] += coin_net
        v["rep"]   += rep_gain
        v["exp"]   += exp_gain

        # Scratch damage even on win
        scratch = max(0, round(dmg_var * 0.25))
        v["hp"] = max(0, v["hp"] - scratch)

        died_after_win = (v["hp"] <= 0)
        if died_after_win:
            v["hp"] = 0
            v["alive"] = False

        result.update(
            {
                "outcome": "DEAD" if died_after_win else "WIN",
                "hpLost": scratch,
                "coinGained": coin_net,
                "taxPaid": tax_paid,
                "victory": True,          # <-- NEW: tells caller this death was after a win
                "diedAfterWin": died_after_win,  # <-- optional but handy
            }
        )
        return result

    # LOSS / DEAD path
    heavy = max(1, round(dmg_var * (1.1 + random.random() * 0.6)))
    v["hp"] = max(0, v["hp"] - heavy)

    death_prob = 0.07
    if bank is not None:
        lvl_clinic = get_building_level(bank, "clinic")
        lvl_temple = get_building_level(bank, "temple")
        death_prob *= max(0.2, 1 - 0.15 * lvl_clinic - 0.10 * lvl_temple)

    died = v["hp"] <= 0 or (v["hp"] < 25 and random.random() < death_prob)

    if died:
        v["hp"] = 0
        v["alive"] = False
        result.update(
            {
                "outcome": "DEAD",
                "hpLost": heavy,
                "coinGained": 0,
                "victory": False,
                "diedAfterWin": False,
            }
        )
    else:
        result.update(
            {
                "outcome": "LOSS",
                "hpLost": heavy,
                "coinGained": 0,
                "victory": False,
                "diedAfterWin": False,
            }
        )

    return result


def apply_action(
    v: dict,
    action: str,
    bank: dict | None = None,
    all_characters: list[dict] | None = None,
    weather: str | None = None,
):
    """
    Apply the chosen action to the villager (stats, hunger, coins, EXP).
    Also triggers combat for "hunt" and applies tax on taxable income.
    Building passives are applied if `bank` is provided.
    For relationship actions:
    - "socialize" (mostly improves relationship with one villager)
    - "hangout"   (group socialize with several villagers)
    - "steal"     (big negative relationship, coins move to culprit)
    """

    # -------------------- TRAIN --------------------
    if action == "train":
        delta_atk    = rand_int(1, 3)
        delta_def    = rand_int(1, 2)
        delta_hp     = rand_int(0, 2)
        delta_hunger = rand_int(5, 12)
        delta_exp    = rand_int(2, 5)

        w = (weather or "sunny").strip().lower()
        if w == "rain":
            # training outside / movement is harder
            delta_atk = max(1, int(round(delta_atk * 0.90)))
            delta_def = max(1, int(round(delta_def * 0.90)))
            delta_hunger += 1

        if bank is not None:
            lvl_barracks   = get_building_level(bank, "barracks")
            lvl_blacksmith = get_building_level(bank, "blacksmith")
            lvl_granary    = get_building_level(bank, "granary")
            lvl_clinic     = get_building_level(bank, "clinic")

            bonus_mult = 1 + 0.20 * lvl_barracks + 0.15 * lvl_blacksmith
            delta_atk = max(1, int(round(delta_atk * bonus_mult)))
            delta_def = max(1, int(round(delta_def * bonus_mult)))

            if lvl_clinic > 0:
                delta_hp += lvl_clinic  # trained with basic medical support

            if lvl_granary > 0:
                delta_hunger = max(
                    1, int(round(delta_hunger * (1 - 0.08 * lvl_granary)))
                )

        v["atk"]    += delta_atk
        v["def"]    += delta_def
        v["hp"]     += delta_hp
        v["hunger"] += delta_hunger
        v["exp"]    += delta_exp

    # -------------------- STUDY --------------------
    elif action == "study":
        delta_int    = rand_int(1, 3)
        delta_exp    = rand_int(3, 7)
        delta_hunger = rand_int(4, 9)

        if bank is not None:
            lvl_library = get_building_level(bank, "library")
            lvl_temple  = get_building_level(bank, "temple")
            lvl_granary = get_building_level(bank, "granary")

            if lvl_library > 0:
                mult = 1 + 0.25 * lvl_library
                delta_int = max(1, int(round(delta_int * mult)))
                delta_exp = max(
                    1, int(round(delta_exp * (1 + 0.15 * lvl_library)))
                )
            if lvl_temple > 0:
                delta_exp += lvl_temple
            if lvl_granary > 0:
                delta_hunger = max(
                    1, int(round(delta_hunger * (1 - 0.06 * lvl_granary)))
                )

        v["int"]    += delta_int
        v["exp"]    += delta_exp
        v["hunger"] += delta_hunger

    # -------------------- WORK --------------------
    elif action == "work":
        gross        = rand_int(10, 100)
        hunger_delta = rand_int(6, 12)
        exp_delta    = rand_int(1, 4)

        w = (weather or "sunny").strip().lower()
        if w == "rain":
            # less productivity in rain, slightly more hunger drain
            gross = int(round(gross * 0.90))
            hunger_delta += 2

        if bank is not None:
            lvl_market    = get_building_level(bank, "market")
            lvl_blacksmith = get_building_level(bank, "blacksmith")
            lvl_tavern    = get_building_level(bank, "tavern")
            lvl_granary   = get_building_level(bank, "granary")

            income_mult = 1 + 0.20 * lvl_market + 0.10 * lvl_blacksmith
            gross = max(1, int(round(gross * income_mult)))

            if lvl_granary > 0:
                hunger_delta = max(
                    1, int(round(hunger_delta * (1 - 0.05 * lvl_granary)))
                )

            if lvl_tavern > 0:
                # small social reputation gain from work/tavern economy
                v["rep"] += rand_int(0, lvl_tavern)

        if bank is not None:
            res = apply_tax_on_income(v, gross, bank)
            net = res["net"]
            tax = res["tax"]
        else:
            net = gross
            tax = 0

        v["coins"]  += net
        v["exp"]    += exp_delta
        v["hunger"] += hunger_delta

        if tax > 0:
            v["last_action"] = (
                f"work (earned {net} coins, paid {tax} coins in tax)"
            )

    # -------------------- REST --------------------
    elif action == "rest":
        hp_delta     = rand_int(2, 6)
        hunger_delta = rand_int(5, 15)

        if bank is not None:
            lvl_clinic  = get_building_level(bank, "clinic")
            lvl_tavern  = get_building_level(bank, "tavern")
            lvl_granary = get_building_level(bank, "granary")

            heal_mult = 1 + 0.25 * lvl_clinic + 0.10 * lvl_tavern
            hp_delta = max(1, int(round(hp_delta * heal_mult)))

            if lvl_granary > 0:
                hunger_delta = int(
                    round(hunger_delta * (1 + 0.15 * lvl_granary))
                )

        v["hunger"] += hunger_delta
        v["hp"]     += hp_delta

    # -------------------- SOCIALIZE --------------------
    elif action == "socialize":
        # If we don't know other villagers, just treat as a mild rest
        if not all_characters:
            v["hunger"] -= rand_int(1, 4)
            v["hp"] += rand_int(0, 3)
        else:
            candidates = [
                o for o in all_characters
                if o.get("id") != v.get("id") and o.get("alive", True)
            ]
            if not candidates:
                v["hunger"] -= rand_int(1, 4)
                v["hp"] += rand_int(0, 3)
            else:
                other = random.choice(candidates)

                # Mostly positive change, sometimes negative
                if random.random() < 0.8:
                    delta = rand_int(5, 15)
                else:
                    delta = -rand_int(2, 4)

                adjust_relationship(v, other, delta)
                adjust_relationship(other, v, delta)

                v["hunger"] += rand_int(2, 6)
                v["exp"] += rand_int(1, 3)

                label = relationship_label(v, other)
                sign = "+" if delta > 0 else ""
                if label and delta > 0:
                    v["last_action"] = (
                        f"socialize with {other['name']} "
                        f"({sign}{delta} relation → {label})"
                    )
                else:
                    v["last_action"] = (
                        f"socialize with {other['name']} "
                        f"({sign}{delta} relation)"
                    )

    # -------------------- HANGOUT (group socialize) --------------------
    elif action == "hangout":
        # If we don't know other villagers, treat as slightly better rest
        if not all_characters:
            v["hunger"] += rand_int(3, 7)
            v["hp"] += rand_int(2, 5)
            v["exp"] += rand_int(1, 3)
        else:
            # pick several alive villagers (2–5) to join the hangout
            candidates = [
                o for o in all_characters
                if o.get("id") != v.get("id") and o.get("alive", True)
            ]
            if not candidates:
                v["hunger"] += rand_int(3, 7)
                v["hp"] += rand_int(2, 5)
                v["exp"] += rand_int(1, 3)
            else:
                random.shuffle(candidates)
                group_size = rand_int(2, 5)
                group = candidates[:group_size]

                total_delta_pos = 0
                # base stats
                hunger_delta = rand_int(4, 10)
                hp_delta = rand_int(1, 5)
                extra_rep = 0

                # building influence
                if bank is not None:
                    lvl_tavern = get_building_level(bank, "tavern")
                    lvl_granary = get_building_level(bank, "granary")

                    if lvl_tavern > 0:
                        # tavern makes hangouts more effective and less exhausting
                        hunger_delta = max(
                            1, int(round(hunger_delta * (1 - 0.08 * lvl_tavern)))
                        )
                        extra_rep += lvl_tavern

                    if lvl_granary > 0:
                        hunger_delta = max(
                            1, int(round(hunger_delta * (1 - 0.04 * lvl_granary)))
                        )

                # apply relationship changes with each member
                for other in group:
                    # mostly positive, rarely small negative
                    if random.random() < 0.9:
                        delta = rand_int(3, 10)
                    else:
                        delta = -rand_int(1, 3)

                    adjust_relationship(v, other, delta)
                    adjust_relationship(other, v, delta)

                    if delta > 0:
                        total_delta_pos += delta

                v["hunger"] -= hunger_delta
                v["hp"] += hp_delta

                # EXP & REP scale a bit with how good the hangout was
                v["exp"] += rand_int(2, 5) + total_delta_pos // 6
                v["rep"] = clamp(
                    v.get("rep", 0) + total_delta_pos // 4 + extra_rep,
                    -100,
                    100,
                )

                # Build a compact action log message
                names_preview = ", ".join(o["name"] for o in group[:3])
                if len(group) > 3:
                    names_preview += f" + {len(group) - 3} others"

                sign = "+" if total_delta_pos > 0 else ""
                v["last_action"] = (
                    f"hangout with {names_preview} "
                    f"({sign}{total_delta_pos} total relation gain)"
                )

    # -------------------- STEAL --------------------
    elif action == "steal":
        if not all_characters:
            # No context; fallback: small work-like action
            gross = rand_int(5, 15)
            v["coins"] += gross
            v["exp"] += rand_int(1, 3)
            v["hunger"] += rand_int(5, 10)
            v["rep"] = clamp(v.get("rep", 0) - rand_int(1, 4), -100, 100)
            v["last_action"] = (
                f"steal (no target, did work instead, earned {gross} coins)"
            )
        else:
            victims = [
                o for o in all_characters
                if o.get("id") != v.get("id")
                and o.get("alive", True)
                and o.get("coins", 0) > 0
            ]
            if not victims:
                # No one to rob → fallback to work
                gross = rand_int(5, 15)
                v["coins"] += gross
                v["exp"] += rand_int(1, 3)
                v["hunger"] += rand_int(5, 10)
                v["rep"] = clamp(v.get("rep", 0) - rand_int(1, 4), -100, 100)
                v["last_action"] = (
                    f"steal (no rich target, worked instead, earned {gross} coins)"
                )
            else:
                target = random.choice(victims)
                max_steal = min(target.get("coins", 0), rand_int(5, 30))

                if max_steal <= 0:
                    v["hunger"] += rand_int(2, 5)
                    v["rep"] = clamp(v.get("rep", 0) - rand_int(2, 6), -100, 100)
                    v["last_action"] = (
                        f"steal (failed, no coins from {target['name']})"
                    )
                else:
                    target["coins"] -= max_steal
                    v["coins"] += max_steal

                    # Big relationship drop both ways
                    delta = -rand_int(20, 40)
                    adjust_relationship(v, target, delta)
                    adjust_relationship(target, v, delta)

                    # Reputation penalty
                    v["rep"] = clamp(v.get("rep", 0) - rand_int(4, 10), -100, 100)

                    v["hunger"] += rand_int(3, 8)
                    v["exp"] += rand_int(2, 4)

                    v["last_action"] = (
                        f"steal from {target['name']} "
                        f"(+{max_steal} coins, {delta} relation)"
                    )

    # -------------------- BUY FOOD --------------------
    elif action == "buy_food":
        cost                 = rand_int(3, 10)
        hunger_delta_success = -rand_int(8, 18)
        hunger_delta_fail    = rand_int(1, 4)

        if bank is not None:
            lvl_market  = get_building_level(bank, "market")
            lvl_granary = get_building_level(bank, "granary")

            if lvl_market > 0:
                cost = max(1, int(round(cost * (1 - 0.05 * lvl_market))))
            if lvl_granary > 0:
                hunger_delta_success = int(
                    round(hunger_delta_success * (1 + 0.15 * lvl_granary))
                )

        if v["coins"] >= cost:
            v["coins"]  -= cost
            v["hunger"] += hunger_delta_success
        else:
            # Tried to buy but too poor → still gets a bit hungrier
            v["hunger"] += hunger_delta_fail

    # -------------------- BUY GEAR --------------------
    elif action == "buy_gear":
        offer = create_shop_offer(v)
        cost  = offer["cost"]

        if bank is not None:
            lvl_blacksmith = get_building_level(bank, "blacksmith")
            if lvl_blacksmith > 0:
                cost = max(1, int(round(cost * (1 - 0.08 * lvl_blacksmith))))

        if v["coins"] >= cost:
            v["coins"] -= cost

            bonuses = offer.get("bonuses", [])
            bonus_parts = []
            for b in bonuses:
                key = b["key"]
                amt = b["amt"]
                old_val = v.get(key, 0)

                # blacksmith slightly boosts ATK/DEF gear bonuses
                if bank is not None and key in ("atk", "def"):
                    lvl_blacksmith = get_building_level(bank, "blacksmith")
                    if lvl_blacksmith > 0:
                        amt = amt + lvl_blacksmith

                v[key] = old_val + amt
                bonus_parts.append(f"{key.upper()} +{amt}")

            v["hunger"] += rand_int(1, 5)
            v["exp"]    += rand_int(1, 3)

            bonus_text = ", ".join(bonus_parts)
            if bonus_text:
                v["last_action"] = (
                    f"buy_gear (bought {offer['type']} "
                    f"for {cost} coins, {bonus_text})"
                )
            else:
                v["last_action"] = (
                    f"buy_gear (bought {offer['type']} for {cost} coins)"
                )
        else:
            v["hunger"] += rand_int(1, 4)
            v["last_action"] = (
                f"buy_gear (wanted {offer['type']} but lacked coins: {cost})"
            )

    # -------------------- HUNT --------------------
    elif action == "hunt":
        enemy  = create_enemy_for(v)
        combat = resolve_combat(v, enemy, bank, weather=weather)

        won_hunt = (combat["outcome"] == "WIN") or (combat["outcome"] == "DEAD" and combat.get("victory", False))
        if won_hunt:
            v["huntWins"] = int(v.get("huntWins", 0) or 0) + 1
            v["huntWinsYear"] = int(v.get("huntWinsYear", 0) or 0) + 1

        if combat["outcome"] == "WIN":
            hunger_delta = -rand_int(5, 14)

            if bank is not None:
                lvl_granary = get_building_level(bank, "granary")
                if lvl_granary > 0:
                    hunger_delta = int(round(hunger_delta * (1 + 0.10 * lvl_granary)))

            v["hunger"] += hunger_delta

            tax_paid = combat.get("taxPaid", 0)
            if tax_paid > 0:
                v["last_action"] = f"hunt (WIN vs {enemy['tier']} {enemy['name']}, paid {tax_paid} tax)"
            else:
                v["last_action"] = f"hunt (WIN vs {enemy['tier']} {enemy['name']})"

            if not v.get("alive", True) or v.get("hp", 0) <= 0:
                v["alive"] = False
                v["hp"] = 0
                v["last_action"] = f"dead (won hunt vs {enemy['tier']} {enemy['name']}, died from wounds)"

        elif combat["outcome"] == "DEAD":
            # Distinguish: died after winning vs died from losing
            if combat.get("victory", False):
                v["last_action"] = f"dead (won vs {enemy['tier']} {enemy['name']} but died from wounds)"
            else:
                v["last_action"] = f"dead (hunt vs {enemy['tier']} {enemy['name']})"

            # hunger can still move, but doesn't matter much when dead
            v["hunger"] += rand_int(3, 10)

        else:  # "LOSS"
            hunger_delta = rand_int(3, 10)

            if bank is not None:
                lvl_granary = get_building_level(bank, "granary")
                if lvl_granary > 0:
                    hunger_delta = max(1, int(round(hunger_delta * (1 - 0.05 * lvl_granary))))

            v["hunger"] += hunger_delta
            v["last_action"] = f"hunt (LOSS vs {enemy['tier']} {enemy['name']})"

    # Clamp hunger & HP (HP can stay at 0 if dead)
    v["hunger"] = clamp(v["hunger"], 0, 100)
    v["hp"] = min(v["hp"], 260)
    v["rep"] = clamp(int(v.get("rep", 0) or 0), -100, 100)

    # Level-up check using the updated EXP
    handle_level_up(v)

# ---------------------------------------------------------------------------
#  Social & Meta
# ---------------------------------------------------------------------------

def append_action_history(v: dict, max_len: int = 5):
    """
    Keep a rolling history of the last `max_len` actions in v['action_log'].
    Stored as a '||'-joined string so it survives CSV round-trips.
    """
    last = v.get("last_action", "")
    if not last:
        return

    hist_str = v.get("action_log", "")
    if hist_str:
        items = hist_str.split("||")
    else:
        items = []

    items.append(last)
    # keep only the last `max_len`
    if len(items) > max_len:
        items = items[-max_len:]

    v["action_log"] = "||".join(items)

def maybe_add_immigrants(characters: list[dict], bank: dict) -> tuple[list[dict], int]:
    """
    Small chance each day that 1-2 immigrants arrive.

    - Chance scales with Tavern level.
    - Immigrants are NPCs with immigrantGen = 1.
    """

    # Tavern effect: higher level => more known, more travelers
    tavern_lvl = get_building_level(bank, "tavern")

    # Base daily chance: 2% + 1% per tavern level, clamped to [2%, 25%]
    base_chance = 0.01 + 0.01 * tavern_lvl
    chance = max(0.01, min(0.25, base_chance))

    # Roll the dice
    if random.random() >= chance:
        return characters, 0

    # 1–2 new immigrants
    add_count = rand_int(1, 2)

    taken_names = {c.get("name", "") for c in characters}
    added = []

    for _ in range(add_count):
        # Use non-royal jobs for immigrants
        new_v = make_row(taken_names, jobs_pool=JOBS_NO_ROYAL)

        # Mark as NPC immigrant
        new_v["origin"] = "npc"          # as requested (not a separate "immigrant" origin)
        new_v["immigrantGen"] = 1        # first-generation immigrant
        # gen already starts at 1 in make_row, we keep it

        # Flavor log
        arrival_msg = f"{new_v['name']} arrived to settle in the village."
        new_v["last_action"] = "immigrant arrival"
        new_v["action_log"] = arrival_msg

        characters.append(new_v)
        added.append(new_v)

    return characters, len(added)

# ---------------------------------------------------------------------------
#  Player ownership / inheritance
# ---------------------------------------------------------------------------

def _norm_origin(v: dict) -> str:
    return (v.get("origin", "") or "").strip().lower()

def _is_player_char(v: dict) -> bool:
    return _norm_origin(v) == "player" and bool(v.get("owner", ""))

def _is_alive(v: dict) -> bool:
    return v.get("alive", True) and int(v.get("hp", 0) or 0) > 0

def _normalize_id_list(raw):
    """
    childrenIds might be:
      - list[int]
      - JSON string like "[1,2,3]"
      - empty / None
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw if str(x).strip().isdigit()]
    if isinstance(raw, str) and raw.strip():
        s = raw.strip()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [int(x) for x in parsed if str(x).strip().isdigit()]
        except Exception:
            return []
    return []

def _demote_to_npc(v: dict):
    v["origin"] = "npc"
    v["owner"] = ""

def _promote_to_player(v: dict, owner: str):
    v["origin"] = "player"
    v["owner"] = owner or ""

def _find_children(parent: dict, characters: list[dict], id_map: dict[int, dict]) -> list[dict]:
    """
    Prefer explicit childrenIds, but fallback to scanning motherId/fatherId
    in case childrenIds is missing/out-of-sync.
    """
    pid = int(parent.get("id", 0) or 0)

    # 1) from childrenIds
    child_ids = _normalize_id_list(parent.get("childrenIds", []))
    kids = []
    for cid in child_ids:
        c = id_map.get(int(cid))
        if c:
            kids.append(c)

    # 2) fallback scan if empty
    if not kids and pid > 0:
        for c in characters:
            if int(c.get("motherId", 0) or 0) == pid or int(c.get("fatherId", 0) or 0) == pid:
                kids.append(c)

    # dedupe by id
    seen = set()
    out = []
    for k in kids:
        kid = int(k.get("id", 0) or 0)
        if kid and kid not in seen:
            seen.add(kid)
            out.append(k)
    return out


def _find_siblings(person: dict, characters: list[dict]) -> list[dict]:
    """
    Siblings = share motherId OR fatherId (half-siblings included).
    Only works for born characters (motherId/fatherId > 0).
    """
    pid = int(person.get("id", 0) or 0)
    mid = int(person.get("motherId", 0) or 0)
    fid = int(person.get("fatherId", 0) or 0)

    if mid <= 0 and fid <= 0:
        return []

    sibs = []
    for c in characters:
        if int(c.get("id", 0) or 0) == pid:
            continue
        cm = int(c.get("motherId", 0) or 0)
        cf = int(c.get("fatherId", 0) or 0)

        if (mid > 0 and cm == mid) or (fid > 0 and cf == fid):
            sibs.append(c)

    # dedupe
    seen = set()
    out = []
    for s in sibs:
        sid = int(s.get("id", 0) or 0)
        if sid and sid not in seen:
            seen.add(sid)
            out.append(s)
    return out


def _choose_heir(candidates: list[dict], owner: str | None = None) -> dict | None:
    """
    Pick ONE heir from alive candidates.
    Priority:
      - adult first (age > 16)
      - then older
      - then higher level
      - then higher rep
      - then lowest id (stable)
    Also: never steal another owner's player character.
    """
    alive = []
    for c in candidates:
        if not c or not _is_alive(c):
            continue
        if owner:
            # allow: non-player, or player owned by SAME owner
            if _is_player_char(c) and (c.get("owner", "") != owner):
                continue
        alive.append(c)

    if not alive:
        return None

    def key(c):
        age = int(c.get("age", 0) or 0)
        lvl = int(c.get("level", 1) or 1)
        rep = int(c.get("rep", 0) or 0)
        cid = int(c.get("id", 0) or 0)
        is_adult = 1 if age > 16 else 0
        return (is_adult, age, lvl, rep, -cid)

    return sorted(alive, key=key, reverse=True)[0]

def enforce_one_player_per_owner(characters: list[dict]):
    """
    Ensure each owner has exactly ONE 'player' character.
    If duplicates exist, keep the best candidate and demote the rest to NPC.
    """
    by_owner: dict[str, list[dict]] = {}
    for v in characters:
        if _is_player_char(v):
            by_owner.setdefault(v["owner"], []).append(v)

    for owner, group in by_owner.items():
        if len(group) <= 1:
            continue

        def key(v):
            alive = 1 if _is_alive(v) else 0
            age = int(v.get("age", 0) or 0)
            lvl = int(v.get("level", 1) or 1)
            rep = int(v.get("rep", 0) or 0)
            vid = int(v.get("id", 0) or 0)
            return (alive, lvl, age, rep, -vid)

        group_sorted = sorted(group, key=key, reverse=True)
        keep = group_sorted[0]

        for v in group_sorted[1:]:
            _demote_to_npc(v)
            # don't overwrite meaningful last_action, just annotate if empty
            if not v.get("last_action"):
                v["last_action"] = f"lost player status (duplicate owner {owner})"

def player_inheritance_phase(characters: list[dict], current_day: int = 0):
    """
    If a player character dies:
      - promote ONE alive CHILD -> player, same owner
      - else promote ONE alive SIBLING -> player, same owner
      - demote dead player -> npc (owner cleared)
      - ensure owner has only one player char
    """
    id_map = {int(c.get("id", 0) or 0): c for c in characters}

    # run once: clean duplicates before doing transfers
    enforce_one_player_per_owner(characters)

    for parent in characters:
        if not _is_player_char(parent):
            continue
        if _is_alive(parent):
            continue  # still alive

        owner = parent.get("owner", "")
        if not owner:
            continue

        # If owner already has another alive player char, just demote this dead one
        has_alive_player = any(
            (_is_player_char(v) and v.get("owner") == owner and _is_alive(v) and v is not parent)
            for v in characters
        )
        if has_alive_player:
            _demote_to_npc(parent)
            continue

        heir = None
        heir_kind = None

        # 1) Children first
        children = _find_children(parent, characters, id_map)
        heir = _choose_heir(children, owner=owner)
        heir_kind = "child"

        # 2) Then siblings
        if not heir:
            siblings = _find_siblings(parent, characters)
            heir = _choose_heir(siblings, owner=owner)
            heir_kind = "sibling"

        if not heir:
            continue  # no valid heir => keep parent as player-dead (still owned)

        # Transfer: parent becomes NPC, heir becomes player
        parent_name = parent.get("name", "Unknown")
        _demote_to_npc(parent)
        _promote_to_player(heir, owner)

        # Make sure the owner has ONLY this heir as player
        for v in characters:
            if v is heir:
                continue
            if _is_player_char(v) and v.get("owner") == owner:
                _demote_to_npc(v)

        # Log a visible note (captured by append_action_history later)
        note = f"inherited legacy of {parent_name} ({heir_kind})"
        if heir.get("last_action"):
            heir["last_action"] = f"{heir['last_action']} / {note}"
        else:
            heir["last_action"] = note

# ---------------------------------------------------------------------------
#  Day Loop
# ---------------------------------------------------------------------------

def simulate_one_day(characters, bank: dict, current_day: int = 0):
    """
    Simulate actions for one day for each villager in the list.

    - Dead villagers never act again.
    - Starvation can reduce HP and cause death.
    - Income from work/hunt is taxed into the village bank.
    - NEW: small chance King assassinates an enemy.
    """

    reset_id_from_characters(characters)
    weather_today = load_weather()
    # bank["weather"] = weather_today
    coming_of_age_phase(characters, current_day=current_day)
    enforce_one_player_per_owner(characters)

    # 1) Daily individual phase
    for v in characters:
        if v.get("hp", 0) <= 0 or not v.get("alive", True):
            v["hp"] = 0
            v["alive"] = False
            if not v.get("last_action"):
                v["last_action"] = "dead"
            continue
        
        v["last_action"] = ""
        
        # children handled later in child_daily_phase
        if is_child(v):
            v["job"] = "Child"
            v["hunger"] = 0
            continue

        action = choose_action(v, bank, weather=weather_today)
        v["last_action"] = action
        apply_action(v, action, bank, characters, weather=weather_today)

        hp_loss = apply_starvation_damage(v, bank)

        if not v.get("alive", True) and int(v.get("spouseId", 0) or 0) > 0 and not v.get("spouseId_at_death"):
            v["spouseId_at_death"] = int(v["spouseId"])

        if hp_loss:
            if v["alive"]:
                v["last_action"] = f"{v['last_action']} / starvation -{hp_loss} HP"
            else:
                v["last_action"] = f"dead (starvation -{hp_loss} HP)"

        maybe_corrupt_from_bank(v, bank)

    # 2) World phases (immigrants, spouses)
    characters, _added_count = maybe_add_immigrants(characters, bank)
    child_daily_phase(characters, current_day=current_day)
    spouse_daily_phase(characters, current_day=current_day)

    # 3) King assassination phase
    king_assassination_phase(characters, bank=bank, current_day=current_day)

    # 3.5) Player inheritance (dead player -> alive child becomes player)
    player_inheritance_phase(characters, current_day=current_day)

    # 4) Log history LAST so it captures spouse changes + assassination too
    for v in characters:
        append_action_history(v)

    return characters, bank