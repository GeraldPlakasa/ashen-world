from __future__ import annotations

import math
import random

from config import (
    ENEMY_BASE,
    MAGIC_JOBS,
    MINOR_MAGIC_JOBS,
)
from src.utils.world_utils import (
    rand_int,
    pick_weighted,
    is_child,
)
from src.services.building_service import (
    get_building_level,
    apply_tax_on_income,
)
from src.models.villager import Villager
from src.models.bank import Bank
from src.models.combat import CombatResult, Enemy


def create_enemy_for(v: Villager) -> Enemy:
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


def apply_starvation_damage(v: Villager, bank: Bank | None = None) -> int | None:
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

    # Starvation damage (increased for unlimited HP balance)
    hp_loss = rand_int(8, 25)

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


def resolve_combat(v: Villager, enemy: Enemy, bank: Bank | None = None, weather: str | None = None) -> CombatResult:
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
    # Phase 3: equipped magical artifacts contribute to power computation.
    # effective_stats() is a read-only snapshot — base stats are not mutated.
    from src.services.artifact_service import effective_stats, equip_mods
    es = effective_stats(v)
    mods = equip_mods(v)

    mp = es["mp"]
    job = v.get("job", "")

    char_power = (
        es["atk"] * 1.15
        + es["def"]
        + es["int"] * 0.6
        + v["level"] * 12
        + es["rep"] * 0.2
        + 20
    )
    # +HP mod from artifacts gives a small power kicker (mirrors enemy hp-power term).
    if mods.get("hp", 0):
        char_power += mods["hp"] * 0.15

    # Magic power: magic jobs channel MP into combat spells.
    # Effective MP (incl. tome/ring mods) drives the spell, but we spend
    # only from the base pool — the artifact's mod stays intact.
    base_mp = int(v.get("mp", 0) or 0)
    if job in MAGIC_JOBS and mp > 0:
        spell_power = mp * 0.8 + es["int"] * 0.4
        char_power += spell_power
        # Spend MP on casting (30-60% of current effective MP)
        mp_cost = max(1, int(mp * (0.3 + random.random() * 0.3)))
        v["mp"] = max(0, base_mp - mp_cost)
    elif job in MINOR_MAGIC_JOBS and mp > 0:
        spell_power = mp * 0.3 + es["int"] * 0.15
        char_power += spell_power
        mp_cost = max(1, int(mp * (0.15 + random.random() * 0.15)))
        v["mp"] = max(0, base_mp - mp_cost)

    if bank is not None:
        lvl_barracks = get_building_level(bank, "barracks")
        lvl_walls    = get_building_level(bank, "walls")

        power_mult = 1.0 + 0.06 * lvl_barracks + 0.04 * lvl_walls
        char_power *= power_mult

    # Trait bonuses for combat
    traits_str = v.get("traits", "") or ""
    traits = [t.strip() for t in traits_str.split(",") if t.strip()]
    for t in traits:
        if t == "Hunter":
            char_power *= 1.15  # +15% combat power
        if t == "Fearless":
            char_power *= 1.10  # +10% combat power
        if t == "Resilient":
            char_power *= 1.05  # +5% combat power
        if t == "Brave":
            char_power *= 1.08  # +8% combat power
        if t == "Cautious":
            char_power *= 0.95  # -5% combat power (defensive focus)
        if t == "Reckless":
            char_power *= 1.12  # +12% combat power (risky)
        if t == "Hot-headed":
            char_power *= 1.06  # +6% combat power

    # Skill bonuses for combat
    from src.services.skill_service import parse_skills, get_skill_info
    skills = parse_skills(v.get("skills", ""))
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        if cat == "COMBAT":
            char_power *= 1.12  # +12% per combat skill
        elif cat == "MAGIC":
            char_power *= 1.15  # +15% per magic skill (spells are powerful)
        elif cat == "SURVIVAL":
            char_power *= 1.05  # +5% survival helps in fights

    # Weather effect (rain makes fights riskier)
    w = (weather or "sunny").strip().lower()
    if w == "rain":
        char_power *= 0.93

    # Optional companions (not yet surfaced in UI)
    companion = v.get("_companion")
    if companion == "war_beast":
        char_power += 40 + v["level"] * 3
    elif companion == "clockwork_soldier":
        char_power += 55 + v["level"] * 2

    enemy_power = (enemy["atk"] * 1.0 + enemy["def"] + enemy["hp"] * 0.18) * 0.9

    # Win probability (logistic curve)
    raw_win_prob = 1.0 / (1.0 + math.exp(-(char_power - enemy_power) / 65.0))
    win_prob = min(0.98, max(0.02, raw_win_prob))  # clamp to 2-98%

    win = random.random() < win_prob

    # Use effective def so armor/shield artifacts mitigate damage.
    dmg_base = max(0, round(enemy["atk"] * 0.45 - es["def"] * 0.25))
    dmg_var = round(dmg_base * (0.8 + random.random() * 0.6))

    if bank is not None:
        lvl_clinic = get_building_level(bank, "clinic")
        if lvl_clinic > 0:
            dmg_var = max(0, int(round(dmg_var * (1 - 0.12 * lvl_clinic))))

    if w == "rain":
        dmg_var = int(round(dmg_var * 1.08))

    # Trait-based damage reduction
    for t in traits:
        if t == "Resilient":
            dmg_var = max(0, int(round(dmg_var * 0.85)))  # -15% damage taken
        if t == "Immortal":
            dmg_var = max(0, int(round(dmg_var * 0.80)))  # -20% damage taken
        if t == "Stoic":
            dmg_var = max(0, int(round(dmg_var * 0.92)))  # -8% damage taken
        if t == "Protective":
            dmg_var = max(0, int(round(dmg_var * 0.90)))  # -10% damage taken
    
    # Skill-based damage reduction
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        # Bulwark and Iron Constitution reduce damage
        if skill_name in ("Bulwark", "Iron Constitution"):
            dmg_var = max(0, int(round(dmg_var * 0.85)))  # -15% damage

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

        # Apply rewards first
        v["coins"] += coin_net
        v["rep"]   += rep_gain
        v["exp"]   += exp_gain

        # Scratch damage even on win. Halved from 0.20 -> 0.10 because at
        # high levels enemy atk mirrors the villager's own atk and dmg_var
        # grows in lockstep — the old multiplier turned routine wins into
        # "won but died from wounds". Also cap each scratch at 25% of
        # current HP so one fight never 0-shots a wounded winner.
        raw_scratch = round(dmg_var * 0.10)
        hp_cap = max(1, int(v["hp"] * 0.25))
        scratch = max(1, min(raw_scratch, hp_cap))
        v["hp"] = max(0, v["hp"] - scratch)

        died_after_win = (v["hp"] <= 0)
        if died_after_win:
            v["hp"] = 0
            v["alive"] = False
        else:
            # Check for Iron Will achievement (survived with low HP)
            from src.services.achievement_service import trigger_iron_will_check
            if v["hp"] < 80:
                trigger_iron_will_check(v)

        result.update(
            {
                "outcome": "DEAD" if died_after_win else "WIN",
                "hpLost": scratch,
                "coinGained": coin_net,
                "taxPaid": tax_paid,
                "victory": True,
                "diedAfterWin": died_after_win,
            }
        )
        return result

    # LOSS / DEAD path (increased for unlimited HP balance)
    heavy = max(2, round(dmg_var * (1.4 + random.random() * 0.8)))
    v["hp"] = max(0, v["hp"] - heavy)

    death_prob = 0.10
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
        # Check for Iron Will achievement (survived with low HP)
        from src.services.achievement_service import trigger_iron_will_check
        if v["hp"] < 80:
            trigger_iron_will_check(v)
        
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
