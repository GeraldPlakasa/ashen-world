from __future__ import annotations

import json
import random

from config import (
    JOBS_NO_ROYAL,
    MAGIC_JOBS,
    MINOR_MAGIC_JOBS,
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
    
    - Age 70-79: HP decay 0-1, 2% stat decay chance, ~1.8% yearly death
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
            # Early elder: very gentle decay
            hp_decay = rand_int(0, 1)
            stat_decay_chance = 0.02  # 2% chance per day
            death_chance = 0.0005  # 0.05% per day (~1.8% per year)
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
    Base 3% chance, tavern increases by 2% per level.
    """
    tavern_lvl = get_building_level(bank, "tavern")

    # Lower base chance for controlled population growth
    base_chance = 0.03 + 0.02 * tavern_lvl  # 3% base, +2% per tavern level
    chance = max(0.02, min(0.15, base_chance))  # 2-15% range

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
            # No heir found - demote dead player so user can create new character
            _demote_to_npc(parent)
            parent["last_action"] = f"lineage ended (no heirs)"
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
    for v in characters:
        if v.get("hp", 0) <= 0 or not v.get("alive", True):
            v["hp"] = 0
            v["alive"] = False
            if not v.get("last_action"):
                v["last_action"] = "dead"
            continue

        v["last_action"] = ""

        if is_child(v):
            v["job"] = "Child"
            v["hunger"] = 0
            continue

        action = choose_action(v, bank, weather=weather_today)
        v["last_action"] = action
        apply_action(v, action, bank, characters, weather=weather_today)

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
    births_count = spouse_daily_phase(characters, current_day=current_day)

    # 3) King assassination phase
    king_assassination_phase(characters, bank=bank, current_day=current_day)

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
