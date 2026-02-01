from __future__ import annotations

import os
import json

import config
from src.repositories.base import db_conn, init_db
from src.models.stats import AllTimeLeader, YearlyChampions, YearStats

def clear_yearly_stats() -> None:
    """Delete all rows from the yearly_stats table."""
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM yearly_stats;")


def get_year_entry(year: int) -> YearStats | None:
    """Retrieve the stats record for a specific year, or None."""
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM yearly_stats WHERE year=? LIMIT 1;",
            (int(year),),
        ).fetchone()
        return dict(row) if row else None


def list_yearly_history(finalized_only: bool = True) -> list[YearStats]:
    """Return yearly stats records, optionally filtered to finalized years only."""
    init_db()
    where = "WHERE is_finalized=1" if finalized_only else ""
    with db_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM yearly_stats {where} ORDER BY year DESC;"
        ).fetchall()
        return [dict(r) for r in rows]


def ensure_year_row(year: int, treasury_start: int | None = None) -> None:
    """Ensure a yearly_stats row exists for the given year, inserting one if missing."""
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
    """Accumulate daily stats (deaths, immigrants, tax) into the yearly_stats row for a year."""
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


def finalize_year(year: int, champions: YearlyChampions | None = None) -> None:
    """
    Finalize a year:
    - compute avg tax rate
    - mark row finalized
    - optionally store champions snapshot (most_atk, most_int, richest, top_hunter)
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

        # No champions passed -> keep old behavior
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

def get_all_time_leader(metric: str, finalized_only: bool = True) -> AllTimeLeader | None:
    """
    Return the best (highest value) champion across years for a metric.
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


def get_all_time_leaders(finalized_only: bool = True) -> dict[str, AllTimeLeader | None]:
    """
    Convenience wrapper returning all metrics in one dict.
    """
    return {
        "most_atk": get_all_time_leader("most_atk", finalized_only=finalized_only),
        "most_int": get_all_time_leader("most_int", finalized_only=finalized_only),
        "richest": get_all_time_leader("richest", finalized_only=finalized_only),
        "top_hunter": get_all_time_leader("top_hunter", finalized_only=finalized_only),
    }


# ---------------------------------------------------------------------------
#  OPTIONAL: one-time migration from existing CSV/JSON into SQLite
# ---------------------------------------------------------------------------

def migrate_legacy_files_to_sqlite():
    """
    Runs safe one-time migrations if old files exist.
    """
    from src.repositories.villager_repo import save_villagers
    from src.repositories.world_repo import save_day
    from src.repositories.bank_repo import save_bank
    from src.repositories.base import db_conn

    init_db()

    # 1) villagers from CSV
    if os.path.exists(config.CSV_PATH):
        try:
            import csv as _csv

            rows = []
            with open(config.CSV_PATH, "r", newline="", encoding="utf-8") as f:
                reader = _csv.DictReader(f)
                for r in reader:
                    rows.append(dict(r))

            # Convert types similarly to old loader
            normalized = []
            for r in rows:
                r2 = dict(r)
                for key in config.INT_FIELDS:
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
    if os.path.exists(config.USERS_CSV):
        try:
            import csv as _csv

            with open(config.USERS_CSV, "r", newline="", encoding="utf-8") as f:
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
    if os.path.exists(config.DAY_PATH):
        try:
            with open(config.DAY_PATH, "r", encoding="utf-8") as f:
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
    if os.path.exists(config.BANK_PATH):
        try:
            with open(config.BANK_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                save_bank(data)
        except Exception:
            pass
