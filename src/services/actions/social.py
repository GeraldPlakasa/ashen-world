"""Social actions: socialize, hangout, visit_tavern, woo."""
from __future__ import annotations

import random

from src.utils.world_utils import rand_int
from src.services.building_service import get_building_level
from src.services.relationship_service import adjust_relationship, relationship_label
from src.services.skill_service import get_socialize_bonus
from src.models.villager import Villager
from src.models.bank import Bank


def apply_socialize(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    # Rain reduces social interaction quality
    w = (weather or "sunny").strip().lower()
    rain_penalty = 0.85 if w == "rain" else 1.0

    skill_bonus = get_socialize_bonus(v)

    if not all_characters:
        v["hunger"] -= rand_int(1, 4)
        v["hp"] += rand_int(0, 3)
        return

    candidates = [
        o for o in all_characters
        if o.get("id") != v.get("id") and o.get("alive", True)
    ]
    if not candidates:
        v["hunger"] -= rand_int(1, 4)
        v["hp"] += rand_int(0, 3)
        return

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


def apply_hangout(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    if not all_characters:
        v["hunger"] += rand_int(3, 7)
        v["hp"] += rand_int(2, 5)
        v["exp"] += rand_int(1, 3)
        return

    candidates = [
        o for o in all_characters
        if o.get("id") != v.get("id") and o.get("alive", True)
    ]
    if not candidates:
        v["hunger"] += rand_int(3, 7)
        v["hp"] += rand_int(2, 5)
        v["exp"] += rand_int(1, 3)
        return

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


def apply_visit_tavern(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    lvl_t = get_building_level(bank, "tavern") if bank is not None else 0
    coins_have = int(v.get("coins", 0) or 0)
    cost = rand_int(5, 10)

    if coins_have < cost or lvl_t <= 0:
        v["last_action"] = "visit tavern (couldn't afford it)"
        return

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
        return

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


def apply_woo(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    from src.services.relationship_service import get_relationship_score

    if not all_characters or int(v.get("spouseId", 0) or 0) != 0:
        v["hunger"] += rand_int(1, 3)
        v["last_action"] = "woo (no one available)"
        return

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
        return

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
