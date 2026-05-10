"""
Artifact service — business logic for magical artifacts.

Templates (config.ARTIFACT_TEMPLATES) define what an item *is*.
Instances (artifacts table) track who currently holds it and its lineage.

Phase 1 surface: template lookup, drop-rolling, equip helpers.
Phase 2 surface: combat-drop entrypoint used by action_service.
Later phases will add: effective_stats wrapper, inheritance flow, UI.
"""
from __future__ import annotations

import random
from typing import Any

import config
from src.repositories import artifact_repo
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
#  Template lookup
# ---------------------------------------------------------------------------

_TEMPLATES_BY_SLUG: dict[str, dict[str, Any]] = {
    t["slug"]: t for t in getattr(config, "ARTIFACT_TEMPLATES", [])
}


def get_template(slug: str) -> dict[str, Any] | None:
    return _TEMPLATES_BY_SLUG.get(slug)


def list_templates() -> list[dict[str, Any]]:
    return list(_TEMPLATES_BY_SLUG.values())


def slot_field(slot: str) -> str:
    """Map an artifact slot to its villager column name."""
    return f"equip_{slot}"


def is_valid_slot(slot: str) -> bool:
    return slot in getattr(config, "ARTIFACT_SLOTS", [])


# ---------------------------------------------------------------------------
#  Equip helpers
# ---------------------------------------------------------------------------

def get_equipped_id(v: dict, slot: str) -> int:
    return int(v.get(slot_field(slot), 0) or 0)


def equip(v: dict, slot: str, artifact_id: int) -> None:
    """Set the villager's equip slot to the given artifact id (no DB transfer)."""
    if not is_valid_slot(slot):
        return
    v[slot_field(slot)] = int(artifact_id or 0)


def unequip_slot(v: dict, slot: str) -> int:
    """Clear the slot. Returns the previously equipped artifact id (0 if empty)."""
    if not is_valid_slot(slot):
        return 0
    prev = int(v.get(slot_field(slot), 0) or 0)
    v[slot_field(slot)] = 0
    return prev


def auto_equip_if_better(v: dict, artifact_id: int, template: dict[str, Any]) -> bool:
    """
    Equip the artifact on `v` if the slot is empty or the new artifact's rarity
    is strictly higher than the currently equipped one.

    Returns True if equipped, False otherwise.
    """
    slot = template.get("slot", "")
    if not is_valid_slot(slot):
        return False

    current_id = get_equipped_id(v, slot)
    if current_id <= 0:
        equip(v, slot, artifact_id)
        return True

    current = artifact_repo.get_artifact(current_id)
    if not current:
        equip(v, slot, artifact_id)
        return True

    current_tpl = get_template(current.get("slug", ""))
    rarity_order = config.ARTIFACT_RARITY_ORDER
    new_rank = rarity_order.get(template.get("rarity", "common"), 1)
    cur_rank = rarity_order.get((current_tpl or {}).get("rarity", "common"), 1)

    if new_rank > cur_rank:
        equip(v, slot, artifact_id)
        return True
    return False


# ---------------------------------------------------------------------------
#  Effective stats — base + equipped artifact mods (read-only snapshot)
# ---------------------------------------------------------------------------

_STAT_KEYS = ("atk", "def", "int", "hp", "mp", "rep")


def _equipped_artifact_ids(v: dict) -> list[int]:
    out: list[int] = []
    for slot in getattr(config, "ARTIFACT_SLOTS", []):
        aid = int(v.get(slot_field(slot), 0) or 0)
        if aid > 0:
            out.append(aid)
    return out


def get_equipped_with_templates(v: dict) -> list[dict]:
    """
    Return one row per slot for the given villager, joined with template data.
    Empty slots come back with artifact=None / template=None so the UI can
    render them as blanks.

    Each row: {slot, artifact, template}
    """
    out: list[dict] = []
    slot_to_id = {}
    for slot in getattr(config, "ARTIFACT_SLOTS", []):
        slot_to_id[slot] = int(v.get(slot_field(slot), 0) or 0)

    ids = [aid for aid in slot_to_id.values() if aid > 0]
    artifacts = artifact_repo.get_artifacts_by_ids(ids) if ids else {}

    for slot in getattr(config, "ARTIFACT_SLOTS", []):
        aid = slot_to_id.get(slot, 0)
        if aid <= 0:
            out.append({"slot": slot, "artifact": None, "template": None})
            continue
        art = artifacts.get(aid)
        if not art or art.get("destroyed"):
            out.append({"slot": slot, "artifact": None, "template": None})
            continue
        tpl = get_template(art.get("slug", ""))
        out.append({"slot": slot, "artifact": art, "template": tpl})
    return out


def equip_mods(v: dict) -> dict[str, int]:
    """
    Sum of stat_mods across all currently equipped (non-destroyed) artifacts.
    Returns zeros for stats not modified. Cheap when no slots are filled
    (skips DB read entirely).
    """
    totals = {k: 0 for k in _STAT_KEYS}
    ids = _equipped_artifact_ids(v)
    if not ids:
        return totals

    try:
        artifacts = artifact_repo.get_artifacts_by_ids(ids)
    except Exception as exc:
        logger.warning("equip_mods DB read failed: %s", exc)
        return totals

    for art in artifacts.values():
        if art.get("destroyed"):
            continue
        tpl = get_template(art.get("slug", ""))
        if not tpl:
            continue
        for stat, val in (tpl.get("stat_mods") or {}).items():
            if stat in totals:
                try:
                    totals[stat] += int(val or 0)
                except Exception:
                    pass
    return totals


def effective_stats(v: dict) -> dict[str, int]:
    """
    Return a snapshot of base stats + equipped artifact mods.
    Does NOT mutate the villager; base stats remain authoritative.
    """
    base = {k: int(v.get(k, 0) or 0) for k in _STAT_KEYS}
    mods = equip_mods(v)
    return {k: base[k] + mods.get(k, 0) for k in _STAT_KEYS}


# ---------------------------------------------------------------------------
#  Drop rolling
# ---------------------------------------------------------------------------

# Per-tier drop chances and rarity weights for combat kills.
# Tuned to be genuinely scarce — players should remember the day a hero pulled
# a rare artifact off a corpse. Most kills produce nothing.
_TIER_DROP_CHANCE = {
    "common": 0.001,    # 0.1% per common kill (1 in 1000)
    "elite": 0.007,     # 0.7% per elite kill
    "legendary": 0.08,  # 8% per legendary kill
}

_TIER_RARITY_WEIGHTS = {
    "common":    {"common": 1.00, "uncommon": 0.00, "rare": 0.00, "legendary": 0.00},
    "elite":     {"common": 0.85, "uncommon": 0.14, "rare": 0.01, "legendary": 0.00},
    "legendary": {"common": 0.50, "uncommon": 0.38, "rare": 0.11, "legendary": 0.01},
}


def _pick_weighted(weights: dict[str, float]) -> str:
    items = list(weights.items())
    total = sum(w for _, w in items) or 1.0
    r = random.random() * total
    acc = 0.0
    for k, w in items:
        acc += w
        if r <= acc:
            return k
    return items[-1][0]


def roll_drop_for_tier(tier: str) -> dict[str, Any] | None:
    """
    Decide whether a kill of `tier` drops an artifact and which template.
    Returns the template dict, or None if no drop.
    """
    chance = _TIER_DROP_CHANCE.get(tier, 0.03)
    if random.random() >= chance:
        return None

    rarity_weights = _TIER_RARITY_WEIGHTS.get(tier, _TIER_RARITY_WEIGHTS["common"])
    rarity = _pick_weighted(rarity_weights)

    candidates = [t for t in list_templates() if t.get("rarity") == rarity]
    if not candidates:
        # Fallback: any template at all
        candidates = list_templates()
    if not candidates:
        return None
    return random.choice(candidates)


# ---------------------------------------------------------------------------
#  Forge eligibility — many parameters, all required.
# ---------------------------------------------------------------------------

# Configurable thresholds — bumped deliberately high so forging is rare.
FORGE_MIN_INT = 50
FORGE_MIN_LEVEL = 15
FORGE_MIN_AGE = 25
FORGE_MIN_HP = 70
FORGE_MAX_HUNGER = 60
FORGE_MIN_TREASURY = 800
FORGE_COOLDOWN_DAYS = 365         # one game-year between attempts
FORGE_FAILURE_CHANCE = 0.40       # even when eligible, 40% of attempts produce nothing
FORGE_BASE_COST_MIN = 600
FORGE_BASE_COST_MAX = 1000

FORGE_JOBS = ("Blacksmith", "Wizard", "Sorcerer")
_SMITH_SKILL_CATEGORIES = ("CRAFT", "KNOWLEDGE")
_MAGE_SKILL_CATEGORIES = ("MAGIC", "KNOWLEDGE")


def _has_forge_skill(v: dict, allowed_categories: tuple) -> bool:
    """Returns True if the villager has at least one skill in the given categories."""
    try:
        from src.services.skill_service import parse_skills, get_skill_info
    except Exception:
        return False
    skills = parse_skills(v.get("skills", "") or "")
    for sk in skills:
        info = get_skill_info(sk)
        if info and info.get("category", "") in allowed_categories:
            return True
    return False


def can_forge(v: dict, bank: dict | None, current_day: int | None) -> tuple[bool, str]:
    """
    Return (eligible, reason). reason is empty when eligible, otherwise a short
    explanation suitable for action_log / debug output.

    Required parameters (all must hold):
        - job ∈ FORGE_JOBS
        - alive
        - INT ≥ FORGE_MIN_INT
        - level ≥ FORGE_MIN_LEVEL
        - age ≥ FORGE_MIN_AGE
        - hp ≥ FORGE_MIN_HP
        - hunger ≤ FORGE_MAX_HUNGER
        - treasury ≥ FORGE_MIN_TREASURY
        - bank exists and has the right building level:
            * Blacksmith → blacksmith building level ≥ 1
            * Wizard / Sorcerer → library building level ≥ 2
        - has at least one CRAFT/KNOWLEDGE skill (smiths) or MAGIC/KNOWLEDGE skill (mages)
        - cooldown elapsed since last_forge_day (≥ FORGE_COOLDOWN_DAYS)
    """
    if not v.get("alive", True):
        return False, "deceased"
    job = (v.get("job") or "").strip()
    if job not in FORGE_JOBS:
        return False, "wrong job"
    if int(v.get("int", 0) or 0) < FORGE_MIN_INT:
        return False, f"INT < {FORGE_MIN_INT}"
    if int(v.get("level", 0) or 0) < FORGE_MIN_LEVEL:
        return False, f"level < {FORGE_MIN_LEVEL}"
    if int(v.get("age", 0) or 0) < FORGE_MIN_AGE:
        return False, f"age < {FORGE_MIN_AGE}"
    if int(v.get("hp", 0) or 0) < FORGE_MIN_HP:
        return False, f"hp < {FORGE_MIN_HP}"
    if int(v.get("hunger", 0) or 0) > FORGE_MAX_HUNGER:
        return False, "too hungry"
    if bank is None:
        return False, "no bank"
    if int(bank.get("balance", 0) or 0) < FORGE_MIN_TREASURY:
        return False, f"treasury < {FORGE_MIN_TREASURY}"

    # Building requirement.
    try:
        from src.services.building_service import get_building_level
        if job == "Blacksmith":
            if get_building_level(bank, "blacksmith") < 1:
                return False, "no blacksmith building"
        else:
            if get_building_level(bank, "library") < 2:
                return False, "library < lvl 2"
    except Exception:
        return False, "building lookup failed"

    # Skill prerequisite.
    allowed = _SMITH_SKILL_CATEGORIES if job == "Blacksmith" else _MAGE_SKILL_CATEGORIES
    if not _has_forge_skill(v, allowed):
        return False, "missing forge skill"

    # Cooldown.
    last = int(v.get("last_forge_day", 0) or 0)
    if last > 0 and current_day is not None:
        if int(current_day) - last < FORGE_COOLDOWN_DAYS:
            return False, "forge cooldown"

    return True, ""


# ---------------------------------------------------------------------------
#  Phase 2 entrypoint: combat-drop pipeline
# ---------------------------------------------------------------------------

def drop_for_kill(
    killer: dict,
    enemy: dict,
    current_day: int,
) -> dict[str, Any] | None:
    """
    Roll an artifact drop after a successful kill, persist the instance,
    and auto-equip on the killer if appropriate.

    Returns a result dict for callers (chronicle/UI) or None if no drop:
        {
          "artifact_id": int,
          "template": template_dict,
          "equipped": bool,
        }
    """
    if not killer or not enemy:
        return None

    tier = enemy.get("tier", "common")
    template = roll_drop_for_tier(tier)
    if not template:
        return None

    try:
        artifact_id = artifact_repo.create_artifact(
            slug=template["slug"],
            owner_id=int(killer.get("id", 0) or 0),
            acquired_day=int(current_day or 0),
            acquired_via=f"combat:{tier}:{enemy.get('name','enemy')}",
            forged_history=[
                {
                    "owner_id": int(killer.get("id", 0) or 0),
                    "owner_name": (killer.get("name") or "").strip(),
                    "day": int(current_day or 0),
                    "event": "acquired",
                    "via": f"slew {tier} {enemy.get('name','enemy')}",
                }
            ],
        )
    except Exception as exc:
        logger.warning("Artifact drop persist failed: %s", exc)
        return None

    equipped = auto_equip_if_better(killer, artifact_id, template)

    return {
        "artifact_id": artifact_id,
        "template": template,
        "equipped": equipped,
    }


# ---------------------------------------------------------------------------
#  Inheritance (Phase 4)
# ---------------------------------------------------------------------------

# Treasury reward when an artifact has no heir and gets liquidated.
_LIQUIDATION_GOLD = {
    "common": 50,
    "uncommon": 150,
    "rare": 500,
    "legendary": 2000,
}


def _safe_int(x, default: int = 0) -> int:
    try:
        return int(x or 0)
    except Exception:
        return default


def _living_children(deceased: dict, id_map: dict[int, dict]) -> list[dict]:
    out: list[dict] = []
    raw = deceased.get("childrenIds", []) or []
    if isinstance(raw, str):
        try:
            import json as _json
            raw = _json.loads(raw or "[]")
        except Exception:
            raw = []
    for cid in raw:
        cid = _safe_int(cid)
        if cid <= 0:
            continue
        c = id_map.get(cid)
        if c and c.get("alive", True):
            out.append(c)
    # Sort by age desc — oldest first
    out.sort(key=lambda c: _safe_int(c.get("age", 0)), reverse=True)
    return out


def _living_spouse(deceased: dict, id_map: dict[int, dict]) -> dict | None:
    sid = _safe_int(deceased.get("spouseId_at_death", 0)) or _safe_int(deceased.get("spouseId", 0))
    if sid <= 0:
        return None
    s = id_map.get(sid)
    if s and s.get("alive", True):
        return s
    return None


def _living_siblings(deceased: dict, characters: list[dict]) -> list[dict]:
    """Living siblings — share at least one parent with the deceased, but aren't the deceased."""
    mom = _safe_int(deceased.get("motherId", 0))
    dad = _safe_int(deceased.get("fatherId", 0))
    if mom <= 0 and dad <= 0:
        return []
    did = _safe_int(deceased.get("id", 0))
    out = []
    for c in characters:
        if not c.get("alive", True):
            continue
        if _safe_int(c.get("id", 0)) == did:
            continue
        cm = _safe_int(c.get("motherId", 0))
        cd = _safe_int(c.get("fatherId", 0))
        if (mom > 0 and cm == mom) or (dad > 0 and cd == dad):
            out.append(c)
    out.sort(key=lambda c: _safe_int(c.get("age", 0)), reverse=True)
    return out


def settle_artifact_inheritance(
    deceased: dict,
    characters: list[dict],
    bank: dict | None,
    current_day: int,
) -> list[dict]:
    """
    Settle every artifact owned by `deceased` according to the inheritance flow:

      1. Soulbound -> destroy.
      2. Else pick heir: oldest living child > spouse > oldest living sibling.
      3. Else liquidate to treasury for a rarity-scaled gold reward.

    For each artifact: append a chronicle-style entry to forged_history,
    auto-equip on the heir (if better/empty), and emit a chronicle event.

    Returns a list of inheritance result dicts (for callers/tests).
    """
    from src.services.chronicle_service import (
        record_artifact_inheritance,
        record_artifact_destroyed,
        record_artifact_liquidated,
    )

    did = _safe_int(deceased.get("id", 0))
    if did <= 0:
        return []

    try:
        owned = artifact_repo.list_artifacts_for_owner(did)
    except Exception as exc:
        logger.warning("settle_artifact_inheritance load failed: %s", exc)
        return []

    if not owned:
        return []

    id_map = {_safe_int(c.get("id", 0)): c for c in characters}
    results: list[dict] = []

    for art in owned:
        slug = art.get("slug", "")
        template = get_template(slug)
        artifact_id = _safe_int(art.get("id", 0))
        if not template or artifact_id <= 0:
            continue

        history_entry_base = {
            "owner_id": did,
            "owner_name": (deceased.get("name") or "").strip(),
            "day": int(current_day),
        }

        # 1. Soulbound — destroy with owner.
        if (template.get("binding") or "").lower() == "soulbound":
            try:
                artifact_repo.append_history(
                    artifact_id,
                    {**history_entry_base, "event": "destroyed_with_owner"},
                )
                artifact_repo.destroy_artifact(artifact_id)
            except Exception as exc:
                logger.warning("Soulbound destroy failed: %s", exc)
            try:
                record_artifact_destroyed(template, deceased, current_day)
            except Exception:
                pass
            results.append({"artifact_id": artifact_id, "outcome": "destroyed", "template": template})
            continue

        # 2. Pick heir: child > spouse > sibling.
        heir: dict | None = None
        relation = ""
        for h in _living_children(deceased, id_map):
            heir, relation = h, "child"
            break
        if heir is None:
            s = _living_spouse(deceased, id_map)
            if s:
                heir, relation = s, "spouse"
        if heir is None:
            sibs = _living_siblings(deceased, characters)
            if sibs:
                heir, relation = sibs[0], "sibling"

        if heir is not None:
            heir_id = _safe_int(heir.get("id", 0))
            try:
                artifact_repo.transfer_artifact(artifact_id, heir_id)
                artifact_repo.append_history(
                    artifact_id,
                    {
                        **history_entry_base,
                        "event": "inherited",
                        "to_id": heir_id,
                        "to_name": (heir.get("name") or "").strip(),
                        "relation": relation,
                    },
                )
            except Exception as exc:
                logger.warning("Artifact transfer failed: %s", exc)
                continue

            equipped = auto_equip_if_better(heir, artifact_id, template)
            history_count = len(art.get("forged_history") or []) + 1
            try:
                record_artifact_inheritance(
                    artifact_template=template,
                    deceased=deceased,
                    heir=heir,
                    relation=relation,
                    day=current_day,
                    history_count=history_count,
                )
            except Exception:
                pass

            results.append({
                "artifact_id": artifact_id,
                "outcome": "inherited",
                "template": template,
                "heir_id": heir_id,
                "relation": relation,
                "equipped": equipped,
            })
            continue

        # 3. No heirs — liquidate.
        rarity = template.get("rarity", "common")
        gold = _LIQUIDATION_GOLD.get(rarity, 50)
        try:
            artifact_repo.append_history(
                artifact_id,
                {**history_entry_base, "event": "liquidated", "gold": gold},
            )
            artifact_repo.destroy_artifact(artifact_id)
        except Exception as exc:
            logger.warning("Liquidation failed: %s", exc)

        if bank is not None:
            try:
                bank["balance"] = _safe_int(bank.get("balance", 0)) + gold
            except Exception:
                pass

        try:
            record_artifact_liquidated(template, deceased, gold, current_day)
        except Exception:
            pass

        results.append({
            "artifact_id": artifact_id,
            "outcome": "liquidated",
            "template": template,
            "gold": gold,
        })

    return results
