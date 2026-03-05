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
- Gear chance for top performers
- Achievement progress
- Special traits for exceptional success

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


# Quest type definitions with base difficulty and rewards
QUEST_TYPES = {
    "COMBAT": {
        "name": "Hunt the Beast",
        "descriptions": [
            "Hunt the {beast} terrorizing nearby farms",
            "Slay the {beast} in the northern caves",
            "Eliminate the {beast} pack threatening travelers",
        ],
        "beasts": ["Dire Wolf", "Cave Troll", "Wyvern", "Bandit Chief", "Orc Warband", "Giant Spider"],
        "base_difficulty": 60,
        "gold_reward": (150, 400),
        "stat_focus": "atk",
    },
    "DIPLOMACY": {
        "name": "Diplomatic Mission",
        "descriptions": [
            "Negotiate a trade agreement with {village}",
            "Establish peace with the {village} delegation",
            "Resolve the border dispute with {village}",
        ],
        "villages": ["Riverdale", "Ironhold", "Sunhaven", "Mistwood", "Thornbury", "Goldcrest"],
        "base_difficulty": 50,
        "gold_reward": (100, 300),
        "stat_focus": "int",
    },
    "EXPLORATION": {
        "name": "Explore Unknown Lands",
        "descriptions": [
            "Map the uncharted {location}",
            "Investigate the ancient {location}",
            "Scout the mysterious {location}",
        ],
        "locations": ["Ruins", "Forest", "Mountains", "Caverns", "Marshlands", "Desert Oasis"],
        "base_difficulty": 55,
        "gold_reward": (120, 350),
        "stat_focus": "def",
    },
    "TRADE": {
        "name": "Trade Expedition",
        "descriptions": [
            "Secure {goods} from the eastern merchants",
            "Transport valuable {goods} to market",
            "Acquire rare {goods} for the kingdom",
        ],
        "goods": ["Spices", "Silk", "Iron Ore", "Gemstones", "Exotic Animals", "Ancient Artifacts"],
        "base_difficulty": 45,
        "gold_reward": (200, 500),
        "stat_focus": "rep",
    },
}

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


def _calculate_quest_success(party: list[Villager], quest_type: str, bank: Bank) -> tuple[bool, float]:
    """Calculate if quest succeeds and success margin."""
    qt_data = QUEST_TYPES[quest_type]
    base_difficulty = qt_data["base_difficulty"]
    stat_focus = qt_data["stat_focus"]
    
    # Sum party stats
    party_power = 0
    for v in party:
        if stat_focus == "atk":
            party_power += int(v.get("atk", 10) or 10)
        elif stat_focus == "int":
            party_power += int(v.get("int", 10) or 10)
        elif stat_focus == "def":
            party_power += int(v.get("def", 10) or 10)
        else:
            party_power += int(v.get("rep", 0) or 0) + 20
        
        party_power += int(v.get("level", 1) or 1) * 2
    
    # Building bonuses
    if quest_type == "COMBAT":
        barracks_lvl = get_building_level(bank, "barracks")
        party_power += barracks_lvl * 15
    elif quest_type == "DIPLOMACY":
        court_lvl = get_building_level(bank, "royal_court")
        party_power += court_lvl * 15
    elif quest_type == "TRADE":
        market_lvl = get_building_level(bank, "market")
        party_power += market_lvl * 15
    elif quest_type == "EXPLORATION":
        library_lvl = get_building_level(bank, "library")
        party_power += library_lvl * 10
    
    # Calculate success chance
    success_chance = min(0.95, max(0.15, (party_power - base_difficulty) / 100 + 0.5))
    
    roll = random.random()
    success = roll < success_chance
    margin = success_chance - roll if success else roll - success_chance
    
    return success, margin


def _apply_quest_results(
    party: list[Villager],
    quest_type: str,
    success: bool,
    margin: float,
    bank: Bank,
    current_day: int
) -> tuple[int, int, list[str]]:
    """
    Apply quest results to party members.
    
    Returns:
        (gold_distributed, deaths, injured_names)
    """
    qt_data = QUEST_TYPES[quest_type]
    gold_min, gold_max = qt_data["gold_reward"]
    
    deaths = 0
    injured = []
    gold_distributed = 0
    
    if success:
        # Success: distribute gold, minor injuries
        total_gold = rand_int(gold_min, gold_max)
        
        # Margin bonus
        if margin > 0.3:
            total_gold = int(total_gold * 1.5)
        
        gold_per_member = total_gold // len(party)
        gold_distributed = total_gold
        
        for v in party:
            v["coins"] = int(v.get("coins", 0) or 0) + gold_per_member
            
            # Small chance of minor injury
            if random.random() < 0.15:
                damage = rand_int(5, 15)
                v["hp"] = max(1, int(v.get("hp", 100) or 100) - damage)
                injured.append(v.get("name", "Unknown"))
            
            # XP reward
            v["exp"] = int(v.get("exp", 0) or 0) + rand_int(15, 30)
            
            # Update action log
            v["last_action"] = f"Quest success: +{gold_per_member} gold"
            
            # Small stat boost chance
            if random.random() < 0.2:
                stat = qt_data["stat_focus"]
                if stat in ("atk", "def", "int"):
                    v[stat] = int(v.get(stat, 10) or 10) + rand_int(1, 2)
                elif stat == "rep":
                    v["rep"] = clamp(int(v.get("rep", 0) or 0) + rand_int(2, 5), -100, 100)
    else:
        # Failure: significant injuries, possible deaths
        for v in party:
            # Damage based on margin of failure
            if margin > 0.3:
                damage = rand_int(30, 60)
            else:
                damage = rand_int(15, 35)
            
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
    
    return gold_distributed, deaths, injured


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
    
    success, margin = _calculate_quest_success(party, quest_type, bank)
    gold, deaths, injured = _apply_quest_results(party, quest_type, success, margin, bank, current_day)
    
    # Mark as triggered
    bank["quest_triggered_this_year"] = True
    
    # Build message
    party_names = [v.get("name", "Unknown") for v in party]
    
    if success:
        if deaths == 0:
            result_text = f"Success! Party earned {gold} gold."
        else:
            result_text = f"Pyrrhic victory. {deaths} died, {gold} gold earned."
    else:
        if deaths == 0:
            result_text = f"Failed. Party returned injured."
        else:
            result_text = f"Failed. {deaths} died in the attempt."
    
    message = f"QUEST: {quest_name} - {quest_desc}. Party: {', '.join(party_names[:3])}{'...' if len(party_names) > 3 else ''}. {result_text}"
    
    # Store quest info
    bank["last_quest_message"] = message
    bank["last_quest_day"] = current_day
    bank["last_quest_type"] = quest_type
    bank["last_quest_success"] = success
    
    # Build detailed record
    party_details = []
    for v in party:
        party_details.append({
            "id": v.get("id"),
            "name": v.get("name", "Unknown"),
            "job": v.get("job", "Unknown"),
            "level": v.get("level", 1),
            "alive": v.get("alive", True),
        })
    
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
        "king_name": king.get("name", "Unknown"),
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
