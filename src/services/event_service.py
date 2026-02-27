"""
Event Service - Random world events that impact villagers and the village.

Event Types:
- PLAGUE: Reduces health, can cause deaths
- FAMINE: Reduces food/resources, increases hunger
- FESTIVAL: Boosts happiness/reputation, may cause bonus births
- INVASION: Random attacks, casualties
- GOOD_HARVEST: Bonus food/coins
- BLESSING: Health boost for villagers
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import TYPE_CHECKING

from world_utils import clamp, rand_int
from buildings import get_building_level

if TYPE_CHECKING:
    from src.models.villager import Villager
    from src.models.bank import Bank

# Event configuration
EVENT_CHANCE_PER_DAY = 0.12  # 12% chance of an event each day
EVENT_COOLDOWN_DAYS = 45     # Minimum days between events

# Event type weights (higher = more likely)
EVENT_WEIGHTS = {
    "PLAGUE": 8,
    "FAMINE": 10,
    "FESTIVAL": 20,
    "INVASION": 12,
    "GOOD_HARVEST": 25,
    "BLESSING": 15,
}

# In-memory event history (will be reset on server restart)
# For persistent storage, this should be moved to database
_event_history: list[dict] = []
_last_event_day: int = -999


def get_event_history() -> list[dict]:
    """Get the event history list."""
    return _event_history.copy()


def clear_event_history() -> None:
    """Clear event history."""
    global _event_history, _last_event_day
    _event_history = []
    _last_event_day = -999


def _record_event(event_type: str, day: int, details: str, affected_count: int = 0) -> dict:
    """Record an event in history."""
    global _last_event_day
    event = {
        "type": event_type,
        "day": day,
        "details": details,
        "affected_count": affected_count,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _event_history.append(event)
    _last_event_day = day
    
    # Keep only last 100 events
    if len(_event_history) > 100:
        _event_history.pop(0)
    
    return event


def _pick_event_type() -> str:
    """Pick a random event type based on weights."""
    total = sum(EVENT_WEIGHTS.values())
    r = random.random() * total
    cumulative = 0
    for event_type, weight in EVENT_WEIGHTS.items():
        cumulative += weight
        if r <= cumulative:
            return event_type
    return "GOOD_HARVEST"  # fallback


def _apply_plague(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    PLAGUE event: Reduces health of villagers, can cause deaths.
    Clinic building reduces impact.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Plague came but found no one to afflict.", 0
    
    # Clinic reduces plague severity
    clinic_level = get_building_level(bank, "clinic") if bank else 0
    severity_mod = max(0.3, 1.0 - clinic_level * 0.2)
    
    affected = 0
    deaths = 0
    
    for v in alive:
        # 40-70% of villagers affected
        if random.random() > 0.55:
            continue
        
        affected += 1
        hp = int(v.get("hp", 100) or 100)
        
        # Damage: 15-40 HP, reduced by clinic
        damage = int(rand_int(15, 40) * severity_mod)
        new_hp = max(0, hp - damage)
        v["hp"] = new_hp
        
        if new_hp <= 0:
            v["alive"] = False
            v["death_day"] = current_day
            v["last_action"] = "died from plague"
            deaths += 1
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / suffered plague (-{damage} HP)"
            else:
                v["last_action"] = f"suffered plague (-{damage} HP)"
    
    if deaths > 0:
        msg = f"☠️ PLAGUE struck the village! {affected} villagers afflicted, {deaths} died."
    else:
        msg = f"🤒 PLAGUE spread through the village! {affected} villagers fell ill."
    
    return msg, affected


def _apply_famine(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    FAMINE event: Increases hunger, drains village resources.
    Granary reduces impact.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Famine came but no one was around.", 0
    
    # Granary reduces famine severity
    granary_level = get_building_level(bank, "granary") if bank else 0
    severity_mod = max(0.3, 1.0 - granary_level * 0.2)
    
    affected = 0
    
    for v in alive:
        # 60-80% of villagers affected
        if random.random() > 0.70:
            continue
        
        affected += 1
        hunger = int(v.get("hunger", 0) or 0)
        
        # Increase hunger by 15-30
        hunger_increase = int(rand_int(15, 30) * severity_mod)
        v["hunger"] = clamp(hunger + hunger_increase, 0, 100)
        
        if v.get("last_action"):
            v["last_action"] = f"{v['last_action']} / starving (hunger +{hunger_increase})"
        else:
            v["last_action"] = f"starving from famine (hunger +{hunger_increase})"
    
    # Also drain some village coins
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        drain = int(balance * random.uniform(0.05, 0.15) * severity_mod)
        bank["balance"] = max(0, balance - drain)
        msg = f"🌾 FAMINE struck! {affected} villagers are starving. Village lost {drain} coins to emergency measures."
    else:
        msg = f"🌾 FAMINE struck! {affected} villagers are starving."
    
    return msg, affected


def _apply_festival(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    FESTIVAL event: Boosts reputation, may trigger marriages/births.
    Temple and Tavern boost effects.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Festival planned but no one attended.", 0
    
    # Temple and Tavern boost festival effects
    temple_level = get_building_level(bank, "temple") if bank else 0
    tavern_level = get_building_level(bank, "tavern") if bank else 0
    bonus_mod = 1.0 + (temple_level + tavern_level) * 0.15
    
    affected = 0
    
    for v in alive:
        # Everyone joins the festival!
        affected += 1
        
        # Rep boost: 2-8 points
        rep = int(v.get("rep", 0) or 0)
        rep_boost = int(rand_int(2, 8) * bonus_mod)
        v["rep"] = clamp(rep + rep_boost, -100, 100)
        
        # Small HP restore
        hp = int(v.get("hp", 100) or 100)
        max_hp = int(v.get("max_hp", 200) or 200)
        hp_restore = int(rand_int(5, 15) * bonus_mod)
        v["hp"] = min(hp + hp_restore, max_hp)
        
        # Reduce hunger
        hunger = int(v.get("hunger", 0) or 0)
        hunger_reduce = int(rand_int(10, 20) * bonus_mod)
        v["hunger"] = max(0, hunger - hunger_reduce)
        
        if v.get("last_action"):
            v["last_action"] = f"{v['last_action']} / celebrated festival (rep +{rep_boost})"
        else:
            v["last_action"] = f"celebrated festival (rep +{rep_boost})"
    
    # Village gains some coins from festival
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        gain = int(rand_int(50, 150) * bonus_mod)
        bank["balance"] = balance + gain
        msg = f"🎉 FESTIVAL celebrated! Village gained {gain} coins. All {affected} villagers are joyful!"
    else:
        msg = f"🎉 FESTIVAL celebrated! All {affected} villagers are joyful!"
    
    return msg, affected


def _apply_invasion(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    INVASION event: Random attacks cause casualties.
    Barracks and Walls reduce impact.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Invaders came but found an empty village.", 0
    
    # Barracks and Walls reduce invasion damage
    barracks_level = get_building_level(bank, "barracks") if bank else 0
    walls_level = get_building_level(bank, "walls") if bank else 0
    defense_mod = max(0.2, 1.0 - (barracks_level * 0.15 + walls_level * 0.2))
    
    affected = 0
    deaths = 0
    
    # Military jobs get attack bonuses
    military_jobs = {"Soldier", "Commander", "Guard", "Captain", "Ranger", "Archer", "Scout"}
    
    for v in alive:
        # 30-50% of villagers affected
        if random.random() > 0.40:
            continue
        
        affected += 1
        hp = int(v.get("hp", 100) or 100)
        defense = int(v.get("def", 10) or 10)
        job = v.get("job", "")
        
        # Military jobs take less damage
        job_mod = 0.5 if job in military_jobs else 1.0
        
        # Damage: 20-50 HP, reduced by defense and buildings
        base_damage = rand_int(20, 50)
        damage = int(max(5, (base_damage - defense * 0.3) * defense_mod * job_mod))
        new_hp = max(0, hp - damage)
        v["hp"] = new_hp
        
        if new_hp <= 0:
            v["alive"] = False
            v["death_day"] = current_day
            v["last_action"] = "killed in invasion"
            deaths += 1
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / wounded in invasion (-{damage} HP)"
            else:
                v["last_action"] = f"wounded in invasion (-{damage} HP)"
    
    # Invaders also steal some coins
    coins_lost = 0
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        coins_lost = int(balance * random.uniform(0.1, 0.25) * defense_mod)
        bank["balance"] = max(0, balance - coins_lost)
    
    if deaths > 0:
        msg = f"⚔️ INVASION! Raiders attacked! {deaths} villagers killed, {affected - deaths} wounded. Lost {coins_lost} coins."
    else:
        msg = f"⚔️ INVASION repelled! {affected} villagers wounded. Lost {coins_lost} coins."
    
    return msg, affected


def _apply_good_harvest(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    GOOD_HARVEST event: Bonus food and coins for the village.
    Granary and Marketplace boost effects.
    """
    alive = [c for c in characters if c.get("alive", True)]
    
    # Granary and Market boost harvest
    granary_level = get_building_level(bank, "granary") if bank else 0
    market_level = get_building_level(bank, "market") if bank else 0
    bonus_mod = 1.0 + (granary_level + market_level) * 0.2
    
    affected = 0
    
    # Farmers and nature jobs benefit more
    nature_jobs = {"Farmer", "Shepherd", "Fisher", "Hunter", "Herbalist", "Beekeeper", "Forester"}
    
    for v in alive:
        affected += 1
        job = v.get("job", "")
        
        # Reduce hunger significantly
        hunger = int(v.get("hunger", 0) or 0)
        hunger_reduce = rand_int(20, 35)
        v["hunger"] = max(0, hunger - hunger_reduce)
        
        # Nature workers get bonus coins
        if job in nature_jobs:
            coins = int(v.get("coins", 0) or 0)
            coin_bonus = int(rand_int(10, 30) * bonus_mod)
            v["coins"] = coins + coin_bonus
            
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / good harvest (+{coin_bonus} coins)"
            else:
                v["last_action"] = f"good harvest (+{coin_bonus} coins)"
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / well fed from harvest"
            else:
                v["last_action"] = "well fed from good harvest"
    
    # Village treasury gets bonus
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        gain = int(rand_int(100, 300) * bonus_mod)
        bank["balance"] = balance + gain
        msg = f"🌻 GOOD HARVEST! Village gained {gain} coins. All {affected} villagers are well fed!"
    else:
        msg = f"🌻 GOOD HARVEST! All {affected} villagers are well fed!"
    
    return msg, affected


def _apply_blessing(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    BLESSING event: Health boost for all villagers.
    Temple boosts effects.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Divine blessing descended but found no one.", 0
    
    # Temple boosts blessing
    temple_level = get_building_level(bank, "temple") if bank else 0
    bonus_mod = 1.0 + temple_level * 0.25
    
    affected = 0
    
    for v in alive:
        affected += 1
        
        hp = int(v.get("hp", 100) or 100)
        max_hp = int(v.get("max_hp", 200) or 200)
        
        # Heal 25-50 HP
        heal = int(rand_int(25, 50) * bonus_mod)
        v["hp"] = min(hp + heal, max_hp)
        
        # Small stat boost
        if random.random() < 0.3:
            stat = random.choice(["atk", "def", "int"])
            current = int(v.get(stat, 10) or 10)
            boost = rand_int(1, 3)
            v[stat] = current + boost
            
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / blessed (+{heal} HP, +{boost} {stat})"
            else:
                v["last_action"] = f"blessed (+{heal} HP, +{boost} {stat})"
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / blessed (+{heal} HP)"
            else:
                v["last_action"] = f"blessed (+{heal} HP)"
    
    msg = f"✨ DIVINE BLESSING! All {affected} villagers received healing and blessings!"
    
    return msg, affected


def maybe_trigger_event(
    characters: list[Villager],
    bank: Bank | None,
    current_day: int
) -> tuple[str | None, dict | None]:
    """
    Check if a random event should occur and apply it.
    
    Returns:
        (message, event_record) if event occurred
        (None, None) if no event
    """
    global _last_event_day
    
    # Check cooldown
    if current_day - _last_event_day < EVENT_COOLDOWN_DAYS:
        return None, None
    
    # Random chance check
    if random.random() > EVENT_CHANCE_PER_DAY:
        return None, None
    
    # Pick and apply event
    event_type = _pick_event_type()
    
    event_handlers = {
        "PLAGUE": _apply_plague,
        "FAMINE": _apply_famine,
        "FESTIVAL": _apply_festival,
        "INVASION": _apply_invasion,
        "GOOD_HARVEST": _apply_good_harvest,
        "BLESSING": _apply_blessing,
    }
    
    handler = event_handlers.get(event_type)
    if not handler:
        return None, None
    
    message, affected = handler(characters, bank, current_day)
    
    # Record the event
    event_record = _record_event(event_type, current_day, message, affected)
    
    return message, event_record
