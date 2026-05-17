"""Crime & Justice service.

Villagers commit crimes via the `steal` / `assault` / `murder` actions
(see action_service). When a Guard is on patrol or alive guards are present,
crimes can be witnessed and recorded as pending cases on the bank. Once per
day a `crime_trial_phase` runs: if there is a sitting King and any pending
cases, the King issues verdicts (fine / exile / execution) modulated by his
traits and crime severity. Outcomes are persisted on the criminal's
`crime_record` field, applied to game state (treasury / alive flag), and
narrated via the chronicle service.

The phase is best-effort — exceptions are swallowed so a broken verdict
never halts the daily tick.
"""
from __future__ import annotations

import json
import random
from typing import Any

from config import (
    CRIME_SEVERITY,
    CRIME_BASE_WITNESS_CHANCE,
    CRIME_WITNESS_PER_GUARD,
    CRIME_WITNESS_PER_PATROLLER,
    CRIME_FINE_AMOUNT,
    GUARD_JOBS,
)
from src.models.villager import Villager
from src.models.bank import Bank
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _year_for(day: int) -> int:
    """Map total_day -> year (1-indexed). Best-effort: silently returns 1 on
    any failure so stat bumps never break the sim loop."""
    try:
        from src.repositories.world_repo import compute_year_and_day
        year, _ = compute_year_and_day(int(day or 1))
        return int(year)
    except Exception:
        return 1


def _bump_stats(day: int, **kwargs) -> None:
    """Forward to stats_repo.bump_yearly_justice. Swallows errors."""
    try:
        from src.repositories.stats_repo import bump_yearly_justice
        bump_yearly_justice(_year_for(day), **kwargs)
    except Exception as exc:
        logger.warning("Justice stat bump failed: %s", exc)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _find_king(characters: list[Villager]) -> Villager | None:
    for v in characters:
        if v.get("alive", True) and v.get("job") == "King":
            return v
    return None


def _alive_guards(characters: list[Villager]) -> list[Villager]:
    return [v for v in characters if v.get("alive", True) and v.get("job") in GUARD_JOBS]


def _patrollers_today(characters: list[Villager]) -> list[Villager]:
    """Guards who chose `patrol` this tick (their last_action begins with 'patrol')."""
    out = []
    for v in characters:
        if not v.get("alive", True) or v.get("job") not in GUARD_JOBS:
            continue
        last = (v.get("last_action") or "").strip().lower()
        if last.startswith("patrol"):
            out.append(v)
    return out


def _load_crime_record(v: Villager) -> list[dict]:
    raw = v.get("crime_record") or "[]"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        data = []
    return data if isinstance(data, list) else []


def _store_crime_record(v: Villager, record: list[dict]) -> None:
    v["crime_record"] = json.dumps(record)


def _by_id(characters: list[Villager], target_id: int) -> Villager | None:
    if not target_id:
        return None
    for v in characters:
        if int(v.get("id", 0) or 0) == int(target_id):
            return v
    return None


def _trait_set(v: Villager) -> set[str]:
    raw = v.get("traits", "") or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


# ---------------------------------------------------------------------------
#  Witness + record (called from action_service when a crime is committed)
# ---------------------------------------------------------------------------

def witness_chance(crime_type: str, characters: list[Villager]) -> float:
    """Probability that a freshly committed crime is witnessed today."""
    base = CRIME_BASE_WITNESS_CHANCE.get(crime_type, 0.10)
    guard_count = len(_alive_guards(characters))
    patroller_count = len(_patrollers_today(characters))
    chance = base + (CRIME_WITNESS_PER_GUARD * guard_count) + (CRIME_WITNESS_PER_PATROLLER * patroller_count)
    return max(0.0, min(0.95, chance))


def record_pending_crime(
    bank: Bank,
    criminal: Villager,
    victim: Villager | None,
    crime_type: str,
    current_day: int,
    witness: Villager | None = None,
) -> None:
    """Append a case to bank['pending_crimes'] and stamp criminal['crime_record']."""
    if not isinstance(bank, dict):
        return
    cases = bank.get("pending_crimes")
    if not isinstance(cases, list):
        cases = []
        bank["pending_crimes"] = cases

    cid = int(criminal.get("id", 0) or 0)
    vid = int(victim.get("id", 0) or 0) if victim else 0
    wid = int(witness.get("id", 0) or 0) if witness else 0

    cases.append({
        "day": int(current_day or 0),
        "criminal_id": cid,
        "victim_id": vid,
        "crime_type": crime_type,
        "witness_id": wid,
    })

    record = _load_crime_record(criminal)
    record.append({
        "day": int(current_day or 0),
        "type": crime_type,
        "victim_id": vid,
        "verdict": None,
        "verdict_day": None,
    })
    _store_crime_record(criminal, record)


def maybe_witness_and_record(
    bank: Bank,
    criminal: Villager,
    victim: Villager | None,
    crime_type: str,
    characters: list[Villager],
    current_day: int,
) -> bool:
    """Roll witness chance; if hit, register the crime as a pending case.

    Returns True if the crime was recorded.
    """
    if not characters or crime_type not in CRIME_SEVERITY:
        return False
    chance = witness_chance(crime_type, characters)
    if random.random() >= chance:
        return False

    # Pick a likely witness: a patroller first, then any alive guard, else any bystander.
    guards = _patrollers_today(characters) or _alive_guards(characters)
    witness: Villager | None = None
    if guards:
        witness = random.choice(guards)
    else:
        bystanders = [
            o for o in characters
            if o.get("alive", True)
            and o.get("id") not in (criminal.get("id"), victim.get("id") if victim else 0)
        ]
        if bystanders:
            witness = random.choice(bystanders)

    record_pending_crime(bank, criminal, victim, crime_type, current_day, witness)
    _bump_stats(current_day, crimes=1)

    # Chronicle hook (best-effort)
    try:
        from src.services.chronicle_service import record_crime
        record_crime(criminal, victim, crime_type, witness, current_day)
    except Exception as exc:
        logger.warning("Chronicle crime hook failed: %s", exc)

    return True


# ---------------------------------------------------------------------------
#  Verdict logic
# ---------------------------------------------------------------------------

def verdict_for_king(king: Villager, crime_type: str, prior_offenses: int = 0) -> str:
    """Pick a verdict for a single case based on King's traits, severity, and
    the defendant's prior record.

    Verdict options: 'fine', 'exile', 'execution'.

    Balance philosophy:
      - First-offense theft: nearly always a fine — village is forgiving.
      - Repeat offenders: escalation per prior conviction (toward exile, then
        execution at 3+ priors for serious crimes).
      - Exile is the harshest sentence the village should reach for casually;
        execution should feel rare and reserved for murder / recidivism.
    """
    severity = CRIME_SEVERITY.get(crime_type, 1)
    traits = _trait_set(king)

    # Severity-driven base weights — strongly biased toward fines for low crimes.
    if severity >= 4:        # murder
        weights = {"fine": 0.15, "exile": 0.50, "execution": 0.35}
    elif severity >= 2:      # assault
        weights = {"fine": 0.60, "exile": 0.30, "execution": 0.10}
    else:                     # theft (and lower)
        weights = {"fine": 0.88, "exile": 0.10, "execution": 0.02}

    # Recidivism: each prior offense shifts mass from fine toward exile, and
    # from exile toward execution at the highest counts. Hard cap at 4.
    priors = max(0, min(4, int(prior_offenses or 0)))
    if priors >= 1:
        shift = 0.12 * priors
        # Move from fine -> exile
        take = min(weights["fine"] - 0.05, shift)
        weights["fine"] -= take
        weights["exile"] += take
        # At 3+ priors, also bleed exile -> execution
        if priors >= 3:
            extra = 0.10 * (priors - 2)
            take2 = min(weights["exile"] - 0.05, extra)
            weights["exile"] -= take2
            weights["execution"] += take2

    # Trait modifiers — milder than before so a single trait doesn't dominate.
    if "Empathic" in traits or "Generous" in traits:
        weights["fine"] += 0.15
        weights["exile"] = max(0.02, weights["exile"] - 0.08)
        weights["execution"] = max(0.01, weights["execution"] - 0.07)
    if "Strict" in traits:
        # Strict prefers a strong but measured hand: more exile, modest execution.
        weights["fine"] = max(0.05, weights["fine"] - 0.10)
        weights["exile"] += 0.07
        weights["execution"] += 0.03
    if "Greedy" in traits:
        # Greedy king prefers fines (treasury fills up).
        weights["fine"] += 0.20
        weights["exile"] = max(0.02, weights["exile"] - 0.10)
        weights["execution"] = max(0.01, weights["execution"] - 0.10)
    if "Cruel" in traits or "Reckless" in traits or "Hot-headed" in traits:
        weights["execution"] += 0.10
        weights["fine"] = max(0.02, weights["fine"] - 0.07)
    if "Wise" in traits or "Patient" in traits:
        # Measured: slightly more lenient overall — fines preferred over exile.
        weights["fine"] += 0.08
        weights["execution"] = max(0.01, weights["execution"] - 0.05)
    if "Cautious" in traits:
        weights["fine"] += 0.10
        weights["execution"] = max(0.01, weights["execution"] - 0.08)
    if "Loyal" in traits:
        # Steady, balanced — slight tilt away from execution.
        weights["execution"] = max(0.01, weights["execution"] - 0.04)

    # Normalize and roll
    total = sum(max(0.0, w) for w in weights.values())
    if total <= 0:
        return "fine"
    keys = list(weights.keys())
    probs = [max(0.0, weights[k]) / total for k in keys]
    return random.choices(keys, probs, k=1)[0]


def _count_prior_offenses(criminal: Villager) -> int:
    """Number of crimes this villager has already been convicted of.
    Excludes the current pending case and 'died_before_trial' entries."""
    record = _load_crime_record(criminal)
    count = 0
    for entry in record:
        verdict = entry.get("verdict")
        if verdict and verdict != "died_before_trial":
            count += 1
    return count


# ---------------------------------------------------------------------------
#  Verdict application
# ---------------------------------------------------------------------------

def apply_verdict(
    criminal: Villager,
    victim: Villager | None,
    crime_type: str,
    verdict: str,
    bank: Bank,
    current_day: int,
) -> dict:
    """Apply the verdict to game state. Returns a dict describing the outcome.

    Mutates: criminal (alive, last_action, rep, coins), bank (balance).
    """
    outcome = {
        "verdict": verdict,
        "crime_type": crime_type,
        "criminal_name": criminal.get("name", "?"),
        "victim_name": victim.get("name") if victim else None,
        "amount_paid": 0,
    }

    if verdict == "fine":
        amount = CRIME_FINE_AMOUNT.get(crime_type, 30)
        paid = min(int(criminal.get("coins", 0) or 0), amount)
        criminal["coins"] = int(criminal.get("coins", 0) or 0) - paid
        if isinstance(bank, dict):
            bank["balance"] = int(bank.get("balance", 0) or 0) + paid
        criminal["rep"] = int(criminal.get("rep", 0) or 0) - 5
        outcome["amount_paid"] = paid
        criminal["last_action"] = (
            f"{(criminal.get('last_action') or '').strip()} | fined {paid} coins for {crime_type}".strip(" |")
        )

    elif verdict == "exile":
        # Exile removes them from the village. Simplest implementation: mark
        # dead with a distinctive cause so chronicle/family-tree treats them
        # as a non-violent exit (they are not killed, but no longer participate).
        criminal["alive"] = False
        criminal["hp"] = 0
        criminal["death_day"] = int(current_day or 0)
        criminal["last_action"] = f"exiled for {crime_type}"
        criminal["rep"] = int(criminal.get("rep", 0) or 0) - 10

    elif verdict == "execution":
        criminal["alive"] = False
        criminal["hp"] = 0
        criminal["death_day"] = int(current_day or 0)
        criminal["last_action"] = f"executed for {crime_type}"
        criminal["rep"] = int(criminal.get("rep", 0) or 0) - 15

    else:
        # Unknown verdict → treat as fine fallback
        return apply_verdict(criminal, victim, crime_type, "fine", bank, current_day)

    # Stamp the latest crime_record entry of this type with the verdict
    record = _load_crime_record(criminal)
    for entry in reversed(record):
        if entry.get("type") == crime_type and not entry.get("verdict"):
            entry["verdict"] = verdict
            entry["verdict_day"] = int(current_day or 0)
            break
    _store_crime_record(criminal, record)

    return outcome


# ---------------------------------------------------------------------------
#  Trial phase entrypoint (called from simulate_one_day)
# ---------------------------------------------------------------------------

def crime_trial_phase(characters: list[Villager], bank: Bank, current_day: int) -> int:
    """If there are pending crimes and a sitting King, judge each case.

    Returns the number of cases resolved this tick. Pending list is cleared
    of every case the King ruled on (even if the criminal or victim has died
    in the meantime — death-by-mob is still a recorded outcome).
    """
    if not isinstance(bank, dict):
        return 0
    cases = bank.get("pending_crimes")
    if not isinstance(cases, list) or not cases:
        return 0

    king = _find_king(characters)
    if king is None:
        # No king → trials can't be held. Cases accumulate until the next
        # election seats one. (This is intentional drama.)
        return 0

    resolved = 0
    leftovers: list[dict] = []

    for case in cases:
        try:
            ctype = str(case.get("crime_type") or "")
            if ctype not in CRIME_SEVERITY:
                continue
            criminal = _by_id(characters, int(case.get("criminal_id", 0) or 0))
            if criminal is None:
                # Criminal vanished from the population (purged from graveyard?). Drop case.
                continue
            if not criminal.get("alive", True):
                # Already dead — no further punishment needed. Stamp record only.
                record = _load_crime_record(criminal)
                for entry in reversed(record):
                    if entry.get("type") == ctype and not entry.get("verdict"):
                        entry["verdict"] = "died_before_trial"
                        entry["verdict_day"] = int(current_day or 0)
                        break
                _store_crime_record(criminal, record)
                resolved += 1
                continue

            victim = _by_id(characters, int(case.get("victim_id", 0) or 0))
            priors = _count_prior_offenses(criminal)
            verdict = verdict_for_king(king, ctype, prior_offenses=priors)
            outcome = apply_verdict(criminal, victim, ctype, verdict, bank, current_day)
            resolved += 1

            # Per-verdict yearly stat bump. Note: `fines` is gold,
            # `fines_count` is the count of fine verdicts — they're separate
            # so the verdict-count chart doesn't get crushed by the gold axis.
            paid = int(outcome.get("amount_paid", 0) or 0)
            _bump_stats(
                current_day,
                trials=1,
                fines=paid if verdict == "fine" else 0,
                fines_count=1 if verdict == "fine" else 0,
                exiles=1 if verdict == "exile" else 0,
                executions=1 if verdict == "execution" else 0,
            )

            try:
                from src.services.chronicle_service import record_trial_verdict
                record_trial_verdict(king, criminal, victim, ctype, verdict, outcome, current_day)
            except Exception as exc:
                logger.warning("Chronicle verdict hook failed: %s", exc)
        except Exception as exc:
            logger.warning("Trial case failed: %s — leaving on docket", exc)
            leftovers.append(case)

    bank["pending_crimes"] = leftovers
    return resolved
