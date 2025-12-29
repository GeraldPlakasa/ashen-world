import csv
import json
import math
import os
import random
import threading
import time

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    TRAITS,
    JOBS_NO_ROYAL,
    DAYS_PER_YEAR,
    AUTO_SIM_ENABLED,
    AUTO_SIM_SECONDS,
    BUILDINGS,
    _next_villager_id,
    ELECTION_INTERVAL_YEARS,
    MAX_DEAD_YEARS
)
from storage import (
    save_to_csv,
    load_from_csv,
    load_users,
    save_user,
    load_day,
    save_day,
    load_bank,
    save_bank,
    compute_year_and_day,
    ensure_year_row,
    update_year_daily,
    finalize_year,
    list_yearly_history,
    get_year_entry,
    clear_yearly_stats,
    get_all_time_leaders,
)
from villagers import (
    generate_characters,
    make_row,
    reset_id_from_characters,
    simulate_one_day,
    hold_election,
)
from buildings import (
    update_tax_policy,
    maybe_construct_building,
    maybe_upgrade_building,
    decay_buildings,
    maybe_repair_buildings,
)
from villagers_social import settle_inheritance_phase

app = Flask(__name__)
# NOTE: Change this in production and load it from a safe place (env/secret store).
app.secret_key = "super-secret-key"

_state_lock = threading.Lock()   # guard CSV + world_time read/writes

# ---------------------------------------------------------------------------
#  Helper
# ---------------------------------------------------------------------------

def compute_year_champions(characters: list[dict]) -> dict:
    # prefer alive, fallback to all
    pool = [c for c in characters if c.get("alive", True)]
    if not pool:
        pool = characters[:]

    def top_by(key: str):
        if not pool:
            return {"id": None, "name": None, "value": 0}
        best = max(pool, key=lambda c: int(c.get(key, 0) or 0))
        return {
            "id": int(best.get("id", 0) or 0),
            "name": best.get("name") or "—",
            "value": int(best.get(key, 0) or 0),
        }

    return {
        "most_atk": top_by("atk"),
        "most_int": top_by("int"),
        "richest":  top_by("coins"),
        "top_hunter": top_by("huntWinsYear"),
    }

# ---------------------------------------------------------------------------
#  Villager generation
# ---------------------------------------------------------------------------

def get_current_state():
    """
    Thread-safe helper: read current characters + world time.

    Returns:
        (characters, year, day_in_year, total_day)
    """
    with _state_lock:
        characters = load_from_csv()
        total_day = load_day()

    year, day_in_year = compute_year_and_day(total_day)
    return characters, year, day_in_year, total_day

def advance_one_day():
    """
    Advance the world by one day in a thread-safe way.

    Handles:
    - Year rollover (aging)
    - Scheduled elections every ELECTION_INTERVAL_YEARS
    - Emergency election if the King dies or no King exists
    - Tax policy update
    - Daily simulation
    - Building construction/upgrade/decay/repair
    - Treasury interest

    Returns:
        (ok, message, year, day_in_year, total_day)
    """
    with _state_lock:
        characters = load_from_csv()
        bank = load_bank()

        if not characters:
            # No villagers yet
            return (
                False,
                "No villagers yet. Generate a population first.",
                None,
                None,
                None,
            )

        old_total_day = load_day()
        if old_total_day < 1:
            old_total_day = 1

        new_total_day = old_total_day + 1

        yr_now, day_now = compute_year_and_day(new_total_day)

        # If this is the first day (Day 0) of a year, capture treasury_start before spending
        if day_now == 0:
            ensure_year_row(yr_now, treasury_start=int(bank.get("balance", 0) or 0))
        else:
            ensure_year_row(yr_now)

        # --- For yearly stats: snapshot BEFORE simulation ---
        before_ids = {int(v.get("id", 0) or 0) for v in characters if int(v.get("id", 0) or 0) > 0}
        before_alive_ids = {int(v.get("id", 0) or 0) for v in characters if v.get("alive", True) and int(v.get("id", 0) or 0) > 0}

        # Track King at the start of the day (before any elections / deaths)
        prev_king = next(
            (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
            None,
        )
        prev_king_id = prev_king.get("id") if prev_king else None

        # --- Year boundary check ---
        old_year_idx = (old_total_day - 1) // DAYS_PER_YEAR
        new_year_idx = (new_total_day - 1) // DAYS_PER_YEAR
        crossed_year = new_year_idx > old_year_idx

        if crossed_year:

            old_year = old_year_idx + 1

            # compute champions for the year that just ended
            champions = compute_year_champions(characters)
            finalize_year(old_year, champions=champions)

            # One in-world year passed → everyone ages by +1
            for v in characters:
                if v.get("alive", True):
                    v["age"] = int(v.get("age", 0) or 0) + 1
                v["huntWinsYear"] = 0

            # Compute the new year number (1-based)
            new_year = new_year_idx + 1

            # 🔹 Scheduled election: every ELECTION_INTERVAL_YEARS
            if new_year % ELECTION_INTERVAL_YEARS == 0:
                winner, election_msg = hold_election(
                    characters,
                    current_day=new_total_day,
                )
                if winner and election_msg:
                    # Store in bank so we can show it on the dashboard
                    bank["last_election_year"] = int(new_year)
                    bank["last_election_message"] = election_msg

        # Update tax policy based on current (possibly new) King traits
        bank = update_tax_policy(characters, bank, log_it=False)

        # --- Daily simulation (combat, income, deaths, etc.) ---
        characters, bank = simulate_one_day(characters, bank, current_day=new_total_day)

        for v in characters:
            if not v.get("alive", True) or v.get("hp", 0) <= 0:
                v["alive"] = False
                if v.get("hp", 0) < 0:
                    v["hp"] = 0

                try:
                    dd = int(v.get("death_day", 0) or 0)
                except (TypeError, ValueError):
                    dd = 0
                if dd <= 0:
                    v["death_day"] = new_total_day
                
        settle_inheritance_phase(characters, bank, current_day=new_total_day)

        # -------------------------------------------------------------------
        #  Emergency election: if the King died today, or no living King exists
        # -------------------------------------------------------------------
        # Check if there is any living King after the simulation
        current_king = next(
            (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
            None,
        )

        # Detect if the King at start-of-day died during this tick
        king_died_today = False
        if prev_king_id is not None:
            prev_after = next(
                (v for v in characters if v.get("id") == prev_king_id),
                None,
            )
            if prev_after is not None and not prev_after.get("alive", True):
                king_died_today = True

        # Condition:
        #  - No living King at all, OR
        #  - The previous King died during this day
        if (current_king is None and characters) or king_died_today:
            winner_em, emergency_msg = hold_election(
                characters,
                current_day=new_total_day,
            )
            if winner_em and emergency_msg:
                yr, _ = compute_year_and_day(new_total_day)
                bank["last_election_year"] = int(yr)
                # Mark message so player can see it was emergency
                bank["last_election_message"] = f"[Emergency] {emergency_msg}"
                # King changed mid-day → update tax policy for upcoming days
                bank = update_tax_policy(characters, bank, log_it=False)
        
        # --- Yearly stats bucket for CURRENT year (after elections/emergency) ---
        yr_now, _ = compute_year_and_day(new_total_day)


        # Update king info for this year (keep last known king)
        final_king = next((v for v in characters if v.get("job") == "King" and v.get("alive", True)), None)

        # -------------------------------------------------------------------
        #  Buildings + treasury interest
        # -------------------------------------------------------------------
        # 1) King may construct one new building
        bank, build_event = maybe_construct_building(characters, bank, new_total_day)

        # 2) King may upgrade one existing building
        bank, upgrade_event = maybe_upgrade_building(characters, bank, new_total_day)

        # 3) Buildings decay over time
        bank, decay_events = decay_buildings(bank, new_total_day)

        # 4) If something important is damaged, repair it
        bank, repair_event = maybe_repair_buildings(characters, bank, new_total_day)

        # 5) Treasury passive: small daily interest on bank balance
        levels = bank.get("building_levels") or {}
        lvl_treasury = int(levels.get("treasury", 0) or 0)
        if lvl_treasury > 0 and bank.get("balance", 0) > 0:
            interest_rate = 0.003 * lvl_treasury  # 0.3% per level per day
            interest = max(1, int(bank["balance"] * interest_rate))
            bank["balance"] += interest

        #  6) Prune
        max_dead_days = MAX_DEAD_YEARS * DAYS_PER_YEAR

        pruned_characters = []
        for v in characters:
            if v.get("alive", True):
                pruned_characters.append(v)
                continue

            try:
                death_day = int(v.get("death_day", 0) or 0)
            except (TypeError, ValueError):
                death_day = 0

            if death_day <= 0:
                pruned_characters.append(v)
                continue

            if new_total_day - death_day < max_dead_days:
                pruned_characters.append(v)
                continue

        characters = pruned_characters

        # --- For yearly stats: compute immigrants/deaths TODAY ---
        after_ids = {int(v.get("id", 0) or 0) for v in characters if int(v.get("id", 0) or 0) > 0}
        after_alive_ids = {int(v.get("id", 0) or 0) for v in characters if v.get("alive", True) and int(v.get("id", 0) or 0) > 0}

        immigrants_today = len(after_ids - before_ids)
        deaths_today = len(before_alive_ids - after_alive_ids)

        final_king = next((v for v in characters if v.get("job") == "King" and v.get("alive", True)), None)
        king_id = int(final_king.get("id", 0) or 0) if final_king else None
        king_name = final_king.get("name") if final_king else None

        update_year_daily(
            year=yr_now,
            king_id=king_id,
            king_name=king_name,
            deaths_today=deaths_today,
            immigrants_today=immigrants_today,
            tax_rate_today=float(bank.get("tax_rate", 0.10) or 0.10),
            treasury_end=int(bank.get("balance", 0) or 0),
        )

        # Persist updated state
        save_to_csv(characters)
        save_day(new_total_day)
        save_bank(bank)

    year, day_in_year = compute_year_and_day(new_total_day)
    msg = f"Simulated +1 day of actions (Year {year}, Day {day_in_year})."

    return True, msg, year, day_in_year, new_total_day

def auto_simulation_loop():
    """
    Background loop: automatically advance the world every AUTO_SIM_SECONDS.
    Runs as long as the process is alive and AUTO_SIM_ENABLED is True.
    """
    if not AUTO_SIM_ENABLED:
        return

    # Simple loop: every tick, try to advance one day.
    # If there are no villagers yet, advance_one_day() just returns False.
    while True:
        time.sleep(AUTO_SIM_SECONDS)
        try:
            advance_one_day()
        except Exception as exc:
            # Avoid killing the thread if something weird happens
            print("[auto_simulation_loop] Error:", exc)

with app.app_context():
    """
    Kick off the background auto-simulation loop once the server
    receives its first real request.
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
    characters = load_from_csv()
    total_day = load_day()
    year, day_in_year = compute_year_and_day(total_day)
    pinned_spouse_name = None
    pinned_spouse_alive = True

    total = len(characters)
    alive_count = sum(1 for c in characters if c.get("alive", True))
    dead_count = total - alive_count

    username = session.get("username")

    village_bank = load_bank()
    bank_balance = village_bank.get("balance", 0)
    tax_rate = village_bank.get("tax_rate", 0.10)
    last_election_year = village_bank.get("last_election_year")
    last_election_message = village_bank.get("last_election_message", "")

    # --- Build simple building list for UI ---
    raw_levels = village_bank.get("building_levels") or {}
    village_buildings = []

    for b in BUILDINGS:
        key = b["key"]
        name = b["name"]
        try:
            lvl = int(raw_levels.get(key, 0) or 0)
        except (TypeError, ValueError):
            lvl = 0

        village_buildings.append(
            {
                "key": key,
                "name": name,
                "level": lvl,
            }
        )

    # built first, then by name
    village_buildings.sort(key=lambda x: (x["level"] <= 0, x["name"]))

    # Find pinned character for this user + its recent actions + relationships
    pinned_character = None
    pinned_actions = []
    pinned_rel_bonds = []      # 🔹 closest positive relationships
    pinned_rel_conflicts = []  # 🔹 rivals & enemies
    pinned_mother = None
    pinned_father = None
    pinned_children = []

    if username:
        def _safe_int(x, default=0):
            try:
                return int(x or 0)
            except (TypeError, ValueError):
                return default

        def _parse_children_ids(raw):
            if not raw:
                return []
            if isinstance(raw, list):
                return [_safe_int(i) for i in raw if _safe_int(i) > 0]
            if isinstance(raw, str) and raw.strip():
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        return [_safe_int(i) for i in data if _safe_int(i) > 0]
                except Exception:
                    return []
            return []

        # quick index to map id(int) -> character
        id_to_char = {}
        for cc in characters:
            cid = _safe_int(cc.get("id"))
            if cid > 0:
                id_to_char[cid] = cc

        for c in characters:
            if c.get("origin") == "player" and c.get("owner") == username:
                pinned_character = c

                # --- Spouse name (if any) ---
                spouse_id = c.get("spouseId", 0) or 0
                try:
                    spouse_id = int(spouse_id)
                except (TypeError, ValueError):
                    spouse_id = 0

                if spouse_id > 0:
                    spouse = id_to_char.get(spouse_id)
                    if spouse:
                        pinned_spouse_name = spouse.get("name", f"#{spouse_id}")
                        pinned_spouse_alive = spouse.get("alive", True)
                    else:
                        pinned_spouse_name = f"#{spouse_id}"
                        pinned_spouse_alive = True
                
                # --- Mother / Father ---
                mother_id = _safe_int(c.get("motherId"))
                father_id = _safe_int(c.get("fatherId"))

                if mother_id > 0:
                    mom = id_to_char.get(mother_id)
                    pinned_mother = {
                        "id": mother_id,
                        "name": (mom.get("name") if mom else f"#{mother_id}"),
                        "alive": (mom.get("alive", True) if mom else None),
                    }

                if father_id > 0:
                    dad = id_to_char.get(father_id)
                    pinned_father = {
                        "id": father_id,
                        "name": (dad.get("name") if dad else f"#{father_id}"),
                        "alive": (dad.get("alive", True) if dad else None),
                    }

                # --- Children ---
                child_ids = _parse_children_ids(c.get("childrenIds"))
                pinned_children = []
                for cid in child_ids:
                    ch = id_to_char.get(cid)
                    pinned_children.append({
                        "id": cid,
                        "name": (ch.get("name") if ch else f"#{cid}"),
                        "alive": (ch.get("alive", True) if ch else None),
                    })

                # --- Action history ---
                hist_str = c.get("action_log", "") or ""
                if hist_str:
                    actions = [a.strip() for a in hist_str.split("||") if a.strip()]
                    pinned_actions = list(reversed(actions))

                # --- Relationship summary ---
                rel_raw = c.get("relationships") or {}
                if isinstance(rel_raw, dict):
                    rel_entries = []

                    for other_id_str, score in rel_raw.items():
                        try:
                            oid = int(other_id_str)
                            score_int = int(score)
                        except (TypeError, ValueError):
                            continue

                        other = id_to_char.get(oid)
                        if not other:
                            continue

                        g1 = c.get("gender")
                        g2 = other.get("gender")
                        is_mf_pair = {g1, g2} == {"Male", "Female"}

                        label = None
                        if is_mf_pair and score_int >= 80:
                            label = "love"
                        elif score_int >= 65:
                            label = "bestfriend"
                        elif score_int >= 30:
                            label = "friend"
                        elif score_int <= -60:
                            label = "enemy"
                        elif score_int <= -30:
                            label = "rival"
                        else:
                            label = None

                        if label is None:
                            continue

                        rel_entries.append(
                            {
                                "id": oid,
                                "name": other.get("name", f"#{oid}"),
                                "score": score_int,
                                "label": label,
                            }
                        )

                    # Split into positive & negative
                    positives = [r for r in rel_entries if r["score"] > 0]
                    negatives = [r for r in rel_entries if r["score"] < 0]

                    positives.sort(key=lambda r: r["score"], reverse=True)
                    negatives.sort(key=lambda r: r["score"])

                    pinned_rel_bonds = positives[:3]
                    pinned_rel_conflicts = negatives[:3]

                break  # found pinned char; stop

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
        pinned_spouse_name=pinned_spouse_name,
        pinned_spouse_alive=pinned_spouse_alive,
        pinned_mother=pinned_mother,
        pinned_father=pinned_father,
        pinned_children=pinned_children,
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page: username + email + password.
    Saves to users.csv, then redirect to login.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        # Basic validation
        if not username or not email or not password:
            flash("All fields are required.", "info")
            return render_template("register.html")

        if password != confirm:
            flash("Password and confirmation do not match.", "info")
            return render_template("register.html")

        users = load_users()

        # 💠 Username cannot duplicate existing users
        if any(u.get("username", "").lower() == username.lower() for u in users):
            flash("Username is already taken.", "info")
            return render_template("register.html")

        # 💠 Username cannot be same as reserved admin username
        if username.lower() == ADMIN_USERNAME.lower():
            flash("This username is reserved for the high steward. Please choose another.", "info")
            return render_template("register.html")

        # 💠 Email must be unique
        if any(u.get("email", "").lower() == email.lower() for u in users):
            flash("Email is already registered.", "info")
            return render_template("register.html")

        # Save user
        save_user(username, email, password)
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page.
    - Cek user dari users.csv (username/password).
    - Fallback: admin hardcoded (optional).
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        users = load_users()
        user = next(
            (u for u in users if u.get("username", "").lower() == username.lower()),
            None,
        )

        # 1) Coba login dari CSV
        if user and check_password_hash(user.get("password_hash", ""), password):
            session["logged_in"] = True
            session["username"] = user["username"]
            session["is_admin"] = False
            flash(f"Welcome back, {user['username']}.", "success")
            return redirect(url_for("landing"))

        # 2) Fallback: hardcoded admin (opsional)
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            session["is_admin"] = True
            flash("Welcome back, steward of Ashen World.", "success")
            return redirect(url_for("admin"))

        # 3) Gagal
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
    - GET             : display current CSV-based population and world time.
    """
    # 🔒 must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    # 🔒 must be admin
    if not session.get("is_admin"):
        flash("You must be an admin to access the control hall.", "info")
        return redirect(url_for("landing"))

    if request.method == "POST":
        op = request.form.get("op", "generate")

        if op == "generate":
            # Fresh population, reset world time to the beginning
            with _state_lock:
                characters = generate_characters(50)
                save_to_csv(characters)

                # total_day = 1 → Year 1, Day 0
                save_day(1)

                # Reset village bank
                save_bank({
                    "tax_rate": 0.10,
                    "balance": 0,
                    "building_levels": {},
                    "building_health": {},
                    "last_election_year": None,
                    "last_election_message": "",
                })

                clear_yearly_stats()

            year, day_in_year = compute_year_and_day(1)

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
    characters, year, day_in_year, _ = get_current_state()

    # Load village bank for building info
    village_bank = load_bank()
    raw_levels = village_bank.get("building_levels") or {}
    raw_health = village_bank.get("building_health") or {}

    village_buildings = []
    for b in BUILDINGS:
        key = b["key"]
        name = b["name"]

        try:
            lvl = int(raw_levels.get(key, 0) or 0)
        except (TypeError, ValueError):
            lvl = 0

        try:
            hp = int(raw_health.get(key, 0) or 0)
        except (TypeError, ValueError):
            hp = 0

        # Clamp HP into 0–100
        hp = max(0, min(100, hp))
        built = lvl > 0 and hp > 0

        village_buildings.append(
            {
                "key": key,
                "name": name,
                "level": lvl,
                "health": hp,
                "built": built,
            }
        )

    # Built first, then by name
    village_buildings.sort(key=lambda x: (not x["built"], x["name"]))

    # Load registered users for KPI
    users = load_users()
    total_users = len(users)

    return render_template(
        "admin.html",
        characters=characters,
        day=day_in_year,
        year=year,
        active_page="admin",
        total_users=total_users,
        village_buildings=village_buildings,
    )

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    total_day = load_day()
    year, day_in_year = compute_year_and_day(total_day)

    history_sorted = list_yearly_history(finalized_only=True)
    current_entry = get_year_entry(year)

    characters = load_from_csv()
    current_champions = compute_year_champions(characters)

    # All-time legends from archived years
    all_time = get_all_time_leaders(finalized_only=True) or {}

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
    characters, year, day_in_year, _ = get_current_state()

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

    full_name = f"{given_name} {family}"

    with _state_lock:
        # Reload inside lock for safety
        characters = load_from_csv()
        taken_names = {c.get("name", "") for c in characters}

        # sync internal ID counter
        reset_id_from_characters(characters)

        # prevent duplicate full names
        if full_name in taken_names:
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

        # ensure internal ID counter is at least current max ID
        global _next_villager_id
        if characters:
            max_id = max(c.get("id", 0) for c in characters)
            if _next_villager_id < max_id:
                _next_villager_id = max_id

        # base row from generator (random stats, job, etc.)
        new_row = make_row(taken_names, jobs_pool=JOBS_NO_ROYAL)

        # override identity + origin + owner + gender
        new_row["name"] = full_name
        new_row["family"] = family
        new_row["origin"] = "player"
        new_row["owner"] = username
        new_row["gender"] = gender

        # traits: chosen + one random extra trait
        other_traits = [t for t in TRAITS if t != chosen_trait]
        second_trait = random.choice(other_traits) if other_traits else chosen_trait
        new_row["traits"] = f"{chosen_trait}, {second_trait}"

        characters.append(new_row)
        save_to_csv(characters)

    flash(f"Created new character: {full_name} (Player).", "success")
    return redirect(url_for("landing"))

@app.route("/api/state", methods=["GET"])
def api_state():
    """
    JSON API that returns the current world time + characters
    WITHOUT advancing the simulation.

    Now also returns village bank + building info so the admin
    auto-refresh can update KPI and buildings card.
    """
    characters, year, day_in_year, total_day = get_current_state()
    bank = load_bank()

    building_levels = bank.get("building_levels") or {}
    building_health = bank.get("building_health") or {}

    buildings_payload = []
    for b in BUILDINGS:
        key = b["key"]
        name = b["name"]

        try:
            lvl = int(building_levels.get(key, 0) or 0)
        except (TypeError, ValueError):
            lvl = 0

        try:
            hp = int(building_health.get(key, 0) or 0)
        except (TypeError, ValueError):
            hp = 0

        hp = max(0, min(100, hp))
        built = (lvl > 0 and hp > 0)

        buildings_payload.append(
            {
                "key": key,
                "name": name,
                "level": lvl,
                "health": hp,
                "built": built,
            }
        )

    return jsonify({
        "ok": True,
        "message": "Current state",
        "year": year,
        "day": day_in_year,
        "total_day": total_day,
        "characters": characters,
        "bank_balance": bank.get("balance", 0),
        "tax_rate": bank.get("tax_rate", 0.10),
        "buildings": buildings_payload,
        "last_election_year": bank.get("last_election_year"),
        "last_election_message": bank.get("last_election_message", ""),
    })

if __name__ == "__main__":
    app.run(debug=True)

    # if AUTO_SIM_ENABLED:
    #     t = threading.Thread(target=auto_simulation_loop, daemon=True)
    #     t.start()
    # app.run(debug=True, use_reloader=False)
