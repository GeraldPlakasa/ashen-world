"""
Chronicle repository — narrative event log (the in-world Town Crier).

Events are written here from the simulation services and rendered on the
/chronicle page and the landing-page headlines widget.

Importance scale (1-5):
    1: trivia (one villager's level-up, minor scuffles)
    2: routine drama (births, normal deaths, coming-of-age)
    3: notable (marriages, building completions, world events)
    4: major (kings elected, nobles murdered, magic milestones)
    5: legendary (king assassinations, ARCANE quest completion)
"""
from __future__ import annotations

import json
from typing import Any

from src.repositories.base import db_conn, init_db


def record_event(
    day: int,
    year: int,
    category: str,
    headline: str,
    body: str = "",
    actors: list[dict] | None = None,
    importance: int = 2,
) -> int:
    """Insert a chronicle event. Returns the new row id."""
    init_db()
    actors_json = json.dumps(actors or [])
    with db_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO chronicle_events (day, year, category, headline, body, actors, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                int(day),
                int(year),
                str(category),
                str(headline),
                str(body or ""),
                actors_json,
                max(1, min(5, int(importance))),
            ),
        )
        return int(cur.lastrowid or 0)


def list_events(
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    year: int | None = None,
    min_importance: int = 1,
    q: str | None = None,
    actor_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return chronicle events, newest first, optionally filtered.
    `q` does a case-insensitive substring match against headline + body.
    `actor_name` keeps only events whose `actors` JSON contains a
    member with the exact `name` field — used by the chronicle page's
    king filter, but the predicate is generic.
    """
    init_db()
    where, params = _build_where(category, year, min_importance, q, actor_name)
    params.extend([int(limit), int(offset)])
    with db_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, day, year, category, headline, body, actors, importance, created_at
            FROM chronicle_events
            {where}
            ORDER BY day DESC, id DESC
            LIMIT ? OFFSET ?;
            """,
            tuple(params),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["actors"] = json.loads(d.get("actors") or "[]")
            except Exception:
                d["actors"] = []
            out.append(d)
        return out


def _build_where(
    category: str | None,
    year: int | None,
    min_importance: int,
    q: str | None,
    actor_name: str | None,
) -> tuple[str, list[Any]]:
    """Shared WHERE-clause builder for list_events and count_events.
    Returns (where_sql, params)."""
    clauses = ["importance >= ?"]
    params: list[Any] = [int(min_importance)]
    if category:
        clauses.append("category = ?")
        params.append(category)
    if year is not None:
        clauses.append("year = ?")
        params.append(int(year))
    if q:
        like = f"%{q.strip()}%"
        clauses.append("(headline LIKE ? COLLATE NOCASE OR body LIKE ? COLLATE NOCASE)")
        params.extend([like, like])
    if actor_name:
        # SQLite JSON1: walk the actors array, match the exact `name` field.
        # Handles unicode names (D'Arion etc.) correctly — LIKE would have
        # to match the JSON-escaped form `’` which is brittle.
        clauses.append(
            "EXISTS (SELECT 1 FROM json_each(actors) je "
            "WHERE json_extract(je.value, '$.name') = ?)"
        )
        params.append(actor_name)
    return "WHERE " + " AND ".join(clauses), params


def list_top_recent(limit: int = 5, min_importance: int = 3) -> list[dict[str, Any]]:
    """Top N high-importance events, newest first. For the landing widget."""
    return list_events(limit=limit, min_importance=min_importance)


def count_events(
    category: str | None = None,
    year: int | None = None,
    q: str | None = None,
    min_importance: int = 1,
    actor_name: str | None = None,
) -> int:
    init_db()
    where_sql, params = _build_where(category, year, min_importance, q, actor_name)
    with db_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM chronicle_events {where_sql};",
            tuple(params),
        ).fetchone()
        return int(row["c"] if row else 0)


def list_categories() -> list[str]:
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM chronicle_events ORDER BY category;"
        ).fetchall()
        return [r["category"] for r in rows]


def list_kings() -> list[str]:
    """All distinct king names that ever held the throne, alphabetically.
    Pulled from yearly_stats (authoritative) rather than chronicle actors,
    so a king with zero chronicle entries still appears in the filter."""
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT king_name FROM yearly_stats "
            "WHERE king_name IS NOT NULL AND king_name != '' "
            "ORDER BY king_name;"
        ).fetchall()
        return [r["king_name"] for r in rows]


def list_years() -> list[int]:
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT year FROM chronicle_events ORDER BY year DESC;"
        ).fetchall()
        return [int(r["year"]) for r in rows]


def prune_low_importance(current_year: int, keep_years: int = 3) -> int:
    """
    Drop importance 1-2 events older than `keep_years`.
    Importance >= 3 are kept forever.
    Returns number of rows deleted.
    """
    init_db()
    cutoff_year = int(current_year) - int(keep_years)
    with db_conn() as conn:
        cur = conn.execute(
            "DELETE FROM chronicle_events WHERE importance <= 2 AND year < ?;",
            (cutoff_year,),
        )
        return int(cur.rowcount or 0)


def clear_chronicle() -> None:
    """Wipe all chronicle events. Used on world reset."""
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM chronicle_events;")
