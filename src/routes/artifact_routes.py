"""
Artifact routes: /artifacts page (catalog of all named artifacts in the world)
and /artifacts/<id> (full lineage of a single artifact).
"""
from flask import Blueprint, render_template, session, abort, jsonify

from src.services.world_service import get_current_state
from src.repositories import artifact_repo
from src.repositories.villager_repo import graveyard_get_many
from src.services.artifact_service import get_template, list_templates

artifact_bp = Blueprint("artifact", __name__)


def _resolve_owner_label(owner_id: int, alive_index: dict, dead_index: dict) -> dict:
    """Best-effort lookup for an owner's display name + status."""
    owner_id = int(owner_id or 0)
    if owner_id <= 0:
        return {"id": 0, "name": "—", "alive": None}
    v = alive_index.get(owner_id)
    if v:
        return {
            "id": owner_id,
            "name": v.get("name") or "Unknown",
            "family": v.get("family") or "",
            "alive": bool(v.get("alive", True)),
        }
    g = dead_index.get(owner_id)
    if g:
        return {
            "id": owner_id,
            "name": g.get("name") or "Unknown",
            "family": g.get("family") or "",
            "alive": False,
        }
    return {"id": owner_id, "name": f"#{owner_id}", "family": "", "alive": None}


def _build_owner_indexes(characters: list[dict], owner_ids: set[int]) -> tuple[dict, dict]:
    """Build alive_index (id -> villager) and dead_index (id -> graveyard row)."""
    alive_index = {int(c.get("id", 0) or 0): c for c in characters if c.get("id")}
    missing = [oid for oid in owner_ids if oid not in alive_index and oid > 0]
    dead_index = graveyard_get_many(missing) if missing else {}
    return alive_index, dead_index


@artifact_bp.route("/artifacts", methods=["GET"])
def artifacts():
    """Catalog of all living (non-destroyed) artifacts in the world."""
    characters, _, year, day_in_year, _, _, _ = get_current_state()

    rows = artifact_repo.list_all_artifacts(include_destroyed=False)

    # Collect all ids referenced as current owner OR in lineage history.
    owner_ids: set[int] = set()
    for r in rows:
        owner_ids.add(int(r.get("owner_id", 0) or 0))
        for h in r.get("forged_history", []) or []:
            try:
                owner_ids.add(int(h.get("owner_id", 0) or 0))
                if h.get("to_id"):
                    owner_ids.add(int(h["to_id"]))
            except Exception:
                pass

    alive_index, dead_index = _build_owner_indexes(characters, owner_ids)

    enriched = []
    for r in rows:
        tpl = get_template(r.get("slug", "")) or {}
        owner = _resolve_owner_label(r.get("owner_id", 0), alive_index, dead_index)
        enriched.append({
            **r,
            "template": tpl,
            "owner": owner,
            "history_len": len(r.get("forged_history") or []),
        })

    # Sort: legendary first, then by lineage depth desc, then by name.
    rarity_rank = {"legendary": 0, "rare": 1, "uncommon": 2, "common": 3}
    enriched.sort(key=lambda a: (
        rarity_rank.get((a["template"].get("rarity") or "common"), 4),
        -a["history_len"],
        a["template"].get("name", "") or a.get("slug", ""),
    ))

    return render_template(
        "artifacts.html",
        active_page="artifacts",
        username=session.get("username"),
        year=year,
        day=day_in_year,
        artifacts=enriched,
        templates=list_templates(),
    )


@artifact_bp.route("/artifacts/<int:artifact_id>", methods=["GET"])
def artifact_detail(artifact_id: int):
    """Single artifact with full lineage."""
    art = artifact_repo.get_artifact(artifact_id)
    if not art:
        abort(404)

    characters, _, year, day_in_year, _, _, _ = get_current_state()
    tpl = get_template(art.get("slug", "")) or {}

    history = art.get("forged_history", []) or []
    owner_ids: set[int] = {int(art.get("owner_id", 0) or 0)}
    for h in history:
        try:
            owner_ids.add(int(h.get("owner_id", 0) or 0))
            if h.get("to_id"):
                owner_ids.add(int(h["to_id"]))
        except Exception:
            pass

    alive_index, dead_index = _build_owner_indexes(characters, owner_ids)
    owner = _resolve_owner_label(art.get("owner_id", 0), alive_index, dead_index)

    enriched_history = []
    for h in history:
        h_owner = _resolve_owner_label(h.get("owner_id", 0), alive_index, dead_index)
        h_recipient = _resolve_owner_label(h.get("to_id", 0), alive_index, dead_index) if h.get("to_id") else None
        enriched_history.append({**h, "owner": h_owner, "recipient": h_recipient})

    return render_template(
        "artifact_detail.html",
        active_page="artifacts",
        username=session.get("username"),
        year=year,
        day=day_in_year,
        artifact=art,
        template=tpl,
        owner=owner,
        history=enriched_history,
    )


@artifact_bp.route("/api/artifacts", methods=["GET"])
def api_artifacts():
    """JSON listing for ajax / future client use."""
    rows = artifact_repo.list_all_artifacts(include_destroyed=False)
    out = []
    for r in rows:
        tpl = get_template(r.get("slug", "")) or {}
        out.append({
            "id": r.get("id"),
            "slug": r.get("slug"),
            "name": tpl.get("name", ""),
            "rarity": tpl.get("rarity", ""),
            "slot": tpl.get("slot", ""),
            "owner_id": r.get("owner_id"),
            "history_len": len(r.get("forged_history") or []),
        })
    return jsonify({"artifacts": out, "count": len(out)})
