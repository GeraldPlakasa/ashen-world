import random

# ---------------------------------------------------------------------------
#  Generic helpers
# ---------------------------------------------------------------------------

def pick(seq):
    """Return a random element from a non-empty sequence."""
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

    If all weights are non-positive, returns the first key.
    """
    total = sum(max(w, 0.0) for w in weights.values())
    if total <= 0:
        return next(iter(weights.keys()))

    r = random.random() * total
    acc = 0.0

    for k, w in weights.items():
        w = max(w, 0.0)
        acc += w
        if r <= acc:
            return k

    # Fallback: should not normally reach here
    return next(iter(weights.keys()))

def exp_to_next_level(level: int) -> int:
    """Simple EXP curve: each level needs 100 * current_level EXP."""
    return 100 * level

def is_child(v: dict) -> bool:
    return int(v.get("age", 0) or 0) <= 16