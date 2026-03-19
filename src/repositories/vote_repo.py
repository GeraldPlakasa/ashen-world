"""
Repository for villager_votes table.

Tracks which kings a villager has voted for, using normalized table
instead of JSON array in villagers.kingsVotedFor column.
"""
from __future__ import annotations

from .base import db_conn


def get_kings_voted_for(villager_id: int) -> list[int]:
    """Get all king IDs this villager has voted for."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT king_id FROM villager_votes WHERE villager_id = ?",
            (villager_id,),
        )
        return [row["king_id"] for row in cur.fetchall()]


def has_voted_for(villager_id: int, king_id: int) -> bool:
    """Check if villager has voted for a specific king."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM villager_votes WHERE villager_id = ? AND king_id = ?",
            (villager_id, king_id),
        )
        return cur.fetchone() is not None


def add_vote(villager_id: int, king_id: int, vote_day: int = 0) -> bool:
    """
    Record that villager voted for king. Returns True if newly added.
    """
    if has_voted_for(villager_id, king_id):
        return False
    
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO villager_votes (villager_id, king_id, vote_day)
            VALUES (?, ?, ?)
            """,
            (villager_id, king_id, vote_day),
        )
        conn.commit()
    return True


def clear_votes(villager_id: int) -> None:
    """Remove all vote records for villager."""
    with db_conn() as conn:
        conn.execute(
            "DELETE FROM villager_votes WHERE villager_id = ?",
            (villager_id,),
        )
        conn.commit()


def count_votes_for_king(king_id: int) -> int:
    """Count how many villagers have voted for this king."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) as cnt FROM villager_votes WHERE king_id = ?",
            (king_id,),
        )
        return cur.fetchone()["cnt"]


def get_voters_for_king(king_id: int) -> list[int]:
    """Get all villager IDs that voted for this king."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT villager_id FROM villager_votes WHERE king_id = ?",
            (king_id,),
        )
        return [row["villager_id"] for row in cur.fetchall()]
