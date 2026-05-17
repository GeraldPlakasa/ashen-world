from __future__ import annotations

import random

from config import (
    NAME_PREFIX,
    NAME_SUFFIX,
    TRAITS,
    FAMILY_NAMES,
    JOBS_POOL,
    JOBS_NO_ROYAL,
    JOB_RESOURCE_YIELD,
    MAGIC_JOBS,
    MINOR_MAGIC_JOBS,
)
from src.utils.world_utils import (
    pick,
    rand_int,
)
from src.services.relationship_service import (
    _set_spouses,
    sync_queen_to_king_spouse,
)
from src.models.villager import Villager

_next_villager_id = 0

def next_unique_id() -> int:
    """Return a unique integer ID for villagers (auto-increment)."""
    global _next_villager_id
    _next_villager_id += 1
    return _next_villager_id


def reset_id_from_characters(characters: list[Villager]) -> None:
    """
    Optional helper so create_character doesn't touch _next_villager_id directly.
    """
    global _next_villager_id
    if characters:
        max_id = max(c.get("id", 0) for c in characters)
        if _next_villager_id < max_id:
            _next_villager_id = max_id


def unique_full_name(taken: set[str]) -> tuple[str, str]:
    """
    Generate a unique (given + family) name that is not present in `taken`.
    Returns (full_name, family_name).
    """

    def build_given():
        base = pick(NAME_PREFIX) + pick(NAME_SUFFIX)
        # ~35% chance to have a second given name
        if random.random() < 0.35:
            return base + " " + pick(NAME_PREFIX) + pick(NAME_SUFFIX)
        return base

    attempt = 0
    full = None
    family = None

    while attempt < 2000:
        given = build_given()
        family = pick(FAMILY_NAMES)
        full = f"{given} {family}"
        if full not in taken:
            break
        attempt += 1

    if full in taken:
        full = f"{full} #{rand_int(1000, 9999)}"
    taken.add(full)
    return full, family

def make_row(taken_names: set[str], jobs_pool: list[str] | None = None, forced_gender: str | None = None, forced_job: str | None = None) -> Villager:
    """
    Create a single villager row (dict).
    """
    if jobs_pool is None:
        jobs_pool = JOBS_POOL

    id_ = next_unique_id()
    age = rand_int(10, 40)
    coins = rand_int(0, 999)
    int_stat = rand_int(1, 100)
    atk = rand_int(5, 120)
    defense = rand_int(5, 120)
    hp = rand_int(60, 220)
    # Start hunger modest — villagers spawned at 0..100 were triggering the
    # hungry-→-buy_food rule on day 1 before they could even pick a job action.
    hunger = rand_int(0, 30)
    rep = rand_int(-100, 100)
    level = 1
    exp = 0
    alive = True

    gender = pick(["Male", "Female"])
    job = pick(jobs_pool)

    if forced_gender is not None:
        gender = forced_gender
    if forced_job is not None:
        job = forced_job

    if forced_job in ("King", "Queen"):
        age = max(age, 18)
    elif forced_job is not None and forced_job != "Child":
        # Any forced non-child job needs an adult age, otherwise the age check
        # below would overwrite it back to "Child".
        age = max(age, 17)

    if age <= 16 and forced_job is None:
        job = "Child"
        hunger = 0
        coins = 0

    # MP based on job type
    if job in MAGIC_JOBS:
        mp = rand_int(80, 200)
    elif job in MINOR_MAGIC_JOBS:
        mp = rand_int(20, 60)
    else:
        mp = rand_int(0, 15)

    full, family = unique_full_name(taken_names)
    traits = ", ".join(random.sample(TRAITS, 2))

    # Founder King/Queen at world gen count as having served their current term,
    # so they show up in "Past Kings" stats, and they start with royal blood so
    # the cascade-to-descendants logic seeds the royal line correctly. Without
    # this the founders were invisible to lineage stats and their kids got 0
    # blue_blood unless one parent later married into another royal line.
    is_founder_royal = forced_job in ("King", "Queen")
    initial_king_terms = 1 if is_founder_royal else 0
    initial_blue_blood = 1 if is_founder_royal else 0

    return {
        "id": id_,
        "name": full,
        "family": family,
        "job": job,
        "gender": gender,
        "coins": coins,
        "age": age,
        "int": int_stat,
        "rep": rep,
        "level": level,
        "exp": exp,
        "atk": atk,
        "def": defense,
        "hp": hp,
        "mp": mp,
        "hunger": hunger,
        "traits": traits,
        "last_action": "",
        "alive": alive,
        "origin": "npc",
        "owner": "",
        "gen": 1,
        "immigrantGen": 0,
        "motherId": 0,
        "fatherId": 0,
        "childrenIds": [],
        "action_log": "",
        "relationships": {},
        "death_day": 0,
        "spouseId": 0,
        "spouseSinceDay": 0,
        "spouseId_at_death": 0,
        "kingTerms": initial_king_terms,
        "consecutiveTerms": initial_king_terms,
        "huntWins": 0,
        "huntWinsYear": 0,
        "born_day": 0,
        "last_birth_day": 0,
        "achievements": "[]",
        "kingsVotedFor": "[]",
        "blue_blood": initial_blue_blood,
        "disease": "",
        "disease_day": 0,
        "immunities": "[]",
    }

def generate_characters(n: int = 50) -> list[Villager]:
    """
    Generate an initial population of `n` villagers.
    """
    taken_names = set()
    characters = []

    global _next_villager_id
    _next_villager_id = 0

    if n >= 1:
        king_row = make_row(
            taken_names,
            jobs_pool=JOBS_NO_ROYAL,
            forced_gender="Male",
            forced_job="King",
        )
        characters.append(king_row)

    if n >= 2:
        queen_row = make_row(
            taken_names,
            jobs_pool=JOBS_NO_ROYAL,
            forced_gender="Female",
            forced_job="Queen",
        )
        characters.append(queen_row)
        _set_spouses(king_row, queen_row, current_day=0)

    # Ensure Queen title matches rule (Queen = King's spouse)
    sync_queen_to_king_spouse(characters, current_day=0)

    # Force a healthy ratio of producer jobs in the INITIAL spawn so the
    # village can feed itself from day 1. Uniform sampling from ~55 jobs gives
    # only ~3 farmers / 100 villagers, which can't keep pace with consumption.
    # Daily immigrants are unaffected — they're still uniformly sampled.
    remaining = n - len(characters)
    producer_quota_targets: list[str] = []
    food_weighting = {
        "Farmer": 8, "Fisher": 5, "Hunter": 5, "Shepherd": 4,
        "Baker": 3, "Butcher": 3, "Cook": 2, "Beekeeper": 2,
        "Woodcutter": 5, "Forester": 3, "Carpenter": 2,
        "Mason": 3, "Miner": 4, "Blacksmith": 2,
    }
    target_producer_count = int(remaining * 0.45)
    total_weight = max(1, sum(food_weighting.values()))
    for job, w in food_weighting.items():
        slots = max(1, int(round(w / total_weight * target_producer_count)))
        producer_quota_targets.extend([job] * slots)
    producer_quota_targets = producer_quota_targets[:target_producer_count]
    random.shuffle(producer_quota_targets)

    for i in range(remaining):
        forced = producer_quota_targets[i] if i < len(producer_quota_targets) else None
        characters.append(
            make_row(taken_names, jobs_pool=JOBS_NO_ROYAL, forced_job=forced)
        )

    return characters
