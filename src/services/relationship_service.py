import json
import random

from config import (
    JOBS_NO_ROYAL,
)
from world_utils import (
    clamp,
    pick,
    rand_int,
)
from buildings import (
    get_building_level,
)

# Rough job groups for "guild" vibes
MILITARY_JOBS = {
    "Soldier", "Commander", "Guard", "Captain", "Ranger",
    "Archer", "Scout", "Falconer",
}
LEARNED_JOBS = {
    "Scholar", "Scribe", "Advisor", "Engineer", "Druid",
    "Alchemist", "Priest", "Healer",
}
COMMERCE_JOBS = {
    "Merchant", "Trader", "Innkeeper", "Jeweler", "Brewer",
    "Baker", "Butcher",
}
CRAFT_JOBS = {
    "Blacksmith", "Carpenter", "Mason", "Weaver", "Potter",
    "Glassblower", "Tanner",
}
NATURE_JOBS = {
    "Druid", "Forester", "Herbalist", "Shepherd", "Fisher",
    "Hunter", "Farmer", "Beekeeper",
}

# ---------------------------------------------------------------------------
#  Relationship helpers
# ---------------------------------------------------------------------------

def _family_key(v: dict) -> str:
    """Normalized family name. Falls back to last token of `name` if `family` is empty."""
    fam = (v.get("family") or "").strip().lower()
    if fam:
        return fam
    nm = (v.get("name") or "").strip()
    if nm and " " in nm:
        return nm.split()[-1].strip().lower()
    return ""

def _same_family(a: dict, b: dict) -> bool:
    fa = _family_key(a)
    fb = _family_key(b)
    return bool(fa and fb and fa == fb)

def _get_relations_dict(v: dict) -> dict:
    """
    Ensure v['relationships'] is a dict and return it.
    """
    rel = v.get("relationships")

    # If it's already a dict, just return it
    if isinstance(rel, dict):
        return rel

    # If it's a JSON string from CSV, try to parse
    if isinstance(rel, str) and rel.strip():
        try:
            parsed = json.loads(rel)
            if isinstance(parsed, dict):
                v["relationships"] = parsed
                return parsed
        except json.JSONDecodeError:
            pass  # fall through to empty dict

    # Otherwise create a fresh dict
    rel = {}
    v["relationships"] = rel
    return rel


def get_relationship_score(v: dict, other_id: int) -> int:
    rel = _get_relations_dict(v)
    try:
        return int(rel.get(str(other_id), 0))
    except (TypeError, ValueError):
        return 0


def set_relationship_score(v: dict, other_id: int, score: int):
    rel = _get_relations_dict(v)
    rel[str(other_id)] = int(score)


def adjust_relationship(v: dict, other: dict, delta: int):
    """
    Adjust relationship score between v -> other by delta, clamped [-100, 120].
    """
    oid = other.get("id")
    if oid is None:
        return
    cur = get_relationship_score(v, oid)
    set_relationship_score(v, oid, clamp(cur + delta, -100, 120))


def relationship_label(v: dict, other: dict) -> str | None:
    """
    Map numeric score to labels:
      friend, bestfriend, love (only Male-Female), rival, enemy.
    """
    oid = other.get("id")
    if oid is None:
        return None

    score = get_relationship_score(v, oid)
    g1 = v.get("gender")
    g2 = other.get("gender")

    # Love only for Male-Female pairs (your rule)
    is_mf_pair = {g1, g2} == {"Male", "Female"}

    if is_mf_pair and score >= 80:
        return "love"
    if score >= 65:
        return "bestfriend"
    if score >= 30:
        return "friend"
    if score <= -60:
        return "enemy"
    if score <= -30:
        return "rival"
    return None

def _append_last_action(v: dict, msg: str):
    if v.get("last_action"):
        v["last_action"] = f"{v['last_action']} / {msg}"
    else:
        v["last_action"] = msg


def _get_by_id(characters: list[dict], vid: int) -> dict | None:
    for c in characters:
        if c.get("id") == vid:
            return c
    return None


def _is_spouse_eligible(a: dict, b: dict) -> bool:
    if not a.get("alive", True) or not b.get("alive", True):
        return False
    if a.get("id") == b.get("id"):
        return False

    # Only man-woman pairs (your rule)
    if {a.get("gender"), b.get("gender")} != {"Male", "Female"}:
        return False

    # forbid same family name
    if _same_family(a, b):
        return False

    # Age constraints
    a_age = int(a.get("age", 0) or 0)
    b_age = int(b.get("age", 0) or 0)
    if not (18 <= a_age <= 60 and 18 <= b_age <= 60):
        return False

    return True


def _set_spouses(a: dict, b: dict, current_day: int):
    a["spouseId"] = b["id"]
    b["spouseId"] = a["id"]
    a["spouseSinceDay"] = current_day
    b["spouseSinceDay"] = current_day


def _clear_spouses(a: dict, b: dict, reason: str):
    a["spouseId"] = 0
    b["spouseId"] = 0
    a["spouseSinceDay"] = 0
    b["spouseSinceDay"] = 0
    _append_last_action(a, reason)
    _append_last_action(b, reason)


def _is_mutual_spouse(a: dict, b: dict) -> bool:
    return int(a.get("spouseId", 0) or 0) == b.get("id") and int(b.get("spouseId", 0) or 0) == a.get("id")


def _safe_int(x, default=0) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
#  Queen
# ---------------------------------------------------------------------------

def _get_current_king(characters: list[dict]) -> dict | None:
    """Return the first living King, else None."""
    for c in characters:
        if c.get("alive", True) and c.get("job") == "King":
            return c
    return None


def _demote_queen(q: dict):
    """
    Remove Queen title from someone (give them a normal job again).
    """
    if q.get("job") != "Queen":
        return

    prev = q.get("job_before_queen")
    q["job"] = prev if prev else pick(JOBS_NO_ROYAL)
    q.pop("job_before_queen", None)


def sync_queen_to_king_spouse(characters: list[dict], current_day: int | None = None):
    """
    Enforce: Queen must be the current King's spouse.
    If King has no spouse -> no Queen exists.
    """
    # 1) Find current living King
    king = _get_current_king(characters)

    # 2) Clear ALL current Queens first (we will assign the correct one if possible)
    for c in characters:
        if c.get("job") == "Queen":
            _demote_queen(c)

    if king is None:
        return

    spouse_id = int(king.get("spouseId", 0) or 0)
    if spouse_id == 0:
        return

    spouse = _get_by_id(characters, spouse_id)
    if spouse is None or not spouse.get("alive", True):
        return

    # 3) Assign spouse as Queen
    spouse["job_before_queen"] = spouse.get("job")
    spouse["job"] = "Queen"

    if current_day is not None:
        _append_last_action(spouse, f"became Queen (spouse of King {king.get('name','')})")


def spouse_daily_phase(characters: list[dict], current_day: int):
    """
    Daily spouse logic:
    - If relationship reaches 100 and label is 'love', chance to become spouses.
    - Each villager can have only 1 spouse (mutual spouseId).
    - Small chance to break up (more likely if love score is low).
    - Singles with strong love target can propose.
    """

    # --------- Fix broken spouse links (safety) ----------
    for v in characters:
        sid = int(v.get("spouseId", 0) or 0)
        if sid == 0:
            continue
        spouse = _get_by_id(characters, sid)
        if spouse is None or not spouse.get("alive", True):
            # widow/widower
            v["spouseId"] = 0
            v["spouseSinceDay"] = 0
            _append_last_action(v, "widowed")
            continue
        # must be mutual; otherwise clear
        if int(spouse.get("spouseId", 0) or 0) != v.get("id"):
            v["spouseId"] = 0
            v["spouseSinceDay"] = 0

    # --------- Breakup phase (very small) ----------
    for a in characters:
        if not a.get("alive", True):
            continue
        sid = int(a.get("spouseId", 0) or 0)
        if sid == 0:
            continue
        b = _get_by_id(characters, sid)
        if b is None or not b.get("alive", True):
            continue
        if _safe_int(a.get("id")) > _safe_int(b.get("id")):
            continue  # handle each couple once

        if not _is_mutual_spouse(a, b):
            continue

        score_ab = get_relationship_score(a, _safe_int(b.get("id")))
        score_ba = get_relationship_score(b, _safe_int(a.get("id")))
        score = min(score_ab, score_ba)

        # Base: extremely small because this runs every day
        p = 0.00002  # 0.002% per day (~0.73% per year)

        # Only increase a bit if relationship is truly bad
        if score < 70: p += 0.00003
        if score < 50: p += 0.00006
        if score < 30: p += 0.00012
        if score < 10: p += 0.00025
        if score < 0:  p += 0.00040

        # Cap: still small even at worst
        p = min(0.001, max(0.0, p))

        if random.random() < p:
            _clear_spouses(a, b, "broke up")
            continue

    # --------- Marriage / Proposal phase ----------
    singles = [v for v in characters if v.get("alive", True) and int(v.get("spouseId", 0) or 0) == 0]

    # Sort to reduce chaotic outcomes: older first, then higher rep
    singles.sort(key=lambda x: (-(x.get("age", 0) or 0), -(x.get("rep", 0) or 0)))

    for a in singles:
        if int(a.get("spouseId", 0) or 0) != 0:
            continue

        a_age = int(a.get("age", 0) or 0)
        if not (18 <= a_age <= 60):
            continue

        best_b = None
        best_score = -10**9

        for b in singles:
            if b.get("id") == a.get("id"):
                continue
            if int(b.get("spouseId", 0) or 0) != 0:
                continue
            if not _is_spouse_eligible(a, b):
                continue

            label = relationship_label(a, b)
            if label != "love":
                continue

            s1 = get_relationship_score(a, b["id"])
            s2 = get_relationship_score(b, a["id"])
            s = min(s1, s2)

            if s < 100:
                continue

            if s > best_score:
                best_score = s
                best_b = b

        if best_b is None:
            continue

        p_marry = 0.04
        p_marry = min(0.10, p_marry + max(0, best_score - 100) * 0.002)

        if random.random() < p_marry:
            _set_spouses(a, best_b, current_day)
            _append_last_action(a, f"married {best_b['name']}")
            _append_last_action(best_b, f"married {a['name']}")

    # Late import to avoid circular dependency
    from src.services.family_service import birth_daily_phase
    birth_daily_phase(characters, current_day=current_day)

    sync_queen_to_king_spouse(characters, current_day=current_day)


# ---------------------------------------------------------------------------
#  Corruption + assassination
# ---------------------------------------------------------------------------

def maybe_corrupt_from_bank(v: dict, bank: dict | None) -> int:
    """
    Small daily chance for King / Queen / Noble to skim coins
    from the village bank into their own pocket.
    """
    if bank is None:
        return 0
    if not v.get("alive", True):
        return 0

    job = v.get("job", "")
    if job not in ("King", "Queen", "Noble"):
        return 0

    balance = int(bank.get("balance", 0) or 0)
    if balance <= 0:
        return 0

    # --- base probability ---
    traits_str = v.get("traits", "") or ""
    traits = [t.strip() for t in traits_str.split(",") if t.strip()]

    base_chance = 0.03

    if "Greedy" in traits:
        base_chance += 0.04
    if "Ambitious" in traits:
        base_chance += 0.02
    if "Loyal" in traits:
        base_chance -= 0.02
    if "Generous" in traits:
        base_chance -= 0.01

    if get_building_level(bank, "treasury") > 0:
        base_chance += 0.01
    if get_building_level(bank, "tax_office") > 0:
        base_chance -= 0.01

    base_chance = max(0.0, min(0.15, base_chance))

    if random.random() >= base_chance:
        return 0

    # --- amount stolen ---
    fraction = random.uniform(0.02, 0.08)
    stolen = max(5, int(balance * fraction))
    stolen = min(stolen, balance)

    if stolen <= 0:
        return 0

    bank["balance"] = balance - stolen
    v["coins"] = v.get("coins", 0) + stolen

    rep_penalty = rand_int(3, 10)
    v["rep"] = clamp(v.get("rep", 0) - rep_penalty, -100, 100)

    msg = f"corruption: skimmed {stolen} coins from treasury (rep -{rep_penalty})"
    if v.get("last_action"):
        v["last_action"] = f"{v['last_action']} / {msg}"
    else:
        v["last_action"] = msg

    return stolen

def _mark_dead(characters, victim, reason, current_day=None):
    sid = int(victim.get("spouseId", 0) or 0)
    if sid:
        victim["spouseId_at_death"] = sid

    victim["hp"] = 0
    victim["alive"] = False
    victim["last_action"] = reason
    if current_day is not None:
        victim["death_day"] = int(current_day)

    # widow/widower
    if sid:
        spouse = _get_by_id(characters, sid)
        if spouse and spouse.get("alive", True):
            spouse["spouseId"] = 0
            spouse["spouseSinceDay"] = 0
            _append_last_action(spouse, "widowed")

    victim["spouseId"] = 0
    victim["spouseSinceDay"] = 0


def king_assassination_phase(characters: list[dict], bank: dict | None = None, current_day: int | None = None) -> bool:
    """
    Small chance per day: if King has an enemy, the King assassinates 1 enemy.
    """
    from src.services.election_service import get_traits_set

    king = _get_current_king(characters)
    if king is None or not king.get("alive", True):
        return False

    enemies = []
    king_id = king.get("id")
    king_spouse = int(king.get("spouseId", 0) or 0)

    for o in characters:
        if not o.get("alive", True):
            continue
        if o.get("id") == king_id:
            continue
        if o.get("id") == king_spouse:
            continue

        s1 = get_relationship_score(king, o["id"])
        s2 = get_relationship_score(o, king_id)
        if min(s1, s2) <= -60 or relationship_label(king, o) == "enemy" or relationship_label(o, king) == "enemy":
            enemies.append(o)

    if not enemies:
        return False

    p = 0.008

    kt = get_traits_set(king)
    if "Deceitful" in kt:  p += 0.008
    if "Ambitious" in kt:  p += 0.004
    if "Hot-headed" in kt: p += 0.003
    if "Brave" in kt:      p += 0.002
    if "Loyal" in kt:      p -= 0.003
    if "Generous" in kt:   p -= 0.003
    if "Empathic" in kt:   p -= 0.003
    if "Wise" in kt:       p -= 0.001

    if bank is not None:
        lvl_barracks = get_building_level(bank, "barracks")
        lvl_walls = get_building_level(bank, "walls")
        p += 0.002 * lvl_barracks
        p += 0.001 * lvl_walls

    p = max(0.0, min(0.05, p))

    if random.random() >= p:
        return False

    enemies.sort(key=lambda o: (min(get_relationship_score(king, o["id"]),
                                   get_relationship_score(o, king_id))))
    target = enemies[0]

    _mark_dead(characters, target, "killed by assassinate", current_day=current_day)
    _append_last_action(king, f"assassinated {target.get('name','an enemy')}")

    sync_queen_to_king_spouse(characters, current_day=current_day)
    return True
