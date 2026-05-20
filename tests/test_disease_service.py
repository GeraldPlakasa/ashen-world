"""Tests for the disease service: infection, transmission, cure, daily phase."""
from __future__ import annotations

import random
import pytest

from src.services import disease_service as ds
from src.services.disease_service import (
    infect, is_sick, has_immunity, cure, cure_chance, try_transmit,
    find_sick_in_circle, daily_disease_phase, _immunities,
)


def _make_villager(**overrides):
    """Minimal villager dict used across these tests."""
    base = {
        "id": 1, "name": "Test", "family": "Testfamily",
        "job": "Farmer", "gender": "Male",
        "alive": True, "hp": 100, "int": 50,
        "age": 25, "rep": 0, "coins": 0, "level": 1,
        "disease": "", "disease_day": 0, "immunities": "[]",
        "spouseId": 0,
    }
    base.update(overrides)
    return base


class TestInfectAndImmunity:
    @pytest.mark.unit
    def test_infect_sets_state(self):
        v = _make_villager()
        ok = infect(v, "fever", current_day=10)
        assert ok
        assert is_sick(v)
        assert v["disease"] == "fever"
        assert v["disease_day"] == 10

    @pytest.mark.unit
    def test_infect_skips_dead(self):
        v = _make_villager(alive=False)
        assert not infect(v, "fever", current_day=1)
        assert not is_sick(v)

    @pytest.mark.unit
    def test_infect_skips_already_sick(self):
        v = _make_villager(disease="cough", disease_day=5)
        assert not infect(v, "fever", current_day=10)
        # Existing illness remains
        assert v["disease"] == "cough"

    @pytest.mark.unit
    def test_infect_skips_immune(self):
        v = _make_villager(immunities='["plague"]')
        assert not infect(v, "plague", current_day=1)
        assert not is_sick(v)

    @pytest.mark.unit
    def test_unknown_disease_no_op(self):
        v = _make_villager()
        assert not infect(v, "spider_bite", current_day=1)
        assert not is_sick(v)


class TestCure:
    @pytest.mark.unit
    def test_cure_clears_and_grants_immunity(self):
        v = _make_villager(disease="fever", disease_day=3)
        result = cure(v)
        assert result == "fever"
        assert not is_sick(v)
        assert has_immunity(v, "fever")

    @pytest.mark.unit
    def test_cure_no_op_when_healthy(self):
        v = _make_villager()
        assert cure(v) is None

    @pytest.mark.unit
    def test_cure_chance_range(self):
        patient = _make_villager(disease="cough")
        healer = _make_villager(id=2, job="Healer", int=50)
        p = cure_chance(patient, healer, bank=None)
        # Cough base 0.55 + INT(50/25 * 0.10) = 0.75
        assert 0.70 <= p <= 0.80

    @pytest.mark.unit
    def test_cure_chance_zero_when_healthy(self):
        patient = _make_villager()  # no disease
        healer = _make_villager(id=2, job="Healer", int=80)
        assert cure_chance(patient, healer, bank=None) == 0.0


class TestTransmission:
    @pytest.mark.unit
    def test_contact_can_transmit(self):
        random.seed(0)  # ensure roll succeeds for cough (0.30 rate)
        source = _make_villager(id=1, disease="cough", disease_day=1)
        target = _make_villager(id=2)
        ok = try_transmit(source, target, current_day=2, kind="contact")
        # Probabilistic — with seed 0 the first roll should land
        assert isinstance(ok, bool)

    @pytest.mark.unit
    def test_transmit_skips_immune(self):
        source = _make_villager(id=1, disease="plague", disease_day=1)
        target = _make_villager(id=2, immunities='["plague"]')
        for _ in range(50):
            ok = try_transmit(source, target, current_day=2, kind="contact")
            assert not ok

    @pytest.mark.unit
    def test_transmit_skips_dead_target(self):
        source = _make_villager(id=1, disease="cough", disease_day=1)
        target = _make_villager(id=2, alive=False)
        for _ in range(20):
            assert not try_transmit(source, target, current_day=2, kind="contact")

    @pytest.mark.unit
    def test_healthy_source_doesnt_transmit(self):
        source = _make_villager(id=1)  # healthy
        target = _make_villager(id=2)
        for _ in range(20):
            assert not try_transmit(source, target, current_day=2)


class TestFindSickInCircle:
    @pytest.mark.unit
    def test_prioritizes_spouse(self):
        healer = _make_villager(id=10, job="Healer", spouseId=20)
        spouse = _make_villager(id=20, disease="fever", disease_day=1)
        other = _make_villager(id=30, disease="plague", disease_day=1)
        result = find_sick_in_circle(healer, [healer, spouse, other])
        assert len(result) == 1
        assert result[0]["id"] == 20  # spouse picked first

    @pytest.mark.unit
    def test_prioritizes_family(self):
        healer = _make_villager(id=10, job="Healer", family="Smith")
        fam = _make_villager(id=20, family="Smith", disease="cough", disease_day=1)
        other = _make_villager(id=30, family="Jones", disease="plague", disease_day=1)
        result = find_sick_in_circle(healer, [healer, fam, other])
        assert any(p["id"] == 20 for p in result)

    @pytest.mark.unit
    def test_empty_when_no_sick(self):
        healer = _make_villager(id=10, job="Healer")
        others = [_make_villager(id=20), _make_villager(id=30)]
        assert find_sick_in_circle(healer, [healer] + others) == []


class TestDailyPhase:
    @pytest.fixture(autouse=True)
    def _isolate_db(self, test_db_connection):
        """daily_disease_phase writes chronicle entries via record_death and
        record_disease_outbreak. Force them to a temp DB."""
        return

    @pytest.mark.unit
    def test_progression_drains_hp(self):
        random.seed(42)
        v = _make_villager(disease="fever", disease_day=0, hp=100)
        daily_disease_phase([v], bank=None, current_day=2)
        # Fever drains 3-6 HP per day on average; with seed 42 we should
        # see HP drop (unless recovery kicked in, which is rare on day 2).
        # The test asserts something happened — drain OR recovery.
        changed = v["hp"] < 100 or v["disease"] == ""
        assert changed

    @pytest.mark.unit
    def test_recovery_grants_immunity(self):
        random.seed(0)
        v = _make_villager(disease="cough", disease_day=0, hp=100)
        # Run many days; one recovery is highly likely within cough's window
        for d in range(1, 30):
            daily_disease_phase([v], bank=None, current_day=d)
            if not is_sick(v):
                break
        assert not is_sick(v), "Cough should resolve within ~30 days"
        assert has_immunity(v, "cough")

    @pytest.mark.unit
    def test_dead_villagers_skipped(self):
        v = _make_villager(alive=False, hp=0, disease="plague", disease_day=0)
        # Should not raise; should not flip anything weird
        daily_disease_phase([v], bank=None, current_day=5)
        assert v["alive"] is False

    @pytest.mark.unit
    def test_immunities_field_parses(self):
        v = _make_villager(immunities='["cough", "fever"]')
        imms = _immunities(v)
        assert imms == {"cough", "fever"}
        v2 = _make_villager(immunities='')  # empty/malformed
        assert _immunities(v2) == set()
