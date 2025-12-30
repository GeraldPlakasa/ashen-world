import json
import random
import math

from config import (
    JOBS_POOL,
    JOBS_NO_ROYAL,
    KING_MAX_TERMS,
    DYNASTY_BONUS,
    TRAITS,
    NAME_PREFIX,
    NAME_SUFFIX,
    CHILD_MAX_AGE,
    BIRTH_BASE_P,
    BIRTH_COOLDOWN_DAYS,
    COUPLE_DECAY,
    FAMILY_DECAY,
)
from world_utils import (
    clamp,
    pick,
    rand_int,
    pick_weighted,
)
from buildings import (
    get_building_level,
)

# Rough job groups for “guild” vibes
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
#  Royal / election
# ---------------------------------------------------------------------------

def get_traits_set(v: dict) -> set[str]:
    """Parse v['traits'] into a set of clean trait strings."""
    traits_str = v.get("traits", "") or ""
    return {t.strip() for t in traits_str.split(",") if t.strip()}

def leadership_score(c: dict, prev_king: dict | None = None) -> float:
    """
    Leadership score for a candidate:
    stats + traits + age shaping + dynasty bonus.
    """
    if not c.get("alive", True):
        return -1e9

    s = 0.0
    s += c.get("int", 0)   * 1.2
    s += c.get("rep", 0)   * 0.9
    s += c.get("level", 1) * 2.0
    s += c.get("atk", 0)   * 0.4
    s += c.get("def", 0)   * 0.5

    # Age shaping (prefer ~22–55)
    age = c.get("age", 0) or 0
    if age < 18:
        s -= 1000
    elif age < 22:
        s -= 12
    elif age > 55:
        s -= 8
    else:
        s += 5

    t = get_traits_set(c)
    def add(x: float):
        nonlocal s
        s += x

    if "Wise"       in t: add(14)
    if "Generous"   in t: add(8)
    if "Loyal"      in t: add(8)
    if "Brave"      in t: add(6)
    if "Empathic"   in t: add(6)
    if "Diligent"   in t: add(6)
    if "Patient"    in t: add(5)
    if "Ambitious"  in t: add(3)
    if "Cautious"   in t: add(2)

    if "Greedy"     in t: add(-10)
    if "Deceitful"  in t: add(-12)
    if "Hot-headed" in t: add(-8)
    if "Lazy"       in t: add(-10)
    if "Reckless"   in t: add(-6)

    # Dynasty bonus: same family as previous King
    if prev_king and c.get("family") and c.get("family") == prev_king.get("family"):
        s += DYNASTY_BONUS

    return s


def voter_adjustment(v: dict, c: dict) -> float:
    """
    How a voter tweaks a candidate's appeal (affinity/alignment).
    """
    if not v.get("alive", True):
        return 0.0

    a = 0.0
    vt = get_traits_set(v)
    ct = get_traits_set(c)

    # Shared values
    for tr in ct:
        if tr in vt:
            a += 1.0

    # Simple oppositions
    if "Generous" in vt and "Greedy" in ct:
        a -= 1.0
    if "Greedy" in vt and "Generous" in ct:
        a -= 1.0
    if "Cautious" in vt and "Hot-headed" in ct:
        a -= 1.0
    if "Wise" in vt and "Reckless" in ct:
        a -= 1.0

    # Kinship & “guild” vibes
    if v.get("family") and v.get("family") == c.get("family"):
        a += 1.5

    job_v = v.get("job", "")
    if job_v in MILITARY_JOBS and ({"Brave", "Cautious", "Wise"} & ct):
        a += 0.8
    if job_v in LEARNED_JOBS and ({"Wise", "Patient", "Generous"} & ct):
        a += 0.8
    if (job_v in COMMERCE_JOBS or job_v in CRAFT_JOBS) and ({"Diligent", "Wise", "Loyal"} & ct):
        a += 0.6
    if job_v in NATURE_JOBS and ({"Brave", "Empathic", "Wise"} & ct):
        a += 0.6

    # Tiny random “likeability” noise
    a += random.random() * 0.5
    return a

def reassign_job_by_traits(p: dict) -> str:
    """
    Trait-based job reassignment for a dethroned king.
    Returns the new job string.
    """
    weights = {j: 1.0 for j in JOBS_POOL}
    def add(job: str, w: float = 1.0):
        if job in weights:
            weights[job] += w

    t = get_traits_set(p)
    power = p.get("atk", 0) + p.get("def", 0)
    high_int = p.get("int", 0) > 65
    high_rep = p.get("rep", 0) > 40
    high_hp  = p.get("hp", 0) > 180
    high_lvl = p.get("level", 1) >= 8

    # Stats nudges
    if high_int:
        for j in ["Scholar", "Advisor", "Alchemist", "Priest", "Scribe", "Engineer", "Clerk"]:
            add(j, 2 if j in ("Scholar", "Advisor", "Scribe", "Engineer") else 1)
    if power > 180:
        for j in ["Soldier", "Guard", "Commander", "Captain", "Ranger", "Archer", "Falconer"]:
            add(j, 2 if j in ("Soldier", "Guard") else 1)
    if high_rep:
        for j in ["Noble", "Advisor", "Innkeeper", "Trader"]:
            add(j, 2 if j == "Noble" else 1)
    if high_hp:
        for j in ["Guard", "Soldier", "Miner", "Mason", "Woodcutter"]:
            add(j, 1)
    if high_lvl:
        for j in ["Commander", "Captain", "Engineer"]:
            add(j, 1)

    # Trait nudges (shortened but same flavour)
    if "Brave" in t:
        for j in ["Soldier", "Guard", "Ranger", "Archer", "Captain", "Falconer"]:
            add(j, 2 if j in ("Soldier", "Guard") else 1)
    if "Hot-headed" in t:
        for j in ["Soldier", "Ranger", "Archer", "Bard"]:
            add(j, 1)
    if "Cautious" in t:
        for j in ["Scout", "Guard", "Forester", "Clerk"]:
            add(j, 1)
    if "Wise" in t:
        for j in ["Scholar", "Advisor", "Priest", "Engineer", "Druid"]:
            add(j, 2 if j in ("Scholar", "Advisor") else 1)
    if "Generous" in t:
        for j in ["Healer", "Priest", "Farmer", "Innkeeper"]:
            add(j, 2 if j == "Healer" else 1)
    if "Empathic" in t:
        for j in ["Healer", "Priest", "Herbalist"]:
            add(j, 2 if j == "Healer" else 1)
    if "Diligent" in t:
        for j in ["Farmer", "Blacksmith", "Mason", "Carpenter", "Weaver", "Tanner",
                  "Potter", "Glassblower", "Baker", "Butcher"]:
            add(j, 2 if j in ("Farmer", "Blacksmith", "Mason", "Carpenter") else 1)
    if "Greedy" in t:
        for j in ["Merchant", "Trader", "Jeweler", "Innkeeper"]:
            add(j, 3 if j in ("Merchant", "Trader") else 1)
    if "Loyal" in t:
        for j in ["Guard", "Priest", "Clerk"]:
            add(j, 1)
    if "Deceitful" in t:
        for j in ["Spy", "Merchant", "Trader"]:
            add(j, 3 if j == "Spy" else 1)
    if "Ambitious" in t:
        for j in ["Commander", "Noble", "Merchant", "Trader"]:
            add(j, 1)

    if "Curious" in t or "Patient" in t:
        for j in ["Herbalist", "Druid", "Forester"]:
            add(j, 1)

    # Pick weighted
    job = pick_weighted(weights)
    p["job"] = job
    return job

def hold_election(characters: list[dict], current_day: int | None = None):
    """
    Yearly election:
    - every living villager votes, adults are candidates (prefer males).
    - respects KING_MAX_TERMS (lifetime).
    - updates King job, reassigns dethroned King, increments kingTerms.
    Returns (winner, message) or (None, None).
    """
    alive = [r for r in characters if r.get("alive", True)]
    if not alive:
        return None, None

    prev_king = next((r for r in alive if r.get("job") == "King"), None)

    # Prefer adult males; fallback to any adult
    candidates = [r for r in alive if r.get("age", 0) >= 18 and r.get("gender") == "Male"]
    if not candidates:
        candidates = [r for r in alive if r.get("age", 0) >= 18]
    if not candidates:
        return None, None

    # TERM LIMIT
    under_limit = [c for c in candidates if (c.get("kingTerms", 0) or 0) < KING_MAX_TERMS]
    term_limited_only = len(under_limit) == 0
    if not term_limited_only:
        candidates = under_limit

    # Precompute base scores
    base_score = {c["id"]: leadership_score(c, prev_king) for c in candidates}

    from collections import defaultdict
    votes = defaultdict(int)
    voters = [v for v in alive if v.get("age", 0) >= 16]

    for v in voters:
        best = None
        best_score = -1e18
        for c in candidates:
            s = base_score[c["id"]] + voter_adjustment(v, c)
            if s > best_score:
                best_score = s
                best = c
        if best is not None:
            votes[best["id"]] += 1

    if not votes:
        return None, None

    top_votes = max(votes.values())
    tied = [c for c in candidates if votes.get(c["id"], 0) == top_votes]

    def tie_break(pool: list[dict]) -> dict:
        if len(pool) <= 1:
            return pool[0]

        def filter_best(pool, fn):
            best_val = max(fn(c) for c in pool)
            return [c for c in pool if fn(c) == best_val]

        # 1) highest leadership
        pool = filter_best(pool, lambda c: base_score[c["id"]])
        if len(pool) == 1:
            return pool[0]

        # 2) highest REP
        pool = filter_best(pool, lambda c: c.get("rep", 0))
        if len(pool) == 1:
            return pool[0]

        # 3) highest INT
        pool = filter_best(pool, lambda c: c.get("int", 0))
        if len(pool) == 1:
            return pool[0]

        # 4) highest LEVEL
        pool = filter_best(pool, lambda c: c.get("level", 1))
        if len(pool) == 1:
            return pool[0]

        # 5) age closeness to 35 (then older)
        def age_score(c):
            age = c.get("age", 0)
            return -abs(age - 35) + age / 1000.0

        pool = filter_best(pool, age_score)
        if len(pool) == 1:
            return pool[0]

        # 6) final coin toss
        return random.choice(pool)

    winner = tie_break(tied)
    if not winner:
        return None, None

    win_votes = top_votes

    if term_limited_only:
        msg = (
            f"election: all candidates reached the {KING_MAX_TERMS}-term limit. "
            f"Emergency vote, {winner['name']} chosen with {win_votes} votes."
        )
    elif prev_king and prev_king is not winner:
        msg = (
            f"election: {winner['name']} is the new King with {win_votes} votes. "
            f"Former King {prev_king['name']} steps down."
        )
    elif not prev_king:
        msg = f"election: {winner['name']} is elected King with {win_votes} votes."
    else:
        msg = f"election: {winner['name']} remains King with {win_votes} votes."

    # Apply roles
    if prev_king and prev_king is not winner:
        if prev_king.get("job") == "King":
            prev_king["job"] = reassign_job_by_traits(prev_king)

    winner["job"] = "King"
    winner["kingTerms"] = int(winner.get("kingTerms", 0) or 0) + 1

    # Keep a hint on the winner as well
    winner["last_action"] = msg

    sync_queen_to_king_spouse(characters, current_day=current_day)

    return winner, msg

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
    Keep it simple and stable: assign a non-royal job.
    """
    # If already not queen, do nothing
    if q.get("job") != "Queen":
        return

    # Reassign to non-royal job (trait-weighted would be nicer, but keep minimal)
    # If you want trait-weighted, we can reuse your reassign_job_by_traits with a pool.
    q["job"] = pick(JOBS_NO_ROYAL)


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
        # No king -> no queen
        return

    spouse_id = int(king.get("spouseId", 0) or 0)
    if spouse_id == 0:
        # King has no spouse -> no queen
        return

    spouse = _get_by_id(characters, spouse_id)
    if spouse is None or not spouse.get("alive", True):
        # Invalid spouse link -> no queen
        return

    # 3) Assign spouse as Queen
    spouse["job"] = "Queen"

    # Optional: add small log (won't overwrite important logs)
    if current_day is not None:
        _append_last_action(spouse, f"became Queen (spouse of King {king.get('name','')})")

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
    Supports:
      - dict  → used directly
      - str   → try json.loads, else {}
      - None  → {}
    Stored format: { other_id_str: score_int }.
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
    Adjust relationship score between v -> other by delta, clamped [-100, 100].
    """
    oid = other.get("id")
    if oid is None:
        return
    cur = get_relationship_score(v, oid)
    set_relationship_score(v, oid, clamp(cur + delta, -100, 120))


def relationship_label(v: dict, other: dict) -> str | None:
    """
    Map numeric score to labels:
      friend, bestfriend, love (only Male–Female), rival, enemy.
    """
    oid = other.get("id")
    if oid is None:
        return None

    score = get_relationship_score(v, oid)
    g1 = v.get("gender")
    g2 = other.get("gender")

    # Love only for Male–Female pairs (your rule)
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
            _append_last_action(v, "widowed")
            continue
        # must be mutual; otherwise clear
        if int(spouse.get("spouseId", 0) or 0) != v.get("id"):
            v["spouseId"] = 0

    # --------- Breakup phase (very small) ----------
    # Evaluate only once per couple (use id ordering)
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
        if score < 70: p += 0.00003   # +0.003%
        if score < 50: p += 0.00006   # +0.006%
        if score < 30: p += 0.00012   # +0.012%
        if score < 10: p += 0.00025   # +0.025%
        if score < 0:  p += 0.00040   # +0.04%

        # Cap: still small even at worst
        p = min(0.001, max(0.0, p))   # max 0.1% per day

        if random.random() < p:
            _clear_spouses(a, b, "broke up")
            continue

    # --------- Marriage / Proposal phase ----------
    # Strategy:
    # - For each single villager, find the best eligible single "love" target.
    # - If their label is love AND relationship >= 100, chance to marry today.
    singles = [v for v in characters if v.get("alive", True) and int(v.get("spouseId", 0) or 0) == 0]

    # Sort to reduce chaotic outcomes: older first, then higher rep
    singles.sort(key=lambda x: (-(x.get("age", 0) or 0), -(x.get("rep", 0) or 0)))

    for a in singles:
        if int(a.get("spouseId", 0) or 0) != 0:
            continue  # might have been married earlier in loop

        # must be eligible age bracket even to search
        a_age = int(a.get("age", 0) or 0)
        if not (18 <= a_age <= 60):
            continue

        # Find best candidate b among singles
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

            # You asked: love relationship 100 triggers spouse chance
            if s < 100:
                continue

            # pick the strongest mutual love
            if s > best_score:
                best_score = s
                best_b = b

        if best_b is None:
            continue

        # Chance to become spouses (proposal/marriage)
        # Small but real; slightly higher if their love exceeds 100 (if you ever allow >100)
        p_marry = 0.04  # 4% per day when mutual love is 100+
        p_marry = min(0.10, p_marry + max(0, best_score - 100) * 0.002)

        if random.random() < p_marry:
            _set_spouses(a, best_b, current_day)
            _append_last_action(a, f"married {best_b['name']}")
            _append_last_action(best_b, f"married {a['name']}")

    birth_daily_phase(characters, current_day=current_day)
    
    sync_queen_to_king_spouse(characters, current_day=current_day)

# ---------------------------------------------------------------------------
#  Corruption + assassination
# ---------------------------------------------------------------------------

def maybe_corrupt_from_bank(v: dict, bank: dict | None) -> int:
    """
    Small daily chance for King / Queen / Noble to skim coins
    from the village bank into their own pocket.

    Returns:
        int: amount stolen (0 if no corruption happened).
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

    base_chance = 0.03  # 3% per day

    # Trait influence
    if "Greedy" in traits:
        base_chance += 0.04
    if "Ambitious" in traits:
        base_chance += 0.02
    if "Loyal" in traits:
        base_chance -= 0.02
    if "Generous" in traits:
        base_chance -= 0.01

    # Building influence – treasury makes bigger pot, tax office = audits
    if get_building_level(bank, "treasury") > 0:
        base_chance += 0.01
    if get_building_level(bank, "tax_office") > 0:
        base_chance -= 0.01

    # Clamp between 0% and 15%
    base_chance = max(0.0, min(0.15, base_chance))

    # Roll – if fail, no corruption today
    if random.random() >= base_chance:
        return 0

    # --- amount stolen ---
    # Between 2%–8% of balance, at least 5 coins, but never more than balance
    fraction = random.uniform(0.02, 0.08)
    stolen = max(5, int(balance * fraction))
    stolen = min(stolen, balance)

    if stolen <= 0:
        return 0

    bank["balance"] = balance - stolen
    v["coins"] = v.get("coins", 0) + stolen

    # Reputation penalty for shady behavior
    rep_penalty = rand_int(3, 10)
    v["rep"] = clamp(v.get("rep", 0) - rep_penalty, -100, 100)

    # Log into last_action (append, similar style to starvation)
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
    Returns True if an assassination happened.
    """
    king = _get_current_king(characters)
    if king is None or not king.get("alive", True):
        return False

    # Collect enemy candidates
    enemies = []
    king_id = king.get("id")
    king_spouse = int(king.get("spouseId", 0) or 0)

    for o in characters:
        if not o.get("alive", True):
            continue
        if o.get("id") == king_id:
            continue
        # avoid assassinating spouse (keeps royal system stable)
        if o.get("id") == king_spouse:
            continue

        # "enemy" if mutual <= -60 OR label says enemy either way
        s1 = get_relationship_score(king, o["id"])
        s2 = get_relationship_score(o, king_id)
        if min(s1, s2) <= -60 or relationship_label(king, o) == "enemy" or relationship_label(o, king) == "enemy":
            enemies.append(o)

    if not enemies:
        return False

    # --- small chance ---
    # Base 0.8% per day if any enemy exists
    p = 0.008

    # Trait tuning (optional but fun)
    kt = get_traits_set(king)
    if "Deceitful" in kt:  p += 0.008
    if "Ambitious" in kt:  p += 0.004
    if "Hot-headed" in kt: p += 0.003
    if "Brave" in kt:      p += 0.002
    if "Loyal" in kt:      p -= 0.003
    if "Generous" in kt:   p -= 0.003
    if "Empathic" in kt:   p -= 0.003
    if "Wise" in kt:       p -= 0.001

    # Building influence (guards/force projection)
    if bank is not None:
        lvl_barracks = get_building_level(bank, "barracks")
        lvl_walls = get_building_level(bank, "walls")
        p += 0.002 * lvl_barracks
        p += 0.001 * lvl_walls

    p = max(0.0, min(0.05, p))  # cap at 5%

    if random.random() >= p:
        return False

    # Pick a target (bias toward worst relationship)
    enemies.sort(key=lambda o: (min(get_relationship_score(king, o["id"]),
                                   get_relationship_score(o, king_id))))
    target = enemies[0]

    _mark_dead(characters, target, "killed by assassinate", current_day=current_day)
    _append_last_action(king, f"assassinated {target.get('name','an enemy')}")

    # If target was Queen (shouldn't happen because spouse excluded), sync anyway
    sync_queen_to_king_spouse(characters, current_day=current_day)
    return True

def _safe_int(x, default=0) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return default


def settle_inheritance_phase(characters: list[dict], bank: dict | None, current_day: int):
    """
    Settle inheritance for villagers who died TODAY (death_day == current_day),
    and haven't been settled before.
    """
    id_map = {c.get("id"): c for c in characters}

    for deceased in characters:
        # only dead
        if deceased.get("alive", True):
            continue

        dd = _safe_int(deceased.get("death_day", 0), 0)
        if dd != int(current_day):
            continue

        # prevent double payout
        if deceased.get("estate_settled", False):
            continue

        estate = _safe_int(deceased.get("coins", 0), 0)
        if estate <= 0:
            deceased["estate_settled"] = True
            continue

        heirs: list[dict] = []

        # 1) children first
        child_ids = _ensure_list_field(deceased, "childrenIds")
        for cid in child_ids:
            cid = _safe_int(cid, 0)
            if cid <= 0:
                continue
            child = id_map.get(cid)
            if child and child.get("alive", True):
                heirs.append(child)

        # 2) if no children -> spouse
        if not heirs:
            sid = _safe_int(deceased.get("spouseId_at_death", 0), 0) or _safe_int(deceased.get("spouseId", 0), 0)
            if sid > 0:
                spouse = id_map.get(sid)
                if spouse and spouse.get("alive", True):
                    heirs.append(spouse)

        # 3) if no spouse -> same family name adults
        if not heirs:
            fam = (deceased.get("family") or "").strip()
            if fam:
                fam_members = [
                    c for c in characters
                    if c.get("alive", True)
                    and (c.get("family") or "").strip() == fam
                    and c.get("id") != deceased.get("id")
                    and _safe_int(c.get("age", 0), 0) >= 17
                ]
                # optional: prefer richer/older/rep? for now just take all
                heirs = fam_members

        # 4) if nobody -> treasury/bank
        if not heirs:
            if bank is not None:
                bank["balance"] = _safe_int(bank.get("balance", 0), 0) + estate
            deceased["coins"] = 0
            deceased["estate_settled"] = True
            _append_last_action(deceased, f"estate: {estate} coins transferred to treasury")
            continue

        # distribute equally with remainder
        n = len(heirs)
        base = estate // n
        rem = estate % n

        for i, h in enumerate(heirs):
            share = base + (1 if i < rem else 0)
            if share <= 0:
                continue
            h["coins"] = _safe_int(h.get("coins", 0), 0) + share
            _append_last_action(h, f"inherited {share} coins from {deceased.get('name','someone')}")

        deceased["coins"] = 0
        deceased["estate_settled"] = True

        heir_names = ", ".join([h.get("name", "?") for h in heirs[:5]])
        if len(heirs) > 5:
            heir_names += f", +{len(heirs)-5} others"
        _append_last_action(deceased, f"estate: {estate} coins inherited by {heir_names}")


# ---------------------------------------------------------------------------
#  Birth + Childhood
# ---------------------------------------------------------------------------

def _traits_list(v: dict) -> list[str]:
    s = (v.get("traits", "") or "").strip()
    return [t.strip() for t in s.split(",") if t.strip()]

def _ensure_list_field(v: dict, key: str) -> list:
    x = v.get(key)
    if isinstance(x, list):
        return x
    if isinstance(x, str) and x.strip():
        try:
            data = json.loads(x)
            if isinstance(data, list):
                v[key] = data
                return data
        except Exception:
            pass
    v[key] = []
    return v[key]

def _new_id(characters: list[dict]) -> int:
    mx = 0
    for c in characters:
        try:
            mx = max(mx, int(c.get("id", 0) or 0))
        except Exception:
            pass
    return mx + 1

def _unique_child_name(taken: set[str]) -> str:
    # Uses your existing prefix/suffix pools
    for _ in range(120):
        name = f"{pick(NAME_PREFIX)}{pick(NAME_SUFFIX)}"
        if name not in taken:
            return name
    # fallback
    return f"Child{random.randint(1000, 9999)}"

def _inherit_one_trait(parent_traits: list[str]) -> str | None:
    if not parent_traits:
        return None
    return random.choice(parent_traits)

def _make_child_traits(mom: dict, dad: dict) -> str:
    mom_t = _traits_list(mom)
    dad_t = _traits_list(dad)

    inherited = []
    t1 = _inherit_one_trait(mom_t)
    t2 = _inherit_one_trait(dad_t)

    if t1: inherited.append(t1)
    if t2 and t2 not in inherited: inherited.append(t2)

    # small mutation chance: one extra random trait (keeps variety)
    if random.random() < 0.08 and TRAITS:
        extra = random.choice(TRAITS)
        if extra not in inherited:
            if len(inherited) >= 2:
                inherited[random.randrange(2)] = extra
            else:
                inherited.append(extra)

    return ", ".join(inherited[:2])

def _inherit_stat_small(mom_val: int, dad_val: int, base_lo: int, base_hi: int, inherit_ratio: float) -> int:
    try:
        m = int(mom_val or 0)
        d = int(dad_val or 0)
    except Exception:
        m, d = 0, 0
    avg = (m + d) / 2.0
    base = rand_int(base_lo, base_hi)
    inherited = int(avg * inherit_ratio)
    noise = rand_int(-1, 2)
    return max(1, base + inherited + noise)

def _count_couple_children(characters: list[dict], mom_id: int, dad_id: int) -> int:
    n = 0
    for c in characters:
        try:
            if int(c.get("motherId", 0) or 0) == mom_id and int(c.get("fatherId", 0) or 0) == dad_id:
                n += 1
        except Exception:
            pass
    return n

def _count_family_children(characters: list[dict], father_family: str) -> int:
    if not father_family:
        return 0
    n = 0
    for c in characters:
        if c.get("family") == father_family:
            # count only kids that are actually children of someone (born)
            if int(c.get("fatherId", 0) or 0) > 0 or int(c.get("motherId", 0) or 0) > 0:
                n += 1
    return n

def _birth_probability(characters: list[dict], mom: dict, dad: dict, current_day: int) -> float:
    # fertility window (simple, stable)
    mom_age = int(mom.get("age", 0) or 0)
    dad_age = int(dad.get("age", 0) or 0)

    if mom_age < 18 or mom_age > 42:
        return 0.0
    if dad_age < 18 or dad_age > 65:
        return 0.0

    # cooldown check
    mom_last = int(mom.get("last_birth_day", 0) or 0)
    dad_last = int(dad.get("last_birth_day", 0) or 0)
    last = max(mom_last, dad_last)
    if last > 0 and (current_day - last) < BIRTH_COOLDOWN_DAYS:
        return 0.0

    # base
    p = BIRTH_BASE_P

    # love strength helps a bit
    s1 = get_relationship_score(mom, dad["id"])
    s2 = get_relationship_score(dad, mom["id"])
    love = min(s1, s2)
    if love >= 100:
        p += 0.002
    elif love >= 80:
        p += 0.001
    else:
        p -= 0.001

    # decay: couple children
    couple_kids = _count_couple_children(characters, mom["id"], dad["id"])
    p *= (COUPLE_DECAY ** couple_kids)

    # decay: father-family children
    fam_kids = _count_family_children(characters, dad.get("family", ""))
    p *= (FAMILY_DECAY ** max(0, fam_kids - 1))

    # clamp
    return max(0.0, min(0.03, p))


def _spawn_child(characters: list[dict], mom: dict, dad: dict, current_day: int) -> dict:
    taken_names = {c.get("name", "") for c in characters}
    child_id = _new_id(characters)

    gender = random.choice(["Male", "Female"])
    family = dad.get("family", "") or ""

    given = _unique_child_name(taken_names)
    full_name = f"{given} {family}".strip()

    child = {
        "id": child_id,
        "name": full_name,
        "family": family,
        "gender": gender,

        # child state
        "age": 0,
        "job": "Child",

        # inherited stats (small)
        "atk": _inherit_stat_small(mom.get("atk", 0), dad.get("atk", 0), 1, 4, 0.12),
        "def": _inherit_stat_small(mom.get("def", 0), dad.get("def", 0), 1, 4, 0.12),
        "int": _inherit_stat_small(mom.get("int", 0), dad.get("int", 0), 2, 6, 0.14),

        "hp": rand_int(35, 55),
        "hunger": 0,  # IMPORTANT: child hunger stays 0
        "coins": 0,
        "rep": 0,
        "level": 1,
        "exp": 0,

        "traits": _make_child_traits(mom, dad),

        "alive": True,
        "origin": "born",
        "owner": "",

        "motherId": int(mom.get("id", 0) or 0),
        "fatherId": int(dad.get("id", 0) or 0),
        "childrenIds": [],
        "relationships": {},

        "spouseId": 0,
        "spouseSinceDay": 0,

        "born_day": int(current_day),
        "last_birth_day": 0,

        "last_action": f"born to {mom.get('name','?')} and {dad.get('name','?')}",
        "action_log": "",
    }

    # link to parents
    mom_kids = _ensure_list_field(mom, "childrenIds")
    dad_kids = _ensure_list_field(dad, "childrenIds")
    mom_kids.append(child_id)
    dad_kids.append(child_id)

    mom["last_birth_day"] = int(current_day)
    dad["last_birth_day"] = int(current_day)

    _append_last_action(mom, f"gave birth to {child['name']}")
    _append_last_action(dad, f"welcomed child {child['name']}")

    return child


def birth_daily_phase(characters: list[dict], current_day: int):
    """
    Run after spouse logic each day.
    For each married couple, small chance to have a child.
    Chance decays with number of children (couple + father-family).
    """
    # handle each couple once
    for a in characters:
        if not a.get("alive", True):
            continue
        sid = int(a.get("spouseId", 0) or 0)
        if sid == 0:
            continue

        b = _get_by_id(characters, sid)
        if b is None or not b.get("alive", True):
            continue

        # once per couple
        if int(a.get("id", 0) or 0) > int(b.get("id", 0) or 0):
            continue

        if not _is_mutual_spouse(a, b):
            continue

        # assign roles by gender (your rule: MF only)
        if {a.get("gender"), b.get("gender")} != {"Male", "Female"}:
            continue

        dad = a if a.get("gender") == "Male" else b
        mom = b if dad is a else a

        # must be adults
        if int(mom.get("age", 0) or 0) < 18 or int(dad.get("age", 0) or 0) < 18:
            continue

        p = _birth_probability(characters, mom, dad, current_day)
        if p <= 0:
            continue

        if random.random() < p:
            child = _spawn_child(characters, mom, dad, current_day)
            characters.append(child)

def child_daily_phase(characters: list[dict], current_day: int):
    """
    Child-only actions (0–16):
      train, rest, study, hangout, socialize
    Hunger always 0. No adult work/earn.
    """
    kids = [c for c in characters if c.get("alive", True) and int(c.get("age", 0) or 0) <= CHILD_MAX_AGE]
    if not kids:
        return

    # quick id index for socializing
    id_map = {c.get("id"): c for c in characters}

    for c in kids:
        # enforce child state
        c["job"] = "Child"
        c["hunger"] = 0

        t = get_traits_set(c)
        weights = {
            "train": 1.0,
            "rest": 1.2,
            "study": 1.0,
            "hangout": 1.0,
            "socialize": 1.0,
        }

        if "Brave" in t: weights["train"] += 0.7
        if "Hot-headed" in t: weights["train"] += 0.4
        if "Wise" in t: weights["study"] += 0.9
        if "Patient" in t: weights["study"] += 0.3
        if "Empathic" in t: weights["socialize"] += 0.6
        if "Loyal" in t: weights["hangout"] += 0.5
        if "Lazy" in t: weights["rest"] += 0.8

        act = pick_weighted(weights)

        if act == "train":
            if random.random() < 0.55:
                c["atk"] = clamp(int(c.get("atk", 1) or 1) + 1, 1, 9999)
            if random.random() < 0.45:
                c["def"] = clamp(int(c.get("def", 1) or 1) + 1, 1, 9999)
            _append_last_action(c, "child trained")

        elif act == "study":
            if random.random() < 0.60:
                c["int"] = clamp(int(c.get("int", 1) or 1) + 1, 1, 9999)
            _append_last_action(c, "child studied")

        elif act == "rest":
            # heal a bit
            c["hp"] = int(c.get("hp", 0) or 0) + rand_int(1, 4)
            _append_last_action(c, "child rested")

        elif act == "hangout":
            c["rep"] = clamp(int(c.get("rep", 0) or 0) + rand_int(0, 1), -100, 100)
            _append_last_action(c, "child hung out")

        else:  # socialize
            # pick a random peer (prefer children)
            peers = [p for p in kids if p.get("id") != c.get("id")]
            if peers:
                other = random.choice(peers)
                adjust_relationship(c, other, rand_int(1, 3))
                adjust_relationship(other, c, rand_int(1, 3))
                _append_last_action(c, f"socialized with {other.get('name','a peer')}")
            else:
                _append_last_action(c, "child socialized")

def _assign_job_for_young_adult(p: dict) -> str:
    """
    When a child becomes adult (age >= 17):
    pick a job based on stats + traits (non-royal).
    """
    pool = list(JOBS_NO_ROYAL) if JOBS_NO_ROYAL else list(JOBS_POOL)
    weights = {j: 1.0 for j in pool}

    def add(job: str, w: float):
        if job in weights:
            weights[job] += w

    t = get_traits_set(p)
    power = int(p.get("atk", 0) or 0) + int(p.get("def", 0) or 0)
    intel = int(p.get("int", 0) or 0)

    # stat nudges
    if intel >= 25:
        for j in ["Scholar", "Scribe", "Advisor", "Engineer", "Alchemist", "Priest", "Healer"]:
            add(j, 2.0)
    if power >= 25:
        for j in ["Soldier", "Guard", "Ranger", "Archer", "Scout", "Hunter"]:
            add(j, 2.0)

    # trait nudges
    if "Brave" in t:
        for j in ["Soldier", "Guard", "Ranger", "Archer", "Hunter"]:
            add(j, 1.5)
    if "Wise" in t:
        for j in ["Scholar", "Scribe", "Advisor", "Engineer", "Druid"]:
            add(j, 1.8)
    if "Diligent" in t:
        for j in ["Farmer", "Blacksmith", "Mason", "Carpenter", "Weaver", "Tanner", "Baker", "Butcher"]:
            add(j, 1.5)
    if "Greedy" in t:
        for j in ["Merchant", "Trader", "Innkeeper", "Jeweler"]:
            add(j, 2.0)
    if "Empathic" in t or "Generous" in t:
        for j in ["Healer", "Priest", "Herbalist"]:
            add(j, 1.8)
    if "Deceitful" in t:
        add("Spy", 3.0)

    job = pick_weighted(weights)
    p["job"] = job
    return job


def coming_of_age_phase(characters: list[dict], current_day: int | None = None):
    """
    If age >= 17 and still Child -> assign an adult job.
    """
    for c in characters:
        if not c.get("alive", True):
            continue
        age = int(c.get("age", 0) or 0)
        if age >= (CHILD_MAX_AGE + 1) and c.get("job") == "Child":
            new_job = _assign_job_for_young_adult(c)
            msg = f"came of age and became {new_job}"
            if current_day is not None:
                _append_last_action(c, msg)
            else:
                c["last_action"] = msg