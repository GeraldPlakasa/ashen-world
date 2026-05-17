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
    "ANCIENT_TOMB": 1,  # Very rare: explorers unearth 1-2 artifacts (Phase 7)
    "TRADE_CARAVAN": 2, # Rare: a wandering merchant offers an artifact (Phase 7)
}

# Event history now stored in SQLite (persistent across restarts)
from src.repositories.base import db_conn, init_db


def get_event_history(limit: int = 200) -> list[dict]:
    """Get event history from database."""
    init_db()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT event_type as type, day, year, details, affected_count, COALESCE(king_name, '') as king_name, created_at as timestamp "
            "FROM event_history ORDER BY id DESC LIMIT ?;",
            (limit,),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def clear_event_history() -> None:
    """Clear all event history."""
    init_db()
    with db_conn() as conn:
        conn.execute("DELETE FROM event_history;")


def _record_event(event_type: str, day: int, details: str, affected_count: int = 0, king_name: str = "") -> dict:
    """Record an event in database."""
    year = ((day - 1) // DAYS_PER_YEAR) + 1

    event = {
        "type": event_type,
        "day": day,
        "year": year,
        "details": details,
        "affected_count": affected_count,
        "king_name": king_name,
    }

    init_db()
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO event_history (event_type, day, year, details, affected_count, king_name) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            (event_type, day, year, details, affected_count, king_name),
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
        
        # Healers/Clerics resist plague better (magical healing)
        job = v.get("job", "")
        plague_resist = 1.0
        if job in ("Cleric", "Healer", "Priest", "Herbalist"):
            plague_resist = 0.5
            mp = int(v.get("mp", 0) or 0)
            if mp > 0:
                v["mp"] = max(0, mp - rand_int(5, 15))  # Spend MP healing self
                plague_resist *= 0.7

        # Damage: 15-40 HP, reduced by clinic and magic resistance
        damage = int(rand_int(15, 40) * severity_mod * plague_resist)
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
    
    # Drain coins AND the food stockpile — a famine should empty larders.
    food_drained = 0
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        drain = int(balance * random.uniform(0.05, 0.15) * severity_mod)
        bank["balance"] = max(0, balance - drain)

        stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
        food_now = int(stock.get("food", 0) or 0)
        food_drained = int(food_now * random.uniform(0.30, 0.55) * severity_mod)
        stock["food"] = max(0, food_now - food_drained)

        msg = (
            f"🌾 FAMINE struck! {affected} villagers are starving. "
            f"Village lost {drain} coins and {food_drained} food to emergency measures."
        )
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
        v["rep"] = rep + rep_boost
        
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
    military_jobs = {"Soldier", "Commander", "Guard", "Captain", "Scout"}
    from config import MAGIC_JOBS
    
    for v in alive:
        # 30-50% of villagers affected
        if random.random() > 0.40:
            continue
        
        affected += 1
        hp = int(v.get("hp", 100) or 100)
        defense = int(v.get("def", 10) or 10)
        job = v.get("job", "")
        
        # Military and magic jobs take less damage (they fight back)
        if job in military_jobs:
            job_mod = 0.5
        elif job in MAGIC_JOBS:
            job_mod = 0.55
            # Magic users spend MP defending
            mp = int(v.get("mp", 0) or 0)
            if mp > 0:
                mp_cost = min(mp, rand_int(10, 25))
                v["mp"] = mp - mp_cost
                job_mod *= 0.7  # Extra protection from spells
        else:
            job_mod = 1.0
        
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
    
    # Village treasury and the food stockpile both gain.
    food_gain = 0
    if bank:
        balance = int(bank.get("balance", 0) or 0)
        gain = int(rand_int(100, 300) * bonus_mod)
        bank["balance"] = balance + gain

        stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
        food_gain = int(rand_int(200, 400) * bonus_mod)
        stock["food"] = int(stock.get("food", 0) or 0) + food_gain

        msg = (
            f"🌻 GOOD HARVEST! Village gained {gain} coins and {food_gain} food. "
            f"All {affected} villagers are well fed!"
        )
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
        
        # MP restoration from divine blessing
        mp_gain = int(rand_int(10, 25) * bonus_mod)
        v["mp"] = int(v.get("mp", 0) or 0) + mp_gain

        # Small stat boost
        if random.random() < 0.3:
            stat = random.choice(["atk", "def", "int"])
            current = int(v.get(stat, 10) or 10)
            boost = rand_int(1, 3)
            v[stat] = current + boost
            
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / blessed (+{heal} HP, +{mp_gain} MP, +{boost} {stat})"
            else:
                v["last_action"] = f"blessed (+{heal} HP, +{mp_gain} MP, +{boost} {stat})"
        else:
            if v.get("last_action"):
                v["last_action"] = f"{v['last_action']} / blessed (+{heal} HP, +{mp_gain} MP)"
            else:
                v["last_action"] = f"blessed (+{heal} HP, +{mp_gain} MP)"
    
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


def _apply_ancient_tomb(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    ANCIENT_TOMB event (Phase 7): explorers stumble upon a sealed tomb.
    1-3 of the most-respected alive villagers each take home a non-legendary
    artifact. Library boosts the count by interpreting the runes.
    """
    alive = [c for c in characters if c.get("alive", True) and not _is_child_safe(c)]
    if not alive:
        return "An old tomb was uncovered, but no one came forth to claim its contents.", 0

    # Library helps the village identify and recover more items, but the
    # tomb stays a stingy patron — at most a couple of artifacts.
    library_level = get_building_level(bank, "library") if bank else 0
    base_min, base_max = 1, 1
    if library_level >= 2:
        base_max = 2
    if library_level >= 3:
        base_min = 1

    count = rand_int(base_min, base_max)
    # Pick top-rep recipients (ties broken by random order).
    pool = sorted(alive, key=lambda c: (int(c.get("rep", 0) or 0), random.random()), reverse=True)
    recipients = pool[:count]
    if not recipients:
        return "An old tomb was uncovered, but no one came forth to claim its contents.", 0

    try:
        from src.services import artifact_service
        from src.repositories import artifact_repo
        from src.services.chronicle_service import _safe_record, _yd, _actor
    except Exception:
        return "An old tomb was uncovered, but its contents slipped away.", 0

    # Tomb rarity: lots of dust and pottery, only rarely a true relic.
    tomb_rarity_weights = {"common": 0.55, "uncommon": 0.30, "rare": 0.13, "legendary": 0.02}

    awarded_names = []
    for v in recipients:
        rarity = artifact_service._pick_weighted(tomb_rarity_weights)
        candidates = [t for t in artifact_service.list_templates() if t.get("rarity") == rarity]
        if not candidates:
            candidates = artifact_service.list_templates()
        if not candidates:
            continue
        template = random.choice(candidates)
        recipient_id = int(v.get("id", 0) or 0)
        if recipient_id <= 0:
            continue
        try:
            artifact_id = artifact_repo.create_artifact(
                slug=template["slug"],
                owner_id=recipient_id,
                acquired_day=int(current_day or 0),
                acquired_via="event:ancient_tomb",
                forged_history=[
                    {
                        "owner_id": recipient_id,
                        "owner_name": (v.get("name") or "").strip(),
                        "day": int(current_day or 0),
                        "event": "acquired",
                        "via": "claimed from an ancient tomb",
                    }
                ],
            )
        except Exception:
            continue
        equipped = artifact_service.auto_equip_if_better(v, artifact_id, template)
        awarded_names.append(v.get("name", "?"))

        # Per-find chronicle entry — important when legendary, otherwise modest.
        try:
            year, _ = _yd(current_day)
            r_name = template.get("name", "an artifact")
            r_rar = template.get("rarity", "common")
            headline = f"{v.get('name','?')} draws the {r_name} from the tomb"
            body = f"Out of the dust, the {r_name} found a new bearer."
            if equipped:
                body = f"{body} They wear it now."
            importance = 5 if r_rar == "legendary" else 4 if r_rar == "rare" else 3
            _safe_record(
                day=current_day,
                year=year,
                category="magic",
                headline=headline,
                body=body,
                actors=[_actor(v)],
                importance=importance,
            )
        except Exception:
            pass

        # Action log on the recipient.
        v["last_action"] = f"unearthed the {template.get('name','an artifact')} from the tomb"

    if not awarded_names:
        return "A tomb was opened, but the seals proved too treacherous.", 0

    msg = f"⚱️ ANCIENT TOMB! {len(awarded_names)} villagers claimed relics: {', '.join(awarded_names[:3])}{'…' if len(awarded_names) > 3 else ''}"
    return msg, len(awarded_names)


def _apply_trade_caravan(characters: list[Villager], bank: Bank | None, current_day: int) -> tuple[str, int]:
    """
    TRADE_CARAVAN event (Phase 7): a merchant arrives bearing an artifact.
    The reigning King may spend treasury to acquire it. If there's no King
    or the treasury is too lean, the caravan moves on.

    Cost / rarity tiers:
        common:    300 coins
        uncommon:  900 coins
        rare:    2,500 coins
        legendary: 8,000 coins (very rarely offered)
    """
    if bank is None:
        return "A merchant caravan arrived but found no one to deal with.", 0

    # Find the reigning King.
    king = next(
        (c for c in characters
         if c.get("alive", True) and c.get("job") == "King"),
        None,
    )

    treasury = int(bank.get("balance", 0) or 0)

    # Roll the offered artifact's rarity (legendary very rare).
    try:
        from src.services import artifact_service
        from src.repositories import artifact_repo
        from src.services.chronicle_service import _safe_record, _yd, _actor
    except Exception:
        return "A merchant caravan passed through, but the trade fell apart.", 0

    rarity_weights = {"common": 0.65, "uncommon": 0.27, "rare": 0.07, "legendary": 0.01}
    rarity = artifact_service._pick_weighted(rarity_weights)
    cost = {"common": 600, "uncommon": 1800, "rare": 5000, "legendary": 15000}.get(rarity, 600)

    # Market reduces price.
    market_level = get_building_level(bank, "market") if bank else 0
    if market_level > 0:
        cost = int(cost * max(0.7, 1.0 - 0.1 * market_level))

    if king is None:
        msg = (
            f"⚖️ TRADE CARAVAN: a merchant offered a {rarity} artifact for {cost} coins, "
            f"but the village had no King to seal the deal."
        )
        return msg, 0

    if treasury < cost:
        msg = (
            f"⚖️ TRADE CARAVAN: a merchant offered a {rarity} artifact for {cost} coins, "
            f"but the treasury was too lean ({treasury}). The King turned them away."
        )
        return msg, 0

    candidates = [t for t in artifact_service.list_templates()
                  if t.get("rarity") == rarity
                  and (t.get("binding") or "none") != "soulbound"]
    if not candidates:
        return f"A merchant offered a {rarity} artifact, but couldn't agree on terms.", 0
    template = random.choice(candidates)

    bank["balance"] = treasury - cost

    king_id = int(king.get("id", 0) or 0)
    artifact_id = artifact_repo.create_artifact(
        slug=template["slug"],
        owner_id=king_id,
        acquired_day=int(current_day or 0),
        acquired_via=f"trade_caravan:{rarity}",
        forged_history=[
            {
                "owner_id": king_id,
                "owner_name": (king.get("name") or "").strip(),
                "day": int(current_day or 0),
                "event": "acquired",
                "via": f"purchased from a trade caravan for {cost} coins",
            }
        ],
    )
    equipped = artifact_service.auto_equip_if_better(king, artifact_id, template)

    # Chronicle entry.
    try:
        year, _ = _yd(current_day)
        body_pieces = [
            f"A merchant caravan rolled into the village. King {king.get('name','?')} "
            f"paid {cost} coins from the treasury and took the {template.get('name')}."
        ]
        if equipped:
            body_pieces.append("They wear it now.")
        importance = 5 if rarity == "legendary" else 4 if rarity == "rare" else 3
        _safe_record(
            day=current_day,
            year=year,
            category="economy",
            headline=f"King {king.get('name','?')} buys the {template.get('name','artifact')}",
            body=" ".join(body_pieces),
            actors=[_actor(king)],
            importance=importance,
        )
    except Exception:
        pass

    msg = (
        f"⚖️ TRADE CARAVAN: King {king.get('name','?')} purchased the "
        f"{template.get('name','artifact')} ({rarity}) for {cost} coins."
    )
    return msg, 1


def _is_child_safe(c: dict) -> bool:
    try:
        from config import CHILD_MAX_AGE
        return int(c.get("age", 0) or 0) <= CHILD_MAX_AGE
    except Exception:
        return False


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

    # DB-level guard: check if an event was already recorded for this year
    # (protects against duplicate sim processes, e.g. Flask debug reloader)
    try:
        init_db()
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM event_history WHERE year = ?;",
                (current_year,),
            ).fetchone()[0]
            if existing > 0:
                bank["event_triggered_this_year"] = True
                return None, None
    except Exception:
        pass  # DB unavailable (e.g. unit tests) — fall through to in-memory guard

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
        "ANCIENT_TOMB": _apply_ancient_tomb,
        "TRADE_CARAVAN": _apply_trade_caravan,
    }
    
    handler = event_handlers.get(event_type)
    if not handler:
        return None, None
    
    message, affected = handler(characters, bank, current_day)
    
    # Find current king name
    king_name = ""
    for c in characters:
        if c.get("alive") and c.get("job") == "King":
            king_name = c.get("name", "Unknown")
            break
    
    # Record the event
    event_record = _record_event(event_type, current_day, message, affected, king_name=king_name)
    
    return message, event_record
