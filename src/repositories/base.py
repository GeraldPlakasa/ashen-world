from __future__ import annotations

import os
import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator

import config

def _ensure_data_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
#  Connection pooling: one persistent connection per thread
# ---------------------------------------------------------------------------

_local = threading.local()

def _get_persistent_conn() -> sqlite3.Connection:
    """
    Return a persistent SQLite connection for the current thread.
    Reuses the same connection across calls instead of open/close every time.
    """
    conn = getattr(_local, "conn", None)
    db_path = getattr(_local, "db_path", None)

    # Reconnect if path changed (e.g. tests monkeypatch config.DB_PATH)
    if conn is not None and db_path == config.DB_PATH:
        try:
            conn.execute("SELECT 1")
            return conn
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            # Connection is closed or broken — recreate
            pass

    _ensure_data_dir()
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    _local.conn = conn
    _local.db_path = config.DB_PATH
    return conn


def close_thread_conn() -> None:
    """Close the persistent connection for the current thread (for cleanup/tests)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        _local.db_path = None


@contextmanager
def db_conn() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for SQLite connection.
    Reuses a thread-local persistent connection for performance.
    """
    conn = _get_persistent_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
#  Schema initialization (cached — runs once per DB path)
# ---------------------------------------------------------------------------

_init_done_for: str | None = None
_init_lock = threading.Lock()


def reset_init_cache() -> None:
    """Reset the init_db cache so it re-runs on next call. Used by tests."""
    global _init_done_for
    with _init_lock:
        _init_done_for = None
    close_thread_conn()


def init_db(force: bool = False):
    """
    Create tables if they don't exist.
    Cached: only runs once per DB path unless force=True or reset_init_cache() is called.
    """
    global _init_done_for
    if not force and _init_done_for == config.DB_PATH:
        return
    with _init_lock:
        # Double-check inside the lock
        if not force and _init_done_for == config.DB_PATH:
            return
        _init_db_impl()
        _init_done_for = config.DB_PATH


def _init_db_impl():
    """Actual schema creation logic (called once by init_db)."""
    with db_conn() as conn:
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
        for f in config.FIELDNAMES:
            if f == "id":
                cols.append("id INTEGER PRIMARY KEY")
            elif f in config.INT_FIELDS:
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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS world_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

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

                -- Corruption tracking
                total_corruption INTEGER DEFAULT 0,
                
                -- Birth tracking
                total_births INTEGER DEFAULT 0,
                
                -- King trait
                king_trait TEXT DEFAULT '',

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

        # Normalized relationship table (replaces JSON in villagers.relationships)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS villager_relationships (
                villager_id INTEGER NOT NULL,
                other_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                PRIMARY KEY (villager_id, other_id)
            );
            """
        )

        # Normalized achievement table (replaces JSON in villagers.achievements)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS villager_achievements (
                villager_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                earned_day INTEGER DEFAULT 0,
                PRIMARY KEY (villager_id, achievement_id)
            );
            """
        )

        # Normalized vote tracking (replaces JSON in villagers.kingsVotedFor)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS villager_votes (
                villager_id INTEGER NOT NULL,
                king_id INTEGER NOT NULL,
                vote_day INTEGER DEFAULT 0,
                PRIMARY KEY (villager_id, king_id)
            );
            """
        )

        # Event history table (persistent, replaces in-memory list)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                day INTEGER NOT NULL,
                year INTEGER NOT NULL,
                details TEXT DEFAULT '',
                affected_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )

        # Site statistics tracking (page views, char creations, etc.)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS site_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_type TEXT NOT NULL,
                stat_date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                UNIQUE(stat_type, stat_date)
            );
            """
        )

        _ensure_world_defaults(conn)
        _ensure_bank_defaults(conn)
        _ensure_villagers_columns(conn)
        _ensure_yearly_columns(conn)
        _ensure_graveyard_columns(conn)
        _ensure_event_history_columns(conn)
        _ensure_indexes(conn)


def _ensure_indexes(conn: sqlite3.Connection):
    """Create indexes for common queries to improve performance."""
    # Index on villagers.alive for filtering living villagers
    conn.execute("CREATE INDEX IF NOT EXISTS idx_villagers_alive ON villagers(alive);")
    # Index on villagers.owner for player character lookups
    conn.execute("CREATE INDEX IF NOT EXISTS idx_villagers_owner ON villagers(owner);")
    # Index on villagers.family for family tree queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_villagers_family ON villagers(family);")
    # Index on graveyard.family for family tree queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graveyard_family ON graveyard(family);")
    # Indexes for normalized relationship/achievement/vote tables
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vr_villager ON villager_relationships(villager_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vr_other ON villager_relationships(other_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_va_villager ON villager_achievements(villager_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vv_villager ON villager_votes(villager_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vv_king ON villager_votes(king_id);")
    # Event history indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eh_year ON event_history(year);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eh_type ON event_history(event_type);")
    # Site stats indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ss_type_date ON site_stats(stat_type, stat_date);")

def _ensure_villagers_columns(conn: sqlite3.Connection):
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(villagers);").fetchall()}

    # Build desired column definitions exactly like init_db does
    desired = {}
    for f in config.FIELDNAMES:
        if f == "id":
            continue  # already PK
        if f in config.INT_FIELDS:
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
        "total_corruption": "total_corruption INTEGER DEFAULT 0",
        "total_births": "total_births INTEGER DEFAULT 0",
        "king_trait": "king_trait TEXT DEFAULT ''",
        
        # Emergency election tracking
        "emergency_elections": "emergency_elections INTEGER DEFAULT 0",
        
        # Wealthiest family tracking
        "wealthiest_family": "wealthiest_family TEXT DEFAULT ''",
        "wealthiest_family_coins": "wealthiest_family_coins INTEGER DEFAULT 0",

        # Population snapshot at end of each day (latest value = year-end population)
        "population_end": "population_end INTEGER DEFAULT 0",

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

def _ensure_event_history_columns(conn: sqlite3.Connection):
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(event_history);").fetchall()}
    desired = {
        "king_name": "king_name TEXT DEFAULT ''",
    }
    for col, ddl in desired.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE event_history ADD COLUMN {ddl};")

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
        "death_day": "death_day INTEGER DEFAULT 0",
        "created_at": "created_at TEXT DEFAULT (datetime('now'))",
    }
    for col, ddl in desired.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE graveyard ADD COLUMN {ddl};")
