"""TypedDicts for yearly stats and champion data structures."""

from __future__ import annotations

from typing import TypedDict


class Champion(TypedDict, total=False):
    id: int | None
    name: str
    value: int


class YearlyChampions(TypedDict, total=False):
    most_atk: Champion
    most_int: Champion
    richest: Champion
    top_hunter: Champion


class YearStats(TypedDict, total=False):
    year: int
    king_id: int | None
    king_name: str | None
    total_deaths: int
    total_immigrants: int
    tax_rate_sum: float
    days_counted: int
    treasury_start: int | None
    treasury_end: int | None
    avg_tax_rate: float | None
    is_finalized: int
    most_atk_id: int | None
    most_atk_name: str
    most_atk_value: int
    most_int_id: int | None
    most_int_name: str
    most_int_value: int
    richest_id: int | None
    richest_name: str
    richest_value: int
    top_hunter_id: int | None
    top_hunter_name: str
    top_hunter_value: int


class AllTimeLeader(TypedDict, total=False):
    year: int
    id: int | None
    name: str
    value: int
