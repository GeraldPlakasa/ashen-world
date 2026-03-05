"""TypedDict for the Bank (village treasury) data structure."""

from __future__ import annotations

from typing import TypedDict


class Bank(TypedDict, total=False):
    tax_rate: float
    balance: int
    building_levels: dict[str, int]
    building_health: dict[str, int]
    
    # Election tracking
    last_election_year: int | None
    last_election_message: str
    
    # Event tracking
    last_event_message: str
    last_event_day: int | None
    last_event_year_tracking: int
    event_day_for_year: int | None
    event_triggered_this_year: bool
    
    # Quest tracking
    last_quest_year: int
    quest_day_for_year: int | None
    quest_triggered_this_year: bool
    last_quest_message: str
    last_quest_day: int | None
    last_quest_type: str | None
    last_quest_success: bool | None
    
    # Stats
    year_stats: dict
    yearly_history: list
