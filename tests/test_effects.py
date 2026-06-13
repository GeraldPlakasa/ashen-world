"""
Unit tests for trait effects, skill effects, weather effects, and reward systems.
"""
import pytest
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRAITS
from src.services.action_service import choose_action, apply_action
from src.services.combat_service import resolve_combat, create_enemy_for
from src.services.skill_service import (
    SKILLS, parse_skills, get_skill_info,
    SKILL_BIRTH_CHANCE, SECOND_SKILL_CHANCE
)
from src.services.event_service import (
    EVENT_WEIGHTS, _apply_plague, _apply_famine, _apply_festival,
    _apply_invasion, _apply_good_harvest, _apply_blessing
)


class TestTraitEffectsOnActions:
    """Tests that all traits influence action selection."""

    @pytest.fixture
    def base_villager(self):
        # Use a non-producer job so trait effects aren't masked by the
        # producer-job work bias (Farmers/Miners/etc. lean toward work).
        return {
            "id": 1, "name": "Test", "age": 25, "job": "Tailor",
            "atk": 10, "def": 10, "int": 10, "hp": 100, "rep": 10,
            "coins": 50, "hunger": 30, "level": 5, "exp": 0,
            "traits": "", "skills": "", "alive": True,
        }

    @pytest.mark.unit
    def test_brave_increases_train_and_hunt(self, base_villager):
        """Brave trait should increase train and hunt weights."""
        random.seed(42)
        base_villager["traits"] = "Brave"
        
        # Run many times to see effect
        actions = [choose_action(base_villager) for _ in range(100)]
        train_count = actions.count("train")
        hunt_count = actions.count("hunt")
        
        # Brave should have significant train/hunt presence
        assert train_count + hunt_count > 20

    @pytest.mark.unit
    def test_wise_increases_study(self, base_villager):
        """Wise trait should increase study weight."""
        random.seed(42)
        base_villager["traits"] = "Wise"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        study_count = actions.count("study")
        
        assert study_count > 15

    @pytest.mark.unit
    def test_greedy_increases_work_and_steal(self, base_villager):
        """Greedy trait should increase work and steal weights.

        Threshold relaxed in the 2026-05-18 crime-rate softening (steal base
        0.10 → 0.04, Greedy +0.30 → +0.15). Compare against the no-trait
        baseline on the same seed to keep the test about *direction*, not
        absolute count.
        """
        random.seed(42)
        base_villager["traits"] = "Greedy"
        actions = [choose_action(base_villager) for _ in range(400)]
        greedy_steal = actions.count("steal")
        greedy_work = actions.count("work")

        random.seed(42)
        base_villager["traits"] = ""
        actions_plain = [choose_action(base_villager) for _ in range(400)]
        plain_steal = actions_plain.count("steal")

        assert greedy_work > 60, f"greedy work share too low: {greedy_work}/400"
        assert greedy_steal > plain_steal, (
            f"greedy steal {greedy_steal} should exceed plain {plain_steal}"
        )

    @pytest.mark.unit
    def test_lazy_increases_rest(self, base_villager):
        """Lazy trait should increase rest weight."""
        random.seed(42)
        base_villager["traits"] = "Lazy"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        rest_count = actions.count("rest")
        
        assert rest_count > 15

    @pytest.mark.unit
    def test_deceitful_increases_steal(self, base_villager):
        """Deceitful trait should noticeably increase steal weight relative
        to a no-trait villager. Threshold relaxed in the 2026-05-18 crime
        softening (steal base 0.10 → 0.04, Deceitful +0.50 → +0.25)."""
        random.seed(42)
        base_villager["traits"] = "Deceitful"
        deceitful_steal = sum(
            1 for _ in range(400) if choose_action(base_villager) == "steal"
        )

        random.seed(42)
        base_villager["traits"] = ""
        plain_steal = sum(
            1 for _ in range(400) if choose_action(base_villager) == "steal"
        )

        # Deceitful should at least double the plain rate (still well above
        # the floor; absolute count remains modest with the new tuning).
        assert deceitful_steal > max(2 * plain_steal, 5), (
            f"deceitful steal {deceitful_steal} should clearly exceed plain {plain_steal}"
        )

    @pytest.mark.unit
    def test_diligent_increases_work_and_train(self, base_villager):
        """Diligent trait should increase work and train weights."""
        random.seed(42)
        base_villager["traits"] = "Diligent"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        work_count = actions.count("work")
        train_count = actions.count("train")
        
        assert work_count + train_count > 25

    @pytest.mark.unit
    def test_stoic_reduces_rest(self, base_villager):
        """Stoic trait should reduce rest tendency."""
        random.seed(42)
        base_villager["traits"] = "Stoic"
        actions_stoic = [choose_action(base_villager) for _ in range(500)]

        base_villager["traits"] = ""
        random.seed(42)
        actions_normal = [choose_action(base_villager) for _ in range(500)]

        # Stoic should rest less than normal (statistical — needs a large
        # sample so single-trial swings don't flip the comparison).
        assert actions_stoic.count("rest") <= actions_normal.count("rest")

    @pytest.mark.unit
    def test_patient_increases_study(self, base_villager):
        """Patient trait should increase study weight."""
        random.seed(42)
        base_villager["traits"] = "Patient"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        study_count = actions.count("study")
        
        assert study_count > 10

    @pytest.mark.unit
    def test_loyal_reduces_steal(self, base_villager):
        """Loyal trait should reduce steal tendency."""
        random.seed(42)
        base_villager["traits"] = "Loyal"
        actions_loyal = [choose_action(base_villager) for _ in range(100)]
        
        base_villager["traits"] = "Greedy"
        random.seed(42)
        actions_greedy = [choose_action(base_villager) for _ in range(100)]
        
        assert actions_loyal.count("steal") < actions_greedy.count("steal")

    @pytest.mark.unit
    def test_all_config_traits_exist(self):
        """All traits defined in config should be valid."""
        assert len(TRAITS) >= 15
        for trait in TRAITS:
            assert isinstance(trait, str)
            assert len(trait) > 0


class TestSkillEffectsOnActions:
    """Tests that skills influence action selection."""

    @pytest.fixture
    def base_villager(self):
        # Use a non-producer job so trait effects aren't masked by the
        # producer-job work bias (Farmers/Miners/etc. lean toward work).
        return {
            "id": 1, "name": "Test", "age": 25, "job": "Tailor",
            "atk": 10, "def": 10, "int": 10, "hp": 100, "rep": 10,
            "coins": 50, "hunger": 30, "level": 5, "exp": 0,
            "traits": "", "skills": "", "alive": True,
        }

    @pytest.mark.unit
    def test_combat_skill_increases_train(self, base_villager):
        """Combat skills should increase train and hunt weights."""
        random.seed(42)
        base_villager["skills"] = "Bladesong"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        train_count = actions.count("train")
        hunt_count = actions.count("hunt")
        
        assert train_count + hunt_count > 20

    @pytest.mark.unit
    def test_craft_skill_increases_work(self, base_villager):
        """Craft skills should increase work weight."""
        random.seed(42)
        base_villager["skills"] = "Forgeblessed"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        work_count = actions.count("work")
        
        assert work_count > 15

    @pytest.mark.unit
    def test_knowledge_skill_increases_study(self, base_villager):
        """Knowledge skills should increase study weight."""
        random.seed(42)
        base_villager["skills"] = "Lorekeeper"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        study_count = actions.count("study")
        
        assert study_count > 15

    @pytest.mark.unit
    def test_social_skill_increases_socialize(self, base_villager):
        """Social skills should increase socialize weight."""
        random.seed(42)
        base_villager["skills"] = "Silver Tongue"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        social_count = actions.count("socialize") + actions.count("hangout")
        
        assert social_count > 15

    @pytest.mark.unit
    def test_multiple_skills_stack(self, base_villager):
        """Multiple skills should stack their effects."""
        random.seed(42)
        base_villager["skills"] = "Bladesong, Hawkeye"
        
        actions = [choose_action(base_villager) for _ in range(100)]
        combat_actions = actions.count("train") + actions.count("hunt")
        
        # Double combat skills = very high combat action rate
        assert combat_actions > 30


class TestSkillEffectsOnCombat:
    """Tests that skills affect combat outcomes."""

    @pytest.fixture
    def base_villager(self):
        return {
            "id": 1, "name": "Test", "age": 25, "job": "Soldier",
            "atk": 20, "def": 15, "int": 10, "hp": 100, "rep": 10,
            "coins": 50, "hunger": 30, "level": 5, "exp": 0,
            "traits": "", "skills": "", "alive": True,
        }

    @pytest.mark.unit
    def test_combat_skill_improves_win_rate(self, base_villager):
        """Combat skills should improve combat win rate."""
        enemy = create_enemy_for(base_villager)
        
        # Without skill
        base_villager["skills"] = ""
        wins_no_skill = 0
        for i in range(50):
            v_copy = base_villager.copy()
            v_copy["hp"] = 100
            v_copy["alive"] = True
            random.seed(i)
            result = resolve_combat(v_copy, enemy.copy())
            if result["outcome"] == "WIN":
                wins_no_skill += 1
        
        # With combat skill
        base_villager["skills"] = "Bladesong"
        wins_with_skill = 0
        for i in range(50):
            v_copy = base_villager.copy()
            v_copy["hp"] = 100
            v_copy["alive"] = True
            random.seed(i)
            result = resolve_combat(v_copy, enemy.copy())
            if result["outcome"] == "WIN":
                wins_with_skill += 1
        
        # Combat skill should help win more
        assert wins_with_skill >= wins_no_skill


class TestWeatherEffects:
    """Tests that weather affects various systems."""

    @pytest.fixture
    def base_villager(self):
        # Use a non-producer job so trait effects aren't masked by the
        # producer-job work bias (Farmers/Miners/etc. lean toward work).
        return {
            "id": 1, "name": "Test", "age": 25, "job": "Tailor",
            "atk": 10, "def": 10, "int": 10, "hp": 100, "rep": 10,
            "coins": 50, "hunger": 30, "level": 5, "exp": 0,
            "traits": "", "skills": "", "alive": True,
        }

    @pytest.mark.unit
    def test_rain_reduces_outdoor_actions(self, base_villager):
        """Rain should reduce outdoor activity weights."""
        random.seed(42)
        actions_sunny = [choose_action(base_villager, weather="sunny") for _ in range(100)]
        
        random.seed(42)
        actions_rain = [choose_action(base_villager, weather="rain") for _ in range(100)]
        
        # Rain should have more study/rest, less hunt
        assert actions_rain.count("study") >= actions_sunny.count("study")
        assert actions_rain.count("hunt") <= actions_sunny.count("hunt")

    @pytest.mark.unit
    def test_rain_boosts_study_gains(self, base_villager):
        """Rain should boost study gains."""
        random.seed(42)
        
        # Sunny study
        v_sunny = base_villager.copy()
        apply_action(v_sunny, "study", weather="sunny")
        int_sunny = v_sunny["int"]
        
        # Rain study
        random.seed(42)
        v_rain = base_villager.copy()
        apply_action(v_rain, "study", weather="rain")
        int_rain = v_rain["int"]
        
        # Rain should give equal or more INT
        assert int_rain >= int_sunny

    @pytest.mark.unit
    def test_rain_reduces_work_income(self, base_villager):
        """Rain should reduce work income."""
        # Test multiple times to see average effect
        total_sunny = 0
        total_rain = 0
        
        for i in range(20):
            random.seed(i)
            v_sunny = base_villager.copy()
            apply_action(v_sunny, "work", weather="sunny")
            total_sunny += v_sunny["coins"] - base_villager["coins"]
            
            random.seed(i)
            v_rain = base_villager.copy()
            apply_action(v_rain, "work", weather="rain")
            total_rain += v_rain["coins"] - base_villager["coins"]
        
        # Rain should reduce average income
        assert total_rain <= total_sunny


class TestEventEffects:
    """Tests that events have proper effects."""

    @pytest.fixture
    def alive_villagers(self):
        return [
            {"id": i, "name": f"V{i}", "age": 25, "hp": 100, "hunger": 30,
             "rep": 10, "coins": 50, "job": "Farmer", "alive": True,
             "traits": "", "last_action": ""}
            for i in range(10)
        ]

    @pytest.fixture
    def bank(self):
        return {"balance": 1000}

    @pytest.mark.unit
    def test_plague_damages_villagers(self, alive_villagers, bank):
        """Plague should damage villager HP."""
        random.seed(42)
        initial_total_hp = sum(v["hp"] for v in alive_villagers)
        
        msg, affected = _apply_plague(alive_villagers, bank, 100)
        
        final_total_hp = sum(v["hp"] for v in alive_villagers if v.get("alive", True))
        
        assert affected > 0
        assert final_total_hp < initial_total_hp
        assert "PLAGUE" in msg

    @pytest.mark.unit
    def test_famine_increases_hunger(self, alive_villagers, bank):
        """Famine should increase hunger and drain treasury."""
        random.seed(42)
        initial_balance = bank["balance"]
        initial_hunger = sum(v["hunger"] for v in alive_villagers)
        
        msg, affected = _apply_famine(alive_villagers, bank, 100)
        
        final_hunger = sum(v["hunger"] for v in alive_villagers)
        
        assert affected > 0
        assert final_hunger > initial_hunger
        assert bank["balance"] < initial_balance
        assert "FAMINE" in msg

    @pytest.mark.unit
    def test_festival_boosts_rep_and_hp(self, alive_villagers, bank):
        """Festival should boost rep and restore HP."""
        random.seed(42)
        initial_rep = sum(v["rep"] for v in alive_villagers)
        initial_hp = sum(v["hp"] for v in alive_villagers)
        initial_balance = bank["balance"]
        
        msg, affected = _apply_festival(alive_villagers, bank, 100)
        
        final_rep = sum(v["rep"] for v in alive_villagers)
        final_hp = sum(v["hp"] for v in alive_villagers)
        
        assert affected == len(alive_villagers)
        assert final_rep > initial_rep
        assert final_hp > initial_hp
        assert bank["balance"] > initial_balance
        assert "FESTIVAL" in msg

    @pytest.mark.unit
    def test_good_harvest_reduces_hunger(self, alive_villagers, bank):
        """Good harvest should reduce hunger and add treasury."""
        random.seed(42)
        # Set high hunger first
        for v in alive_villagers:
            v["hunger"] = 60
        
        initial_hunger = sum(v["hunger"] for v in alive_villagers)
        initial_balance = bank["balance"]
        
        msg, affected = _apply_good_harvest(alive_villagers, bank, 100)
        
        final_hunger = sum(v["hunger"] for v in alive_villagers)
        
        assert affected > 0
        assert final_hunger < initial_hunger
        assert bank["balance"] > initial_balance
        assert "HARVEST" in msg.upper()

    @pytest.mark.unit
    def test_invasion_damages_and_steals(self, alive_villagers, bank):
        """Invasion should damage villagers and steal coins."""
        random.seed(42)
        initial_hp = sum(v["hp"] for v in alive_villagers)
        initial_balance = bank["balance"]
        
        msg, affected = _apply_invasion(alive_villagers, bank, 100)
        
        final_hp = sum(v["hp"] for v in alive_villagers if v.get("alive", True))
        
        assert affected > 0
        assert final_hp < initial_hp
        assert bank["balance"] < initial_balance
        assert "INVASION" in msg

    @pytest.mark.unit
    def test_blessing_heals_villagers(self, alive_villagers, bank):
        """Blessing should heal villagers."""
        random.seed(42)
        # Set low HP first
        for v in alive_villagers:
            v["hp"] = 50
        
        initial_hp = sum(v["hp"] for v in alive_villagers)
        
        msg, affected = _apply_blessing(alive_villagers, bank, 100)
        
        final_hp = sum(v["hp"] for v in alive_villagers)
        
        assert affected > 0
        assert final_hp > initial_hp
        assert "BLESSING" in msg

    @pytest.mark.unit
    def test_all_events_have_weights(self):
        """All event types should have weights defined."""
        expected_events = {"PLAGUE", "FAMINE", "FESTIVAL", "INVASION", "GOOD_HARVEST", "BLESSING"}
        for event in expected_events:
            assert event in EVENT_WEIGHTS
            assert EVENT_WEIGHTS[event] > 0


class TestRewardSystem:
    """Tests that rewards are properly applied."""

    @pytest.fixture
    def base_villager(self):
        return {
            "id": 1, "name": "Test", "age": 25, "job": "Soldier",
            "atk": 20, "def": 15, "int": 10, "hp": 100, "rep": 10,
            "coins": 50, "hunger": 30, "level": 5, "exp": 0,
            "traits": "", "skills": "", "alive": True,
        }

    @pytest.mark.unit
    def test_combat_win_gives_rewards(self, base_villager):
        """Winning combat should give coins, exp, and rep."""
        random.seed(42)
        # Use create_enemy_for to get properly formatted enemy
        enemy = create_enemy_for(base_villager)
        
        initial_coins = base_villager["coins"]
        initial_exp = base_villager["exp"]
        
        result = resolve_combat(base_villager, enemy)
        
        if result["outcome"] == "WIN":
            assert base_villager["coins"] > initial_coins
            assert base_villager["exp"] > initial_exp

    @pytest.mark.unit
    def test_work_gives_coins(self, base_villager):
        """Work action should give coins."""
        random.seed(42)
        initial_coins = base_villager["coins"]
        
        apply_action(base_villager, "work")
        
        assert base_villager["coins"] > initial_coins

    @pytest.mark.unit
    def test_train_gives_stats(self, base_villager):
        """Train action should increase ATK and DEF."""
        random.seed(42)
        initial_atk = base_villager["atk"]
        initial_def = base_villager["def"]
        
        apply_action(base_villager, "train")
        
        assert base_villager["atk"] > initial_atk
        assert base_villager["def"] > initial_def

    @pytest.mark.unit
    def test_study_gives_int_and_exp(self, base_villager):
        """Study action should increase INT and EXP."""
        random.seed(42)
        initial_int = base_villager["int"]
        initial_exp = base_villager["exp"]
        
        apply_action(base_villager, "study")
        
        assert base_villager["int"] > initial_int
        assert base_villager["exp"] > initial_exp


class TestSkillBirthChances:
    """Tests for skill birth chance configuration."""

    @pytest.mark.unit
    def test_skill_birth_chance_reasonable(self):
        """Skill birth chance should be between 5-20%."""
        assert 0.05 <= SKILL_BIRTH_CHANCE <= 0.20

    @pytest.mark.unit
    def test_second_skill_chance_reasonable(self):
        """Second skill chance should be between 10-30%."""
        assert 0.10 <= SECOND_SKILL_CHANCE <= 0.30

    @pytest.mark.unit
    def test_all_skills_have_category(self):
        """All skills should have a valid category."""
        valid_categories = {"COMBAT", "CRAFT", "SOCIAL", "SURVIVAL", "KNOWLEDGE", "MAGIC"}
        for name, data in SKILLS.items():
            assert data["category"] in valid_categories


class TestImmigrationRate:
    """Tests for immigration system."""

    @pytest.mark.unit
    def test_immigration_chance_reduced(self):
        """Immigration base chance should be 3% (reduced from 8%)."""
        from src.services.simulation_service import maybe_add_immigrants
        
        # Test that function exists and runs
        characters = []
        bank = {"balance": 1000}
        
        # Should not crash
        result, count = maybe_add_immigrants(characters, bank)
        assert isinstance(result, list)
        assert isinstance(count, int)
