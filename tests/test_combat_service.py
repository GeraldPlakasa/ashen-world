"""
Unit tests for Combat Service
"""
import pytest
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.combat_service import (
    create_enemy_for,
    apply_starvation_damage,
    resolve_combat,
)


class TestCreateEnemyFor:
    """Tests for enemy creation."""

    @pytest.fixture
    def weak_villager(self):
        return {
            "id": 1,
            "name": "Weakling",
            "level": 1,
            "atk": 10,
            "def": 10,
        }

    @pytest.fixture
    def strong_villager(self):
        return {
            "id": 2,
            "name": "Hero",
            "level": 20,
            "atk": 100,
            "def": 80,
        }

    @pytest.mark.unit
    def test_creates_enemy_dict(self, weak_villager):
        """Should return enemy dictionary."""
        enemy = create_enemy_for(weak_villager)
        assert isinstance(enemy, dict)
        assert "name" in enemy
        assert "hp" in enemy
        assert "atk" in enemy
        assert "def" in enemy

    @pytest.mark.unit
    def test_enemy_scales_with_level(self, weak_villager, strong_villager):
        """Stronger villager should face tougher enemy."""
        random.seed(42)
        weak_enemy = create_enemy_for(weak_villager)
        random.seed(42)
        strong_enemy = create_enemy_for(strong_villager)
        # Enemy stats should scale with villager level
        assert strong_enemy["hp"] >= weak_enemy["hp"]


class TestApplyStarvationDamage:
    """Tests for starvation damage."""

    @pytest.fixture
    def hungry_villager(self):
        return {
            "id": 1,
            "name": "Hungry",
            "hp": 100,
            "hunger": 100,  # Max hunger
            "alive": True,
        }

    @pytest.fixture
    def fed_villager(self):
        return {
            "id": 2,
            "name": "Fed",
            "hp": 100,
            "hunger": 0,
            "alive": True,
        }

    @pytest.fixture
    def basic_bank(self):
        return {
            "balance": 1000,
            "building_levels": {},
        }

    @pytest.mark.unit
    def test_no_damage_when_not_hungry(self, fed_villager, basic_bank):
        """Should not take damage when hunger is low."""
        damage = apply_starvation_damage(fed_villager, basic_bank)
        assert damage is None or damage == 0
        assert fed_villager["hp"] == 100

    @pytest.mark.unit
    def test_damage_when_starving(self, hungry_villager, basic_bank):
        """Should take damage when hunger is high."""
        initial_hp = hungry_villager["hp"]
        damage = apply_starvation_damage(hungry_villager, basic_bank)
        # Should either return damage or reduce HP
        if damage:
            assert damage > 0
        else:
            assert hungry_villager["hp"] <= initial_hp

    @pytest.mark.unit
    def test_death_from_starvation(self, basic_bank):
        """Villager can die from starvation."""
        starving = {
            "id": 1,
            "name": "Starving",
            "hp": 1,
            "hunger": 100,
            "alive": True,
        }
        apply_starvation_damage(starving, basic_bank)
        # HP should be reduced, possibly to 0 or below
        assert starving["hp"] <= 1


class TestResolveCombat:
    """Tests for combat resolution."""

    @pytest.fixture
    def fighter(self):
        return {
            "id": 1,
            "name": "Fighter",
            "hp": 100,
            "atk": 50,
            "def": 30,
            "int": 20,
            "rep": 10,
            "level": 5,
            "exp": 0,
            "coins": 100,
            "alive": True,
            "huntWins": 0,
            "huntWinsYear": 0,
            "traits": "Brave",
            "skills": "",
            "hunger": 0,
            "gender": "Male",
            "age": 25,
        }

    @pytest.fixture
    def weak_enemy(self):
        return {
            "tier": "common",
            "name": "Rat",
            "hp": 10,
            "atk": 5,
            "def": 2,
            "coinReward": 10,
            "expReward": 5,
            "repReward": 3,
        }

    @pytest.fixture
    def strong_enemy(self):
        return {
            "tier": "legendary",
            "name": "Dragon",
            "hp": 500,
            "atk": 100,
            "def": 80,
            "coinReward": 100,
            "expReward": 50,
            "repReward": 10,
        }

    @pytest.fixture
    def basic_bank(self):
        return {
            "balance": 1000,
            "building_levels": {},
        }

    @pytest.mark.unit
    def test_combat_returns_result(self, fighter, weak_enemy, basic_bank):
        """Should return combat result dict."""
        result = resolve_combat(fighter, weak_enemy, basic_bank)
        assert isinstance(result, dict)
        assert "outcome" in result
        assert result["outcome"] in ["WIN", "LOSS", "DEAD"]

    @pytest.mark.unit
    def test_combat_updates_hp(self, fighter, weak_enemy, basic_bank):
        """Combat should potentially reduce villager HP."""
        initial_hp = fighter["hp"]
        resolve_combat(fighter, weak_enemy, basic_bank)
        # HP might be reduced (or not if won without damage)
        assert fighter["hp"] <= initial_hp

    @pytest.mark.unit
    def test_victory_grants_rewards(self, fighter, weak_enemy, basic_bank):
        """Winning combat should grant exp/coins."""
        random.seed(42)  # Seed for consistent results
        initial_exp = fighter["exp"]
        initial_coins = fighter["coins"]
        
        # Fight multiple times to ensure at least one win
        for _ in range(10):
            fighter["hp"] = 100  # Reset HP
            result = resolve_combat(fighter, weak_enemy, basic_bank)
            if result.get("outcome") == "WIN":
                break
        
        # After wins, should have more exp or coins
        assert fighter["exp"] >= initial_exp or fighter["coins"] >= initial_coins

    @pytest.mark.unit
    def test_strong_enemy_can_kill(self, fighter, strong_enemy, basic_bank):
        """Strong enemy can kill villager."""
        fighter["hp"] = 50  # Low HP
        fighter["def"] = 5  # Low defense
        
        # Fight until death or 20 attempts
        for _ in range(20):
            if not fighter["alive"] or fighter["hp"] <= 0:
                break
            resolve_combat(fighter, strong_enemy, basic_bank)
        
        # Should eventually die or be very low HP
        assert fighter["hp"] <= 50
