from __future__ import annotations

import json

from src.repositories.base import db_conn, init_db
from src.models.bank import Bank

def load_bank() -> Bank:
    """Load the village bank state from SQLite, returning defaults if no data exists."""
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
            "last_event_message": data.get("last_event_message", ""),
            "last_event_day": data.get("last_event_day"),
            "year_stats": year_stats,
            "yearly_history": yearly_history,
        }


def save_bank(bank: Bank) -> None:
    """Persist the village bank state to SQLite."""
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
        "last_event_message": bank.get("last_event_message", ""),
        "last_event_day": bank.get("last_event_day"),
        "year_stats": year_stats,
        "yearly_history": yearly_history,
    }

    with db_conn() as conn:
        conn.execute(
            "UPDATE bank_state SET value=? WHERE key='bank_payload';",
            (json.dumps(data, ensure_ascii=False),),
        )
