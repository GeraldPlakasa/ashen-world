from __future__ import annotations

import json
import random

from config import (
    JOBS_POOL,
    JOBS_NO_ROYAL,
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
from src.services.relationship_service import (
    adjust_relationship,
    get_relationship_score,
    _append_last_action,
    _get_by_id,
    _is_mutual_spouse,
    _safe_int,
)
from src.services.election_service import (
    get_traits_set,
)
from src.models.villager import Villager
from src.models.bank import Bank

def _ensure_list_field(v: Villager, key: str) -> list:
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


def settle_inheritance_phase(characters: list[Villager], bank: Bank | None, current_day: int) -> None:
    """
    Settle inheritance for villagers who died TODAY (death_day == current_day),
    and haven't been settled before.
    """
    id_map = {c.get("id"): c for c in characters}

    for deceased in characters:
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


def _traits_list(v: Villager) -> list[str]:
    s = (v.get("traits", "") or "").strip()
    return [t.strip() for t in s.split(",") if t.strip()]

def _new_id(characters: list[Villager]) -> int:
    mx = 0
    for c in characters:
        try:
            mx = max(mx, int(c.get("id", 0) or 0))
        except Exception:
            pass
    return mx + 1

def _unique_child_name(taken: set[str]) -> str:
    for _ in range(120):
        name = f"{pick(NAME_PREFIX)}{pick(NAME_SUFFIX)}"
        if name not in taken:
            return name
    return f"Child{random.randint(1000, 9999)}"

def _inherit_one_trait(parent_traits: list[str]) -> str | None:
    if not parent_traits:
        return None
    return random.choice(parent_traits)

def _make_child_traits(mom: Villager, dad: Villager) -> str:
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

def _count_couple_children(characters: list[Villager], mom_id: int, dad_id: int) -> int:
    n = 0
    for c in characters:
        try:
            if int(c.get("motherId", 0) or 0) == mom_id and int(c.get("fatherId", 0) or 0) == dad_id:
                n += 1
        except Exception:
            pass
    return n

def _count_family_children(characters: list[Villager], father_family: str) -> int:
    if not father_family:
        return 0
    n = 0
    for c in characters:
        if c.get("family") == father_family:
            if int(c.get("fatherId", 0) or 0) > 0 or int(c.get("motherId", 0) or 0) > 0:
                n += 1
    return n

def _birth_probability(characters: list[Villager], mom: Villager, dad: Villager, current_day: int) -> float:
    mom_age = int(mom.get("age", 0) or 0)
    dad_age = int(dad.get("age", 0) or 0)

    if mom_age < 18 or mom_age > 50:
        return 0.0
    if dad_age < 18 or dad_age > 75:
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


def _spawn_child(characters: list[Villager], mom: Villager, dad: Villager, current_day: int) -> Villager:
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

        "age": 0,
        "job": "Child",

        # inherited stats (small)
        "atk": _inherit_stat_small(mom.get("atk", 0), dad.get("atk", 0), 1, 4, 0.12),
        "def": _inherit_stat_small(mom.get("def", 0), dad.get("def", 0), 1, 4, 0.12),
        "int": _inherit_stat_small(mom.get("int", 0), dad.get("int", 0), 2, 6, 0.14),

        "hp": rand_int(35, 55),
        "hunger": 0,
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

    mom_kids = _ensure_list_field(mom, "childrenIds")
    dad_kids = _ensure_list_field(dad, "childrenIds")
    mom_kids.append(child_id)
    dad_kids.append(child_id)

    mom["last_birth_day"] = int(current_day)
    dad["last_birth_day"] = int(current_day)

    _append_last_action(mom, f"gave birth to {child['name']}")
    _append_last_action(dad, f"welcomed child {child['name']}")

    return child


def birth_daily_phase(characters: list[Villager], current_day: int) -> int:
    """
    Run after spouse logic each day.
    For each married couple, small chance to have a child.
    
    Returns:
        Number of births that occurred.
    """
    births_count = 0
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

        if {a.get("gender"), b.get("gender")} != {"Male", "Female"}:
            continue

        dad = a if a.get("gender") == "Male" else b
        mom = b if dad is a else a

        if int(mom.get("age", 0) or 0) < 18 or int(dad.get("age", 0) or 0) < 18:
            continue

        p = _birth_probability(characters, mom, dad, current_day)
        if p <= 0:
            continue

        if random.random() < p:
            child = _spawn_child(characters, mom, dad, current_day)
            characters.append(child)
            births_count += 1
    
    return births_count

def child_daily_phase(characters: list[Villager], current_day: int) -> None:
    """
    Child-only actions (0-16):
      train, rest, study, hangout, socialize
    """
    kids = [c for c in characters if c.get("alive", True) and int(c.get("age", 0) or 0) <= CHILD_MAX_AGE]
    if not kids:
        return

    id_map = {c.get("id"): c for c in characters}

    for c in kids:
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
            c["hp"] = int(c.get("hp", 0) or 0) + rand_int(1, 4)
            _append_last_action(c, "child rested")

        elif act == "hangout":
            c["rep"] = clamp(int(c.get("rep", 0) or 0) + rand_int(0, 1), -100, 100)
            _append_last_action(c, "child hung out")

        else:  # socialize
            peers = [p for p in kids if p.get("id") != c.get("id")]
            if peers:
                other = random.choice(peers)
                adjust_relationship(c, other, rand_int(1, 3))
                adjust_relationship(other, c, rand_int(1, 3))
                _append_last_action(c, f"socialized with {other.get('name','a peer')}")
            else:
                _append_last_action(c, "child socialized")

def _assign_job_for_young_adult(p: Villager) -> str:
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

    if intel >= 25:
        for j in ["Scholar", "Scribe", "Advisor", "Engineer", "Alchemist", "Priest", "Healer"]:
            add(j, 2.0)
    if power >= 25:
        for j in ["Soldier", "Guard", "Ranger", "Archer", "Scout", "Hunter"]:
            add(j, 2.0)

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


def coming_of_age_phase(characters: list[Villager], current_day: int | None = None) -> None:
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
