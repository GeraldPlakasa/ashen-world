from __future__ import annotations

import json

import config
from src.repositories.base import db_conn, init_db
from src.models.villager import Villager
from src.models.graveyard import GraveyardRecord

def _parse_json_list(raw, cast=str) -> list:
    """Parse a value that may be a list or JSON string into a list."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    if raw is None:
        return []
    return []


def save_villagers(rows: list[Villager]) -> None:
    """
    Persist all villagers to SQLite.
    Relationships, achievements, and votes are stored as JSON columns in
    the villagers table for fast bulk save (~800 rows). The normalized
    tables are NOT updated here — they remain as a queryable index and
    are kept in sync separately when needed.
    """
    init_db()

    with db_conn() as conn:
        conn.execute("DELETE FROM villagers;")

        if not rows:
            return

        columns = list(config.FIELDNAMES)
        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)
        insert_sql = f"INSERT INTO villagers ({col_list}) VALUES ({placeholders});"

        for r in rows:
            r2 = dict(r)

            # Store boolean alive as TEXT "true"/"false"
            r2["alive"] = "true" if r2.get("alive", True) else "false"

            # Serialize complex fields to JSON
            r2["childrenIds"] = json.dumps(r2.get("childrenIds", []), ensure_ascii=False)

            # Relationships: dict -> JSON string
            rels = r2.get("relationships", {})
            if not isinstance(rels, dict):
                rels = {}
            r2["relationships"] = json.dumps(rels, ensure_ascii=False)

            # Achievements: list or JSON string -> JSON string
            achs = r2.get("achievements", "[]")
            if isinstance(achs, list):
                r2["achievements"] = json.dumps(achs, ensure_ascii=False)
            elif not isinstance(achs, str):
                r2["achievements"] = "[]"

            # Votes: list or JSON string -> JSON string
            votes = r2.get("kingsVotedFor", "[]")
            if isinstance(votes, list):
                r2["kingsVotedFor"] = json.dumps(votes, ensure_ascii=False)
            elif not isinstance(votes, str):
                r2["kingsVotedFor"] = "[]"

            r2.setdefault("last_action", "")
            r2.setdefault("owner", "")
            r2.setdefault("action_log", "")

            values = [r2.get(c, "" if c not in config.INT_FIELDS else 0) for c in columns]
            conn.execute(insert_sql, values)


def load_villagers(alive_only: bool = False) -> list[Villager]:
    """
    Load villagers from SQLite.
    Relationships, achievements, and votes are read from JSON columns
    in the villagers table (fast: no joins, no 456K-row reads).
    If alive_only=True, skip dead villagers for faster loading.
    """
    init_db()

    with db_conn() as conn:
        if alive_only:
            cur = conn.execute("SELECT * FROM villagers WHERE alive='true';")
        else:
            cur = conn.execute("SELECT * FROM villagers;")
        out: list[Villager] = []

        for row in cur.fetchall():
            r2 = dict(row)

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

            # Relationships: JSON string -> dict
            rels_raw = r2.get("relationships", "{}")
            if isinstance(rels_raw, str) and rels_raw.strip():
                try:
                    rels = json.loads(rels_raw)
                    r2["relationships"] = rels if isinstance(rels, dict) else {}
                except Exception:
                    r2["relationships"] = {}
            elif isinstance(rels_raw, dict):
                pass  # already a dict
            else:
                r2["relationships"] = {}

            # Achievements & votes stay as JSON strings (consumers parse as needed)
            if r2.get("achievements") is None:
                r2["achievements"] = "[]"
            if r2.get("kingsVotedFor") is None:
                r2["kingsVotedFor"] = "[]"

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


def graveyard_clear_all() -> None:
    """Delete all graveyard entries (used on world reset)."""
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM graveyard;")


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
