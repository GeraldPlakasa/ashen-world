"""
Event Service - Random world events that impact villagers and the village.

Event Types:
- PLAGUE: Reduces health, can cause deaths
- FAMINE: Reduces food/resources, increases hunger
- FESTIVAL: Boosts happiness/reputation, may cause bonus births
- INVASION: Random attacks, casualties
- GOOD_HARVEST: Bonus food/coins
- BLESSING: Health boost for villagers

Event Timing:
- Events occur ONCE per year on a RANDOM day
- At the start of each year, a random day (1 to DAYS_PER_YEAR) is selected
- When that day arrives, the event triggers
- This creates anticipation and strategic building of mitigations
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import TYPE_CHECKING

from config import DAYS_PER_YEAR
from src.utils.world_utils import clamp, rand_int
from src.services.building_service import get_building_level
from src.services.achievement_service import trigger_survivor_achievement

if TYPE_CHECKING:
    from src.models.villager import Villager
    from src.models.bank import Bank

# Event type weights (higher = more likely)
EVENT_WEIGHTS = {
    "PLAGUE": 8,
    "FAMINE": 10,
    "FESTIVAL": 20,
    "INVASION": 12,
    "GOOD_HARVEST": 25,
    "BLESSING": 15,
    "WINDFALL": 12,     # Positive: treasure discovery
    "STORM": 10,        # Negative: natural disaster
}

# Event history now stored in SQLite (persistent across restarts)
from src.repositories.base import db_conn, init_db


def get_event_history(limit: int = 200) -> list[dict]:
    """Get event history from database."""
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT event_type as type, day, year, details, affected_count, created_at as timestamp "
            "FROM event_history ORDER BY id DESC LIMIT ?;",
            (limit,),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def clear_event_history() -> None:
    """Clear all event history."""
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM event_history;")


def _record_event(event_type: str, day: int, details: str, affected_count: int = 0) -> dict:
    """Record an event in database."""
    year = ((day - 1) // DAYS_PER_YEAR) + 1

    event = {
        "type": event_type,
        "day": day,
        "year": year,
        "details": details,
        "affected_count": affected_count,
    }

    init_db()
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO event_history (event_type, day, year, details, affected_count) "
            "VALUES (?, ?, ?, ?, ?);",
            (event_type, day, year, details, affected_count),
        )

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
            # Survivor achievement for surviving plague
            trigger_survivor_achievement(v)
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
        
        # Small HP restore (no cap)
        hp = int(v.get("hp", 100) or 100)
        hp_restore = int(rand_int(5, 15) * bonus_mod)
        v["hp"] = hp + hp_restore
        
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
        
        # Heal 25-50 HP (no cap)
        heal = int(rand_int(25, 50) * bonus_mod)
        v["hp"] = hp + heal
        
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


def _apply_windfall(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    WINDFALL event: A traveling merchant or hidden treasure brings fortune.
    Market boosts effects.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Fortune arrived but no one claimed it.", 0
    
    # Market boosts windfall
    market_level = get_building_level(bank, "market") if bank else 0
    bonus_mod = 1.0 + market_level * 0.3
    
    affected = 0
    total_coins = 0
    
    # Pick lucky villagers (30-50% of population)
    lucky_ones = [v for v in alive if random.random() < 0.40]
    
    for v in lucky_ones:
        affected += 1
        
        # Coin bonus: 20-60 coins per villager
        coins = int(v.get("coins", 0) or 0)
        coin_bonus = int(rand_int(20, 60) * bonus_mod)
        v["coins"] = coins + coin_bonus
        total_coins += coin_bonus
        
        # Small chance for stat boost
        if random.random() < 0.15:
            stat = random.choice(["atk", "def", "int"])
            current = int(v.get(stat, 10) or 10)
            boost = rand_int(1, 2)
            v[stat] = current + boost
            
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / found treasure (+{coin_bonus} coins, +{boost} {stat})"
            else:
                v["last_action"] = f"found treasure (+{coin_bonus} coins, +{boost} {stat})"
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / found treasure (+{coin_bonus} coins)"
            else:
                v["last_action"] = f"found treasure (+{coin_bonus} coins)"
    
    # Village treasury also gets bonus
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        treasury_gain = int(rand_int(200, 500) * bonus_mod)
        bank["balance"] = balance + treasury_gain
        msg = f"💰 WINDFALL! A merchant caravan brought riches! {affected} villagers found treasure. Treasury gained {treasury_gain} coins!"
    else:
        msg = f"💰 WINDFALL! {affected} villagers found treasure worth {total_coins} coins total!"
    
    return msg, affected


def _apply_storm(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    STORM event: A terrible storm damages buildings and injures villagers.
    Walls reduce impact.
    """
    alive = [c for c in characters if c.get("alive", True)]
    if not alive:
        return "Storm passed over an empty village.", 0
    
    # Walls reduce storm damage
    walls_level = get_building_level(bank, "walls") if bank else 0
    severity_mod = max(0.4, 1.0 - walls_level * 0.2)
    
    affected = 0
    deaths = 0
    
    for v in alive:
        # 40-60% of villagers affected
        if random.random() > 0.50:
            continue
        
        affected += 1
        hp = int(v.get("hp", 100) or 100)
        
        # Damage: 10-30 HP from debris/lightning
        damage = int(rand_int(10, 30) * severity_mod)
        new_hp = max(0, hp - damage)
        v["hp"] = new_hp
        
        if new_hp <= 0:
            v["alive"] = False
            v["death_day"] = current_day
            v["last_action"] = "killed by storm"
            deaths += 1
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / injured in storm (-{damage} HP)"
            else:
                v["last_action"] = f"injured in storm (-{damage} HP)"
    
    # Storm damages buildings and treasury
    coins_lost = 0
    building_damage = ""
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        coins_lost = int(balance * random.uniform(0.05, 0.15) * severity_mod)
        bank["balance"] = max(0, balance - coins_lost)
        
        # Damage random buildings
        buildings = bank.get("buildings", {})
        if buildings:
            damaged_buildings = []
            for bname, bdata in buildings.items():
                if random.random() < 0.3 * severity_mod:
                    health = bdata.get("health", 100)
                    damage_pct = rand_int(10, 25)
                    bdata["health"] = max(0, health - damage_pct)
                    damaged_buildings.append(bname)
            if damaged_buildings:
                building_damage = f" Buildings damaged: {', '.join(damaged_buildings)}."
    
    if deaths > 0:
        msg = f"🌪️ TERRIBLE STORM! {deaths} villagers killed, {affected - deaths} injured. Lost {coins_lost} coins to repairs.{building_damage}"
    else:
        msg = f"🌪️ STORM struck the village! {affected} villagers injured. Lost {coins_lost} coins to repairs.{building_damage}"
    
    return msg, affected


def _get_current_year(current_day: int) -> int:
    """Calculate the current year from total day (1-indexed)."""
    return ((current_day - 1) // DAYS_PER_YEAR) + 1


def _get_day_in_year(current_day: int) -> int:
    """Calculate the day within the current year (0-indexed, 0 to DAYS_PER_YEAR-1)."""
    return (current_day - 1) % DAYS_PER_YEAR


def maybe_trigger_event(
    characters: list[Villager],
    bank: Bank | None,
    current_day: int
) -> tuple[str | None, dict | None]:
    """
    Check if a random event should occur and apply it.
    
    Event Timing Logic (Yearly-based):
    - Each year has ONE event on a RANDOM day
    - Bank stores: last_event_year, event_day_for_year
    - At year start (day 0 of year), pick a random day for the event
    - When current day matches event_day_for_year, trigger the event
    
    Returns:
        (message, event_record) if event occurred
        (None, None) if no event
    """
    if bank is None:
        return None, None
    
    current_year = _get_current_year(current_day)
    day_in_year = _get_day_in_year(current_day)
    
    # Get tracking info from bank
    last_event_year = bank.get("last_event_year_tracking") or 0
    event_day_for_year = bank.get("event_day_for_year")
    
    # Check if we're in a new year that needs event scheduling
    if last_event_year < current_year:
        # New year! Pick a random day for this year's event (1 to DAYS_PER_YEAR-1)
        # We use 1 to DAYS_PER_YEAR-1 to avoid day 0 (year transition day)
        event_day_for_year = random.randint(1, DAYS_PER_YEAR - 1)
        bank["event_day_for_year"] = event_day_for_year
        bank["last_event_year_tracking"] = current_year
        bank["event_triggered_this_year"] = False
    
    # Check if event already triggered this year
    if bank.get("event_triggered_this_year", False):
        return None, None
    
    # Check if today is the event day
    if day_in_year != event_day_for_year:
        return None, None
    
    # Today is the event day! Trigger the event
    bank["event_triggered_this_year"] = True
    
    # Pick and apply event
    event_type = _pick_event_type()
    
    event_handlers = {
        "PLAGUE": _apply_plague,
        "FAMINE": _apply_famine,
        "FESTIVAL": _apply_festival,
        "INVASION": _apply_invasion,
        "GOOD_HARVEST": _apply_good_harvest,
        "BLESSING": _apply_blessing,
        "WINDFALL": _apply_windfall,
        "STORM": _apply_storm,
    }
    
    handler = event_handlers.get(event_type)
    if not handler:
        return None, None
    
    message, affected = handler(characters, bank, current_day)
    
    # Record the event
    event_record = _record_event(event_type, current_day, message, affected)
    
    return message, event_record
