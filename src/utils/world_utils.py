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


# ---------------------------------------------------------------------------
#  Death cause classification (for reign-card breakdowns)
# ---------------------------------------------------------------------------

# Bucket slugs surfaced in the UI. "other" is the catch-all for unmatched
# strings — anything new we add to the sim will land here until classified.
DEATH_CAUSE_BUCKETS = ("judicial", "disease", "combat", "starvation", "age", "other")


def classify_death_cause(last_action: str | None) -> str:
    """Map a villager's `last_action` string to one of DEATH_CAUSE_BUCKETS.

    Order is load-bearing: judicial verdicts can co-occur with "died after:"
    prefixes from the world-service safety net, so they're matched first.
    """
    s = (last_action or "").lower()
    if not s:
        return "other"
    if "exiled" in s or "executed" in s:
        return "judicial"
    if "died of " in s or "succumbed to " in s:
        return "disease"
    if "starv" in s:
        return "starvation"
    if "peacefully" in s:
        return "age"
    # Combat covers hunt deaths, sparring/training accidents, and the
    # "won vs ... died from wounds" tail (which doesn't always contain
    # the word "hunt"). Checked after the more specific phrases above so
    # a peaceful death never gets mis-bucketed by a stray "hunt" in
    # inheritance text.
    if ("died from wounds" in s
            or "dead (hunt" in s
            or "dead (won " in s
            or "spar" in s
            or "training accident" in s
            or "sparring accident" in s):
        return "combat"
    return "other"


def compute_death_buckets_by_year(
    characters: list[Villager],
    days_per_year: int = DAYS_PER_YEAR,
) -> dict[int, dict[str, int]]:
    """For each year present in the input, count dead villagers by cause.

    Uses `death_day` to derive the year (1-indexed, matching world_repo's
    compute_year_and_day). Only the villagers table is consulted — dead
    villagers older than MAX_DEAD_YEARS have been pruned to the graveyard
    (which doesn't store last_action), so old years come back empty and the
    caller should fall back to the persisted exile/execution counters.
    """
    buckets: dict[int, dict[str, int]] = {}
    if not characters or days_per_year <= 0:
        return buckets
    for v in characters:
        if v.get("alive", True):
            continue
        try:
            dday = int(v.get("death_day", 0) or 0)
        except (TypeError, ValueError):
            continue
        if dday <= 0:
            continue
        year = (dday - 1) // days_per_year + 1
        cause = classify_death_cause(v.get("last_action"))
        row = buckets.setdefault(year, {b: 0 for b in DEATH_CAUSE_BUCKETS})
        row[cause] = row.get(cause, 0) + 1
    return buckets
