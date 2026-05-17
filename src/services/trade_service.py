"""Foreign trade: the King may spend treasury coins to import resources
from outside the village when the local stockpile is low.

This is a king-driven decision, modulated by traits and the treasury level.
A Greedy king resists spending, a Generous king buys food readily, an
Ambitious king prefers materials for construction. There is always a hard
"emergency" rule that any king will buy food if the village is days from
mass starvation, regardless of personality.
"""
from __future__ import annotations

import random

from config import (
    TRADE_PRICES,
    TRADE_TREASURY_FLOOR,
    TRADE_ORDER_SIZE,
    TRADE_LOW_STOCK,
    TRADE_EMERGENCY_FOOD_STOCK,
    TRADE_EMERGENCY_FOOD_TARGET,
    TRADE_SELL_PRICES,
    TRADE_EXPORT_FLOOR,
    TRADE_EXPORT_SIZE,
)
from src.models.villager import Villager
from src.models.bank import Bank


def _trait_set(king: Villager) -> set[str]:
    raw = king.get("traits", "") or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


def _buy_chance_food(traits: set[str], days_supply: float) -> float:
    """Probability a king imports food today given the current days-of-supply.

    < 2 days: always buys (emergency rule, handled by caller).
    2-5 days: trait-modulated chance.
    > 5 days: very small chance (only for prep-minded kings).
    """
    if days_supply < 5:
        chance = 0.50
    else:
        chance = 0.05  # only highly cautious kings stockpile when comfortable

    if "Generous" in traits or "Empathic" in traits:
        chance += 0.35
    if "Cautious" in traits:
        chance += 0.25
    if "Wise" in traits:
        chance += 0.15
    if "Loyal" in traits:
        chance += 0.10
    if "Greedy" in traits:
        chance -= 0.35
    if "Reckless" in traits:
        chance -= 0.15
    return max(0.0, min(0.95, chance))


def _buy_chance_material(traits: set[str], resource: str) -> float:
    """Probability a king imports wood/stone/iron today when stock is low."""
    chance = 0.20
    if "Ambitious" in traits:
        chance += 0.30
    if "Diligent" in traits:
        chance += 0.20
    if "Protective" in traits and resource in ("stone", "iron"):
        chance += 0.15  # walls, weapons
    if "Wise" in traits:
        chance += 0.10
    if "Greedy" in traits:
        chance -= 0.25
    return max(0.0, min(0.85, chance))


def _purchase(bank: Bank, resource: str, units: int) -> int:
    """Subtract coins, add resources. Returns coins spent (0 if not affordable)."""
    price = TRADE_PRICES.get(resource, 0)
    if price <= 0 or units <= 0:
        return 0
    cost = price * units
    balance = int(bank.get("balance", 0) or 0)
    if balance - cost < TRADE_TREASURY_FLOOR:
        # Buy as much as the floor allows
        affordable = max(0, balance - TRADE_TREASURY_FLOOR) // price
        if affordable <= 0:
            return 0
        units = affordable
        cost = price * units
    bank["balance"] = balance - cost
    stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
    stock[resource] = int(stock.get(resource, 0) or 0) + units
    return cost


def maybe_king_imports_resources(
    characters: list[Villager],
    bank: Bank,
    current_day: int | None = None,
) -> str | None:
    """Once-per-day check: may the king import resources today?

    Returns a short summary string (for chronicle / event message) or None.
    """
    if not bank:
        return None

    king = next(
        (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
        None,
    )
    if not king:
        return None

    balance = int(bank.get("balance", 0) or 0)
    if balance <= TRADE_TREASURY_FLOOR:
        return None

    traits = _trait_set(king)
    stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})

    adults = sum(
        1 for c in characters
        if c.get("alive") and int(c.get("age", 0) or 0) >= 17
    )

    purchases: list[tuple[str, int, int]] = []  # (resource, units, cost)

    # ---- FOOD ---------------------------------------------------------------
    food = int(stock.get("food", 0) or 0)
    days_supply = (food / max(1, adults)) if adults > 0 else 999.0
    food_low_threshold = max(TRADE_LOW_STOCK["food"], adults * 5)

    # Emergency: any food stockpile below the absolute threshold (default 1000).
    # The king buys enough to refill toward TRADE_EMERGENCY_FOOD_TARGET (1500).
    food_emergency = food < TRADE_EMERGENCY_FOOD_STOCK
    if food_emergency or food < food_low_threshold:
        chance = 1.0 if food_emergency else _buy_chance_food(traits, days_supply)
        if random.random() < chance:
            if food_emergency:
                # Refill toward the target; one large order rather than spreading
                # across multiple days, so the village stops being in crisis.
                order = max(TRADE_ORDER_SIZE["food"], TRADE_EMERGENCY_FOOD_TARGET - food)
            else:
                order = TRADE_ORDER_SIZE["food"]
            spent = _purchase(bank, "food", order)
            if spent > 0:
                actual_units = spent // TRADE_PRICES["food"]
                purchases.append(("food", actual_units, spent))

    # ---- MATERIALS (wood / stone / iron) -----------------------------------
    for res in ("wood", "stone", "iron"):
        threshold = TRADE_LOW_STOCK[res]
        current = int(stock.get(res, 0) or 0)
        if current >= threshold:
            continue
        balance_now = int(bank.get("balance", 0) or 0)
        if balance_now <= TRADE_TREASURY_FLOOR:
            break
        if random.random() < _buy_chance_material(traits, res):
            spent = _purchase(bank, res, TRADE_ORDER_SIZE[res])
            if spent > 0:
                actual_units = spent // TRADE_PRICES[res]
                purchases.append((res, actual_units, spent))

    if not purchases:
        return None

    # Build a human message and chronicle it.
    parts = [f"+{u} {r} ({c}g)" for (r, u, c) in purchases]
    total_cost = sum(c for (_, _, c) in purchases)
    message = (
        f"King {king.get('name','')} imported resources from outside: "
        f"{', '.join(parts)}. Total cost: {total_cost}g."
    )

    try:
        from src.services.chronicle_service import record_trade_import
        record_trade_import(king, purchases, total_cost, day=int(current_day or 0))
    except Exception:
        pass

    return message


# ===========================================================================
#  EXPORT — King sells surplus stockpile back for coins
# ===========================================================================

def _sell_chance_food(traits: set[str]) -> float:
    """Probability the king sells surplus food today. Most traits are
    reluctant to sell food (it's the village's safety margin); only
    money-minded kings sell readily."""
    chance = 0.20
    if "Greedy" in traits:
        chance += 0.45
    if "Ambitious" in traits:
        chance += 0.20
    if "Deceitful" in traits:
        chance += 0.15
    if "Generous" in traits or "Empathic" in traits:
        chance -= 0.30  # cares for the people, hoards a reserve
    if "Cautious" in traits:
        chance -= 0.30  # hoards by nature
    if "Loyal" in traits:
        chance -= 0.15
    if "Wise" in traits:
        chance -= 0.05  # wise kings keep modest stockpile
    return max(0.0, min(0.85, chance))


def _sell_chance_material(traits: set[str], resource: str) -> float:
    """Probability the king sells surplus wood/stone/iron today."""
    chance = 0.25
    if "Greedy" in traits:
        chance += 0.40
    if "Ambitious" in traits:
        chance += 0.10  # ambitious kings prefer to keep materials for building
    if "Deceitful" in traits:
        chance += 0.15
    if "Diligent" in traits:
        chance -= 0.10  # builds with materials instead of selling
    if "Protective" in traits and resource in ("stone", "iron"):
        chance -= 0.20  # keeps walls/weapons material
    if "Cautious" in traits:
        chance -= 0.15
    return max(0.0, min(0.80, chance))


def _sell(bank: Bank, resource: str, units: int) -> int:
    """Subtract resources, add coins. Returns coins earned."""
    price = TRADE_SELL_PRICES.get(resource, 0)
    if price <= 0 or units <= 0:
        return 0
    stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
    have = int(stock.get(resource, 0) or 0)
    units = min(units, have)
    if units <= 0:
        return 0
    earned = price * units
    stock[resource] = have - units
    bank["balance"] = int(bank.get("balance", 0) or 0) + earned
    return earned


def maybe_king_exports_resources(
    characters: list[Villager],
    bank: Bank,
    current_day: int | None = None,
) -> str | None:
    """Once-per-day check: may the king sell surplus stockpile for coins?

    Only fires when a resource is comfortably above its export floor AND
    the king has a trait that encourages selling. Sell prices are below
    buy prices to discourage arbitrage with imports.
    """
    if not bank:
        return None

    king = next(
        (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
        None,
    )
    if not king:
        return None

    traits = _trait_set(king)
    stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})

    sales: list[tuple[str, int, int]] = []  # (resource, units, earned)

    # ---- FOOD ---------------------------------------------------------------
    food = int(stock.get("food", 0) or 0)
    food_floor = TRADE_EXPORT_FLOOR["food"]
    if food > food_floor:
        if random.random() < _sell_chance_food(traits):
            # Never sell into emergency territory — cap units at (food - floor).
            max_units = max(0, food - food_floor)
            units = min(TRADE_EXPORT_SIZE["food"], max_units)
            earned = _sell(bank, "food", units)
            if earned > 0:
                sales.append(("food", units, earned))

    # ---- MATERIALS ----------------------------------------------------------
    for res in ("wood", "stone", "iron"):
        current = int(stock.get(res, 0) or 0)
        floor = TRADE_EXPORT_FLOOR[res]
        if current <= floor:
            continue
        if random.random() < _sell_chance_material(traits, res):
            max_units = max(0, current - floor)
            units = min(TRADE_EXPORT_SIZE[res], max_units)
            earned = _sell(bank, res, units)
            if earned > 0:
                sales.append((res, units, earned))

    if not sales:
        return None

    parts = [f"-{u} {r} (+{e}g)" for (r, u, e) in sales]
    total_earned = sum(e for (_, _, e) in sales)
    message = (
        f"King {king.get('name','')} exported surplus to outside: "
        f"{', '.join(parts)}. Total earned: {total_earned}g."
    )

    try:
        from src.services.chronicle_service import record_trade_export
        record_trade_export(king, sales, total_earned, day=int(current_day or 0))
    except Exception:
        pass

    return message
