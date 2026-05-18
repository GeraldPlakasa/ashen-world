"""Welfare actions: rest."""
from __future__ import annotations

from config import MAGIC_JOBS, MINOR_MAGIC_JOBS
from src.utils.world_utils import rand_int
from src.services.building_service import get_building_level
from src.services.skill_service import get_rest_bonus
from src.models.villager import Villager
from src.models.bank import Bank


def apply_rest(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
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
