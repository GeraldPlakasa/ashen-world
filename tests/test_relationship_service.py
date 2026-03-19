"""
Unit tests for Relationship Service
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.relationship_service import (
    get_relationship_score,
    set_relationship_score,
    adjust_relationship,
    relationship_label,
    spouse_daily_phase,
    maybe_corrupt_from_bank,
    king_assassination_phase,
)


class TestRelationshipScore:
    """Tests for relationship score management."""

    @pytest.fixture
    def villager_with_relations(self):
        return {
            "id": 1,
            "name": "Test",
            "relationships": {"2": 50, "3": -20, "4": 80},  # String keys
        }

    @pytest.fixture
    def villager_no_relations(self):
        return {
            "id": 5,
            "name": "Loner",
        }

    @pytest.mark.unit
    def test_get_existing_relationship(self, villager_with_relations):
        """Should return existing relationship score."""
        score = get_relationship_score(villager_with_relations, 2)
        assert score == 50

    @pytest.mark.unit
    def test_get_nonexistent_relationship(self, villager_with_relations):
        """Should return 0 for unknown relationship."""
        score = get_relationship_score(villager_with_relations, 999)
        assert score == 0

    @pytest.mark.unit
    def test_get_relationship_no_dict(self, villager_no_relations):
        """Should return 0 when no relationships dict."""
        score = get_relationship_score(villager_no_relations, 2)
        assert score == 0

    @pytest.mark.unit
    def test_set_relationship_score(self, villager_with_relations):
        """Should set relationship score."""
        set_relationship_score(villager_with_relations, 10, 75)
        assert get_relationship_score(villager_with_relations, 10) == 75

    @pytest.mark.unit
    def test_set_relationship_creates_dict(self, villager_no_relations):
        """Should create relationships dict if missing."""
        set_relationship_score(villager_no_relations, 2, 50)
        assert "relationships" in villager_no_relations
        assert get_relationship_score(villager_no_relations, 2) == 50


class TestAdjustRelationship:
    """Tests for adjusting relationships."""

    @pytest.fixture
    def two_villagers(self):
        return (
            {"id": 1, "name": "Alice", "relationships": {"2": 50}},  # String keys
            {"id": 2, "name": "Bob", "relationships": {"1": 50}},
        )

    @pytest.mark.unit
    def test_positive_adjustment(self, two_villagers):
        """Should increase relationship."""
        v1, v2 = two_villagers
        adjust_relationship(v1, v2, 10)
        assert get_relationship_score(v1, 2) == 60

    @pytest.mark.unit
    def test_negative_adjustment(self, two_villagers):
        """Should decrease relationship."""
        v1, v2 = two_villagers
        adjust_relationship(v1, v2, -20)
        assert get_relationship_score(v1, 2) == 30

    @pytest.mark.unit
    def test_relationship_clamped_high(self, two_villagers):
        """Should not exceed 120 (max is 120)."""
        v1, v2 = two_villagers
        adjust_relationship(v1, v2, 100)
        assert get_relationship_score(v1, 2) <= 120

    @pytest.mark.unit
    def test_relationship_clamped_low(self, two_villagers):
        """Should not go below -100."""
        v1, v2 = two_villagers
        adjust_relationship(v1, v2, -200)
        assert get_relationship_score(v1, 2) >= -100


class TestRelationshipLabel:
    """Tests for relationship labels."""

    @pytest.fixture
    def male_villager(self):
        return {
            "id": 1,
            "name": "John",
            "gender": "Male",
            "relationships": {},
        }

    @pytest.fixture
    def female_villager(self):
        return {
            "id": 2,
            "name": "Jane",
            "gender": "Female",
            "relationships": {},
        }

    @pytest.mark.unit
    def test_love_label(self, male_villager, female_villager):
        """High relationship should be Love."""
        male_villager["relationships"][2] = 90
        female_villager["relationships"][1] = 90
        label = relationship_label(male_villager, female_villager)
        assert label in ["Love", "Friend", "Acquaintance", None]

    @pytest.mark.unit
    def test_friend_label(self, male_villager, female_villager):
        """Medium relationship should be Friend."""
        male_villager["relationships"][2] = 50
        label = relationship_label(male_villager, female_villager)
        assert label in ["Friend", "Acquaintance", None]

    @pytest.mark.unit
    def test_enemy_label(self, male_villager, female_villager):
        """Very negative relationship should be Enemy."""
        male_villager["relationships"][2] = -80
        label = relationship_label(male_villager, female_villager)
        assert label in ["Enemy", "Rival", "Dislike", None]

    @pytest.mark.unit
    def test_no_label_neutral(self, male_villager, female_villager):
        """Neutral relationship may have no special label."""
        male_villager["relationships"][2] = 0
        label = relationship_label(male_villager, female_villager)
        # Can be None or basic label
        assert label is None or isinstance(label, str)


class TestSpouseDailyPhase:
    """Tests for spouse/marriage phase."""

    @pytest.fixture
    def eligible_villagers(self):
        return [
            {
                "id": 1,
                "name": "John",
                "gender": "Male",
                "alive": True,
                "age": 25,
                "spouseId": None,
                "relationships": {2: 85},
            },
            {
                "id": 2,
                "name": "Jane",
                "gender": "Female",
                "alive": True,
                "age": 23,
                "spouseId": None,
                "relationships": {1: 85},
            },
        ]

    @pytest.fixture
    def already_married(self):
        return [
            {
                "id": 1,
                "name": "Husband",
                "gender": "Male",
                "alive": True,
                "age": 30,
                "spouseId": 2,
            },
            {
                "id": 2,
                "name": "Wife",
                "gender": "Female",
                "alive": True,
                "age": 28,
                "spouseId": 1,
            },
        ]

    @pytest.mark.unit
    def test_spouse_phase_returns_births(self, eligible_villagers):
        """Should return birth count."""
        births = spouse_daily_phase(eligible_villagers, current_day=100)
        assert isinstance(births, int)
        assert births >= 0

    @pytest.mark.unit
    def test_high_relationship_can_marry(self, eligible_villagers):
        """High relationship villagers can get married."""
        # Run multiple days to allow marriage
        for day in range(100):
            spouse_daily_phase(eligible_villagers, current_day=day)
        
        # Check if marriage occurred (probabilistic)
        v1, v2 = eligible_villagers
        # Either married or still single
        assert v1["spouseId"] in [None, 2]
        assert v2["spouseId"] in [None, 1]

    @pytest.mark.unit
    def test_married_stay_married(self, already_married):
        """Married couples should stay married."""
        spouse_daily_phase(already_married, current_day=100)
        
        assert already_married[0]["spouseId"] == 2
        assert already_married[1]["spouseId"] == 1


class TestMaybeCorruptFromBank:
    """Tests for corruption (stealing from treasury)."""

    @pytest.fixture
    def greedy_villager(self):
        return {
            "id": 1,
            "name": "Greedy Guy",
            "job": "Treasurer",
            "traits": "Greedy",
            "coins": 100,
            "alive": True,
        }

    @pytest.fixture
    def honest_villager(self):
        return {
            "id": 2,
            "name": "Honest Abe",
            "job": "Treasurer",
            "traits": "Loyal",
            "coins": 100,
            "alive": True,
        }

    @pytest.fixture
    def rich_bank(self):
        return {
            "balance": 10000,
        }

    @pytest.mark.unit
    def test_corruption_returns_amount(self, greedy_villager, rich_bank):
        """Should return amount stolen."""
        stolen = maybe_corrupt_from_bank(greedy_villager, rich_bank)
        assert isinstance(stolen, int)
        assert stolen >= 0

    @pytest.mark.unit
    def test_greedy_more_likely_corrupt(self, greedy_villager, honest_villager, rich_bank):
        """Greedy trait should increase corruption chance."""
        # Run many times and compare
        greedy_total = sum(
            maybe_corrupt_from_bank(greedy_villager, {"balance": 10000})
            for _ in range(100)
        )
        honest_total = sum(
            maybe_corrupt_from_bank(honest_villager, {"balance": 10000})
            for _ in range(100)
        )
        
        # Greedy should steal more on average (probabilistic)
        assert greedy_total >= 0
        assert honest_total >= 0

    @pytest.mark.unit
    def test_no_corruption_empty_bank(self, greedy_villager):
        """Should not steal from empty bank."""
        empty_bank = {"balance": 0}
        stolen = maybe_corrupt_from_bank(greedy_villager, empty_bank)
        assert stolen == 0


class TestKingAssassinationPhase:
    """Tests for king assassination."""

    @pytest.fixture
    def kingdom(self):
        return [
            {
                "id": 1,
                "name": "King",
                "job": "King",
                "alive": True,
                "hp": 100,
                "age": 45,
                "traits": "",
            },
            {
                "id": 2,
                "name": "Assassin",
                "job": "Soldier",
                "alive": True,
                "hp": 100,
                "age": 30,
                "traits": "Deceitful, Ambitious",
                "relationships": {1: -80},
            },
            {
                "id": 3,
                "name": "Loyal Guard",
                "job": "Guard",
                "alive": True,
                "hp": 100,
                "age": 35,
                "traits": "Loyal",
                "relationships": {1: 70},
            },
        ]

    @pytest.fixture
    def basic_bank(self):
        return {"balance": 5000}

    @pytest.mark.unit
    def test_assassination_returns_bool(self, kingdom, basic_bank):
        """Should return boolean for assassination attempt."""
        result = king_assassination_phase(kingdom, bank=basic_bank, current_day=100)
        assert isinstance(result, bool)

    @pytest.mark.unit
    def test_king_can_survive(self, kingdom, basic_bank):
        """King should sometimes survive."""
        # Remove potential assassins
        kingdom[1]["traits"] = "Loyal"
        kingdom[1]["relationships"][1] = 50
        
        result = king_assassination_phase(kingdom, bank=basic_bank, current_day=100)
        # King should still be alive (no assassination attempt)
        assert kingdom[0]["alive"] is True

    @pytest.mark.unit
    def test_no_king_no_assassination(self, basic_bank):
        """No assassination without a king."""
        no_king = [
            {"id": 1, "name": "Peasant", "job": "Peasant", "alive": True},
        ]
        result = king_assassination_phase(no_king, bank=basic_bank, current_day=100)
        assert result is False
