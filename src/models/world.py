"""TypedDict for the WorldPayload data structure."""

from __future__ import annotations

from typing import TypedDict


class WorldPayload(TypedDict, total=False):
    total_day: int
    year: int
    day_in_year: int
    weather: str
    next_weather_roll_day: int
