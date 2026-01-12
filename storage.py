import os
import json
import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any

from werkzeug.security import generate_password_hash

from config import (
    DATA_DIR,
    DB_PATH,        # <-- add this in config.py
    DAY_PATH,       # optional migration
    BANK_PATH,      # optional migration
    USERS_CSV,      # optional migration
    CSV_PATH,       # optional migration (characters.csv)
    DAYS_PER_YEAR,
    INT_FIELDS,
    FIELDNAMES,
    WEATHER_CHANGE_DAYS,
    WEATHER_RAIN_CHANCE,
    WEATHER_TYPES,
)

# ---------------------------------------------------------------------------
#  SQLite helpers
# ---------------------------------------------------------------------------

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

@contextmanager
def db_conn():
    """
    Context manager for SQLite connection.
    - check_same_thread=False helps if you read/write from a background thread.
    - WAL improves concurrency for small apps.
    """
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """
    Create tables if they don't exist.
    Call this once at app startup (or before first use).
    """
    with db_conn() as conn:
        # Users
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )

        # Villagers: store ALL fields from FIELDNAMES as columns (TEXT by default).
        # We'll cast INT_FIELDS on load and store JSON fields as TEXT.
        cols = []
        for f in FIELDNAMES:
            if f == "id":
                cols.append("id INTEGER PRIMARY KEY")
            elif f in INT_FIELDS:
                cols.append(f"{f} INTEGER DEFAULT 0")
            else:
                cols.append(f"{f} TEXT DEFAULT ''")

        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS villagers (
                {", ".join(cols)}
            );
            """
        )

        # World state (day)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS world_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        # Bank state
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        # Yearly stats
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS yearly_stats (
                year INTEGER PRIMARY KEY,
                king_id INTEGER,
                king_name TEXT,

                total_deaths INTEGER DEFAULT 0,
                total_immigrants INTEGER DEFAULT 0,
                tax_rate_sum REAL DEFAULT 0,
                days_counted INTEGER DEFAULT 0,

                treasury_start INTEGER,
                treasury_end INTEGER,
                avg_tax_rate REAL,
                is_finalized INTEGER DEFAULT 0,

                -- Champions (snapshot at year end)
                most_atk_id INTEGER,
                most_atk_name TEXT DEFAULT '',
                most_atk_value INTEGER DEFAULT 0,

                most_int_id INTEGER,
                most_int_name TEXT DEFAULT '',
                most_int_value INTEGER DEFAULT 0,

                richest_id INTEGER,
                richest_name TEXT DEFAULT '',
                richest_value INTEGER DEFAULT 0,

                top_hunter_id INTEGER,
                top_hunter_name TEXT DEFAULT '',
                top_hunter_value INTEGER DEFAULT 0,

                updated_at TEXT DEFAULT (datetime('now'))
            );
            """
        )

        # Graveyard: lightweight identity records for pruned/dead/archived villagers
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graveyard (
                id INTEGER PRIMARY KEY,
                name TEXT DEFAULT '',
                family TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                traits TEXT DEFAULT '',
                origin TEXT DEFAULT '',
                owner TEXT DEFAULT '',
                motherId INTEGER DEFAULT 0,
                fatherId INTEGER DEFAULT 0,
                childrenIds TEXT DEFAULT '[]',
                spouseId INTEGER DEFAULT 0,
                born_day INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )

        # Ensure defaults exist
        _ensure_world_defaults(conn)
        _ensure_bank_defaults(conn)
        _ensure_villagers_columns(conn)
        _ensure_yearly_columns(conn)
        _ensure_graveyard_columns(conn)

def _ensure_villagers_columns(conn: sqlite3.Connection):
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(villagers);").fetchall()}

    # Build desired column definitions exactly like init_db does
    desired = {}
    for f in FIELDNAMES:
        if f == "id":
            continue  # already PK
        if f in INT_FIELDS:
            desired[f] = f"{f} INTEGER DEFAULT 0"
        else:
            desired[f] = f"{f} TEXT DEFAULT ''"

    # Add missing columns
    for col, ddl in desired.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE villagers ADD COLUMN {ddl};")

def _ensure_world_defaults(conn: sqlite3.Connection):
    cur = conn.execute("SELECT value FROM world_state WHERE key='day_payload' LIMIT 1;")
    row = cur.fetchone()
    if row is None:
        payload = {
            "total_day": 1,
            "year": 1,
            "day_in_year": 0,
            "weather": "sunny",
            "next_weather_roll_day": 1,  # will roll on day 1
        }
        conn.execute(
            "INSERT INTO world_state(key, value) VALUES(?, ?);",
            ("day_payload", json.dumps(payload)),
        )

def load_world_payload() -> Dict[str, Any]:
    """
    Returns the full world payload stored in world_state.day_payload.
    """
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT value FROM world_state WHERE key='day_payload' LIMIT 1;"
        ).fetchone()
        if not row:
            return {"total_day": 1, "year": 1, "day_in_year": 0, "weather": "sunny", "next_weather_roll_day": 1}
        try:
            data = json.loads(row["value"])
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        # Defaults
        data.setdefault("total_day", 1)
        data.setdefault("year", 1)
        data.setdefault("day_in_year", 0)
        data.setdefault("weather", "sunny")
        data.setdefault("next_weather_roll_day", 1)
        return data


def save_world_payload(payload: Dict[str, Any]):
    """
    Persists the full world payload back to SQLite (world_state.day_payload).
    """
    init_db()
    if not isinstance(payload, dict):
        payload = {}
    total_day = int(payload.get("total_day", 1) or 1)
    if total_day < 1:
        total_day = 1

    year, day_in_year = compute_year_and_day(total_day)
    payload["total_day"] = int(total_day)
    payload["year"] = int(year)
    payload["day_in_year"] = int(day_in_year)

    # Make sure weather keys exist
    payload.setdefault("weather", "sunny")
    payload.setdefault("next_weather_roll_day", 1)

    with db_conn() as conn:
        conn.execute(
            "UPDATE world_state SET value=? WHERE key='day_payload';",
            (json.dumps(payload, ensure_ascii=False),),
        )


def load_weather() -> str:
    """
    Returns current weather ("sunny" / "rain").
    """
    payload = load_world_payload()
    w = (payload.get("weather") or "sunny").strip().lower()
    return w if w in WEATHER_TYPES else "sunny"


def maybe_roll_weather(current_day: int) -> str:
    """
    Roll weather if we've reached the scheduled roll day.
    Weather is persisted so it won't change randomly between requests.
    """
    payload = load_world_payload()

    day = int(current_day or payload.get("total_day", 1) or 1)
    if day < 1:
        day = 1

    next_roll = int(payload.get("next_weather_roll_day", 1) or 1)
    weather = (payload.get("weather") or "sunny").strip().lower()
    if weather not in WEATHER_TYPES:
        weather = "sunny"

    # If it's not time yet, keep current weather
    if day < next_roll:
        return weather

    # Roll new weather
    import random as _random
    weather = "rain" if _random.random() < float(WEATHER_RAIN_CHANCE) else "sunny"

    # Schedule next roll
    next_roll = day + int(WEATHER_CHANGE_DAYS or 5)
    payload["weather"] = weather
    payload["next_weather_roll_day"] = next_roll
    payload["total_day"] = day  # keep consistent

    save_world_payload(payload)
    return weather

def _ensure_bank_defaults(conn: sqlite3.Connection):
    cur = conn.execute("SELECT value FROM bank_state WHERE key='bank_payload' LIMIT 1;")
    row = cur.fetchone()
    if row is None:
        payload = {
            "tax_rate": 0.10,
            "balance": 0,
            "building_levels": {},
            "building_health": {},
            "last_election_year": None,
            "last_election_message": "",
            "year_stats": {},
            "yearly_history": [],
        }
        conn.execute(
            "INSERT INTO bank_state(key, value) VALUES(?, ?);",
            ("bank_payload", json.dumps(payload)),
        )

def _ensure_yearly_columns(conn: sqlite3.Connection):
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(yearly_stats);").fetchall()}

    desired = {
        "most_atk_id": "most_atk_id INTEGER",
        "most_atk_name": "most_atk_name TEXT DEFAULT ''",
        "most_atk_value": "most_atk_value INTEGER DEFAULT 0",

        "most_int_id": "most_int_id INTEGER",
        "most_int_name": "most_int_name TEXT DEFAULT ''",
        "most_int_value": "most_int_value INTEGER DEFAULT 0",

        "richest_id": "richest_id INTEGER",
        "richest_name": "richest_name TEXT DEFAULT ''",
        "richest_value": "richest_value INTEGER DEFAULT 0",

        "top_hunter_id": "top_hunter_id INTEGER",
        "top_hunter_name": "top_hunter_name TEXT DEFAULT ''",
        "top_hunter_value": "top_hunter_value INTEGER DEFAULT 0",
    }

    for col, ddl in desired.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE yearly_stats ADD COLUMN {ddl};")

def _ensure_graveyard_columns(conn: sqlite3.Connection):
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(graveyard);").fetchall()}
    desired = {
        "name": "name TEXT DEFAULT ''",
        "family": "family TEXT DEFAULT ''",
        "gender": "gender TEXT DEFAULT ''",
        "traits": "traits TEXT DEFAULT ''",
        "origin": "origin TEXT DEFAULT ''",
        "owner": "owner TEXT DEFAULT ''",
        "motherId": "motherId INTEGER DEFAULT 0",
        "fatherId": "fatherId INTEGER DEFAULT 0",
        "childrenIds": "childrenIds TEXT DEFAULT '[]'",
        "spouseId": "spouseId INTEGER DEFAULT 0",
        "born_day": "born_day INTEGER DEFAULT 0",
        "created_at": "created_at TEXT DEFAULT (datetime('now'))",
    }
    for col, ddl in desired.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE graveyard ADD COLUMN {ddl};")

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
        columns = list(FIELDNAMES)
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

            values = [r2.get(c, "" if c not in INT_FIELDS else 0) for c in columns]
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
            for key in INT_FIELDS:
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


# Backward-compatible aliases (so you don’t have to update all imports at once)
save_to_csv = save_villagers
load_from_csv = load_villagers


# ---------------------------------------------------------------------------
#  Users (replaces users.csv)
# ---------------------------------------------------------------------------

def load_users() -> List[Dict[str, Any]]:
    init_db()
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT username, email, password_hash FROM users ORDER BY created_at DESC;"
        )
        return [dict(r) for r in cur.fetchall()]


def save_user(username: str, email: str, password_plain: str):
    """
    Insert a single user into SQLite with hashed password.
    Enforces unique username via PRIMARY KEY.
    """
    init_db()
    password_hash = generate_password_hash(password_plain)

    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO users(username, email, password_hash)
            VALUES(?, ?, ?);
            """,
            (username, email, password_hash),
        )


# ---------------------------------------------------------------------------
#  Day / World time (replaces day.txt)
# ---------------------------------------------------------------------------

def compute_year_and_day(total_day: int):
    if total_day < 1:
        total_day = 1
    year_index = (total_day - 1) // DAYS_PER_YEAR
    year = year_index + 1
    day_in_year = (total_day - 1) % DAYS_PER_YEAR
    return year, day_in_year


def load_day() -> int:
    """
    Read world time from SQLite (day_payload JSON).
    Returns total_day (>=1)
    """
    init_db()
    with db_conn() as conn:
        cur = conn.execute("SELECT value FROM world_state WHERE key='day_payload' LIMIT 1;")
        row = cur.fetchone()
        if not row:
            return 1
        try:
            payload = json.loads(row["value"])
            return max(1, int(payload.get("total_day", 1)))
        except Exception:
            return 1


def save_day(day: int):
    init_db()
    if day < 1:
        day = 1
    year, day_in_year = compute_year_and_day(day)

    # Load existing payload
    payload = load_world_payload()
    
    # Update day
    payload["total_day"] = int(day)
    year, day_in_year = compute_year_and_day(day)
    payload["year"] = int(year)
    payload["day_in_year"] = int(day_in_year)
    
    # Roll weather BEFORE saving (avoid stale reads)
    weather_today = _roll_weather_if_needed(day, payload)  # New helper
    payload["weather"] = weather_today
    
    save_world_payload(payload)

def _roll_weather_if_needed(current_day: int, payload: dict) -> str:
    """Internal helper to roll weather based on current payload."""
    day = int(current_day or payload.get("total_day", 1) or 1)
    next_roll = int(payload.get("next_weather_roll_day", 1) or 1)
    weather = (payload.get("weather") or "sunny").strip().lower()
    
    if day < next_roll:
        return weather
    
    # Roll new weather
    import random as _random
    weather = "rain" if _random.random() < float(WEATHER_RAIN_CHANCE) else "sunny"
    
    # Schedule next roll
    payload["next_weather_roll_day"] = day + int(WEATHER_CHANGE_DAYS or 5)
    return weather

# Simplify maybe_roll_weather to just read
def maybe_roll_weather(current_day: int) -> str:
    """Read current weather (rolling happens in save_day)."""
    return load_weather()

# ---------------------------------------------------------------------------
#  Bank (replaces bank.json)
# ---------------------------------------------------------------------------

def load_bank():
    init_db()
    with db_conn() as conn:
        cur = conn.execute("SELECT value FROM bank_state WHERE key='bank_payload' LIMIT 1;")
        row = cur.fetchone()
        if not row:
            return {
                "tax_rate": 0.10,
                "balance": 0,
                "building_levels": {},
                "building_health": {},
                "last_election_year": None,
                "last_election_message": "",
                "year_stats": {},
                "yearly_history": [],
            }

        try:
            data = json.loads(row["value"])
        except Exception:
            data = {}

        # existing fields...
        rate = max(0.0, min(0.35, float(data.get("tax_rate", 0.10) or 0.10)))
        bal = int(data.get("balance", 0) or 0)

        levels = data.get("building_levels") or {}
        health = data.get("building_health") or {}
        if not isinstance(levels, dict): levels = {}
        if not isinstance(health, dict): health = {}

        year_stats = data.get("year_stats") or {}
        if not isinstance(year_stats, dict):
            year_stats = {}

        yearly_history = data.get("yearly_history") or []
        if not isinstance(yearly_history, list):
            yearly_history = []

        return {
            "tax_rate": rate,
            "balance": bal,
            "building_levels": levels,
            "building_health": health,
            "last_election_year": data.get("last_election_year"),
            "last_election_message": data.get("last_election_message", ""),
            "year_stats": year_stats,
            "yearly_history": yearly_history,
        }


def save_bank(bank: dict):
    init_db()

    year_stats = bank.get("year_stats")
    if not isinstance(year_stats, dict):
        year_stats = {}

    yearly_history = bank.get("yearly_history")
    if not isinstance(yearly_history, list):
        yearly_history = []

    data = {
        "tax_rate": float(bank.get("tax_rate", 0.10)),
        "balance": int(bank.get("balance", 0)),
        "building_levels": bank.get("building_levels") if isinstance(bank.get("building_levels"), dict) else {},
        "building_health": bank.get("building_health") if isinstance(bank.get("building_health"), dict) else {},
        "last_election_year": bank.get("last_election_year"),
        "last_election_message": bank.get("last_election_message", ""),
        "year_stats": year_stats,
        "yearly_history": yearly_history,
    }

    with db_conn() as conn:
        conn.execute(
            "UPDATE bank_state SET value=? WHERE key='bank_payload';",
            (json.dumps(data, ensure_ascii=False),),
        )


# ---------------------------------------------------------------------------
#  OPTIONAL: one-time migration from existing CSV/JSON into SQLite
# ---------------------------------------------------------------------------

def migrate_legacy_files_to_sqlite():
    """
    Runs safe one-time migrations if old files exist.
    - characters.csv -> villagers table
    - users.csv -> users table
    - day.txt -> world_state.day_payload
    - bank.json -> bank_state.bank_payload

    You can call this once at startup then delete it later.
    """
    init_db()

    # 1) villagers from CSV
    if os.path.exists(CSV_PATH):
        try:
            import csv as _csv

            rows = []
            with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
                reader = _csv.DictReader(f)
                for r in reader:
                    rows.append(dict(r))

            # Convert types similarly to old loader
            normalized = []
            for r in rows:
                r2 = dict(r)
                for key in INT_FIELDS:
                    val = r2.get(key)
                    try:
                        r2[key] = int(val) if val not in (None, "") else 0
                    except Exception:
                        r2[key] = 0

                r2["alive"] = str(r2.get("alive", "true")).lower() == "true"
                try:
                    r2["childrenIds"] = json.loads(r2.get("childrenIds") or "[]")
                except Exception:
                    r2["childrenIds"] = []
                try:
                    rels = json.loads(r2.get("relationships") or "{}")
                    r2["relationships"] = rels if isinstance(rels, dict) else {}
                except Exception:
                    r2["relationships"] = {}

                r2.setdefault("last_action", "")
                r2.setdefault("owner", "")
                r2.setdefault("action_log", "")
                normalized.append(r2)

            save_villagers(normalized)
        except Exception:
            pass

    # 2) users from users.csv
    if os.path.exists(USERS_CSV):
        try:
            import csv as _csv

            with open(USERS_CSV, "r", newline="", encoding="utf-8") as f:
                reader = _csv.DictReader(f)
                with db_conn() as conn:
                    for row in reader:
                        u = (row.get("username") or "").strip()
                        if not u:
                            continue
                        email = row.get("email") or ""
                        pw = row.get("password_hash") or ""
                        # Insert if missing
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO users(username, email, password_hash)
                            VALUES(?, ?, ?);
                            """,
                            (u, email, pw),
                        )
        except Exception:
            pass

    # 3) day.txt -> sqlite
    if os.path.exists(DAY_PATH):
        try:
            with open(DAY_PATH, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        total_day = int(data.get("total_day", 1))
                    else:
                        total_day = int(data)
                except Exception:
                    total_day = int(text)

                save_day(max(1, total_day))
        except Exception:
            pass

    # 4) bank.json -> sqlite
    if os.path.exists(BANK_PATH):
        try:
            with open(BANK_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                save_bank(data)
        except Exception:
            pass

def clear_yearly_stats():
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM yearly_stats;")


def get_year_entry(year: int):
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM yearly_stats WHERE year=? LIMIT 1;",
            (int(year),),
        ).fetchone()
        return dict(row) if row else None


def list_yearly_history(finalized_only: bool = True):
    init_db()
    where = "WHERE is_finalized=1" if finalized_only else ""
    with db_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM yearly_stats {where} ORDER BY year DESC;"
        ).fetchall()
        return [dict(r) for r in rows]


def ensure_year_row(year: int, treasury_start: int | None = None):
    init_db()
    with db_conn() as conn:
        # Insert row if missing
        conn.execute(
            """
            INSERT OR IGNORE INTO yearly_stats(year)
            VALUES(?);
            """,
            (int(year),),
        )

        # Set treasury_start once (if provided and still NULL)
        if treasury_start is not None:
            conn.execute(
                """
                UPDATE yearly_stats
                SET treasury_start = COALESCE(treasury_start, ?),
                    updated_at = datetime('now')
                WHERE year = ?;
                """,
                (int(treasury_start), int(year)),
            )


def update_year_daily(
    year: int,
    king_id: int | None,
    king_name: str | None,
    deaths_today: int,
    immigrants_today: int,
    tax_rate_today: float,
    treasury_end: int,
):
    init_db()
    with db_conn() as conn:
        # Ensure exists
        conn.execute("INSERT OR IGNORE INTO yearly_stats(year) VALUES(?);", (int(year),))

        # Update rollup
        conn.execute(
            """
            UPDATE yearly_stats
            SET
                king_id = COALESCE(?, king_id),
                king_name = COALESCE(?, king_name),
                total_deaths = COALESCE(total_deaths, 0) + ?,
                total_immigrants = COALESCE(total_immigrants, 0) + ?,
                tax_rate_sum = COALESCE(tax_rate_sum, 0) + ?,
                days_counted = COALESCE(days_counted, 0) + 1,
                treasury_end = ?,
                updated_at = datetime('now')
            WHERE year = ?;
            """,
            (
                int(king_id) if king_id else None,
                king_name if king_name else None,
                int(deaths_today),
                int(immigrants_today),
                float(tax_rate_today),
                int(treasury_end),
                int(year),
            ),
        )


def finalize_year(year: int, champions: dict | None = None):
    """
    Finalize a year:
    - compute avg tax rate
    - mark row finalized
    - optionally store champions snapshot (most_atk, most_int, richest, top_hunter)
    champions format example:
      {
        "most_atk": {"id": 12, "name": "A", "value": 31},
        "most_int": {"id": 5, "name": "B", "value": 29},
        "richest": {"id": 7, "name": "C", "value": 120},
        "top_hunter": {"id": 9, "name": "D", "value": 4}
      }
    """
    init_db()

    def _pick(ch: dict | None, key: str):
        if not isinstance(ch, dict):
            return (None, "", 0)
        d = ch.get(key) or {}
        if not isinstance(d, dict):
            return (None, "", 0)

        cid = d.get("id")
        try:
            cid = int(cid) if cid is not None else None
        except Exception:
            cid = None

        name = (d.get("name") or "").strip()
        try:
            val = int(d.get("value", 0) or 0)
        except Exception:
            val = 0

        return (cid, name, val)

    with db_conn() as conn:
        row = conn.execute(
            "SELECT tax_rate_sum, days_counted FROM yearly_stats WHERE year=?;",
            (int(year),),
        ).fetchone()
        if not row:
            return

        tax_sum = float(row["tax_rate_sum"] or 0.0)
        days = int(row["days_counted"] or 0)
        avg_tax = (tax_sum / days) if days > 0 else None

        # No champions passed → keep old behavior
        if champions is None:
            conn.execute(
                """
                UPDATE yearly_stats
                SET avg_tax_rate = ?,
                    is_finalized = 1,
                    updated_at = datetime('now')
                WHERE year = ?;
                """,
                (avg_tax, int(year)),
            )
            return

        most_atk_id, most_atk_name, most_atk_value = _pick(champions, "most_atk")
        most_int_id, most_int_name, most_int_value = _pick(champions, "most_int")
        richest_id, richest_name, richest_value = _pick(champions, "richest")
        top_hunter_id, top_hunter_name, top_hunter_value = _pick(champions, "top_hunter")

        conn.execute(
            """
            UPDATE yearly_stats
            SET avg_tax_rate = ?,
                is_finalized = 1,

                most_atk_id = ?,
                most_atk_name = ?,
                most_atk_value = ?,

                most_int_id = ?,
                most_int_name = ?,
                most_int_value = ?,

                richest_id = ?,
                richest_name = ?,
                richest_value = ?,

                top_hunter_id = ?,
                top_hunter_name = ?,
                top_hunter_value = ?,

                updated_at = datetime('now')
            WHERE year = ?;
            """,
            (
                avg_tax,

                most_atk_id, most_atk_name, most_atk_value,
                most_int_id, most_int_name, most_int_value,
                richest_id, richest_name, richest_value,
                top_hunter_id, top_hunter_name, top_hunter_value,

                int(year),
            ),
        )

def get_all_time_leader(metric: str, finalized_only: bool = True):
    """
    Return the best (highest value) champion across years for a metric.

    metric: one of
      - "most_atk"
      - "most_int"
      - "richest"
      - "top_hunter"
    """
    init_db()

    mapping = {
        "most_atk": ("most_atk_id", "most_atk_name", "most_atk_value"),
        "most_int": ("most_int_id", "most_int_name", "most_int_value"),
        "richest": ("richest_id", "richest_name", "richest_value"),
        "top_hunter": ("top_hunter_id", "top_hunter_name", "top_hunter_value"),
    }

    if metric not in mapping:
        return None

    id_col, name_col, val_col = mapping[metric]

    where_parts = []
    if finalized_only:
        where_parts.append("is_finalized=1")

    # Only pick meaningful champions (avoid empty rows)
    where_parts.append(f"(COALESCE({val_col}, 0) > 0 OR TRIM(COALESCE({name_col}, '')) <> '')")

    where_sql = "WHERE " + " AND ".join(where_parts)

    with db_conn() as conn:
        row = conn.execute(
            f"""
            SELECT
                year,
                {id_col}   AS id,
                {name_col} AS name,
                {val_col}  AS value
            FROM yearly_stats
            {where_sql}
            ORDER BY COALESCE({val_col}, 0) DESC, year DESC
            LIMIT 1;
            """
        ).fetchone()

        return dict(row) if row else None


def get_all_time_leaders(finalized_only: bool = True):
    """
    Convenience wrapper returning all metrics in one dict.
    """
    return {
        "most_atk": get_all_time_leader("most_atk", finalized_only=finalized_only),
        "most_int": get_all_time_leader("most_int", finalized_only=finalized_only),
        "richest": get_all_time_leader("richest", finalized_only=finalized_only),
        "top_hunter": get_all_time_leader("top_hunter", finalized_only=finalized_only),
    }


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