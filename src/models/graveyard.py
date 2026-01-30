"""TypedDict for the GraveyardRecord data structure."""

from __future__ import annotations

from typing import TypedDict


class GraveyardRecord(TypedDict, total=False):
    id: int
    name: str
    family: str
    gender: str
    traits: str
    origin: str
    owner: str
    motherId: int
    fatherId: int
    childrenIds: list
    spouseId: int
    born_day: int
