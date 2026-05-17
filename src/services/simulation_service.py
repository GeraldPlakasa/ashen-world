from __future__ import annotations

import json
import random

from config import (
    JOBS_NO_ROYAL,
    MAGIC_JOBS,
    MINOR_MAGIC_JOBS,
    FOOD_PER_ADULT_PER_DAY,
    FOOD_PER_CHILD_PER_DAY,
    GRANARY_CONSUMPTION_MULT,
)
from src.utils.world_utils import (
    clamp,
    rand_int,
    is_child,
)
from src.services.building_service import (
    get_building_level,
)
from src.services.villager_service import (
    make_row,
    reset_id_from_characters,
)
from src.services.action_service import (
    choose_action,
    apply_action,
    append_action_history,
)
from src.services.combat_service import (
    apply_starvation_damage,
)
from src.services.relationship_service import (
    spouse_daily_phase,
    maybe_corrupt_from_bank,
    king_assassination_phase,
    rival_coup_phase,
)
from src.services.event_service import (
    maybe_trigger_event,
)
from src.services.family_service import (
    child_daily_phase,
    coming_of_age_phase,
)
from src.services.achievement_service import (
    achievement_check_phase,
    trigger_iron_will_check,
)
from src.services.quest_service import maybe_trigger_quest
from src.repositories.world_repo import load_weather
from src.models.villager import Villager
from src.models.bank import Bank


# ===========================================================================
#  Elder Decay Phase (age 70+)
# ===========================================================================

def elder_decay_phase(characters: list[Villager], current_day: int = 0) -> int:
    """
    Apply daily decay for elderly villagers (70+).

    - Age 70-79: 40% chance of 1 HP loss/day, 1% stat decay chance, ~0.9% yearly death
    - Age 80-89: HP decay 1-2, 5% stat decay chance, ~7% yearly death
    - Age 90-99: HP decay 1-3, 10% stat decay chance, ~17% yearly death
    - Age 100+: HP decay 2-5, 15% stat decay chance, ~30% yearly death

    Returns number of natural deaths from old age.
    """
    natural_deaths = 0

    for v in characters:
        if not v.get("alive", True):
            continue

        age = int(v.get("age", 0) or 0)
        if age < 70:
            continue

        hp = int(v.get("hp", 100) or 100)
        atk = int(v.get("atk", 10) or 10)
        def_stat = int(v.get("def", 10) or 10)
        int_stat = int(v.get("int", 10) or 10)

        hp_decay = 0
        stat_decay_chance = 0.0
        death_chance = 0.0

        if 70 <= age < 80:
            # Early elder: very gentle decay. Reduced from prior tuning where
            # too many villagers died "peacefully" in their early 70s before
            # ever reaching real old age. HP loss is now probabilistic (40%
            # of days lose 1 HP, else 0) instead of every day, and the stat
            # decay chance is halved.
            hp_decay = 1 if random.random() < 0.40 else 0
            stat_decay_chance = 0.01  # 1% chance per day (was 2%)
            death_chance = 0.00025  # ~0.9% per year (was ~1.8%)
        elif 80 <= age < 90:
            # Old: mild decay
            hp_decay = rand_int(1, 2)
            stat_decay_chance = 0.05  # 5% chance
            death_chance = 0.002  # 0.2% per day (~7% per year)
        elif 90 <= age < 100:
            # Very old: moderate decay
            hp_decay = rand_int(1, 3)
            stat_decay_chance = 0.10  # 10% chance
            death_chance = 0.005  # 0.5% per day (~17% per year)
        else:  # 100+
            # Ancient: noticeable decay but survivable
            hp_decay = rand_int(2, 5)
            stat_decay_chance = 0.15  # 15% chance
            death_chance = 0.01  # 1% per day (~30% per year)
        
        # Apply HP decay
        v["hp"] = max(0, hp - hp_decay)
        
        # MP decay for elders (magic fades with age)
        mp = int(v.get("mp", 0) or 0)
        if mp > 0 and random.random() < stat_decay_chance:
            mp_decay = rand_int(1, 3)
            v["mp"] = max(0, mp - mp_decay)

        # Stat decay (random which stat decreases)
        if random.random() < stat_decay_chance:
            stat_to_decay = random.choice(["atk", "def", "int"])
            decay_amount = rand_int(1, 2)
            if stat_to_decay == "atk":
                v["atk"] = max(1, atk - decay_amount)
            elif stat_to_decay == "def":
                v["def"] = max(1, def_stat - decay_amount)
            else:
                v["int"] = max(1, int_stat - decay_amount)
        
        # Check for natural death
        if v["hp"] <= 0 or random.random() < death_chance:
            v["hp"] = 0
            v["alive"] = False
            v["death_day"] = current_day
            v["last_action"] = f"passed away peacefully at age {age}"
            natural_deaths += 1
        else:
            # Update last_action to note aging effects
            if hp_decay > 3:
                current_action = v.get("last_action", "")
                if current_action:
                    v["last_action"] = f"{current_action} / aging -{hp_decay} HP"
                else:
                    v["last_action"] = f"feeling age... -{hp_decay} HP"
    
    return natural_deaths

def maybe_add_immigrants(characters: list[Villager], bank: Bank) -> tuple[list[Villager], int]:
    """
    Daily chance for 1-2 immigrants to arrive.
    Base 1.5% chance, tavern increases by 1% per level.
    """
    tavern_lvl = get_building_level(bank, "tavern")

    # Lower base chance for controlled population growth
    base_chance = 0.015 + 0.01 * tavern_lvl  # 1.5% base, +1% per tavern level
    chance = max(0.01, min(0.08, base_chance))  # 1-8% range

    if random.random() >= chance:
        return characters, 0

    add_count = rand_int(1, 2)  # 1-2 immigrants per arrival

    taken_names = {c.get("name", "") for c in characters}
    added = []

    for _ in range(add_count):
        new_v = make_row(taken_names, jobs_pool=JOBS_NO_ROYAL)

        new_v["origin"] = "npc"
        new_v["immigrantGen"] = 1

        arrival_msg = f"{new_v['name']} arrived to settle in the village."
        new_v["last_action"] = "immigrant arrival"
        new_v["action_log"] = arrival_msg

        characters.append(new_v)
        added.append(new_v)

    return characters, len(added)


def _norm_origin(v: Villager) -> str:
    return (v.get("origin", "") or "").strip().lower()

def _is_player_char(v: Villager) -> bool:
    return _norm_origin(v) == "player" and bool(v.get("owner", ""))

def _is_alive(v: Villager) -> bool:
    return v.get("alive", True) and int(v.get("hp", 0) or 0) > 0

def _normalize_id_list(raw):
    """
    childrenIds might be:
      - list[int]
      - JSON string like "[1,2,3]"
      - empty / None
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw if str(x).strip().isdigit()]
    if isinstance(raw, str) and raw.strip():
        s = raw.strip()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [int(x) for x in parsed if str(x).strip().isdigit()]
        except Exception:
            return []
    return []

def _demote_to_npc(v: Villager) -> None:
    v["origin"] = "npc"
    v["owner"] = ""

def _promote_to_player(v: Villager, owner: str) -> None:
    v["origin"] = "player"
    v["owner"] = owner or ""

def _find_children(parent: Villager, characters: list[Villager], id_map: dict[int, Villager]) -> list[Villager]:
    """
    Prefer explicit childrenIds, but fallback to scanning motherId/fatherId.
    """
    pid = int(parent.get("id", 0) or 0)

    child_ids = _normalize_id_list(parent.get("childrenIds", []))
    kids = []
    for cid in child_ids:
        c = id_map.get(int(cid))
        if c:
            kids.append(c)

    if not kids and pid > 0:
        for c in characters:
            if int(c.get("motherId", 0) or 0) == pid or int(c.get("fatherId", 0) or 0) == pid:
                kids.append(c)

    seen = set()
    out = []
    for k in kids:
        kid = int(k.get("id", 0) or 0)
        if kid and kid not in seen:
            seen.add(kid)
            out.append(k)
    return out


def _find_siblings(person: Villager, characters: list[Villager]) -> list[Villager]:
    """
    Siblings = share motherId OR fatherId (half-siblings included).
    """
    pid = int(person.get("id", 0) or 0)
    mid = int(person.get("motherId", 0) or 0)
    fid = int(person.get("fatherId", 0) or 0)

    if mid <= 0 and fid <= 0:
        return []

    sibs = []
    for c in characters:
        if int(c.get("id", 0) or 0) == pid:
            continue
        cm = int(c.get("motherId", 0) or 0)
        cf = int(c.get("fatherId", 0) or 0)

        if (mid > 0 and cm == mid) or (fid > 0 and cf == fid):
            sibs.append(c)

    seen = set()
    out = []
    for s in sibs:
        sid = int(s.get("id", 0) or 0)
        if sid and sid not in seen:
            seen.add(sid)
            out.append(s)
    return out


def _choose_heir(candidates: list[Villager], owner: str | None = None) -> Villager | None:
    """
    Pick ONE heir from alive candidates.
    """
    alive = []
    for c in candidates:
        if not c or not _is_alive(c):
            continue
        if owner:
            if _is_player_char(c) and (c.get("owner", "") != owner):
                continue
        alive.append(c)

    if not alive:
        return None

    def key(c):
        age = int(c.get("age", 0) or 0)
        lvl = int(c.get("level", 1) or 1)
        rep = int(c.get("rep", 0) or 0)
        cid = int(c.get("id", 0) or 0)
        is_adult = 1 if age > 16 else 0
        return (is_adult, age, lvl, rep, -cid)

    return sorted(alive, key=key, reverse=True)[0]

def enforce_one_player_per_owner(characters: list[Villager]) -> None:
    """
    Ensure each owner has exactly ONE 'player' character.
    """
    by_owner: dict[str, list[dict]] = {}
    for v in characters:
        if _is_player_char(v):
            by_owner.setdefault(v["owner"], []).append(v)

    for owner, group in by_owner.items():
        if len(group) <= 1:
            continue

        def key(v):
            alive = 1 if _is_alive(v) else 0
            age = int(v.get("age", 0) or 0)
            lvl = int(v.get("level", 1) or 1)
            rep = int(v.get("rep", 0) or 0)
            vid = int(v.get("id", 0) or 0)
            return (alive, lvl, age, rep, -vid)

        group_sorted = sorted(group, key=key, reverse=True)
        keep = group_sorted[0]

        for v in group_sorted[1:]:
            _demote_to_npc(v)
            if not v.get("last_action"):
                v["last_action"] = f"lost player status (duplicate owner {owner})"

def player_inheritance_phase(characters: list[Villager], current_day: int = 0) -> None:
    """
    If a player character dies:
      - promote ONE alive CHILD -> player, same owner
      - else promote ONE alive SIBLING -> player, same owner
      - demote dead player -> npc (owner cleared)
      - ensure owner has only one player char
    """
    id_map = {int(c.get("id", 0) or 0): c for c in characters}

    enforce_one_player_per_owner(characters)

    for parent in characters:
        if not _is_player_char(parent):
            continue
        if _is_alive(parent):
            continue

        owner = parent.get("owner", "")
        if not owner:
            continue

        has_alive_player = any(
            (_is_player_char(v) and v.get("owner") == owner and _is_alive(v) and v is not parent)
            for v in characters
        )
        if has_alive_player:
            _demote_to_npc(parent)
            continue

        heir = None
        heir_kind = None

        children = _find_children(parent, characters, id_map)
        heir = _choose_heir(children, owner=owner)
        heir_kind = "child"

        if not heir:
            siblings = _find_siblings(parent, characters)
            heir = _choose_heir(siblings, owner=owner)
            heir_kind = "sibling"

        if not heir:
            # No heir found - demote dead player so user can create new character.
            # Preserve the actual death cause (e.g. "dead (starvation -8 HP)")
            # and append the lineage-end note instead of overwriting it.
            _demote_to_npc(parent)
            death_cause = parent.get("last_action") or "dead"
            parent["last_action"] = f"{death_cause} / lineage ended (no heirs)"
            continue

        parent_name = parent.get("name", "Unknown")
        _demote_to_npc(parent)
        _promote_to_player(heir, owner)

        for v in characters:
            if v is heir:
                continue
            if _is_player_char(v) and v.get("owner") == owner:
                _demote_to_npc(v)

        note = f"inherited legacy of {parent_name} ({heir_kind})"
        if heir.get("last_action"):
            heir["last_action"] = f"{heir['last_action']} / {note}"
        else:
            heir["last_action"] = note


def consume_food_phase(characters: list[Villager], bank: Bank) -> dict[str, int]:
    """Drain the town's food stockpile and feed the adult population.

    When supply meets demand, each adult eats and their hunger drops. When
    supply falls short, eating is rationed proportionally AND a deficit
    hunger penalty is added on top — so a low stockpile both fails to feed
    AND actively raises hunger toward starvation.
    """
    if not isinstance(bank, dict):
        return {"need": 0, "available": 0, "fed": 0, "deficit": 0}

    stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})

    adults = sum(1 for v in characters if v.get("alive") and not is_child(v))
    kids = sum(1 for v in characters if v.get("alive") and is_child(v))
    need = adults * FOOD_PER_ADULT_PER_DAY + kids * FOOD_PER_CHILD_PER_DAY

    if get_building_level(bank, "granary") > 0:
        need = max(1, int(round(need * GRANARY_CONSUMPTION_MULT)))

    available = int(stock.get("food", 0) or 0)
    fed = min(available, need)
    stock["food"] = available - fed

    # Per-adult hunger reduction when fed. Calibrated so it roughly cancels
    # the typical daily hunger gain from "work" (+6-12), keeping a working
    # population at hunger equilibrium when food is plentiful. Granary boosts
    # this further (better distribution to the table).
    base_reduction = 11
    granary_lvl = get_building_level(bank, "granary")
    if granary_lvl > 0:
        base_reduction += 2 * granary_lvl

    fed_ratio = (fed / need) if need > 0 else 1.0
    hunger_reduction = int(round(base_reduction * fed_ratio))

    deficit = max(0, need - available)
    deficit_ratio = (deficit / need) if need > 0 else 0.0
    hunger_penalty = int(round(20 * deficit_ratio))

    for v in characters:
        if not v.get("alive") or is_child(v):
            continue
        h = int(v.get("hunger", 0) or 0)
        h = max(0, h - hunger_reduction)
        if hunger_penalty > 0:
            h = min(100, h + hunger_penalty)
        v["hunger"] = h

    return {"need": need, "available": available, "fed": fed, "deficit": deficit}


def simulate_one_day(characters: list[Villager], bank: Bank, current_day: int = 0) -> tuple[list[Villager], Bank, int, str | None, int, str | None]:
    """
    Simulate actions for one day for each villager in the list.
    
    Returns:
        (characters, bank, corruption_total, event_message, births_count, quest_message)
    """
    reset_id_from_characters(characters)
    weather_today = load_weather()
    coming_of_age_phase(characters, current_day=current_day)
    enforce_one_player_per_owner(characters)

    corruption_total = 0

    # 1) Daily individual phase
    # Process guards first so patrollers boost witness chance for any crimes
    # committed by other villagers later in the same tick.
    _GUARD_PRIORITY = {"Guard", "Captain", "Soldier", "Commander"}
    ordered = sorted(
        characters,
        key=lambda x: 0 if x.get("job") in _GUARD_PRIORITY else 1,
    )
    _DEATH_WORDS = ("died", "killed", "dead", "succumbed", "passed away", "murdered", "slain", "perished")
    for v in ordered:
        if v.get("hp", 0) <= 0 or not v.get("alive", True):
            v["hp"] = 0
            v["alive"] = False
            last = (v.get("last_action") or "").strip()
            if not last:
                v["last_action"] = "dead of unknown causes"
            elif not any(w in last.lower() for w in _DEATH_WORDS):
                # Action ran but didn't annotate death — preserve context
                v["last_action"] = f"died after: {last}"
            continue

        v["last_action"] = ""

        if is_child(v):
            v["job"] = "Child"
            v["hunger"] = 0
            continue

        action = choose_action(v, bank, weather=weather_today, all_characters=characters)
        v["last_action"] = action
        apply_action(v, action, bank, characters, weather=weather_today, current_day=current_day)

        hp_loss = apply_starvation_damage(v, bank)

        if not v.get("alive", True) and int(v.get("spouseId", 0) or 0) > 0 and not v.get("spouseId_at_death"):
            v["spouseId_at_death"] = int(v["spouseId"])

        if hp_loss:
            if v["alive"]:
                v["last_action"] = f"{v['last_action']} / starvation -{hp_loss} HP"
            else:
                v["last_action"] = f"dead (starvation -{hp_loss} HP)"

        stolen = maybe_corrupt_from_bank(v, bank)
        corruption_total += stolen

    # 1.35) Disease progression — HP drain, lethality rolls, recovery,
    # ambient new infections. Runs before food consumption so a starving
    # villager who also has plague can compound damage on the same day.
    try:
        from src.services.disease_service import daily_disease_phase
        daily_disease_phase(characters, bank, current_day)
    except Exception:
        pass

    # 1.4) Town-wide food consumption from the shared stockpile.
    # Runs after the action loop so a Farmer's daily harvest is on the shelf
    # before the village eats. Shortages bump hunger across the population,
    # which the next day's starvation pass will translate into HP loss.
    consume_food_phase(characters, bank)

    # 1.5) Passive MP regeneration (magic jobs regen more)
    for v in characters:
        if not v.get("alive", True) or is_child(v):
            continue
        job = v.get("job", "")
        if job in MAGIC_JOBS:
            v["mp"] = int(v.get("mp", 0) or 0) + rand_int(2, 5)
        elif job in MINOR_MAGIC_JOBS:
            v["mp"] = int(v.get("mp", 0) or 0) + rand_int(1, 3)
        else:
            # Non-magic: tiny regen (1 MP every ~3 days)
            if random.random() < 0.33:
                v["mp"] = int(v.get("mp", 0) or 0) + 1

    # 2) World phases (immigrants, spouses)
    characters, _added_count = maybe_add_immigrants(characters, bank)
    child_daily_phase(characters, current_day=current_day)
    births_count = spouse_daily_phase(characters, current_day=current_day, bank=bank)

    # 3) King assassination phase (king kills enemies + rivals may coup the king)
    king_assassination_phase(characters, bank=bank, current_day=current_day)
    rival_coup_phase(characters, bank=bank, current_day=current_day)

    # 3.25) Crime & justice — the King rules on any pending cases today.
    # No-ops when there are no pending cases or no sitting King.
    try:
        from src.services.justice_service import crime_trial_phase
        crime_trial_phase(characters, bank, current_day)
    except Exception:
        pass

    # 3.5) Player inheritance
    player_inheritance_phase(characters, current_day=current_day)

    # 4) Elder decay phase (70+ age penalties)
    elder_decay_phase(characters, current_day=current_day)

    # 5) Random world events (plague, famine, festival, etc.)
    event_message, _event_record = maybe_trigger_event(characters, bank, current_day)

    # 6) Quest system (every 2 years)
    quest_message, _quest_record = maybe_trigger_quest(characters, bank, current_day)

    # 7) Achievement check phase
    achievement_check_phase(characters, current_day=current_day)

    # 8) Log history LAST
    for v in characters:
        append_action_history(v)

    return characters, bank, corruption_total, event_message, births_count, quest_message
