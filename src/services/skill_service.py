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

# Chance for a newborn to have any skill (very rare)
SKILL_BIRTH_CHANCE = 0.08  # 8% chance to get at least one skill

# If has skill, chance to get a second one
SECOND_SKILL_CHANCE = 0.15  # 15% chance for second skill if first acquired

# Skill definitions with effects and job affinities
SKILLS = {
    # COMBAT SKILLS
    "Swordsmanship": {
        "category": "COMBAT",
        "description": "Natural talent with bladed weapons",
        "stat_bonus": {"atk": 5},
        "job_affinity": ["Soldier", "Guard", "Knight", "Commander", "Captain"],
        "rarity": "common",
    },
    "Archery": {
        "category": "COMBAT",
        "description": "Exceptional aim with ranged weapons",
        "stat_bonus": {"atk": 3, "def": 2},
        "job_affinity": ["Archer", "Ranger", "Hunter"],
        "rarity": "common",
    },
    "Berserker": {
        "category": "COMBAT",
        "description": "Fearless fury in battle",
        "stat_bonus": {"atk": 8, "def": -2},
        "job_affinity": ["Soldier", "Guard", "Hunter"],
        "rarity": "rare",
    },
    "Shield Master": {
        "category": "COMBAT",
        "description": "Expert defensive techniques",
        "stat_bonus": {"def": 6, "hp": 10},
        "job_affinity": ["Guard", "Knight", "Soldier"],
        "rarity": "uncommon",
    },
    "Tactician": {
        "category": "COMBAT",
        "description": "Strategic mind for warfare",
        "stat_bonus": {"int": 4, "atk": 2},
        "job_affinity": ["Commander", "Captain", "Advisor"],
        "rarity": "rare",
    },

    # CRAFT SKILLS
    "Smithing": {
        "category": "CRAFT",
        "description": "Mastery of metalwork",
        "stat_bonus": {"atk": 2, "def": 2},
        "job_affinity": ["Blacksmith", "Armorer", "Weaponsmith"],
        "rarity": "common",
    },
    "Alchemy": {
        "category": "CRAFT",
        "description": "Knowledge of potions and elixirs",
        "stat_bonus": {"int": 4, "hp": 5},
        "job_affinity": ["Alchemist", "Healer", "Apothecary"],
        "rarity": "uncommon",
    },
    "Artisan": {
        "category": "CRAFT",
        "description": "Skilled in fine craftsmanship",
        "stat_bonus": {"rep": 3, "int": 2},
        "job_affinity": ["Jeweler", "Tailor", "Carpenter", "Potter"],
        "rarity": "common",
    },
    "Engineering": {
        "category": "CRAFT",
        "description": "Understanding of complex mechanisms",
        "stat_bonus": {"int": 5, "def": 2},
        "job_affinity": ["Engineer", "Architect", "Mason"],
        "rarity": "rare",
    },
    "Brewing": {
        "category": "CRAFT",
        "description": "Art of making drinks and potions",
        "stat_bonus": {"rep": 4, "hp": 3},
        "job_affinity": ["Brewer", "Innkeeper", "Cook"],
        "rarity": "common",
    },

    # SOCIAL SKILLS
    "Charisma": {
        "category": "SOCIAL",
        "description": "Natural charm and persuasion",
        "stat_bonus": {"rep": 6},
        "job_affinity": ["Merchant", "Noble", "Bard", "Diplomat"],
        "rarity": "uncommon",
    },
    "Leadership": {
        "category": "SOCIAL",
        "description": "Born to command others",
        "stat_bonus": {"rep": 4, "int": 3},
        "job_affinity": ["Commander", "Captain", "Noble", "Advisor"],
        "rarity": "rare",
    },
    "Negotiation": {
        "category": "SOCIAL",
        "description": "Skilled at making deals",
        "stat_bonus": {"rep": 5, "int": 2},
        "job_affinity": ["Merchant", "Trader", "Diplomat"],
        "rarity": "uncommon",
    },
    "Intimidation": {
        "category": "SOCIAL",
        "description": "Imposing presence that demands respect",
        "stat_bonus": {"rep": 3, "atk": 2},
        "job_affinity": ["Guard", "Soldier", "Spy", "Assassin"],
        "rarity": "uncommon",
    },
    "Inspiration": {
        "category": "SOCIAL",
        "description": "Ability to motivate and inspire",
        "stat_bonus": {"rep": 5, "hp": 5},
        "job_affinity": ["Bard", "Priest", "Noble", "Advisor"],
        "rarity": "rare",
    },

    # SURVIVAL SKILLS
    "Tracking": {
        "category": "SURVIVAL",
        "description": "Expert at following trails",
        "stat_bonus": {"def": 3, "atk": 2},
        "job_affinity": ["Hunter", "Ranger", "Scout", "Forester"],
        "rarity": "common",
    },
    "Herbalism": {
        "category": "SURVIVAL",
        "description": "Knowledge of medicinal plants",
        "stat_bonus": {"hp": 8, "int": 2},
        "job_affinity": ["Healer", "Druid", "Apothecary", "Farmer"],
        "rarity": "common",
    },
    "Endurance": {
        "category": "SURVIVAL",
        "description": "Exceptional stamina and resilience",
        "stat_bonus": {"hp": 15, "def": 3},
        "job_affinity": ["Soldier", "Miner", "Farmer", "Shepherd"],
        "rarity": "uncommon",
    },
    "Navigation": {
        "category": "SURVIVAL",
        "description": "Never gets lost, reads terrain well",
        "stat_bonus": {"def": 4, "int": 2},
        "job_affinity": ["Scout", "Ranger", "Sailor", "Explorer"],
        "rarity": "uncommon",
    },
    "Animal Handling": {
        "category": "SURVIVAL",
        "description": "Natural bond with animals",
        "stat_bonus": {"def": 2, "rep": 3},
        "job_affinity": ["Shepherd", "Stablemaster", "Hunter", "Farmer"],
        "rarity": "common",
    },

    # KNOWLEDGE SKILLS
    "Scholarly": {
        "category": "KNOWLEDGE",
        "description": "Quick learner with vast knowledge",
        "stat_bonus": {"int": 6},
        "job_affinity": ["Scholar", "Scribe", "Advisor", "Librarian"],
        "rarity": "uncommon",
    },
    "Arcane Sense": {
        "category": "KNOWLEDGE",
        "description": "Sensitivity to magical energies",
        "stat_bonus": {"int": 5, "hp": 5},
        "job_affinity": ["Druid", "Alchemist", "Priest"],
        "rarity": "rare",
    },
    "Medicine": {
        "category": "KNOWLEDGE",
        "description": "Understanding of healing arts",
        "stat_bonus": {"int": 4, "hp": 8},
        "job_affinity": ["Healer", "Apothecary", "Priest"],
        "rarity": "uncommon",
    },
    "Linguistics": {
        "category": "KNOWLEDGE",
        "description": "Talent for languages and communication",
        "stat_bonus": {"int": 4, "rep": 3},
        "job_affinity": ["Scribe", "Diplomat", "Merchant", "Scholar"],
        "rarity": "uncommon",
    },
    "History": {
        "category": "KNOWLEDGE",
        "description": "Deep understanding of the past",
        "stat_bonus": {"int": 5, "rep": 2},
        "job_affinity": ["Scholar", "Advisor", "Scribe", "Noble"],
        "rarity": "uncommon",
    },
}

# Rarity weights for skill selection
RARITY_WEIGHTS = {
    "common": 60,
    "uncommon": 30,
    "rare": 10,
}


def get_skill_info(skill_name: str) -> dict | None:
    """Get information about a specific skill."""
    return SKILLS.get(skill_name)


def get_skills_by_category(category: str) -> list[str]:
    """Get all skill names in a category."""
    return [name for name, data in SKILLS.items() if data["category"] == category]


def get_skills_by_rarity(rarity: str) -> list[str]:
    """Get all skill names of a rarity."""
    return [name for name, data in SKILLS.items() if data["rarity"] == rarity]


def roll_birth_skills() -> list[str]:
    """
    Roll for skills when a villager is born.
    Returns a list of 0-2 skill names.
    """
    skills = []
    
    # First skill check
    if random.random() >= SKILL_BIRTH_CHANCE:
        return skills  # No skills
    
    # Got first skill - select based on rarity
    first_skill = _select_random_skill()
    if first_skill:
        skills.append(first_skill)
    
    # Check for second skill
    if skills and random.random() < SECOND_SKILL_CHANCE:
        second_skill = _select_random_skill(exclude=skills)
        if second_skill:
            skills.append(second_skill)
    
    return skills


def _select_random_skill(exclude: list[str] | None = None) -> str | None:
    """Select a random skill based on rarity weights."""
    exclude = exclude or []
    
    # Build weighted pool
    pool = []
    for skill_name, skill_data in SKILLS.items():
        if skill_name in exclude:
            continue
        rarity = skill_data["rarity"]
        weight = RARITY_WEIGHTS.get(rarity, 10)
        pool.extend([skill_name] * weight)
    
    if not pool:
        return None
    
    return random.choice(pool)


def apply_skill_bonuses(v: Villager) -> None:
    """Apply stat bonuses from villager's skills."""
    skills_str = v.get("skills", "")
    if not skills_str:
        return
    
    skill_list = parse_skills(skills_str)
    
    for skill_name in skill_list:
        skill_data = SKILLS.get(skill_name)
        if not skill_data:
            continue
        
        bonuses = skill_data.get("stat_bonus", {})
        for stat, amount in bonuses.items():
            current = int(v.get(stat, 0) or 0)
            v[stat] = current + amount


def get_job_from_skills(skill_list: list[str], available_jobs: list[str]) -> str | None:
    """
    Suggest a job based on skills.
    Returns the best matching job or None.
    """
    if not skill_list:
        return None
    
    # Collect all job affinities from skills
    job_scores = {}
    for skill_name in skill_list:
        skill_data = SKILLS.get(skill_name)
        if not skill_data:
            continue
        
        for job in skill_data.get("job_affinity", []):
            if job in available_jobs:
                job_scores[job] = job_scores.get(job, 0) + 1
    
    if not job_scores:
        return None
    
    # Return job with highest score (most skill matches)
    best_job = max(job_scores.keys(), key=lambda j: job_scores[j])
    return best_job


def parse_skills(skills_str: str) -> list[str]:
    """Parse skills string to list."""
    if not skills_str:
        return []
    if isinstance(skills_str, list):
        return skills_str
    return [s.strip() for s in skills_str.split(",") if s.strip()]


def skills_to_string(skills: list[str]) -> str:
    """Convert skills list to comma-separated string."""
    return ", ".join(skills)


def get_skill_display(v: Villager) -> list[dict]:
    """Get skills formatted for display."""
    skills_str = v.get("skills", "")
    skill_list = parse_skills(skills_str)
    
    result = []
    for skill_name in skill_list:
        skill_data = SKILLS.get(skill_name)
        if skill_data:
            result.append({
                "name": skill_name,
                "category": skill_data["category"],
                "description": skill_data["description"],
                "rarity": skill_data["rarity"],
            })
    
    return result


def get_all_categories() -> list[str]:
    """Get all skill categories."""
    return ["COMBAT", "CRAFT", "SOCIAL", "SURVIVAL", "KNOWLEDGE"]
