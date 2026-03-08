"""Family tree graph building and graveyard index construction."""
from __future__ import annotations

import json

from src.models import Villager
from world_utils import safe_int
from src.repositories.villager_repo import graveyard_get, graveyard_get_many


def parse_children_ids(raw) -> list[int]:
    """Parse childrenIds field from list, JSON string, or None."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [safe_int(i) for i in raw if safe_int(i) > 0]
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [safe_int(i) for i in data if safe_int(i) > 0]
        except Exception:
            return []
    return []


def parse_relationship_ids(raw) -> list[int]:
    """
    Accept dict or JSON-string dict of relationships.
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


def build_graveyard_index_for(characters: list[Villager]) -> dict:
    """
    Collect IDs referenced by current villagers (spouse/parents/children/relationships)
    that are missing from the live list, then fetch them from graveyard in one batch.

    Returns: {id: graveyard_row_dict}
    """
    live_ids = {safe_int(c.get("id")) for c in characters if safe_int(c.get("id")) > 0}
    need_ids: set[int] = set()

    for c in characters:
        # direct family refs
        for k in ("spouseId", "motherId", "fatherId"):
            pid = safe_int(c.get(k))
            if pid > 0 and pid not in live_ids:
                need_ids.add(pid)

        # children
        for cid in parse_children_ids(c.get("childrenIds")):
            if cid > 0 and cid not in live_ids:
                need_ids.add(cid)

        # relationships targets
        for oid in parse_relationship_ids(c.get("relationships")):
            if oid > 0 and oid not in live_ids:
                need_ids.add(oid)

    if not need_ids:
        return {}

    # returns dict keyed by int IDs
    return graveyard_get_many(sorted(need_ids)) or {}


def find_person(characters: list[Villager], person_id: int) -> dict | None:
    """Find a person by ID from live characters, falling back to graveyard."""
    for c in characters:
        if safe_int(c.get("id")) == person_id:
            return c
    return graveyard_get(person_id)


def build_family_graph(
    characters: list[Villager],
    root_id: int,
    up_depth: int = 3,
    down_depth: int = 3,
    max_nodes: int = 250,
) -> dict:
    """
    Build a vis-network graph payload (nodes + edges) for family tree.
    Includes graveyard fallback for pruned villagers.
    """

    live_by_id: dict[int, dict] = {}
    for c in characters:
        cid = safe_int(c.get("id"))
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
        lvl = safe_int(p.get("level"))
        if job:
            return f"{name}\n{job} \u2022 Lv {lvl}"
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
        age = safe_int(p.get("age"))
        lvl = safe_int(p.get("level"))
        rep = safe_int(p.get("rep"))
        coins = safe_int(p.get("coins"))

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
        sid = safe_int(root.get("spouseId") or root.get("spouse_id"))
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

        mother = safe_int(p.get("motherId"))
        father = safe_int(p.get("fatherId"))

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

        child_ids = parse_children_ids(p.get("childrenIds"))
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


def get_all_families(characters: list[Villager]) -> list[dict]:
    """
    Get all family names with their members.
    
    Returns list of dicts:
    [
        {
            "name": "Stormborn",
            "members": [villager_dicts...],
            "alive_count": int,
            "dead_count": int,
            "total_count": int,
            "avg_age": float,
            "total_wealth": int,
            "founders": [villager names without parents in family]
        }
    ]
    """
    # Group by family name
    family_map: dict[str, list[Villager]] = {}
    
    for c in characters:
        family = (c.get("family", "") or "").strip()
        if not family:
            family = "(No Family)"
        
        if family not in family_map:
            family_map[family] = []
        family_map[family].append(c)
    
    result = []
    
    for family_name, members in family_map.items():
        alive_members = [m for m in members if m.get("alive", True)]
        dead_members = [m for m in members if not m.get("alive", True)]
        
        # Calculate stats
        alive_count = len(alive_members)
        dead_count = len(dead_members)
        total_count = len(members)
        
        # Average age of living members
        if alive_members:
            avg_age = sum(int(m.get("age", 0) or 0) for m in alive_members) / len(alive_members)
        else:
            avg_age = 0
        
        # Total wealth of living members
        total_wealth = sum(int(m.get("coins", 0) or 0) for m in alive_members)
        
        # Find founders (members without parents in the same family)
        family_ids = {int(m.get("id", 0) or 0) for m in members}
        founders = []
        for m in members:
            mom_id = int(m.get("motherId", 0) or 0)
            dad_id = int(m.get("fatherId", 0) or 0)
            # If neither parent is in this family, they're a founder
            if mom_id not in family_ids and dad_id not in family_ids:
                founders.append(m.get("name", "?"))
        
        # Sort members: alive first, then by age descending
        sorted_members = sorted(
            members,
            key=lambda m: (
                0 if m.get("alive", True) else 1,  # alive first
                -int(m.get("age", 0) or 0),  # older first
            )
        )
        
        result.append({
            "name": family_name,
            "members": sorted_members,
            "alive_count": alive_count,
            "dead_count": dead_count,
            "total_count": total_count,
            "avg_age": round(avg_age, 1),
            "total_wealth": total_wealth,
            "founders": founders[:3],  # Top 3 founders
        })
    
    # Sort families by alive count descending
    result.sort(key=lambda f: (-f["alive_count"], f["name"]))
    
    return result
