"""
Map routes: top-down stylized village map.
"""
from flask import Blueprint, render_template, session, redirect, url_for

from config import MAP_LAYOUT, MAP_VIEWBOX, BUILDINGS, PRODUCTION_BUILDING_BONUS
from src.services.world_service import get_current_state
from src.services.building_service import get_building_level, build_building_summary

map_bp = Blueprint("map", __name__)


# Static catalog (name + description) per building key. Anything not listed
# falls back to the BUILDINGS list entry from config.
_BUILDING_DESCRIPTIONS = {
    "market":      "Marketplace — boosts trade and reduces buy_food cost",
    "library":     "Library — boosts the study action's INT gain",
    "barracks":    "Barracks — military training, invasion defense",
    "granary":     "Granary — reduces food consumption and starvation impact",
    "clinic":      "Clinic — improves HP recovery and plague resistance",
    "walls":       "City Walls — defensive perimeter against invasions",
    "temple":      "Temple — blessings, morale, magic affinity",
    "blacksmith":  "Blacksmith — gear quality + enables iron→coin conversion at work",
    "treasury":    "Treasury — daily interest on village balance",
    "royal_court": "Royal Court — election influence, +REP for nobles",
    "tax_office":  "Tax Office — tax collection efficiency",
    "tavern":      "Tavern — socialization bonus, hosts visit_tavern",
    "farm":        "Farm — boosts Farmer/Shepherd/Beekeeper yields",
    "lumbermill":  "Lumbermill — boosts Woodcutter/Forester/Carpenter",
    "quarry":      "Quarry — boosts Mason/Miner stone yields",
    "mine":        "Mine — boosts Miner output (+20% per level)",
    "smelter":     "Smelter — boosts Blacksmith iron→coin conversion (+40%/level)",
}


def _job_assignments_by_building(characters: list[dict]) -> dict[str, list[dict]]:
    """For each production building, list villagers whose job benefits from it.
    Returns: { building_key: [{id, name, job, alive}, ...] }
    """
    out: dict[str, list[dict]] = {}
    for b_key, bonus in PRODUCTION_BUILDING_BONUS.items():
        jobs = set(bonus.keys())
        members = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "job": c.get("job"),
                "alive": c.get("alive", True),
            }
            for c in characters
            if c.get("job") in jobs and c.get("alive", True)
        ]
        out[b_key] = members
    return out


@map_bp.route("/map", methods=["GET"])
def map_view():
    """Top-down village map page."""
    characters, bank, year, day_in_year, total_day, weather, season = get_current_state()

    # Build per-building runtime info
    summary_rows = build_building_summary(bank, include_health=True)
    summary_by_key = {row["key"]: row for row in summary_rows}

    buildings_payload = []
    for b in BUILDINGS:
        key = b["key"]
        layout = MAP_LAYOUT.get(key)
        if not layout:
            continue
        row = summary_by_key.get(key) or {}
        buildings_payload.append({
            "key": key,
            "name": b["name"],
            "cost_coin": b.get("cost", 0),
            "cost_resources": b.get("resources") or {},
            "level": row.get("level", 0),
            "health": row.get("health", 0),
            "built": bool(row.get("built", False)),
            "description": _BUILDING_DESCRIPTIONS.get(key, b["name"]),
            "x": layout["x"],
            "y": layout["y"],
            "w": layout["w"],
            "h": layout["h"],
            "icon": layout["icon"],
            "tint": layout["tint"],
            "zone": layout["zone"],
        })

    worker_map = _job_assignments_by_building(characters)

    return render_template(
        "map.html",
        active_page="map",
        username=session.get("username"),
        year=year,
        day=day_in_year,
        weather=weather,
        buildings=buildings_payload,
        viewbox_w=MAP_VIEWBOX[0],
        viewbox_h=MAP_VIEWBOX[1],
        worker_map=worker_map,
        alive_count=sum(1 for c in characters if c.get("alive")),
        total_count=len(characters),
    )
