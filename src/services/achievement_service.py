"""
Achievement / Milestone System for Ashen World.

Achievements are tracked per-villager and can unlock traits or grant stat bonuses.
"""
from __future__ import annotations

import json
import random
from typing import Callable

from src.models.villager import Villager
from world_utils import clamp


# ===========================================================================
#  Achievement Definitions
# ===========================================================================
# Format: { "id": { "name", "description", "check_fn", "reward" } }
# reward can be: {"type": "stat", "stat": "atk", "value": 10}
#            or: {"type": "trait", "trait": "Veteran"}
#            or: {"type": "both", "stat": "hp", "value": 20, "trait": "Blessed"}

ACHIEVEMENTS = {
    "dynasty_founder": {
        "name": "Dynasty Founder", 
        "description": "Have 5 or more children",
        "icon": "👨‍👩‍👧‍👦",
        "reward": {"type": "both", "stat": "rep", "value": 15, "trait": "Patriarch"},
    },
    "kingmaker": {
        "name": "Kingmaker",
        "description": "Vote for 5 different kings",
        "icon": "🗳️",
        "reward": {"type": "stat", "stat": "int", "value": 10},
    },
    "centurion": {
        "name": "Centurion",
        "description": "Reach age 100",
        "icon": "🎂",
        "reward": {"type": "both", "stat": "hp", "value": 50, "trait": "Immortal"},
    },
    "legendary_hunter": {
        "name": "Legendary Hunter",
        "description": "Win 500 hunts total",
        "icon": "🏹",
        "reward": {"type": "both", "stat": "atk", "value": 25, "trait": "Hunter"},
    },
    "wealthy": {
        "name": "Wealthy",
        "description": "Accumulate 10000 coins",
        "icon": "💰",
        "reward": {"type": "stat", "stat": "coins", "value": 1000},
    },
    "survivor": {
        "name": "Survivor",
        "description": "Survive a plague event",
        "icon": "🛡️",
        "reward": {"type": "stat", "stat": "def", "value": 10},
    },
    "elder_statesman": {
        "name": "Elder Statesman",
        "description": "Become King at age 60+",
        "icon": "👑",
        "reward": {"type": "both", "stat": "rep", "value": 20, "trait": "Wise"},
    },
    "iron_will": {
        "name": "Iron Will",
        "description": "Survive with HP below 10 five times",
        "icon": "💪",
        "reward": {"type": "both", "stat": "def", "value": 15, "trait": "Resilient"},
    },
    "questmaster": {
        "name": "Questmaster",
        "description": "Complete 5 successful quests",
        "icon": "⚔️",
        "reward": {"type": "both", "stat": "atk", "value": 10, "trait": "Veteran"},
    },
}


# ===========================================================================
#  Helper Functions
# ===========================================================================

def get_achievements(v: Villager) -> list[str]:
    """Get list of achievement IDs the villager has earned."""
    raw = v.get("achievements", "[]")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def set_achievements(v: Villager, achievements: list[str]) -> None:
    """Set the villager's achievements list."""
    v["achievements"] = json.dumps(achievements)


def has_achievement(v: Villager, achievement_id: str) -> bool:
    """Check if villager has a specific achievement."""
    return achievement_id in get_achievements(v)


def get_kings_voted_for(v: Villager) -> list[int]:
    """Get list of king IDs the villager has voted for."""
    raw = v.get("kingsVotedFor", "[]")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def set_kings_voted_for(v: Villager, kings: list[int]) -> None:
    """Set the list of kings voted for."""
    v["kingsVotedFor"] = json.dumps(kings)


def add_king_voted_for(v: Villager, king_id: int) -> None:
    """Add a king to the list of kings voted for."""
    kings = get_kings_voted_for(v)
    if king_id not in kings:
        kings.append(king_id)
        set_kings_voted_for(v, kings)


def _add_trait(v: Villager, new_trait: str) -> None:
    """Add a trait to villager if they don't already have it."""
    current_traits = v.get("traits", "")
    if new_trait in current_traits:
        return
    if current_traits:
        v["traits"] = f"{current_traits}, {new_trait}"
    else:
        v["traits"] = new_trait


# ===========================================================================
#  Award Achievement
# ===========================================================================

def award_achievement(v: Villager, achievement_id: str) -> bool:
    """
    Award an achievement to a villager.
    
    Returns True if newly awarded, False if already had it.
    """
    if achievement_id not in ACHIEVEMENTS:
        return False
    
    if has_achievement(v, achievement_id):
        return False
    
    # Add achievement
    achievements = get_achievements(v)
    achievements.append(achievement_id)
    set_achievements(v, achievements)
    
    # Apply reward
    ach = ACHIEVEMENTS[achievement_id]
    reward = ach.get("reward", {})
    reward_type = reward.get("type", "")
    
    if reward_type in ("stat", "both"):
        stat = reward.get("stat", "")
        value = reward.get("value", 0)
        if stat and value:
            if stat == "coins":
                v[stat] = int(v.get(stat, 0) or 0) + value
            elif stat == "rep":
                v[stat] = clamp(int(v.get(stat, 0) or 0) + value, -100, 100)
            else:
                v[stat] = int(v.get(stat, 0) or 0) + value
    
    if reward_type in ("trait", "both"):
        trait = reward.get("trait", "")
        if trait:
            _add_trait(v, trait)
    
    # Update last_action to show achievement
    icon = ach.get("icon", "🏆")
    name = ach.get("name", achievement_id)
    current_action = v.get("last_action", "")
    if current_action:
        v["last_action"] = f"{current_action} / {icon} ACHIEVEMENT: {name}!"
    else:
        v["last_action"] = f"{icon} ACHIEVEMENT: {name}!"
    
    return True


# ===========================================================================
#  Achievement Check Functions
# ===========================================================================

def check_dynasty_founder(v: Villager) -> bool:
    """Check if villager has 5+ children."""
    if has_achievement(v, "dynasty_founder"):
        return False
    children = v.get("childrenIds", [])
    if isinstance(children, str):
        try:
            children = json.loads(children) if children else []
        except (json.JSONDecodeError, TypeError):
            children = []
    return len(children) >= 5


def check_kingmaker(v: Villager) -> bool:
    """Check if villager has voted for 5+ different kings."""
    if has_achievement(v, "kingmaker"):
        return False
    kings = get_kings_voted_for(v)
    return len(kings) >= 5


def check_centurion(v: Villager) -> bool:
    """Check if villager has reached age 100."""
    if has_achievement(v, "centurion"):
        return False
    age = int(v.get("age", 0) or 0)
    return age >= 100


def check_legendary_hunter(v: Villager) -> bool:
    """Check if villager has 500+ total hunt wins."""
    if has_achievement(v, "legendary_hunter"):
        return False
    hunt_wins = int(v.get("huntWins", 0) or 0)
    return hunt_wins >= 500


def check_wealthy(v: Villager) -> bool:
    """Check if villager has 10000+ coins."""
    if has_achievement(v, "wealthy"):
        return False
    coins = int(v.get("coins", 0) or 0)
    return coins >= 10000


def check_elder_statesman(v: Villager) -> bool:
    """Check if villager became King at age 60+."""
    if has_achievement(v, "elder_statesman"):
        return False
    job = v.get("job", "")
    age = int(v.get("age", 0) or 0)
    return job == "King" and age >= 60


def check_questmaster(v: Villager) -> bool:
    """Check if villager has completed 5+ successful quests."""
    if has_achievement(v, "questmaster"):
        return False
    quest_wins = int(v.get("questWins", 0) or 0)
    return quest_wins >= 5


# ===========================================================================
#  Daily Achievement Check Phase
# ===========================================================================

def achievement_check_phase(characters: list[Villager], current_day: int = 0) -> None:
    """
    Run daily achievement checks for all living villagers.
    """
    for v in characters:
        if not v.get("alive", True):
            continue
        
        # Check each achievement
        if check_dynasty_founder(v):
            award_achievement(v, "dynasty_founder")
        
        if check_kingmaker(v):
            award_achievement(v, "kingmaker")
        
        if check_centurion(v):
            award_achievement(v, "centurion")
        
        if check_legendary_hunter(v):
            award_achievement(v, "legendary_hunter")
        
        if check_wealthy(v):
            award_achievement(v, "wealthy")
        
        if check_elder_statesman(v):
            award_achievement(v, "elder_statesman")
        
        if check_questmaster(v):
            award_achievement(v, "questmaster")


# ===========================================================================
#  Special Achievement Triggers (called from specific events)
# ===========================================================================

def trigger_survivor_achievement(v: Villager) -> bool:
    """Called when a villager survives a plague. Returns True if newly awarded."""
    return award_achievement(v, "survivor")


def trigger_iron_will_check(v: Villager) -> bool:
    """
    Called when villager's HP drops below 10 but survives.
    Tracks count internally and awards at 5 occurrences.
    """
    if has_achievement(v, "iron_will"):
        return False
    
    # Track low HP survival count in achievements field temporarily
    achievements = get_achievements(v)
    
    # Count how many times "iron_will_count_X" appears
    count = sum(1 for a in achievements if a.startswith("iron_will_count_"))
    count += 1
    
    if count >= 5:
        # Remove tracking entries
        achievements = [a for a in achievements if not a.startswith("iron_will_count_")]
        set_achievements(v, achievements)
        return award_achievement(v, "iron_will")
    else:
        # Add another tracking entry
        achievements.append(f"iron_will_count_{count}")
        set_achievements(v, achievements)
        return False
