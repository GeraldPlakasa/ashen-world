from __future__ import annotations

import random
from config import CHILD_MAX_AGE
from src.models.villager import Villager

def pick(seq):
    """Return a random element from a non-empty sequence."""
    if not seq:
        raise ValueError("pick() received an empty sequence")
    return random.choice(seq)

def rand_int(a, b):
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

def safe_int(x, default=0):
    """Convert x to int, returning default on failure."""
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return default

def is_child(v: Villager) -> bool:
    """Child if age <= CHILD_MAX_AGE."""
    return int(v.get("age", 0) or 0) <= CHILD_MAX_AGE
