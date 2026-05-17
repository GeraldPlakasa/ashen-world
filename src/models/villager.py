"""TypedDict for the Villager data structure."""

from __future__ import annotations

from typing import TypedDict

# Functional form required: "int" and "def" are Python keywords.
Villager = TypedDict(
    "Villager",
    {
        "id": int,
        "name": str,
        "family": str,
        "gender": str,
        "job": str,
        "coins": int,
        "age": int,
        "int": int,
        "rep": int,
        "level": int,
        "exp": int,
        "atk": int,
        "def": int,
        "hp": int,
        "mp": int,
        "hunger": int,
        "traits": str,
        "last_action": str,
        "action_log": str,
        "relationships": dict,
        "spouseId": int,
        "spouseSinceDay": int,
        "spouseId_at_death": int,
        "alive": bool,
        "origin": str,
        "owner": str,
        "gen": int,
        "immigrantGen": int,
        "motherId": int,
        "fatherId": int,
        "childrenIds": list,
        "kingTerms": int,
        "consecutiveTerms": int,
        "death_day": int,
        "huntWins": int,
        "huntWinsYear": int,
        "born_day": int,
        "last_birth_day": int,
        "skills": str,  # Comma-separated skill names
        "skill_learning": str,  # JSON dict of {skill_name: lesson_count} for mentoring progress
        "questWins": int,
        "achievements": str,  # JSON list of achievement IDs
        "kingsVotedFor": str,  # JSON list of king IDs voted for
        "equip_weapon": int,  # artifact instance id (0 = empty)
        "equip_armor": int,
        "equip_ring": int,
        "equip_amulet": int,
        "equip_tome": int,
        "last_forge_day": int,  # cooldown anchor for forge_artifact action
        "blue_blood": int,  # 1 if descended from a king (set at birth or on king coronation)
    },
    total=False,
)
