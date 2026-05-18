"""Economic actions: work, buy_food, buy_gear.

`work` is the load-bearing one — it produces both coin income (taxed) and
raw resource yields scaled by villager level, weather, season, and any
production-building bonuses. The Blacksmith iron-consumption sink lives
here too.
"""
from __future__ import annotations

from src.utils.world_utils import rand_int, season_for_total_day, season_modifier
from src.services.building_service import get_building_level, apply_tax_on_income
from src.services.skill_service import get_work_bonus
from src.services.actions.utility import create_shop_offer
from src.models.villager import Villager
from src.models.bank import Bank


def apply_work(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
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


def apply_buy_food(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
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


def apply_buy_gear(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
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
