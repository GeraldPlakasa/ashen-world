"""Player character creation and pinned character data extraction."""
from __future__ import annotations

import random

import config
from config import TRAITS, JOBS_NO_ROYAL
from src.models import Villager
from src.utils.world_utils import safe_int
from src.services.villager_service import make_row, reset_id_from_characters
from src.repositories.villager_repo import load_villagers, save_villagers, graveyard_get_many
from src.services.family_tree_service import parse_children_ids


def create_player_character(
    username: str,
    given_name: str,
    family: str,
    chosen_trait: str,
    gender: str,
) -> tuple[bool, str, Villager | None]:
    """
    Create a player character under the state lock.

    Returns:
        (success, message_or_error_code, new_villager_or_none)

    Error codes when success=False:
        "already_exists" - user already has a character
        "name_taken" - full name already in use
    """
    from src.services.world_service import _state_lock

    full_name = f"{given_name} {family}"

    with _state_lock:
        characters = load_villagers()

        # Check if user already has a LIVING player character
        # Allow creating new hero if previous one died or achieved greatness
        existing = next(
            (c for c in characters 
             if c.get("origin") == "player" 
             and c.get("owner") == username
             and c.get("alive", True)),  # Only block if existing hero is alive
            None,
        )
        if existing:
            return False, "already_exists", None

        taken_names = {c.get("name", "") for c in characters}
        if full_name in taken_names:
            return False, "name_taken", None

        # sync internal ID counter
        reset_id_from_characters(characters)

        # ensure internal ID counter is at least current max ID
        if characters:
            max_id = max(c.get("id", 0) for c in characters)
            if config._next_villager_id < max_id:
                config._next_villager_id = max_id

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
        save_villagers(characters)

    return True, full_name, new_row


def get_pinned_character_data(username: str, characters: list[Villager]) -> dict | None:
    """
    Find and prepare display data for a user's pinned player character.

    Returns dict with keys:
        character, actions, rel_bonds, rel_conflicts,
        spouse_name, spouse_alive, mother, father, children
    or None if no pinned character found.
    """
    if not username:
        return None

    # Build ID index
    id_to_char: dict[int, Villager] = {}
    for cc in characters:
        cid = safe_int(cc.get("id"))
        if cid > 0:
            id_to_char[cid] = cc

    # Find pinned character
    pinned = None
    for c in characters:
        if c.get("origin") == "player" and c.get("owner") == username:
            pinned = c
            break

    if pinned is None:
        return None

    # Collect all referenced IDs for batch graveyard lookup
    rel_raw = pinned.get("relationships") or {}
    rel_ids: list[int] = []
    if isinstance(rel_raw, dict):
        for k in rel_raw.keys():
            try:
                rel_ids.append(int(k))
            except Exception:
                continue

    spouse_id = safe_int(pinned.get("spouseId"))
    mother_id = safe_int(pinned.get("motherId"))
    father_id = safe_int(pinned.get("fatherId"))
    child_ids = parse_children_ids(pinned.get("childrenIds"))

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
    result_spouse_name = None
    result_spouse_alive = None
    if spouse_id > 0:
        s_name, s_alive, _, _ = _resolve_person(spouse_id)
        result_spouse_name = s_name
        result_spouse_alive = s_alive

    # --- Mother / Father ---
    result_mother = None
    result_father = None
    if mother_id > 0:
        m_name, m_alive, _, _ = _resolve_person(mother_id)
        result_mother = {"id": mother_id, "name": m_name, "alive": m_alive}

    if father_id > 0:
        f_name, f_alive, _, _ = _resolve_person(father_id)
        result_father = {"id": father_id, "name": f_name, "alive": f_alive}

    # --- Children ---
    result_children = []
    for cid in child_ids:
        ch_name, ch_alive, _, _ = _resolve_person(cid)
        result_children.append({"id": cid, "name": ch_name, "alive": ch_alive})

    # --- Action history ---
    result_actions: list[str] = []
    hist_str = pinned.get("action_log", "") or ""
    if hist_str:
        actions = [a.strip() for a in hist_str.split("||") if a.strip()]
        result_actions = list(reversed(actions))

    # --- Relationship summary (supports graveyard) ---
    result_rel_bonds: list[dict] = []
    result_rel_conflicts: list[dict] = []

    if isinstance(rel_raw, dict):
        rel_entries: list[dict] = []
        g1 = pinned.get("gender")

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

        result_rel_bonds = positives[:3]
        result_rel_conflicts = negatives[:3]

    return {
        "character": pinned,
        "actions": result_actions,
        "rel_bonds": result_rel_bonds,
        "rel_conflicts": result_rel_conflicts,
        "spouse_name": result_spouse_name,
        "spouse_alive": result_spouse_alive,
        "mother": result_mother,
        "father": result_father,
        "children": result_children,
    }
