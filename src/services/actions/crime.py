"""Crime + patrol actions: steal, assault, murder, patrol.

Crime apply-handlers all share a witness pattern at the end: after the
deed is done, they call `justice_service.maybe_witness_and_record()` so
guards (and patrollers, prioritized in `simulate_one_day`) may register
a pending case on the bank. The trial phase later in the same tick
resolves whatever the king rules on.
"""
from __future__ import annotations

import random

from src.utils.world_utils import rand_int
from src.services.building_service import get_building_level
from src.services.relationship_service import adjust_relationship
from src.models.villager import Villager
from src.models.bank import Bank


def apply_steal(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    if not all_characters:
        gross = rand_int(5, 15)
        v["coins"] += gross
        v["exp"] += rand_int(1, 3)
        v["hunger"] += rand_int(5, 10)
        v["rep"] = v.get("rep", 0) - rand_int(1, 4)
        v["last_action"] = (
            f"steal (no target, did work instead, earned {gross} coins)"
        )
        return

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
        return

    target = random.choice(victims)
    max_steal = min(target.get("coins", 0), rand_int(5, 30))

    if max_steal <= 0:
        v["hunger"] += rand_int(2, 5)
        v["rep"] = v.get("rep", 0) - rand_int(2, 6)
        v["last_action"] = (
            f"steal (failed, no coins from {target['name']})"
        )
        return

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


def _violent_candidates(v: Villager, all_characters: list[Villager] | None) -> list[Villager]:
    """Shared adult-target filter for assault/murder."""
    if not all_characters:
        return []
    return [
        o for o in all_characters
        if o.get("id") != v.get("id")
        and o.get("alive", True)
        and int(o.get("age", 0) or 0) >= 12
        and o.get("job") != "Child"
    ]


def _pick_rival(v: Villager, candidates: list[Villager]) -> Villager:
    """Pick the lowest-relationship-score candidate; fall back to random."""
    try:
        from src.services.relationship_service import get_relationship_score
        def _score(o):
            return get_relationship_score(v, int(o.get("id", 0) or 0))
        return min(candidates, key=_score)
    except Exception:
        return random.choice(candidates)


def _report_crime(
    bank: Bank | None,
    criminal: Villager,
    victim: Villager,
    crime_type: str,
    characters: list[Villager] | None,
    current_day: int | None,
) -> None:
    try:
        from src.services.justice_service import maybe_witness_and_record
        maybe_witness_and_record(
            bank=bank,
            criminal=criminal,
            victim=victim,
            crime_type=crime_type,
            characters=characters,
            current_day=int(current_day or 0),
        )
    except Exception:
        pass


def _maybe_record_death(target: Villager, cause: str, day: int) -> None:
    try:
        from src.services.chronicle_service import record_death
        record_death(target, cause=cause, day=int(day or 0))
    except Exception:
        pass


def apply_assault(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    candidates = _violent_candidates(v, all_characters)
    if not candidates:
        v["last_action"] = "assault (no target found, brooded instead)"
        v["hunger"] += rand_int(2, 5)
        return

    target = _pick_rival(v, candidates)

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
        _maybe_record_death(target, f"assault by {v.get('name','?')}", int(current_day or 0))

    v["last_action"] = (
        f"assault {target['name']} (-{base_damage} HP, {delta} relation"
        + (", killed" if killed else "") + ")"
    )

    # If the assault was lethal, upgrade the witnessed crime to murder.
    crime_label = "murder" if killed else "assault"
    _report_crime(bank, v, target, crime_label, all_characters, current_day)


def apply_murder(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    candidates = _violent_candidates(v, all_characters)
    if not candidates:
        v["last_action"] = "murder (no target found, brooded instead)"
        v["hunger"] += rand_int(2, 5)
        return

    target = _pick_rival(v, candidates)

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
        _maybe_record_death(target, f"murdered by {v.get('name','?')}", int(current_day or 0))

    v["last_action"] = (
        f"murder attempt on {target['name']} (-{damage} HP"
        + (", killed" if killed else ", survived") + ")"
    )

    # Crime category is murder if lethal, assault if the victim survived.
    crime_label = "murder" if killed else "assault"
    _report_crime(bank, v, target, crime_label, all_characters, current_day)


def apply_patrol(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    """Guards on duty: light training + rep gain. Setting `last_action` to
    start with 'patrol' promotes them into the patroller bucket used by
    `justice_service._patrollers_today` later in the tick."""
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
