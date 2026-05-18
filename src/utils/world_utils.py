"""
World utility functions for Ashen World game.

This module provides common utilities used across services:
- Random selection helpers (pick, rand_int, pick_weighted)
- Value clamping
- Experience calculations
- Type conversion helpers
- Age checks
"""
from __future__ import annotations

import random
from config import CHILD_MAX_AGE, DAYS_PER_YEAR, SEASONS, SEASON_MODIFIERS
from src.models.villager import Villager


def pick(seq):
    """Return a random element from a non-empty sequence."""
    if not seq:
        raise ValueError("pick() received an empty sequence")
    return random.choice(seq)


def rand_int(a: int, b: int) -> int:
    """Return a random integer in the inclusive range [a, b]."""
    return random.randint(a, b)


def clamp(val, lo, hi):
    """Clamp val into the range [lo, hi]."""
    return max(lo, min(hi, val))


def pick_weighted(weights: dict) -> str:
    """
    Pick a key based on a weight dictionary: {label -> weight}.
    Non-positive weights are treated as zero.
    """
    if not weights:
        raise ValueError("pick_weighted() received an empty dict")

    total = sum(max(float(w), 0.0) for w in weights.values())
    if total <= 0:
        return next(iter(weights.keys()))

    r = random.random() * total
    acc = 0.0
    for k, w in weights.items():
        acc += max(float(w), 0.0)
        if r <= acc:
            return k

    # Fallback: due to floating point rounding
    return next(iter(weights.keys()))


def exp_to_next_level(level: int) -> int:
    """Simple EXP curve: each level needs 100 * level EXP."""
    level = max(1, int(level))
    return 100 * level


def safe_int(x, default: int = 0) -> int:
    """Convert x to int, returning default on failure."""
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return default


def is_child(v: Villager) -> bool:
    """Child if age <= CHILD_MAX_AGE."""
    return int(v.get("age", 0) or 0) <= CHILD_MAX_AGE


# ---------------------------------------------------------------------------
#  Seasons
# ---------------------------------------------------------------------------

def season_for_day(day_in_year: int) -> str:
    """Map a 0..DAYS_PER_YEAR-1 day index to a season slug.

    Splits the year into four equal-ish quarters. Anything outside the year
    range is wrapped via modulo so callers can pass total_day-derived indices.
    """
    if DAYS_PER_YEAR <= 0:
        return SEASONS[0]
    d = int(day_in_year or 0) % DAYS_PER_YEAR
    quarter = DAYS_PER_YEAR / 4.0
    # idx is 0..3; the final season absorbs any rounding remainder.
    idx = min(int(d / quarter), len(SEASONS) - 1)
    return SEASONS[idx]


def season_for_total_day(total_day: int) -> str:
    """Convenience: derive a season from a 1-based monotonic total_day."""
    td = max(1, int(total_day or 1))
    day_in_year = (td - 1) % DAYS_PER_YEAR
    return season_for_day(day_in_year)


def season_modifier(season: str, key: str, default: float = 1.0) -> float:
    """Look up a per-season multiplier with a safe default."""
    table = SEASON_MODIFIERS.get((season or "").lower())
    if not table:
        return default
    try:
        return float(table.get(key, default))
    except (TypeError, ValueError):
        return default
