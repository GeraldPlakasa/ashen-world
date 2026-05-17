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
from src.utils.world_utils import (
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

        # Phase 4: settle magical artifacts before coins.
        # Soulbound -> destroyed, else passes to oldest child/spouse/sibling,
        # else liquidated to treasury.
        try:
            from src.services.artifact_service import settle_artifact_inheritance
            settle_artifact_inheritance(deceased, characters, bank, int(current_day))
        except Exception:
            pass  # never break the sim loop

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


def cascade_blue_blood_from_king(king: Villager, characters: list[Villager]) -> int:
    """
    Walk the new king's MALE descendants (sons, grandsons through sons, ...) and
    grant blue_blood + the Royal Blood achievement. Daughters and their
    descendants are skipped — royal blood passes strictly along the male line
    (Salic-style succession).

    Note: the king himself is not flagged — only the line below him.
    Returns the number of villagers newly granted blue_blood.
    """
    if not king:
        return 0

    try:
        from src.services.achievement_service import trigger_royal_blood
    except Exception:
        return 0

    id_map = {int(c.get("id", 0) or 0): c for c in characters}
    granted = 0
    seen: set[int] = set()
    queue: list[int] = []

    for cid in _ensure_list_field(king, "childrenIds"):
        try:
            queue.append(int(cid or 0))
        except Exception:
            continue

    while queue:
        cid = queue.pop()
        if cid <= 0 or cid in seen:
            continue
        seen.add(cid)

        person = id_map.get(cid)
        if person is None:
            continue

        # Female descendants don't inherit the line and don't pass it on; skip
        # both the flagging and the recursion through their children.
        if (person.get("gender") or "") != "Male":
            continue

        if int(person.get("blue_blood", 0) or 0) != 1:
            try:
                trigger_royal_blood(person)
                granted += 1
            except Exception:
                person["blue_blood"] = 1

        # Only traverse further down through male descendants.
        for sub in _ensure_list_field(person, "childrenIds"):
            try:
                queue.append(int(sub or 0))
            except Exception:
                continue

    return granted


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
    from src.services.skill_service import roll_birth_skills_with_inheritance, skills_to_string
    
    taken_names = {c.get("name", "") for c in characters}
    child_id = _new_id(characters)

    gender = random.choice(["Male", "Female"])
    family = dad.get("family", "") or ""

    given = _unique_child_name(taken_names)
    full_name = f"{given} {family}".strip()

    # Roll for skills at birth (considers parent skills for inheritance)
    birth_skills = roll_birth_skills_with_inheritance(mom, dad)
    skills_str = skills_to_string(birth_skills)

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
        "skills": skills_str,  # Rare birth skills

        "alive": True,
        "origin": "born",
        "owner": "",

        "motherId": int(mom.get("id", 0) or 0),
        "fatherId": int(dad.get("id", 0) or 0),
        "childrenIds": [],
        "relationships": {},

        "spouseId": 0,
        "spouseSinceDay": 0,
        "spouseId_at_death": 0,

        "born_day": int(current_day),
        "last_birth_day": 0,
        "death_day": 0,

        "kingTerms": 0,
        "huntWins": 0,
        "huntWinsYear": 0,
        "questWins": 0,

        "gen": max(int(mom.get("gen", 1) or 1), int(dad.get("gen", 1) or 1)) + 1,
        "immigrantGen": 0,

        "achievements": "[]",
        "kingsVotedFor": "[]",

        "disease": "",
        "disease_day": 0,
        "immunities": "[]",

        "last_action": f"born to {mom.get('name','?')} and {dad.get('name','?')}",
        "action_log": "",
    }
    
    # Skills don't add stats at birth - they provide bonuses during actions

    mom_kids = _ensure_list_field(mom, "childrenIds")
    dad_kids = _ensure_list_field(dad, "childrenIds")
    mom_kids.append(child_id)
    dad_kids.append(child_id)

    mom["last_birth_day"] = int(current_day)
    dad["last_birth_day"] = int(current_day)

    # Blue blood (Salic-style male-line succession): only male children of a
    # royal parent inherit. Daughters do not receive the flag, and their own
    # children later won't either — which keeps royal-blood lineage strictly
    # along the male line.
    parent_is_royal = (
        int(mom.get("blue_blood", 0) or 0) == 1
        or int(dad.get("blue_blood", 0) or 0) == 1
        or mom.get("job") == "King"
        or dad.get("job") == "King"
    )
    if parent_is_royal and child.get("gender") == "Male":
        try:
            from src.services.achievement_service import trigger_royal_blood
            trigger_royal_blood(child)
        except Exception:
            child["blue_blood"] = 1

    _append_last_action(mom, f"gave birth to {child['name']}")
    _append_last_action(dad, f"welcomed child {child['name']}")

    return child


def _food_pressure_birth_multiplier(characters: list[Villager], bank) -> float:
    """Reduce birth rate when food is scarce so the population doesn't grow
    faster than the village can feed it. Returns a multiplier in [0.1, 1.0].

    Anchored to "days of food supply remaining" at the current adult demand:
      ≥ 7 days  → 1.00 (no penalty)
      4–6 days  → 0.60
      2–3 days  → 0.30
      < 2 days  → 0.10 (only the strongest couples bear children)
    """
    if not bank:
        return 1.0
    stock = bank.get("resources") or {}
    food = int(stock.get("food", 0) or 0)
    adults = sum(
        1 for v in characters
        if v.get("alive") and int(v.get("age", 0) or 0) > CHILD_MAX_AGE
    )
    if adults <= 0:
        return 1.0
    days_supply = food / max(1, adults)
    if days_supply >= 7:
        return 1.0
    if days_supply >= 4:
        return 0.6
    if days_supply >= 2:
        return 0.3
    return 0.1


def birth_daily_phase(characters: list[Villager], current_day: int, bank=None) -> int:
    """
    Run after spouse logic each day.
    For each married couple, small chance to have a child. Birth rate is
    scaled down when the food stockpile is low — a hungry village doesn't grow.

    Returns:
        Number of births that occurred.
    """
    food_mult = _food_pressure_birth_multiplier(characters, bank)
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
        p *= food_mult

        if random.random() < p:
            child = _spawn_child(characters, mom, dad, current_day)
            characters.append(child)
            births_count += 1
            try:
                from src.services.chronicle_service import record_birth
                record_birth(child, mom, dad, day=int(current_day or 1))
            except Exception:
                pass

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
            c["rep"] = int(c.get("rep", 0) or 0) + rand_int(0, 1)
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

def _assign_job_for_young_adult(p: Villager, characters: list[Villager] | None = None) -> str:
    """
    When a child becomes adult (age >= 17):
    pick a job based on skills, parent's trade, stats + traits.

    Priority: skill affinity → parent's profession (40% chance, medieval-style
    apprenticeship) → stats/traits-weighted random. Job inheritance keeps the
    village's producer-job ratio from drifting toward uniform-random over
    generations, which is what causes food spirals after population growth.
    """
    from src.services.skill_service import parse_skills, get_job_from_skills
    from config import JOB_RESOURCE_YIELD

    pool = list(JOBS_NO_ROYAL) if JOBS_NO_ROYAL else list(JOBS_POOL)

    # Check if villager has skills that suggest a job
    skills = parse_skills(p.get("skills", ""))
    if skills:
        skill_job = get_job_from_skills(skills, pool)
        if skill_job:
            # 75% chance to follow skill affinity
            if random.random() < 0.75:
                p["job"] = skill_job
                return skill_job

    # Profession inheritance: prefer parent's trade. Father first (traditional
    # primary breadwinner in this kind of sim), fall back to mother. Producer
    # parents transfer more readily (skill-passed) than non-producers.
    if characters is not None:
        parent_jobs: list[str] = []
        for parent_key in ("fatherId", "motherId"):
            pid = int(p.get(parent_key, 0) or 0)
            if pid > 0:
                parent = next((c for c in characters if int(c.get("id", 0) or 0) == pid), None)
                if parent and parent.get("job"):
                    pj = parent["job"]
                    if pj in pool:
                        parent_jobs.append(pj)
        if parent_jobs:
            primary = parent_jobs[0]
            inherit_chance = 0.55 if primary in JOB_RESOURCE_YIELD else 0.35
            if random.random() < inherit_chance:
                p["job"] = primary
                return primary
    
    # Standard job assignment based on stats/traits. Producer jobs get a
    # gentle baseline boost so the village stays food-secure as generations
    # turn over — without it, a 100-villager village drifts from 45% producers
    # toward ~25% (the uniform-random equilibrium).
    weights = {j: 1.0 for j in pool}
    for producer_job in JOB_RESOURCE_YIELD.keys():
        if producer_job in weights:
            weights[producer_job] += 1.5

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
        for j in ["Soldier", "Guard", "Scout", "Hunter"]:
            add(j, 2.0)

    if "Brave" in t:
        for j in ["Soldier", "Guard", "Scout", "Hunter"]:
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
        for j in ["Healer", "Priest", "Herbalist", "Cleric"]:
            add(j, 1.8)
    if "Deceitful" in t:
        add("Spy", 3.0)
    if "Curious" in t:
        for j in ["Wizard", "Sorcerer", "Scholar", "Alchemist"]:
            add(j, 1.8)
    # High INT makes magic jobs more likely
    if intel >= 35:
        for j in ["Wizard", "Sorcerer", "Cleric", "Druid"]:
            add(j, 2.0)

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
            new_job = _assign_job_for_young_adult(c, characters)
            # Assign initial MP based on new job
            from config import MAGIC_JOBS, MINOR_MAGIC_JOBS
            if new_job in MAGIC_JOBS:
                c["mp"] = rand_int(60, 120)
            elif new_job in MINOR_MAGIC_JOBS:
                c["mp"] = rand_int(15, 40)
            else:
                c["mp"] = rand_int(0, 10)
            msg = f"came of age and became {new_job}"
            if current_day is not None:
                _append_last_action(c, msg)
            else:
                c["last_action"] = msg
