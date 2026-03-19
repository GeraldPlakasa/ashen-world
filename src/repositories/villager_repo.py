from __future__ import annotations

import json
from typing import Dict, Any

import config
from src.repositories.base import db_conn, init_db
from src.models.villager import Villager
from src.models.graveyard import GraveyardRecord
from src.repositories import relationship_repo, achievement_repo, vote_repo

def save_villagers(rows: list[Villager]) -> None:
    """
    Persist all villagers to SQLite.
    Also syncs normalized tables (relationships, achievements, votes).
    """
    init_db()

    with db_conn() as conn:
        conn.execute("DELETE FROM villagers;")  # simplest "replace all" behavior
        # Clear normalized tables for full sync
        conn.execute("DELETE FROM villager_relationships;")
        conn.execute("DELETE FROM villager_achievements;")
        conn.execute("DELETE FROM villager_votes;")

        if not rows:
            return

        columns = list(config.FIELDNAMES)
        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)

        insert_sql = f"INSERT INTO villagers ({col_list}) VALUES ({placeholders});"

        for r in rows:
            r2 = dict(r)
            vid = int(r2.get("id", 0) or 0)

            # Store boolean alive as TEXT "true"/"false"
            r2["alive"] = "true" if r2.get("alive", True) else "false"

            # childrenIds still stored as JSON in villagers table
            r2["childrenIds"] = json.dumps(r2.get("childrenIds", []), ensure_ascii=False)

            # Save relationships to normalized table
            rels = r2.get("relationships", {})
            if not isinstance(rels, dict):
                rels = {}
            for other_id, score in rels.items():
                try:
                    conn.execute(
                        "INSERT INTO villager_relationships (villager_id, other_id, score) VALUES (?, ?, ?)",
                        (vid, int(other_id), int(score)),
                    )
                except (ValueError, TypeError):
                    pass

            # Save achievements to normalized table
            achs = r2.get("achievements", "[]")
            if isinstance(achs, str):
                try:
                    achs = json.loads(achs) if achs else []
                except json.JSONDecodeError:
                    achs = []
            elif isinstance(achs, list):
                pass  # already a list
            else:
                achs = []
            for ach_id in (achs or []):
                if ach_id:
                    conn.execute(
                        "INSERT INTO villager_achievements (villager_id, achievement_id) VALUES (?, ?)",
                        (vid, str(ach_id)),
                    )

            # Save votes to normalized table
            votes = r2.get("kingsVotedFor", "[]")
            if isinstance(votes, str):
                try:
                    votes = json.loads(votes) if votes else []
                except json.JSONDecodeError:
                    votes = []
            elif isinstance(votes, list):
                pass  # already a list
            else:
                votes = []
            for king_id in (votes or []):
                try:
                    conn.execute(
                        "INSERT INTO villager_votes (villager_id, king_id) VALUES (?, ?)",
                        (vid, int(king_id)),
                    )
                except (ValueError, TypeError):
                    pass

            r2.setdefault("last_action", "")
            r2.setdefault("owner", "")
            r2.setdefault("action_log", "")

            values = [r2.get(c, "" if c not in config.INT_FIELDS else 0) for c in columns]
            conn.execute(insert_sql, values)


def load_villagers() -> list[Villager]:
    """
    Load all villagers from SQLite.
    Populates relationships, achievements, votes from normalized tables.
    """
    init_db()

    with db_conn() as conn:
        cur = conn.execute("SELECT * FROM villagers;")
        out: list[Villager] = []

        # Pre-load all normalized data for efficiency
        rel_rows = conn.execute("SELECT villager_id, other_id, score FROM villager_relationships").fetchall()
        ach_rows = conn.execute("SELECT villager_id, achievement_id FROM villager_achievements").fetchall()
        vote_rows = conn.execute("SELECT villager_id, king_id FROM villager_votes").fetchall()

        # Build lookup dicts
        rels_by_vid: dict[int, dict[str, int]] = {}
        for r in rel_rows:
            vid = r["villager_id"]
            if vid not in rels_by_vid:
                rels_by_vid[vid] = {}
            rels_by_vid[vid][str(r["other_id"])] = r["score"]

        achs_by_vid: dict[int, list[str]] = {}
        for r in ach_rows:
            vid = r["villager_id"]
            if vid not in achs_by_vid:
                achs_by_vid[vid] = []
            achs_by_vid[vid].append(r["achievement_id"])

        votes_by_vid: dict[int, list[int]] = {}
        for r in vote_rows:
            vid = r["villager_id"]
            if vid not in votes_by_vid:
                votes_by_vid[vid] = []
            votes_by_vid[vid].append(r["king_id"])

        for row in cur.fetchall():
            r2 = dict(row)
            vid = int(r2.get("id", 0) or 0)

            for key in config.INT_FIELDS:
                val = r2.get(key)
                try:
                    r2[key] = int(val) if val is not None and val != "" else 0
                except Exception:
                    r2[key] = 0

            r2["alive"] = str(r2.get("alive", "true")).lower() == "true"

            try:
                r2["childrenIds"] = json.loads(r2.get("childrenIds") or "[]")
            except Exception:
                r2["childrenIds"] = []

            # Load from normalized tables (columns dropped from villagers table)
            r2["relationships"] = rels_by_vid.get(vid, {})
            r2["achievements"] = json.dumps(achs_by_vid.get(vid, []))
            r2["kingsVotedFor"] = json.dumps(votes_by_vid.get(vid, []))

            if r2.get("last_action") is None:
                r2["last_action"] = ""
            if r2.get("owner") is None:
                r2["owner"] = ""
            if r2.get("action_log") is None:
                r2["action_log"] = ""

            out.append(r2)

        return out


# Backward-compatible aliases (so you don't have to update all imports at once)
save_to_csv = save_villagers
load_from_csv = load_villagers


# ---------------------------------------------------------------------------
#  Graveyard
# ---------------------------------------------------------------------------

def graveyard_upsert_from_villager(v: Villager) -> None:
    """
    Save a lightweight identity snapshot into graveyard.
    Upsert by id (so repeated calls are safe).
    """
    init_db()

    vid = int(v.get("id", 0) or 0)
    if vid <= 0:
        return

    payload = {
        "id": vid,
        "name": (v.get("name") or ""),
        "family": (v.get("family") or ""),
        "gender": (v.get("gender") or ""),
        "traits": (v.get("traits") or ""),
        "origin": (v.get("origin") or ""),
        "owner": (v.get("owner") or ""),
        "motherId": int(v.get("motherId", 0) or 0),
        "fatherId": int(v.get("fatherId", 0) or 0),
        "childrenIds": json.dumps(v.get("childrenIds", []) or [], ensure_ascii=False),
        "spouseId": int(v.get("spouseId", 0) or 0),
        "born_day": int(v.get("born_day", 0) or 0),
        "death_day": int(v.get("death_day", 0) or 0),
    }

    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO graveyard (
                id, name, family, gender, traits, origin, owner,
                motherId, fatherId, childrenIds, spouseId, born_day, death_day
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                family=excluded.family,
                gender=excluded.gender,
                traits=excluded.traits,
                origin=excluded.origin,
                owner=excluded.owner,
                motherId=excluded.motherId,
                fatherId=excluded.fatherId,
                childrenIds=excluded.childrenIds,
                spouseId=excluded.spouseId,
                born_day=excluded.born_day,
                death_day=excluded.death_day;
            """,
            (
                payload["id"],
                payload["name"],
                payload["family"],
                payload["gender"],
                payload["traits"],
                payload["origin"],
                payload["owner"],
                payload["motherId"],
                payload["fatherId"],
                payload["childrenIds"],
                payload["spouseId"],
                payload["born_day"],
                payload["death_day"],
            ),
        )


def graveyard_get(vid: int) -> GraveyardRecord | None:
    """Retrieve a single graveyard record by villager ID, or None."""
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM graveyard WHERE id=? LIMIT 1;",
            (int(vid),),
        ).fetchone()
        if not row:
            return None
        r = dict(row)
        # decode childrenIds back to list
        try:
            r["childrenIds"] = json.loads(r.get("childrenIds") or "[]")
        except Exception:
            r["childrenIds"] = []
        return r


def graveyard_get_many(ids: list[int]) -> dict[int, GraveyardRecord]:
    """
    Return {id: record} for quick lookup (useful for pinned view).
    """
    init_db()
    ids = [int(x) for x in ids if str(x).strip().isdigit()]
    if not ids:
        return {}

    placeholders = ",".join(["?"] * len(ids))
    with db_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM graveyard WHERE id IN ({placeholders});",
            ids,
        ).fetchall()

    out = {}
    for row in rows:
        r = dict(row)
        try:
            r["childrenIds"] = json.loads(r.get("childrenIds") or "[]")
        except Exception:
            r["childrenIds"] = []
        out[int(r["id"])] = r
    return out


def graveyard_cleanup_old(current_total_day: int, max_years: int) -> int:
    """
    Remove graveyard entries where death occurred more than max_years ago.
    Returns count of deleted records.
    """
    init_db()
    max_dead_days = max_years * config.DAYS_PER_YEAR
    cutoff_day = current_total_day - max_dead_days

    with db_conn() as conn:
        # Delete entries where death_day > 0 and death_day < cutoff
        cursor = conn.execute(
            """
            DELETE FROM graveyard
            WHERE death_day > 0 AND death_day < ?;
            """,
            (cutoff_day,),
        )
        return cursor.rowcount
