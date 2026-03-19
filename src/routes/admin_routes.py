"""
Admin routes: Admin dashboard and controls.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from src.services.world_service import (
    get_current_state,
    advance_one_day,
    generate_new_world,
)
from src.services.family_tree_service import build_graveyard_index_for
from src.services.building_service import build_building_summary
from src.repositories.user_repo import load_users

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin", methods=["GET", "POST"])
def admin():
    """
    Main admin view:
    - POST "generate" : create a new population, reset to Day 1.
    - POST "+1 Day"   : advance the world by one day and simulate actions.
    - GET             : display current population and world time.
    """
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    if not session.get("is_admin"):
        flash("You must be an admin to access the control hall.", "info")
        return redirect(url_for("main.landing"))

    if request.method == "POST":
        op = request.form.get("op", "generate")

        if op == "generate":
            year, day_in_year = generate_new_world(50)

            flash(
                f"World reset: spawned 50 villagers (Year {year}, Day {day_in_year}).",
                "success",
            )

        elif op == "next_day":
            ok, msg, year, day_in_year, _ = advance_one_day()
            if ok:
                flash(msg, "success")
            else:
                flash(msg, "info")
            return redirect(url_for("admin.admin"))

    # GET: load current state (thread-safe)
    characters, village_bank, year, day_in_year, _, weather = get_current_state()

    graveyard_index = build_graveyard_index_for(characters)
    village_buildings = build_building_summary(village_bank, include_health=True)

    # Load registered users for KPI
    users = load_users()
    total_users = len(users)

    # Load skill descriptions for UI
    from src.services.skill_service import SKILLS
    skill_descriptions = {name: data["description"] for name, data in SKILLS.items()}
    
    # Load achievement descriptions for UI
    from src.services.achievement_service import ACHIEVEMENTS
    achievement_descriptions = {
        aid: {
            "name": data["name"],
            "description": data["description"],
            "icon": data.get("icon", "🏆"),
            "reward": data.get("reward", {})
        }
        for aid, data in ACHIEVEMENTS.items()
    }

    return render_template(
        "admin.html",
        characters=characters,
        day=day_in_year,
        year=year,
        active_page="admin",
        total_users=total_users,
        village_buildings=village_buildings,
        graveyard_index=graveyard_index,
        skill_descriptions=skill_descriptions,
        achievement_descriptions=achievement_descriptions,
    )
