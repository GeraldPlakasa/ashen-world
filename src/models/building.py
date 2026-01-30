"""TypedDict for the Building data structure."""

from __future__ import annotations

from typing import TypedDict


class Building(TypedDict):
    key: str
    name: str
    cost: int
