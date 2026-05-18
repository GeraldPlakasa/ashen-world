"""
Admin routes: Admin dashboard and controls.
"""
import json as _json

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session, jsonify,
)

from src.services.world_service import (
    get_current_state,
    advance_one_day,
    generate_new_world,
)
from src.services.family_tree_service import build_graveyard_index_for
from src.services.building_service import build_building_summary, get_building_level
from src.repositories.user_repo import load_users
from src.utils.world_utils import is_child

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
#  Dashboard builders — pure functions reused by the page render and the
#  /admin/snapshot.json API (so the in-page refresh button can update charts
#  without a full browser reload).
# ---------------------------------------------------------------------------

def _build_resources_dashboard(characters, bank, year, day_in_year):
    from config import (
        JOB_RESOURCE_YIELD,
        FOOD_PER_ADULT_PER_DAY,
        FOOD_PER_CHILD_PER_DAY,
        GRANARY_CONSUMPTION_MULT,
        TRADE_EMERGENCY_FOOD_STOCK,
        TRADE_PRICES,
        TRADE_SELL_PRICES,
    )

    alive = [c for c in characters if c.get("alive", True)]
    adults_alive = [c for c in alive if not is_child(c)]
    kids_alive = [c for c in alive if is_child(c)]

    job_counts: dict[str, int] = {}
    for v in adults_alive:
        job = v.get("job", "")
        if job in JOB_RESOURCE_YIELD:
            job_counts[job] = job_counts.get(job, 0) + 1

    production_rows = []
    expected_daily = {"food": 0, "wood": 0, "stone": 0, "iron": 0}
    for job, yield_table in JOB_RESOURCE_YIELD.items():
        count = job_counts.get(job, 0)
        if count == 0:
            continue
        per_villager = ", ".join(f"+{n} {r}" for r, n in yield_table.items())
        total = {r: n * count for r, n in yield_table.items()}
        total_str = ", ".join(f"+{n} {r}" for r, n in total.items())
        production_rows.append({
            "job": job,
            "count": count,
            "per_villager": per_villager,
            "total": total_str,
        })
        for r, n in total.items():
            expected_daily[r] = expected_daily.get(r, 0) + n
    production_rows.sort(key=lambda x: -x["count"])

    granary_lvl = get_building_level(bank, "granary")
    raw_food_need = len(adults_alive) * FOOD_PER_ADULT_PER_DAY + len(kids_alive) * FOOD_PER_CHILD_PER_DAY
    granary_mult = GRANARY_CONSUMPTION_MULT if granary_lvl > 0 else 1.0
    effective_food_need = max(1, int(round(raw_food_need * granary_mult)))

    food_stock = int((bank.get("resources") or {}).get("food", 0) or 0)
    days_of_supply = food_stock / max(1, effective_food_need)
    if food_stock < TRADE_EMERGENCY_FOOD_STOCK:
        food_status, food_status_class = "Emergency", "dead"
    elif food_stock < 1500:
        food_status, food_status_class = "Cautious", "damaged"
    else:
        food_status, food_status_class = "Stable", "alive"

    try:
        from src.repositories.chronicle_repo import list_events
        recent_imports = list_events(limit=40, category="economy")
    except Exception:
        recent_imports = []

    return {
        "stockpile": bank.get("resources") or {"food": 0, "wood": 0, "stone": 0, "iron": 0},
        "prices": TRADE_PRICES,
        "sell_prices": TRADE_SELL_PRICES,
        "production_rows": production_rows,
        "expected_daily": expected_daily,
        "raw_food_need": raw_food_need,
        "effective_food_need": effective_food_need,
        "granary_lvl": granary_lvl,
        "granary_mult": granary_mult,
        "adults_alive": len(adults_alive),
        "kids_alive": len(kids_alive),
        "days_of_supply": round(days_of_supply, 1),
        "food_status": food_status,
        "food_status_class": food_status_class,
        "emergency_threshold": TRADE_EMERGENCY_FOOD_STOCK,
        "net_food": expected_daily.get("food", 0) - effective_food_need,
        "recent_imports": recent_imports,
    }


def _build_health_dashboard(characters, bank, year, day_in_year):
    from config import DISEASES, HEALER_JOBS

    _disease_colors = {"cough": "#94a3b8", "fever": "#f59e0b", "plague": "#ef4444"}
    disease_meta = {
        slug: {
            "name": params.get("name", slug),
            "icon": params.get("icon", ""),
            "color": _disease_colors.get(slug, "#6366f1"),
            "duration_days": params.get("duration_days", 0),
        }
        for slug, params in DISEASES.items()
    }

    current_by_disease = {slug: 0 for slug in DISEASES}
    immune_by_disease = {slug: 0 for slug in DISEASES}
    sick_villagers: list[dict] = []
    healers: list[dict] = []
    total_alive_h = 0

    for v in characters:
        if not v.get("alive", True):
            continue
        total_alive_h += 1

        try:
            raw = v.get("immunities") or "[]"
            imms = _json.loads(raw) if isinstance(raw, str) else (raw or [])
            if not isinstance(imms, list):
                imms = []
        except Exception:
            imms = []
        for slug in imms:
            if slug in immune_by_disease:
                immune_by_disease[slug] += 1

        disease = (v.get("disease") or "").strip()
        if disease and disease in DISEASES:
            current_by_disease[disease] += 1
            day_caught = int(v.get("disease_day", 0) or 0)
            sick_villagers.append({
                "id": int(v.get("id", 0) or 0),
                "name": v.get("name", "?"),
                "family": v.get("family", ""),
                "job": v.get("job", ""),
                "age": int(v.get("age", 0) or 0),
                "hp": int(v.get("hp", 0) or 0),
                "disease": disease,
                "disease_name": DISEASES[disease].get("name", disease),
                "disease_icon": DISEASES[disease].get("icon", ""),
                "days_sick": max(0, (year - 1) * 90 + day_in_year - day_caught) if day_caught else 0,
            })

        if v.get("job") in HEALER_JOBS:
            healers.append({
                "id": int(v.get("id", 0) or 0),
                "name": v.get("name", "?"),
                "job": v.get("job", ""),
                "int": int(v.get("int", 0) or 0),
                "level": int(v.get("level", 1) or 1),
                "age": int(v.get("age", 0) or 0),
                "family": v.get("family", ""),
            })

    sick_villagers.sort(key=lambda s: (s["hp"], -s["days_sick"]))
    healers.sort(key=lambda h: (-h["int"], -h["level"]))

    total_sick_h = sum(current_by_disease.values())
    total_immune_h = sum(immune_by_disease.values())

    plague_now = current_by_disease.get("plague", 0)
    sick_pct = (total_sick_h / total_alive_h * 100) if total_alive_h else 0
    if plague_now > 0:
        outbreak_status, outbreak_class = "Plague Outbreak", "dead"
    elif sick_pct >= 5:
        outbreak_status, outbreak_class = "Outbreak", "damaged"
    elif total_sick_h > 0:
        outbreak_status, outbreak_class = "Cases", "damaged"
    else:
        outbreak_status, outbreak_class = "Healthy", "alive"

    # Pull recent events from the dedicated `health` chronicle category.
    # Previously this scanned the last 120 events of any category for
    # keyword hits — that over-matched anything containing "ill" (e.g.
    # "still", "Williams") and silently inherited categorization changes.
    try:
        from src.repositories.chronicle_repo import list_events
        recent_health_events = list_events(limit=30, category="health", min_importance=1)
    except Exception:
        recent_health_events = []

    return {
        "disease_meta": disease_meta,
        "current_by_disease": current_by_disease,
        "immune_by_disease": immune_by_disease,
        "sick_villagers": sick_villagers,
        "healers": healers,
        "total_alive": total_alive_h,
        "total_sick": total_sick_h,
        "total_immune": total_immune_h,
        "sick_pct": round(sick_pct, 1),
        "outbreak_status": outbreak_status,
        "outbreak_class": outbreak_class,
        "recent_events": recent_health_events,
    }


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
            year, day_in_year = generate_new_world(100)

            flash(
                f"World reset: spawned 100 villagers (Year {year}, Day {day_in_year}).",
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
    characters, village_bank, year, day_in_year, _, weather, season = get_current_state()

    graveyard_index = build_graveyard_index_for(characters)
    village_buildings = build_building_summary(village_bank, include_health=True)

    # Load registered users for KPI
    users = load_users()
    total_users = len(users)

    # ---- Resources & Health dashboards (extracted helpers — also serve
    # the /admin/snapshot.json endpoint for in-page refresh).
    resources_dashboard = _build_resources_dashboard(characters, village_bank, year, day_in_year)
    health_dashboard = _build_health_dashboard(characters, village_bank, year, day_in_year)

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
        resources_dashboard=resources_dashboard,
        health_dashboard=health_dashboard,
    )


@admin_bp.route("/admin/snapshot.json", methods=["GET"])
def admin_snapshot():
    """JSON snapshot of the Resources + Health dashboards. Used by the
    Control Hall's in-page Refresh button to update charts and KPI numbers
    without a full page reload (which would reset the active tab)."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    characters, bank, year, day_in_year, _, _, _ = get_current_state()
    return jsonify({
        "ok": True,
        "year": year,
        "day": day_in_year,
        "resources": _build_resources_dashboard(characters, bank, year, day_in_year),
        "health": _build_health_dashboard(characters, bank, year, day_in_year),
    })
