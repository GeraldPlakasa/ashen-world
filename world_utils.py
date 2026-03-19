"""
Backward-compatible shim: re-exports everything from src/utils/world_utils.

Existing imports like ``from world_utils import clamp`` keep working.
For new code, prefer ``from src.utils.world_utils import clamp``.
"""
from src.utils.world_utils import (  # noqa: F401
    pick,
    rand_int,
    clamp,
    pick_weighted,
    exp_to_next_level,
    safe_int,
    is_child,
)
