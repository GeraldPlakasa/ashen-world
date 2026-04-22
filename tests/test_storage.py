"""
Integration tests for storage.py - database persistence.
Tests save/load roundtrip for villagers, bank, and day.
"""
import pytest
import json

from src.repositories.base import init_db
from src.repositories.villager_repo import (
    save_villagers,
    load_villagers,
    graveyard_upsert_from_villager,
    graveyard_get,
)
from src.repositories.bank_repo import save_bank, load_bank
from src.repositories.world_repo import save_day, load_day, compute_year_and_day


class TestVillagerPersistence:
    """Tests for villager save/load roundtrip."""

    @pytest.mark.integration
    def test_save_load_single_villager(self, test_db_connection, sample_villager):
        """Single villager should roundtrip correctly."""
        save_villagers([sample_villager])

        loaded = load_villagers()

        assert len(loaded) == 1
        assert loaded[0]["id"] == sample_villager["id"]
        assert loaded[0]["name"] == sample_villager["name"]
        assert loaded[0]["job"] == sample_villager["job"]

    @pytest.mark.integration
    def test_save_load_multiple_villagers(self, test_db_connection, multiple_villagers):
        """Multiple villagers should roundtrip correctly."""
        save_villagers(multiple_villagers)

        loaded = load_villagers()

        assert len(loaded) == len(multiple_villagers)

        # Verify all IDs preserved
        original_ids = {v["id"] for v in multiple_villagers}
        loaded_ids = {v["id"] for v in loaded}
        assert original_ids == loaded_ids

    @pytest.mark.integration
    def test_relationships_preserved_as_dict(self, test_db_connection, sample_villager):
        """Relationships dict should be preserved."""
        sample_villager["relationships"] = {"42": 75, "99": -30}

        save_villagers([sample_villager])
        loaded = load_villagers()

        assert loaded[0]["relationships"] == {"42": 75, "99": -30}

    @pytest.mark.integration
    def test_children_ids_preserved_as_list(self, test_db_connection, sample_villager):
        """childrenIds list should be preserved."""
        sample_villager["childrenIds"] = [10, 11, 12]

        save_villagers([sample_villager])
        loaded = load_villagers()

        assert loaded[0]["childrenIds"] == [10, 11, 12]

    @pytest.mark.integration
    def test_alive_boolean_preserved(self, test_db_connection, sample_villager, dead_villager):
        """alive boolean should be preserved."""
        save_villagers([sample_villager, dead_villager])
        loaded = load_villagers()

        alive_villager = next(v for v in loaded if v["id"] == sample_villager["id"])
        dead_loaded = next(v for v in loaded if v["id"] == dead_villager["id"])

        assert alive_villager["alive"] is True
        assert dead_loaded["alive"] is False

    @pytest.mark.integration
    def test_integer_fields_converted(self, test_db_connection, sample_villager):
        """Integer fields should be loaded as int."""
        save_villagers([sample_villager])
        loaded = load_villagers()

        v = loaded[0]
        assert isinstance(v["id"], int)
        assert isinstance(v["age"], int)
        assert isinstance(v["coins"], int)
        assert isinstance(v["atk"], int)
        assert isinstance(v["def"], int)
        assert isinstance(v["hp"], int)

    @pytest.mark.integration
    def test_empty_relationships_handled(self, test_db_connection, sample_villager):
        """Empty relationships should be loaded as empty dict."""
        sample_villager["relationships"] = {}

        save_villagers([sample_villager])
        loaded = load_villagers()

        assert loaded[0]["relationships"] == {}

    @pytest.mark.integration
    def test_empty_children_handled(self, test_db_connection, sample_villager):
        """Empty childrenIds should be loaded as empty list."""
        sample_villager["childrenIds"] = []

        save_villagers([sample_villager])
        loaded = load_villagers()

        assert loaded[0]["childrenIds"] == []

    @pytest.mark.integration
    def test_relationships_stored_as_json_column(self, test_db_connection, sample_villager):
        """Relationships should be stored as JSON in villagers table and roundtrip correctly."""
        sample_villager["relationships"] = {"2": 50, "3": -20}
        save_villagers([sample_villager])

        # Check load returns correct data
        loaded = load_villagers()
        assert loaded[0]["relationships"] == {"2": 50, "3": -20}

    @pytest.mark.integration
    def test_achievements_stored_as_json_column(self, test_db_connection, sample_villager):
        """Achievements should be stored as JSON in villagers table and roundtrip correctly."""
        sample_villager["achievements"] = '["centurion", "hunter"]'
        save_villagers([sample_villager])

        # Check load returns correct data
        loaded = load_villagers()
        loaded_achs = json.loads(loaded[0]["achievements"])
        assert set(loaded_achs) == {"centurion", "hunter"}

    @pytest.mark.integration
    def test_votes_stored_as_json_column(self, test_db_connection, sample_villager):
        """kingsVotedFor should be stored as JSON in villagers table and roundtrip correctly."""
        sample_villager["kingsVotedFor"] = '[10, 20]'
        save_villagers([sample_villager])

        # Check load returns correct data
        loaded = load_villagers()
        loaded_votes = json.loads(loaded[0]["kingsVotedFor"])
        assert set(loaded_votes) == {10, 20}


class TestBankPersistence:
    """Tests for bank save/load roundtrip."""

    @pytest.mark.integration
    def test_save_load_basic_bank(self, test_db_connection, sample_bank):
        """Basic bank state should roundtrip correctly."""
        save_bank(sample_bank)

        loaded = load_bank()

        assert loaded["tax_rate"] == sample_bank["tax_rate"]
        assert loaded["balance"] == sample_bank["balance"]

    @pytest.mark.integration
    def test_building_levels_preserved(self, test_db_connection, sample_bank_with_buildings):
        """Building levels dict should be preserved."""
        save_bank(sample_bank_with_buildings)

        loaded = load_bank()

        assert loaded["building_levels"]["market"] == 2
        assert loaded["building_levels"]["barracks"] == 1
        assert loaded["building_levels"]["granary"] == 1

    @pytest.mark.integration
    def test_building_health_preserved(self, test_db_connection, sample_bank_with_buildings):
        """Building health dict should be preserved."""
        save_bank(sample_bank_with_buildings)

        loaded = load_bank()

        assert loaded["building_health"]["market"] == 100
        assert loaded["building_health"]["barracks"] == 75
        assert loaded["building_health"]["granary"] == 50

    @pytest.mark.integration
    def test_tax_rate_clamped(self, test_db_connection, sample_bank):
        """Tax rate should be clamped on load."""
        sample_bank["tax_rate"] = 0.50  # Above max

        save_bank(sample_bank)
        loaded = load_bank()

        assert loaded["tax_rate"] <= 0.35

    @pytest.mark.integration
    def test_election_info_preserved(self, test_db_connection, sample_bank):
        """Election info should be preserved."""
        sample_bank["last_election_year"] = 5
        sample_bank["last_election_message"] = "Test King elected"

        save_bank(sample_bank)
        loaded = load_bank()

        assert loaded["last_election_year"] == 5
        assert loaded["last_election_message"] == "Test King elected"


class TestDayPersistence:
    """Tests for day save/load roundtrip."""

    @pytest.mark.integration
    def test_save_load_day(self, test_db_connection):
        """Day number should roundtrip correctly."""
        save_day(100)

        loaded = load_day()

        assert loaded == 100

    @pytest.mark.integration
    def test_day_minimum_one(self, test_db_connection):
        """Day should be at least 1."""
        save_day(0)

        loaded = load_day()

        assert loaded >= 1

    @pytest.mark.integration
    def test_day_increment(self, test_db_connection):
        """Day should increment correctly."""
        save_day(50)
        day1 = load_day()

        save_day(day1 + 1)
        day2 = load_day()

        assert day2 == day1 + 1


class TestComputeYearAndDay:
    """Tests for year/day calculation."""

    @pytest.mark.unit
    def test_day_1_is_year_1_day_0(self):
        """Day 1 should be Year 1, Day 0."""
        year, day = compute_year_and_day(1)
        assert year == 1
        assert day == 0

    @pytest.mark.unit
    def test_day_90_is_year_1_day_89(self):
        """Day 90 should be Year 1, Day 89 (last day of year 1)."""
        # DAYS_PER_YEAR = 90
        year, day = compute_year_and_day(90)
        assert year == 1
        assert day == 89

    @pytest.mark.unit
    def test_day_91_is_year_2_day_0(self):
        """Day 91 should be Year 2, Day 0 (first day of year 2)."""
        year, day = compute_year_and_day(91)
        assert year == 2
        assert day == 0

    @pytest.mark.unit
    def test_day_180_is_year_2_day_89(self):
        """Day 180 should be Year 2, Day 89."""
        year, day = compute_year_and_day(180)
        assert year == 2
        assert day == 89

    @pytest.mark.unit
    def test_year_rollover_correct(self):
        """Year should rollover every 90 days."""
        # Year 1: days 1-90
        # Year 2: days 91-180
        # Year 3: days 181-270
        year, day = compute_year_and_day(181)
        assert year == 3
        assert day == 0

    @pytest.mark.unit
    def test_invalid_day_treated_as_one(self):
        """Day 0 or negative should be treated as day 1."""
        year, day = compute_year_and_day(0)
        assert year == 1
        assert day == 0

        year, day = compute_year_and_day(-10)
        assert year == 1
        assert day == 0


class TestGraveyard:
    """Tests for graveyard persistence."""

    @pytest.mark.integration
    def test_upsert_and_get(self, test_db_connection, dead_villager):
        """Villager should be saved to and retrieved from graveyard."""
        graveyard_upsert_from_villager(dead_villager)

        retrieved = graveyard_get(dead_villager["id"])

        assert retrieved is not None
        assert retrieved["id"] == dead_villager["id"]
        assert retrieved["name"] == dead_villager["name"]
        assert retrieved["family"] == dead_villager["family"]

    @pytest.mark.integration
    def test_graveyard_preserves_family_links(self, test_db_connection, sample_villager):
        """Graveyard should preserve family links."""
        sample_villager["motherId"] = 10
        sample_villager["fatherId"] = 11
        sample_villager["childrenIds"] = [20, 21, 22]

        graveyard_upsert_from_villager(sample_villager)
        retrieved = graveyard_get(sample_villager["id"])

        assert retrieved["motherId"] == 10
        assert retrieved["fatherId"] == 11
        assert retrieved["childrenIds"] == [20, 21, 22]

    @pytest.mark.integration
    def test_graveyard_upsert_updates(self, test_db_connection, sample_villager):
        """Upsert should update existing record."""
        graveyard_upsert_from_villager(sample_villager)

        # Update and upsert again
        sample_villager["name"] = "Updated Name"
        graveyard_upsert_from_villager(sample_villager)

        retrieved = graveyard_get(sample_villager["id"])
        assert retrieved["name"] == "Updated Name"

    @pytest.mark.integration
    def test_graveyard_get_missing(self, test_db_connection):
        """Getting missing ID should return None."""
        retrieved = graveyard_get(99999)
        assert retrieved is None


class TestInitDb:
    """Tests for database initialization."""

    @pytest.mark.integration
    def test_init_db_creates_tables(self, test_db_connection):
        """init_db should create all required tables."""
        # The test_db_connection fixture already calls init_db
        # Verify we can load from all major tables without error

        villagers = load_villagers()
        assert isinstance(villagers, list)

        bank = load_bank()
        assert isinstance(bank, dict)

        day = load_day()
        assert isinstance(day, int)

    @pytest.mark.integration
    def test_init_db_idempotent(self, test_db_connection):
        """init_db should be safe to call multiple times."""
        # Call init_db multiple times
        init_db()
        init_db()
        init_db()

        # Should still work
        day = load_day()
        assert isinstance(day, int)

    @pytest.mark.integration
    def test_default_values_set(self, test_db_connection):
        """Default values should be set on fresh database."""
        day = load_day()
        assert day >= 1

        bank = load_bank()
        assert bank["tax_rate"] == 0.10
        assert bank["balance"] == 0
