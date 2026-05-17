"""
Main routes: Landing page and features.
"""
from flask import Blueprint, render_template, session

from src.services.world_service import get_current_state
from src.services.character_service import get_pinned_character_data
from src.services.building_service import build_building_summary
from src.repositories.chronicle_repo import list_top_recent

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def landing():
    """
    Landing page (dashboard):
    - Shows current world time (year / day)
    - Simple KPIs (villagers total, alive, dead)
    - Read-only table of villagers
    - Shows pinned character for logged-in user (if any).
    """
    characters, village_bank, year, day_in_year, total_day, weather = get_current_state()

    total = len(characters)
    alive_count = sum(1 for c in characters if c.get("alive", True))
    dead_count = total - alive_count

    username = session.get("username")

    bank_balance = village_bank.get("balance", 0)
    tax_rate = village_bank.get("tax_rate", 0.10)
    village_resources = village_bank.get("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
    last_election_year = village_bank.get("last_election_year")
    last_election_message = village_bank.get("last_election_message", "")
    last_event_message = village_bank.get("last_event_message", "")
    last_event_day = village_bank.get("last_event_day")
    # Hide festival headlines from the Recent News widget — they crowd out the
    # signal events (plague, famine, invasion). Festivals still chronicle.
    if last_event_message and "FESTIVAL" in last_event_message.upper():
        last_event_message = ""
        last_event_day = None
    last_quest_message = village_bank.get("last_quest_message", "")
    last_quest_day = village_bank.get("last_quest_day")
    last_quest_success = village_bank.get("last_quest_success")
    last_quest_type = village_bank.get("last_quest_type", "")
    last_quest_name = village_bank.get("last_quest_name", "")
    last_quest_desc = village_bank.get("last_quest_desc", "")

    village_buildings = build_building_summary(village_bank)

    pinned_data = get_pinned_character_data(username, characters)

    try:
        # Pull a few extra so we still have ~5 after filtering out weddings.
        raw_headlines = list_top_recent(limit=12, min_importance=3)
        # Weddings are noisy (~10+ per year in a healthy village); they stay
        # in the full Chronicle but don't belong on the landing widget.
        chronicle_headlines = [
            h for h in raw_headlines
            if "are wed" not in (h.get("headline") or "").lower()
        ][:5]
    except Exception:
        chronicle_headlines = []

    pinned_character = pinned_data["character"] if pinned_data else None
    # Equipped artifacts now render via /api/character/<id> on the JS side
    # so they update for whichever villager the user inspects, not just the player.
    pinned_actions = pinned_data["actions"] if pinned_data else []
    pinned_rel_bonds = pinned_data["rel_bonds"] if pinned_data else []
    pinned_rel_conflicts = pinned_data["rel_conflicts"] if pinned_data else []
    pinned_spouse_name = pinned_data["spouse_name"] if pinned_data else None
    pinned_spouse_alive = pinned_data["spouse_alive"] if pinned_data else None
    pinned_mother = pinned_data["mother"] if pinned_data else None
    pinned_father = pinned_data["father"] if pinned_data else None
    pinned_children = pinned_data["children"] if pinned_data else []

    return render_template(
        "landing.html",
        characters=characters,
        day=day_in_year,
        year=year,
        total_day=total_day,
        total_villagers=total,
        alive_count=alive_count,
        dead_count=dead_count,
        active_page="dashboard",
        username=username,
        pinned_character=pinned_character,
        bank_balance=bank_balance,
        tax_rate=tax_rate,
        village_resources=village_resources,
        pinned_actions=pinned_actions,
        village_buildings=village_buildings,
        pinned_rel_bonds=pinned_rel_bonds,
        pinned_rel_conflicts=pinned_rel_conflicts,
        last_election_year=last_election_year,
        last_election_message=last_election_message,
        last_event_message=last_event_message,
        last_event_day=last_event_day,
        last_quest_message=last_quest_message,
        last_quest_day=last_quest_day,
        last_quest_success=last_quest_success,
        last_quest_type=last_quest_type,
        last_quest_name=last_quest_name,
        last_quest_desc=last_quest_desc,
        pinned_spouse_name=pinned_spouse_name,
        pinned_spouse_alive=pinned_spouse_alive,
        pinned_mother=pinned_mother,
        pinned_father=pinned_father,
        pinned_children=pinned_children,
        weather_today=weather,
        chronicle_headlines=chronicle_headlines,
    )


@main_bp.route("/features", methods=["GET"])
def features():
    """Static feature showcase page."""
    _, _, year, day_in_year, _, weather = get_current_state()

    return render_template(
        "features.html",
        active_page="features",
        username=session.get("username"),
        year=year,
        day=day_in_year,
    )
