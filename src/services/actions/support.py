"""Support actions: mentor, heal_sick, forge_artifact.

Grouped together because each one is heavily gated (age + skills / Healer
job + sick patients / Smith eligibility + treasury) and produces a
relatively rare, narrative-heavy outcome rather than baseline stat tweaks.
"""
from __future__ import annotations

import random

from config import CHILD_MAX_AGE
from src.utils.world_utils import rand_int
from src.services.relationship_service import adjust_relationship
from src.services.skill_service import (
    parse_skills, get_skill_info,
    add_skill_to_villager, add_learning_progress, reset_learning_progress,
)
from src.models.villager import Villager
from src.models.bank import Bank


def apply_mentor(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    """Age 20+ villagers with skills can teach children. After 100 lessons in
    a skill, the child gains it. Small chance of failure resets progress.
    """
    mentor_skills = parse_skills(v.get("skills", ""))

    if not mentor_skills or not all_characters:
        v["hunger"] += rand_int(2, 5)
        v["last_action"] = "mentor (no one to teach)"
        return

    children = [
        c for c in all_characters
        if c.get("id") != v.get("id")
        and c.get("alive", True)
        and c.get("age", 100) <= CHILD_MAX_AGE
    ]

    if not children:
        v["hunger"] += rand_int(2, 5)
        v["last_action"] = "mentor (no children available)"
        return

    num_mentees = min(rand_int(1, 2), len(children))
    random.shuffle(children)
    mentees = children[:num_mentees]

    skill_to_teach = random.choice(mentor_skills)
    get_skill_info(skill_to_teach)  # legacy lookup to keep parity (was unused result)

    taught_names = []
    skills_gained = []
    progress_reset = []

    for child in mentees:
        mentor_int = v.get("int", 10)
        fail_chance = max(0.02, 0.05 - (mentor_int / 1000))

        if random.random() < fail_chance:
            reset_learning_progress(child, skill_to_teach)
            progress_reset.append(child["name"])
        else:
            current = add_learning_progress(child, skill_to_teach, rand_int(1, 3))

            if current >= 100:
                if add_skill_to_villager(child, skill_to_teach):
                    skills_gained.append((child["name"], skill_to_teach))
                    reset_learning_progress(child, skill_to_teach)

            taught_names.append(child["name"])

        rel_gain = rand_int(3, 8)
        adjust_relationship(v, child, rel_gain)
        adjust_relationship(child, v, rel_gain)

    v["rep"] = v.get("rep", 0) + rand_int(1, 3)
    v["exp"] += rand_int(2, 5)
    v["int"] += rand_int(0, 1)
    v["hunger"] += rand_int(3, 7)

    action_parts = []
    if taught_names:
        action_parts.append(f"taught {', '.join(taught_names)} [{skill_to_teach}]")
    if skills_gained:
        for name, skill in skills_gained:
            action_parts.append(f"{name} mastered {skill}!")
    if progress_reset:
        action_parts.append(f"{', '.join(progress_reset)} failed to learn")

    if action_parts:
        v["last_action"] = f"mentor ({'; '.join(action_parts)})"
    else:
        v["last_action"] = "mentor (no results)"


def apply_heal_sick(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    from src.services.disease_service import (
        find_sick_in_circle, cure_chance, cure as cure_patient,
    )
    from config import DISEASES, HEALER_JOBS
    from src.repositories.world_repo import load_day

    day_for_heal = current_day if current_day is not None else load_day()

    if v.get("job") not in HEALER_JOBS:
        v["hunger"] += rand_int(1, 3)
        v["last_action"] = "considered healing but not a healer"
        return

    patients = find_sick_in_circle(v, all_characters or [], limit=1)
    if not patients:
        v["hunger"] += rand_int(1, 3)
        v["hp"] += rand_int(0, 2)
        v["last_action"] = "looked for the sick (none found)"
        return

    patient = patients[0]
    disease = (patient.get("disease") or "").strip()
    p = cure_chance(patient, v, bank)
    roll = random.random()
    v["hunger"] += rand_int(3, 7)
    v["exp"] += rand_int(2, 5)
    if roll < p:
        cure_patient(patient, v, day_for_heal)
        v["rep"] = int(v.get("rep", 0) or 0) + rand_int(2, 5)
        coin_tip = rand_int(2, 8)
        v["coins"] = int(v.get("coins", 0) or 0) + coin_tip
        illness_name = DISEASES.get(disease, {}).get("name", disease) if disease else "illness"
        v["last_action"] = f"cured {patient.get('name','?')} of {illness_name.lower()} (+{coin_tip}g tip)"
        last = patient.get("last_action") or ""
        patient["last_action"] = (last + " / " if last else "") + f"cured by {v.get('name','a healer')}"
        try:
            from src.services.chronicle_service import record_disease_cure
            record_disease_cure(v, patient, disease, day=int(day_for_heal))
        except Exception:
            pass
    else:
        illness_name = DISEASES.get(disease, {}).get("name", disease) if disease else "illness"
        v["last_action"] = f"tended to {patient.get('name','?')} ({illness_name.lower()}, no cure yet)"


def apply_forge_artifact(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    from src.services import artifact_service
    from src.repositories import artifact_repo
    from src.repositories.world_repo import load_day
    from src.services.chronicle_service import _safe_record, _yd, _actor

    day_for_drop = current_day if current_day is not None else load_day()

    # Defense in depth: re-check eligibility (the action weight is 0.05 floor
    # so non-eligible villagers can rarely still pick this; we punt them).
    eligible, reason = artifact_service.can_forge(v, bank, current_day=day_for_drop)
    if not eligible:
        v["hp"] += rand_int(1, 3)
        v["hunger"] += rand_int(2, 4)
        v["last_action"] = f"considered forging but couldn't ({reason})"
        return

    # Cost scales with INT (more skilled smiths use rarer materials).
    cost = rand_int(artifact_service.FORGE_BASE_COST_MIN,
                    artifact_service.FORGE_BASE_COST_MAX)
    v_int = int(v.get("int", 0) or 0)
    if v_int >= 80:
        cost += rand_int(150, 350)
    bank["balance"] = max(0, int(bank.get("balance", 0) or 0) - cost)
    v["last_forge_day"] = int(day_for_drop or 0)
    v["hunger"] += rand_int(10, 20)

    # Random failure even when fully eligible — forging is hard.
    if random.random() < artifact_service.FORGE_FAILURE_CHANCE:
        v["exp"] = int(v.get("exp", 0) or 0) + rand_int(4, 8)
        v["last_action"] = (
            f"forge attempt failed — materials wasted ({cost}g treasury)"
        )
        return

    # Rarity weights skew strongly toward common; rare is exceptional.
    if v_int >= 80:
        roll_weights = {"common": 0.55, "uncommon": 0.40, "rare": 0.05}
    else:
        roll_weights = {"common": 0.80, "uncommon": 0.18, "rare": 0.02}

    rarity = artifact_service._pick_weighted(roll_weights)

    if v.get("job", "") == "Blacksmith":
        slot_pool = ["weapon", "armor"]
    else:
        slot_pool = ["weapon", "armor", "ring", "tome"]

    candidates = [t for t in artifact_service.list_templates()
                  if t.get("rarity") == rarity and t.get("slot") in slot_pool
                  and (t.get("binding") or "none") != "soulbound"]
    if not candidates:
        candidates = [t for t in artifact_service.list_templates()
                      if t.get("rarity") == rarity
                      and (t.get("binding") or "none") != "soulbound"]

    if not candidates:
        v["last_action"] = (
            f"forge produced no fitting design ({cost}g spent)"
        )
        return

    template = random.choice(candidates)
    artifact_id = artifact_repo.create_artifact(
        slug=template["slug"],
        owner_id=int(v.get("id", 0) or 0),
        acquired_day=int(day_for_drop or 0),
        acquired_via=f"forge:{v.get('job','')}",
        forged_history=[
            {
                "owner_id": int(v.get("id", 0) or 0),
                "owner_name": (v.get("name") or "").strip(),
                "day": int(day_for_drop or 0),
                "event": "acquired",
                "via": f"forged at the {v.get('job','craft').lower()}'s bench",
            }
        ],
    )
    artifact_service.auto_equip_if_better(v, artifact_id, template)
    v["int"] = v_int + rand_int(1, 2)
    v["exp"] = int(v.get("exp", 0) or 0) + rand_int(12, 24)
    v["last_action"] = (
        f"forged the {template.get('name','artifact')} ({cost}g treasury)"
    )

    # Chronicle entry — importance scales with rarity.
    try:
        year, _ = _yd(int(day_for_drop or 0))
        rar = template.get("rarity", "common")
        importance = 4 if rar == "rare" else 3 if rar == "uncommon" else 2
        _safe_record(
            day=int(day_for_drop or 0),
            year=year,
            category="economy",
            headline=f"{v.get('name','?')} forges the {template.get('name','artifact')}",
            body=(
                f"{v.get('name','?')} of the {v.get('family','unknown')} family "
                f"shaped a new {template.get('slot','tool')} at the cost of {cost} coins "
                f"from the treasury."
            ),
            actors=[_actor(v)],
            importance=importance,
        )
    except Exception:
        pass
