"""
Artifact repository — persistence for magical artifact instances.

Templates (immutable item definitions) live in config.ARTIFACT_TEMPLATES.
This module manages the per-instance state: who owns it, when it was acquired,
and the chronicle of past owners.
"""
from __future__ import annotations

import json
from typing import Any

from src.repositories.base import db_conn, init_db


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["forged_history"] = json.loads(d.get("forged_history") or "[]")
    except Exception:
        d["forged_history"] = []
    d["destroyed"] = bool(d.get("destroyed", 0))
    return d


def create_artifact(
    slug: str,
    owner_id: int,
    acquired_day: int,
    acquired_via: str,
    forged_history: list[dict] | None = None,
    condition: int = 100,
) -> int:
    """Insert a new artifact instance. Returns the new row id."""
    init_db()
    history_json = json.dumps(forged_history or [], ensure_ascii=False)
    with db_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO artifacts (slug, owner_id, acquired_day, acquired_via,
                                   forged_history, condition, destroyed)
            VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (
                str(slug),
                int(owner_id or 0),
                int(acquired_day or 0),
                str(acquired_via or ""),
                history_json,
                int(condition),
            ),
        )
        return int(cur.lastrowid or 0)


def get_artifact(artifact_id: int) -> dict[str, Any] | None:
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE id=? LIMIT 1;",
            (int(artifact_id),),
        ).fetchone()
        if not row:
            return None
        return _row_to_dict(row)


def get_artifacts_by_ids(ids: list[int]) -> dict[int, dict[str, Any]]:
    """Bulk fetch — returns {id: artifact_dict}."""
    init_db()
    ids = [int(x) for x in ids if int(x or 0) > 0]
    if not ids:
        return {}
    placeholders = ",".join(["?"] * len(ids))
    with db_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM artifacts WHERE id IN ({placeholders});",
            ids,
        ).fetchall()
    return {int(r["id"]): _row_to_dict(r) for r in rows}


def list_artifacts_for_owner(owner_id: int) -> list[dict[str, Any]]:
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE owner_id=? AND destroyed=0;",
            (int(owner_id),),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_all_artifacts(include_destroyed: bool = False) -> list[dict[str, Any]]:
    init_db()
    with db_conn() as conn:
        if include_destroyed:
            rows = conn.execute("SELECT * FROM artifacts;").fetchall()
        else:
            rows = conn.execute("SELECT * FROM artifacts WHERE destroyed=0;").fetchall()
        return [_row_to_dict(r) for r in rows]


def transfer_artifact(artifact_id: int, new_owner_id: int) -> None:
    """Move an artifact to a new owner (does not append history — caller decides)."""
    init_db()
    with db_conn() as conn:
        conn.execute(
            "UPDATE artifacts SET owner_id=? WHERE id=?;",
            (int(new_owner_id), int(artifact_id)),
        )


def append_history(artifact_id: int, entry: dict) -> None:
    """Append an owner-history entry to forged_history."""
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT forged_history FROM artifacts WHERE id=? LIMIT 1;",
            (int(artifact_id),),
        ).fetchone()
        if not row:
            return
        try:
            history = json.loads(row["forged_history"] or "[]")
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
        history.append(entry)
        conn.execute(
            "UPDATE artifacts SET forged_history=? WHERE id=?;",
            (json.dumps(history, ensure_ascii=False), int(artifact_id)),
        )


def destroy_artifact(artifact_id: int) -> None:
    """Mark an artifact as destroyed (soulbound death, etc.). Owner cleared."""
    init_db()
    with db_conn() as conn:
        conn.execute(
            "UPDATE artifacts SET destroyed=1, owner_id=0 WHERE id=?;",
            (int(artifact_id),),
        )


def clear_artifacts() -> None:
    """Wipe all artifacts. Used on world reset."""
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM artifacts;")
