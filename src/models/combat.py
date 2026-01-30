"""TypedDicts for combat-related data structures."""

from __future__ import annotations

from typing import TypedDict

# Functional form required: "def" is a Python keyword.
Enemy = TypedDict(
    "Enemy",
    {
        "tier": str,
        "name": str,
        "atk": int,
        "def": int,
        "hp": int,
        "expReward": int,
        "repReward": int,
        "coinReward": int,
    },
    total=False,
)


class CombatResult(TypedDict, total=False):
    enemy: Enemy
    outcome: str | None
    hpLost: int
    coinGained: int
    taxPaid: int
    victory: bool
    diedAfterWin: bool


class ShopOffer(TypedDict, total=False):
    type: str
    cost: int
    bonuses: list[dict]
