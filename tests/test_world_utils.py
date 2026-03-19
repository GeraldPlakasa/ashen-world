"""
Unit tests for world_utils.py - pure utility functions.
"""
import pytest
import random

from src.utils.world_utils import clamp, exp_to_next_level, is_child, pick, rand_int, pick_weighted


class TestClamp:
    """Tests for the clamp() function."""

    @pytest.mark.unit
    def test_clamp_within_range(self):
        """Value within range should be unchanged."""
        assert clamp(50, 0, 100) == 50
        assert clamp(0, 0, 100) == 0
        assert clamp(100, 0, 100) == 100

    @pytest.mark.unit
    def test_clamp_below_min(self):
        """Value below min should return min."""
        assert clamp(-10, 0, 100) == 0
        assert clamp(-1, 0, 100) == 0
        assert clamp(-1000, -50, 50) == -50

    @pytest.mark.unit
    def test_clamp_above_max(self):
        """Value above max should return max."""
        assert clamp(150, 0, 100) == 100
        assert clamp(101, 0, 100) == 100
        assert clamp(1000, -50, 50) == 50

    @pytest.mark.unit
    def test_clamp_at_boundaries(self):
        """Values exactly at boundaries should be unchanged."""
        assert clamp(0, 0, 100) == 0
        assert clamp(100, 0, 100) == 100
        assert clamp(-50, -50, 50) == -50
        assert clamp(50, -50, 50) == 50

    @pytest.mark.unit
    def test_clamp_with_floats(self):
        """Clamp should work with float values."""
        assert clamp(0.5, 0, 1) == 0.5
        assert clamp(-0.1, 0, 1) == 0
        assert clamp(1.5, 0, 1) == 1

    @pytest.mark.unit
    def test_clamp_negative_range(self):
        """Clamp should work with negative ranges."""
        assert clamp(-25, -100, -10) == -25
        assert clamp(0, -100, -10) == -10
        assert clamp(-200, -100, -10) == -100


class TestExpToNextLevel:
    """Tests for the exp_to_next_level() function."""

    @pytest.mark.unit
    def test_level_1_exp(self):
        """Level 1 requires 100 EXP."""
        assert exp_to_next_level(1) == 100

    @pytest.mark.unit
    def test_level_5_exp(self):
        """Level 5 requires 500 EXP."""
        assert exp_to_next_level(5) == 500

    @pytest.mark.unit
    def test_level_10_exp(self):
        """Level 10 requires 1000 EXP."""
        assert exp_to_next_level(10) == 1000

    @pytest.mark.unit
    def test_level_zero_treated_as_one(self):
        """Level 0 or below should be treated as level 1."""
        assert exp_to_next_level(0) == 100
        assert exp_to_next_level(-1) == 100
        assert exp_to_next_level(-100) == 100

    @pytest.mark.unit
    def test_large_level(self):
        """Large levels should scale correctly."""
        assert exp_to_next_level(100) == 10000
        assert exp_to_next_level(50) == 5000


class TestIsChild:
    """Tests for the is_child() function."""

    @pytest.mark.unit
    def test_age_16_is_child(self):
        """Age 16 should be considered a child."""
        v = {"age": 16}
        assert is_child(v) is True

    @pytest.mark.unit
    def test_age_17_is_adult(self):
        """Age 17 should be considered an adult."""
        v = {"age": 17}
        assert is_child(v) is False

    @pytest.mark.unit
    def test_age_0_is_child(self):
        """Age 0 (newborn) should be a child."""
        v = {"age": 0}
        assert is_child(v) is True

    @pytest.mark.unit
    def test_missing_age_is_child(self):
        """Missing age field should default to 0 (child)."""
        v = {}
        assert is_child(v) is True

    @pytest.mark.unit
    def test_none_age_is_child(self):
        """None age should default to 0 (child)."""
        v = {"age": None}
        assert is_child(v) is True

    @pytest.mark.unit
    def test_adult_ages(self):
        """Various adult ages should not be children."""
        assert is_child({"age": 18}) is False
        assert is_child({"age": 25}) is False
        assert is_child({"age": 50}) is False
        assert is_child({"age": 100}) is False


class TestPick:
    """Tests for the pick() function."""

    @pytest.mark.unit
    def test_pick_from_list(self):
        """pick() should return an element from the list."""
        items = ["a", "b", "c"]
        result = pick(items)
        assert result in items

    @pytest.mark.unit
    def test_pick_single_element(self):
        """pick() with single element should return that element."""
        items = ["only"]
        assert pick(items) == "only"

    @pytest.mark.unit
    def test_pick_empty_raises(self):
        """pick() with empty sequence should raise ValueError."""
        with pytest.raises(ValueError, match="empty sequence"):
            pick([])

    @pytest.mark.unit
    def test_pick_from_tuple(self):
        """pick() should work with tuples."""
        items = (1, 2, 3)
        result = pick(items)
        assert result in items

    @pytest.mark.unit
    def test_pick_deterministic_with_seed(self, seeded_random):
        """pick() should be deterministic when random is seeded."""
        seeded_random(42)
        items = ["a", "b", "c", "d", "e"]
        result1 = pick(items)

        seeded_random(42)
        result2 = pick(items)

        assert result1 == result2


class TestRandInt:
    """Tests for the rand_int() function."""

    @pytest.mark.unit
    def test_rand_int_in_range(self):
        """rand_int should return values in the inclusive range."""
        for _ in range(100):
            result = rand_int(1, 10)
            assert 1 <= result <= 10

    @pytest.mark.unit
    def test_rand_int_same_bounds(self):
        """rand_int with same bounds should return that value."""
        assert rand_int(5, 5) == 5

    @pytest.mark.unit
    def test_rand_int_deterministic_with_seed(self, seeded_random):
        """rand_int should be deterministic when random is seeded."""
        seeded_random(42)
        result1 = rand_int(1, 100)

        seeded_random(42)
        result2 = rand_int(1, 100)

        assert result1 == result2


class TestPickWeighted:
    """Tests for the pick_weighted() function."""

    @pytest.mark.unit
    def test_pick_weighted_returns_key(self):
        """pick_weighted should return a key from the weights dict."""
        weights = {"a": 1, "b": 2, "c": 3}
        result = pick_weighted(weights)
        assert result in weights

    @pytest.mark.unit
    def test_pick_weighted_single_option(self):
        """pick_weighted with single option should return that option."""
        weights = {"only": 10}
        assert pick_weighted(weights) == "only"

    @pytest.mark.unit
    def test_pick_weighted_empty_raises(self):
        """pick_weighted with empty dict should raise ValueError."""
        with pytest.raises(ValueError, match="empty dict"):
            pick_weighted({})

    @pytest.mark.unit
    def test_pick_weighted_all_zero_weights(self):
        """pick_weighted with all zero weights should return first key."""
        weights = {"a": 0, "b": 0, "c": 0}
        result = pick_weighted(weights)
        # Should return first key as fallback
        assert result in weights

    @pytest.mark.unit
    def test_pick_weighted_negative_weights_treated_as_zero(self):
        """Negative weights should be treated as zero."""
        weights = {"a": -10, "b": 5}
        # With "a" having effective weight 0, "b" should always be picked
        # Run multiple times to increase confidence
        for _ in range(10):
            result = pick_weighted(weights)
            assert result == "b"

    @pytest.mark.unit
    def test_pick_weighted_deterministic_with_seed(self, seeded_random):
        """pick_weighted should be deterministic when random is seeded."""
        weights = {"a": 1, "b": 2, "c": 3, "d": 4}

        seeded_random(42)
        result1 = pick_weighted(weights)

        seeded_random(42)
        result2 = pick_weighted(weights)

        assert result1 == result2

    @pytest.mark.unit
    def test_pick_weighted_respects_distribution(self, seeded_random):
        """Higher weights should be picked more often (statistical test)."""
        seeded_random(12345)
        weights = {"rare": 1, "common": 99}

        counts = {"rare": 0, "common": 0}
        for _ in range(1000):
            result = pick_weighted(weights)
            counts[result] += 1

        # "common" should be picked much more often
        assert counts["common"] > counts["rare"] * 5
