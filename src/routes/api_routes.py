"""
API routes: JSON endpoints for frontend.
"""
from flask import Blueprint, jsonify

from src.services.world_service import get_current_state
from src.services.family_tree_service import build_graveyard_index_for
from src.services.building_service import build_building_summary

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/state", methods=["GET"])
def api_state():
    """
    JSON API that returns the current world time + characters
    WITHOUT advancing the simulation.

    Now also returns village bank + building info so the admin
    auto-refresh can update KPI and buildings card.
    """
    characters, bank, year, day_in_year, total_day, weather = get_current_state()
    graveyard_index = build_graveyard_index_for(characters)
    buildings_payload = build_building_summary(bank, include_health=True)

    return jsonify({
        "ok": True,
        "message": "Current state",
        "year": year,
        "day": day_in_year,
        "total_day": total_day,
        "characters": characters,
        "graveyard_index": graveyard_index,
        "bank_balance": bank.get("balance", 0),
        "tax_rate": bank.get("tax_rate", 0.10),
        "buildings": buildings_payload,
        "last_election_year": bank.get("last_election_year"),
        "last_election_message": bank.get("last_election_message", ""),
        "last_event_message": bank.get("last_event_message", ""),
        "last_event_day": bank.get("last_event_day"),
        "last_quest_message": bank.get("last_quest_message", ""),
        "last_quest_day": bank.get("last_quest_day"),
        "last_quest_success": bank.get("last_quest_success"),
        "weather": weather,
    })
