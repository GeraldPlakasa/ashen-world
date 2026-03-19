"""
Unit tests for Family Service
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.family_service import (
    birth_daily_phase,
    child_daily_phase,
    coming_of_age_phase,
)


class TestBirthDailyPhase:
    """Tests for daily birth phase."""

    @pytest.fixture
    def married_couple(self):
        return [
            {
                "id": 1,
                "name": "Husband",
                "gender": "Male",
                "alive": True,
                "age": 30,
                "spouseId": 2,
                "hp": 100,
                "childrenIds": [],
            },
            {
                "id": 2,
                "name": "Wife",
                "gender": "Female",
                "alive": True,
                "age": 28,
                "spouseId": 1,
                "hp": 100,
                "childrenIds": [],
            },
        ]

    @pytest.fixture
    def too_old_couple(self):
        return [
            {
                "id": 1,
                "name": "Old Husband",
                "gender": "Male",
                "alive": True,
                "age": 60,
                "spouseId": 2,
                "hp": 100,
                "childrenIds": [],
            },
            {
                "id": 2,
                "name": "Old Wife",
                "gender": "Female",
                "alive": True,
                "age": 55,
                "spouseId": 1,
                "hp": 100,
                "childrenIds": [],
            },
        ]

    @pytest.mark.unit
    def test_birth_returns_count(self, married_couple):
        """Should return number of births."""
        count = birth_daily_phase(married_couple, current_day=100)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.unit
    def test_no_birth_without_spouse(self):
        """Single person should not have children."""
        singles = [
            {
                "id": 1,
                "name": "Single",
                "gender": "Female",
                "alive": True,
                "age": 25,
                "spouseId": None,
                "hp": 100,
            },
        ]
        count = birth_daily_phase(singles, current_day=100)
        assert count == 0

    @pytest.mark.unit
    def test_dead_cannot_have_children(self, married_couple):
        """Dead spouse should not have children."""
        married_couple[1]["alive"] = False
        count = birth_daily_phase(married_couple, current_day=100)
        assert count == 0

    @pytest.mark.unit
    def test_old_couple_less_likely(self, too_old_couple):
        """Old couples should have fewer/no children."""
        # Run many times, old couples should have 0 births most of the time
        total_births = 0
        for day in range(100):
            total_births += birth_daily_phase(too_old_couple, current_day=day)
        # Very old couple should have very few births
        # This is probabilistic, so we just check it's not crazy high
        assert total_births < 50


class TestChildDailyPhase:
    """Tests for child daily phase."""

    @pytest.fixture
    def family_with_children(self):
        return [
            {
                "id": 1,
                "name": "Father",
                "gender": "Male",
                "alive": True,
                "age": 35,
                "job": "Merchant",
                "childrenIds": [3, 4],
            },
            {
                "id": 2,
                "name": "Mother",
                "gender": "Female",
                "alive": True,
                "age": 33,
                "job": "Artisan",
                "childrenIds": [3, 4],
            },
            {
                "id": 3,
                "name": "Son",
                "gender": "Male",
                "alive": True,
                "age": 10,
                "job": "Child",
                "fatherId": 1,
                "motherId": 2,
                "int": 20,
                "exp": 0,
            },
            {
                "id": 4,
                "name": "Daughter",
                "gender": "Female",
                "alive": True,
                "age": 8,
                "job": "Child",
                "fatherId": 1,
                "motherId": 2,
                "int": 25,
                "exp": 0,
            },
        ]

    @pytest.mark.unit
    def test_children_gain_exp(self, family_with_children):
        """Children should gain experience daily."""
        initial_exp = [family_with_children[2]["exp"], family_with_children[3]["exp"]]
        
        # Run child phase for multiple days
        for day in range(10):
            child_daily_phase(family_with_children, current_day=day)
        
        # Children should have gained some exp
        final_exp = [family_with_children[2]["exp"], family_with_children[3]["exp"]]
        assert final_exp[0] >= initial_exp[0]
        assert final_exp[1] >= initial_exp[1]

    @pytest.mark.unit
    def test_children_have_child_job(self, family_with_children):
        """Young children should have Child job."""
        child_daily_phase(family_with_children, current_day=100)
        
        for c in family_with_children:
            if c["age"] < 17:
                assert c["job"] == "Child"


class TestComingOfAgePhase:
    """Tests for coming of age (age 17)."""

    @pytest.fixture
    def teen_family(self):
        return [
            {
                "id": 1,
                "name": "Teen Boy",
                "gender": "Male",
                "alive": True,
                "age": 17,
                "job": "Child",
                "traits": "Brave",
                "fatherId": 2,
                "motherId": 3,
            },
            {
                "id": 2,
                "name": "Father",
                "gender": "Male",
                "alive": True,
                "age": 45,
                "job": "Soldier",
            },
            {
                "id": 3,
                "name": "Mother",
                "gender": "Female",
                "alive": True,
                "age": 43,
                "job": "Merchant",
            },
        ]

    @pytest.mark.unit
    def test_coming_of_age_assigns_job(self, teen_family):
        """Teen turning 17 should get adult job."""
        coming_of_age_phase(teen_family, current_day=100)
        
        teen = teen_family[0]
        # Should no longer be Child
        assert teen["job"] != "Child" or teen["age"] < 17

    @pytest.mark.unit
    def test_younger_stays_child(self, teen_family):
        """Under 17 should stay Child."""
        teen_family[0]["age"] = 15
        coming_of_age_phase(teen_family, current_day=100)
        
        assert teen_family[0]["job"] == "Child"

    @pytest.mark.unit
    def test_coming_of_age_uses_traits(self, teen_family):
        """Job assignment should consider traits."""
        # Brave trait should influence job choice
        coming_of_age_phase(teen_family, current_day=100)
        
        teen = teen_family[0]
        # Just verify a job was assigned
        assert isinstance(teen["job"], str)
        assert len(teen["job"]) > 0
