import json
import random
import threading
import time

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import check_password_hash

from config import (
    ENV_ADMIN_USERNAME,
    ENV_ADMIN_PASSWORD,
    TRAITS,
    JOBS_NO_ROYAL,
    DAYS_PER_YEAR,
    AUTO_SIM_ENABLED,
    AUTO_SIM_SECONDS,
    BUILDINGS,
    _next_villager_id,
    ELECTION_INTERVAL_YEARS,
    MAX_DEAD_YEARS,
    ENV_FLASK_SECRET_KEY,
)
from src.repositories.villager_repo import (
    save_villagers as save_to_csv,
    load_villagers as load_from_csv,
    graveyard_get,
    graveyard_get_many,
    graveyard_upsert_from_villager,
)
from src.repositories.world_repo import (
    load_day,
    save_day,
    compute_year_and_day,
    load_world_payload,
    save_world_payload,
    load_weather,
)
from src.repositories.user_repo import (
    load_users,
    save_user,
)
from src.repositories.bank_repo import (
    load_bank,
    save_bank,
)
from src.repositories.stats_repo import (
    ensure_year_row,
    update_year_daily,
    finalize_year,
    list_yearly_history,
    get_year_entry,
    clear_yearly_stats,
    get_all_time_leaders,
)
from src.services.villager_service import (
    generate_characters,
    make_row,
    reset_id_from_characters,
)
from src.services.simulation_service import simulate_one_day
from src.services.election_service import hold_election
from src.services.building_service import (
    update_tax_policy,
    maybe_construct_building,
    maybe_upgrade_building,
    decay_buildings,
    maybe_repair_buildings,
)
from src.services.family_service import settle_inheritance_phase

app = Flask(__name__)
app.secret_key = ENV_FLASK_SECRET_KEY

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

def _parse_relationship_ids(raw):
    """
    Accept dict or JSON-string dict.
    Returns list[int] of other villager IDs.
    """
    if not raw:
        return []
    rel = raw
    if isinstance(rel, str) and rel.strip():
        try:
            rel = json.loads(rel)
        except Exception:
            return []
    if isinstance(rel, dict):
        out = []
        for k in rel.keys():
            try:
                oid = int(k)
            except Exception:
                continue
            if oid > 0:
                out.append(oid)
        return out
    return []

def build_graveyard_index_for(characters: list[dict]) -> dict:
    """
    Collect IDs referenced by current villagers (spouse/parents/children/relationships)
    that are missing from the live list, then fetch them from graveyard in one batch.

    Returns: {id: graveyard_row_dict}
    """
    live_ids = {_safe_int(c.get("id")) for c in characters if _safe_int(c.get("id")) > 0}
    need_ids: set[int] = set()

    for c in characters:
        # direct family refs
        for k in ("spouseId", "motherId", "fatherId"):
            pid = _safe_int(c.get(k))
            if pid > 0 and pid not in live_ids:
                need_ids.add(pid)

        # children
        for cid in _parse_children_ids(c.get("childrenIds")):
            if cid > 0 and cid not in live_ids:
                need_ids.add(cid)

        # relationships targets
        for oid in _parse_relationship_ids(c.get("relationships")):
            if oid > 0 and oid not in live_ids:
                need_ids.add(oid)

    if not need_ids:
        return {}

    # returns dict keyed by int IDs
    return graveyard_get_many(sorted(need_ids)) or {}

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

def build_family_graph(characters: list[dict], root_id: int, up_depth: int = 3, down_depth: int = 3, max_nodes: int = 250):
    """
    Build a vis-network graph payload (nodes + edges) for family tree.
    Includes graveyard fallback for pruned villagers.
    """

    live_by_id: dict[int, dict] = {}
    for c in characters:
        cid = _safe_int(c.get("id"))
        if cid > 0:
            live_by_id[cid] = c

    gy_cache: dict[int, dict] = {}

    def get_person(pid: int) -> dict | None:
        """Return unified person dict with _source field: live/graveyard."""
        if pid <= 0:
            return None
        if pid in live_by_id:
            p = dict(live_by_id[pid])
            p["_source"] = "live"
            return p
        if pid in gy_cache:
            p = dict(gy_cache[pid])
            p["_source"] = "graveyard"
            return p

        gy = graveyard_get(pid)
        if gy:
            gy_cache[pid] = gy
            p = dict(gy)
            p["_source"] = "graveyard"
            return p

        return None

    def node_group(p: dict, pid: int) -> str:
        if pid == root_id:
            return "root"
        if p.get("_source") == "graveyard":
            return "archived"
        alive = p.get("alive", True)
        if alive is False:
            return "dead"
        if (p.get("origin") or "") == "player":
            return "player"
        return "npc"

    def node_label(p: dict, pid: int) -> str:
        name = (p.get("name") or f"#{pid}").strip()
        src = p.get("_source")
        if src == "graveyard":
            return f"{name}\n(archived)"
        job = (p.get("job") or "").strip()
        lvl = _safe_int(p.get("level"))
        if job:
            return f"{name}\n{job} • Lv {lvl}"
        return f"{name}\nLv {lvl}"

    def node_title(p: dict, pid: int) -> str:
        # Tooltip HTML (vis uses "title" as HTML)
        name = (p.get("name") or f"#{pid}").strip()
        src = p.get("_source")
        gender = p.get("gender") or "?"
        origin = p.get("origin") or "?"
        owner = p.get("owner") or ""
        traits = (p.get("traits") or "").strip()

        if src == "graveyard":
            return f"<b>{name}</b><br>Gender: {gender}<br>Origin: {origin}<br>{('Owner: ' + owner + '<br>') if owner else ''}<i>Archived record</i><br>Traits: {traits}"

        alive = p.get("alive", True)
        job = p.get("job") or "-"
        age = _safe_int(p.get("age"))
        lvl = _safe_int(p.get("level"))
        rep = _safe_int(p.get("rep"))
        coins = _safe_int(p.get("coins"))

        return (
            f"<b>{name}</b><br>"
            f"Status: {'Alive' if alive else 'Dead'}<br>"
            f"Job: {job}<br>"
            f"Gender: {gender}<br>"
            f"Age: {age}<br>"
            f"Lv: {lvl}<br>"
            f"REP: {rep}<br>"
            f"Coins: {coins}<br>"
            f"Origin: {origin}<br>"
            f"{('Owner: ' + owner + '<br>') if owner else ''}"
            f"Traits: {traits}"
        )

    nodes: dict[int, dict] = {}
    edges: dict[str, dict] = {}

    def add_node(pid: int):
        if pid <= 0:
            return
        if pid in nodes:
            return
        if len(nodes) >= max_nodes:
            return

        p = get_person(pid)
        if not p:
            # Unknown id -> still show placeholder node
            nodes[pid] = {
                "id": pid,
                "label": f"#{pid}\n(unknown)",
                "group": "unknown",
                "title": f"<b>#{pid}</b><br><i>Missing record</i>",
            }
            return

        nodes[pid] = {
            "id": pid,
            "label": node_label(p, pid),
            "group": node_group(p, pid),
            "title": node_title(p, pid),
        }

    def add_edge(fr: int, to: int, kind: str):
        if fr <= 0 or to <= 0 or fr == to:
            return
        key = f"{fr}->{to}:{kind}"
        if key in edges:
            return

        if kind == "parent":
            edges[key] = {
                "from": fr,
                "to": to,
                "arrows": "to",
                "label": "",
            }
        elif kind == "spouse":
            edges[key] = {
                "from": fr,
                "to": to,
                "dashes": True,
                "label": "spouse",
                "arrows": "",
            }
        else:
            edges[key] = {"from": fr, "to": to}

    # ---- Build root base
    add_node(root_id)
    root = get_person(root_id)

    if root:
        # spouse (show node + dashed link)
        sid = _safe_int(root.get("spouseId") or root.get("spouse_id"))
        if sid > 0 and len(nodes) < max_nodes:
            add_node(sid)
            add_edge(root_id, sid, "spouse")
            add_edge(sid, root_id, "spouse")

    # ---- Ancestors BFS (up)
    up_q = [(root_id, 0)]
    up_seen = set([root_id])

    while up_q and len(nodes) < max_nodes:
        pid, d = up_q.pop(0)
        if d >= up_depth:
            continue
        p = get_person(pid)
        if not p:
            continue

        mother = _safe_int(p.get("motherId"))
        father = _safe_int(p.get("fatherId"))

        for par_id in (mother, father):
            if par_id <= 0:
                continue
            add_node(par_id)
            add_edge(par_id, pid, "parent")

            if par_id not in up_seen:
                up_seen.add(par_id)
                up_q.append((par_id, d + 1))

    # ---- Descendants BFS (down)
    down_q = [(root_id, 0)]
    down_seen = set([root_id])

    while down_q and len(nodes) < max_nodes:
        pid, d = down_q.pop(0)
        if d >= down_depth:
            continue
        p = get_person(pid)
        if not p:
            continue

        child_ids = _parse_children_ids(p.get("childrenIds"))
        for ch_id in child_ids:
            if ch_id <= 0:
                continue
            add_node(ch_id)
            add_edge(pid, ch_id, "parent")  # parent -> child

            if ch_id not in down_seen:
                down_seen.add(ch_id)
                down_q.append((ch_id, d + 1))

    return {
        "root_id": root_id,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "meta": {
            "up_depth": up_depth,
            "down_depth": down_depth,
            "max_nodes": max_nodes,
            "live_count": len(live_by_id),
            "graph_nodes": len(nodes),
        },
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
        bank = load_bank()
        weather = load_weather()

    year, day_in_year = compute_year_and_day(total_day)
    return characters, bank, year, day_in_year, total_day, weather

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

        # If day_in_year == 0, we are on the first day of a new year.
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

        #  6) Prune (archive to graveyard first)
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

            # if no death_day, keep (data anomaly)
            if death_day <= 0:
                pruned_characters.append(v)
                continue

            # keep if not old enough
            if new_total_day - death_day < max_dead_days:
                pruned_characters.append(v)
                continue

            try:
                graveyard_upsert_from_villager(v)
            except Exception as exc:
                print("[prune] graveyard_upsert failed:", exc)

            # DO NOT append (means pruned)

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
    pinned_spouse_name = None
    pinned_spouse_alive = None

    total = len(characters)
    alive_count = sum(1 for c in characters if c.get("alive", True))
    dead_count = total - alive_count

    username = session.get("username")

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
                rel_raw = c.get("relationships") or {}
                rel_ids = []
                if isinstance(rel_raw, dict):
                    for k in rel_raw.keys():
                        try:
                            rel_ids.append(int(k))
                        except Exception:
                            continue

                spouse_id = _safe_int(c.get("spouseId"))
                mother_id = _safe_int(c.get("motherId"))
                father_id = _safe_int(c.get("fatherId"))
                child_ids = _parse_children_ids(c.get("childrenIds"))

                referenced_ids = set([spouse_id, mother_id, father_id] + child_ids + rel_ids)
                referenced_ids = {i for i in referenced_ids if i > 0}

                missing_ids = [i for i in referenced_ids if i not in id_to_char]
                gy_map = graveyard_get_many(missing_ids) if missing_ids else {}

                def _resolve_person(pid: int):
                    """
                    Return (name, alive, gender, raw_obj)
                    alive = True/False if in current villagers
                          = None if only in graveyard
                    """
                    if pid <= 0:
                        return (None, None, None, None)

                    live = id_to_char.get(pid)
                    if live:
                        return (
                            live.get("name", f"#{pid}"),
                            live.get("alive", True),
                            live.get("gender"),
                            live,
                        )

                    gy = gy_map.get(pid)
                    if gy:
                        return (
                            gy.get("name", f"#{pid}"),
                            None,
                            gy.get("gender"),
                            gy,
                        )

                    return (f"#{pid}", None, None, None)

                # --- Spouse ---
                if spouse_id > 0:
                    s_name, s_alive, _, _ = _resolve_person(spouse_id)
                    pinned_spouse_name = s_name
                    pinned_spouse_alive = s_alive

                # --- Mother / Father ---
                if mother_id > 0:
                    m_name, m_alive, _, _ = _resolve_person(mother_id)
                    pinned_mother = {"id": mother_id, "name": m_name, "alive": m_alive}

                if father_id > 0:
                    f_name, f_alive, _, _ = _resolve_person(father_id)
                    pinned_father = {"id": father_id, "name": f_name, "alive": f_alive}

                # --- Children ---
                pinned_children = []
                for cid in child_ids:
                    ch_name, ch_alive, _, _ = _resolve_person(cid)
                    pinned_children.append({"id": cid, "name": ch_name, "alive": ch_alive})

                # --- Action history ---
                hist_str = c.get("action_log", "") or ""
                if hist_str:
                    actions = [a.strip() for a in hist_str.split("||") if a.strip()]
                    pinned_actions = list(reversed(actions))

                # --- Relationship summary (now supports graveyard) ---
                pinned_rel_bonds = []
                pinned_rel_conflicts = []

                if isinstance(rel_raw, dict):
                    rel_entries = []
                    g1 = c.get("gender")

                    for other_id_str, score in rel_raw.items():
                        try:
                            oid = int(other_id_str)
                            score_int = int(score)
                        except (TypeError, ValueError):
                            continue

                        o_name, o_alive, g2, other_obj = _resolve_person(oid)
                        if not other_obj:
                            continue

                        is_mf_pair = {g1, g2} == {"Male", "Female"} if g1 and g2 else False

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

                        if label is None:
                            continue

                        rel_entries.append(
                            {
                                "id": oid,
                                "name": o_name,
                                "score": score_int,
                                "label": label,
                            }
                        )

                    positives = [r for r in rel_entries if r["score"] > 0]
                    negatives = [r for r in rel_entries if r["score"] < 0]

                    positives.sort(key=lambda r: r["score"], reverse=True)
                    negatives.sort(key=lambda r: r["score"])

                    pinned_rel_bonds = positives[:3]
                    pinned_rel_conflicts = negatives[:3]

                break  # found pinned char; stop

    # weather_today = (village_bank.get("weather") or "sunny")
    # weather_today = "rain"
    # print(village_bank.get("weather"))

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
        weather_today=weather,
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
        if username.lower() == ENV_ADMIN_USERNAME.lower():
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
        if username == ENV_ADMIN_USERNAME and password == ENV_ADMIN_PASSWORD:
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

                # Reset weather to default
                payload = load_world_payload()
                payload["weather"] = "sunny"
                payload["next_weather_roll_day"] = 1
                save_world_payload(payload)

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
    characters, village_bank, year, day_in_year, _, weather = get_current_state()

    graveyard_index = build_graveyard_index_for(characters)

    # Load village bank for building info
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
        graveyard_index=graveyard_index,
    )

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    characters, bank, year, day_in_year, total_day, weather = get_current_state()

    history_sorted = list_yearly_history(finalized_only=True)
    current_entry = get_year_entry(year)

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
        if characters:
            max_id = max(c.get("id", 0) for c in characters)
            global _next_villager_id
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

@app.route("/family-tree", methods=["GET"])
def family_tree():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    username = session.get("username")
    is_admin = bool(session.get("is_admin"))

    # get current world time
    characters, bank, year, day_in_year, _, weather = get_current_state()

    # default root: user's player character
    root = None
    root_id = request.args.get("root_id")

    if is_admin and root_id and str(root_id).isdigit():
        rid = int(root_id)
        root = next((c for c in characters if _safe_int(c.get("id")) == rid), None) or graveyard_get(rid)
    else:
        # normal user: only their own player char
        root = next((c for c in characters if c.get("origin") == "player" and c.get("owner") == username), None)

        # If not in live (maybe dead/pruned), try graveyard by scanning (cheap, since one player per user)
        if root is None:
            # Optional: if you store player in graveyard with owner, you can search via SQL later.
            # For now, keep simple: no root found.
            root = None

    if not root:
        flash("You don’t have a player character yet. Create one first.", "info")
        return redirect(url_for("create_character"))

    rid = _safe_int(root.get("id"))
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
    if not session.get("logged_in"):
        return jsonify({"ok": False, "message": "Unauthorized"}), 401

    username = session.get("username")
    is_admin = bool(session.get("is_admin"))

    up_depth = _safe_int(request.args.get("up", 3), 3)
    down_depth = _safe_int(request.args.get("down", 3), 3)

    # guardrails
    up_depth = max(0, min(10, up_depth))
    down_depth = max(0, min(10, down_depth))

    with _state_lock:
        characters = load_from_csv()

    # Authorization:
    # - admin can view any root
    # - user can only view their own player character as root
    if not is_admin:
        root_live = next((c for c in characters if _safe_int(c.get("id")) == root_id), None)
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
        "graveyard_index": graveyard_index,
        "bank_balance": bank.get("balance", 0),
        "tax_rate": bank.get("tax_rate", 0.10),
        "buildings": buildings_payload,
        "last_election_year": bank.get("last_election_year"),
        "last_election_message": bank.get("last_election_message", ""),
        "weather": bank.get("weather", "sunny"),
    })

@app.route("/features", methods=["GET"])
def features():

    # optional: you can show current year/day at top like other pages
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
