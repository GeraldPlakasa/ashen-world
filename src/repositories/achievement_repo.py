"""
Repository for villager_achievements table.

Handles achievement tracking using normalized table
instead of JSON array in villagers.achievements column.
"""
from __future__ import annotations

from .base import db_conn


def get_achievements(villager_id: int) -> list[str]:
    """Get all achievement IDs for a villager."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT achievement_id FROM villager_achievements WHERE villager_id = ?",
            (villager_id,),
        )
        return [row["achievement_id"] for row in cur.fetchall()]


def has_achievement(villager_id: int, achievement_id: str) -> bool:
    """Check if villager has a specific achievement."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM villager_achievements WHERE villager_id = ? AND achievement_id = ?",
            (villager_id, achievement_id),
        )
        return cur.fetchone() is not None


def add_achievement(villager_id: int, achievement_id: str, earned_day: int = 0) -> bool:
    """
    Add achievement to villager. Returns True if newly added, False if already had.
    """
    if has_achievement(villager_id, achievement_id):
        return False
    
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO villager_achievements (villager_id, achievement_id, earned_day)
            VALUES (?, ?, ?)
            """,
            (villager_id, achievement_id, earned_day),
        )
        conn.commit()
    return True


def remove_achievement(villager_id: int, achievement_id: str) -> None:
    """Remove achievement from villager."""
    with db_conn() as conn:
        conn.execute(
            "DELETE FROM villager_achievements WHERE villager_id = ? AND achievement_id = ?",
            (villager_id, achievement_id),
        )
        conn.commit()


def clear_achievements(villager_id: int) -> None:
    """Remove all achievements from villager."""
    with db_conn() as conn:
        conn.execute(
            "DELETE FROM villager_achievements WHERE villager_id = ?",
            (villager_id,),
        )
        conn.commit()


def count_achievements(villager_id: int) -> int:
    """Count achievements for a villager."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) as cnt FROM villager_achievements WHERE villager_id = ?",
            (villager_id,),
        )
        return cur.fetchone()["cnt"]


def get_villagers_with_achievement(achievement_id: str) -> list[int]:
    """Get all villager IDs that have a specific achievement."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT villager_id FROM villager_achievements WHERE achievement_id = ?",
            (achievement_id,),
        )
        return [row["villager_id"] for row in cur.fetchall()]
