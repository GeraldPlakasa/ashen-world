"""
Chronicle routes: in-world Town Crier feed of narrated events.
"""
from flask import Blueprint, render_template, request, session, jsonify

from src.services.world_service import get_current_state
from src.repositories.chronicle_repo import (
    list_events,
    list_top_recent,
    list_categories,
    list_years,
    count_events,
)

chronicle_bp = Blueprint("chronicle", __name__)


@chronicle_bp.route("/chronicle", methods=["GET"])
def chronicle():
    """Full chronicle timeline."""
    _, _, year, day_in_year, _, _ = get_current_state()

    category = (request.args.get("category") or "").strip() or None
    year_filter_raw = request.args.get("year")
    try:
        year_filter = int(year_filter_raw) if year_filter_raw else None
    except (TypeError, ValueError):
        year_filter = None
    try:
        min_importance = int(request.args.get("min_importance", 1))
    except (TypeError, ValueError):
        min_importance = 1
    q = (request.args.get("q") or "").strip() or None

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 30
    offset = (page - 1) * per_page

    events = list_events(
        limit=per_page,
        offset=offset,
        category=category,
        year=year_filter,
        min_importance=min_importance,
        q=q,
    )
    total = count_events(
        category=category, year=year_filter, q=q, min_importance=min_importance
    )
    has_more = (offset + len(events)) < total

    return render_template(
        "chronicle.html",
        active_page="chronicle",
        username=session.get("username"),
        year=year,
        day=day_in_year,
        events=events,
        category=category,
        year_filter=year_filter,
        min_importance=min_importance,
        q=q,
        page=page,
        has_more=has_more,
        total=total,
        all_categories=list_categories(),
        all_years=list_years(),
    )


@chronicle_bp.route("/api/chronicle", methods=["GET"])
def api_chronicle():
    """JSON feed for the headlines widget and any future ajax pagination."""
    try:
        limit = max(1, min(100, int(request.args.get("limit", 5))))
    except (TypeError, ValueError):
        limit = 5
    try:
        min_importance = int(request.args.get("min_importance", 3))
    except (TypeError, ValueError):
        min_importance = 3
    category = (request.args.get("category") or "").strip() or None
    top_only = request.args.get("top") in ("1", "true", "yes")

    if top_only:
        events = list_top_recent(limit=limit, min_importance=min_importance)
    else:
        events = list_events(
            limit=limit,
            offset=0,
            category=category,
            min_importance=min_importance,
        )
    return jsonify({"events": events, "count": len(events)})
