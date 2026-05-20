from __future__ import annotations

import math

from config import (
    BUILDINGS,
    MAX_BUILDING_LEVEL,
    REPAIR_THRESHOLD,
)
from src.utils.world_utils import (
    rand_int,
    pick_weighted,
)
from src.models.villager import Villager
from src.models.bank import Bank
from src.models.building import Building

def update_tax_policy(characters: list[Villager], bank: Bank, log_it: bool = False) -> Bank:
    """
    Set bank['tax_rate'] based on the King's traits, mirroring the JS logic.
    If no King exists, fall back to base 10%.
    """
    base_rate = 0.10
    rate = base_rate

    king = next(
        (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
        None,
    )

    if king:
        traits = [
            t.strip() for t in king.get("traits", "").split(",") if t.strip()
        ]

        if "Greedy" in traits:
            rate += 0.08
        if "Generous" in traits:
            rate -= 0.04
        if "Wise" in traits:
            rate -= 0.02
        if "Cautious" in traits:
            rate += 0.02
        if "Ambitious" in traits:
            rate += 0.03
        if "Hot-headed" in traits:
            rate += 0.01
        if "Loyal" in traits:
            rate -= 0.02

    levels = bank.get("building_levels") or {}
    lvl_tax_office = int(levels.get("tax_office", 0) or 0)
    lvl_treasury   = int(levels.get("treasury", 0) or 0)

    if lvl_tax_office > 0:
        rate += 0.01 * lvl_tax_office

    if lvl_treasury > 0:
        rate += 0.005 * lvl_treasury

    rate = max(0.0, min(0.35, rate))
    bank["tax_rate"] = rate

    return bank


def apply_tax_on_income(v: Villager, gross: int, bank: Bank) -> dict[str, int]:
    """
    Apply tax on a villager's income and send it to the village bank.
    """
    if gross <= 0:
        return {"net": gross, "tax": 0}

    rate = float(bank.get("tax_rate", 0.0))
    if rate <= 0:
        return {"net": gross, "tax": 0}

    tax = max(0, math.floor(gross * rate))
    net = gross - tax
    if net < 0:
        net = 0

    bank["balance"] = bank.get("balance", 0) + tax
    return {"net": net, "tax": tax}

def get_building_level(bank: Bank | None, key: str) -> int:
    """
    Convenience helper to read a building's level from the village bank.
    Returns 0 if bank / key is missing.
    """
    if bank is None:
        return 0
    levels = bank.get("building_levels") or {}
    try:
        return int(levels.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0

def _ensure_building_dicts(bank: Bank) -> tuple[dict[str, int], dict[str, int]]:
    """
    Make sure bank has mutable 'building_levels' and 'building_health' dicts.
    Returns (building_levels, building_health).
    """
    levels = bank.get("building_levels")
    if not isinstance(levels, dict):
        levels = {}
        bank["building_levels"] = levels

    health = bank.get("building_health")
    if not isinstance(health, dict):
        health = {}
        bank["building_health"] = health

    return levels, health


def has_building(key: str, bank: Bank) -> bool:
    """
    Return True if this building exists and is not collapsed.
    """
    levels, health = _ensure_building_dicts(bank)
    lvl = int(levels.get(key, 0) or 0)
    h = int(health.get(key, 100 if lvl > 0 else 0))
    if key not in health and lvl > 0:
        health[key] = 100
    return lvl >= 1 and h > 0


def building_priority_weights(king: Villager | None) -> dict[str, float]:
    """
    Priority weights for each building, based on the King's traits.
    """
    # base weight 1 for each building
    w = {b["key"]: 1.0 for b in BUILDINGS}
    # optional 'housing' for future use
    w["housing"] = 1.0

    if not king:
        return w

    traits_str = king.get("traits", "") or ""
    t = [s.strip() for s in traits_str.split(",") if s.strip()]

    if "Greedy" in t:
        w["treasury"] = w.get("treasury", 1.0) + 3
        w["market"] = w.get("market", 1.0) + 2
        w["blacksmith"] = w.get("blacksmith", 1.0) + 1
        w["tavern"] = w.get("tavern", 1.0) + 1
        w["mine"] = w.get("mine", 1.0) + 2          # iron → coin
        w["smelter"] = w.get("smelter", 1.0) + 1

    if "Generous" in t:
        w["clinic"] = w.get("clinic", 1.0) + 2
        w["granary"] = w.get("granary", 1.0) + 2
        w["temple"] = w.get("temple", 1.0) + 1
        w["housing"] = w.get("housing", 1.0) + 1
        w["farm"] = w.get("farm", 1.0) + 2          # feed the people
        w["midwife"] = w.get("midwife", 1.0) + 2    # care for mothers/newborns

    if "Wise" in t:
        w["library"] = w.get("library", 1.0) + 2
        w["temple"] = w.get("temple", 1.0) + 1
        w["tax_office"] = w.get("tax_office", 1.0) + 1
        w["farm"] = w.get("farm", 1.0) + 1          # plan for famine
        w["midwife"] = w.get("midwife", 1.0) + 1    # long-horizon population

    if "Cautious" in t:
        w["walls"] = w.get("walls", 1.0) + 2
        w["clinic"] = w.get("clinic", 1.0) + 1
        w["tax_office"] = w.get("tax_office", 1.0) + 2
        w["housing"] = w.get("housing", 1.0) + 0.5
        w["granary"] = w.get("granary", 1.0) + 1
        w["farm"] = w.get("farm", 1.0) + 1

    if "Brave" in t or "Hot-headed" in t:
        w["barracks"] = w.get("barracks", 1.0) + 2
        w["walls"] = w.get("walls", 1.0) + 1
        if "Hot-headed" in t:
            w["tavern"] = w.get("tavern", 1.0) + 2
        w["smelter"] = w.get("smelter", 1.0) + 1    # iron for weapons

    if "Ambitious" in t:
        w["royal_court"] = w.get("royal_court", 1.0) + 3
        w["treasury"] = w.get("treasury", 1.0) + 1
        w["market"] = w.get("market", 1.0) + 1
        w["temple"] = w.get("temple", 1.0) + 1
        w["housing"] = w.get("housing", 1.0) + 1
        w["mine"] = w.get("mine", 1.0) + 1
        w["quarry"] = w.get("quarry", 1.0) + 1

    if "Diligent" in t:
        w["farm"] = w.get("farm", 1.0) + 2
        w["lumbermill"] = w.get("lumbermill", 1.0) + 2
        w["quarry"] = w.get("quarry", 1.0) + 1
        w["mine"] = w.get("mine", 1.0) + 1

    if "Loyal" in t:
        w["temple"] = w.get("temple", 1.0) + 1
        w["walls"] = w.get("walls", 1.0) + 1
        w["farm"] = w.get("farm", 1.0) + 1

    if "Protective" in t:
        w["walls"] = w.get("walls", 1.0) + 1
        w["smelter"] = w.get("smelter", 1.0) + 1    # iron → weapons/armor

    return w


def _find_building(key: str) -> Building | None:
    return next((b for b in BUILDINGS if b["key"] == key), None)


def _bank_resources(bank: Bank) -> dict[str, int]:
    """Get (and initialize) the shared resource stockpile."""
    stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
    if not isinstance(stock, dict):
        stock = {"food": 0, "wood": 0, "stone": 0, "iron": 0}
        bank["resources"] = stock
    return stock


def construction_resource_cost(key: str, level: int = 1) -> dict[str, int]:
    """Resource bundle required to build (level=1) or upgrade to a given level.
    Upgrades scale the base bundle linearly with level (Lv2 = 2x, Lv3 = 3x).
    """
    base = _find_building(key)
    if not base:
        return {}
    bundle = base.get("resources") or {}
    if level <= 1:
        return dict(bundle)
    return {r: math.ceil(n * level) for r, n in bundle.items()}


def has_resources_for(bank: Bank, bundle: dict[str, int]) -> bool:
    if not bundle:
        return True
    stock = _bank_resources(bank)
    return all(int(stock.get(r, 0) or 0) >= n for r, n in bundle.items())


def spend_resources(bank: Bank, bundle: dict[str, int]) -> None:
    if not bundle:
        return
    stock = _bank_resources(bank)
    for r, n in bundle.items():
        stock[r] = int(stock.get(r, 0) or 0) - int(n)


def choose_building_to_construct(characters: list[Villager], bank: Bank) -> Building | None:
    """
    Pick ONE building to construct this day, if any.
    """
    king = next(
        (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
        None,
    )
    if not king:
        return None

    w = building_priority_weights(king)
    balance = int(bank.get("balance", 0))

    candidates = [
        b
        for b in BUILDINGS
        if not has_building(b["key"], bank)
        and balance >= b["cost"]
        and has_resources_for(bank, b.get("resources") or {})
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda b: w.get(b["key"], 0.0), reverse=True)
    weights = {b["key"]: w.get(b["key"], 1.0) for b in candidates}
    picked_key = pick_weighted(weights)
    choice = next(b for b in candidates if b["key"] == picked_key)
    return choice


def maybe_construct_building(
    characters: list[Villager],
    bank: Bank,
    current_day: int | None = None,
) -> tuple[Bank, str | None]:
    """
    Spend village bank coins (if possible) to construct one building
    chosen by the King's priorities.
    """
    choice = choose_building_to_construct(characters, bank)
    if not choice:
        return bank, None

    cost = int(choice["cost"])
    balance = int(bank.get("balance", 0))
    if balance < cost:
        return bank, None

    bundle = choice.get("resources") or {}
    if not has_resources_for(bank, bundle):
        return bank, None

    bank["balance"] = balance - cost
    spend_resources(bank, bundle)
    levels, health = _ensure_building_dicts(bank)

    key = choice["key"]
    levels[key] = 1
    health[key] = 100

    if bundle:
        parts = ", ".join(f"{n} {r}" for r, n in bundle.items())
        event_text = f"Village built {choice['name']} for {cost} coins and {parts}."
    else:
        event_text = f"Village built {choice['name']} for {cost} coins."

    # Chronicle the build, attributed to the sitting king (best-effort)
    try:
        from src.services.chronicle_service import record_construction
        king = next(
            (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
            None,
        )
        record_construction(king, choice["name"], 1, cost, int(current_day or 0))
    except Exception:
        pass

    return bank, event_text


def upgrade_cost(key: str, bank: Bank) -> int:
    """
    Cost to upgrade a building from its current level to the next level.
    Lv2 = 1.75x base, Lv3 = 2.5x base, etc.
    """
    base = _find_building(key)
    if not base:
        return -1  # <- sentinel for "invalid"

    levels, _ = _ensure_building_dicts(bank)
    lvl = int(levels.get(key, 1) or 1)
    next_lvl = lvl + 1
    mult = 1 + (next_lvl - 1) * 1
    return math.ceil(base["cost"] * mult)


def can_upgrade_building(key: str, bank: Bank) -> bool:
    """Return True if the building exists, is below max level, and the village can afford it (coin + resources)."""
    if not has_building(key, bank):
        return False
    if not _find_building(key):
        return False

    levels, _ = _ensure_building_dicts(bank)
    lvl = int(levels.get(key, 1) or 1)
    if lvl >= MAX_BUILDING_LEVEL:
        return False

    cost = upgrade_cost(key, bank)
    if cost <= 0:
        return False

    if int(bank.get("balance", 0)) < cost:
        return False

    bundle = construction_resource_cost(key, lvl + 1)
    return has_resources_for(bank, bundle)


def choose_building_to_upgrade(characters: list[Villager], bank: Bank) -> str | None:
    """
    Among existing buildings, choose one to upgrade based on King priorities.
    """
    king = next(
        (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
        None,
    )
    if not king:
        return None

    w = building_priority_weights(king)
    levels, _ = _ensure_building_dicts(bank)
    balance = int(bank.get("balance", 0))

    candidates = []
    for key, lvl in levels.items():
        if lvl is None:
            continue
        lvl = int(lvl)
        if lvl < 1 or lvl >= MAX_BUILDING_LEVEL:
            continue
        if not has_building(key, bank):
            continue
        cost = upgrade_cost(key, bank)
        if balance < cost:
            continue
        bundle = construction_resource_cost(key, lvl + 1)
        if not has_resources_for(bank, bundle):
            continue
        candidates.append(key)

    if not candidates:
        return None

    candidates.sort(key=lambda k: w.get(k, 0.0), reverse=True)
    return candidates[0]


def upgrade_building(
    key: str,
    bank: Bank,
    current_day: int | None = None,
) -> tuple[Bank, str | None]:
    """
    Perform the actual upgrade of a building, if affordable.
    """
    if not can_upgrade_building(key, bank):
        return bank, None
    if not _find_building(key):
        return bank, None

    cost = upgrade_cost(key, bank)
    balance = int(bank.get("balance", 0))
    if balance < cost:
        return bank, None

    levels, _ = _ensure_building_dicts(bank)
    next_lvl = int(levels.get(key, 1) or 1) + 1
    bundle = construction_resource_cost(key, next_lvl)
    if not has_resources_for(bank, bundle):
        return bank, None

    bank["balance"] = balance - cost
    spend_resources(bank, bundle)

    levels[key] = next_lvl

    base = _find_building(key)
    name = base["name"] if base else key
    if bundle:
        parts = ", ".join(f"{n} {r}" for r, n in bundle.items())
        event_text = f"{name} upgraded to Lv.{next_lvl} (-{cost} coins, {parts})."
    else:
        event_text = f"{name} upgraded to Lv.{next_lvl} (-{cost} coins)."
    return bank, event_text


def maybe_upgrade_building(
    characters: list[Villager],
    bank: Bank,
    current_day: int | None = None,
) -> tuple[Bank, str | None]:
    """
    Select a building to upgrade (if any) and upgrade it.
    """
    key = choose_building_to_upgrade(characters, bank)
    if not key:
        return bank, None

    # Snapshot the cost before the upgrade mutates state; needed for the
    # chronicle line.
    cost_for_chronicle = upgrade_cost(key, bank)

    bank, event_text = upgrade_building(key, bank, current_day)
    if event_text:
        try:
            from src.services.chronicle_service import record_construction
            base = _find_building(key)
            name = base["name"] if base else key
            levels, _ = _ensure_building_dicts(bank)
            new_lvl = int(levels.get(key, 1) or 1)
            king = next(
                (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
                None,
            )
            record_construction(king, name, new_lvl, cost_for_chronicle, int(current_day or 0))
        except Exception:
            pass

    return bank, event_text


def decay_buildings(bank: Bank, current_day: int | None = None) -> tuple[Bank, list[str]]:
    """
    Daily decay of building health. Buildings can collapse if health hits 0.
    """
    levels, health = _ensure_building_dicts(bank)
    events: list[str] = []

    if not levels:
        return bank, events

    for key, lvl in list(levels.items()):
        if int(lvl or 0) < 1:
            continue
        if not has_building(key, bank):
            continue

        cur = int(health.get(key, 100))
        # slower decay; higher level decays slightly slower
        drop = rand_int(1, 25)

        next_hp = max(0, cur - drop)
        if cur > 0 and next_hp == 0:
            health[key] = 0
            levels[key] = 0  # destroyed -> treat as not built
            base = _find_building(key)
            name = base["name"] if base else key
            events.append(f"{name} collapsed and must be rebuilt from Level 1.")
        else:
            health[key] = next_hp

    bank["building_levels"] = levels
    bank["building_health"] = health
    return bank, events


def repair_cost_for(key: str, bank: Bank) -> int:
    """
    Cost to repair a building from its current health up to 100%.
    """
    base = _find_building(key)
    if not base:
        return 0

    _, health = _ensure_building_dicts(bank)
    cur = int(health.get(key, 100))
    missing = max(0, 100 - cur)

    # same formula as JS: missing% * (base_cost * 0.25)
    cost = math.ceil(missing * (base["cost"] * 0.25) / 100)
    return cost


def choose_building_to_repair(characters: list[Villager], bank: Bank) -> tuple[str, int] | None:
    """
    Among damaged buildings, choose one to repair, considering King priorities
    and available coins.
    """
    levels, health = _ensure_building_dicts(bank)
    if not levels:
        return None

    # find damaged buildings below threshold but not collapsed
    damaged_keys = []
    for key, lvl in levels.items():
        lvl = int(lvl or 0)
        if lvl < 1:
            continue
        hp = int(health.get(key, 100))
        if 0 < hp < REPAIR_THRESHOLD:
            damaged_keys.append(key)

    if not damaged_keys:
        return None

    king = next(
        (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
        None,
    )
    w = building_priority_weights(king)

    # sort: higher weight first, then lower health first
    damaged_keys.sort(
        key=lambda k: (-w.get(k, 0.0), int(health.get(k, 100))),
    )

    balance = int(bank.get("balance", 0))
    for key in damaged_keys:
        cost = repair_cost_for(key, bank)
        if balance >= cost and cost > 0:
            return key, cost

    return None


def maybe_repair_buildings(
    characters: list[Villager],
    bank: Bank,
    current_day: int | None = None,
) -> tuple[Bank, str | None]:
    """
    If any important building is damaged and coins are sufficient,
    repair exactly one building (back to 100% health).
    """
    choice = choose_building_to_repair(characters, bank)
    if not choice:
        return bank, None

    key, cost = choice
    balance = int(bank.get("balance", 0))
    if balance < cost:
        return bank, None

    bank["balance"] = balance - cost
    _, health = _ensure_building_dicts(bank)

    base = _find_building(key)
    name = base["name"] if base else key

    health[key] = 100
    bank["building_health"] = health

    event_text = f"Repaired {name} for {cost} coins (health 100%)."
    return bank, event_text


def build_building_summary(bank: Bank, include_health: bool = False) -> list[dict]:
    """
    Build a sorted list of building summaries for UI display.

    If include_health is True, each entry includes 'health' and 'built' fields
    and is sorted by (not built, name). Otherwise entries include only key/name/level
    and are sorted by (level <= 0, name).
    """
    raw_levels = bank.get("building_levels") or {}
    raw_health = bank.get("building_health") or {}

    result = []
    for b in BUILDINGS:
        key = b["key"]
        name = b["name"]

        try:
            lvl = int(raw_levels.get(key, 0) or 0)
        except (TypeError, ValueError):
            lvl = 0

        entry: dict = {"key": key, "name": name, "level": lvl}

        if include_health:
            try:
                hp = int(raw_health.get(key, 0) or 0)
            except (TypeError, ValueError):
                hp = 0
            hp = max(0, min(100, hp))
            entry["health"] = hp
            entry["built"] = lvl > 0 and hp > 0

        result.append(entry)

    if include_health:
        result.sort(key=lambda x: (not x["built"], x["name"]))
    else:
        result.sort(key=lambda x: (x["level"] <= 0, x["name"]))

    return result
