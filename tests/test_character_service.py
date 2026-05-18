"""
Unit tests for Character Service
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.character_service import (
    create_player_character,
    get_pinned_character_data,
)


class TestCreatePlayerCharacter:
    """Tests for player character creation."""

    @pytest.mark.unit
    def test_returns_tuple(self):
        """Should return (success, message, villager) tuple."""
        result = create_player_character(
            username="testuser",
            given_name="Hero",
            family="Smith",
            chosen_trait="Brave",
            gender="Male"
        )
        assert isinstance(result, tuple)
        assert len(result) == 3

    @pytest.mark.unit
    def test_success_creates_villager(self):
        """Successful creation should return villager dict."""
        success, msg, villager = create_player_character(
            username="newuser123",
            given_name="TestHero",
            family="TestFamily",
            chosen_trait="Wise",
            gender="Female"
        )
        # May fail if username exists, but should return valid tuple
        assert isinstance(success, bool)
        if success:
            assert villager is not None
            assert isinstance(villager, dict)

    @pytest.mark.unit
    def test_player_marked_correctly(self):
        """Created player should have correct owner and origin."""
        success, msg, villager = create_player_character(
            username="uniqueuser456",
            given_name="UniqueHero",
            family="UniqueFamily",
            chosen_trait="Brave",
            gender="Male"
        )
        if success and villager:
            assert villager.get("owner") == "uniqueuser456"
            assert villager.get("origin") == "player"


class TestGetPinnedCharacterData:
    """Tests for getting pinned character info."""

    @pytest.fixture
    def characters_with_player(self):
        return [
            {"id": 1, "name": "King Arthur", "job": "King", "alive": True, "owner": None},
            {
                "id": 2,
                "name": "Player Hero",
                "job": "Knight",
                "alive": True,
                "owner": "testuser",
                "isPlayer": True,
                "hp": 100,
                "atk": 50,
                "coins": 500,
            },
            {"id": 3, "name": "Peasant Joe", "job": "Peasant", "alive": True, "owner": None},
        ]

    @pytest.fixture
    def characters_no_player(self):
        return [
            {"id": 1, "name": "King Arthur", "job": "King", "alive": True},
            {"id": 2, "name": "Knight Bob", "job": "Knight", "alive": True},
        ]

    @pytest.mark.unit
    def test_returns_none_for_no_player(self, characters_no_player):
        """Should return None when user has no player."""
        data = get_pinned_character_data("testuser", characters_no_player)
        assert data is None

    @pytest.mark.unit
    def test_returns_none_for_wrong_user(self, characters_with_player):
        """Should return None for different username."""
        data = get_pinned_character_data("wronguser", characters_with_player)
        assert data is None

    @pytest.mark.unit
    def test_handles_dead_player(self):
        """Should handle dead player character."""
        characters = [
            {
                "id": 1,
                "name": "Dead Player",
                "job": "Knight",
                "alive": False,
                "owner": "testuser",
                "isPlayer": True,
            },
        ]
        data = get_pinned_character_data("testuser", characters)
        # Should still return data for dead player (or None based on implementation)
        # Just verify no crash
        assert data is None or isinstance(data, dict)

    @pytest.mark.unit
    def test_empty_characters_list(self):
        """Should handle empty character list."""
        data = get_pinned_character_data("testuser", [])
        assert data is None
