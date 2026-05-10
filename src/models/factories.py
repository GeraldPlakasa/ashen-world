"""Factory functions for creating default typed data structures."""

from __future__ import annotations

from typing import Any

from src.models.villager import Villager
from src.models.bank import Bank
from src.models.world import WorldPayload


def create_default_villager(**overrides: Any) -> Villager:
    """Return a Villager dict pre-filled with safe defaults.

    Any keyword argument overrides the corresponding field.
    """
    base: Villager = {
        "id": 0,
        "name": "",
        "family": "",
        "gender": "Male",
        "job": "Farmer",
        "coins": 0,
        "age": 18,
        "int": 1,
        "rep": 0,
        "level": 1,
        "exp": 0,
        "atk": 1,
        "def": 1,
        "hp": 100,
        "mp": 0,
        "hunger": 0,
        "traits": "",
        "last_action": "",
        "action_log": "",
        "relationships": {},
        "spouseId": 0,
        "spouseSinceDay": 0,
        "spouseId_at_death": 0,
        "alive": True,
        "origin": "npc",
        "owner": "",
        "gen": 1,
        "immigrantGen": 0,
        "motherId": 0,
        "fatherId": 0,
        "childrenIds": [],
        "kingTerms": 0,
        "consecutiveTerms": 0,
        "death_day": 0,
        "huntWins": 0,
        "huntWinsYear": 0,
        "questWins": 0,
        "born_day": 0,
        "last_birth_day": 0,
        "achievements": "[]",
        "kingsVotedFor": "[]",
        "skills": "",
        "skill_learning": "{}",
        "equip_weapon": 0,
        "equip_armor": 0,
        "equip_ring": 0,
        "equip_amulet": 0,
        "equip_tome": 0,
        "last_forge_day": 0,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def create_default_bank(**overrides: Any) -> Bank:
    """Return a Bank dict pre-filled with safe defaults."""
    base: Bank = {
        "tax_rate": 0.10,
        "balance": 0,
        "building_levels": {},
        "building_health": {},
        "last_election_year": None,
        "last_election_message": "",
        "year_stats": {},
        "yearly_history": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def create_default_world(**overrides: Any) -> WorldPayload:
    """Return a WorldPayload dict pre-filled with safe defaults."""
    base: WorldPayload = {
        "total_day": 1,
        "year": 1,
        "day_in_year": 0,
        "weather": "sunny",
        "next_weather_roll_day": 1,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base
