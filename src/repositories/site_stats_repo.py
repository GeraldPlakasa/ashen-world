"""Repository for site statistics tracking (page views, character creations, etc.)."""
from __future__ import annotations

from datetime import datetime, timezone

from src.repositories.base import db_conn, init_db


def increment_stat(stat_type: str, date_str: str | None = None) -> None:
    """Increment a stat counter for a given date (defaults to today UTC)."""
    init_db()
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO site_stats (stat_type, stat_date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(stat_type, stat_date) DO UPDATE SET count = count + 1;
            """,
            (stat_type, date_str),
        )


def get_stats_by_type(stat_type: str, limit: int = 90) -> list[dict]:
    """Get daily stats for a type, ordered by date DESC."""
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT stat_date, count FROM site_stats WHERE stat_type=? ORDER BY stat_date DESC LIMIT ?;",
            (stat_type, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_stats_summary() -> dict:
    """Get total counts grouped by stat_type."""
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT stat_type, SUM(count) as total FROM site_stats GROUP BY stat_type;"
        ).fetchall()
        return {r["stat_type"]: r["total"] for r in rows}
