from __future__ import annotations

import random

from config import (
    JOBS_POOL,
    KING_MAX_TERMS,
    DYNASTY_BONUS,
)
from world_utils import (
    pick_weighted,
)
from src.services.relationship_service import (
    sync_queen_to_king_spouse,
    MILITARY_JOBS,
    LEARNED_JOBS,
    COMMERCE_JOBS,
    CRAFT_JOBS,
    NATURE_JOBS,
)
from src.models.villager import Villager

def get_traits_set(v: Villager) -> set[str]:
    """Parse v['traits'] into a set of clean trait strings."""
    traits_str = v.get("traits", "") or ""
    return {t.strip() for t in traits_str.split(",") if t.strip()}

def leadership_score(c: Villager, prev_king: Villager | None = None) -> float:
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

    # Age shaping (prefer ~22-55)
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


def voter_adjustment(v: Villager, c: Villager) -> float:
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

    # Kinship & "guild" vibes
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

    # Tiny random "likeability" noise
    a += random.random() * 0.5
    return a

def reassign_job_by_traits(p: Villager) -> str:
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

def hold_election(characters: list[Villager], current_day: int | None = None) -> tuple[Villager | None, str | None]:
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

    under_limit = [c for c in candidates if (c.get("kingTerms", 0) or 0) < KING_MAX_TERMS]
    term_limited_only = len(under_limit) == 0
    if not term_limited_only:
        candidates = under_limit

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
    
    # Calculate percentage from total alive villagers
    total_alive = len(alive)
    vote_percentage = (win_votes / total_alive * 100) if total_alive > 0 else 0

    if term_limited_only:
        msg = (
            f"election: all candidates reached the {KING_MAX_TERMS}-term limit. "
            f"Emergency vote, {winner['name']} chosen with {win_votes} votes "
            f"({vote_percentage:.0f}% of {total_alive} villagers)."
        )
    elif prev_king and prev_king is not winner:
        msg = (
            f"election: {winner['name']} is the new King with {win_votes} votes "
            f"({vote_percentage:.0f}% of {total_alive} villagers). "
            f"Former King {prev_king['name']} steps down."
        )
    elif not prev_king:
        msg = (
            f"election: {winner['name']} is elected King with {win_votes} votes "
            f"({vote_percentage:.0f}% of {total_alive} villagers)."
        )
    else:
        msg = (
            f"election: {winner['name']} remains King with {win_votes} votes "
            f"({vote_percentage:.0f}% of {total_alive} villagers)."
        )

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
