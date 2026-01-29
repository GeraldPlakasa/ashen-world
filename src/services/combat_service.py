import math
import random

from config import (
    ENEMY_BASE,
)
from world_utils import (
    rand_int,
    pick_weighted,
    is_child,
)
from buildings import (
    get_building_level,
    apply_tax_on_income,
)


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
    win_prob = min(0.98, max(0.02, raw_win_prob))  # clamp to 2-98%

    win = random.random() < win_prob

    # Base damage
    dmg_base = max(0, round(enemy["atk"] * 0.45 - v["def"] * 0.25))
    dmg_var = round(dmg_base * (0.8 + random.random() * 0.6))

    if bank is not None:
        lvl_clinic = get_building_level(bank, "clinic")
        if lvl_clinic > 0:
            dmg_var = max(0, int(round(dmg_var * (1 - 0.12 * lvl_clinic))))

    if w == "rain":
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

        # Apply rewards first
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
                "victory": True,
                "diedAfterWin": died_after_win,
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
