"""
Unit tests for Villager Service
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.villager_service import (
    next_unique_id,
    reset_id_from_characters,
    unique_full_name,
    make_row,
    generate_characters,
)


class TestNextUniqueId:
    """Tests for unique ID generation."""

    @pytest.mark.unit
    def test_returns_positive_int(self):
        """Should return positive integer."""
        id1 = next_unique_id()
        assert isinstance(id1, int)
        assert id1 > 0

    @pytest.mark.unit
    def test_ids_are_unique(self):
        """Consecutive IDs should be different."""
        ids = [next_unique_id() for _ in range(10)]
        assert len(ids) == len(set(ids)), "IDs should be unique"

    @pytest.mark.unit
    def test_ids_increment(self):
        """IDs should generally increment."""
        id1 = next_unique_id()
        id2 = next_unique_id()
        assert id2 > id1


class TestResetIdFromCharacters:
    """Tests for ID counter reset."""

    @pytest.mark.unit
    def test_reset_from_existing_chars(self):
        """Should reset counter based on existing max ID."""
        chars = [
            {"id": 100, "name": "Test1"},
            {"id": 50, "name": "Test2"},
            {"id": 200, "name": "Test3"},
        ]
        reset_id_from_characters(chars)
        
        # Next ID should be higher than 200
        new_id = next_unique_id()
        assert new_id > 200

    @pytest.mark.unit
    def test_reset_empty_list(self):
        """Should handle empty character list."""
        reset_id_from_characters([])
        # Should not crash, next ID still works
        new_id = next_unique_id()
        assert new_id > 0

    @pytest.mark.unit
    def test_reset_with_missing_ids(self):
        """Should handle characters without IDs."""
        chars = [
            {"name": "NoId1"},
            {"id": 50, "name": "HasId"},
            {"name": "NoId2"},
        ]
        reset_id_from_characters(chars)
        new_id = next_unique_id()
        assert new_id > 50


class TestUniqueFullName:
    """Tests for unique name generation."""

    @pytest.mark.unit
    def test_returns_tuple(self):
        """Should return (first, last) tuple."""
        taken = set()
        result = unique_full_name(taken)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.unit
    def test_names_are_strings(self):
        """Both names should be strings."""
        taken = set()
        first, last = unique_full_name(taken)
        assert isinstance(first, str)
        assert isinstance(last, str)
        assert len(first) > 0
        assert len(last) > 0

    @pytest.mark.unit
    def test_avoids_taken_names(self):
        """Should not return taken names."""
        taken = {"John Smith", "Jane Doe", "Bob Builder"}
        first, last = unique_full_name(taken)
        full_name = f"{first} {last}"
        assert full_name not in taken

    @pytest.mark.unit
    def test_generates_unique_names(self):
        """Should generate unique names repeatedly."""
        taken = set()
        names = []
        for _ in range(50):
            first, last = unique_full_name(taken)
            full_name = f"{first} {last}"
            names.append(full_name)
            taken.add(full_name)
        
        assert len(names) == len(set(names)), "All names should be unique"


class TestMakeRow:
    """Tests for villager creation."""

    @pytest.mark.unit
    def test_creates_villager_dict(self):
        """Should create complete villager dictionary."""
        taken = set()
        v = make_row(taken)
        assert isinstance(v, dict)

    @pytest.mark.unit
    def test_has_required_fields(self):
        """Villager should have all required fields."""
        required = [
            "id", "name", "family", "gender", "age",
            "hp", "atk", "def", "int", "rep", "coins", "hunger",
            "job", "traits", "alive", "level", "exp"
        ]
        taken = set()
        v = make_row(taken)
        
        for field in required:
            assert field in v, f"Missing field: {field}"

    @pytest.mark.unit
    def test_valid_gender(self):
        """Gender should be Male or Female."""
        taken = set()
        v = make_row(taken)
        assert v["gender"] in ["Male", "Female"]

    @pytest.mark.unit
    def test_valid_age(self):
        """Age should be reasonable."""
        taken = set()
        v = make_row(taken)
        assert 0 <= v["age"] <= 100

    @pytest.mark.unit
    def test_alive_by_default(self):
        """New villagers should be alive."""
        taken = set()
        v = make_row(taken)
        assert v["alive"] is True

    @pytest.mark.unit
    def test_positive_stats(self):
        """Stats should be positive."""
        taken = set()
        v = make_row(taken)
        assert v["hp"] > 0
        assert v["atk"] >= 0
        assert v["def"] >= 0
        assert v["int"] >= 0

    @pytest.mark.unit
    def test_forced_gender(self):
        """Should respect forced gender."""
        taken = set()
        v = make_row(taken, forced_gender="Female")
        assert v["gender"] == "Female"

    @pytest.mark.unit
    def test_forced_job(self):
        """Should respect forced job."""
        taken = set()
        v = make_row(taken, forced_job="King")
        assert v["job"] == "King"

    @pytest.mark.unit
    def test_has_traits(self):
        """Villager should have traits assigned."""
        taken = set()
        v = make_row(taken)
        # Traits can be empty string or have values
        assert "traits" in v


class TestGenerateCharacters:
    """Tests for bulk character generation."""

    @pytest.mark.unit
    def test_generates_correct_count(self):
        """Should generate requested number of characters."""
        chars = generate_characters(n=20)
        assert len(chars) == 20

    @pytest.mark.unit
    def test_all_have_unique_ids(self):
        """All characters should have unique IDs."""
        chars = generate_characters(n=30)
        ids = [c["id"] for c in chars]
        assert len(ids) == len(set(ids)), "IDs should be unique"

    @pytest.mark.unit
    def test_all_have_unique_names(self):
        """All characters should have unique names."""
        chars = generate_characters(n=30)
        names = [c["name"] for c in chars]
        assert len(names) == len(set(names)), "Names should be unique"

    @pytest.mark.unit
    def test_includes_king(self):
        """Should include at least one King."""
        chars = generate_characters(n=50)
        kings = [c for c in chars if c.get("job") == "King"]
        assert len(kings) >= 1, "Should have at least one King"

    @pytest.mark.unit
    def test_mixed_genders(self):
        """Should have both genders."""
        chars = generate_characters(n=50)
        males = sum(1 for c in chars if c["gender"] == "Male")
        females = sum(1 for c in chars if c["gender"] == "Female")
        assert males > 0, "Should have males"
        assert females > 0, "Should have females"

    @pytest.mark.unit
    def test_varied_ages(self):
        """Should have variety of ages."""
        chars = generate_characters(n=50)
        ages = [c["age"] for c in chars]
        assert min(ages) < max(ages), "Should have varied ages"

    @pytest.mark.unit
    def test_minimum_count(self):
        """Should handle small counts (minimum 2 for King+Queen)."""
        chars = generate_characters(n=2)
        assert len(chars) == 2
        # Should have King and Queen
        jobs = [c["job"] for c in chars]
        assert "King" in jobs
        assert "Queen" in jobs

    @pytest.mark.unit
    def test_large_count(self):
        """Should handle large counts."""
        chars = generate_characters(n=100)
        assert len(chars) == 100
        # All should still be valid
        for c in chars:
            assert "id" in c
            assert "name" in c
            assert c["alive"] is True
