"""
Family routes: Family list and family tree.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify

from src.utils.world_utils import safe_int
from src.services.world_service import get_current_state, load_characters_locked
from src.services.family_tree_service import (
    build_family_graph,
    find_person,
    get_all_families,
)

family_bp = Blueprint("family", __name__)


@family_bp.route("/families", methods=["GET"])
def families():
    """List all families with their members."""
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    username = session.get("username")
    characters, bank, year, day_in_year, _, weather, _season = get_current_state()

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


@family_bp.route("/family-tree", methods=["GET"])
def family_tree():
    """Family tree visualization page for the logged-in user's character."""
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    username = session.get("username")
    is_admin = bool(session.get("is_admin"))

    characters, bank, year, day_in_year, _, weather, _season = get_current_state()

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
        return redirect(url_for("character.create_character"))

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


@family_bp.route("/api/family-tree/<int:root_id>", methods=["GET"])
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
