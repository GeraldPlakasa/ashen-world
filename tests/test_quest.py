"""
Unit tests for Quest System
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.quest_service import (
    QUEST_TYPES,
    _calculate_quest_success,
    _select_quest_type,
    _generate_quest_description,
    _calculate_volunteer_score,
)


class TestQuestTypes:
    """Tests for quest type definitions."""

    @pytest.mark.unit
    def test_all_quest_types_have_required_fields(self):
        """All quest types should have required configuration."""
        required_fields = ["name", "descriptions", "stat_focus", "stat_threshold", "gold_reward", "gear_chance"]
        
        for qt_name, qt_data in QUEST_TYPES.items():
            for field in required_fields:
                assert field in qt_data, f"{qt_name} missing {field}"

    @pytest.mark.unit
    def test_quest_thresholds_are_high(self):
        """Quest thresholds should be challenging (>=100)."""
        for qt_name, qt_data in QUEST_TYPES.items():
            assert qt_data["stat_threshold"] >= 100, f"{qt_name} threshold too low"

    @pytest.mark.unit
    def test_quest_stat_focus_valid(self):
        """Quest stat focus should be atk, def, int, or rep."""
        valid_stats = {"atk", "def", "int", "rep", "mp"}
        for qt_name, qt_data in QUEST_TYPES.items():
            assert qt_data["stat_focus"] in valid_stats, f"{qt_name} has invalid stat_focus"


class TestQuestDescription:
    """Tests for quest description generation."""

    @pytest.mark.unit
    def test_generates_combat_description(self):
        """Should generate valid combat quest description."""
        name, desc = _generate_quest_description("COMBAT")
        assert name == "Hunt the Beast"
        assert any(beast in desc for beast in QUEST_TYPES["COMBAT"]["beasts"])

    @pytest.mark.unit
    def test_generates_diplomacy_description(self):
        """Should generate valid diplomacy quest description."""
        name, desc = _generate_quest_description("DIPLOMACY")
        assert name == "Diplomatic Mission"
        assert any(village in desc for village in QUEST_TYPES["DIPLOMACY"]["villages"])

    @pytest.mark.unit
    def test_generates_exploration_description(self):
        """Should generate valid exploration quest description."""
        name, desc = _generate_quest_description("EXPLORATION")
        assert name == "Explore Unknown Lands"
        assert any(loc in desc for loc in QUEST_TYPES["EXPLORATION"]["locations"])

    @pytest.mark.unit
    def test_generates_trade_description(self):
        """Should generate valid trade quest description."""
        name, desc = _generate_quest_description("TRADE")
        assert name == "Trade Expedition"
        assert any(goods in desc for goods in QUEST_TYPES["TRADE"]["goods"])

    @pytest.mark.unit
    def test_generates_rescue_description(self):
        """Should generate valid rescue quest description."""
        name, desc = _generate_quest_description("RESCUE")
        assert name == "Rescue Mission"
        assert any(enemy in desc for enemy in QUEST_TYPES["RESCUE"]["enemies"])

    @pytest.mark.unit
    def test_generates_treasure_hunt_description(self):
        """Should generate valid treasure hunt quest description."""
        name, desc = _generate_quest_description("TREASURE_HUNT")
        assert name == "Treasure Hunt"
        assert any(treasure in desc for treasure in QUEST_TYPES["TREASURE_HUNT"]["treasures"])

    @pytest.mark.unit
    def test_all_quest_types_generate_valid_description(self):
        """All quest types should generate valid descriptions without error."""
        for quest_type in QUEST_TYPES.keys():
            name, desc = _generate_quest_description(quest_type)
            assert name is not None
            assert desc is not None
            assert len(desc) > 0


class TestVolunteerScore:
    """Tests for volunteer scoring."""

    @pytest.fixture
    def basic_villager(self):
        return {
            "id": 1,
            "name": "Test",
            "alive": True,
            "age": 25,
            "atk": 50,
            "def": 30,
            "int": 40,
            "rep": 20,
            "hp": 100,
            "hunger": 30,
            "coins": 100,
            "level": 5,
            "job": "Soldier",
            "traits": "Brave",
        }

    @pytest.mark.unit
    def test_dead_villager_cannot_volunteer(self, basic_villager):
        """Dead villagers should have negative score."""
        basic_villager["alive"] = False
        score = _calculate_volunteer_score(basic_villager, "COMBAT")
        assert score < 0

    @pytest.mark.unit
    def test_child_cannot_volunteer(self, basic_villager):
        """Children under 18 should have negative score."""
        basic_villager["age"] = 15
        score = _calculate_volunteer_score(basic_villager, "COMBAT")
        assert score < 0

    @pytest.mark.unit
    def test_elderly_cannot_volunteer(self, basic_villager):
        """Villagers over 65 should have negative score."""
        basic_villager["age"] = 70
        score = _calculate_volunteer_score(basic_villager, "COMBAT")
        assert score < 0

    @pytest.mark.unit
    def test_king_cannot_volunteer(self, basic_villager):
        """King should have negative score."""
        basic_villager["job"] = "King"
        score = _calculate_volunteer_score(basic_villager, "COMBAT")
        assert score < 0

    @pytest.mark.unit
    def test_queen_cannot_volunteer(self, basic_villager):
        """Queen should have negative score."""
        basic_villager["job"] = "Queen"
        score = _calculate_volunteer_score(basic_villager, "COMBAT")
        assert score < 0

    @pytest.mark.unit
    def test_eligible_villager_has_positive_score(self, basic_villager):
        """Eligible villager should have positive score."""
        score = _calculate_volunteer_score(basic_villager, "COMBAT")
        assert score > 0

    @pytest.mark.unit
    def test_brave_trait_increases_combat_score(self, basic_villager):
        """Brave trait should increase combat quest score."""
        basic_villager["traits"] = ""
        base_score = _calculate_volunteer_score(basic_villager, "COMBAT")
        
        basic_villager["traits"] = "Brave"
        brave_score = _calculate_volunteer_score(basic_villager, "COMBAT")
        
        assert brave_score > base_score


class TestQuestSuccess:
    """Tests for quest success calculation."""

    @pytest.fixture
    def strong_party(self):
        """Party with very high stats."""
        return [
            {"id": 1, "atk": 250, "def": 200, "int": 180, "rep": 150, "hp": 200, "hunger": 20, "coins": 500, "level": 20},
            {"id": 2, "atk": 240, "def": 190, "int": 170, "rep": 140, "hp": 180, "hunger": 30, "coins": 400, "level": 18},
            {"id": 3, "atk": 230, "def": 180, "int": 160, "rep": 130, "hp": 170, "hunger": 25, "coins": 350, "level": 17},
        ]

    @pytest.fixture
    def weak_party(self):
        """Party with very low stats."""
        return [
            {"id": 1, "atk": 15, "def": 12, "int": 10, "rep": 5, "hp": 50, "hunger": 60, "coins": 20, "level": 1},
            {"id": 2, "atk": 12, "def": 10, "int": 8, "rep": 3, "hp": 40, "hunger": 70, "coins": 15, "level": 1},
        ]

    @pytest.fixture
    def basic_bank(self):
        return {
            "balance": 1000,
            "building_levels": {},
            "building_health": {},
        }

    @pytest.mark.unit
    def test_strong_party_has_high_success_chance(self, strong_party, basic_bank):
        """Strong party should have high success chance."""
        success, margin, stats = _calculate_quest_success(strong_party, "COMBAT", basic_bank)
        assert stats["final_chance"] >= 50, f"Strong party should have >=50% chance, got {stats['final_chance']}"

    @pytest.mark.unit
    def test_weak_party_has_low_success_chance(self, weak_party, basic_bank):
        """Weak party should have low success chance."""
        success, margin, stats = _calculate_quest_success(weak_party, "COMBAT", basic_bank)
        assert stats["final_chance"] <= 30, f"Weak party should have <=30% chance, got {stats['final_chance']}"

    @pytest.mark.unit
    def test_success_chance_never_exceeds_95(self, strong_party, basic_bank):
        """Success chance should never exceed 95%."""
        # Give extremely high stats
        for v in strong_party:
            v["atk"] = 1000
            v["coins"] = 10000
        basic_bank["balance"] = 100000
        
        success, margin, stats = _calculate_quest_success(strong_party, "COMBAT", basic_bank)
        assert stats["final_chance"] <= 95

    @pytest.mark.unit
    def test_success_chance_never_below_1(self, weak_party, basic_bank):
        """Success chance should never go below 1%."""
        # Give extremely low stats
        for v in weak_party:
            v["atk"] = 1
            v["hp"] = 10
            v["hunger"] = 90
        
        success, margin, stats = _calculate_quest_success(weak_party, "COMBAT", basic_bank)
        assert stats["final_chance"] >= 1

    @pytest.mark.unit
    def test_low_hp_reduces_success(self, strong_party, basic_bank):
        """Low HP party should have reduced success chance."""
        # Normal HP
        success1, margin1, stats1 = _calculate_quest_success(strong_party, "COMBAT", basic_bank)
        
        # Low HP
        for v in strong_party:
            v["hp"] = 25
        success2, margin2, stats2 = _calculate_quest_success(strong_party, "COMBAT", basic_bank)
        
        assert stats2["final_chance"] < stats1["final_chance"]

    @pytest.mark.unit
    def test_stats_info_contains_required_fields(self, strong_party, basic_bank):
        """Stats info should contain all required fields for display."""
        success, margin, stats = _calculate_quest_success(strong_party, "COMBAT", basic_bank)
        
        required = ["avg_stat", "threshold", "ratio", "final_chance"]
        for field in required:
            assert field in stats, f"Missing {field} in stats_info"


class TestKingTraitInfluence:
    """Tests for King trait influence on quest type selection."""

    @pytest.mark.unit
    def test_select_quest_type_returns_valid_type(self):
        """Should return a valid quest type."""
        characters = [
            {"id": 1, "job": "King", "alive": True, "traits": ""},
        ]
        qt = _select_quest_type(characters)
        assert qt in QUEST_TYPES

    @pytest.mark.unit
    def test_no_king_still_selects_quest(self):
        """Should select quest type even without king."""
        characters = [
            {"id": 1, "job": "Farmer", "alive": True, "traits": ""},
        ]
        qt = _select_quest_type(characters)
        assert qt in QUEST_TYPES
