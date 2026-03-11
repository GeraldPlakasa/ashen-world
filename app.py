from __future__ import annotations

import threading

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from werkzeug.security import check_password_hash

from config import (
    ENV_ADMIN_USERNAME,
    ENV_ADMIN_PASSWORD,
    TRAITS,
    AUTO_SIM_ENABLED,
    ENV_FLASK_SECRET_KEY,
)
from world_utils import safe_int

from src.repositories.user_repo import (
    load_users,
    save_user,
)
from src.repositories.stats_repo import (
    list_yearly_history,
    get_year_entry,
    get_all_time_leaders,
)
from src.services.world_service import (
    get_current_state,
    advance_one_day,
    generate_new_world,
    compute_year_champions,
    auto_simulation_loop,
    load_characters_locked,
)
from src.services.family_tree_service import (
    build_family_graph,
    build_graveyard_index_for,
    find_person,
    get_all_families,
)
from src.services.character_service import (
    create_player_character,
    get_pinned_character_data,
)
from src.services.building_service import build_building_summary

app = Flask(__name__)
app.secret_key = ENV_FLASK_SECRET_KEY

with app.app_context():
    """
    Start background auto-simulation thread at startup (beware debug reloader).
    """
    if AUTO_SIM_ENABLED:
        t = threading.Thread(target=auto_simulation_loop, daemon=True)
        t.start()

# ---------------------------------------------------------------------------
#  Flask routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
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
    last_election_year = village_bank.get("last_election_year")
    last_election_message = village_bank.get("last_election_message", "")
    last_event_message = village_bank.get("last_event_message", "")
    last_event_day = village_bank.get("last_event_day")
    last_quest_message = village_bank.get("last_quest_message", "")
    last_quest_day = village_bank.get("last_quest_day")
    last_quest_success = village_bank.get("last_quest_success")
    last_quest_type = village_bank.get("last_quest_type", "")
    last_quest_name = village_bank.get("last_quest_name", "")
    last_quest_desc = village_bank.get("last_quest_desc", "")

    village_buildings = build_building_summary(village_bank)

    pinned_data = get_pinned_character_data(username, characters)

    pinned_character = pinned_data["character"] if pinned_data else None
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
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page: username + email + password.
    Saves user to database, then redirect to login.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "info")
            return render_template("register.html")

        if password != confirm:
            flash("Password and confirmation do not match.", "info")
            return render_template("register.html")

        users = load_users()

        if any(u.get("username", "").lower() == username.lower() for u in users):
            flash("Username is already taken.", "info")
            return render_template("register.html")

        if username.lower() == ENV_ADMIN_USERNAME.lower():
            flash("This username is reserved for the high steward. Please choose another.", "info")
            return render_template("register.html")

        if any(u.get("email", "").lower() == email.lower() for u in users):
            flash("Email is already registered.", "info")
            return render_template("register.html")

        save_user(username, email, password)
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page.
    - Check user credentials from database.
    - Fallback: hardcoded admin credentials.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        users = load_users()
        user = next(
            (u for u in users if u.get("username", "").lower() == username.lower()),
            None,
        )

        if user and check_password_hash(user.get("password_hash", ""), password):
            session["logged_in"] = True
            session["username"] = user["username"]
            session["is_admin"] = False
            flash(f"Welcome back, {user['username']}.", "success")
            return redirect(url_for("landing"))

        if username == ENV_ADMIN_USERNAME and password == ENV_ADMIN_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            session["is_admin"] = True
            flash("Welcome back, steward of Ashen World.", "success")
            return redirect(url_for("admin"))

        flash("Invalid username or password.", "info")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """
    Log out the current user and clear session.
    """
    session.clear()
    flash("You have left the control hall.", "info")
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    """
    Main admin view:
    - POST "generate" : create a new population, reset to Day 1.
    - POST "+1 Day"   : advance the world by one day and simulate actions.
    - GET             : display current population and world time.
    """
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if not session.get("is_admin"):
        flash("You must be an admin to access the control hall.", "info")
        return redirect(url_for("landing"))

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
            return redirect(url_for("admin"))

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

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    """Leaderboard page: yearly champions and all-time leaders."""
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    characters, bank, year, day_in_year, total_day, weather = get_current_state()

    history_sorted = list_yearly_history(finalized_only=True)
    current_entry = get_year_entry(year)

    current_champions = compute_year_champions(characters)

    # All-time legends from archived years
    all_time = get_all_time_leaders(finalized_only=True) or {}
    
    # Compute current wealthiest family
    family_wealth = {}
    for v in characters:
        if v.get("alive", True):
            family = (v.get("family") or "").strip()
            if family:
                family_wealth[family] = family_wealth.get(family, 0) + int(v.get("coins", 0) or 0)
    
    current_wealthiest_family = None
    if family_wealth:
        top_family = max(family_wealth.items(), key=lambda x: x[1])
        current_wealthiest_family = {"name": top_family[0], "coins": top_family[1]}

    return render_template(
        "leaderboard.html",
        active_page="leaderboard",
        username=session.get("username"),
        year=year,
        day=day_in_year,
        history=history_sorted,
        current_entry=current_entry,
        current_champions=current_champions,
        all_time=all_time,
        current_wealthiest_family=current_wealthiest_family,
    )

@app.route("/history/csv", methods=["GET"])
def download_history_csv():
    """Download historical records as CSV (one row per year)."""
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    history = list_yearly_history(finalized_only=True)
    
    # CSV header
    headers = [
        "Year",
        "King Name",
        "King Trait",
        "Days",
        "Births",
        "Deaths",
        "Immigrants",
        "Treasury Start",
        "Treasury End",
        "Avg Tax Rate",
        "Total Corruption",
        "Wealthiest Family",
        "Wealthiest Family Coins",
        "Most ATK Name",
        "Most ATK Value",
        "Most INT Name",
        "Most INT Value",
        "Richest Name",
        "Richest Value",
        "Top Hunter Name",
        "Top Hunter Value",
    ]
    
    lines = [",".join(headers)]
    
    for y in history:
        # Escape commas in names
        def esc(val):
            if val is None:
                return ""
            s = str(val)
            if "," in s or '"' in s:
                return '"' + s.replace('"', '""') + '"'
            return s
        
        row = [
            str(y.get("year", "")),
            esc(y.get("king_name", "")),
            esc(y.get("king_trait", "")),
            str(y.get("days_counted", 0)),
            str(y.get("total_births", 0)),
            str(y.get("total_deaths", 0)),
            str(y.get("total_immigrants", 0)),
            str(y.get("treasury_start", 0)),
            str(y.get("treasury_end", 0)),
            f"{(y.get('avg_tax_rate', 0) or 0) * 100:.1f}%",
            str(y.get("total_corruption", 0)),
            esc(y.get("wealthiest_family", "")),
            str(y.get("wealthiest_family_coins", 0)),
            esc(y.get("most_atk_name", "")),
            str(y.get("most_atk_value", 0)),
            esc(y.get("most_int_name", "")),
            str(y.get("most_int_value", 0)),
            esc(y.get("richest_name", "")),
            str(y.get("richest_value", 0)),
            esc(y.get("top_hunter_name", "")),
            str(y.get("top_hunter_value", 0)),
        ]
        lines.append(",".join(row))
    
    csv_content = "\n".join(lines)
    
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=ashen_world_history.csv"}
    )


@app.route("/quests/csv", methods=["GET"])
def download_quest_csv():
    """Download quest history as CSV."""
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    characters, bank, year, day_in_year, total_day, weather = get_current_state()
    quest_history = bank.get("quest_history", [])
    if not isinstance(quest_history, list):
        quest_history = []
    
    # CSV header
    headers = [
        "Year",
        "Day",
        "Quest Type",
        "Quest Name",
        "Description",
        "Threshold",
        "Success",
        "Success Chance",
        "Gold Reward",
        "Party Members",
        "Party Size",
        "Avg Primary Stat",
        "Avg Level",
        "Deaths",
        "King",
    ]
    
    lines = [",".join(headers)]
    
    def esc(val):
        if val is None:
            return ""
        s = str(val)
        if "," in s or '"' in s:
            return '"' + s.replace('"', '""') + '"'
        return s
    
    for q in quest_history:
        # party contains names as strings
        party = q.get("party", [])
        
        # Handle both string list and dict list formats
        if party and isinstance(party[0], dict):
            party_names = [p.get("name", "?") for p in party]
        else:
            party_names = [str(p) for p in party]
        
        # Get stats_info for success chance and threshold
        stats_info = q.get("stats_info", {})
        success_chance = stats_info.get("final_chance", 0)
        threshold = stats_info.get("threshold", 0)
        avg_stat = stats_info.get("avg_stat", 0)
        avg_level = stats_info.get("avg_level", 0)
        
        row = [
            str(q.get("year", "")),
            str(q.get("day_in_year", q.get("day", ""))),
            esc(q.get("type", "")),
            esc(q.get("name", "")),
            esc(q.get("description", "")),
            str(threshold),
            "Yes" if q.get("success") else "No",
            f"{success_chance:.1f}%",
            str(q.get("gold", 0)),
            esc(", ".join(party_names)),
            str(q.get("party_size", len(party))),
            str(avg_stat),
            str(avg_level),
            str(q.get("deaths", 0)),
            esc(q.get("king_name", "")),
        ]
        lines.append(",".join(row))
    
    csv_content = "\n".join(lines)
    
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=ashen_world_quests.csv"}
    )


@app.route("/character/new", methods=["GET", "POST"])
def create_character():
    """
    Create a custom character:
    - User inputs given name + family name
    - User chooses 1 trait (radio)
    - 1 extra trait is added randomly
    - origin = 'player'
    - Each user may only create 1 character.
    """
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    username = session.get("username") or ""

    # Get current state (characters + world time)
    characters, bank, year, day_in_year, _, weather = get_current_state()

    # Check if this user already has a player character
    existing_player = None
    if username:
        for c in characters:
            if c.get("origin") == "player" and c.get("owner") == username:
                existing_player = c
                break

    # If already have one, redirect to landing
    if request.method == "GET":
        if existing_player:
            flash("You already have a character in this world.", "info")
            return redirect(url_for("landing"))

        return render_template(
            "create_character.html",
            traits=TRAITS,
            year=year,
            day=day_in_year,
            active_page="create_character",
            form_name="",
            form_family="",
            chosen_trait="",
            form_gender="",
        )

    # POST
    if existing_player:
        flash("You already have a character in this world.", "info")
        return redirect(url_for("landing"))

    given_name = request.form.get("name", "").strip()
    family = request.form.get("family", "").strip()
    chosen_trait = request.form.get("trait", "").strip()
    gender = request.form.get("gender", "").strip()

    if not given_name or not family or not chosen_trait or not gender:
        flash("Name, family, gender, and one trait are required.", "info")
        return render_template(
            "create_character.html",
            traits=TRAITS,
            year=year,
            day=day_in_year,
            active_page="create_character",
            form_name=given_name,
            form_family=family,
            chosen_trait=chosen_trait,
            form_gender=gender,
        )

    success, result, new_villager = create_player_character(
        username, given_name, family, chosen_trait, gender
    )

    if not success:
        if result == "already_exists":
            flash("You already have a character in this world.", "info")
            return redirect(url_for("landing"))
        elif result == "name_taken":
            flash("A character with that full name already exists.", "info")
            return render_template(
                "create_character.html",
                traits=TRAITS,
                year=year,
                day=day_in_year,
                active_page="create_character",
                form_name=given_name,
                form_family=family,
                chosen_trait=chosen_trait,
                form_gender=gender,
            )

    flash(f"Created new character: {result} (Player).", "success")
    return redirect(url_for("landing"))

@app.route("/families", methods=["GET"])
def families():
    """List all families with their members."""
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    username = session.get("username")
    characters, bank, year, day_in_year, _, weather = get_current_state()

    all_families = get_all_families(characters)

    return render_template(
        "families.html",
        active_page="families",
        username=username,
        year=year,
        day=day_in_year,
        families=all_families,
        total_families=len(all_families),
    )


@app.route("/family-tree", methods=["GET"])
def family_tree():
    """Family tree visualization page for the logged-in user's character."""
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    username = session.get("username")
    is_admin = bool(session.get("is_admin"))

    characters, bank, year, day_in_year, _, weather = get_current_state()

    # default root: user's player character
    root = None
    root_id = request.args.get("root_id")

    if is_admin and root_id and str(root_id).isdigit():
        rid = int(root_id)
        root = find_person(characters, rid)
    else:
        # normal user: only their own player char
        root = next((c for c in characters if c.get("origin") == "player" and c.get("owner") == username), None)

        # If not in live (maybe dead/pruned), try graveyard by scanning (cheap, since one player per user)
        if root is None:
            root = None

    if not root:
        flash("You don't have a player character yet. Create one first.", "info")
        return redirect(url_for("create_character"))

    rid = safe_int(root.get("id"))
    rname = root.get("name") or f"#{rid}"

    return render_template(
        "family_tree.html",
        active_page="family_tree",
        username=username,
        year=year,
        day=day_in_year,
        root_id=rid,
        root_name=rname,
    )

@app.route("/api/family-tree/<int:root_id>", methods=["GET"])
def api_family_tree(root_id: int):
    """Return vis-network graph data for a family tree rooted at root_id."""
    if not session.get("logged_in"):
        return jsonify({"ok": False, "message": "Unauthorized"}), 401

    username = session.get("username")
    is_admin = bool(session.get("is_admin"))

    up_depth = safe_int(request.args.get("up", 3), 3)
    down_depth = safe_int(request.args.get("down", 3), 3)

    up_depth = max(0, min(10, up_depth))
    down_depth = max(0, min(10, down_depth))

    characters = load_characters_locked()

    # Authorization:
    # - admin can view any root
    # - user can only view their own player character as root
    if not is_admin:
        root_live = next((c for c in characters if safe_int(c.get("id")) == root_id), None)
        if not root_live:
            return jsonify({"ok": False, "message": "Root not found"}), 404

        if root_live.get("origin") != "player" or root_live.get("owner") != username:
            return jsonify({"ok": False, "message": "Forbidden"}), 403

    payload = build_family_graph(
        characters=characters,
        root_id=root_id,
        up_depth=up_depth,
        down_depth=down_depth,
        max_nodes=250,
    )
    payload["ok"] = True
    return jsonify(payload)

@app.route("/api/state", methods=["GET"])
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

@app.route("/quests", methods=["GET"])
def quest_history():
    """Quest history page showing all completed quests."""
    _, bank, year, day_in_year, _, _ = get_current_state()
    
    quest_history_data = bank.get("quest_history", [])
    if not isinstance(quest_history_data, list):
        quest_history_data = []
    
    return render_template(
        "quest_history.html",
        active_page="quests",
        username=session.get("username"),
        year=year,
        day=day_in_year,
        quest_history=quest_history_data,
    )


@app.route("/features", methods=["GET"])
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

if __name__ == "__main__":
    app.run(debug=True)

    # if AUTO_SIM_ENABLED:
    #     t = threading.Thread(target=auto_simulation_loop, daemon=True)
    #     t.start()
    # app.run(debug=True, use_reloader=False)
