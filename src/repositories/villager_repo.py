import json
from typing import List, Dict, Any

import config
from src.repositories.base import db_conn, init_db

# ---------------------------------------------------------------------------
#  Villagers (replaces characters.csv)
# ---------------------------------------------------------------------------

def save_villagers(rows: List[Dict[str, Any]]):
    """
    Persist the current villager list to SQLite.
    This replaces save_to_csv().
    """
    init_db()

    # Normalize and store.
    with db_conn() as conn:
        conn.execute("DELETE FROM villagers;")  # simplest "replace all" behavior

        if not rows:
            return

        # Insert rows
        columns = list(config.FIELDNAMES)
        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)

        insert_sql = f"INSERT INTO villagers ({col_list}) VALUES ({placeholders});"

        for r in rows:
            r2 = dict(r)

            # Store boolean alive as TEXT "true"/"false"
            r2["alive"] = "true" if r2.get("alive", True) else "false"

            # JSON fields stored as TEXT
            r2["childrenIds"] = json.dumps(r2.get("childrenIds", []), ensure_ascii=False)
            rels = r2.get("relationships", {})
            if not isinstance(rels, dict):
                rels = {}
            r2["relationships"] = json.dumps(rels, ensure_ascii=False)

            # Defaults
            r2.setdefault("last_action", "")
            r2.setdefault("owner", "")
            r2.setdefault("action_log", "")

            values = [r2.get(c, "" if c not in config.INT_FIELDS else 0) for c in columns]
            conn.execute(insert_sql, values)


def load_villagers() -> List[Dict[str, Any]]:
    """
    Load villagers from SQLite.
    This replaces load_from_csv().
    """
    init_db()

    with db_conn() as conn:
        cur = conn.execute("SELECT * FROM villagers;")
        out: List[Dict[str, Any]] = []

        for row in cur.fetchall():
            r2 = dict(row)

            # Convert known integer fields
            for key in config.INT_FIELDS:
                val = r2.get(key)
                try:
                    r2[key] = int(val) if val is not None and val != "" else 0
                except Exception:
                    r2[key] = 0

            # Alive flag -> bool
            r2["alive"] = str(r2.get("alive", "true")).lower() == "true"

            # childrenIds -> list
            try:
                r2["childrenIds"] = json.loads(r2.get("childrenIds") or "[]")
            except Exception:
                r2["childrenIds"] = []

            # relationships -> dict
            rel_str = r2.get("relationships") or "{}"
            try:
                data = json.loads(rel_str)
                r2["relationships"] = data if isinstance(data, dict) else {}
            except Exception:
                r2["relationships"] = {}

            # Safe defaults
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

def graveyard_upsert_from_villager(v: Dict[str, Any]):
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
    }

    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO graveyard (
                id, name, family, gender, traits, origin, owner,
                motherId, fatherId, childrenIds, spouseId, born_day
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                born_day=excluded.born_day;
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
            ),
        )


def graveyard_get(vid: int) -> Dict[str, Any] | None:
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


def graveyard_get_many(ids: List[int]) -> Dict[int, Dict[str, Any]]:
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
