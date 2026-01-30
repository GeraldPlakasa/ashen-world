"""TypedDict for the Bank (village treasury) data structure."""

from __future__ import annotations

from typing import TypedDict


class Bank(TypedDict, total=False):
    tax_rate: float
    balance: int
    building_levels: dict[str, int]
    building_health: dict[str, int]
    last_election_year: int | None
    last_election_message: str
    year_stats: dict
    yearly_history: list
