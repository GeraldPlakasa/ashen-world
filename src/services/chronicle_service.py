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
    runners_up: list[dict] | None = None,
) -> None:
    """`total_alive` historically meant the whole population; it now carries
    the count of *eligible voters* (alive adults age 16+) so the percentage
    matches the on-page tally. Param name kept for backward compatibility.

    `runners_up` is an optional list of {id, name, family, votes} dicts for
    the non-winning candidates that received at least one vote (top 3 by
    vote count). They are appended to the body and registered as actors so
    losing-candidate context is preserved in the chronicle."""
    if not winner:
        return
    year, _ = _yd(day)
    name = winner.get("name", "Unknown")
    family = winner.get("family", "")
    total_voters = total_alive
    pct = (votes / total_voters * 100) if total_voters else 0

    actors = [_actor(winner)]
    if prev_king:
        actors.append(_actor(prev_king))

    if emergency:
        headline = f"Emergency election: {name} crowned"
        body_choices = [
            f"With the throne suddenly empty, {name} of the {family} family was hastily raised to the crown — {votes} votes ({pct:.0f}% of {total_voters} eligible voters).",
            f"The village convened in haste. {name} took the crown after winning {votes} of {total_voters} possible votes.",
            f"An emergency vote saw {name} crowned with {votes} votes — {pct:.0f}% of eligible voters.",
        ]
        importance = 5 if (prev_king and not prev_king.get("alive", True)) else 4
    elif prev_king and prev_king.get("id") != winner.get("id"):
        headline = f"{name} crowned, {prev_king.get('name','the former King')} steps down"
        body_choices = [
            f"After a contested vote ({votes} of {total_voters}, {pct:.0f}%), {name} ascends — and {prev_king.get('name')} returns to common life.",
            f"The crown changes hands: {name} takes the throne with {votes} votes, while {prev_king.get('name')} steps down.",
            f"The {family} banner rises — {name} elected King with {votes} of {total_voters} votes.",
        ]
        importance = 4
    elif not prev_king:
        headline = f"{name} elected first King"
        body_choices = [
            f"In the first true vote of the age, {name} of the {family} family takes the crown with {votes} votes ({pct:.0f}%).",
            f"The throne, long empty, finds its first occupant: {name}, chosen by {votes} of {total_voters} eligible voters.",
        ]
        importance = 5
    else:
        headline = f"{name} re-elected"
        body_choices = [
            f"The crown stays put. {name} re-elected with {votes} of {total_voters} votes ({pct:.0f}%).",
            f"Voters reaffirm {name}'s reign — {votes} votes, {pct:.0f}% of eligible voters.",
        ]
        importance = 3

    if term_limited:
        body_choices = [
            f"All eligible candidates had reached the term limit. The village settled on {name} with {votes} votes."
        ]
        importance = max(importance, 4)

    body = random.choice(body_choices)

    # Append runners-up to the body so losing candidates appear in the
    # historical record. Also push them onto the actors list so the
    # chronicle UI can link to them.
    if runners_up:
        parts = []
        for r in runners_up:
            rname = r.get("name", "?")
            rfam = r.get("family", "")
            rvotes = int(r.get("votes", 0) or 0)
            fam_str = f" of the {rfam} family" if rfam else ""
            parts.append(f"{rname}{fam_str} ({rvotes} votes)")
            actors.append({
                "id": int(r.get("id", 0) or 0),
                "name": rname,
                "family": rfam,
            })
        if parts:
            label = "Other contender" if len(parts) == 1 else "Other contenders"
            body += f" {label}: " + "; ".join(parts) + "."

    _safe_record(
        day=day,
        year=year,
        category="royal",
        headline=headline,
        body=body,
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


def record_rivalry_brewing(loser: dict, king: dict, streak: int, day: int) -> None:
    """A runner-up has lost `streak` consecutive elections and is publicly
    embittered. Importance scales with streak length so a 3-loss rival is
    medium-importance and a 5+-loss rival headlines."""
    if not loser or not king:
        return
    year, _ = _yd(day)
    importance = 3 if streak <= 3 else (4 if streak <= 4 else 5)
    headline = f"{loser.get('name','?')} loses {streak} elections in a row"
    fam = loser.get("family", "")
    fam_str = f" of the {fam} family" if fam else ""
    body_choices = [
        f"{loser.get('name','?')}{fam_str} has now placed second in {streak} elections without ever taking the throne. Whispers grow that {loser.get('name','?')} no longer accepts the people's verdict and sees King {king.get('name','?')} as a usurper.",
        f"For the {streak}th time, {loser.get('name','?')}{fam_str} ran for King and lost — this time to {king.get('name','?')}. Witnesses in the tavern say the words 'next time, by other means' were heard.",
        f"{loser.get('name','?')}{fam_str} stormed out of the vote count after another loss to King {king.get('name','?')}. {streak} elections, {streak} defeats — the next move may not be a ballot.",
    ]
    _safe_record(
        day=day,
        year=year,
        category="royal",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(loser), _actor(king)],
        importance=importance,
    )


def record_coup(rival: dict, king: dict, streak: int, day: int) -> None:
    """A losing-streak rival successfully assassinates the reigning king.
    Highest-importance political event; the chronicle references the
    rivalry streak so the reader can connect the build-up to the act."""
    if not rival or not king:
        return
    year, _ = _yd(day)
    headline = f"King {king.get('name','?')} slain — coup by {rival.get('name','?')}"
    fam = rival.get("family", "")
    fam_str = f" of the {fam} family" if fam else ""
    body_choices = [
        f"After {streak} elections lost to him, {rival.get('name','?')}{fam_str} struck down King {king.get('name','?')} in the dead of night. The throne stands empty; an emergency vote will follow at dawn.",
        f"The long-rumoured coup arrived. {rival.get('name','?')}{fam_str}, denied the crown {streak} times by the ballot, took it by the blade — King {king.get('name','?')} is dead.",
        f"Blood on the steps of the royal court. {rival.get('name','?')}{fam_str}, a perennial runner-up ({streak} losses), assassinated King {king.get('name','?')} and vanished into the crowd.",
    ]
    _safe_record(
        day=day,
        year=year,
        category="scandal",
        headline=headline,
        body=random.choice(body_choices),
        actors=[_actor(rival), _actor(king)],
        importance=5,
    )


def record_militarization_decree(king: dict, conscripts: list[dict], day: int) -> None:
    """King declares a militarization decree on taking office, conscripting
    civilians into Guard/Scout duty. Records a single chronicle entry naming
    the king and how many were drafted."""
    if not king or not conscripts:
        return
    year, _ = _yd(day)
    n = len(conscripts)
    headline = f"King {king.get('name','?')} decrees conscription"
    names = ", ".join(c.get("name", "?") for c in conscripts[:4])
    if n > 4:
        names += f", and {n - 4} more"
    body_choices = [
        f"On taking the crown, King {king.get('name')} declared the village must arm itself — {n} villagers ({names}) were pressed into Guard and Scout duty, with no recourse.",
        f"King {king.get('name')}'s first decree: militarization. {n} civilians ({names}) traded their trades for spears and watchtowers.",
        f"The new King {king.get('name')} brooked no debate. {n} villagers ({names}) were conscripted into the watch overnight.",
    ]
    actors = [_actor(king)] + [_actor(c) for c in conscripts[:6]]
    _safe_record(
        day=day,
        year=year,
        category="royal",
        headline=headline,
        body=random.choice(body_choices),
        actors=actors,
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

def record_trade_import(king: dict, purchases: list, total_cost: int, day: int) -> None:
    """Record a king's foreign-trade import in the chronicle.
    purchases: list of (resource, units, cost) tuples.
    """
    if not purchases or not king:
        return
    year, _ = _yd(day)
    parts = ", ".join(f"+{u} {r} ({c}g)" for (r, u, c) in purchases)
    body = (
        f"King {king.get('name','')} of {king.get('family','')} spent "
        f"{total_cost}g of village treasury on imports from outside: {parts}."
    )
    _safe_record(
        day=day,
        year=year,
        category="economy",
        headline=f"King {king.get('name','')} orders imports",
        body=body,
        actors=[_actor(king)],
        importance=2,
    )


def record_disease_outbreak(victim: dict, disease: str, day: int) -> None:
    """Record an individual catching an illness. Low importance (1) — these
    happen often; raise to 3 only for plague which is dramatic.
    """
    if not victim or not disease:
        return
    try:
        from config import DISEASES
        name = DISEASES.get(disease, {}).get("name", disease)
    except Exception:
        name = disease
    year, _ = _yd(day)
    importance = 3 if disease == "plague" else (2 if disease == "fever" else 1)
    _safe_record(
        day=day,
        year=year,
        category="health",
        headline=f"{victim.get('name','?')} has fallen ill with {name.lower()}",
        body=f"{victim.get('name','?')} of the {victim.get('family','?')} family was struck down by {name.lower()}.",
        actors=[_actor(victim)],
        importance=importance,
    )


def record_disease_cure(healer: dict, patient: dict, disease: str, day: int) -> None:
    """Record a successful healing — rewards the healer's reputation."""
    if not healer or not patient:
        return
    try:
        from config import DISEASES
        name = DISEASES.get(disease, {}).get("name", disease) if disease else "an illness"
    except Exception:
        name = disease or "an illness"
    year, _ = _yd(day)
    _safe_record(
        day=day,
        year=year,
        category="health",
        headline=f"{healer.get('name','?')} cured {patient.get('name','?')} of {name.lower()}",
        body=(
            f"{healer.get('name','?')} the {healer.get('job','healer')} tended to "
            f"{patient.get('name','?')} and brought them back from {name.lower()}."
        ),
        actors=[_actor(healer), _actor(patient)],
        importance=2,
    )


def record_trade_export(king: dict, sales: list, total_earned: int, day: int) -> None:
    """Record a king's surplus-export sale in the chronicle.
    sales: list of (resource, units, earned) tuples.
    """
    if not sales or not king:
        return
    year, _ = _yd(day)
    parts = ", ".join(f"-{u} {r} (+{e}g)" for (r, u, e) in sales)
    body = (
        f"King {king.get('name','')} of {king.get('family','')} sold surplus "
        f"stockpile to outside merchants for {total_earned}g: {parts}."
    )
    _safe_record(
        day=day,
        year=year,
        category="economy",
        headline=f"King {king.get('name','')} sells surplus",
        body=body,
        actors=[_actor(king)],
        importance=2,
    )


def record_season_change(new_season: str, day: int) -> None:
    """Best-effort chronicle entry on a season transition.

    Emits a low-importance world entry so the seasonal rhythm is visible in
    the Town Crier feed without crowding out plagues / wars / elections.
    """
    season = (new_season or "").strip().lower()
    if not season:
        return
    year, _ = _yd(day)
    pool = {
        "spring": [
            "Spring arrives — fields thaw, blossoms return.",
            "The first warm winds blow through the valley. Spring has come.",
            "Spring breaks the grip of winter. Sowing begins.",
        ],
        "summer": [
            "Summer settles over the village. The sun bakes the high road.",
            "Long summer days return. Markets bustle past dusk.",
            "Summer is here — the granaries empty as the fields grow tall.",
        ],
        "autumn": [
            "Autumn comes; the harvest begins.",
            "Leaves turn. The barns fill with the year's grain.",
            "Autumn winds carry woodsmoke through every lane.",
        ],
        "winter": [
            "Winter descends. The first snows quiet the streets.",
            "The cold months begin. Hearths burn long and food is rationed.",
            "Winter comes for the village. Fields lie fallow under frost.",
        ],
    }.get(season, [f"A new season begins: {season}."])
    icons = {"spring": "🌱", "summer": "☀️", "autumn": "🍂", "winter": "❄️"}
    headline = f"{icons.get(season, '·')} {season.capitalize()} begins"
    body = random.choice(pool)
    _safe_record(
        day=day,
        year=year,
        category="world",
        headline=headline,
        body=body,
        actors=[],
        importance=2,
    )


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


# ---------------------------------------------------------------------------
#  Justice (crime & trial)
# ---------------------------------------------------------------------------

def record_crime(
    criminal: dict,
    victim: dict | None,
    crime_type: str,
    witness: dict | None,
    day: int,
) -> None:
    """A crime was witnessed and pending case opened. Records a justice entry
    so the chronicle shows the report before the trial verdict."""
    if not criminal:
        return
    year, _ = _yd(day)
    cname = criminal.get("name", "Someone")
    cfam = criminal.get("family", "")
    vname = victim.get("name") if victim else None
    wname = witness.get("name") if witness else None

    if crime_type == "theft":
        headline = f"{cname} accused of theft"
        body_choices = [
            f"{cname} of the {cfam} family was seen rifling through " + (f"{vname}'s belongings" if vname else "the village stores") + ".",
            f"A theft has been reported against {cname}." + (f" The victim: {vname}." if vname else ""),
        ]
        importance = 2
    elif crime_type == "assault":
        headline = f"{cname} accused of assault"
        body_choices = [
            f"{cname} struck " + (f"{vname}" if vname else "a fellow villager") + " in broad daylight.",
            f"Blood was drawn — {cname} stands accused of attacking " + (f"{vname}" if vname else "another villager") + ".",
        ]
        importance = 3
    elif crime_type == "murder":
        headline = f"{cname} accused of murder"
        body_choices = [
            f"A killing! " + (f"{vname} was found dead, and {cname} stands accused." if vname else f"{cname} is accused of murder."),
            f"{cname} of the {cfam} family is charged with the murder of " + (vname or "a villager") + ".",
        ]
        importance = 5
    else:
        return

    if wname:
        body_choices = [b + f" {wname} bore witness." for b in body_choices]

    actors = [_actor(criminal)]
    if victim:
        actors.append(_actor(victim))
    if witness:
        actors.append(_actor(witness))

    _safe_record(
        day=day,
        year=year,
        category="justice",
        headline=headline,
        body=random.choice(body_choices),
        actors=actors,
        importance=importance,
    )


def record_trial_verdict(
    king: dict,
    criminal: dict,
    victim: dict | None,
    crime_type: str,
    verdict: str,
    outcome: dict,
    day: int,
) -> None:
    """The king ruled on a pending case. Records the verdict."""
    if not criminal or not king:
        return
    year, _ = _yd(day)
    kname = king.get("name", "the King")
    cname = criminal.get("name", "the accused")
    vname = victim.get("name") if victim else None
    paid = int(outcome.get("amount_paid", 0) or 0)

    if verdict == "fine":
        headline = f"{cname} fined for {crime_type}"
        body = f"King {kname} ruled on the {crime_type} case against {cname}. A fine of {paid} coins was levied."
        importance = 2 if crime_type == "theft" else 3
    elif verdict == "exile":
        headline = f"{cname} exiled for {crime_type}"
        body = f"King {kname} cast {cname} out of the village for {crime_type}. They are never to return."
        importance = 4
    elif verdict == "execution":
        headline = f"{cname} executed for {crime_type}"
        body = f"By order of King {kname}, {cname} was put to death for {crime_type}."
        if vname:
            body += f" Justice for {vname}."
        importance = 4
    else:
        return

    actors = [_actor(king), _actor(criminal)]
    if victim:
        actors.append(_actor(victim))

    _safe_record(
        day=day,
        year=year,
        category="justice",
        headline=headline,
        body=body,
        actors=actors,
        importance=importance,
    )
