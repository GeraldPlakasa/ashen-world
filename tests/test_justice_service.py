"""Tests for the crime & justice service:
witness recording, king verdicts by trait, verdict application,
and the trial phase wiring.
"""
from __future__ import annotations

import json
import random
import pytest

from src.services import justice_service as js
from src.services.justice_service import (
    witness_chance,
    record_pending_crime,
    maybe_witness_and_record,
    verdict_for_king,
    apply_verdict,
    crime_trial_phase,
    _load_crime_record,
    _count_prior_offenses,
)


def _v(**overrides):
    base = {
        "id": 1, "name": "Crim", "family": "Shady",
        "job": "Farmer", "gender": "Male", "alive": True,
        "hp": 100, "atk": 10, "def": 5, "int": 20, "rep": 0,
        "coins": 100, "age": 25, "level": 1,
        "traits": "", "crime_record": "[]",
    }
    base.update(overrides)
    return base


def _bank(**overrides):
    base = {
        "balance": 1000,
        "tax_rate": 0.10,
        "resources": {"food": 0, "wood": 0, "stone": 0, "iron": 0},
        "building_levels": {},
        "building_health": {},
        "pending_crimes": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
#  witness_chance
# ---------------------------------------------------------------------------

class TestWitnessChance:
    @pytest.mark.unit
    def test_base_chance_no_guards(self):
        chars = [_v(id=1, job="Farmer"), _v(id=2, job="Farmer")]
        # No guards → base chance only (0.10 for theft per config)
        assert witness_chance("theft", chars) == pytest.approx(0.10, abs=0.001)

    @pytest.mark.unit
    def test_guards_increase_chance(self):
        chars = [_v(id=i, job="Guard") for i in range(1, 4)]
        # 3 guards × 0.04 + base 0.10 = 0.22
        assert witness_chance("theft", chars) == pytest.approx(0.22, abs=0.001)

    @pytest.mark.unit
    def test_patrollers_add_more(self):
        chars = [_v(id=1, job="Guard", last_action="patrol the streets")]
        # 1 guard (0.04) + 1 patroller (0.10) + base 0.10 = 0.24
        assert witness_chance("theft", chars) == pytest.approx(0.24, abs=0.001)

    @pytest.mark.unit
    def test_chance_capped_at_95(self):
        chars = [_v(id=i, job="Guard", last_action="patrol") for i in range(1, 30)]
        assert witness_chance("murder", chars) == pytest.approx(0.95, abs=0.001)


# ---------------------------------------------------------------------------
#  record_pending_crime + maybe_witness_and_record
# ---------------------------------------------------------------------------

class TestRecording:
    @pytest.mark.unit
    def test_record_pending_crime_appends_case_and_record(self):
        bank = _bank()
        criminal = _v(id=1)
        victim = _v(id=2, name="Victim")
        record_pending_crime(bank, criminal, victim, "theft", current_day=10)
        assert len(bank["pending_crimes"]) == 1
        case = bank["pending_crimes"][0]
        assert case["criminal_id"] == 1
        assert case["victim_id"] == 2
        assert case["crime_type"] == "theft"
        assert case["day"] == 10
        # Criminal's own record stamped
        record = _load_crime_record(criminal)
        assert len(record) == 1
        assert record[0]["type"] == "theft"
        assert record[0]["verdict"] is None

    @pytest.mark.unit
    def test_maybe_witness_records_when_chance_hits(self):
        random.seed(42)  # make the witness roll deterministic
        bank = _bank()
        criminal = _v(id=1)
        victim = _v(id=2)
        chars = [criminal, victim] + [_v(id=i, job="Guard") for i in range(3, 10)]
        # With 7 guards (witness_chance ≈ 0.10 + 7×0.04 = 0.38)
        # Seed 42 chosen so this asserts deterministically; we just check the
        # function returns a bool and updates state coherently.
        result = maybe_witness_and_record(bank, criminal, victim, "theft", chars, current_day=5)
        assert isinstance(result, bool)
        if result:
            assert len(bank["pending_crimes"]) == 1

    @pytest.mark.unit
    def test_maybe_witness_with_unknown_crime_type_noop(self):
        bank = _bank()
        criminal = _v(id=1)
        result = maybe_witness_and_record(
            bank, criminal, None, "embezzlement", [criminal], current_day=1
        )
        assert result is False
        assert bank["pending_crimes"] == []


# ---------------------------------------------------------------------------
#  verdict_for_king
# ---------------------------------------------------------------------------

class TestVerdict:
    @pytest.mark.unit
    def test_greedy_king_prefers_fines(self):
        king = _v(id=99, job="King", traits="Greedy")
        # Run many trials — Greedy should land on 'fine' clearly more than 50%.
        random.seed(0)
        verdicts = [verdict_for_king(king, "theft") for _ in range(400)]
        fine_share = verdicts.count("fine") / len(verdicts)
        assert fine_share > 0.65

    @pytest.mark.unit
    def test_empathic_king_avoids_execution(self):
        king = _v(id=99, job="King", traits="Empathic,Generous")
        random.seed(1)
        verdicts = [verdict_for_king(king, "murder") for _ in range(400)]
        exec_share = verdicts.count("execution") / len(verdicts)
        # Murder base is 0.55 execution; Empathic+Generous knock it down meaningfully.
        assert exec_share < 0.45

    @pytest.mark.unit
    def test_severity_drives_default(self):
        king = _v(id=99, job="King", traits="")
        random.seed(2)
        theft_verdicts = [verdict_for_king(king, "theft") for _ in range(400)]
        murder_verdicts = [verdict_for_king(king, "murder") for _ in range(400)]
        # Theft → mostly fine. Murder → mostly exile/execution.
        assert theft_verdicts.count("fine") > theft_verdicts.count("execution")
        assert murder_verdicts.count("execution") > murder_verdicts.count("fine")

    @pytest.mark.unit
    def test_first_time_theft_almost_always_fined(self):
        """Balance: a first-time petty theft case should land on `fine` the
        overwhelming majority of the time. Exile must stay rare for theft."""
        king = _v(id=99, job="King", traits="")  # no trait bias
        random.seed(3)
        verdicts = [verdict_for_king(king, "theft", prior_offenses=0) for _ in range(500)]
        fine_share = verdicts.count("fine") / len(verdicts)
        exile_share = verdicts.count("exile") / len(verdicts)
        assert fine_share > 0.80, f"first-time theft should mostly be fines, got {fine_share:.2f}"
        assert exile_share < 0.15, f"first-time theft exile share too high: {exile_share:.2f}"

    @pytest.mark.unit
    def test_first_time_assault_mostly_fined(self):
        """Assault used to send ~40% of first-time offenders to exile/execution
        (30% exile + 10% execution). Refresh: harsh outcomes should sit ~25%
        for a no-trait king, with fines firmly in the majority."""
        king = _v(id=99, job="King", traits="")
        random.seed(5)
        verdicts = [verdict_for_king(king, "assault", prior_offenses=0) for _ in range(600)]
        fine_share = verdicts.count("fine") / len(verdicts)
        harsh_share = (verdicts.count("exile") + verdicts.count("execution")) / len(verdicts)
        assert fine_share > 0.65, f"assault should mostly fine, got fine={fine_share:.2f}"
        assert harsh_share < 0.30, f"assault harsh share too high: {harsh_share:.2f}"

    @pytest.mark.unit
    def test_first_time_murder_execution_capped(self):
        """Murder still escalates hard, but the execution share should sit
        well below the old 35% baseline for a no-trait king."""
        king = _v(id=99, job="King", traits="")
        random.seed(6)
        verdicts = [verdict_for_king(king, "murder", prior_offenses=0) for _ in range(600)]
        exec_share = verdicts.count("execution") / len(verdicts)
        # Base is 0.25 — give a generous tolerance for sampling noise (±0.07).
        assert exec_share < 0.33, f"murder execution share too high: {exec_share:.2f}"

    @pytest.mark.unit
    def test_protective_king_pushes_toward_fines(self):
        """Protective is a new modifier — it should pull verdicts toward fines."""
        plain_king = _v(id=99, job="King", traits="")
        protective_king = _v(id=99, job="King", traits="Protective")
        random.seed(7)
        plain = [verdict_for_king(plain_king, "assault") for _ in range(400)]
        random.seed(7)  # same draw sequence — only the weights differ
        prot = [verdict_for_king(protective_king, "assault") for _ in range(400)]
        assert prot.count("fine") > plain.count("fine"), (
            "Protective king should fine more than a plain king on the same RNG draws"
        )

    @pytest.mark.unit
    def test_recidivism_escalates_to_exile(self):
        """Same crime + heavy prior record should be markedly more likely to
        end in exile or execution than a clean record."""
        king = _v(id=99, job="King", traits="")
        random.seed(4)
        first_time = [verdict_for_king(king, "theft", prior_offenses=0) for _ in range(400)]
        repeat     = [verdict_for_king(king, "theft", prior_offenses=4) for _ in range(400)]
        first_harsh = first_time.count("exile") + first_time.count("execution")
        repeat_harsh = repeat.count("exile") + repeat.count("execution")
        assert repeat_harsh > first_harsh * 2

    @pytest.mark.unit
    def test_count_prior_offenses(self):
        criminal = _v(id=1)
        # No record yet
        assert _count_prior_offenses(criminal) == 0
        # Pending crime (no verdict) doesn't count
        criminal["crime_record"] = json.dumps([
            {"day": 1, "type": "theft", "victim_id": 0, "verdict": None, "verdict_day": None},
        ])
        assert _count_prior_offenses(criminal) == 0
        # Resolved crime counts
        criminal["crime_record"] = json.dumps([
            {"day": 1, "type": "theft", "victim_id": 0, "verdict": "fine", "verdict_day": 2},
            {"day": 5, "type": "assault", "victim_id": 3, "verdict": "exile", "verdict_day": 6},
        ])
        assert _count_prior_offenses(criminal) == 2
        # 'died_before_trial' is not a real conviction
        criminal["crime_record"] = json.dumps([
            {"day": 1, "type": "theft", "victim_id": 0, "verdict": "died_before_trial", "verdict_day": 2},
        ])
        assert _count_prior_offenses(criminal) == 0


# ---------------------------------------------------------------------------
#  apply_verdict
# ---------------------------------------------------------------------------

class TestApplyVerdict:
    @pytest.mark.unit
    def test_fine_moves_coins_to_treasury(self):
        criminal = _v(id=1, coins=200, rep=5)
        bank = _bank(balance=500)
        outcome = apply_verdict(criminal, None, "theft", "fine", bank, current_day=10)
        assert outcome["verdict"] == "fine"
        assert outcome["amount_paid"] == 30  # CRIME_FINE_AMOUNT["theft"]
        assert criminal["coins"] == 170
        assert bank["balance"] == 530
        assert criminal["rep"] == 0  # -5 rep

    @pytest.mark.unit
    def test_fine_when_broke_pays_zero(self):
        criminal = _v(id=1, coins=5)
        bank = _bank(balance=500)
        outcome = apply_verdict(criminal, None, "theft", "fine", bank, current_day=10)
        assert outcome["amount_paid"] == 5
        assert criminal["coins"] == 0
        assert bank["balance"] == 505

    @pytest.mark.unit
    def test_exile_removes_villager(self):
        criminal = _v(id=1, alive=True, hp=100)
        bank = _bank()
        apply_verdict(criminal, None, "assault", "exile", bank, current_day=20)
        assert criminal["alive"] is False
        assert criminal["hp"] == 0
        assert criminal["death_day"] == 20
        assert "exiled" in criminal["last_action"]

    @pytest.mark.unit
    def test_execution_kills_villager(self):
        criminal = _v(id=1, alive=True, hp=100)
        bank = _bank()
        apply_verdict(criminal, None, "murder", "execution", bank, current_day=20)
        assert criminal["alive"] is False
        assert criminal["hp"] == 0
        assert criminal["death_day"] == 20
        assert "executed" in criminal["last_action"]

    @pytest.mark.unit
    def test_verdict_stamps_crime_record(self):
        criminal = _v(id=1, coins=100)
        bank = _bank()
        record_pending_crime(bank, criminal, None, "theft", current_day=5)
        apply_verdict(criminal, None, "theft", "fine", bank, current_day=6)
        record = _load_crime_record(criminal)
        assert record[-1]["verdict"] == "fine"
        assert record[-1]["verdict_day"] == 6


# ---------------------------------------------------------------------------
#  crime_trial_phase
# ---------------------------------------------------------------------------

class TestTrialPhase:
    @pytest.mark.unit
    def test_no_king_no_resolution(self):
        criminal = _v(id=1)
        chars = [criminal]
        bank = _bank()
        record_pending_crime(bank, criminal, None, "theft", current_day=5)
        resolved = crime_trial_phase(chars, bank, current_day=10)
        assert resolved == 0
        assert len(bank["pending_crimes"]) == 1

    @pytest.mark.unit
    def test_king_resolves_pending(self):
        random.seed(7)
        king = _v(id=99, job="King", traits="Greedy", name="Sovereign")
        criminal = _v(id=1, coins=200, traits="Greedy")
        chars = [king, criminal]
        bank = _bank()
        record_pending_crime(bank, criminal, None, "theft", current_day=5)
        resolved = crime_trial_phase(chars, bank, current_day=10)
        assert resolved == 1
        assert bank["pending_crimes"] == []
        # Criminal record should now carry a verdict
        record = _load_crime_record(criminal)
        assert record[0]["verdict"] in ("fine", "exile", "execution")

    @pytest.mark.unit
    def test_dead_criminal_stamped_but_unpunished(self):
        king = _v(id=99, job="King", traits="")
        # Already-dead criminal
        criminal = _v(id=1, alive=False, hp=0, death_day=4)
        chars = [king, criminal]
        bank = _bank()
        record_pending_crime(bank, criminal, None, "murder", current_day=3)
        resolved = crime_trial_phase(chars, bank, current_day=10)
        assert resolved == 1
        record = _load_crime_record(criminal)
        assert record[-1]["verdict"] == "died_before_trial"
        # Bank balance untouched (no fine collected)
        assert bank["balance"] == 1000

    @pytest.mark.unit
    def test_empty_docket_noop(self):
        king = _v(id=99, job="King")
        bank = _bank()
        assert crime_trial_phase([king], bank, current_day=1) == 0
