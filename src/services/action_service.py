from __future__ import annotations

import random

from config import (
    WEATHER_TYPES,
)
from src.utils.world_utils import (
    clamp,
    rand_int,
)
from src.services.building_service import (
    get_building_level,
    apply_tax_on_income,
)
from src.services.relationship_service import (
    adjust_relationship,
    relationship_label,
)
from src.services.skill_service import (
    parse_skills, get_skill_info,
    get_train_bonus, get_study_bonus, get_work_bonus,
    get_socialize_bonus, get_hunt_bonus, get_rest_bonus,
    add_skill_to_villager, get_learning_progress, add_learning_progress,
    reset_learning_progress,
)
from config import CHILD_MAX_AGE
from src.models.villager import Villager
from src.models.bank import Bank
from src.models.combat import ShopOffer

def choose_action(villager: Villager, bank: Bank | None = None, weather: str | None = None) -> str:
    """
    Decide the villager's action for the day based on traits, job, hunger, coins,
    weather, and building levels.
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
        "mentor": 0.0,  # Only enabled for age 20+ with skills
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
            weights["train"] += 0.1 * lvl_granary
            weights["work"]  += 0.1 * lvl_granary
            weights["buy_food"] -= 0.1 * lvl_granary

        if lvl_clinic > 0:
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
        if t == "Stoic":
            weights["rest"] -= 0.3
            weights["train"] += 0.3
            weights["work"] += 0.2
        if t == "Naive":
            weights["socialize"] += 0.4
            weights["hangout"] += 0.3
            weights["steal"] -= 0.3
        if t == "Loyal":
            weights["work"] += 0.4
            weights["steal"] -= 0.4
            weights["socialize"] += 0.3
        if t == "Strict":
            weights["train"] += 0.4
            weights["work"] += 0.3
            weights["rest"] -= 0.2
            weights["hangout"] -= 0.2
        if t == "Patient":
            weights["study"] += 0.5
            weights["work"] += 0.3
            weights["train"] += 0.2
        
        # Achievement traits
        if t == "Patriarch":
            weights["socialize"] += 0.5
            weights["hangout"] += 0.6
            weights["work"] += 0.3
        if t == "Immortal":
            weights["rest"] += 0.4
            weights["hunt"] += 0.3
        if t == "Hunter":
            weights["hunt"] += 1.0
            weights["train"] += 0.4
        if t == "Resilient":
            weights["train"] += 0.5
            weights["hunt"] += 0.3
            weights["rest"] -= 0.2
        if t == "Genius":
            weights["study"] += 1.0
            weights["work"] += 0.4
        if t == "Fearless":
            weights["hunt"] += 0.8
            weights["train"] += 0.6
            weights["steal"] += 0.3
        if t == "Veteran":
            weights["hunt"] += 0.6
            weights["train"] += 0.4
            weights["buy_gear"] += 0.2

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
        weights["socialize"] += 0.2
        weights["hangout"] += 0.3
    if job in ["King", "Queen", "Noble"]:
        weights["work"] += 0.4
        weights["study"] += 0.4
        weights["rest"] += 0.6
        weights["socialize"] += 0.6
        weights["hangout"] += 0.6
        weights["steal"] -= 0.4
        weights["hunt"] *= 0.15
        weights["train"] *= 0.7
    if job in ["Spy"]:
        weights["steal"] += 0.8
        weights["socialize"] += 0.3

    # Skill-based action modifiers
    skills = parse_skills(villager.get("skills", ""))
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        # COMBAT skills boost train/hunt
        if cat == "COMBAT":
            weights["train"] += 0.5
            weights["hunt"] += 0.5
            weights["buy_gear"] += 0.3
        
        # CRAFT skills boost work
        if cat == "CRAFT":
            weights["work"] += 0.6
            weights["buy_gear"] += 0.2
        
        # SOCIAL skills boost socializing
        if cat == "SOCIAL":
            weights["socialize"] += 0.6
            weights["hangout"] += 0.4
            weights["work"] += 0.2
        
        # SURVIVAL skills boost hunt and reduce need for rest
        if cat == "SURVIVAL":
            weights["hunt"] += 0.5
            weights["rest"] -= 0.2
            weights["buy_food"] -= 0.1
        
        # KNOWLEDGE skills boost study
        if cat == "KNOWLEDGE":
            weights["study"] += 0.7
            weights["work"] += 0.2

    # Mentor action: only for age 20+ with skills
    age = villager.get("age", 0)
    if age >= 20 and skills:
        weights["mentor"] = 0.5  # Base weight for mentoring
        
        # Traits that boost mentoring
        for t in traits:
            if t in ("Wise", "Patient", "Generous", "Empathic"):
                weights["mentor"] += 0.4
            if t == "Strict":
                weights["mentor"] += 0.3
            if t == "Lazy":
                weights["mentor"] -= 0.3
        
        # Social/Knowledge skills boost mentoring more
        for skill_name in skills:
            info = get_skill_info(skill_name)
            if info and info.get("category") in ("SOCIAL", "KNOWLEDGE"):
                weights["mentor"] += 0.3
        
        # Teachers and scholars are natural mentors
        if job in ["Scholar", "Scribe", "Advisor", "Priest", "Druid"]:
            weights["mentor"] += 0.6

    w = (weather or "sunny").strip().lower()
    if w not in WEATHER_TYPES:
        w = "sunny"

    if w == "rain":
        weights["hunt"] *= 0.65
        weights["train"] *= 0.85
        weights["work"] *= 0.90
        weights["socialize"] *= 0.80
        weights["hangout"] *= 0.75

        weights["study"] *= 1.20
        weights["rest"] *= 1.15

        weights["buy_food"] *= 1.10

    hunger = villager.get("hunger", 50)
    coins = villager.get("coins", 0)

    if hunger >= 70 and coins >= 10:
        return "buy_food"

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


def handle_level_up(v: Villager) -> None:
    """
    Apply level-up logic in-place.
    """
    from src.utils.world_utils import exp_to_next_level

    leveled = False

    while v["exp"] >= exp_to_next_level(v["level"]):
        cost = exp_to_next_level(v["level"])
        v["exp"] -= cost
        v["level"] += 1

        v["atk"] += rand_int(1, 3)
        v["def"] += rand_int(1, 2)
        v["hp"] += rand_int(3, 6)
        leveled = True

    # HP gains from leveling - no upper cap


def create_shop_offer(v: Villager) -> ShopOffer:
    """
    Create a gear shop offer for a villager.
    """
    lvl = int(v.get("level", 1) or 1)

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
        {"type": "Traveler's Bedroll", "cost": 75 + lvl * 4,
         "bonuses": [{"key": "hp", "amt": rand_int(10, 20)}]},
    ]

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
        {"type": "Warhorn of Resolve", "cost": 180 + lvl * 11,
         "bonuses": [{"key": "rep", "amt": rand_int(5, 10)},
                     {"key": "atk", "amt": rand_int(2, 4)}]},
        {"type": "Mageweave Robe",     "cost": 170 + lvl * 10,
         "bonuses": [{"key": "int", "amt": rand_int(5, 10)},
                     {"key": "hp",  "amt": rand_int(10, 22)}]},
        {"type": "Knight's Buckler",   "cost": 190 + lvl * 11,
         "bonuses": [{"key": "def", "amt": rand_int(7, 14)},
                     {"key": "hp",  "amt": rand_int(8, 18)}]},
        {"type": "Duelist Rapier",     "cost": 200 + lvl * 12,
         "bonuses": [{"key": "atk", "amt": rand_int(7, 14)},
                     {"key": "rep", "amt": rand_int(2, 5)}]},
        {"type": "Scholar's Codex",    "cost": 185 + lvl * 11,
         "bonuses": [{"key": "int", "amt": rand_int(6, 12)},
                     {"key": "rep", "amt": rand_int(2, 4)}]},
    ]

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
        {"type": "Emperor's Signet",   "cost": 600 + lvl * 28,
         "bonuses": [{"key": "rep", "amt": rand_int(10, 18)},
                     {"key": "atk", "amt": rand_int(6, 10)},
                     {"key": "def", "amt": rand_int(6, 10)}]},
        {"type": "Archmage Focus",     "cost": 580 + lvl * 27,
         "bonuses": [{"key": "int", "amt": rand_int(16, 28)},
                     {"key": "hp",  "amt": rand_int(20, 40)}]},
        {"type": "Titan's Girdle",     "cost": 540 + lvl * 26,
         "bonuses": [{"key": "hp",  "amt": rand_int(60, 95)},
                     {"key": "def", "amt": rand_int(6, 12)}]},
    ]

    if lvl <= 3:
        pool = t1 + random.sample(t2, k=min(2, len(t2)))
    elif lvl <= 8:
        pool = t1 + t2 + random.sample(t3, k=min(2, len(t3)))
    else:
        pool = t2 + t3 + random.sample(t1, k=min(3, len(t1)))

    return random.choice(pool)


def append_action_history(v: Villager, max_len: int = 5) -> None:
    """
    Keep a rolling history of the last `max_len` actions in v['action_log'].
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
    if len(items) > max_len:
        items = items[-max_len:]

    v["action_log"] = "||".join(items)


def apply_action(
    v: Villager,
    action: str,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
) -> None:
    """
    Apply the chosen action to the villager (stats, hunger, coins, EXP).
    """
    from src.services.combat_service import create_enemy_for, resolve_combat

    # -------------------- TRAIN --------------------
    if action == "train":
        delta_atk    = rand_int(1, 3)
        delta_def    = rand_int(1, 2)
        delta_hp     = rand_int(0, 2)
        delta_hunger = rand_int(5, 12)
        delta_exp    = rand_int(2, 5)

        w = (weather or "sunny").strip().lower()
        if w == "rain":
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
                delta_hp += lvl_clinic

            if lvl_granary > 0:
                delta_hunger = max(
                    1, int(round(delta_hunger * (1 - 0.08 * lvl_granary)))
                )

        # Skill bonuses for training
        skill_bonus = get_train_bonus(v)
        delta_atk = max(1, int(round(delta_atk * skill_bonus["atk_mult"])))
        delta_def = max(1, int(round(delta_def * skill_bonus["def_mult"])))
        delta_exp = max(1, int(round(delta_exp * skill_bonus["exp_mult"])))

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

        # Rain is good for studying (stay indoors focused)
        w = (weather or "sunny").strip().lower()
        if w == "rain":
            delta_int = max(1, int(round(delta_int * 1.15)))
            delta_exp = max(1, int(round(delta_exp * 1.10)))

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

        # Skill bonuses for studying
        skill_bonus = get_study_bonus(v)
        delta_int = max(1, int(round(delta_int * skill_bonus["int_mult"])))
        delta_exp = max(1, int(round(delta_exp * skill_bonus["exp_mult"])))

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
                v["rep"] += rand_int(0, lvl_tavern)

        # Skill bonuses for work
        skill_bonus = get_work_bonus(v)
        gross = max(1, int(round(gross * skill_bonus["coin_mult"])))
        exp_delta = max(1, int(round(exp_delta * skill_bonus["exp_mult"])))

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

        # Skill bonuses for resting
        skill_bonus = get_rest_bonus(v)
        hp_delta = max(1, int(round(hp_delta * skill_bonus["hp_mult"])))
        hunger_delta = max(0, hunger_delta - skill_bonus["hunger_reduce"])

        v["hunger"] += hunger_delta
        v["hp"]     += hp_delta

    # -------------------- SOCIALIZE --------------------
    elif action == "socialize":
        # Rain reduces social interaction quality
        w = (weather or "sunny").strip().lower()
        rain_penalty = 0.85 if w == "rain" else 1.0
        
        # Skill bonuses for socializing
        skill_bonus = get_socialize_bonus(v)
        
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

                if random.random() < 0.85:
                    base_delta = rand_int(5, 15)
                    delta = int(base_delta * rain_penalty * skill_bonus["relation_mult"])
                else:
                    delta = -rand_int(1, 2)

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
        if not all_characters:
            v["hunger"] += rand_int(3, 7)
            v["hp"] += rand_int(2, 5)
            v["exp"] += rand_int(1, 3)
        else:
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
                hunger_delta = rand_int(4, 10)
                hp_delta = rand_int(1, 5)
                extra_rep = 0

                if bank is not None:
                    lvl_tavern = get_building_level(bank, "tavern")
                    lvl_granary = get_building_level(bank, "granary")

                    if lvl_tavern > 0:
                        hunger_delta = max(
                            1, int(round(hunger_delta * (1 - 0.08 * lvl_tavern)))
                        )
                        extra_rep += lvl_tavern

                    if lvl_granary > 0:
                        hunger_delta = max(
                            1, int(round(hunger_delta * (1 - 0.04 * lvl_granary)))
                        )

                for other in group:
                    if random.random() < 0.92:
                        delta = rand_int(3, 10)
                    else:
                        delta = -rand_int(1, 2)

                    adjust_relationship(v, other, delta)
                    adjust_relationship(other, v, delta)

                    if delta > 0:
                        total_delta_pos += delta

                v["hunger"] -= hunger_delta
                v["hp"] += hp_delta

                v["exp"] += rand_int(2, 5) + total_delta_pos // 6
                v["rep"] = clamp(
                    v.get("rep", 0) + total_delta_pos // 4 + extra_rep,
                    -100,
                    100,
                )

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

                    delta = -rand_int(20, 40)
                    adjust_relationship(v, target, delta)
                    adjust_relationship(target, v, delta)

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

    # -------------------- MENTOR --------------------
    elif action == "mentor":
        """
        Mentor action: Age 20+ villagers with skills can teach children.
        - Randomly selects 1-2 children as mentees
        - Teaches one of their skills
        - Children track learning progress per skill
        - After 100 lessons in a skill, child gains the skill
        - Small chance of failure (progress resets)
        - Mentor gains: relationship, reputation, small stats
        """
        mentor_skills = parse_skills(v.get("skills", ""))
        
        if not mentor_skills or not all_characters:
            # No skills to teach or no other characters
            v["hunger"] += rand_int(2, 5)
            v["last_action"] = "mentor (no one to teach)"
        else:
            # Find eligible children (age <= CHILD_MAX_AGE, alive)
            children = [
                c for c in all_characters
                if c.get("id") != v.get("id")
                and c.get("alive", True)
                and c.get("age", 100) <= CHILD_MAX_AGE
            ]
            
            if not children:
                v["hunger"] += rand_int(2, 5)
                v["last_action"] = "mentor (no children available)"
            else:
                # Select 1-2 children to mentor
                num_mentees = min(rand_int(1, 2), len(children))
                random.shuffle(children)
                mentees = children[:num_mentees]
                
                # Choose a skill to teach
                skill_to_teach = random.choice(mentor_skills)
                skill_info = get_skill_info(skill_to_teach)
                
                taught_names = []
                skills_gained = []
                progress_reset = []
                
                for child in mentees:
                    # Chance of failure (5% base, reduced by mentor's int)
                    mentor_int = v.get("int", 10)
                    fail_chance = max(0.02, 0.05 - (mentor_int / 1000))
                    
                    if random.random() < fail_chance:
                        # Learning failed - reset progress for this skill
                        reset_learning_progress(child, skill_to_teach)
                        progress_reset.append(child["name"])
                    else:
                        # Add learning progress
                        current = add_learning_progress(child, skill_to_teach, rand_int(1, 3))
                        
                        # Check if mastered (100+ lessons)
                        if current >= 100:
                            # Child gains the skill!
                            if add_skill_to_villager(child, skill_to_teach):
                                skills_gained.append((child["name"], skill_to_teach))
                                reset_learning_progress(child, skill_to_teach)
                        
                        taught_names.append(child["name"])
                    
                    # Build relationship between mentor and child
                    rel_gain = rand_int(3, 8)
                    adjust_relationship(v, child, rel_gain)
                    adjust_relationship(child, v, rel_gain)
                
                # Mentor rewards
                v["rep"] = clamp(v.get("rep", 0) + rand_int(1, 3), -100, 100)
                v["exp"] += rand_int(2, 5)
                v["int"] += rand_int(0, 1)  # Small int boost from teaching
                v["hunger"] += rand_int(3, 7)
                
                # Build action message
                action_parts = []
                if taught_names:
                    action_parts.append(f"taught {', '.join(taught_names)} [{skill_to_teach}]")
                if skills_gained:
                    for name, skill in skills_gained:
                        action_parts.append(f"{name} mastered {skill}!")
                if progress_reset:
                    action_parts.append(f"{', '.join(progress_reset)} failed to learn")
                
                if action_parts:
                    v["last_action"] = f"mentor ({'; '.join(action_parts)})"
                else:
                    v["last_action"] = "mentor (no results)"

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
            if combat.get("victory", False):
                v["last_action"] = f"dead (won vs {enemy['tier']} {enemy['name']} but died from wounds)"
            else:
                v["last_action"] = f"dead (hunt vs {enemy['tier']} {enemy['name']})"

            v["hunger"] += rand_int(3, 10)

        else:  # "LOSS"
            hunger_delta = rand_int(3, 10)

            if bank is not None:
                lvl_granary = get_building_level(bank, "granary")
                if lvl_granary > 0:
                    hunger_delta = max(1, int(round(hunger_delta * (1 - 0.05 * lvl_granary))))

            v["hunger"] += hunger_delta
            v["last_action"] = f"hunt (LOSS vs {enemy['tier']} {enemy['name']})"

    v["hunger"] = clamp(v["hunger"], 0, 100)
    # HP has no upper cap - can grow unlimited
    v["rep"] = clamp(int(v.get("rep", 0) or 0), -100, 100)

    handle_level_up(v)
