"""
Repository for villager_relationships table.

Handles relationship scores between villagers using normalized table
instead of JSON blob in villagers.relationships column.
"""
from __future__ import annotations

from .base import db_conn


def get_relationship_score(villager_id: int, other_id: int) -> int:
    """Get relationship score between two villagers."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT score FROM villager_relationships WHERE villager_id = ? AND other_id = ?",
            (villager_id, other_id),
        )
        row = cur.fetchone()
        return row["score"] if row else 0


def set_relationship_score(villager_id: int, other_id: int, score: int) -> None:
    """Set relationship score between two villagers."""
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO villager_relationships (villager_id, other_id, score)
            VALUES (?, ?, ?)
            ON CONFLICT(villager_id, other_id) DO UPDATE SET score = excluded.score
            """,
            (villager_id, other_id, score),
        )
        conn.commit()


def adjust_relationship_score(villager_id: int, other_id: int, delta: int) -> int:
    """Adjust relationship score by delta, return new score."""
    current = get_relationship_score(villager_id, other_id)
    new_score = max(-100, min(100, current + delta))  # Clamp to -100..100
    set_relationship_score(villager_id, other_id, new_score)
    return new_score


def get_all_relationships(villager_id: int) -> dict[int, int]:
    """Get all relationships for a villager as {other_id: score}."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT other_id, score FROM villager_relationships WHERE villager_id = ?",
            (villager_id,),
        )
        return {row["other_id"]: row["score"] for row in cur.fetchall()}


def delete_relationships(villager_id: int) -> None:
    """Delete all relationships for a villager (both directions)."""
    with db_conn() as conn:
        conn.execute(
            "DELETE FROM villager_relationships WHERE villager_id = ? OR other_id = ?",
            (villager_id, villager_id),
        )
        conn.commit()


def get_top_relationships(villager_id: int, limit: int = 5) -> list[tuple[int, int]]:
    """Get top N relationships by score. Returns [(other_id, score), ...]."""
    with db_conn() as conn:
        cur = conn.execute(
            """
            SELECT other_id, score FROM villager_relationships
            WHERE villager_id = ?
            ORDER BY score DESC
            LIMIT ?
            """,
            (villager_id, limit),
        )
        return [(row["other_id"], row["score"]) for row in cur.fetchall()]
