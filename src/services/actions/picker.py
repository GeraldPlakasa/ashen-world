"""Action picker — choose_action() and the weight table it builds.

This is the largest single function in the codebase by design: every
trait / job / building / weather / hunger / coins lever feeds into a
single weighted-random selection. Splitting it further fragments the
weight table and hides the holistic balance.

If you're adding a new action:
  1. Add a base weight (or 0.0 if gated) to the `weights` dict below.
  2. Add the trait/job/building/skill modifiers in the matching block.
  3. Register the apply_<action> handler in `src/services/actions/__init__.py`.
"""
from __future__ import annotations

import random

from config import (
    WEATHER_TYPES,
    MAGIC_JOBS,
    MINOR_MAGIC_JOBS,
)
from src.services.building_service import get_building_level
from src.services.skill_service import parse_skills, get_skill_info
from src.models.villager import Villager
from src.models.bank import Bank


def choose_action(
    villager: Villager,
    bank: Bank | None = None,
    weather: str | None = None,
    all_characters: list[Villager] | None = None,
) -> str:
    """Decide the villager's action for the day based on traits, job, hunger,
    coins, weather, and building levels."""
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
    if job in ("King", "Queen"):
        # Royals never pickpocket — they already have an abuse-of-power
        # mechanic (corruption tracking + assassination risk in
        # relationship_service.king_assassination_phase). The key stays
        # in the dict because later modifiers read `weights["steal"]`
        # unconditionally; instead it's zeroed here and re-zeroed AFTER
        # the floor sweep at the end of this function.
        weights["steal"] = 0.0
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
            if t == "Protective":  a_base -= 0.10
        if rep_now < -5:   a_base += 0.10
        if rep_now < -15:  a_base += 0.15
        if rep_now > 10:   a_base -= 0.20
        if guard_count >= 2:
            a_base *= 0.5
        if guard_count >= 5:
            a_base *= 0.35
        if a_base > 0.22:
            weights["assault"] = a_base

        # ----- Murder ----- (very rare; needs an extreme profile)
        m_base = 0.0
        if "Deceitful" in traits and "Hot-headed" in traits:
            m_base = 0.018
        elif "Reckless" in traits and rep_now < -10:
            m_base = 0.010
        if rep_now < -20:
            m_base += 0.03
        if int(villager.get("huntWins", 0) or 0) >= 5:
            m_base += 0.012
        if "Empathic" in traits or "Loyal" in traits or "Wise" in traits or "Protective" in traits:
            m_base *= 0.2
        if guard_count >= 3:
            m_base *= 0.35
        m_base = min(0.06, max(0.0, m_base))
        if m_base > 0.05:
            weights["murder"] = m_base

    # ---- Patrol gating (Guard jobs) ---------------------------------------
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

        if cat == "COMBAT":
            weights["train"] += 0.5
            weights["hunt"] += 0.5
            weights["buy_gear"] += 0.3
        if cat == "CRAFT":
            weights["work"] += 0.6
            weights["buy_gear"] += 0.2
        if cat == "SOCIAL":
            weights["socialize"] += 0.6
            weights["hangout"] += 0.4
            weights["work"] += 0.2
        if cat == "SURVIVAL":
            weights["hunt"] += 0.5
            weights["rest"] -= 0.2
            weights["buy_food"] -= 0.1
        if cat == "KNOWLEDGE":
            weights["study"] += 0.7
            weights["work"] += 0.2
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
            if t == "Stoic":      weights["spar"] += 0.3
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

        for t in traits:
            if t in ("Wise", "Patient", "Generous", "Empathic"):
                weights["mentor"] += 0.4
            if t == "Strict":
                weights["mentor"] += 0.3
            if t == "Lazy":
                weights["mentor"] -= 0.3

        for skill_name in skills:
            info = get_skill_info(skill_name)
            if info and info.get("category") in ("SOCIAL", "KNOWLEDGE"):
                weights["mentor"] += 0.3

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
    # even when hungry — their work is what stocks the village.
    from config import JOB_RESOURCE_YIELD
    is_producer = villager.get("job", "") in JOB_RESOURCE_YIELD

    if hunger >= 70 and coins >= 10 and not is_producer:
        return "buy_food"

    if is_producer:
        weights["work"] += 0.8

        # Stockpile-pressure scaling.
        if bank is not None:
            try:
                stock = bank.get("resources") or {}
                food_stock = int(stock.get("food", 0) or 0)
                if food_stock < 1000:
                    weights["work"] += 1.5
                    weights["socialize"] *= 0.4
                    weights["hangout"] *= 0.4
                    weights["visit_tavern"] *= 0.3
                    weights["study"] *= 0.6
                elif food_stock < 1500:
                    weights["work"] += 0.6
                    weights["hangout"] *= 0.7
            except Exception:
                pass

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

    # Forge artifact: heavily gated.
    try:
        from src.services.artifact_service import can_forge
        eligible, _reason = can_forge(villager, bank, current_day=None)
        if eligible:
            v_int = int(villager.get("int", 0) or 0)
            base = 0.30
            if v_int >= 70:
                base += 0.20
            if job == "Blacksmith":
                base += 0.08 * (get_building_level(bank, "blacksmith") if bank else 0)
            if job in ("Wizard", "Sorcerer"):
                base += 0.08 * (get_building_level(bank, "library") if bank else 0)
            weights["forge_artifact"] = base
    except Exception:
        pass

    # Clip negative weights (from heavy stacked penalties) to 0, and give
    # tiny positives a 0.05 floor so unusual actions stay possible. Explicit
    # zeros are preserved so gated-out actions (drill without Barracks,
    # spar for children, visit_tavern when broke, etc.) stay disabled — the
    # previous unconditional `< 0.05 → 0.05` quietly re-enabled all of them.
    for k in list(weights.keys()):
        w = weights[k]
        if w < 0:
            weights[k] = 0.0
        elif 0 < w < 0.05:
            weights[k] = 0.05

    # Royal theft exclusion — kept as defense-in-depth even though the
    # floor sweep above now preserves the explicit 0.0 above.
    if job in ("King", "Queen"):
        weights["steal"] = 0.0

    actions = list(weights.keys())
    probs = [weights[a] for a in actions]
    total = sum(probs)
    if total <= 0:
        return "rest"
    probs = [p / total for p in probs]

    return random.choices(actions, probs, k=1)[0]
