"""
Chronicle service — high-level helpers that turn structured simulation events
into narrative entries written to the chronicle_events table.

Each helper:
  - is best-effort (swallows exceptions so it never breaks the sim loop)
  - picks a phrasing variant from a small template pool
  - assigns an importance level (1-5)
  - records the actor IDs/names for later cross-linking

Categories: royal, family, combat, magic, economy, scandal, disaster, world
"""
from __future__ import annotations

import random
from typing import Any

from src.repositories.chronicle_repo import record_event
from src.repositories.world_repo import compute_year_and_day
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _safe_record(**kwargs) -> None:
    """Wrapper that never raises out of the sim loop."""
    try:
        record_event(**kwargs)
    except Exception as exc:
        logger.warning("Chronicle record failed: %s", exc)


def _actor(v: dict) -> dict:
    return {
        "id": int(v.get("id", 0) or 0),
        "name": (v.get("name") or "").strip() or "Unknown",
        "family": (v.get("family") or "").strip(),
    }


def _yd(day: int) -> tuple[int, int]:
    """Convert total_day -> (year, day_in_year)."""
    return compute_year_and_day(int(day or 1))


# ---------------------------------------------------------------------------
#  Royal
# ---------------------------------------------------------------------------

def record_election(
    winner: dict,
    prev_king: dict | None,
    votes: int,
    total_alive: int,
    day: int,
    emergency: bool = False,
    term_limited: bool = False,
) -> None:
    if not winner:
        return
    year, _ = _yd(day)
    name = winner.get("name", "Unknown")
    family = winner.get("family", "")
    pct = (votes / total_alive * 100) if total_alive else 0

    actors = [_actor(winner)]
    if prev_king:
        actors.append(_actor(prev_king))

    if emergency:
        headline = f"Emergency election: {name} crowned"
        body_choices = [
            f"With the throne suddenly empty, {name} of the {family} family was hastily raised to the crown — {votes} votes ({pct:.0f}% of the village).",
            f"The village convened in haste. {name} took the crown after winning {votes} of {total_alive} possible votes.",
            f"An emergency vote saw {name} crowned with {votes} votes — {pct:.0f}% of all living villagers.",
        ]
        importance = 5 if (prev_king and not prev_king.get("alive", True)) else 4
    elif prev_king and prev_king.get("id") != winner.get("id"):
        headline = f"{name} crowned, {prev_king.get('name','the former King')} steps down"
        body_choices = [
            f"After a contested vote ({votes} of {total_alive}, {pct:.0f}%), {name} ascends — and {prev_king.get('name')} returns to common life.",
            f"The crown changes hands: {name} takes the throne with {votes} votes, while {prev_king.get('name')} steps down.",
            f"The {family} banner rises — {name} elected King with {votes} of {total_alive} votes.",
        ]
        importance = 4
    elif not prev_king:
        headline = f"{name} elected first King"
        body_choices = [
            f"In the first true vote of the age, {name} of the {family} family takes the crown with {votes} votes ({pct:.0f}%).",
            f"The throne, long empty, finds its first occupant: {name}, chosen by {votes} of {total_alive} villagers.",
        ]
        importance = 5
    else:
        headline = f"{name} re-elected"
        body_choices = [
            f"The crown stays put. {name} re-elected with {votes} of {total_alive} votes ({pct:.0f}%).",
            f"Voters reaffirm {name}'s reign — {votes} votes, {pct:.0f}% of the living.",
        ]
        importance = 3

    if term_limited:
        body_choices = [
            f"All eligible candidates had reached the term limit. The village settled on {name} with {votes} votes."
        ]
        importance = max(importance, 4)

    _safe_record(
        day=day,
        year=year,
        category="royal",
        headline=headline,
        body=random.choice(body_choices),
        actors=actors,
        importance=importance,
    )


def record_assassination(king: dict, victim: dict, day: int) -> None:
    """King kills an enemy."""
    if not king or not victim:
        return
    year, _ = _yd(day)
    headline = f"King {king.get('name','?')} assassinated {victim.get('name','an enemy')}"
    body_choices = [
        f"In the dead of night, King {king.get('name')} settled an old grudge — {victim.get('name')} of the {victim.get('family','?')} family was found slain.",
        f"Whispers travel fast: King {king.get('name')} silenced {victim.get('name')}, an old rival, with no witnesses.",
        f"Court intrigue turned deadly. {victim.get('name')} fell to the King's blade.",
    ]
    _safe_record(
        day=day,
        year=year,
        category="scandal",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(king), _actor(victim)],
        importance=5,
    )


def record_king_death(king: dict, cause: str, day: int) -> None:
    if not king:
        return
    year, _ = _yd(day)
    headline = f"King {king.get('name','?')} is dead"
    body_choices = [
        f"The throne stands empty. King {king.get('name')} of the {king.get('family','?')} family fell — {cause}.",
        f"Mourning grips the village. King {king.get('name')} has died ({cause}).",
        f"The crown falls heavy: King {king.get('name')} has perished. Cause: {cause}.",
    ]
    _safe_record(
        day=day,
        year=year,
        category="royal",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(king)],
        importance=5,
    )


# ---------------------------------------------------------------------------
#  Family
# ---------------------------------------------------------------------------

def record_marriage(a: dict, b: dict, day: int) -> None:
    if not a or not b:
        return
    year, _ = _yd(day)
    headline = f"{a.get('name','?')} and {b.get('name','?')} are wed"
    body_choices = [
        f"Bells rang out as {a.get('name')} of the {a.get('family','?')} family wed {b.get('name')} of the {b.get('family','?')} family.",
        f"A union to remember: {a.get('name')} and {b.get('name')} stood together before the village and pledged their lives.",
        f"{a.get('name')} and {b.get('name')} have married — two families joined under one roof.",
    ]
    _safe_record(
        day=day,
        year=year,
        category="family",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(a), _actor(b)],
        importance=3,
    )


def record_birth(child: dict, mom: dict, dad: dict, day: int) -> None:
    if not child:
        return
    year, _ = _yd(day)
    headline = f"A child is born to the {child.get('family','?')} family"
    body_choices = [
        f"{(mom or {}).get('name','?')} and {(dad or {}).get('name','?')} welcomed a {child.get('gender','child').lower()}, named {child.get('name','?')}.",
        f"The {child.get('family','?')} family grows: {child.get('name','?')} drew first breath today.",
        f"A new villager: {child.get('name','?')}, born to {(mom or {}).get('name','?')} and {(dad or {}).get('name','?')}.",
    ]
    actors = [_actor(child)]
    if mom: actors.append(_actor(mom))
    if dad: actors.append(_actor(dad))
    _safe_record(
        day=day,
        year=year,
        category="family",
        headline=headline,
        body=random.choice(body_choices),
        actors=actors,
        importance=2,
    )


def record_death(victim: dict, cause: str, day: int) -> None:
    """Generic death — kings get a separate richer record. Importance scales with status."""
    if not victim:
        return
    year, _ = _yd(day)
    job = victim.get("job", "")
    age = int(victim.get("age", 0) or 0)
    name = victim.get("name", "Unknown")
    family = victim.get("family", "")

    # Importance based on social weight
    if job == "King":
        return record_king_death(victim, cause, day)
    if job in ("Queen", "Noble", "Commander", "Captain"):
        importance = 4
    elif job in ("Wizard", "Sorcerer", "Cleric", "Priest", "Healer"):
        importance = 3
    elif age <= 16:
        importance = 3  # child death is dramatic
    else:
        importance = 2

    headline = f"{name} has died"
    if "starv" in cause.lower():
        body_choices = [
            f"{name} of the {family or 'unknown'} family wasted away from hunger at age {age}.",
            f"The village lost {name} to starvation — a quiet death, common in lean times.",
        ]
    elif "combat" in cause.lower() or "killed" in cause.lower() or "slain" in cause.lower():
        body_choices = [
            f"{name} fell in battle at age {age}. {cause}.",
            f"Steel found {name} today. They leave behind {family or 'an old family'}.",
        ]
    elif age <= 16:
        body_choices = [
            f"Tragedy: young {name}, only {age}, did not survive. ({cause}.)",
            f"A child gone before their time — {name}, age {age}, passed today.",
        ]
    else:
        body_choices = [
            f"{name} of the {family or 'unknown'} family passed at age {age}. {cause}.",
            f"{name} is no more. Cause: {cause}.",
        ]

    _safe_record(
        day=day,
        year=year,
        category="family",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(victim)],
        importance=importance,
    )


# ---------------------------------------------------------------------------
#  World / disaster
# ---------------------------------------------------------------------------

def record_world_event(message: str, day: int) -> None:
    if not message:
        return
    year, _ = _yd(day)
    msg = message.strip()
    upper = msg.upper()

    if "PLAGUE" in upper:
        cat, importance = "disaster", 4
        headline = "A plague sweeps the village"
    elif "FAMINE" in upper:
        cat, importance = "disaster", 4
        headline = "Famine grips the land"
    elif "INVASION" in upper:
        cat, importance = "disaster", 5
        headline = "The village is invaded"
    elif "FESTIVAL" in upper:
        cat, importance = "world", 3
        headline = "A festival is held"
    elif "HARVEST" in upper:
        cat, importance = "world", 3
        headline = "A bountiful harvest"
    elif "BLESSING" in upper:
        cat, importance = "world", 3
        headline = "A blessing falls upon the village"
    else:
        cat, importance = "world", 2
        headline = "A notable event"

    _safe_record(
        day=day,
        year=year,
        category=cat,
        headline=headline,
        body=msg,
        actors=[],
        importance=importance,
    )


def record_immigrant_wave(count: int, day: int) -> None:
    if count <= 0:
        return
    year, _ = _yd(day)
    headline = f"{count} newcomer{'s' if count != 1 else ''} arrive"
    body_choices = [
        f"A small caravan rolled into the village — {count} new souls seeking a home.",
        f"The gates opened today for {count} immigrants, fleeing harder times elsewhere.",
        f"{count} new villagers joined the rolls today.",
    ]
    importance = 3 if count >= 3 else 2
    _safe_record(
        day=day,
        year=year,
        category="world",
        headline=headline,
        body=random.choice(body_choices),
        actors=[],
        importance=importance,
    )


def record_artifact_drop(killer: dict, enemy: dict, template: dict, equipped: bool, day: int) -> None:
    """Record an artifact drop from combat."""
    if not killer or not template:
        return
    year, _ = _yd(day)
    name = template.get("name", "an artifact")
    rarity = template.get("rarity", "common")
    slot = template.get("slot", "")
    enemy_name = (enemy or {}).get("name", "an enemy")
    enemy_tier = (enemy or {}).get("tier", "")
    killer_name = killer.get("name", "?")
    family = killer.get("family", "")

    headline = f"{killer_name} unearths the {name}"
    flavor = template.get("flavor", "").strip()

    if rarity == "legendary":
        body_choices = [
            f"From the corpse of a {enemy_tier} {enemy_name}, {killer_name} of the {family or 'unknown'} family drew forth the {name} — a legendary {slot}.",
            f"A find for the songs: {killer_name} claimed the {name} after slaying a {enemy_tier} {enemy_name}.",
        ]
        importance = 4
    elif rarity == "rare":
        body_choices = [
            f"{killer_name} pried the {name} from the dead — a rare {slot} won from a {enemy_tier} {enemy_name}.",
            f"A rare prize: {killer_name} carries the {name} home from the hunt.",
        ]
        importance = 3
    else:
        body_choices = [
            f"{killer_name} looted a {name} from a {enemy_tier} {enemy_name}.",
            f"Among the spoils, {killer_name} found the {name}.",
        ]
        importance = 2

    body = random.choice(body_choices)
    if flavor:
        body = f"{body} ({flavor})"
    if equipped:
        body = f"{body} They wear it now."

    _safe_record(
        day=day,
        year=year,
        category="combat",
        headline=headline,
        body=body,
        actors=[_actor(killer)],
        importance=importance,
    )


def record_artifact_inheritance(
    artifact_template: dict,
    deceased: dict,
    heir: dict | None,
    relation: str,
    day: int,
    history_count: int = 1,
) -> None:
    """
    Heir picked up the deceased's artifact. `relation` is one of
    'child', 'spouse', 'sibling', 'family'.
    """
    if not artifact_template or not deceased:
        return
    year, _ = _yd(day)
    name = artifact_template.get("name", "an artifact")
    rarity = artifact_template.get("rarity", "common")
    deceased_name = deceased.get("name", "?")
    deceased_family = deceased.get("family", "")
    heir_name = (heir or {}).get("name", "an heir")

    rel_phrase = {
        "child": "child",
        "spouse": "spouse",
        "sibling": "sibling",
        "family": "kin",
    }.get(relation, "kin")

    headline = f"{heir_name} takes up the {name}"
    body_choices = [
        f"With {deceased_name} of the {deceased_family or 'unknown'} family laid to rest, "
        f"{heir_name} — their {rel_phrase} — took up the {name}.",
        f"The {name} changes hands once more: {heir_name} now bears it after the death of {deceased_name}.",
    ]
    if history_count >= 3:
        body_choices.append(
            f"The {name} has known {history_count} owners now. Today {heir_name} adds their name to its chronicle."
        )

    importance = 4 if rarity == "legendary" else 3 if rarity == "rare" else 2
    # An artifact carrying a long lineage (4+ past owners) is news on its own,
    # regardless of base rarity.
    if history_count >= 4:
        importance = max(importance, 4)

    actors = [_actor(deceased)]
    if heir:
        actors.append(_actor(heir))

    _safe_record(
        day=day,
        year=year,
        category="family",
        headline=headline,
        body=random.choice(body_choices),
        actors=actors,
        importance=importance,
    )


def record_artifact_destroyed(artifact_template: dict, deceased: dict, day: int) -> None:
    """Soulbound artifact destroyed at owner's death."""
    if not artifact_template or not deceased:
        return
    year, _ = _yd(day)
    name = artifact_template.get("name", "an artifact")
    rarity = artifact_template.get("rarity", "common")
    deceased_name = deceased.get("name", "?")
    family = deceased.get("family", "")

    # Strip a leading "The " so we don't get "The The Ashen Crown".
    bare = name[4:] if name.lower().startswith("the ") else name
    headline = f"The {bare} is lost with {deceased_name}"
    body_choices = [
        f"{deceased_name} of the {family or 'unknown'} family went to the grave wearing {name}. "
        "It will not be worn again.",
        f"{name} was bound to {deceased_name}'s soul. Tonight, both have left the world.",
    ]
    importance = 5 if rarity == "legendary" else 3

    _safe_record(
        day=day,
        year=year,
        category="family",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(deceased)],
        importance=importance,
    )


def record_artifact_liquidated(artifact_template: dict, deceased: dict, gold: int, day: int) -> None:
    """No heirs — artifact sold off to fund the treasury."""
    if not artifact_template or not deceased:
        return
    year, _ = _yd(day)
    name = artifact_template.get("name", "an artifact")
    deceased_name = deceased.get("name", "?")
    rarity = artifact_template.get("rarity", "common")

    headline = f"{name} sold from {deceased_name}'s estate"
    body = (
        f"With no heir to claim it, the {name} was sold from {deceased_name}'s estate. "
        f"The treasury gained {gold} coins."
    )
    importance = 3 if rarity in ("rare", "legendary") else 2

    _safe_record(
        day=day,
        year=year,
        category="economy",
        headline=headline,
        body=body,
        actors=[_actor(deceased)],
        importance=importance,
    )


def record_quest(quest: dict, day: int) -> None:
    """Hook for quest completion (success or failure)."""
    if not quest:
        return
    year, _ = _yd(day)
    name = quest.get("name") or quest.get("type") or "A quest"
    success = bool(quest.get("success"))
    deaths = int(quest.get("deaths", 0) or 0)
    gold = int(quest.get("gold", 0) or 0)

    headline = f"Quest {'succeeded' if success else 'failed'}: {name}"
    if success:
        body = f"The party returned victorious from {name}, claiming {gold} gold." + (f" Cost: {deaths} dead." if deaths else "")
        importance = 4 if (gold >= 500 or deaths >= 2) else 3
    else:
        body = f"{name} ended in disaster." + (f" {deaths} of the party did not return." if deaths else "")
        importance = 4 if deaths >= 2 else 3

    # ARCANE quest is legendary
    if "ARCANE" in (name or "").upper() or quest.get("type") == "arcane":
        importance = 5

    _safe_record(
        day=day,
        year=year,
        category="magic" if (quest.get("type") == "arcane" or "ARCANE" in name.upper()) else "world",
        headline=headline,
        body=body,
        actors=[],
        importance=importance,
    )
