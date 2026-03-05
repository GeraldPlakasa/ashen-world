"""
Quest/Mission Service - King issues quests that villagers can volunteer for.

Quest Types:
- COMBAT: Hunt dangerous creatures or defend against threats
- DIPLOMACY: Negotiate with neighboring villages
- EXPLORATION: Discover new lands or ruins
- TRADE: Establish trade routes or acquire goods

Quest Timing:
- Quests occur every 2 years on a random day
- King's traits influence quest type selection
- Villagers volunteer based on their traits and conditions
- Party of 2-5 villagers formed

Rewards:
- Gold distributed to surviving party members
- Gear for top performers
- Achievement progress (Questmaster)
- XP and stat boosts

Risks:
- HP damage to party members
- Death possible for failed quests
- Gold loss on failure
"""
from __future__ import annotations

import random
import json
from typing import TYPE_CHECKING

from config import DAYS_PER_YEAR, QUEST_INTERVAL_YEARS
from world_utils import clamp, rand_int
from buildings import get_building_level

if TYPE_CHECKING:
    from src.models.villager import Villager
    from src.models.bank import Bank


# Quest type definitions with stat requirements and rewards
QUEST_TYPES = {
    "COMBAT": {
        "name": "Hunt the Beast",
        "descriptions": [
            "Hunt the {beast} terrorizing nearby farms",
            "Slay the {beast} in the northern caves",
            "Eliminate the {beast} pack threatening travelers",
        ],
        "beasts": ["Dire Wolf", "Cave Troll", "Wyvern", "Bandit Chief", "Orc Warband", "Giant Spider"],
        "stat_focus": "atk",
        "stat_threshold": 25,  # Average ATK needed per party member
        "gold_reward": (150, 400),
        "gear_chance": 0.40,
    },
    "DIPLOMACY": {
        "name": "Diplomatic Mission",
        "descriptions": [
            "Negotiate a trade agreement with {village}",
            "Establish peace with the {village} delegation",
            "Resolve the border dispute with {village}",
        ],
        "villages": ["Riverdale", "Ironhold", "Sunhaven", "Mistwood", "Thornbury", "Goldcrest"],
        "stat_focus": "int",
        "stat_threshold": 20,
        "gold_reward": (100, 300),
        "gear_chance": 0.25,
    },
    "EXPLORATION": {
        "name": "Explore Unknown Lands",
        "descriptions": [
            "Map the uncharted {location}",
            "Investigate the ancient {location}",
            "Scout the mysterious {location}",
        ],
        "locations": ["Ruins", "Forest", "Mountains", "Caverns", "Marshlands", "Desert Oasis"],
        "stat_focus": "def",
        "stat_threshold": 22,
        "gold_reward": (120, 350),
        "gear_chance": 0.35,
    },
    "TRADE": {
        "name": "Trade Expedition",
        "descriptions": [
            "Secure {goods} from the eastern merchants",
            "Transport valuable {goods} to market",
            "Acquire rare {goods} for the kingdom",
        ],
        "goods": ["Spices", "Silk", "Iron Ore", "Gemstones", "Exotic Animals", "Ancient Artifacts"],
        "stat_focus": "rep",
        "stat_threshold": 15,
        "gold_reward": (200, 500),
        "gear_chance": 0.30,
    },
}

# Gear rewards for quest success (similar to shop items)
QUEST_GEAR_T1 = [
    {"type": "Battle Trophy", "bonuses": [{"key": "atk", "amt": (3, 7)}]},
    {"type": "Explorer's Cloak", "bonuses": [{"key": "def", "amt": (3, 7)}]},
    {"type": "Diplomat's Ring", "bonuses": [{"key": "int", "amt": (2, 5)}, {"key": "rep", "amt": (1, 3)}]},
    {"type": "Merchant's Pouch", "bonuses": [{"key": "rep", "amt": (3, 6)}]},
    {"type": "Adventurer's Boots", "bonuses": [{"key": "hp", "amt": (10, 20)}]},
]

QUEST_GEAR_T2 = [
    {"type": "Slayer's Blade", "bonuses": [{"key": "atk", "amt": (8, 14)}]},
    {"type": "Guardian's Shield", "bonuses": [{"key": "def", "amt": (8, 14)}]},
    {"type": "Sage's Medallion", "bonuses": [{"key": "int", "amt": (6, 10)}, {"key": "rep", "amt": (2, 5)}]},
    {"type": "Hero's Mantle", "bonuses": [{"key": "hp", "amt": (20, 35)}, {"key": "rep", "amt": (3, 6)}]},
    {"type": "Veteran's Armor", "bonuses": [{"key": "def", "amt": (6, 10)}, {"key": "hp", "amt": (12, 22)}]},
]

QUEST_GEAR_T3 = [
    {"type": "Dragonslayer's Edge", "bonuses": [{"key": "atk", "amt": (14, 22)}, {"key": "hp", "amt": (15, 25)}]},
    {"type": "Champion's Plate", "bonuses": [{"key": "def", "amt": (12, 20)}, {"key": "hp", "amt": (25, 40)}]},
    {"type": "Crown of the Wise", "bonuses": [{"key": "int", "amt": (10, 16)}, {"key": "rep", "amt": (6, 10)}]},
    {"type": "Legend's Relic", "bonuses": [{"key": "atk", "amt": (8, 14)}, {"key": "def", "amt": (8, 14)}, {"key": "rep", "amt": (4, 8)}]},
]

# Trait influences on quest type preference (for King)
KING_TRAIT_QUEST_WEIGHTS = {
    "Brave": {"COMBAT": 2.0, "EXPLORATION": 1.5},
    "Wise": {"DIPLOMACY": 2.0, "TRADE": 1.3},
    "Greedy": {"TRADE": 2.5, "EXPLORATION": 1.2},
    "Ambitious": {"COMBAT": 1.5, "DIPLOMACY": 1.5, "EXPLORATION": 1.5},
    "Cautious": {"DIPLOMACY": 2.0, "TRADE": 1.5},
    "Hot-headed": {"COMBAT": 2.5},
    "Clever": {"TRADE": 2.0, "DIPLOMACY": 1.5},
    "Generous": {"DIPLOMACY": 1.5, "TRADE": 1.5},
    "Diligent": {"TRADE": 1.5, "EXPLORATION": 1.5},
}

# Trait influences on volunteer willingness
VOLUNTEER_TRAIT_WEIGHTS = {
    "Brave": {"COMBAT": 2.0, "EXPLORATION": 1.5},
    "Reckless": {"COMBAT": 2.5, "EXPLORATION": 2.0},
    "Cautious": {"DIPLOMACY": 1.5, "TRADE": 1.5, "COMBAT": 0.3},
    "Wise": {"DIPLOMACY": 2.0},
    "Clever": {"DIPLOMACY": 1.5, "TRADE": 1.5},
    "Greedy": {"TRADE": 2.5},
    "Ambitious": {"COMBAT": 1.3, "EXPLORATION": 1.5, "DIPLOMACY": 1.3},
    "Lazy": {"COMBAT": 0.2, "EXPLORATION": 0.3, "TRADE": 0.5, "DIPLOMACY": 0.5},
    "Curious": {"EXPLORATION": 2.5},
    "Hot-headed": {"COMBAT": 2.0},
    "Protective": {"COMBAT": 1.5},
    "Hunter": {"COMBAT": 2.5, "EXPLORATION": 1.5},
    "Veteran": {"COMBAT": 2.0, "EXPLORATION": 1.8, "DIPLOMACY": 1.5, "TRADE": 1.5},
}


def _get_king_traits(characters: list[Villager]) -> set[str]:
    """Get the current King's traits as a set."""
    king = next((v for v in characters if v.get("job") == "King" and v.get("alive", True)), None)
    if not king:
        return set()
    traits_str = king.get("traits", "") or ""
    return {t.strip() for t in traits_str.split(",") if t.strip()}


def _get_villager_traits(v: Villager) -> set[str]:
    """Get villager's traits as a set."""
    traits_str = v.get("traits", "") or ""
    return {t.strip() for t in traits_str.split(",") if t.strip()}


def _select_quest_type(characters: list[Villager]) -> str:
    """Select quest type based on King's traits."""
    king_traits = _get_king_traits(characters)
    
    weights = {qt: 1.0 for qt in QUEST_TYPES}
    
    for trait in king_traits:
        if trait in KING_TRAIT_QUEST_WEIGHTS:
            for qt, mult in KING_TRAIT_QUEST_WEIGHTS[trait].items():
                weights[qt] *= mult
    
    total = sum(weights.values())
    r = random.random() * total
    cumulative = 0
    for qt, w in weights.items():
        cumulative += w
        if r <= cumulative:
            return qt
    return "COMBAT"


def _generate_quest_description(quest_type: str) -> tuple[str, str]:
    """Generate quest name and description."""
    qt_data = QUEST_TYPES[quest_type]
    desc_template = random.choice(qt_data["descriptions"])
    
    if quest_type == "COMBAT":
        target = random.choice(qt_data["beasts"])
        desc = desc_template.format(beast=target)
    elif quest_type == "DIPLOMACY":
        target = random.choice(qt_data["villages"])
        desc = desc_template.format(village=target)
    elif quest_type == "EXPLORATION":
        target = random.choice(qt_data["locations"])
        desc = desc_template.format(location=target)
    else:  # TRADE
        target = random.choice(qt_data["goods"])
        desc = desc_template.format(goods=target)
    
    return qt_data["name"], desc


def _calculate_volunteer_score(v: Villager, quest_type: str) -> float:
    """Calculate how likely a villager is to volunteer for a quest."""
    if not v.get("alive", True):
        return -1000
    
    age = int(v.get("age", 0) or 0)
    if age < 18 or age > 65:
        return -1000
    
    # Base score from relevant stat
    qt_data = QUEST_TYPES[quest_type]
    stat_focus = qt_data["stat_focus"]
    
    if stat_focus == "atk":
        base_score = int(v.get("atk", 10) or 10) * 1.5
    elif stat_focus == "int":
        base_score = int(v.get("int", 10) or 10) * 1.5
    elif stat_focus == "def":
        base_score = int(v.get("def", 10) or 10) * 1.5
    else:  # rep
        base_score = int(v.get("rep", 0) or 0) + 50
    
    # Level bonus
    base_score += int(v.get("level", 1) or 1) * 3
    
    # Trait modifiers
    traits = _get_villager_traits(v)
    trait_mult = 1.0
    for trait in traits:
        if trait in VOLUNTEER_TRAIT_WEIGHTS:
            quest_weights = VOLUNTEER_TRAIT_WEIGHTS[trait]
            if quest_type in quest_weights:
                trait_mult *= quest_weights[quest_type]
    
    base_score *= trait_mult
    
    # Economic condition (poor villagers more likely to risk for gold)
    coins = int(v.get("coins", 0) or 0)
    if coins < 50:
        base_score *= 1.3
    elif coins > 300:
        base_score *= 0.8
    
    # Health penalty
    hp = int(v.get("hp", 100) or 100)
    if hp < 50:
        base_score *= 0.5
    
    # Hunger penalty
    hunger = int(v.get("hunger", 0) or 0)
    if hunger > 70:
        base_score *= 0.6
    
    # Royal jobs don't volunteer
    job = v.get("job", "")
    if job in ("King", "Queen"):
        return -1000
    
    # Some randomness
    base_score *= random.uniform(0.7, 1.3)
    
    return base_score


def _select_party(characters: list[Villager], quest_type: str, party_size: int = None) -> list[Villager]:
    """Select a party of volunteers for the quest."""
    if party_size is None:
        party_size = rand_int(2, 5)
    
    # Score all eligible villagers
    candidates = []
    for v in characters:
        score = _calculate_volunteer_score(v, quest_type)
        if score > 0:
            candidates.append((v, score))
    
    if not candidates:
        return []
    
    # Sort by score and pick top candidates with some randomness
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Take top 2x party_size and randomly select from them
    pool_size = min(len(candidates), party_size * 2)
    pool = candidates[:pool_size]
    
    if len(pool) <= party_size:
        return [c[0] for c in pool]
    
    selected = random.sample(pool, party_size)
    return [c[0] for c in selected]


def _calculate_quest_success(party: list[Villager], quest_type: str, bank: Bank) -> tuple[bool, float, dict]:
    """
    Calculate if quest succeeds based strictly on party stats.
    
    Returns:
        (success, margin, stats_info)
    """
    qt_data = QUEST_TYPES[quest_type]
    stat_focus = qt_data["stat_focus"]
    threshold = qt_data["stat_threshold"]
    
    # Calculate party stats
    total_stat = 0
    total_level = 0
    total_hp = 0
    
    for v in party:
        if stat_focus == "atk":
            total_stat += int(v.get("atk", 10) or 10)
        elif stat_focus == "int":
            total_stat += int(v.get("int", 10) or 10)
        elif stat_focus == "def":
            total_stat += int(v.get("def", 10) or 10)
        else:  # rep
            total_stat += int(v.get("rep", 0) or 0) + 10
        
        total_level += int(v.get("level", 1) or 1)
        total_hp += int(v.get("hp", 100) or 100)
    
    party_size = len(party)
    avg_stat = total_stat / party_size
    avg_level = total_level / party_size
    avg_hp = total_hp / party_size
    
    # Building bonuses (add to average stat)
    building_bonus = 0
    if quest_type == "COMBAT":
        barracks_lvl = get_building_level(bank, "barracks")
        building_bonus = barracks_lvl * 3
    elif quest_type == "DIPLOMACY":
        court_lvl = get_building_level(bank, "royal_court")
        building_bonus = court_lvl * 3
    elif quest_type == "TRADE":
        market_lvl = get_building_level(bank, "market")
        building_bonus = market_lvl * 3
    elif quest_type == "EXPLORATION":
        library_lvl = get_building_level(bank, "library")
        building_bonus = library_lvl * 2
    
    effective_stat = avg_stat + building_bonus + (avg_level * 0.5)
    
    # Calculate success based on stat vs threshold
    # If effective_stat >= threshold * 1.5 -> guaranteed success
    # If effective_stat >= threshold -> 70-95% success
    # If effective_stat >= threshold * 0.7 -> 40-70% success
    # Below that -> 10-40% success
    
    ratio = effective_stat / threshold
    
    if ratio >= 1.5:
        success_chance = 0.95
    elif ratio >= 1.2:
        success_chance = 0.80 + (ratio - 1.2) * 0.5  # 80-95%
    elif ratio >= 1.0:
        success_chance = 0.65 + (ratio - 1.0) * 0.75  # 65-80%
    elif ratio >= 0.8:
        success_chance = 0.40 + (ratio - 0.8) * 1.25  # 40-65%
    elif ratio >= 0.6:
        success_chance = 0.20 + (ratio - 0.6) * 1.0   # 20-40%
    else:
        success_chance = max(0.05, ratio * 0.33)      # 5-20%
    
    # HP factor - low HP party has penalty
    if avg_hp < 50:
        success_chance *= 0.8
    
    # Apply small randomness
    roll = random.random()
    success = roll < success_chance
    margin = abs(success_chance - roll)
    
    stats_info = {
        "avg_stat": round(avg_stat, 1),
        "avg_level": round(avg_level, 1),
        "building_bonus": building_bonus,
        "effective_stat": round(effective_stat, 1),
        "threshold": threshold,
        "ratio": round(ratio, 2),
        "success_chance": round(success_chance * 100, 1),
    }
    
    return success, margin, stats_info


def _generate_gear_reward(quest_type: str, party_size: int) -> dict | None:
    """Generate a gear reward based on quest type and party size."""
    qt_data = QUEST_TYPES[quest_type]
    gear_chance = qt_data["gear_chance"]
    
    # Larger parties have slightly better gear chance
    gear_chance += (party_size - 2) * 0.05
    
    if random.random() > gear_chance:
        return None
    
    # Select tier based on random chance
    tier_roll = random.random()
    if tier_roll < 0.10:  # 10% chance T3
        pool = QUEST_GEAR_T3
        tier = 3
    elif tier_roll < 0.40:  # 30% chance T2
        pool = QUEST_GEAR_T2
        tier = 2
    else:  # 60% chance T1
        pool = QUEST_GEAR_T1
        tier = 1
    
    gear_template = random.choice(pool)
    
    # Generate actual bonus values
    bonuses = []
    for b in gear_template["bonuses"]:
        amt = rand_int(b["amt"][0], b["amt"][1])
        bonuses.append({"key": b["key"], "amt": amt})
    
    return {
        "type": gear_template["type"],
        "tier": tier,
        "bonuses": bonuses,
    }


def _apply_gear_to_villager(v: Villager, gear: dict) -> str:
    """Apply gear bonuses to villager and return description."""
    bonus_strs = []
    for b in gear["bonuses"]:
        key = b["key"]
        amt = b["amt"]
        if key == "rep":
            v[key] = clamp(int(v.get(key, 0) or 0) + amt, -100, 100)
        else:
            v[key] = int(v.get(key, 0) or 0) + amt
        bonus_strs.append(f"+{amt} {key.upper()}")
    
    return f"{gear['type']} ({', '.join(bonus_strs)})"


def _increment_quest_wins(v: Villager) -> int:
    """Increment quest win count and return new total."""
    current = int(v.get("questWins", 0) or 0)
    v["questWins"] = current + 1
    return current + 1


def _apply_quest_results(
    party: list[Villager],
    quest_type: str,
    success: bool,
    margin: float,
    bank: Bank,
    current_day: int
) -> tuple[int, int, list[str], list[dict]]:
    """
    Apply quest results to party members.
    
    Returns:
        (gold_distributed, deaths, injured_names, gear_rewards)
    """
    qt_data = QUEST_TYPES[quest_type]
    gold_min, gold_max = qt_data["gold_reward"]
    
    deaths = 0
    injured = []
    gold_distributed = 0
    gear_rewards = []
    
    if success:
        # Success: distribute gold, gear, minor injuries
        total_gold = rand_int(gold_min, gold_max)
        
        # Margin bonus
        if margin > 0.3:
            total_gold = int(total_gold * 1.5)
        elif margin > 0.15:
            total_gold = int(total_gold * 1.2)
        
        gold_per_member = total_gold // len(party)
        gold_distributed = total_gold
        
        # Generate gear for the party
        gear = _generate_gear_reward(quest_type, len(party))
        
        # Best performer gets gear (highest relevant stat)
        stat_focus = qt_data["stat_focus"]
        if stat_focus == "rep":
            stat_focus_key = "rep"
        else:
            stat_focus_key = stat_focus
        
        party_sorted = sorted(party, key=lambda v: int(v.get(stat_focus_key, 0) or 0), reverse=True)
        
        for i, v in enumerate(party):
            v["coins"] = int(v.get("coins", 0) or 0) + gold_per_member
            
            # Increment quest wins
            quest_wins = _increment_quest_wins(v)
            
            # Small chance of minor injury
            if random.random() < 0.15:
                damage = rand_int(5, 15)
                v["hp"] = max(1, int(v.get("hp", 100) or 100) - damage)
                injured.append(v.get("name", "Unknown"))
            
            # XP reward
            v["exp"] = int(v.get("exp", 0) or 0) + rand_int(20, 40)
            
            # Best performer gets gear
            if gear and v == party_sorted[0]:
                gear_desc = _apply_gear_to_villager(v, gear)
                gear_rewards.append({
                    "recipient": v.get("name", "Unknown"),
                    "gear": gear["type"],
                    "tier": gear["tier"],
                    "bonuses": gear["bonuses"],
                })
                v["last_action"] = f"Quest success: +{gold_per_member}g, {gear_desc}"
            else:
                v["last_action"] = f"Quest success: +{gold_per_member} gold"
            
            # Small stat boost chance for others
            if random.random() < 0.15 and v != party_sorted[0]:
                stat = stat_focus_key if stat_focus_key in ("atk", "def", "int") else "rep"
                if stat == "rep":
                    v["rep"] = clamp(int(v.get("rep", 0) or 0) + rand_int(1, 3), -100, 100)
                else:
                    v[stat] = int(v.get(stat, 10) or 10) + rand_int(1, 2)
    else:
        # Failure: significant injuries, possible deaths
        for v in party:
            # Damage based on margin of failure
            if margin > 0.3:
                damage = rand_int(35, 65)
            elif margin > 0.15:
                damage = rand_int(25, 45)
            else:
                damage = rand_int(15, 30)
            
            v["hp"] = max(0, int(v.get("hp", 100) or 100) - damage)
            
            if v["hp"] <= 0:
                v["alive"] = False
                v["death_day"] = current_day
                v["last_action"] = f"died during {quest_type.lower()} quest"
                deaths += 1
            else:
                injured.append(v.get("name", "Unknown"))
                v["last_action"] = f"Quest failed: -{damage} HP"
            
            # Small XP for attempt
            v["exp"] = int(v.get("exp", 0) or 0) + rand_int(5, 10)
        
        # Gold loss from treasury
        loss = rand_int(50, 150)
        bank["balance"] = max(0, int(bank.get("balance", 0) or 0) - loss)
    
    return gold_distributed, deaths, injured, gear_rewards


def maybe_trigger_quest(
    characters: list[Villager],
    bank: Bank,
    current_day: int
) -> tuple[str | None, dict | None]:
    """
    Check if a quest should trigger and execute it.
    
    Quests trigger every 2 years on a random day (scheduled at year start).
    
    Returns:
        (quest_message, quest_record) or (None, None) if no quest
    """
    year = ((current_day - 1) // DAYS_PER_YEAR) + 1
    day_in_year = ((current_day - 1) % DAYS_PER_YEAR)
    
    # Get quest tracking from bank
    last_quest_year = int(bank.get("last_quest_year", 0) or 0)
    quest_day_for_year = bank.get("quest_day_for_year")
    quest_triggered_this_year = bank.get("quest_triggered_this_year", False)
    
    # Check if this is a quest year (every 2 years starting year 2)
    is_quest_year = year >= 2 and (year % QUEST_INTERVAL_YEARS == 0)
    
    if not is_quest_year:
        return None, None
    
    # If already triggered this year, skip
    if quest_triggered_this_year and last_quest_year == year:
        return None, None
    
    # Schedule quest day at start of year
    if quest_day_for_year is None or last_quest_year != year:
        quest_day_for_year = rand_int(10, DAYS_PER_YEAR - 10)
        bank["quest_day_for_year"] = quest_day_for_year
        bank["quest_triggered_this_year"] = False
        bank["last_quest_year"] = year
    
    # Check if today is the scheduled quest day
    if day_in_year != quest_day_for_year:
        return None, None
    
    # Check if there's a King to issue quests
    king = next((v for v in characters if v.get("job") == "King" and v.get("alive", True)), None)
    if not king:
        return None, None
    
    # Execute quest
    quest_type = _select_quest_type(characters)
    quest_name, quest_desc = _generate_quest_description(quest_type)
    party = _select_party(characters, quest_type)
    
    if len(party) < 2:
        bank["quest_triggered_this_year"] = True
        return None, None
    
    success, margin, stats_info = _calculate_quest_success(party, quest_type, bank)
    gold, deaths, injured, gear_rewards = _apply_quest_results(party, quest_type, success, margin, bank, current_day)
    
    # Mark as triggered
    bank["quest_triggered_this_year"] = True
    
    # Build party details
    party_names = [v.get("name", "Unknown") for v in party]
    party_details = []
    for v in party:
        party_details.append({
            "id": v.get("id"),
            "name": v.get("name", "Unknown"),
            "job": v.get("job", "Unknown"),
            "level": v.get("level", 1),
            "alive": v.get("alive", True),
            "quest_wins": v.get("questWins", 0),
        })
    
    # Build result text
    if success:
        if deaths == 0 and gear_rewards:
            result_text = f"Success! {gold}g earned. {gear_rewards[0]['recipient']} received {gear_rewards[0]['gear']}."
        elif deaths == 0:
            result_text = f"Success! {gold}g earned."
        else:
            result_text = f"Pyrrhic victory. {deaths} died, {gold}g earned."
    else:
        if deaths == 0:
            result_text = f"Failed. Party returned injured."
        else:
            result_text = f"Failed. {deaths} died."
    
    message = f"QUEST: {quest_name} · {result_text}"
    
    # Store quest info
    bank["last_quest_message"] = message
    bank["last_quest_day"] = current_day
    bank["last_quest_type"] = quest_type
    bank["last_quest_success"] = success
    
    record = {
        "type": quest_type,
        "name": quest_name,
        "description": quest_desc,
        "day": current_day,
        "year": year,
        "day_in_year": day_in_year,
        "party": party_names,
        "party_details": party_details,
        "party_size": len(party),
        "success": success,
        "gold": gold,
        "deaths": deaths,
        "injured": injured,
        "gear_rewards": gear_rewards,
        "king_name": king.get("name", "Unknown"),
        "stats_info": stats_info,
    }
    
    # Add to quest history
    quest_history = bank.get("quest_history", [])
    if not isinstance(quest_history, list):
        quest_history = []
    quest_history.append(record)
    # Keep last 50 quests
    if len(quest_history) > 50:
        quest_history = quest_history[-50:]
    bank["quest_history"] = quest_history
    
    return message, record


def clear_quest_state(bank: Bank) -> None:
    """Reset quest tracking state."""
    bank["last_quest_year"] = 0
    bank["quest_day_for_year"] = None
    bank["quest_triggered_this_year"] = False
    bank["last_quest_message"] = ""
    bank["last_quest_day"] = None
    bank["last_quest_type"] = None
    bank["last_quest_success"] = None
    bank["quest_history"] = []
