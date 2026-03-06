"""
Unit tests for Skill System
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.skill_service import (
    SKILLS,
    SKILL_BIRTH_CHANCE,
    SECOND_SKILL_CHANCE,
    get_skill_info,
    get_skills_by_category,
    get_skills_by_rarity,
    roll_birth_skills,
    parse_skills,
    skills_to_string,
    apply_skill_bonuses,
    get_job_from_skills,
    get_all_categories,
)


class TestSkillDefinitions:
    """Tests for skill definitions."""

    @pytest.mark.unit
    def test_all_skills_have_required_fields(self):
        """All skills should have required fields."""
        required = ["category", "description", "stat_bonus", "job_affinity", "rarity"]
        for name, data in SKILLS.items():
            for field in required:
                assert field in data, f"Skill {name} missing {field}"

    @pytest.mark.unit
    def test_all_skills_have_valid_category(self):
        """All skills should have valid categories."""
        valid = {"COMBAT", "CRAFT", "SOCIAL", "SURVIVAL", "KNOWLEDGE"}
        for name, data in SKILLS.items():
            assert data["category"] in valid, f"Skill {name} has invalid category"

    @pytest.mark.unit
    def test_all_skills_have_valid_rarity(self):
        """All skills should have valid rarity."""
        valid = {"common", "uncommon", "rare"}
        for name, data in SKILLS.items():
            assert data["rarity"] in valid, f"Skill {name} has invalid rarity"

    @pytest.mark.unit
    def test_all_skills_have_stat_bonuses(self):
        """All skills should have at least one stat bonus."""
        for name, data in SKILLS.items():
            assert len(data["stat_bonus"]) > 0, f"Skill {name} has no stat bonuses"

    @pytest.mark.unit
    def test_skill_count_reasonable(self):
        """Should have a reasonable number of skills."""
        assert len(SKILLS) >= 20, "Should have at least 20 skills"
        assert len(SKILLS) <= 50, "Should have at most 50 skills"


class TestSkillLookup:
    """Tests for skill lookup functions."""

    @pytest.mark.unit
    def test_get_skill_info_existing(self):
        """Should return info for existing skill."""
        info = get_skill_info("Bladesong")
        assert info is not None
        assert info["category"] == "COMBAT"

    @pytest.mark.unit
    def test_get_skill_info_nonexistent(self):
        """Should return None for nonexistent skill."""
        info = get_skill_info("NonexistentSkill")
        assert info is None

    @pytest.mark.unit
    def test_get_skills_by_category(self):
        """Should return skills in category."""
        combat = get_skills_by_category("COMBAT")
        assert len(combat) > 0
        assert "Bladesong" in combat

    @pytest.mark.unit
    def test_get_skills_by_rarity(self):
        """Should return skills by rarity."""
        common = get_skills_by_rarity("common")
        rare = get_skills_by_rarity("rare")
        assert len(common) > len(rare), "Should have more common than rare"

    @pytest.mark.unit
    def test_get_all_categories(self):
        """Should return all categories."""
        cats = get_all_categories()
        assert "COMBAT" in cats
        assert "CRAFT" in cats
        assert "SOCIAL" in cats
        assert "SURVIVAL" in cats
        assert "KNOWLEDGE" in cats


class TestSkillParsing:
    """Tests for skill string parsing."""

    @pytest.mark.unit
    def test_parse_skills_string(self):
        """Should parse comma-separated skills."""
        result = parse_skills("Bladesong, Hawkeye")
        assert result == ["Bladesong", "Hawkeye"]

    @pytest.mark.unit
    def test_parse_skills_empty(self):
        """Should return empty list for empty string."""
        assert parse_skills("") == []
        assert parse_skills(None) == []

    @pytest.mark.unit
    def test_parse_skills_single(self):
        """Should parse single skill."""
        result = parse_skills("Bladesong")
        assert result == ["Bladesong"]

    @pytest.mark.unit
    def test_skills_to_string(self):
        """Should convert list to comma-separated string."""
        result = skills_to_string(["Bladesong", "Hawkeye"])
        assert result == "Bladesong, Hawkeye"

    @pytest.mark.unit
    def test_skills_to_string_empty(self):
        """Should return empty string for empty list."""
        assert skills_to_string([]) == ""


class TestSkillBonuses:
    """Tests for skill stat bonuses."""

    @pytest.mark.unit
    def test_apply_skill_bonuses(self):
        """Should apply stat bonuses from skills."""
        villager = {
            "skills": "Bladesong",
            "atk": 10,
            "def": 10,
        }
        apply_skill_bonuses(villager)
        assert villager["atk"] == 15  # +5 from Bladesong

    @pytest.mark.unit
    def test_apply_multiple_skill_bonuses(self):
        """Should apply bonuses from multiple skills."""
        villager = {
            "skills": "Bladesong, Hawkeye",
            "atk": 10,
            "def": 10,
        }
        apply_skill_bonuses(villager)
        assert villager["atk"] == 18  # +5 + +3
        assert villager["def"] == 12  # +2

    @pytest.mark.unit
    def test_apply_no_skills(self):
        """Should not change stats if no skills."""
        villager = {
            "skills": "",
            "atk": 10,
        }
        apply_skill_bonuses(villager)
        assert villager["atk"] == 10


class TestJobFromSkills:
    """Tests for job selection from skills."""

    @pytest.mark.unit
    def test_get_job_from_skills(self):
        """Should suggest job based on skill affinity."""
        jobs = ["Farmer", "Soldier", "Merchant"]
        result = get_job_from_skills(["Bladesong"], jobs)
        assert result == "Soldier"

    @pytest.mark.unit
    def test_get_job_no_matching(self):
        """Should return None if no matching jobs."""
        jobs = ["Farmer", "Merchant"]  # No combat jobs
        result = get_job_from_skills(["Bladesong"], jobs)
        assert result is None

    @pytest.mark.unit
    def test_get_job_empty_skills(self):
        """Should return None for empty skills."""
        result = get_job_from_skills([], ["Soldier", "Farmer"])
        assert result is None


class TestRollBirthSkills:
    """Tests for rolling skills at birth."""

    @pytest.mark.unit
    def test_roll_birth_skills_returns_list(self):
        """Should return a list."""
        import random
        random.seed(42)
        result = roll_birth_skills()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_roll_birth_skills_max_two(self):
        """Should return at most 2 skills."""
        import random
        for seed in range(100):
            random.seed(seed)
            result = roll_birth_skills()
            assert len(result) <= 2

    @pytest.mark.unit
    def test_roll_birth_skills_valid_names(self):
        """Should return valid skill names."""
        import random
        for seed in range(100):
            random.seed(seed)
            result = roll_birth_skills()
            for skill in result:
                assert skill in SKILLS

    @pytest.mark.unit
    def test_roll_birth_skills_no_duplicates(self):
        """Should not return duplicate skills."""
        import random
        for seed in range(100):
            random.seed(seed)
            result = roll_birth_skills()
            assert len(result) == len(set(result))
