"""
Skill System for Ashen World

Skills are rare abilities that villagers can be born with.
Each skill provides bonuses and may influence job selection.

Skill Categories:
- COMBAT: Battle-related skills
- CRAFT: Production and crafting
- SOCIAL: Leadership and diplomacy
- SURVIVAL: Exploration and endurance
- KNOWLEDGE: Learning and magic
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.villager import Villager

# Chance for a newborn to have any skill
SKILL_BIRTH_CHANCE = 0.12  # 12% chance to get at least one skill

# If has skill, chance to get a second one
SECOND_SKILL_CHANCE = 0.20  # 20% chance for second skill if first acquired

# Skill definitions with effects and job affinities (Fantasy/DnD names)
SKILLS = {
    # COMBAT SKILLS
    "Bladesong": {
        "category": "COMBAT",
        "description": "Ancient elven sword technique",
        "stat_bonus": {"atk": 5},
        "job_affinity": ["Soldier", "Guard", "Knight", "Commander", "Captain"],
        "rarity": "common",
    },
    "Hawkeye": {
        "category": "COMBAT",
        "description": "Uncanny precision with ranged weapons",
        "stat_bonus": {"atk": 3, "def": 2},
        "job_affinity": ["Archer", "Ranger", "Hunter"],
        "rarity": "common",
    },
    "Bloodrage": {
        "category": "COMBAT",
        "description": "Primal fury that overwhelms foes",
        "stat_bonus": {"atk": 8, "def": -2},
        "job_affinity": ["Soldier", "Guard", "Hunter"],
        "rarity": "rare",
    },
    "Bulwark": {
        "category": "COMBAT",
        "description": "Immovable defensive stance",
        "stat_bonus": {"def": 6, "hp": 10},
        "job_affinity": ["Guard", "Knight", "Soldier"],
        "rarity": "uncommon",
    },
    "Battlemaster": {
        "category": "COMBAT",
        "description": "Strategic genius of warfare",
        "stat_bonus": {"int": 4, "atk": 2},
        "job_affinity": ["Commander", "Captain", "Advisor"],
        "rarity": "rare",
    },

    # CRAFT SKILLS
    "Forgeblessed": {
        "category": "CRAFT",
        "description": "Blessed touch with metal and flame",
        "stat_bonus": {"atk": 2, "def": 2},
        "job_affinity": ["Blacksmith", "Armorer", "Weaponsmith"],
        "rarity": "common",
    },
    "Transmutation": {
        "category": "CRAFT",
        "description": "Art of transforming matter",
        "stat_bonus": {"int": 4, "hp": 5},
        "job_affinity": ["Alchemist", "Healer", "Apothecary"],
        "rarity": "uncommon",
    },
    "Gilded Hands": {
        "category": "CRAFT",
        "description": "Masterful precision in delicate work",
        "stat_bonus": {"rep": 3, "int": 2},
        "job_affinity": ["Jeweler", "Tailor", "Carpenter", "Potter"],
        "rarity": "common",
    },
    "Artificer": {
        "category": "CRAFT",
        "description": "Creator of wondrous mechanisms",
        "stat_bonus": {"int": 5, "def": 2},
        "job_affinity": ["Engineer", "Architect", "Mason"],
        "rarity": "rare",
    },
    "Brewcraft": {
        "category": "CRAFT",
        "description": "Secret recipes passed through ages",
        "stat_bonus": {"rep": 4, "hp": 3},
        "job_affinity": ["Brewer", "Innkeeper", "Cook"],
        "rarity": "common",
    },

    # SOCIAL SKILLS
    "Silver Tongue": {
        "category": "SOCIAL",
        "description": "Words that bend hearts and minds",
        "stat_bonus": {"rep": 6},
        "job_affinity": ["Merchant", "Noble", "Bard", "Diplomat"],
        "rarity": "uncommon",
    },
    "Commanding Presence": {
        "category": "SOCIAL",
        "description": "Aura of natural authority",
        "stat_bonus": {"rep": 4, "int": 3},
        "job_affinity": ["Commander", "Captain", "Noble", "Advisor"],
        "rarity": "rare",
    },
    "Dealmaker": {
        "category": "SOCIAL",
        "description": "Never loses in a bargain",
        "stat_bonus": {"rep": 5, "int": 2},
        "job_affinity": ["Merchant", "Trader", "Diplomat"],
        "rarity": "uncommon",
    },
    "Dreadgaze": {
        "category": "SOCIAL",
        "description": "Stare that freezes the boldest souls",
        "stat_bonus": {"rep": 3, "atk": 2},
        "job_affinity": ["Guard", "Spy", "Commander"],
        "rarity": "uncommon",
    },
    "Heartspark": {
        "category": "SOCIAL",
        "description": "Ignites courage in the downtrodden",
        "stat_bonus": {"rep": 5, "hp": 5},
        "job_affinity": ["Priest", "Bard", "Noble", "Healer"],
        "rarity": "rare",
    },

    # SURVIVAL SKILLS
    "Pathfinder": {
        "category": "SURVIVAL",
        "description": "Reads the wild like an open book",
        "stat_bonus": {"def": 3, "atk": 2},
        "job_affinity": ["Hunter", "Ranger", "Scout", "Forester"],
        "rarity": "common",
    },
    "Herbweaver": {
        "category": "SURVIVAL",
        "description": "Communion with healing flora",
        "stat_bonus": {"hp": 8, "int": 2},
        "job_affinity": ["Healer", "Herbalist", "Druid", "Apothecary"],
        "rarity": "uncommon",
    },
    "Iron Constitution": {
        "category": "SURVIVAL",
        "description": "Body forged through hardship",
        "stat_bonus": {"hp": 15, "def": 3},
        "job_affinity": ["Soldier", "Miner", "Farmer", "Woodcutter"],
        "rarity": "uncommon",
    },
    "Wayfarer": {
        "category": "SURVIVAL",
        "description": "Never lost, even in the darkest wild",
        "stat_bonus": {"def": 4, "int": 2},
        "job_affinity": ["Ranger", "Scout", "Sailor", "Courier"],
        "rarity": "common",
    },
    "Beastbond": {
        "category": "SURVIVAL",
        "description": "Kinship with creatures of nature",
        "stat_bonus": {"def": 2, "rep": 3},
        "job_affinity": ["Stablemaster", "Falconer", "Shepherd", "Hunter"],
        "rarity": "common",
    },

    # KNOWLEDGE SKILLS
    "Lorekeeper": {
        "category": "KNOWLEDGE",
        "description": "Living repository of ancient wisdom",
        "stat_bonus": {"int": 6},
        "job_affinity": ["Scholar", "Scribe", "Advisor", "Priest"],
        "rarity": "common",
    },
    "Arcane Attunement": {
        "category": "KNOWLEDGE",
        "description": "Sensitive to flows of mystic energy",
        "stat_bonus": {"int": 5, "hp": 5},
        "job_affinity": ["Druid", "Alchemist", "Priest", "Herbalist"],
        "rarity": "rare",
    },
    "Chirurgeon": {
        "category": "KNOWLEDGE",
        "description": "Mastery of wounds and ailments",
        "stat_bonus": {"int": 4, "hp": 8},
        "job_affinity": ["Healer", "Herbalist", "Priest"],
        "rarity": "uncommon",
    },
    "Polyglot": {
        "category": "KNOWLEDGE",
        "description": "Speaks in a hundred tongues",
        "stat_bonus": {"int": 4, "rep": 3},
        "job_affinity": ["Scribe", "Merchant", "Diplomat", "Bard"],
        "rarity": "uncommon",
    },
    "Chronicle": {
        "category": "KNOWLEDGE",
        "description": "Remembers every tale ever told",
        "stat_bonus": {"int": 5, "rep": 2},
        "job_affinity": ["Scholar", "Advisor", "Scribe", "Priest"],
        "rarity": "common",
    },

    # MAGIC SKILLS
    "Fireball": {
        "category": "MAGIC",
        "description": "Hurls a devastating ball of flame",
        "stat_bonus": {"mp": 10, "atk": 5},
        "job_affinity": ["Wizard", "Sorcerer"],
        "rarity": "uncommon",
    },
    "Healing Light": {
        "category": "MAGIC",
        "description": "Channels restorative magic to mend wounds",
        "stat_bonus": {"mp": 8, "hp": 10},
        "job_affinity": ["Cleric", "Priest", "Healer"],
        "rarity": "common",
    },
    "Arcane Shield": {
        "category": "MAGIC",
        "description": "Conjures a protective barrier of pure mana",
        "stat_bonus": {"mp": 12, "def": 6},
        "job_affinity": ["Wizard", "Cleric", "Sorcerer"],
        "rarity": "uncommon",
    },
    "Enchantment": {
        "category": "MAGIC",
        "description": "Imbues objects with magical properties",
        "stat_bonus": {"mp": 8, "int": 4},
        "job_affinity": ["Wizard", "Alchemist", "Druid"],
        "rarity": "rare",
    },
    "War Chant": {
        "category": "MAGIC",
        "description": "A powerful song that inspires allies in battle",
        "stat_bonus": {"mp": 6, "atk": 3, "rep": 3},
        "job_affinity": ["Bard", "Cleric"],
        "rarity": "uncommon",
    },
    "Mana Surge": {
        "category": "MAGIC",
        "description": "Draws deep from the ley lines to restore magical energy",
        "stat_bonus": {"mp": 20},
        "job_affinity": ["Wizard", "Sorcerer", "Druid"],
        "rarity": "rare",
    },
    "Shadow Step": {
        "category": "MAGIC",
        "description": "Blinks through shadow to evade attacks",
        "stat_bonus": {"mp": 6, "def": 4},
        "job_affinity": ["Sorcerer", "Spy", "Ranger"],
        "rarity": "rare",
    },
    "Nature's Wrath": {
        "category": "MAGIC",
        "description": "Commands the forces of nature against foes",
        "stat_bonus": {"mp": 10, "atk": 4},
        "job_affinity": ["Druid", "Herbalist", "Ranger"],
        "rarity": "uncommon",
    },
}


def get_skill_info(skill_name: str) -> dict | None:
    """Get information about a skill by name."""
    return SKILLS.get(skill_name)


def get_skills_by_category(category: str) -> list[str]:
    """Get all skill names in a category."""
    return [name for name, data in SKILLS.items() if data["category"] == category]


def get_skills_by_rarity(rarity: str) -> list[str]:
    """Get all skill names of a rarity level."""
    return [name for name, data in SKILLS.items() if data["rarity"] == rarity]


def get_all_categories() -> set[str]:
    """Get all unique skill categories."""
    return {data["category"] for data in SKILLS.values()}


# Chance to inherit a parent's skill
INHERIT_SKILL_CHANCE = 0.25  # 25% chance per parent skill


def _pick_skill_weighted(exclude: list[str] = None) -> str | None:
    """Pick a random skill weighted by rarity."""
    common = get_skills_by_rarity("common")
    uncommon = get_skills_by_rarity("uncommon")
    rare = get_skills_by_rarity("rare")
    
    pool = []
    pool.extend([(s, 60) for s in common])     # 60% common
    pool.extend([(s, 30) for s in uncommon])   # 30% uncommon
    pool.extend([(s, 10) for s in rare])       # 10% rare
    
    if exclude:
        pool = [(s, w) for s, w in pool if s not in exclude]
    
    if not pool:
        return None
    
    total = sum(w for _, w in pool)
    roll = random.random() * total
    cumulative = 0
    for skill, weight in pool:
        cumulative += weight
        if roll <= cumulative:
            return skill
    return pool[-1][0] if pool else None


def roll_birth_skills() -> list[str]:
    """
    Roll for skills at birth (no inheritance).
    Returns a list of 0-2 skill names.
    """
    skills = []
    
    # First skill check
    if random.random() < SKILL_BIRTH_CHANCE:
        skill = _pick_skill_weighted()
        if skill:
            skills.append(skill)
        
        # Second skill check (if first was obtained)
        if skills and random.random() < SECOND_SKILL_CHANCE:
            skill2 = _pick_skill_weighted(exclude=skills)
            if skill2:
                skills.append(skill2)
    
    return skills


def roll_birth_skills_with_inheritance(mom: "Villager", dad: "Villager") -> list[str]:
    """
    Roll for skills at birth with parent inheritance.
    Children have a chance to inherit parent skills.
    Returns a list of 0-2 skill names.
    """
    skills = []
    
    # Collect parent skills
    mom_skills = parse_skills(mom.get("skills", ""))
    dad_skills = parse_skills(dad.get("skills", ""))
    parent_skills = list(set(mom_skills + dad_skills))
    
    # First: check for inherited skills from parents
    for parent_skill in parent_skills:
        if len(skills) >= 2:
            break
        if random.random() < INHERIT_SKILL_CHANCE:
            if parent_skill not in skills:
                skills.append(parent_skill)
    
    # Then: roll for random skills as normal (if not already full)
    if len(skills) < 2 and random.random() < SKILL_BIRTH_CHANCE:
        new_skill = _pick_skill_weighted(exclude=skills)
        if new_skill:
            skills.append(new_skill)
        
        # Second random skill
        if len(skills) < 2 and random.random() < SECOND_SKILL_CHANCE:
            new_skill2 = _pick_skill_weighted(exclude=skills)
            if new_skill2:
                skills.append(new_skill2)
    
    return skills[:2]  # Max 2 skills


def parse_skills(skills_str: str | None) -> list[str]:
    """Parse comma-separated skills string to list."""
    if not skills_str:
        return []
    return [s.strip() for s in skills_str.split(",") if s.strip()]


def skills_to_string(skills: list[str]) -> str:
    """Convert skill list to comma-separated string."""
    return ", ".join(skills)


def apply_skill_bonuses(villager: "Villager") -> None:
    """
    DEPRECATED: Skills no longer add stats at birth.
    Kept for backwards compatibility.
    """
    pass  # Skills provide bonuses during actions, not at birth


# ============================================================================
# SKILL BONUSES DURING ACTIONS
# ============================================================================

def get_train_bonus(villager: "Villager") -> dict:
    """
    Get training bonuses from skills.
    Returns: {"atk_mult": float, "def_mult": float, "exp_mult": float}
    """
    skills = parse_skills(villager.get("skills", ""))
    bonus = {"atk_mult": 1.0, "def_mult": 1.0, "exp_mult": 1.0}
    
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        if cat == "COMBAT":
            bonus["atk_mult"] += 0.20  # +20% ATK gain
            bonus["def_mult"] += 0.15  # +15% DEF gain
            bonus["exp_mult"] += 0.10  # +10% EXP
        
        # Specific skills
        if skill_name == "Bladesong":
            bonus["atk_mult"] += 0.10
        if skill_name == "Bulwark":
            bonus["def_mult"] += 0.20
        if skill_name == "Battlemaster":
            bonus["exp_mult"] += 0.15
    
    return bonus


def get_study_bonus(villager: "Villager") -> dict:
    """
    Get study bonuses from skills.
    Returns: {"int_mult": float, "exp_mult": float}
    """
    skills = parse_skills(villager.get("skills", ""))
    bonus = {"int_mult": 1.0, "exp_mult": 1.0}
    
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        if cat == "KNOWLEDGE":
            bonus["int_mult"] += 0.25  # +25% INT gain
            bonus["exp_mult"] += 0.15  # +15% EXP
        
        # Specific skills
        if skill_name == "Lorekeeper":
            bonus["int_mult"] += 0.15
        if skill_name == "Arcane Attunement":
            bonus["int_mult"] += 0.10
            bonus["exp_mult"] += 0.10
        if skill_name == "Polyglot":
            bonus["exp_mult"] += 0.20
    
    return bonus


def get_work_bonus(villager: "Villager") -> dict:
    """
    Get work bonuses from skills.
    Returns: {"coin_mult": float, "exp_mult": float}
    """
    skills = parse_skills(villager.get("skills", ""))
    bonus = {"coin_mult": 1.0, "exp_mult": 1.0}
    
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        if cat == "CRAFT":
            bonus["coin_mult"] += 0.20  # +20% coin gain
            bonus["exp_mult"] += 0.10
        if cat == "SOCIAL":
            bonus["coin_mult"] += 0.10  # +10% from social skills
        
        # Specific skills
        if skill_name == "Gilded Hands":
            bonus["coin_mult"] += 0.15
        if skill_name == "Dealmaker":
            bonus["coin_mult"] += 0.20
        if skill_name == "Forgeblessed":
            bonus["coin_mult"] += 0.10
    
    return bonus


def get_socialize_bonus(villager: "Villager") -> dict:
    """
    Get socializing bonuses from skills.
    Returns: {"relation_mult": float, "rep_mult": float}
    """
    skills = parse_skills(villager.get("skills", ""))
    bonus = {"relation_mult": 1.0, "rep_mult": 1.0}
    
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        if cat == "SOCIAL":
            bonus["relation_mult"] += 0.25  # +25% relationship gain
            bonus["rep_mult"] += 0.15
        
        # Specific skills
        if skill_name == "Silver Tongue":
            bonus["relation_mult"] += 0.20
        if skill_name == "Commanding Presence":
            bonus["rep_mult"] += 0.25
        if skill_name == "Heartspark":
            bonus["relation_mult"] += 0.15
            bonus["rep_mult"] += 0.10
    
    return bonus


def get_hunt_bonus(villager: "Villager") -> dict:
    """
    Get hunting bonuses from skills.
    Returns: {"power_mult": float, "coin_mult": float, "exp_mult": float}
    """
    skills = parse_skills(villager.get("skills", ""))
    bonus = {"power_mult": 1.0, "coin_mult": 1.0, "exp_mult": 1.0}
    
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        cat = info.get("category", "")
        
        if cat == "COMBAT":
            bonus["power_mult"] += 0.15
            bonus["exp_mult"] += 0.10
        if cat == "SURVIVAL":
            bonus["power_mult"] += 0.10
            bonus["coin_mult"] += 0.15  # Better at harvesting loot
        
        # Specific skills
        if skill_name == "Hawkeye":
            bonus["power_mult"] += 0.15
        if skill_name == "Pathfinder":
            bonus["power_mult"] += 0.10
            bonus["coin_mult"] += 0.10
        if skill_name == "Bloodrage":
            bonus["power_mult"] += 0.25
    
    return bonus


def get_rest_bonus(villager: "Villager") -> dict:
    """
    Get resting bonuses from skills.
    Returns: {"hp_mult": float, "hunger_reduce": float}
    """
    skills = parse_skills(villager.get("skills", ""))
    bonus = {"hp_mult": 1.0, "hunger_reduce": 0}
    
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        
        # Specific skills
        if skill_name == "Iron Constitution":
            bonus["hp_mult"] += 0.30
        if skill_name == "Herbweaver":
            bonus["hp_mult"] += 0.20
            bonus["hunger_reduce"] += 3
        if skill_name == "Chirurgeon":
            bonus["hp_mult"] += 0.25
    
    return bonus


def get_job_from_skills(skills: list[str], available_jobs: list[str]) -> str | None:
    """
    Suggest a job based on skill affinities.
    Returns None if no matching job found.
    """
    if not skills:
        return None
    
    # Count job affinities from all skills
    job_scores: dict[str, int] = {}
    for skill_name in skills:
        info = get_skill_info(skill_name)
        if not info:
            continue
        
        for job in info["job_affinity"]:
            if job in available_jobs:
                job_scores[job] = job_scores.get(job, 0) + 1
    
    if not job_scores:
        return None
    
    # Return job with highest affinity score
    return max(job_scores, key=job_scores.get)


# get_skill_display removed (unused)


# ════════════════════════════════════════════════════════════════
# SKILL LEARNING SYSTEM (for mentoring)
# ════════════════════════════════════════════════════════════════

import json

def get_learning_progress(villager: "Villager") -> dict[str, int]:
    """
    Get the skill learning progress for a villager.
    Returns a dict of {skill_name: lesson_count}.
    Stored in villager["skill_learning"] as JSON.
    """
    raw = villager.get("skill_learning", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def set_learning_progress(villager: "Villager", progress: dict[str, int]) -> None:
    """
    Set the skill learning progress for a villager.
    """
    villager["skill_learning"] = json.dumps(progress)


def add_learning_progress(villager: "Villager", skill_name: str, amount: int = 1) -> int:
    """
    Add learning progress for a specific skill.
    Returns the new total progress for that skill.
    """
    progress = get_learning_progress(villager)
    current = progress.get(skill_name, 0)
    progress[skill_name] = current + amount
    set_learning_progress(villager, progress)
    return progress[skill_name]


def reset_learning_progress(villager: "Villager", skill_name: str) -> None:
    """
    Reset learning progress for a specific skill to 0.
    Used when learning fails.
    """
    progress = get_learning_progress(villager)
    if skill_name in progress:
        progress[skill_name] = 0
        set_learning_progress(villager, progress)


def add_skill_to_villager(villager: "Villager", skill_name: str) -> bool:
    """
    Add a skill to a villager (after completing learning).
    Returns True if skill was added, False if already had it.
    """
    # Validate skill exists
    if skill_name not in SKILLS:
        return False
    
    current_skills = parse_skills(villager.get("skills", ""))
    
    # Check if already has this skill
    if skill_name in current_skills:
        return False
    
    # Add the skill
    current_skills.append(skill_name)
    villager["skills"] = ",".join(current_skills)
    
    # Apply stat bonuses from the new skill
    info = SKILLS[skill_name]
    for stat, bonus in info.get("stat_bonus", {}).items():
        villager[stat] = villager.get(stat, 0) + bonus
    
    return True


# get_learning_display removed (unused)
