"""
API routes: JSON endpoints for frontend.
"""
from flask import Blueprint, jsonify

from src.services.world_service import get_current_state
from src.services.family_tree_service import build_graveyard_index_for
from src.services.building_service import build_building_summary
from src.repositories.stats_repo import list_yearly_history
from src.repositories.user_repo import load_users
from src.repositories.bank_repo import load_bank
from src.services.event_service import get_event_history
from src.services.skill_service import SKILLS
from src.services.achievement_service import ACHIEVEMENTS
from src.repositories.site_stats_repo import get_stats_by_type, get_all_stats_summary

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/state", methods=["GET"])
def api_state():
    """
    JSON API that returns the current world time + characters
    WITHOUT advancing the simulation.

    Now also returns village bank + building info so the admin
    auto-refresh can update KPI and buildings card.
    """
    characters, bank, year, day_in_year, total_day, weather, season = get_current_state()
    graveyard_index = build_graveyard_index_for(characters)
    buildings_payload = build_building_summary(bank, include_health=True)

    # Strip heavy fields to reduce payload size
    slim_chars = []
    for c in characters:
        slim = {k: v for k, v in c.items() if k not in ("action_log", "relationships", "kingsVotedFor")}
        slim_chars.append(slim)

    return jsonify({
        "ok": True,
        "message": "Current state",
        "year": year,
        "day": day_in_year,
        "total_day": total_day,
        "characters": slim_chars,
        "graveyard_index": graveyard_index,
        "bank_balance": bank.get("balance", 0),
        "tax_rate": bank.get("tax_rate", 0.10),
        "resources": bank.get("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0}),
        "buildings": buildings_payload,
        "last_election_year": bank.get("last_election_year"),
        "last_election_message": bank.get("last_election_message", ""),
        # Festivals are filtered out of "recent news" — they're fluff and
        # crowd out signal events. They still appear in the chronicle.
        "last_event_message": (
            "" if "FESTIVAL" in (bank.get("last_event_message", "") or "").upper()
            else bank.get("last_event_message", "")
        ),
        "last_event_day": (
            None if "FESTIVAL" in (bank.get("last_event_message", "") or "").upper()
            else bank.get("last_event_day")
        ),
        "last_quest_message": bank.get("last_quest_message", ""),
        "last_quest_day": bank.get("last_quest_day"),
        "last_quest_success": bank.get("last_quest_success"),
        "weather": weather,
        "season": season,
    })


@api_bp.route("/api/analytics", methods=["GET"])
def api_analytics():
    """
    JSON API for admin dashboard analytics.
    Returns historical data for charts and statistics.
    """
    # Get current state
    characters, bank, year, day_in_year, total_day, weather, _season = get_current_state()
    
    # Yearly history for charts
    yearly_stats = list_yearly_history()
    
    # Population breakdown
    alive_chars = [c for c in characters if c.get("alive", True)]
    dead_chars = [c for c in characters if not c.get("alive", True)]
    
    # Job distribution
    job_counts = {}
    for c in alive_chars:
        job = c.get("job", "Unknown")
        job_counts[job] = job_counts.get(job, 0) + 1
    
    # Gender distribution
    gender_counts = {"Male": 0, "Female": 0}
    for c in alive_chars:
        gender = c.get("gender", "Unknown")
        if gender in gender_counts:
            gender_counts[gender] += 1
    
    # Age distribution
    age_groups = {"0-16": 0, "17-30": 0, "31-50": 0, "51-70": 0, "71+": 0}
    for c in alive_chars:
        age = c.get("age", 0) or 0
        if age <= 16:
            age_groups["0-16"] += 1
        elif age <= 30:
            age_groups["17-30"] += 1
        elif age <= 50:
            age_groups["31-50"] += 1
        elif age <= 70:
            age_groups["51-70"] += 1
        else:
            age_groups["71+"] += 1
    
    # Skill distribution
    skill_counts = {}
    for c in alive_chars:
        skills_str = c.get("skills", "") or ""
        if skills_str:
            for skill in skills_str.split(","):
                skill = skill.strip()
                if skill:
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
    
    # Achievement distribution
    import json, re
    achievement_counts = {}
    for c in characters:
        achs_raw = c.get("achievements", "[]")
        try:
            achs = json.loads(achs_raw) if isinstance(achs_raw, str) else achs_raw
        except:
            achs = []
        for ach in (achs or []):
            # Skip progress trackers like iron_will_count_1, iron_will_count_2, etc.
            if re.search(r'_count_\d+$', ach):
                continue
            achievement_counts[ach] = achievement_counts.get(ach, 0) + 1
    
    # Quest history stats
    quest_history = bank.get("quest_history", [])
    quest_type_counts = {}
    quest_success_counts = {"success": 0, "failed": 0}
    for q in quest_history:
        # Quest record uses "type" key, not "quest_type"
        qtype = q.get("type", q.get("quest_type", "unknown"))
        quest_type_counts[qtype] = quest_type_counts.get(qtype, 0) + 1
        if q.get("success"):
            quest_success_counts["success"] += 1
        else:
            quest_success_counts["failed"] += 1
    
    # Event history stats  
    event_history = get_event_history()
    event_type_counts = {}
    for e in event_history:
        # Event record uses "type" key, not "event_type"
        etype = e.get("type", e.get("event_type", "unknown"))
        event_type_counts[etype] = event_type_counts.get(etype, 0) + 1
    
    # Users
    users = load_users()
    
    # Origin distribution
    origin_counts = {"npc": 0, "player": 0, "born": 0, "immigrant": 0}
    for c in alive_chars:
        origin = c.get("origin", "npc")
        if origin in origin_counts:
            origin_counts[origin] += 1
        else:
            origin_counts["npc"] += 1
    
    # Trait distribution (top 10)
    trait_counts = {}
    for c in alive_chars:
        traits_str = c.get("traits", "") or ""
        if traits_str:
            for trait in traits_str.split(","):
                trait = trait.strip()
                if trait:
                    trait_counts[trait] = trait_counts.get(trait, 0) + 1
    top_traits = sorted(trait_counts.items(), key=lambda x: -x[1])[:10]
    
    return jsonify({
        "ok": True,
        "current": {
            "year": year,
            "day": day_in_year,
            "total_day": total_day,
            "population": len(alive_chars),
            "total_villagers": len(characters),
            "dead_count": len(dead_chars),
            "treasury": bank.get("balance", 0),
            "tax_rate": bank.get("tax_rate", 0.10),
            "resources": bank.get("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0}),
            "total_users": len(users),
        },
        "yearly_stats": yearly_stats,
        "distributions": {
            "jobs": job_counts,
            "gender": gender_counts,
            "age_groups": age_groups,
            "skills": skill_counts,
            "achievements": achievement_counts,
            "origins": origin_counts,
            "top_traits": dict(top_traits),
        },
        "quests": {
            "total": len(quest_history),
            "by_type": quest_type_counts,
            "success_rate": quest_success_counts,
            "history": quest_history[-10:],  # Last 10 quests
        },
        "events": {
            "total": len(event_history),
            "by_type": event_type_counts,
            "history": event_history,
        },
        "skill_definitions": {name: {"category": data.get("category", ""), "rarity": data.get("rarity", "")} for name, data in SKILLS.items()},
        "achievement_definitions": {aid: {"name": data["name"], "icon": data.get("icon", "🏆")} for aid, data in ACHIEVEMENTS.items()},
        "justice": _build_justice_payload(yearly_stats, year),
    })


def _build_justice_payload(yearly_stats: list[dict], current_year: int) -> dict:
    """Aggregate crime / verdict counters for the admin Justice tab.

    - `this_year` reads the live (un-finalized) row for the current year.
    - `history` returns all finalized rows trimmed to the counters we render.
    - `recent` pulls the latest few `justice`-category chronicle entries so
      the dashboard can show a verdict feed without a second API call.
    """
    try:
        from src.repositories.chronicle_repo import list_events
        recent = list_events(limit=15, category="justice", min_importance=1)
    except Exception:
        recent = []

    by_year = {int(r.get("year", 0) or 0): r for r in yearly_stats if r.get("year")}
    this_year_row = by_year.get(int(current_year)) or {}

    history = [
        {
            "year": int(r.get("year", 0) or 0),
            "crimes": int(r.get("crimes_committed", 0) or 0),
            "trials": int(r.get("trials_held", 0) or 0),
            # `fines_count` = number of fine verdicts (count axis).
            # `fines_gold`  = gold collected from those fines (currency axis).
            "fines_count": int(r.get("fines_count", 0) or 0),
            "fines_gold":  int(r.get("fines_collected", 0) or 0),
            "exiles": int(r.get("exiles", 0) or 0),
            "executions": int(r.get("executions", 0) or 0),
            "king": r.get("king_name") or "",
        }
        for r in yearly_stats
    ]
    history.sort(key=lambda x: x["year"])

    total_crimes = sum(h["crimes"] for h in history) + int(this_year_row.get("crimes_committed", 0) or 0)
    total_trials = sum(h["trials"] for h in history) + int(this_year_row.get("trials_held", 0) or 0)
    total_fines_count = sum(h["fines_count"] for h in history) + int(this_year_row.get("fines_count", 0) or 0)
    total_fines_gold  = sum(h["fines_gold"]  for h in history) + int(this_year_row.get("fines_collected", 0) or 0)
    total_exiles = sum(h["exiles"] for h in history) + int(this_year_row.get("exiles", 0) or 0)
    total_execs  = sum(h["executions"] for h in history) + int(this_year_row.get("executions", 0) or 0)

    return {
        "this_year": {
            "year": int(current_year),
            "crimes": int(this_year_row.get("crimes_committed", 0) or 0),
            "trials": int(this_year_row.get("trials_held", 0) or 0),
            "fines_count": int(this_year_row.get("fines_count", 0) or 0),
            "fines_gold":  int(this_year_row.get("fines_collected", 0) or 0),
            "exiles": int(this_year_row.get("exiles", 0) or 0),
            "executions": int(this_year_row.get("executions", 0) or 0),
        },
        "all_time": {
            "crimes": total_crimes,
            "trials": total_trials,
            "fines_count": total_fines_count,
            "fines_gold":  total_fines_gold,
            "exiles": total_exiles,
            "executions": total_execs,
        },
        "history": history,
        "recent": [
            {
                "day": e.get("day"),
                "year": e.get("year"),
                "headline": e.get("headline"),
                "body": e.get("body"),
                "importance": e.get("importance"),
            }
            for e in recent
        ],
    }


@api_bp.route("/api/character/<int:char_id>", methods=["GET"])
def api_character_detail(char_id: int):
    """Return enriched character data (relationships, family, achievements) for any villager."""
    from src.services.character_service import get_character_detail

    characters, _bank, _year, _day, _total, _weather, _season = get_current_state()
    data = get_character_detail(char_id, characters)
    if data is None:
        return jsonify({"error": "Character not found"}), 404
    return jsonify(data)


@api_bp.route("/api/player-stats", methods=["GET"])
def api_player_stats():
    """Player/site statistics for the Players tab."""
    users = load_users()
    characters, bank, year, day_in_year, total_day, weather, _season = get_current_state()

    # Users by registration date
    from collections import Counter
    reg_dates = Counter()
    for u in users:
        created = u.get("created_at", "")
        if created:
            date_part = created[:10]  # YYYY-MM-DD
            reg_dates[date_part] = reg_dates.get(date_part, 0) + 1

    # Player characters
    player_chars = [c for c in characters if c.get("origin") == "player"]
    player_alive = [c for c in player_chars if c.get("alive")]

    # Site stats from tracking table
    page_views = get_stats_by_type("page_view", 30)
    char_creations = get_stats_by_type("char_creation", 30)
    registrations = get_stats_by_type("user_registration", 30)
    stats_summary = get_all_stats_summary()

    return jsonify({
        "ok": True,
        "users": {
            "total": len(users),
            "by_date": sorted(reg_dates.items()),  # [[date, count], ...]
            "recent": [{"username": u["username"], "created_at": u.get("created_at", "")} for u in users[:10]],
        },
        "player_characters": {
            "total": len(player_chars),
            "alive": len(player_alive),
            "dead": len(player_chars) - len(player_alive),
        },
        "site_stats": {
            "page_views": page_views,
            "char_creations": char_creations,
            "registrations": registrations,
            "totals": stats_summary,
        },
    })
