"""Integration tests for the seasons system.

Covers the lever surfaces — food consumption, farm yield, hunt yield, and the
festival event weighting — to make sure the seasonal modifiers actually move
the numbers in the simulation. Pure-function boundary checks live in
test_world_utils.py::TestSeasons.
"""
from __future__ import annotations

import pytest

from config import DAYS_PER_YEAR
from src.utils.world_utils import season_for_total_day


def _make_adult(idx: int) -> dict:
    return {
        "id": idx,
        "name": f"Villager {idx}",
        "family": "Test",
        "gender": "Male",
        "job": "Farmer",
        "alive": True,
        "age": 30,
        "hp": 100,
        "hunger": 0,
    }


def _make_bank(food: int = 10_000) -> dict:
    return {
        "tax_rate": 0.10,
        "balance": 0,
        "resources": {"food": food, "wood": 0, "stone": 0, "iron": 0},
        "building_levels": {},
        "building_health": {},
    }


def _day_of_season(season: str) -> int:
    """Return a total_day that lands in the middle of the given season (year 1).

    Boundary days (eg day_in_year=22 with quarter=22.5) can sit on the wrong
    side of a float division, so we deliberately pick a day well inside each
    quarter to keep these tests stable if DAYS_PER_YEAR ever changes a little.
    """
    quarter = DAYS_PER_YEAR / 4.0
    idx = {"spring": 0, "summer": 1, "autumn": 2, "winter": 3}[season]
    day_in_year = int((idx + 0.5) * quarter)
    return day_in_year + 1  # convert day_in_year (0-based) -> total_day (1-based)


class TestSeasonalFoodConsumption:
    """consume_food_phase should pull more food in winter than in summer."""

    @pytest.mark.unit
    def test_winter_needs_more_food_than_summer(self):
        from src.services.simulation_service import consume_food_phase

        villagers = [_make_adult(i) for i in range(40)]

        summer_bank = _make_bank(food=10_000)
        winter_bank = _make_bank(food=10_000)

        summer_summary = consume_food_phase(
            villagers, summer_bank, current_day=_day_of_season("summer")
        )
        winter_summary = consume_food_phase(
            villagers, winter_bank, current_day=_day_of_season("winter")
        )

        assert winter_summary["need"] > summer_summary["need"], (
            f"Winter need ({winter_summary['need']}) must exceed summer need "
            f"({summer_summary['need']})"
        )
        # The food stockpile after the draw should also be lower in winter
        # (more was eaten), so the stockpile/need relationship holds end-to-end.
        assert winter_bank["resources"]["food"] < summer_bank["resources"]["food"]


class TestSeasonalFarmYield:
    """A Farmer's work-action food output scales with the season."""

    @pytest.mark.unit
    def test_autumn_farm_yield_exceeds_winter(self):
        from src.services.action_service import apply_action

        def _produce(season: str) -> int:
            villager = {
                "id": 1, "name": "F", "family": "T", "gender": "Male",
                "job": "Farmer", "alive": True, "age": 30,
                "level": 1, "exp": 0, "coins": 0,
                "atk": 10, "def": 10, "int": 10, "hp": 100, "mp": 0,
                "hunger": 0, "traits": "", "skills": "",
                "last_action": "",
            }
            bank = _make_bank(food=0)
            apply_action(
                villager, "work", bank=bank, all_characters=[villager],
                weather="sunny", current_day=_day_of_season(season),
            )
            return int(bank["resources"]["food"])

        autumn = _produce("autumn")
        winter = _produce("winter")
        spring = _produce("spring")
        assert autumn > winter, f"autumn={autumn} winter={winter}"
        # Spring is slightly above baseline; winter is well below it.
        assert spring > winter


class TestSeasonalHuntYield:
    """The hunt action's meat drop scales with season multiplier."""

    @pytest.mark.unit
    def test_autumn_hunt_meat_exceeds_winter(self, monkeypatch):
        from src.services import action_service

        # Force a guaranteed kill so the meat-yield branch always runs.
        class _Enemy(dict):
            pass

        def fake_create_enemy_for(_v):
            return _Enemy({"name": "Wolf", "tier": "common", "hp": 1, "atk": 1, "def": 0})

        def fake_resolve_combat(_v, _e, _bank=None, weather=None):
            return {"outcome": "WIN", "victory": True, "taxPaid": 0}

        # Stub combat without breaking the surrounding imports.
        import src.services.combat_service as combat_service
        monkeypatch.setattr(combat_service, "create_enemy_for", fake_create_enemy_for)
        monkeypatch.setattr(combat_service, "resolve_combat", fake_resolve_combat)

        def _hunt(season: str) -> int:
            villager = {
                "id": 1, "name": "H", "family": "T", "gender": "Male",
                "job": "Hunter", "alive": True, "age": 30,
                "level": 1, "exp": 0, "coins": 0,
                "atk": 50, "def": 30, "int": 10, "hp": 100, "mp": 0,
                "hunger": 0, "traits": "", "skills": "",
                "last_action": "", "huntWins": 0, "huntWinsYear": 0,
                "equip_weapon": 0, "equip_armor": 0, "equip_ring": 0,
                "equip_amulet": 0, "equip_tome": 0,
            }
            bank = _make_bank(food=0)
            action_service.apply_action(
                villager, "hunt", bank=bank, all_characters=[villager],
                weather="sunny", current_day=_day_of_season(season),
            )
            return int(bank["resources"]["food"])

        autumn = _hunt("autumn")
        winter = _hunt("winter")
        assert autumn > winter, f"autumn hunt={autumn} winter hunt={winter}"


class TestSeasonalEventBias:
    """_pick_event_type should weight FESTIVAL more heavily in summer."""

    @pytest.mark.unit
    def test_summer_picks_festival_more_often_than_winter(self, seeded_random):
        from src.services.event_service import _pick_event_type

        def _count_festivals(season: str, trials: int = 2_000) -> int:
            seeded_random(98765)  # fix RNG per season for fair comparison
            day = _day_of_season(season)
            n = 0
            for _ in range(trials):
                if _pick_event_type(day) == "FESTIVAL":
                    n += 1
            return n

        summer = _count_festivals("summer")
        winter = _count_festivals("winter")
        # Summer's bonus is +15 on top of the base FESTIVAL weight; winter's
        # bonus is 0. The gap should be obvious across 2k trials. Some
        # randomness is unavoidable, so we leave a generous margin.
        assert summer > winter, f"summer={summer} winter={winter}"


class TestSeasonTransitionChronicleHook:
    """record_season_change should write to chronicle without raising."""

    @pytest.mark.integration
    def test_season_change_records_chronicle_entry(self, test_db_connection):
        from src.services.chronicle_service import record_season_change
        from src.repositories.chronicle_repo import list_events

        record_season_change("autumn", day=46)
        events = list_events(limit=10, offset=0, category="world")
        assert any("Autumn begins" in (e.get("headline") or "") for e in events)


class TestSeasonForTotalDay:
    """Quick sanity check covering the helper in a sim-loop-like context."""

    @pytest.mark.unit
    @pytest.mark.parametrize("total_day,expected", [
        (1, "spring"),
        (DAYS_PER_YEAR // 4 + 5, "summer"),
        (DAYS_PER_YEAR // 2 + 5, "autumn"),
        (DAYS_PER_YEAR - 3, "winter"),
        (DAYS_PER_YEAR + 1, "spring"),  # year 2, day 0
    ])
    def test_known_days(self, total_day, expected):
        assert season_for_total_day(total_day) == expected
