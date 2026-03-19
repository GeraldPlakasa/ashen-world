"""
Unit tests for Achievement Service
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.achievement_service import (
    get_achievements,
    set_achievements,
    has_achievement,
    award_achievement,
    check_dynasty_founder,
    check_kingmaker,
    check_centurion,
    check_legendary_hunter,
    check_wealthy,
    check_elder_statesman,
    check_questmaster,
    get_kings_voted_for,
    set_kings_voted_for,
    add_king_voted_for,
    ACHIEVEMENTS,
)


class TestAchievementDefinitions:
    """Tests for achievement definitions."""

    @pytest.mark.unit
    def test_all_achievements_have_required_fields(self):
        """All achievements should have name, description."""
        required_fields = ["name", "description"]
        for ach_id, ach_data in ACHIEVEMENTS.items():
            for field in required_fields:
                assert field in ach_data, f"Achievement {ach_id} missing {field}"

    @pytest.mark.unit
    def test_achievements_have_valid_keys(self):
        """Achievement keys should be lowercase strings."""
        for ach_id in ACHIEVEMENTS.keys():
            assert isinstance(ach_id, str)
            assert ach_id == ach_id.lower(), f"Achievement key {ach_id} should be lowercase"


class TestGetSetAchievements:
    """Tests for getting and setting achievements."""

    @pytest.fixture
    def basic_villager(self):
        return {
            "id": 1,
            "name": "Test",
            "achievements": '["CENTURION", "WEALTHY"]',  # JSON format
        }

    @pytest.fixture
    def villager_no_achievements(self):
        return {
            "id": 2,
            "name": "Newbie",
            "achievements": "[]",
        }

    @pytest.mark.unit
    def test_get_achievements_parses_json(self, basic_villager):
        """Should parse JSON achievements."""
        achs = get_achievements(basic_villager)
        assert "CENTURION" in achs
        assert "WEALTHY" in achs
        assert len(achs) == 2

    @pytest.mark.unit
    def test_get_achievements_empty(self, villager_no_achievements):
        """Should return empty list when no achievements."""
        achs = get_achievements(villager_no_achievements)
        assert achs == []

    @pytest.mark.unit
    def test_set_achievements(self, villager_no_achievements):
        """Should set achievements as JSON array."""
        set_achievements(villager_no_achievements, ["CENTURION", "WEALTHY"])
        achs = get_achievements(villager_no_achievements)
        assert "CENTURION" in achs
        assert "WEALTHY" in achs

    @pytest.mark.unit
    def test_set_achievements_empty(self, basic_villager):
        """Should handle empty list."""
        set_achievements(basic_villager, [])
        achs = get_achievements(basic_villager)
        assert achs == []

    @pytest.mark.unit
    def test_has_achievement_true(self, basic_villager):
        """Should return True when villager has achievement."""
        assert has_achievement(basic_villager, "CENTURION") is True

    @pytest.mark.unit
    def test_has_achievement_false(self, basic_villager):
        """Should return False when villager doesn't have achievement."""
        assert has_achievement(basic_villager, "DYNASTY_FOUNDER") is False


class TestAwardAchievement:
    """Tests for awarding achievements."""

    @pytest.fixture
    def villager(self):
        return {
            "id": 1,
            "name": "Test",
            "achievements": "[]",
            "rep": 0,
            "traits": "",
        }

    @pytest.mark.unit
    def test_award_new_achievement(self, villager):
        """Should award achievement and return True."""
        result = award_achievement(villager, "centurion")  # lowercase
        assert result is True
        assert has_achievement(villager, "centurion")

    @pytest.mark.unit
    def test_award_duplicate_achievement(self, villager):
        """Should not duplicate and return False."""
        award_achievement(villager, "centurion")
        result = award_achievement(villager, "centurion")
        assert result is False
        # Should still only have one
        assert get_achievements(villager).count("centurion") == 1

    @pytest.mark.unit
    def test_award_invalid_achievement(self, villager):
        """Should return False for invalid achievement ID."""
        result = award_achievement(villager, "INVALID_ACH")
        assert result is False


class TestKingsVotedFor:
    """Tests for tracking kings voted for."""

    @pytest.fixture
    def villager(self):
        return {
            "id": 1,
            "name": "Test",
            "kingsVotedFor": "[10, 20, 30]",  # JSON format
        }

    @pytest.fixture
    def villager_no_votes(self):
        return {
            "id": 2,
            "name": "Newbie",
            "kingsVotedFor": "[]",
        }

    @pytest.mark.unit
    def test_get_kings_voted_for(self, villager):
        """Should parse kings voted for."""
        kings = get_kings_voted_for(villager)
        assert kings == [10, 20, 30]

    @pytest.mark.unit
    def test_get_kings_voted_for_empty(self, villager_no_votes):
        """Should return empty list when no votes."""
        kings = get_kings_voted_for(villager_no_votes)
        assert kings == []

    @pytest.mark.unit
    def test_set_kings_voted_for(self, villager_no_votes):
        """Should set kings as JSON array."""
        set_kings_voted_for(villager_no_votes, [5, 10, 15])
        kings = get_kings_voted_for(villager_no_votes)
        assert kings == [5, 10, 15]

    @pytest.mark.unit
    def test_add_king_voted_for(self, villager):
        """Should add new king to list."""
        add_king_voted_for(villager, 40)
        kings = get_kings_voted_for(villager)
        assert 40 in kings

    @pytest.mark.unit
    def test_add_king_voted_for_no_duplicate(self, villager):
        """Should not add duplicate king."""
        add_king_voted_for(villager, 20)  # Already in list
        kings = get_kings_voted_for(villager)
        assert kings.count(20) == 1


class TestAchievementChecks:
    """Tests for individual achievement checks."""

    @pytest.mark.unit
    def test_check_centurion_true(self):
        """Villager age >= 100 should qualify."""
        v = {"age": 100, "alive": True, "achievements": ""}
        assert check_centurion(v) is True

    @pytest.mark.unit
    def test_check_centurion_false(self):
        """Villager age < 100 should not qualify."""
        v = {"age": 99, "alive": True, "achievements": ""}
        assert check_centurion(v) is False

    @pytest.mark.unit
    def test_check_wealthy_true(self):
        """Villager with >= 10000 coins should qualify."""
        v = {"coins": 10000, "alive": True, "achievements": ""}
        assert check_wealthy(v) is True

    @pytest.mark.unit
    def test_check_wealthy_false(self):
        """Villager with < 10000 coins should not qualify."""
        v = {"coins": 9999, "alive": True, "achievements": ""}
        assert check_wealthy(v) is False

    @pytest.mark.unit
    def test_check_legendary_hunter_true(self):
        """Villager with >= 500 hunt wins should qualify."""
        v = {"huntWins": 500, "alive": True, "achievements": "[]"}
        assert check_legendary_hunter(v) is True

    @pytest.mark.unit
    def test_check_legendary_hunter_false(self):
        """Villager with < 500 hunt wins should not qualify."""
        v = {"huntWins": 499, "alive": True, "achievements": "[]"}
        assert check_legendary_hunter(v) is False

    @pytest.mark.unit
    def test_check_elder_statesman_true(self):
        """King age >= 80 should qualify."""
        v = {"age": 80, "job": "King", "alive": True, "achievements": "[]"}
        assert check_elder_statesman(v) is True

    @pytest.mark.unit
    def test_check_elder_statesman_false(self):
        """Non-King or King age < 80 should not qualify."""
        v = {"age": 80, "job": "Peasant", "alive": True, "achievements": "[]"}
        assert check_elder_statesman(v) is False

    @pytest.mark.unit
    def test_check_questmaster_true(self):
        """Villager with >= 5 quest wins should qualify."""
        v = {"questWins": 5, "alive": True, "achievements": "[]"}
        assert check_questmaster(v) is True

    @pytest.mark.unit
    def test_check_questmaster_false(self):
        """Villager with < 5 quest wins should not qualify."""
        v = {"questWins": 4, "alive": True, "achievements": "[]"}
        assert check_questmaster(v) is False

    @pytest.mark.unit
    def test_check_dynasty_founder_true(self):
        """Villager with >= 5 children should qualify."""
        v = {"childrenIds": [1, 2, 3, 4, 5], "alive": True, "achievements": ""}
        assert check_dynasty_founder(v) is True

    @pytest.mark.unit
    def test_check_dynasty_founder_false(self):
        """Villager with < 5 children should not qualify."""
        v = {"childrenIds": [1, 2, 3, 4], "alive": True, "achievements": ""}
        assert check_dynasty_founder(v) is False

    @pytest.mark.unit
    def test_check_kingmaker_true(self):
        """Villager who voted for >= 5 kings should qualify."""
        v = {"kingsVotedFor": "[1,2,3,4,5]", "alive": True, "achievements": "[]"}
        assert check_kingmaker(v) is True

    @pytest.mark.unit
    def test_check_kingmaker_false(self):
        """Villager who voted for < 5 kings should not qualify."""
        v = {"kingsVotedFor": "[1,2,3,4]", "alive": True, "achievements": "[]"}
        assert check_kingmaker(v) is False
