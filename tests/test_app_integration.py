"""
Integration tests for app.py - Flask routes and day advancement.
"""
import pytest
import json

import app as flask_app
from src.repositories.villager_repo import save_villagers, load_villagers
from src.repositories.bank_repo import save_bank, load_bank
from src.repositories.world_repo import save_day, load_day, compute_year_and_day


class TestAdvanceOneDay:
    """Tests for the advance_one_day() function."""

    @pytest.mark.integration
    def test_advance_increments_day(self, test_db_connection, multiple_villagers, sample_bank, seeded_random):
        """advance_one_day should increment the day counter."""
        seeded_random(42)

        # Setup initial state
        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(1)

        ok, msg, year, day_in_year, total_day = flask_app.advance_one_day()

        assert ok is True
        assert total_day == 2

    @pytest.mark.integration
    def test_advance_returns_correct_tuple(self, test_db_connection, multiple_villagers, sample_bank, seeded_random):
        """advance_one_day should return (ok, message, year, day_in_year, total_day)."""
        seeded_random(42)

        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(1)

        result = flask_app.advance_one_day()

        assert len(result) == 5
        ok, msg, year, day_in_year, total_day = result
        assert isinstance(ok, bool)
        assert isinstance(msg, str)
        assert isinstance(year, int)
        assert isinstance(day_in_year, int)
        assert isinstance(total_day, int)

    @pytest.mark.integration
    def test_advance_no_villagers_returns_false(self, test_db_connection, sample_bank):
        """advance_one_day with no villagers should return ok=False."""
        save_villagers([])
        save_bank(sample_bank)
        save_day(1)

        ok, msg, year, day_in_year, total_day = flask_app.advance_one_day()

        assert ok is False
        assert "No villagers" in msg

    @pytest.mark.integration
    def test_year_rollover_ages_villagers(self, test_db_connection, multiple_villagers, sample_bank, seeded_random):
        """Crossing year boundary should age villagers."""
        seeded_random(42)

        # Setup at day 90 (last day of year 1)
        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(90)

        # Get original ages
        original_ages = {v["id"]: v["age"] for v in multiple_villagers}

        # Advance to day 91 (first day of year 2)
        ok, msg, year, day_in_year, total_day = flask_app.advance_one_day()

        assert ok is True
        assert year == 2
        assert day_in_year == 0

        # Check villagers aged
        loaded = load_villagers()
        for v in loaded:
            if v.get("alive", True):
                original_age = original_ages.get(v["id"])
                if original_age is not None:
                    # Age should have increased by 1
                    assert v["age"] == original_age + 1

    @pytest.mark.integration
    def test_advance_persists_changes(self, test_db_connection, multiple_villagers, sample_bank, seeded_random):
        """advance_one_day should persist all changes to database."""
        seeded_random(42)

        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(1)

        flask_app.advance_one_day()

        # Verify changes were persisted
        loaded_day = load_day()
        assert loaded_day == 2

        loaded_villagers = load_villagers()
        assert len(loaded_villagers) > 0

        loaded_bank = load_bank()
        assert isinstance(loaded_bank, dict)


class TestApiState:
    """Tests for the /api/state endpoint."""

    @pytest.mark.integration
    def test_api_state_returns_json(self, flask_client, test_db_connection, multiple_villagers, sample_bank):
        """GET /api/state should return JSON."""
        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(1)

        response = flask_client.get("/api/state")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True

    @pytest.mark.integration
    def test_api_state_contains_world_info(self, flask_client, test_db_connection, multiple_villagers, sample_bank):
        """GET /api/state should contain year, day, and characters."""
        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(50)

        response = flask_client.get("/api/state")
        data = json.loads(response.data)

        assert "year" in data
        assert "day" in data
        assert "total_day" in data
        assert "characters" in data
        # total_day should be a positive integer (exact value may vary due to auto-sim)
        assert isinstance(data["total_day"], int)
        assert data["total_day"] >= 1

    @pytest.mark.integration
    def test_api_state_contains_bank_info(self, flask_client, test_db_connection, multiple_villagers, sample_bank):
        """GET /api/state should contain bank information."""
        save_villagers(multiple_villagers)
        sample_bank["balance"] = 5000
        sample_bank["tax_rate"] = 0.15
        save_bank(sample_bank)
        save_day(1)

        response = flask_client.get("/api/state")
        data = json.loads(response.data)

        assert "bank_balance" in data
        assert "tax_rate" in data
        assert data["bank_balance"] == 5000
        assert data["tax_rate"] == 0.15

    @pytest.mark.integration
    def test_api_state_contains_buildings(self, flask_client, test_db_connection, multiple_villagers, sample_bank_with_buildings):
        """GET /api/state should contain buildings information."""
        save_villagers(multiple_villagers)
        save_bank(sample_bank_with_buildings)
        save_day(1)

        response = flask_client.get("/api/state")
        data = json.loads(response.data)

        assert "buildings" in data
        assert isinstance(data["buildings"], list)
        assert len(data["buildings"]) > 0

        # Check building structure
        building = data["buildings"][0]
        assert "key" in building
        assert "name" in building
        assert "level" in building
        assert "health" in building


class TestLandingPage:
    """Tests for the landing page route."""

    @pytest.mark.integration
    def test_landing_returns_200(self, flask_client, test_db_connection, multiple_villagers, sample_bank):
        """GET / should return 200."""
        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(1)

        response = flask_client.get("/")

        assert response.status_code == 200

    @pytest.mark.integration
    def test_landing_contains_world_info(self, flask_client, test_db_connection, multiple_villagers, sample_bank):
        """Landing page should contain year/day information."""
        save_villagers(multiple_villagers)
        save_bank(sample_bank)
        save_day(1)

        response = flask_client.get("/")

        # Check that key info is in the response
        assert b"Year" in response.data or b"year" in response.data


class TestComputeYearChampions:
    """Tests for the compute_year_champions() function."""

    @pytest.mark.unit
    def test_computes_most_atk(self, multiple_villagers):
        """Should find villager with highest ATK."""
        # Set one villager to have highest ATK
        multiple_villagers[0]["atk"] = 999

        champions = flask_app.compute_year_champions(multiple_villagers)

        assert champions["most_atk"]["id"] == multiple_villagers[0]["id"]
        assert champions["most_atk"]["value"] == 999

    @pytest.mark.unit
    def test_computes_most_int(self, multiple_villagers):
        """Should find villager with highest INT."""
        multiple_villagers[1]["int"] = 888

        champions = flask_app.compute_year_champions(multiple_villagers)

        assert champions["most_int"]["id"] == multiple_villagers[1]["id"]
        assert champions["most_int"]["value"] == 888

    @pytest.mark.unit
    def test_computes_richest(self, multiple_villagers):
        """Should find villager with most coins."""
        multiple_villagers[2]["coins"] = 10000

        champions = flask_app.compute_year_champions(multiple_villagers)

        assert champions["richest"]["id"] == multiple_villagers[2]["id"]
        assert champions["richest"]["value"] == 10000

    @pytest.mark.unit
    def test_computes_top_hunter(self, multiple_villagers):
        """Should find villager with most lifetime hunt wins."""
        multiple_villagers[3]["huntWins"] = 50  # Lifetime total, not yearly

        champions = flask_app.compute_year_champions(multiple_villagers)

        assert champions["top_hunter"]["id"] == multiple_villagers[3]["id"]
        assert champions["top_hunter"]["value"] == 50

    @pytest.mark.unit
    def test_prefers_alive_villagers(self, multiple_villagers):
        """Should prefer alive villagers over dead ones."""
        # Make villager with high ATK dead
        multiple_villagers[0]["atk"] = 999
        multiple_villagers[0]["alive"] = False

        # Give another villager lower but alive
        multiple_villagers[1]["atk"] = 100
        multiple_villagers[1]["alive"] = True

        champions = flask_app.compute_year_champions(multiple_villagers)

        # Should pick the alive one
        assert champions["most_atk"]["id"] == multiple_villagers[1]["id"]

    @pytest.mark.unit
    def test_empty_characters_handled(self):
        """Should handle empty character list."""
        champions = flask_app.compute_year_champions([])

        assert champions["most_atk"]["id"] is None
        assert champions["most_int"]["id"] is None


class TestBuildFamilyGraph:
    """Tests for the build_family_graph() function."""

    @pytest.mark.unit
    def test_builds_graph_for_root(self, sample_villager):
        """Should build graph with root node."""
        characters = [sample_villager]

        result = flask_app.build_family_graph(characters, sample_villager["id"])

        assert result["root_id"] == sample_villager["id"]
        assert len(result["nodes"]) >= 1
        assert "edges" in result

    @pytest.mark.unit
    def test_includes_parents(self, sample_villager, multiple_villagers):
        """Should include parent nodes when they exist."""
        # Set up parent relationship
        parent = multiple_villagers[0].copy()
        parent["id"] = 100
        parent["name"] = "Parent"

        sample_villager["motherId"] = 100

        characters = [sample_villager, parent]

        result = flask_app.build_family_graph(characters, sample_villager["id"])

        node_ids = [n["id"] for n in result["nodes"]]
        assert 100 in node_ids

    @pytest.mark.unit
    def test_includes_children(self, sample_villager, multiple_villagers):
        """Should include child nodes when they exist."""
        # Set up child relationship
        child = multiple_villagers[0].copy()
        child["id"] = 200
        child["name"] = "Child"

        sample_villager["childrenIds"] = [200]

        characters = [sample_villager, child]

        result = flask_app.build_family_graph(characters, sample_villager["id"])

        node_ids = [n["id"] for n in result["nodes"]]
        assert 200 in node_ids

    @pytest.mark.unit
    def test_respects_max_nodes(self, sample_villager):
        """Should respect max_nodes limit."""
        characters = [sample_villager]

        result = flask_app.build_family_graph(
            characters,
            sample_villager["id"],
            max_nodes=5
        )

        assert len(result["nodes"]) <= 5
