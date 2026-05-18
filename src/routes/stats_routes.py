"""
Stats routes: Leaderboard, history CSV, quest history.
"""
from flask import Blueprint, render_template, redirect, url_for, session, Response

from src.services.world_service import get_current_state, compute_year_champions
from src.repositories.stats_repo import list_yearly_history, get_year_entry, get_all_time_leaders

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    """Leaderboard page: yearly champions and all-time leaders."""
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    characters, bank, year, day_in_year, total_day, weather, _season = get_current_state()

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


@stats_bp.route("/history/csv", methods=["GET"])
def download_history_csv():
    """Download historical records as CSV (one row per year)."""
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

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
        # Crime & Justice — per-year ledger
        "Crimes Witnessed",
        "Trials Held",
        "Fines (count)",
        "Fines (gold)",
        "Exiles",
        "Executions",
    ]
    
    lines = [",".join(headers)]
    
    def esc(val):
        """Escape commas in values for CSV."""
        if val is None:
            return ""
        s = str(val)
        if "," in s or '"' in s:
            return '"' + s.replace('"', '""') + '"'
        return s
    
    for y in history:
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
            str(y.get("crimes_committed", 0)),
            str(y.get("trials_held", 0)),
            str(y.get("fines_count", 0)),
            str(y.get("fines_collected", 0)),
            str(y.get("exiles", 0)),
            str(y.get("executions", 0)),
        ]
        lines.append(",".join(row))
    
    csv_content = "\n".join(lines)
    
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=ashen_world_history.csv"}
    )


@stats_bp.route("/quests/csv", methods=["GET"])
def download_quest_csv():
    """Download quest history as CSV."""
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    characters, bank, year, day_in_year, total_day, weather, _season = get_current_state()
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
        """Escape commas in values for CSV."""
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


@stats_bp.route("/quests", methods=["GET"])
def quest_history():
    """Quest history page showing all completed quests."""
    _, bank, year, day_in_year, _, _, _ = get_current_state()
    
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
