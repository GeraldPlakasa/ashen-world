"""
Unit tests for pure functions in villagers_social.py.
Tests leadership_score, get_traits_set, relationship_label, and related helpers.
"""
import pytest

from src.services.election_service import (
    leadership_score,
    get_traits_set,
)
from src.services.relationship_service import (
    relationship_label,
    get_relationship_score,
    set_relationship_score,
    adjust_relationship,
    _same_family,
    _is_spouse_eligible,
)


class TestGetTraitsSet:
    """Tests for the get_traits_set() function."""

    @pytest.mark.unit
    def test_parse_comma_separated_traits(self):
        """Should parse comma-separated traits into a set."""
        v = {"traits": "Brave, Wise, Loyal"}
        result = get_traits_set(v)
        assert result == {"Brave", "Wise", "Loyal"}

    @pytest.mark.unit
    def test_single_trait(self):
        """Should handle single trait."""
        v = {"traits": "Brave"}
        result = get_traits_set(v)
        assert result == {"Brave"}

    @pytest.mark.unit
    def test_empty_traits(self):
        """Should return empty set for empty traits."""
        v = {"traits": ""}
        result = get_traits_set(v)
        assert result == set()

    @pytest.mark.unit
    def test_missing_traits_key(self):
        """Should return empty set if traits key is missing."""
        v = {}
        result = get_traits_set(v)
        assert result == set()

    @pytest.mark.unit
    def test_none_traits(self):
        """Should return empty set if traits is None."""
        v = {"traits": None}
        result = get_traits_set(v)
        assert result == set()

    @pytest.mark.unit
    def test_whitespace_handling(self):
        """Should strip whitespace from traits."""
        v = {"traits": "  Brave  ,  Wise  ,  Loyal  "}
        result = get_traits_set(v)
        assert result == {"Brave", "Wise", "Loyal"}

    @pytest.mark.unit
    def test_empty_between_commas(self):
        """Should handle empty strings between commas."""
        v = {"traits": "Brave,,Wise,"}
        result = get_traits_set(v)
        assert result == {"Brave", "Wise"}


class TestLeadershipScore:
    """Tests for the leadership_score() function."""

    @pytest.mark.unit
    def test_basic_calculation(self, sample_villager):
        """Basic leadership score from stats."""
        # sample_villager has: int=50, rep=30, level=5, atk=20, def=15
        # Score = 50*1.2 + 30*0.9 + 5*2.0 + 20*0.4 + 15*0.5
        # = 60 + 27 + 10 + 8 + 7.5 = 112.5
        # Age 25 is in prime range (22-55), so +5
        # Traits "Brave, Wise" -> +6 (Brave) + 14 (Wise) = +20
        # Total = 112.5 + 5 + 20 = 137.5

        score = leadership_score(sample_villager)

        assert score == pytest.approx(137.5, rel=0.01)

    @pytest.mark.unit
    def test_dead_villager_penalty(self, sample_villager):
        """Dead villager should have extremely low score."""
        sample_villager["alive"] = False

        score = leadership_score(sample_villager)

        assert score == -1e9

    @pytest.mark.unit
    def test_underage_penalty(self, sample_child):
        """Villager under 18 should have large penalty."""
        # Age 10 -> -1000 penalty
        sample_child["traits"] = ""  # Clear traits for simpler calculation

        score = leadership_score(sample_child)

        assert score < -900  # Should be very negative due to -1000 penalty

    @pytest.mark.unit
    def test_young_adult_penalty(self, sample_villager):
        """Age 18-21 should have small penalty."""
        sample_villager["age"] = 20
        sample_villager["traits"] = ""

        score = leadership_score(sample_villager)
        # Base stats score + age penalty (-12 for 18-21)

        sample_villager["age"] = 25
        prime_score = leadership_score(sample_villager)

        # Young adult should score lower than prime age
        assert score < prime_score

    @pytest.mark.unit
    def test_old_age_penalty(self, sample_villager):
        """Age > 55 should have penalty."""
        sample_villager["age"] = 60
        sample_villager["traits"] = ""

        score = leadership_score(sample_villager)

        sample_villager["age"] = 35
        prime_score = leadership_score(sample_villager)

        # Old age should score lower than prime age
        assert score < prime_score

    @pytest.mark.unit
    def test_dynasty_bonus(self, sample_villager, sample_king):
        """Same family as previous King should get dynasty bonus."""
        sample_villager["family"] = "Testfamily"
        sample_king["family"] = "Testfamily"
        sample_villager["traits"] = ""

        score_with_dynasty = leadership_score(sample_villager, prev_king=sample_king)

        sample_villager["family"] = "DifferentFamily"
        score_without_dynasty = leadership_score(sample_villager, prev_king=sample_king)

        # Dynasty bonus is 1000
        assert score_with_dynasty - score_without_dynasty == 1000

    @pytest.mark.unit
    def test_positive_trait_bonuses(self, sample_villager):
        """Positive traits should increase score."""
        sample_villager["traits"] = ""
        base_score = leadership_score(sample_villager)

        sample_villager["traits"] = "Wise"  # +14
        wise_score = leadership_score(sample_villager)

        sample_villager["traits"] = "Generous"  # +8
        generous_score = leadership_score(sample_villager)

        assert wise_score > base_score
        assert generous_score > base_score
        assert wise_score - base_score == 14
        assert generous_score - base_score == 8

    @pytest.mark.unit
    def test_negative_trait_penalties(self, sample_villager):
        """Negative traits should decrease score."""
        sample_villager["traits"] = ""
        base_score = leadership_score(sample_villager)

        sample_villager["traits"] = "Greedy"  # -10
        greedy_score = leadership_score(sample_villager)

        sample_villager["traits"] = "Deceitful"  # -12
        deceitful_score = leadership_score(sample_villager)

        assert greedy_score < base_score
        assert deceitful_score < base_score
        assert base_score - greedy_score == 10
        assert base_score - deceitful_score == 12


class TestRelationshipLabel:
    """Tests for the relationship_label() function."""

    @pytest.mark.unit
    def test_love_threshold_male_female(self, sample_villager, sample_female_villager):
        """Score >= 80 between Male-Female should be 'love'."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 80)

        label = relationship_label(sample_villager, sample_female_villager)

        assert label == "love"

    @pytest.mark.unit
    def test_love_not_same_gender(self, sample_villager):
        """Score >= 80 between same gender should be 'bestfriend', not 'love'."""
        other_male = sample_villager.copy()
        other_male["id"] = 100
        other_male["gender"] = "Male"

        set_relationship_score(sample_villager, 100, 85)

        label = relationship_label(sample_villager, other_male)

        assert label == "bestfriend"  # Not love for same gender

    @pytest.mark.unit
    def test_bestfriend_threshold(self, sample_villager, sample_female_villager):
        """Score >= 65 (but < 80 for MF) should be 'bestfriend'."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 70)

        label = relationship_label(sample_villager, sample_female_villager)

        assert label == "bestfriend"

    @pytest.mark.unit
    def test_friend_threshold(self, sample_villager, sample_female_villager):
        """Score >= 30 (but < 65) should be 'friend'."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 45)

        label = relationship_label(sample_villager, sample_female_villager)

        assert label == "friend"

    @pytest.mark.unit
    def test_enemy_threshold(self, sample_villager, sample_female_villager):
        """Score <= -60 should be 'enemy'."""
        set_relationship_score(sample_villager, sample_female_villager["id"], -60)

        label = relationship_label(sample_villager, sample_female_villager)

        assert label == "enemy"

    @pytest.mark.unit
    def test_rival_threshold(self, sample_villager, sample_female_villager):
        """Score <= -30 (but > -60) should be 'rival'."""
        set_relationship_score(sample_villager, sample_female_villager["id"], -45)

        label = relationship_label(sample_villager, sample_female_villager)

        assert label == "rival"

    @pytest.mark.unit
    def test_neutral_no_label(self, sample_villager, sample_female_villager):
        """Score between -29 and 29 should return None."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 15)

        label = relationship_label(sample_villager, sample_female_villager)

        assert label is None

    @pytest.mark.unit
    def test_missing_other_id(self, sample_villager):
        """Missing other ID should return None."""
        other = {}

        label = relationship_label(sample_villager, other)

        assert label is None


class TestRelationshipScoreFunctions:
    """Tests for get/set/adjust relationship score functions."""

    @pytest.mark.unit
    def test_get_relationship_score_default_zero(self, sample_villager):
        """Missing relationship should return 0."""
        score = get_relationship_score(sample_villager, 999)
        assert score == 0

    @pytest.mark.unit
    def test_set_and_get_relationship_score(self, sample_villager):
        """Setting and getting relationship score should work."""
        set_relationship_score(sample_villager, 42, 75)

        score = get_relationship_score(sample_villager, 42)

        assert score == 75

    @pytest.mark.unit
    def test_adjust_relationship_positive(self, sample_villager, sample_female_villager):
        """Adjusting relationship positively should increase score."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 50)

        adjust_relationship(sample_villager, sample_female_villager, 10)

        score = get_relationship_score(sample_villager, sample_female_villager["id"])
        assert score == 60

    @pytest.mark.unit
    def test_adjust_relationship_negative(self, sample_villager, sample_female_villager):
        """Adjusting relationship negatively should decrease score."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 50)

        adjust_relationship(sample_villager, sample_female_villager, -20)

        score = get_relationship_score(sample_villager, sample_female_villager["id"])
        assert score == 30

    @pytest.mark.unit
    def test_adjust_relationship_clamped_high(self, sample_villager, sample_female_villager):
        """Relationship score should be clamped at 120."""
        set_relationship_score(sample_villager, sample_female_villager["id"], 110)

        adjust_relationship(sample_villager, sample_female_villager, 50)

        score = get_relationship_score(sample_villager, sample_female_villager["id"])
        assert score == 120

    @pytest.mark.unit
    def test_adjust_relationship_clamped_low(self, sample_villager, sample_female_villager):
        """Relationship score should be clamped at -100."""
        set_relationship_score(sample_villager, sample_female_villager["id"], -80)

        adjust_relationship(sample_villager, sample_female_villager, -50)

        score = get_relationship_score(sample_villager, sample_female_villager["id"])
        assert score == -100


class TestSameFamily:
    """Tests for the _same_family() helper."""

    @pytest.mark.unit
    def test_same_family_name(self):
        """Same family name should return True."""
        a = {"family": "Smith"}
        b = {"family": "Smith"}
        assert _same_family(a, b) is True

    @pytest.mark.unit
    def test_same_family_case_insensitive(self):
        """Family comparison should be case-insensitive."""
        a = {"family": "SMITH"}
        b = {"family": "smith"}
        assert _same_family(a, b) is True

    @pytest.mark.unit
    def test_different_family(self):
        """Different family names should return False."""
        a = {"family": "Smith"}
        b = {"family": "Jones"}
        assert _same_family(a, b) is False

    @pytest.mark.unit
    def test_empty_family(self):
        """Empty family names should return False."""
        a = {"family": ""}
        b = {"family": ""}
        assert _same_family(a, b) is False

    @pytest.mark.unit
    def test_missing_family(self):
        """Missing family key should return False."""
        a = {}
        b = {"family": "Smith"}
        assert _same_family(a, b) is False


class TestIsSpouseEligible:
    """Tests for the _is_spouse_eligible() helper."""

    @pytest.mark.unit
    def test_eligible_couple(self, sample_villager, sample_female_villager):
        """Male and female of appropriate age should be eligible."""
        sample_villager["family"] = "Smith"
        sample_female_villager["family"] = "Jones"

        result = _is_spouse_eligible(sample_villager, sample_female_villager)

        assert result is True

    @pytest.mark.unit
    def test_same_gender_not_eligible(self, sample_villager):
        """Same gender should not be eligible."""
        other_male = sample_villager.copy()
        other_male["id"] = 100
        other_male["family"] = "Jones"

        result = _is_spouse_eligible(sample_villager, other_male)

        assert result is False

    @pytest.mark.unit
    def test_same_family_not_eligible(self, sample_villager, sample_female_villager):
        """Same family should not be eligible."""
        sample_villager["family"] = "Smith"
        sample_female_villager["family"] = "Smith"

        result = _is_spouse_eligible(sample_villager, sample_female_villager)

        assert result is False

    @pytest.mark.unit
    def test_underage_not_eligible(self, sample_villager, sample_female_villager):
        """Under 18 should not be eligible."""
        sample_villager["age"] = 17
        sample_villager["family"] = "Smith"
        sample_female_villager["family"] = "Jones"

        result = _is_spouse_eligible(sample_villager, sample_female_villager)

        assert result is False

    @pytest.mark.unit
    def test_too_old_not_eligible(self, sample_villager, sample_female_villager):
        """Over 60 should not be eligible."""
        sample_villager["age"] = 61
        sample_villager["family"] = "Smith"
        sample_female_villager["family"] = "Jones"

        result = _is_spouse_eligible(sample_villager, sample_female_villager)

        assert result is False

    @pytest.mark.unit
    def test_dead_not_eligible(self, sample_villager, sample_female_villager):
        """Dead villager should not be eligible."""
        sample_villager["alive"] = False
        sample_villager["family"] = "Smith"
        sample_female_villager["family"] = "Jones"

        result = _is_spouse_eligible(sample_villager, sample_female_villager)

        assert result is False

    @pytest.mark.unit
    def test_same_person_not_eligible(self, sample_villager):
        """Same person should not be eligible."""
        result = _is_spouse_eligible(sample_villager, sample_villager)

        assert result is False
