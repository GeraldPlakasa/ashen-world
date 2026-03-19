"""
Unit tests for buildings.py - building and tax calculations.
"""
import pytest
import math

from src.services.building_service import (
    get_building_level,
    upgrade_cost,
    repair_cost_for,
    has_building,
    apply_tax_on_income,
    update_tax_policy,
    building_priority_weights,
    _ensure_building_dicts,
)


class TestGetBuildingLevel:
    """Tests for the get_building_level() function."""

    @pytest.mark.unit
    def test_existing_building_returns_level(self, sample_bank_with_buildings):
        """Existing building should return its level."""
        assert get_building_level(sample_bank_with_buildings, "market") == 2
        assert get_building_level(sample_bank_with_buildings, "barracks") == 1
        assert get_building_level(sample_bank_with_buildings, "granary") == 1

    @pytest.mark.unit
    def test_missing_building_returns_zero(self, sample_bank):
        """Missing building should return 0."""
        assert get_building_level(sample_bank, "market") == 0
        assert get_building_level(sample_bank, "nonexistent") == 0

    @pytest.mark.unit
    def test_none_bank_returns_zero(self):
        """None bank should return 0."""
        assert get_building_level(None, "market") == 0

    @pytest.mark.unit
    def test_empty_building_levels_returns_zero(self):
        """Empty building_levels dict should return 0."""
        bank = {"building_levels": {}}
        assert get_building_level(bank, "market") == 0

    @pytest.mark.unit
    def test_null_level_value_returns_zero(self):
        """Null/None level value should return 0."""
        bank = {"building_levels": {"market": None}}
        assert get_building_level(bank, "market") == 0

    @pytest.mark.unit
    def test_string_level_value_converts(self):
        """String level value should be converted to int."""
        bank = {"building_levels": {"market": "2"}}
        assert get_building_level(bank, "market") == 2

    @pytest.mark.unit
    def test_invalid_string_returns_zero(self):
        """Invalid string level value should return 0."""
        bank = {"building_levels": {"market": "invalid"}}
        assert get_building_level(bank, "market") == 0


class TestUpgradeCost:
    """Tests for the upgrade_cost() function."""

    @pytest.mark.unit
    def test_upgrade_cost_level_1_to_2(self, sample_bank):
        """Upgrade from level 1 to 2 should cost 2x base."""
        # Market base cost is 400
        sample_bank["building_levels"] = {"market": 1}
        sample_bank["building_health"] = {"market": 100}
        cost = upgrade_cost("market", sample_bank)
        # Lv2 = 1 + (2-1)*1 = 2x base = 800
        assert cost == 800

    @pytest.mark.unit
    def test_upgrade_cost_level_2_to_3(self, sample_bank):
        """Upgrade from level 2 to 3 should cost 3x base."""
        # Market base cost is 400
        sample_bank["building_levels"] = {"market": 2}
        sample_bank["building_health"] = {"market": 100}
        cost = upgrade_cost("market", sample_bank)
        # Lv3 = 1 + (3-1)*1 = 3x base = 1200
        assert cost == 1200

    @pytest.mark.unit
    def test_upgrade_cost_invalid_building(self, sample_bank):
        """Invalid building key should return -1."""
        cost = upgrade_cost("nonexistent_building", sample_bank)
        assert cost == -1

    @pytest.mark.unit
    def test_upgrade_cost_various_buildings(self, sample_bank):
        """Test upgrade costs for various buildings."""
        # Barracks base cost is 450
        sample_bank["building_levels"] = {"barracks": 1}
        sample_bank["building_health"] = {"barracks": 100}
        cost = upgrade_cost("barracks", sample_bank)
        assert cost == 900  # 2x base


class TestRepairCostFor:
    """Tests for the repair_cost_for() function."""

    @pytest.mark.unit
    def test_repair_cost_full_health(self, sample_bank):
        """Building at full health should have 0 repair cost."""
        sample_bank["building_levels"] = {"market": 1}
        sample_bank["building_health"] = {"market": 100}
        cost = repair_cost_for("market", sample_bank)
        assert cost == 0

    @pytest.mark.unit
    def test_repair_cost_damaged(self, sample_bank):
        """Damaged building should have repair cost based on missing health."""
        # Market base cost is 400
        # Repair formula: missing% * (base_cost * 0.25) / 100
        sample_bank["building_levels"] = {"market": 1}
        sample_bank["building_health"] = {"market": 50}  # 50% missing

        cost = repair_cost_for("market", sample_bank)
        # missing = 50, cost = ceil(50 * (400 * 0.25) / 100) = ceil(50) = 50
        assert cost == 50

    @pytest.mark.unit
    def test_repair_cost_zero_health(self, sample_bank):
        """Building at 0 health should have full repair cost."""
        sample_bank["building_levels"] = {"market": 1}
        sample_bank["building_health"] = {"market": 0}  # 100% missing

        cost = repair_cost_for("market", sample_bank)
        # missing = 100, cost = ceil(100 * (400 * 0.25) / 100) = ceil(100) = 100
        assert cost == 100

    @pytest.mark.unit
    def test_repair_cost_invalid_building(self, sample_bank):
        """Invalid building key should return 0."""
        cost = repair_cost_for("nonexistent", sample_bank)
        assert cost == 0


class TestHasBuilding:
    """Tests for the has_building() function."""

    @pytest.mark.unit
    def test_has_building_exists_and_healthy(self, sample_bank):
        """Building with level >= 1 and health > 0 exists."""
        sample_bank["building_levels"] = {"market": 1}
        sample_bank["building_health"] = {"market": 50}
        assert has_building("market", sample_bank) is True

    @pytest.mark.unit
    def test_has_building_not_built(self, sample_bank):
        """Building with level 0 does not exist."""
        sample_bank["building_levels"] = {"market": 0}
        assert has_building("market", sample_bank) is False

    @pytest.mark.unit
    def test_has_building_collapsed(self, sample_bank):
        """Building with health 0 is collapsed."""
        sample_bank["building_levels"] = {"market": 1}
        sample_bank["building_health"] = {"market": 0}
        assert has_building("market", sample_bank) is False

    @pytest.mark.unit
    def test_has_building_missing_key(self, sample_bank):
        """Missing building key should return False."""
        assert has_building("nonexistent", sample_bank) is False


class TestApplyTaxOnIncome:
    """Tests for the apply_tax_on_income() function."""

    @pytest.mark.unit
    def test_apply_tax_normal(self):
        """Normal tax application."""
        v = {}
        bank = {"tax_rate": 0.10, "balance": 100}

        result = apply_tax_on_income(v, 100, bank)

        assert result["net"] == 90
        assert result["tax"] == 10
        assert bank["balance"] == 110  # 100 + 10 tax

    @pytest.mark.unit
    def test_apply_tax_zero_income(self):
        """Zero income should have no tax."""
        v = {}
        bank = {"tax_rate": 0.10, "balance": 100}

        result = apply_tax_on_income(v, 0, bank)

        assert result["net"] == 0
        assert result["tax"] == 0
        assert bank["balance"] == 100  # unchanged

    @pytest.mark.unit
    def test_apply_tax_negative_income(self):
        """Negative income should have no tax."""
        v = {}
        bank = {"tax_rate": 0.10, "balance": 100}

        result = apply_tax_on_income(v, -50, bank)

        assert result["net"] == -50
        assert result["tax"] == 0
        assert bank["balance"] == 100  # unchanged

    @pytest.mark.unit
    def test_apply_tax_zero_rate(self):
        """Zero tax rate should not deduct anything."""
        v = {}
        bank = {"tax_rate": 0.0, "balance": 100}

        result = apply_tax_on_income(v, 100, bank)

        assert result["net"] == 100
        assert result["tax"] == 0
        assert bank["balance"] == 100  # unchanged

    @pytest.mark.unit
    def test_apply_tax_high_rate(self):
        """High tax rate test."""
        v = {}
        bank = {"tax_rate": 0.35, "balance": 0}

        result = apply_tax_on_income(v, 100, bank)

        assert result["net"] == 65
        assert result["tax"] == 35
        assert bank["balance"] == 35


class TestUpdateTaxPolicy:
    """Tests for the update_tax_policy() function."""

    @pytest.mark.unit
    def test_update_tax_no_king(self, sample_villager, sample_bank):
        """Without a King, tax rate should be base 10%."""
        characters = [sample_villager]  # Not a king

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] == 0.10

    @pytest.mark.unit
    def test_update_tax_greedy_king(self, sample_king, sample_bank):
        """Greedy King should increase tax rate by 8%."""
        sample_king["traits"] = "Greedy"
        characters = [sample_king]

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] == 0.18  # 10% + 8%

    @pytest.mark.unit
    def test_update_tax_generous_king(self, sample_king, sample_bank):
        """Generous King should decrease tax rate by 4%."""
        sample_king["traits"] = "Generous"
        characters = [sample_king]

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] == pytest.approx(0.06, rel=1e-9)  # 10% - 4%

    @pytest.mark.unit
    def test_update_tax_wise_king(self, sample_king, sample_bank):
        """Wise King should decrease tax rate by 2%."""
        sample_king["traits"] = "Wise"
        characters = [sample_king]

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] == 0.08  # 10% - 2%

    @pytest.mark.unit
    def test_update_tax_multiple_traits(self, sample_king, sample_bank):
        """Multiple traits should combine effects."""
        sample_king["traits"] = "Greedy, Ambitious"  # +8% + 3% = +11%
        characters = [sample_king]

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] == 0.21  # 10% + 11%

    @pytest.mark.unit
    def test_update_tax_clamped_high(self, sample_king, sample_bank):
        """Tax rate should be clamped at 35%."""
        sample_king["traits"] = "Greedy, Ambitious, Cautious, Hot-headed"
        characters = [sample_king]

        # Add buildings that increase tax
        sample_bank["building_levels"] = {"tax_office": 3, "treasury": 3}

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] <= 0.35

    @pytest.mark.unit
    def test_update_tax_clamped_low(self, sample_king, sample_bank):
        """Tax rate should be clamped at 0%."""
        sample_king["traits"] = "Generous, Wise, Loyal"  # -4% - 2% - 2% = -8%
        characters = [sample_king]

        bank = update_tax_policy(characters, sample_bank)

        assert bank["tax_rate"] >= 0.0
        assert bank["tax_rate"] == pytest.approx(0.02, rel=1e-9)  # 10% - 8%


class TestBuildingPriorityWeights:
    """Tests for the building_priority_weights() function."""

    @pytest.mark.unit
    def test_no_king_returns_base_weights(self):
        """Without a King, all buildings have base weight 1."""
        weights = building_priority_weights(None)

        # All standard buildings should have weight 1
        assert weights.get("market") == 1.0
        assert weights.get("barracks") == 1.0
        assert weights.get("library") == 1.0

    @pytest.mark.unit
    def test_greedy_king_priorities(self, sample_king):
        """Greedy King should prioritize treasury and market."""
        sample_king["traits"] = "Greedy"

        weights = building_priority_weights(sample_king)

        assert weights["treasury"] > 1.0
        assert weights["market"] > 1.0

    @pytest.mark.unit
    def test_wise_king_priorities(self, sample_king):
        """Wise King should prioritize library and temple."""
        sample_king["traits"] = "Wise"

        weights = building_priority_weights(sample_king)

        assert weights["library"] > 1.0
        assert weights["temple"] > 1.0

    @pytest.mark.unit
    def test_brave_king_priorities(self, sample_king):
        """Brave King should prioritize barracks and walls."""
        sample_king["traits"] = "Brave"

        weights = building_priority_weights(sample_king)

        assert weights["barracks"] > 1.0
        assert weights["walls"] > 1.0


class TestEnsureBuildingDicts:
    """Tests for the _ensure_building_dicts() helper."""

    @pytest.mark.unit
    def test_creates_missing_dicts(self):
        """Should create building_levels and building_health if missing."""
        bank = {}

        levels, health = _ensure_building_dicts(bank)

        assert bank["building_levels"] == {}
        assert bank["building_health"] == {}
        assert levels is bank["building_levels"]
        assert health is bank["building_health"]

    @pytest.mark.unit
    def test_preserves_existing_dicts(self):
        """Should preserve existing dicts."""
        bank = {
            "building_levels": {"market": 2},
            "building_health": {"market": 75},
        }

        levels, health = _ensure_building_dicts(bank)

        assert levels["market"] == 2
        assert health["market"] == 75

    @pytest.mark.unit
    def test_replaces_non_dict_values(self):
        """Should replace non-dict values with empty dicts."""
        bank = {
            "building_levels": "invalid",
            "building_health": None,
        }

        levels, health = _ensure_building_dicts(bank)

        assert levels == {}
        assert health == {}
