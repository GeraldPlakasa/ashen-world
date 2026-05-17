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
                "resources": {"food": 0, "wood": 0, "stone": 0, "iron": 0},
                "building_levels": {},
                "building_health": {},
                "last_election_year": None,
                "last_election_message": "",
                "last_event_message": "",
                "last_event_day": None,
                "last_event_year_tracking": 0,
                "event_day_for_year": None,
                "event_triggered_this_year": False,
                # Quest tracking
                "last_quest_year": 0,
                "quest_day_for_year": None,
                "quest_triggered_this_year": False,
                "last_quest_message": "",
                "last_quest_day": None,
                "last_quest_type": None,
                "last_quest_success": None,
                "quest_history": [],
                "pending_crimes": [],
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

        resources = data.get("resources") or {}
        if not isinstance(resources, dict):
            resources = {}
        for r in ("food", "wood", "stone", "iron"):
            resources[r] = int(resources.get(r, 0) or 0)

        year_stats = data.get("year_stats") or {}
        if not isinstance(year_stats, dict):
            year_stats = {}

        yearly_history = data.get("yearly_history") or []
        if not isinstance(yearly_history, list):
            yearly_history = []

        return {
            "tax_rate": rate,
            "balance": bal,
            "resources": resources,
            "building_levels": levels,
            "building_health": health,
            # Election tracking
            "last_election_year": data.get("last_election_year"),
            "last_election_message": data.get("last_election_message", ""),
            # Event tracking
            "last_event_message": data.get("last_event_message", ""),
            "last_event_day": data.get("last_event_day"),
            "last_event_year_tracking": data.get("last_event_year_tracking", 0),
            "event_day_for_year": data.get("event_day_for_year"),
            "event_triggered_this_year": data.get("event_triggered_this_year", False),
            # Quest tracking
            "last_quest_year": data.get("last_quest_year", 0),
            "quest_day_for_year": data.get("quest_day_for_year"),
            "quest_triggered_this_year": data.get("quest_triggered_this_year", False),
            "last_quest_message": data.get("last_quest_message", ""),
            "last_quest_day": data.get("last_quest_day"),
            "last_quest_type": data.get("last_quest_type"),
            "last_quest_success": data.get("last_quest_success"),
            "last_quest_name": data.get("last_quest_name", ""),
            "last_quest_desc": data.get("last_quest_desc", ""),
            "quest_history": data.get("quest_history", []) if isinstance(data.get("quest_history"), list) else [],
            "pending_crimes": data.get("pending_crimes", []) if isinstance(data.get("pending_crimes"), list) else [],
            # Stats
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

    raw_resources = bank.get("resources") if isinstance(bank.get("resources"), dict) else {}
    resources = {
        "food":  int(raw_resources.get("food",  0) or 0),
        "wood":  int(raw_resources.get("wood",  0) or 0),
        "stone": int(raw_resources.get("stone", 0) or 0),
        "iron":  int(raw_resources.get("iron",  0) or 0),
    }

    data = {
        "tax_rate": float(bank.get("tax_rate", 0.10)),
        "balance": int(bank.get("balance", 0)),
        "resources": resources,
        "building_levels": bank.get("building_levels") if isinstance(bank.get("building_levels"), dict) else {},
        "building_health": bank.get("building_health") if isinstance(bank.get("building_health"), dict) else {},
        # Election tracking
        "last_election_year": bank.get("last_election_year"),
        "last_election_message": bank.get("last_election_message", ""),
        # Event tracking
        "last_event_message": bank.get("last_event_message", ""),
        "last_event_day": bank.get("last_event_day"),
        "last_event_year_tracking": bank.get("last_event_year_tracking", 0),
        "event_day_for_year": bank.get("event_day_for_year"),
        "event_triggered_this_year": bank.get("event_triggered_this_year", False),
        # Quest tracking
        "last_quest_year": bank.get("last_quest_year", 0),
        "quest_day_for_year": bank.get("quest_day_for_year"),
        "quest_triggered_this_year": bank.get("quest_triggered_this_year", False),
        "last_quest_message": bank.get("last_quest_message", ""),
        "last_quest_day": bank.get("last_quest_day"),
        "last_quest_type": bank.get("last_quest_type"),
        "last_quest_success": bank.get("last_quest_success"),
        "last_quest_name": bank.get("last_quest_name", ""),
        "last_quest_desc": bank.get("last_quest_desc", ""),
        "quest_history": bank.get("quest_history", []) if isinstance(bank.get("quest_history"), list) else [],
        "pending_crimes": bank.get("pending_crimes", []) if isinstance(bank.get("pending_crimes"), list) else [],
        # Stats
        "year_stats": year_stats,
        "yearly_history": yearly_history,
    }

    with db_conn() as conn:
        conn.execute(
            "UPDATE bank_state SET value=? WHERE key='bank_payload';",
            (json.dumps(data, ensure_ascii=False),),
        )
