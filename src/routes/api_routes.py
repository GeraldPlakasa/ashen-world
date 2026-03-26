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


@api_bp.route("/api/analytics", methods=["GET"])
def api_analytics():
    """
    JSON API for admin dashboard analytics.
    Returns historical data for charts and statistics.
    """
    # Get current state
    characters, bank, year, day_in_year, total_day, weather = get_current_state()
    
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
            "history": event_history[-10:],  # Last 10 events
        },
        "skill_definitions": {name: {"category": data.get("category", ""), "rarity": data.get("rarity", "")} for name, data in SKILLS.items()},
        "achievement_definitions": {aid: {"name": data["name"], "icon": data.get("icon", "🏆")} for aid, data in ACHIEVEMENTS.items()},
    })
