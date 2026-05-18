"""Magic-flavored actions: study and meditate."""
from __future__ import annotations

from config import MAGIC_JOBS, MINOR_MAGIC_JOBS
from src.utils.world_utils import rand_int
from src.services.building_service import get_building_level
from src.services.skill_service import get_study_bonus
from src.models.villager import Villager
from src.models.bank import Bank


def apply_study(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
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


def apply_meditate(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
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
