from __future__ import annotations

import random

from config import (
    WEATHER_TYPES,
)
from src.utils.world_utils import (
    clamp,
    rand_int,
    season_for_total_day,
    season_modifier,
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
from config import CHILD_MAX_AGE, MAGIC_JOBS, MINOR_MAGIC_JOBS
from src.models.villager import Villager
from src.models.bank import Bank
from src.models.combat import ShopOffer

def choose_action(villager: Villager, bank: Bank | None = None, weather: str | None = None,
                  all_characters: list[Villager] | None = None) -> str:
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
        # Theft baseline trimmed (was 0.10) — even a no-trait villager was
        # rolling it ~1% per day. Crime should be a deviation, not background.
        "steal": 0.04,
        "mentor": 0.0,  # Only enabled for age 20+ with skills
        "meditate": 0.0,  # Only enabled for magic-capable jobs
        "forge_artifact": 0.0,  # Only enabled for high-INT Blacksmith/Wizard/Sorcerer with treasury funds (Phase 7)
        "woo": 0.0,           # Only enabled for single adults 18-60 (romance — addresses marriage bottleneck)
        "visit_tavern": 0.0,  # Only enabled when Tavern Lvl ≥ 1
        "spar": 0.6,          # Available to any adult; pair training
        "drill": 0.0,         # Only enabled when Barracks Lvl ≥ 1
        "heal_sick": 0.0,     # Only enabled for Healer/Cleric/Herbalist/Priest when sick villagers exist
        # Crime/patrol actions are added below only when gating passes — they
        # are deliberately absent from the default pool so floor logic doesn't
        # dilute everyone's denominator. See "Crime gating" block.
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
            weights["drill"] = 0.5 + 0.3 * lvl_barracks  # gate: requires Barracks
            weights["spar"]  += 0.2 * lvl_barracks       # barracks encourages sparring

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
            weights["visit_tavern"] = 0.5 + 0.3 * lvl_tavern  # gate: requires Tavern

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
            weights["steal"] -= 0.3
        if t == "Greedy":
            weights["work"] += 0.8
            weights["steal"] += 0.15
        if t in ("Generous", "Empathic"):
            weights["buy_food"] += 0.4
            weights["socialize"] += 0.4
            weights["hangout"] += 0.5
            weights["steal"] -= 0.3
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
            weights["steal"] += 0.10
        if t == "Deceitful":
            # Was the single biggest crime driver (+0.50). Halved so even a
            # Deceitful villager spends most days working, not stealing.
            weights["steal"] += 0.25
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
            weights["steal"] -= 0.5
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
            weights["steal"] += 0.08
        if t == "Veteran":
            weights["hunt"] += 0.6
            weights["train"] += 0.4
            weights["buy_gear"] += 0.2

    if job in ["Soldier", "Commander", "Guard", "Captain", "Scout"]:
        weights["train"] += 1.0
        weights["hunt"] += 0.5
        weights["buy_gear"] += 0.6
        weights["steal"] -= 0.4
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
        weights["steal"] -= 0.5
        weights["hunt"] *= 0.15
        weights["train"] *= 0.7
    if job in ["Spy"]:
        # Spies are the canonical thief class — keep the bump meaningful but
        # not dominant. Was +0.40, now +0.22.
        weights["steal"] += 0.22
        weights["socialize"] += 0.3

    # Magic jobs: prefer study/meditate, less physical work
    if job in MAGIC_JOBS:
        weights["meditate"] = 1.5
        weights["study"] += 1.0
        weights["train"] *= 0.5
        weights["work"] *= 0.6
        weights["hunt"] += 0.4  # magical combat is effective
        weights["buy_gear"] += 0.3
        # Low MP triggers meditation urgency
        mp = villager.get("mp", 0)
        if mp < 30:
            weights["meditate"] += 1.5
            weights["hunt"] *= 0.5
    elif job in MINOR_MAGIC_JOBS:
        weights["meditate"] = 0.6
        weights["study"] += 0.4
        mp = villager.get("mp", 0)
        if mp < 15:
            weights["meditate"] += 0.8

    # Heal-sick (Healer/Cleric/Herbalist/Priest only, when there are sick patients)
    from config import HEALER_JOBS as _HEALER_JOBS
    if job in _HEALER_JOBS and all_characters:
        try:
            from src.services.disease_service import is_sick as _is_sick
            sick_count = sum(1 for o in all_characters if o is not villager and _is_sick(o) and o.get("alive", True))
        except Exception:
            sick_count = 0
        if sick_count > 0:
            # Strong base weight when there's even one patient; ramp with caseload
            weights["heal_sick"] = 1.5 + min(2.5, sick_count * 0.15)
            # Healers naturally suppress hunting and stealing when called to duty
            weights["hunt"]  *= 0.6
            weights["steal"] *= 0.4

    # ---- Crime gating (assault / murder) ----------------------------------
    # Only consider these for non-royal adults. Trait-driven; low rep amplifies;
    # high rep + Empathic/Loyal traits suppress.
    age_now = int(villager.get("age", 0) or 0)
    rep_now = int(villager.get("rep", 0) or 0)
    is_royal = job in ("King", "Queen")
    if age_now >= 17 and not is_royal:
        # Count alive guards for deterrence (used by both crimes)
        guard_count = 0
        if all_characters:
            try:
                from config import GUARD_JOBS as _GUARD_JOBS
                guard_count = sum(
                    1 for o in all_characters
                    if o.get("alive", True) and o.get("job") in _GUARD_JOBS
                )
            except Exception:
                guard_count = 0

        # ----- Assault -----
        # Tuned so that even a Hot-headed villager only commits assault a few
        # times a year — not weekly. Requires real provocation (low rep) or
        # multiple aggressive traits stacking.
        # Refresh 2026-05-18: per-trait pushes trimmed and the surface
        # threshold raised (0.18 → 0.22) so a single hot-tempered trait no
        # longer puts assault in the action pool every day.
        a_base = 0.01
        for t in traits:
            if t == "Hot-headed":  a_base += 0.12
            if t == "Reckless":    a_base += 0.10
            if t == "Deceitful":   a_base += 0.05
            if t == "Greedy":      a_base += 0.03
            if t == "Empathic":    a_base -= 0.35
            if t == "Cautious":    a_base -= 0.30
            if t == "Loyal":       a_base -= 0.20
            if t == "Wise":        a_base -= 0.15
            if t == "Protective":  a_base -= 0.10  # new: protective dampens aggression
        if rep_now < -5:   a_base += 0.10
        if rep_now < -15:  a_base += 0.15
        if rep_now > 10:   a_base -= 0.20
        # Guard deterrence — stronger drops when watched
        if guard_count >= 2:
            a_base *= 0.5
        if guard_count >= 5:
            a_base *= 0.35
        # Higher threshold so only motivated profiles land in the action pool.
        if a_base > 0.22:
            weights["assault"] = a_base

        # ----- Murder ----- (very rare; needs an extreme profile)
        # Refresh 2026-05-18: personality bumps trimmed and cap tightened so
        # murder stays a true outlier (~once per year per worst-case villager).
        m_base = 0.0
        # Personality core
        if "Deceitful" in traits and "Hot-headed" in traits:
            m_base = 0.018
        elif "Reckless" in traits and rep_now < -10:
            m_base = 0.010
        if rep_now < -20:
            m_base += 0.03
        # Predator profile: killers tend to have hunt wins
        if int(villager.get("huntWins", 0) or 0) >= 5:
            m_base += 0.012
        if "Empathic" in traits or "Loyal" in traits or "Wise" in traits or "Protective" in traits:
            m_base *= 0.2
        if guard_count >= 3:
            m_base *= 0.35
        # Tight cap so murder stays a true outlier event (was 0.08)
        m_base = min(0.06, max(0.0, m_base))
        if m_base > 0.05:
            weights["murder"] = m_base

    # ---- Patrol gating (Guard jobs) ---------------------------------------
    # Patrol competes with the guard's training/hunting bias — keep base modest
    # so guards split their time across duties rather than patrolling daily.
    from config import GUARD_JOBS as _GUARD_JOBS_FOR_PATROL
    if job in _GUARD_JOBS_FOR_PATROL and age_now >= 17:
        p_base = 0.5
        for t in traits:
            if t in ("Loyal", "Diligent"):  p_base += 0.20
            if t == "Brave":                p_base += 0.15
            if t == "Protective":           p_base += 0.15
            if t == "Strict":               p_base += 0.10
            if t == "Lazy":                 p_base -= 0.30
            if t == "Cautious":             p_base -= 0.05
        # Hungry guards prefer food/rest over patrolling
        if int(villager.get("hunger", 0) or 0) > 70:
            p_base *= 0.4
        if p_base > 0.0:
            weights["patrol"] = p_base

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
        
        # MAGIC skills boost meditate, study, and hunt
        if cat == "MAGIC":
            weights["meditate"] += 0.6
            weights["study"] += 0.4
            weights["hunt"] += 0.4
            weights["train"] -= 0.2

    # Spar action: trait/job tweaks (base weight enabled for any adult)
    age = villager.get("age", 0)
    if age >= 17:
        for t in traits:
            if t == "Brave":      weights["spar"] += 0.5
            if t == "Diligent":   weights["spar"] += 0.4
            if t == "Hot-headed": weights["spar"] += 0.4
            if t == "Patient":    weights["spar"] += 0.2
            if t == "Protective": weights["spar"] += 0.3
            if t == "Stoic":      weights["spar"] += 0.3   # disciplined training fits Stoic
            if t == "Lazy":       weights["spar"] -= 0.4
            if t == "Cautious":   weights["spar"] -= 0.2
        if job in ["Soldier", "Guard", "Captain", "Commander", "Scout", "Spy", "Hunter"]:
            weights["spar"] += 0.6
    else:
        weights["spar"] = 0.0  # children don't spar (they have child_daily_phase)

    # Drill: gated by Barracks (already set above); trait/job tweaks
    if weights.get("drill", 0) > 0 and age >= 17:
        for t in traits:
            if t == "Diligent":   weights["drill"] += 0.6
            if t == "Brave":      weights["drill"] += 0.4
            if t == "Patient":    weights["drill"] += 0.3
            if t == "Stoic":      weights["drill"] += 0.3
            if t == "Strict":     weights["drill"] += 0.2
            if t == "Lazy":       weights["drill"] -= 0.4
        if job in ["Soldier", "Guard", "Captain", "Commander", "Scout"]:
            weights["drill"] += 0.8
    elif age < 17:
        weights["drill"] = 0.0

    # Visit Tavern: gated by Tavern building (already set above); trait/job tweaks
    if weights.get("visit_tavern", 0) > 0:
        if villager.get("coins", 0) < 5:
            weights["visit_tavern"] = 0.0  # need at least 5 coins for a drink
        else:
            for t in traits:
                if t in ("Empathic", "Generous", "Naive"): weights["visit_tavern"] += 0.4
                if t == "Loyal":                            weights["visit_tavern"] += 0.3
                if t == "Curious":                          weights["visit_tavern"] += 0.3
                if t == "Lazy":                             weights["visit_tavern"] += 0.2
                if t == "Stoic":                            weights["visit_tavern"] -= 0.3
                if t == "Strict":                           weights["visit_tavern"] -= 0.2
            if job in ("Bard", "Innkeeper", "Brewer"):
                weights["visit_tavern"] += 0.5

    # Woo: only for single adults 18-60 (addresses marriage bottleneck)
    spouse_id = int(villager.get("spouseId", 0) or 0)
    if spouse_id == 0 and 18 <= age <= 60 and villager.get("job") not in ("Child",):
        weights["woo"] = 0.5
        for t in traits:
            if t in ("Empathic", "Patient"):  weights["woo"] += 0.5
            if t in ("Generous", "Loyal"):    weights["woo"] += 0.3
            if t == "Brave":                  weights["woo"] += 0.2
            if t == "Curious":                weights["woo"] += 0.2
            if t == "Naive":                  weights["woo"] += 0.2
            if t == "Lazy":                   weights["woo"] -= 0.3
            if t == "Stoic":                  weights["woo"] -= 0.3
            if t == "Deceitful":              weights["woo"] -= 0.3
        if job in ("Bard", "Noble"):
            weights["woo"] += 0.4
        # Tavern + Royal Court give a small boost
        if bank is not None:
            lvl_tavern_w = get_building_level(bank, "tavern")
            lvl_court_w  = get_building_level(bank, "royal_court")
            if lvl_tavern_w > 0:
                weights["woo"] += 0.2 * lvl_tavern_w
            if lvl_court_w > 0:
                weights["woo"] += 0.1 * lvl_court_w

    # Mentor action: only for age 20+ with skills
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

    # Producer jobs (Farmer/Hunter/Miner/Woodcutter/etc.) should keep working
    # even when hungry — their work is what stocks the village. Otherwise a
    # village-wide famine triggers a feedback loop where producers stop producing.
    from config import JOB_RESOURCE_YIELD
    is_producer = villager.get("job", "") in JOB_RESOURCE_YIELD

    if hunger >= 70 and coins >= 10 and not is_producer:
        return "buy_food"

    if is_producer:
        # Baseline: producers always lean toward work — their job is the
        # village's food/material supply, not a hobby.
        weights["work"] += 0.8

        # Stockpile-pressure scaling. When the town's food stockpile is low,
        # producers drop social/leisure actions and crank work up. Without
        # this, the village can spiral in early game before the first
        # Granary or trade imports stabilize supply.
        # Emergency threshold (1000) aligns with the king's emergency-import
        # trigger so producers and the crown react at the same signal.
        if bank is not None:
            try:
                stock = bank.get("resources") or {}
                food_stock = int(stock.get("food", 0) or 0)
                if food_stock < 1000:
                    # Emergency mode — everyone in the producer roster works.
                    weights["work"] += 1.5
                    weights["socialize"] *= 0.4
                    weights["hangout"] *= 0.4
                    weights["visit_tavern"] *= 0.3
                    weights["study"] *= 0.6
                elif food_stock < 1500:
                    # Cautious mode — work bias, mild leisure dampening.
                    weights["work"] += 0.6
                    weights["hangout"] *= 0.7
            except Exception:
                pass

        # Hungry producer: still bias toward work, not buy_food.
        if hunger >= 70:
            weights["work"] += 1.5

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
        # Hardship still pushes some villagers toward theft, but no longer
        # doubles a Deceitful villager's steal weight on poor days.
        weights["steal"] += 0.10
    elif coins > 150:
        weights["buy_food"] += 0.4
        weights["steal"] -= 0.25

    if coins > 200 and hunger < 60:
        weights["buy_gear"] += 0.8
    if coins > 400 and hunger < 50:
        weights["buy_gear"] += 0.8

    if coins < 60:
        weights["buy_gear"] -= 0.4

    # Forge artifact: heavily gated. The full eligibility check lives in
    # artifact_service.can_forge() — we don't even surface the action unless
    # every prerequisite is met. See can_forge() for the parameter list.
    try:
        from src.services.artifact_service import can_forge
        eligible, _reason = can_forge(villager, bank, current_day=None)
        if eligible:
            v_int = int(villager.get("int", 0) or 0)
            base = 0.30  # modest weight — forging is special, not routine
            if v_int >= 70:
                base += 0.20
            if job == "Blacksmith":
                base += 0.08 * (get_building_level(bank, "blacksmith") if bank else 0)
            if job in ("Wizard", "Sorcerer"):
                base += 0.08 * (get_building_level(bank, "library") if bank else 0)
            weights["forge_artifact"] = base
    except Exception:
        pass

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

        # MP gain on level up based on job
        lvl_job = v.get("job", "")
        if lvl_job in MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(5, 12)
        elif lvl_job in MINOR_MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(2, 5)
        else:
            # Non-magic jobs gain tiny MP occasionally
            if random.random() < 0.15:
                v["mp"] = v.get("mp", 0) + rand_int(1, 2)

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
        {"type": "Mana Crystal",    "cost": rand_int(30, 80) + lvl * 3,
         "bonuses": [{"key": "mp", "amt": rand_int(8, 18)}]},
        {"type": "Spell Scroll",    "cost": rand_int(40, 100) + lvl * 4,
         "bonuses": [{"key": "mp", "amt": rand_int(5, 12)},
                     {"key": "int", "amt": rand_int(1, 3)}]},
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
                     {"key": "mp",  "amt": rand_int(12, 25)}]},
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
                     {"key": "mp",  "amt": rand_int(25, 50)}]},
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
    current_day: int | None = None,
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

        # Studying grants small MP to magic-capable jobs
        study_job = v.get("job", "")
        if study_job in MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(3, 8)
        elif study_job in MINOR_MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(1, 4)

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

        # Resource production: jobs like Farmer/Miner/Woodcutter deposit raw materials
        # into the shared town stockpile in addition to their coin income.
        produced: dict[str, int] = {}
        if bank is not None:
            from config import JOB_RESOURCE_YIELD, PRODUCTION_BUILDING_BONUS
            job = v.get("job", "")
            yield_table = JOB_RESOURCE_YIELD.get(job, {})
            if yield_table:
                stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
                level_mult = 1.0 + 0.10 * max(0, int(v.get("level", 1)) - 1)
                weather_mult = 1.0
                if (weather or "sunny").lower() == "rain" and job == "Farmer":
                    weather_mult = 0.5

                # Production-building bonus: each specialized building gives
                # +25/50/75% (per level) to specific jobs that work in it.
                building_mult = 1.0
                for b_key, job_bonus in PRODUCTION_BUILDING_BONUS.items():
                    if job in job_bonus:
                        lvl = get_building_level(bank, b_key)
                        if lvl > 0:
                            building_mult += job_bonus[job] * lvl

                # Seasonal modifier on food output only — wood/stone/iron yields
                # are unaffected. Winter cuts farm yields hard; autumn is peak
                # harvest; summer/spring sit just above baseline.
                season_now = season_for_total_day(int(current_day or 0))
                farm_mult = season_modifier(season_now, "farm_mult", 1.0)

                total_mult = level_mult * weather_mult * building_mult
                for res, amt in yield_table.items():
                    res_mult = total_mult * (farm_mult if res == "food" else 1.0)
                    gain = max(1, int(round(amt * res_mult)))
                    stock[res] = int(stock.get(res, 0)) + gain
                    produced[res] = gain

        # --- Blacksmith iron consumption ---
        # Blacksmith no longer mines iron; instead, each work tick consumes
        # 1 iron from the town stockpile and forges it into goods sold for
        # bonus coin. Smelter level amplifies the conversion. This gives
        # iron a recurring sink so it stops piling up.
        forged_coin = 0
        forged_iron = 0
        if bank is not None and v.get("job") == "Blacksmith":
            stock = bank.setdefault(
                "resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0}
            )
            iron_have = int(stock.get("iron", 0) or 0)
            if iron_have > 0:
                forged_iron = 1
                stock["iron"] = iron_have - 1
                smelter_lvl = get_building_level(bank, "smelter")
                forged_coin = rand_int(8, 16) + smelter_lvl * rand_int(3, 6)
                v["coins"] += forged_coin

        if tax > 0 or produced or forged_iron > 0:
            parts = [f"earned {net} coins"]
            if tax > 0:
                parts.append(f"paid {tax} coins in tax")
            if produced:
                parts.append("produced " + ", ".join(f"+{n} {r}" for r, n in produced.items()))
            if forged_iron > 0:
                parts.append(f"forged {forged_iron} iron (+{forged_coin} coins)")
            v["last_action"] = "work (" + ", ".join(parts) + ")"

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

        # Resting also recovers some MP for magic users
        rest_job = v.get("job", "")
        if rest_job in MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(3, 8)
        elif rest_job in MINOR_MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(1, 4)

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

                # Disease transmission: bilateral attempt between the pair.
                try:
                    from src.services.disease_service import try_transmit
                    day_for_inf = current_day if current_day is not None else 0
                    try_transmit(v, other, day_for_inf, "contact")
                    try_transmit(other, v, day_for_inf, "contact")
                except Exception:
                    pass

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

                # Disease transmission across the whole group (and v).
                try:
                    from src.services.disease_service import try_transmit
                    day_for_inf = current_day if current_day is not None else 0
                except Exception:
                    try_transmit = None
                    day_for_inf = 0

                for other in group:
                    if random.random() < 0.92:
                        delta = rand_int(3, 10)
                    else:
                        delta = -rand_int(1, 2)

                    adjust_relationship(v, other, delta)
                    adjust_relationship(other, v, delta)

                    if try_transmit is not None:
                        try_transmit(v, other, day_for_inf, "contact")
                        try_transmit(other, v, day_for_inf, "contact")

                    if delta > 0:
                        total_delta_pos += delta

                v["hunger"] -= hunger_delta
                v["hp"] += hp_delta

                v["exp"] += rand_int(2, 5) + total_delta_pos // 6
                v["rep"] = v.get("rep", 0) + total_delta_pos // 4 + extra_rep

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
            v["rep"] = v.get("rep", 0) - rand_int(1, 4)
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
                v["rep"] = v.get("rep", 0) - rand_int(1, 4)
                v["last_action"] = (
                    f"steal (no rich target, worked instead, earned {gross} coins)"
                )
            else:
                target = random.choice(victims)
                max_steal = min(target.get("coins", 0), rand_int(5, 30))

                if max_steal <= 0:
                    v["hunger"] += rand_int(2, 5)
                    v["rep"] = v.get("rep", 0) - rand_int(2, 6)
                    v["last_action"] = (
                        f"steal (failed, no coins from {target['name']})"
                    )
                else:
                    target["coins"] -= max_steal
                    v["coins"] += max_steal

                    delta = -rand_int(20, 40)
                    adjust_relationship(v, target, delta)
                    adjust_relationship(target, v, delta)

                    v["rep"] = v.get("rep", 0) - rand_int(4, 10)

                    v["hunger"] += rand_int(3, 8)
                    v["exp"] += rand_int(2, 4)

                    v["last_action"] = (
                        f"steal from {target['name']} "
                        f"(+{max_steal} coins, {delta} relation)"
                    )

                    # Witness roll: may upgrade this into a pending theft case.
                    try:
                        from src.services.justice_service import maybe_witness_and_record
                        maybe_witness_and_record(
                            bank=bank,
                            criminal=v,
                            victim=target,
                            crime_type="theft",
                            characters=all_characters,
                            current_day=int(current_day or 0),
                        )
                    except Exception:
                        pass

    # -------------------- ASSAULT --------------------
    elif action == "assault":
        candidates = []
        if all_characters:
            candidates = [
                o for o in all_characters
                if o.get("id") != v.get("id")
                and o.get("alive", True)
                and int(o.get("age", 0) or 0) >= 12
                and o.get("job") != "Child"
            ]
        if not candidates:
            v["last_action"] = "assault (no target found, brooded instead)"
            v["hunger"] += rand_int(2, 5)
        else:
            # Prefer a rival — lowest relationship score
            try:
                from src.services.relationship_service import get_relationship_score
                def _rival_score(o):
                    return get_relationship_score(v, int(o.get("id", 0) or 0))
                target = min(candidates, key=_rival_score)
            except Exception:
                target = random.choice(candidates)

            atk = int(v.get("atk", 1) or 1)
            df  = int(target.get("def", 1) or 1)
            base_damage = max(5, atk - df // 2) + rand_int(4, 12)
            target["hp"] = int(target.get("hp", 0) or 0) - base_damage

            # Big relationship hit both ways
            delta = -rand_int(35, 60)
            adjust_relationship(v, target, delta)
            adjust_relationship(target, v, delta)

            v["rep"] = int(v.get("rep", 0) or 0) - rand_int(6, 12)
            v["exp"] += rand_int(2, 5)
            v["hunger"] += rand_int(5, 9)

            killed = False
            if target.get("hp", 0) <= 0 and target.get("alive", True):
                target["alive"] = False
                target["hp"] = 0
                target["death_day"] = int(current_day or 0)
                target["last_action"] = f"killed in assault by {v.get('name','?')}"
                killed = True
                try:
                    from src.services.chronicle_service import record_death
                    record_death(target, cause=f"assault by {v.get('name','?')}", day=int(current_day or 0))
                except Exception:
                    pass

            v["last_action"] = (
                f"assault {target['name']} (-{base_damage} HP, {delta} relation"
                + (", killed" if killed else "") + ")"
            )

            # If the assault was lethal, upgrade the witnessed crime to murder.
            crime_label = "murder" if killed else "assault"
            try:
                from src.services.justice_service import maybe_witness_and_record
                maybe_witness_and_record(
                    bank=bank,
                    criminal=v,
                    victim=target,
                    crime_type=crime_label,
                    characters=all_characters,
                    current_day=int(current_day or 0),
                )
            except Exception:
                pass

    # -------------------- MURDER --------------------
    elif action == "murder":
        candidates = []
        if all_characters:
            candidates = [
                o for o in all_characters
                if o.get("id") != v.get("id")
                and o.get("alive", True)
                and int(o.get("age", 0) or 0) >= 12
                and o.get("job") != "Child"
            ]
        if not candidates:
            v["last_action"] = "murder (no target found, brooded instead)"
            v["hunger"] += rand_int(2, 5)
        else:
            # Cold killers target their deepest rival.
            try:
                from src.services.relationship_service import get_relationship_score
                def _hate_score(o):
                    return get_relationship_score(v, int(o.get("id", 0) or 0))
                target = min(candidates, key=_hate_score)
            except Exception:
                target = random.choice(candidates)

            atk = int(v.get("atk", 1) or 1)
            df  = int(target.get("def", 1) or 1)
            # Premeditated — lethal damage.
            damage = max(20, atk * 2 - df) + rand_int(10, 25)
            target["hp"] = int(target.get("hp", 0) or 0) - damage

            delta = -rand_int(80, 100)
            adjust_relationship(v, target, delta)
            adjust_relationship(target, v, delta)

            v["rep"] = int(v.get("rep", 0) or 0) - rand_int(15, 25)
            v["exp"] += rand_int(3, 6)
            v["hunger"] += rand_int(6, 12)

            killed = False
            if target.get("hp", 0) <= 0 and target.get("alive", True):
                target["alive"] = False
                target["hp"] = 0
                target["death_day"] = int(current_day or 0)
                target["last_action"] = f"murdered by {v.get('name','?')}"
                killed = True
                try:
                    from src.services.chronicle_service import record_death
                    record_death(target, cause=f"murdered by {v.get('name','?')}", day=int(current_day or 0))
                except Exception:
                    pass

            v["last_action"] = (
                f"murder attempt on {target['name']} (-{damage} HP"
                + (", killed" if killed else ", survived") + ")"
            )

            # Crime category is murder if lethal, assault if the victim survived.
            crime_label = "murder" if killed else "assault"
            try:
                from src.services.justice_service import maybe_witness_and_record
                maybe_witness_and_record(
                    bank=bank,
                    criminal=v,
                    victim=target,
                    crime_type=crime_label,
                    characters=all_characters,
                    current_day=int(current_day or 0),
                )
            except Exception:
                pass

    # -------------------- PATROL --------------------
    elif action == "patrol":
        # Guards on duty: light training + rep gain. Their presence has already
        # been counted by witness_chance via `_alive_guards`; setting
        # last_action to start with "patrol" promotes them into the patroller
        # bucket used by `_patrollers_today`.
        atk_gain = rand_int(0, 1)
        def_gain = rand_int(1, 2)
        rep_gain = rand_int(1, 2)
        exp_gain = rand_int(2, 4)
        hunger_gain = rand_int(4, 8)

        if bank is not None:
            lvl_walls = get_building_level(bank, "walls")
            lvl_barracks = get_building_level(bank, "barracks")
            if lvl_walls > 0:
                def_gain += 1
            if lvl_barracks > 0:
                atk_gain += 1
                exp_gain += lvl_barracks

        v["atk"] += atk_gain
        v["def"] += def_gain
        v["rep"] = int(v.get("rep", 0) or 0) + rep_gain
        v["exp"] += exp_gain
        v["hunger"] += hunger_gain
        v["last_action"] = (
            f"patrol the streets (+{def_gain} DEF, +{rep_gain} REP)"
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
                v["rep"] = v.get("rep", 0) + rand_int(1, 3)
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

    # -------------------- MEDITATE --------------------
    elif action == "meditate":
        job = v.get("job", "")
        mp_regen = rand_int(8, 20)
        int_gain = rand_int(0, 2)
        hp_gain = rand_int(1, 4)
        hunger_delta = rand_int(3, 7)
        exp_delta = rand_int(2, 5)

        # Magic jobs get much more from meditation
        if job in MAGIC_JOBS:
            mp_regen = rand_int(15, 40)
            int_gain = rand_int(1, 3)
            exp_delta = rand_int(3, 7)
        elif job in MINOR_MAGIC_JOBS:
            mp_regen = rand_int(10, 25)

        # Rain is atmospheric, good for meditation
        w = (weather or "sunny").strip().lower()
        if w == "rain":
            mp_regen = max(1, int(round(mp_regen * 1.15)))
            int_gain = max(0, int(round(int_gain * 1.10)))

        if bank is not None:
            lvl_temple = get_building_level(bank, "temple")
            lvl_library = get_building_level(bank, "library")
            if lvl_temple > 0:
                mp_regen = max(1, int(round(mp_regen * (1 + 0.20 * lvl_temple))))
            if lvl_library > 0:
                int_gain += rand_int(0, lvl_library)

        v["mp"] = v.get("mp", 0) + mp_regen
        v["int"] += int_gain
        v["hp"] += hp_gain
        v["exp"] += exp_delta
        v["hunger"] += hunger_delta
        v["last_action"] = f"meditate (+{mp_regen} MP, +{int_gain} INT)"

    # -------------------- HEAL SICK (Healer/Cleric/Herbalist/Priest) --------
    elif action == "heal_sick":
        from src.services.disease_service import (
            find_sick_in_circle, cure_chance, cure as cure_patient, is_sick,
        )
        from config import DISEASES, HEALER_JOBS
        from src.repositories.world_repo import load_day

        day_for_heal = current_day if current_day is not None else load_day()

        if v.get("job") not in HEALER_JOBS:
            v["hunger"] += rand_int(1, 3)
            v["last_action"] = "considered healing but not a healer"
        else:
            patients = find_sick_in_circle(v, all_characters or [], limit=1)
            if not patients:
                v["hunger"] += rand_int(1, 3)
                v["hp"] += rand_int(0, 2)
                v["last_action"] = "looked for the sick (none found)"
            else:
                patient = patients[0]
                disease = (patient.get("disease") or "").strip()
                p = cure_chance(patient, v, bank)
                roll = random.random()
                v["hunger"] += rand_int(3, 7)
                v["exp"] += rand_int(2, 5)
                if roll < p:
                    cure_patient(patient, v, day_for_heal)
                    # Reward the healer
                    v["rep"] = int(v.get("rep", 0) or 0) + rand_int(2, 5)
                    coin_tip = rand_int(2, 8)
                    v["coins"] = int(v.get("coins", 0) or 0) + coin_tip
                    illness_name = DISEASES.get(disease, {}).get("name", disease) if disease else "illness"
                    v["last_action"] = f"cured {patient.get('name','?')} of {illness_name.lower()} (+{coin_tip}g tip)"
                    # Annotate patient too
                    last = patient.get("last_action") or ""
                    patient["last_action"] = (last + " / " if last else "") + f"cured by {v.get('name','a healer')}"
                    # Chronicle
                    try:
                        from src.services.chronicle_service import record_disease_cure
                        record_disease_cure(v, patient, disease, day=int(day_for_heal))
                    except Exception:
                        pass
                else:
                    illness_name = DISEASES.get(disease, {}).get("name", disease) if disease else "illness"
                    v["last_action"] = f"tended to {patient.get('name','?')} ({illness_name.lower()}, no cure yet)"

    # -------------------- FORGE ARTIFACT (Phase 7) --------------------
    elif action == "forge_artifact":
        from src.services import artifact_service
        from src.repositories import artifact_repo
        from src.repositories.world_repo import load_day
        from src.services.chronicle_service import _safe_record, _yd, _actor

        day_for_drop = current_day if current_day is not None else load_day()

        # Defense in depth: re-check eligibility (the action weight is 0.05 floor
        # so non-eligible villagers can rarely still pick this; we punt them).
        eligible, reason = artifact_service.can_forge(v, bank, current_day=day_for_drop)
        if not eligible:
            v["hp"] += rand_int(1, 3)
            v["hunger"] += rand_int(2, 4)
            v["last_action"] = f"considered forging but couldn't ({reason})"
        else:
            # Cost scales with INT (more skilled smiths use rarer materials).
            cost = rand_int(artifact_service.FORGE_BASE_COST_MIN,
                            artifact_service.FORGE_BASE_COST_MAX)
            v_int = int(v.get("int", 0) or 0)
            if v_int >= 80:
                cost += rand_int(150, 350)
            bank["balance"] = max(0, int(bank.get("balance", 0) or 0) - cost)
            v["last_forge_day"] = int(day_for_drop or 0)
            v["hunger"] += rand_int(10, 20)

            # Random failure even when fully eligible — forging is hard.
            if random.random() < artifact_service.FORGE_FAILURE_CHANCE:
                v["exp"] = int(v.get("exp", 0) or 0) + rand_int(4, 8)
                v["last_action"] = (
                    f"forge attempt failed — materials wasted ({cost}g treasury)"
                )
            else:
                # Rarity weights skew strongly toward common; rare is exceptional.
                if v_int >= 80:
                    roll_weights = {"common": 0.55, "uncommon": 0.40, "rare": 0.05}
                else:
                    roll_weights = {"common": 0.80, "uncommon": 0.18, "rare": 0.02}

                rarity = artifact_service._pick_weighted(roll_weights)

                if v.get("job", "") == "Blacksmith":
                    slot_pool = ["weapon", "armor"]
                else:
                    slot_pool = ["weapon", "armor", "ring", "tome"]

                candidates = [t for t in artifact_service.list_templates()
                              if t.get("rarity") == rarity and t.get("slot") in slot_pool
                              and (t.get("binding") or "none") != "soulbound"]
                if not candidates:
                    candidates = [t for t in artifact_service.list_templates()
                                  if t.get("rarity") == rarity
                                  and (t.get("binding") or "none") != "soulbound"]

                if not candidates:
                    v["last_action"] = (
                        f"forge produced no fitting design ({cost}g spent)"
                    )
                else:
                    template = random.choice(candidates)
                    artifact_id = artifact_repo.create_artifact(
                        slug=template["slug"],
                        owner_id=int(v.get("id", 0) or 0),
                        acquired_day=int(day_for_drop or 0),
                        acquired_via=f"forge:{v.get('job','')}",
                        forged_history=[
                            {
                                "owner_id": int(v.get("id", 0) or 0),
                                "owner_name": (v.get("name") or "").strip(),
                                "day": int(day_for_drop or 0),
                                "event": "acquired",
                                "via": f"forged at the {v.get('job','craft').lower()}'s bench",
                            }
                        ],
                    )
                    artifact_service.auto_equip_if_better(v, artifact_id, template)
                    v["int"] = v_int + rand_int(1, 2)
                    v["exp"] = int(v.get("exp", 0) or 0) + rand_int(12, 24)
                    v["last_action"] = (
                        f"forged the {template.get('name','artifact')} ({cost}g treasury)"
                    )

                    # Chronicle entry — importance scales with rarity.
                    try:
                        year, _ = _yd(int(day_for_drop or 0))
                        rar = template.get("rarity", "common")
                        importance = 4 if rar == "rare" else 3 if rar == "uncommon" else 2
                        _safe_record(
                            day=int(day_for_drop or 0),
                            year=year,
                            category="economy",
                            headline=f"{v.get('name','?')} forges the {template.get('name','artifact')}",
                            body=(
                                f"{v.get('name','?')} of the {v.get('family','unknown')} family "
                                f"shaped a new {template.get('slot','tool')} at the cost of {cost} coins "
                                f"from the treasury."
                            ),
                            actors=[_actor(v)],
                            importance=importance,
                        )
                    except Exception:
                        pass

    # -------------------- SPAR --------------------
    elif action == "spar":
        v_id = v.get("id")
        v_age = int(v.get("age", 0) or 0)
        military_jobs = ["Soldier", "Guard", "Captain", "Commander", "Scout", "Hunter", "Spy"]

        candidates = []
        if all_characters:
            candidates = [
                o for o in all_characters
                if o.get("id") != v_id
                and o.get("alive", True)
                and int(o.get("age", 0) or 0) >= 17
                and int(o.get("hp", 0) or 0) >= 30
            ]

        if not candidates:
            v["atk"] += rand_int(0, 1)
            v["def"] += rand_int(0, 1)
            v["hp"]  -= rand_int(0, 2)
            v["hunger"] += rand_int(4, 8)
            v["exp"] += rand_int(1, 3)
            v["last_action"] = "spar (no partner — solo drills)"
            if v.get("hp", 0) <= 0 and v.get("alive", True):
                v["alive"] = False
                v["hp"] = 0
                v["death_day"] = int(current_day or 0)
                v["last_action"] = "died from solo spar drills (training accident)"
                try:
                    from src.services.chronicle_service import record_death
                    record_death(v, cause="training accident", day=int(current_day or 0))
                except Exception:
                    pass
        else:
            def spar_score(o):
                age_close = -abs(int(o.get("age", 0) or 0) - v_age)
                mil_bonus = 5 if o.get("job") in military_jobs else 0
                return age_close + mil_bonus + random.random() * 2
            partner = max(candidates, key=spar_score)

            atk_gain = rand_int(1, 2)
            def_gain = rand_int(1, 2)
            exp_gain = rand_int(2, 4)
            hp_loss = rand_int(1, 4)
            hunger_gain = rand_int(5, 10)

            if bank is not None:
                lvl_b = get_building_level(bank, "barracks")
                if lvl_b > 0:
                    atk_gain += lvl_b // 2
                    def_gain += lvl_b // 2
                    exp_gain += lvl_b

            v["atk"] += atk_gain
            v["def"] += def_gain
            v["exp"] += exp_gain
            v["hp"]  -= hp_loss
            v["hunger"] += hunger_gain

            partner["atk"] = int(partner.get("atk", 0) or 0) + atk_gain
            partner["def"] = int(partner.get("def", 0) or 0) + def_gain
            partner["exp"] = int(partner.get("exp", 0) or 0) + exp_gain
            partner["hp"]  = int(partner.get("hp", 0) or 0) - hp_loss
            partner["hunger"] = int(partner.get("hunger", 0) or 0) + hunger_gain

            rel_delta = rand_int(3, 8)
            adjust_relationship(v, partner, rel_delta)
            adjust_relationship(partner, v, rel_delta)

            v["last_action"] = (
                f"spar with {partner['name']} "
                f"(+{atk_gain} ATK, +{def_gain} DEF, +{rel_delta} relation)"
            )

            # Training accidents — either partner can die from accumulated damage.
            partner_name = partner.get("name", "a sparring partner")
            v_name = v.get("name", "a sparring partner")
            day_for_death = int(current_day or 0)
            try:
                from src.services.chronicle_service import record_death
            except Exception:
                record_death = None

            if v.get("hp", 0) <= 0 and v.get("alive", True):
                v["alive"] = False
                v["hp"] = 0
                v["death_day"] = day_for_death
                v["last_action"] = f"died from spar with {partner_name} (training accident)"
                if record_death is not None:
                    try:
                        record_death(v, cause=f"sparring accident with {partner_name}", day=day_for_death)
                    except Exception:
                        pass

            if partner.get("hp", 0) <= 0 and partner.get("alive", True):
                partner["alive"] = False
                partner["hp"] = 0
                partner["death_day"] = day_for_death
                partner["last_action"] = f"died from spar with {v_name} (training accident)"
                if record_death is not None:
                    try:
                        record_death(partner, cause=f"sparring accident with {v_name}", day=day_for_death)
                    except Exception:
                        pass

    # -------------------- DRILL --------------------
    elif action == "drill":
        lvl_b = get_building_level(bank, "barracks") if bank is not None else 0
        if lvl_b <= 0:
            v["atk"] += rand_int(1, 2)
            v["def"] += rand_int(1, 2)
            v["hunger"] += rand_int(6, 10)
            v["exp"] += rand_int(2, 4)
            v["last_action"] = "drill (no barracks — basic training)"
        else:
            base = 1 + lvl_b
            atk_gain = base + rand_int(0, 1)
            def_gain = base + rand_int(0, 1)
            exp_gain = rand_int(3, 6) + lvl_b * 2
            hp_gain = lvl_b
            hunger_gain = rand_int(8, 14)

            if bank is not None:
                lvl_smith = get_building_level(bank, "blacksmith")
                if lvl_smith > 0:
                    atk_gain += 1

            skill_bonus = get_train_bonus(v)
            atk_gain = max(1, int(round(atk_gain * skill_bonus["atk_mult"])))
            def_gain = max(1, int(round(def_gain * skill_bonus["def_mult"])))
            exp_gain = max(1, int(round(exp_gain * skill_bonus["exp_mult"])))

            v["atk"] += atk_gain
            v["def"] += def_gain
            v["hp"]  += hp_gain
            v["exp"] += exp_gain
            v["hunger"] += hunger_gain

            v["last_action"] = (
                f"drill at barracks Lvl {lvl_b} "
                f"(+{atk_gain} ATK, +{def_gain} DEF)"
            )

    # -------------------- VISIT TAVERN --------------------
    elif action == "visit_tavern":
        lvl_t = get_building_level(bank, "tavern") if bank is not None else 0
        coins_have = int(v.get("coins", 0) or 0)
        cost = rand_int(5, 10)

        if coins_have < cost or lvl_t <= 0:
            v["last_action"] = "visit tavern (couldn't afford it)"
        else:
            v["coins"] -= cost
            v_gender = v.get("gender")
            v_single = int(v.get("spouseId", 0) or 0) == 0
            v_family = v.get("family")

            candidates = []
            if all_characters:
                candidates = [
                    o for o in all_characters
                    if o.get("id") != v.get("id")
                    and o.get("alive", True)
                    and int(o.get("age", 0) or 0) >= 17
                ]

            # If villager is single, bias toward M-F unmarried adults
            if v_single and candidates:
                mf_singles = [
                    o for o in candidates
                    if int(o.get("spouseId", 0) or 0) == 0
                    and o.get("gender") in ("Male", "Female")
                    and o.get("gender") != v_gender
                    and 18 <= int(o.get("age", 0) or 0) <= 60
                    and o.get("family") != v_family
                ]
                if mf_singles and random.random() < 0.7:
                    candidates = mf_singles

            if not candidates:
                v["hunger"] -= rand_int(2, 5)
                v["hp"] += rand_int(1, 3)
                v["last_action"] = f"visit tavern (no company, -{cost} coins)"
            else:
                random.shuffle(candidates)
                group = candidates[:rand_int(1, 3)]
                total_gain = 0
                for other in group:
                    delta = rand_int(2, 5) + lvl_t
                    adjust_relationship(v, other, delta)
                    adjust_relationship(other, v, delta)
                    total_gain += delta

                v["hunger"] -= rand_int(3, 6)
                v["hp"] += rand_int(1, 4)
                v["exp"] += rand_int(1, 2)
                v["rep"] = v.get("rep", 0) + rand_int(0, lvl_t)

                names = ", ".join(o.get("name", "?") for o in group[:2])
                if len(group) > 2:
                    names += f" + {len(group) - 2}"
                v["last_action"] = (
                    f"visit tavern with {names} "
                    f"(-{cost} coins, +{total_gain} relation)"
                )

    # -------------------- WOO --------------------
    elif action == "woo":
        from src.services.relationship_service import get_relationship_score

        if not all_characters or int(v.get("spouseId", 0) or 0) != 0:
            v["hunger"] += rand_int(1, 3)
            v["last_action"] = "woo (no one available)"
        else:
            v_id = v.get("id")
            v_gender = v.get("gender")
            v_family = v.get("family")
            candidates = [
                o for o in all_characters
                if o.get("id") != v_id
                and o.get("alive", True)
                and int(o.get("spouseId", 0) or 0) == 0
                and o.get("gender") in ("Male", "Female")
                and o.get("gender") != v_gender
                and 18 <= int(o.get("age", 0) or 0) <= 60
                and o.get("family") != v_family
            ]
            if not candidates:
                v["hunger"] += rand_int(2, 4)
                v["last_action"] = "woo (found no one suitable)"
            else:
                # Prefer targets in the "stuck zone" 30-84 — no point wooing already-proposable pairs
                def woo_score(o):
                    s1 = get_relationship_score(v, o["id"])
                    s2 = get_relationship_score(o, v_id)
                    mutual = min(s1, s2)
                    if mutual >= 85:
                        return -1000  # already proposable
                    return mutual + random.random() * 5
                partner = max(candidates, key=woo_score)

                base = rand_int(5, 12)
                traits_set = {t.strip() for t in (v.get("traits", "") or "").split(",") if t.strip()}
                if "Empathic" in traits_set or "Patient" in traits_set:
                    base += 2
                if "Generous" in traits_set:
                    base += 1
                if "Deceitful" in traits_set:
                    base -= 2

                atmosphere = 0
                if bank is not None:
                    atmosphere += get_building_level(bank, "tavern")
                    atmosphere += get_building_level(bank, "royal_court") // 2

                sk_bonus = get_socialize_bonus(v)
                base = max(1, int(round(base * sk_bonus["relation_mult"])))

                delta = base + atmosphere
                if random.random() < 0.10:
                    delta = -rand_int(1, 3)

                adjust_relationship(v, partner, delta)
                adjust_relationship(partner, v, delta)

                v["hunger"] += rand_int(3, 6)
                v["exp"] += rand_int(1, 2)
                if delta > 0:
                    v["rep"] = v.get("rep", 0) + 1

                label = relationship_label(v, partner)
                sign = "+" if delta > 0 else ""
                tail = f" → {label}" if label and delta > 0 else ""
                v["last_action"] = (
                    f"woo {partner['name']} "
                    f"({sign}{delta} relation{tail})"
                )

    # -------------------- HUNT --------------------
    elif action == "hunt":
        enemy  = create_enemy_for(v)
        combat = resolve_combat(v, enemy, bank, weather=weather)

        won_hunt = (combat["outcome"] == "WIN") or (combat["outcome"] == "DEAD" and combat.get("victory", False))
        if won_hunt:
            v["huntWins"] = int(v.get("huntWins", 0) or 0) + 1
            v["huntWinsYear"] = int(v.get("huntWinsYear", 0) or 0) + 1

            # Phase 2: artifact drop on kill (live killers only — drops on a
            # post-mortem victory go nowhere because the corpse can't carry it).
            if v.get("alive", True):
                try:
                    from src.services.artifact_service import drop_for_kill
                    from src.services.chronicle_service import record_artifact_drop
                    from src.repositories.world_repo import load_day

                    day_for_drop = current_day if current_day is not None else load_day()
                    drop = drop_for_kill(v, enemy, day_for_drop)
                    if drop:
                        record_artifact_drop(
                            killer=v,
                            enemy=enemy,
                            template=drop["template"],
                            equipped=drop["equipped"],
                            day=int(day_for_drop),
                        )
                except Exception:
                    # Drops are decorative — never break the sim loop.
                    pass

        if combat["outcome"] == "WIN":
            hunger_delta = -rand_int(5, 14)

            if bank is not None:
                lvl_granary = get_building_level(bank, "granary")
                if lvl_granary > 0:
                    hunger_delta = int(round(hunger_delta * (1 + 0.10 * lvl_granary)))

            v["hunger"] += hunger_delta

            # Meat/hides from the kill go into the town stockpile.
            meat_gain = 0
            if bank is not None:
                from config import HUNT_FOOD_PER_KILL
                tier_mult = {"common": 1, "elite": 2, "legendary": 3}.get(
                    str(enemy.get("tier", "common")).lower(), 1
                )
                # Seasonal hunt yield: game is fat in autumn, scarce in winter.
                season_now = season_for_total_day(int(current_day or 0))
                hunt_mult = season_modifier(season_now, "hunt_food_mult", 1.0)
                meat_gain = max(1, int(round(HUNT_FOOD_PER_KILL * tier_mult * hunt_mult)))
                stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
                stock["food"] = int(stock.get("food", 0)) + meat_gain

            tax_paid = combat.get("taxPaid", 0)
            extras = []
            if tax_paid > 0:
                extras.append(f"paid {tax_paid} tax")
            if meat_gain > 0:
                extras.append(f"+{meat_gain} food")
            tail = f", {', '.join(extras)}" if extras else ""
            v["last_action"] = f"hunt (WIN vs {enemy['tier']} {enemy['name']}{tail})"

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
    # rep has no cap either - can grow unbounded for fame, fall unbounded for disgrace
    v["rep"] = int(v.get("rep", 0) or 0)

    handle_level_up(v)
