"""Utility helpers used by apply_action — level-up logic, shop-offer
generator, and the per-villager rolling action log.
"""
from __future__ import annotations

import random

from config import MAGIC_JOBS, MINOR_MAGIC_JOBS
from src.utils.world_utils import rand_int
from src.models.villager import Villager
from src.models.combat import ShopOffer


def handle_level_up(v: Villager) -> None:
    """Apply level-up logic in-place. Runs after every apply_action call."""
    from src.utils.world_utils import exp_to_next_level

    while v["exp"] >= exp_to_next_level(v["level"]):
        cost = exp_to_next_level(v["level"])
        v["exp"] -= cost
        v["level"] += 1

        v["atk"] += rand_int(1, 3)
        v["def"] += rand_int(1, 2)
        v["hp"] += rand_int(3, 6)

        # MP gain on level up based on job
        lvl_job = v.get("job", "")
        if lvl_job in MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(5, 12)
        elif lvl_job in MINOR_MAGIC_JOBS:
            v["mp"] = v.get("mp", 0) + rand_int(2, 5)
        else:
            # Non-magic jobs gain tiny MP occasionally
            if random.random() < 0.15:
                v["mp"] = v.get("mp", 0) + rand_int(1, 2)


def create_shop_offer(v: Villager) -> ShopOffer:
    """Create a tiered gear shop offer for a villager. Higher level unlocks
    better tiers (t1 → t1+t2 → t2+t3 with sampling)."""
    lvl = int(v.get("level", 1) or 1)

    t1 = [
        {"type": "Weapon",   "cost": rand_int(40, 120) + lvl * 5,
         "bonuses": [{"key": "atk", "amt": rand_int(3, 8)}]},
        {"type": "Armor",    "cost": rand_int(40, 120) + lvl * 5,
         "bonuses": [{"key": "def", "amt": rand_int(3, 8)}]},
        {"type": "Tome",     "cost": rand_int(30, 90) + lvl * 4,
         "bonuses": [{"key": "int", "amt": rand_int(2, 6)}]},
        {"type": "Elixir",   "cost": rand_int(25, 75) + lvl * 3,
         "bonuses": [{"key": "hp",  "amt": rand_int(10, 25)}]},
        {"type": "Ring",     "cost": rand_int(50, 120) + lvl * 4,
         "bonuses": [{"key": "rep", "amt": rand_int(2, 5)},
                     {"key": "int", "amt": rand_int(1, 3)}]},
        {"type": "Shield",   "cost": rand_int(60, 140) + lvl * 5,
         "bonuses": [{"key": "def", "amt": rand_int(5, 12)}]},
        {"type": "Boots",    "cost": rand_int(35, 95) + lvl * 3,
         "bonuses": [{"key": "hp",  "amt": rand_int(8, 18)}]},
        {"type": "Banner",   "cost": rand_int(55, 130) + lvl * 5,
         "bonuses": [{"key": "atk", "amt": rand_int(2, 5)},
                     {"key": "rep", "amt": rand_int(1, 2)}]},
        {"type": "Charm",    "cost": rand_int(40, 110) + lvl * 3,
         "bonuses": [{"key": "rep", "amt": rand_int(3, 8)}]},
        {"type": "Traveler's Bedroll", "cost": 75 + lvl * 4,
         "bonuses": [{"key": "hp", "amt": rand_int(10, 20)}]},
        {"type": "Mana Crystal",    "cost": rand_int(30, 80) + lvl * 3,
         "bonuses": [{"key": "mp", "amt": rand_int(8, 18)}]},
        {"type": "Spell Scroll",    "cost": rand_int(40, 100) + lvl * 4,
         "bonuses": [{"key": "mp", "amt": rand_int(5, 12)},
                     {"key": "int", "amt": rand_int(1, 3)}]},
    ]

    t2 = [
        {"type": "Vitality Belt",      "cost": 90 + lvl * 6,
         "bonuses": [{"key": "hp", "amt": rand_int(14, 28)}]},
        {"type": "Sturdy Cloak",       "cost": 110 + lvl * 7,
         "bonuses": [{"key": "hp",  "amt": rand_int(12, 22)},
                     {"key": "def", "amt": rand_int(2, 5)}]},
        {"type": "Reinforced Vest",    "cost": 130 + lvl * 8,
         "bonuses": [{"key": "hp",  "amt": rand_int(16, 30)},
                     {"key": "def", "amt": rand_int(3, 7)}]},
        {"type": "Oak Talisman",       "cost": 100 + lvl * 7,
         "bonuses": [{"key": "hp", "amt": rand_int(18, 34)}]},
        {"type": "Stamina Bracers",    "cost": 120 + lvl * 8,
         "bonuses": [{"key": "hp",  "amt": rand_int(20, 36)},
                     {"key": "atk", "amt": rand_int(1, 3)}]},
        {"type": "Ironheart Pendant",  "cost": 150 + lvl * 10,
         "bonuses": [{"key": "hp", "amt": rand_int(24, 44)}]},
        {"type": "Warhorn of Resolve", "cost": 180 + lvl * 11,
         "bonuses": [{"key": "rep", "amt": rand_int(5, 10)},
                     {"key": "atk", "amt": rand_int(2, 4)}]},
        {"type": "Mageweave Robe",     "cost": 170 + lvl * 10,
         "bonuses": [{"key": "int", "amt": rand_int(5, 10)},
                     {"key": "mp",  "amt": rand_int(12, 25)}]},
        {"type": "Knight's Buckler",   "cost": 190 + lvl * 11,
         "bonuses": [{"key": "def", "amt": rand_int(7, 14)},
                     {"key": "hp",  "amt": rand_int(8, 18)}]},
        {"type": "Duelist Rapier",     "cost": 200 + lvl * 12,
         "bonuses": [{"key": "atk", "amt": rand_int(7, 14)},
                     {"key": "rep", "amt": rand_int(2, 5)}]},
        {"type": "Scholar's Codex",    "cost": 185 + lvl * 11,
         "bonuses": [{"key": "int", "amt": rand_int(6, 12)},
                     {"key": "rep", "amt": rand_int(2, 4)}]},
    ]

    t3 = [
        {"type": "Dragonbone Plate",   "cost": 420 + lvl * 20,
         "bonuses": [{"key": "def", "amt": rand_int(14, 24)},
                     {"key": "hp",  "amt": rand_int(30, 55)}]},
        {"type": "Stormforged Aegis",  "cost": 380 + lvl * 18,
         "bonuses": [{"key": "def", "amt": rand_int(16, 26)},
                     {"key": "rep", "amt": rand_int(4, 8)}]},
        {"type": "Voidsteel Greatblade","cost": 450 + lvl * 22,
         "bonuses": [{"key": "atk", "amt": rand_int(18, 30)},
                     {"key": "hp",  "amt": rand_int(12, 25)}]},
        {"type": "Crown of Counsel",   "cost": 500 + lvl * 24,
         "bonuses": [{"key": "int", "amt": rand_int(14, 24)},
                     {"key": "rep", "amt": rand_int(8, 14)}]},
        {"type": "Relic of the Dawn",  "cost": 520 + lvl * 25,
         "bonuses": [{"key": "hp",  "amt": rand_int(45, 75)},
                     {"key": "rep", "amt": rand_int(6, 12)}]},
        {"type": "Emperor's Signet",   "cost": 600 + lvl * 28,
         "bonuses": [{"key": "rep", "amt": rand_int(10, 18)},
                     {"key": "atk", "amt": rand_int(6, 10)},
                     {"key": "def", "amt": rand_int(6, 10)}]},
        {"type": "Archmage Focus",     "cost": 580 + lvl * 27,
         "bonuses": [{"key": "int", "amt": rand_int(16, 28)},
                     {"key": "mp",  "amt": rand_int(25, 50)}]},
        {"type": "Titan's Girdle",     "cost": 540 + lvl * 26,
         "bonuses": [{"key": "hp",  "amt": rand_int(60, 95)},
                     {"key": "def", "amt": rand_int(6, 12)}]},
    ]

    if lvl <= 3:
        pool = t1 + random.sample(t2, k=min(2, len(t2)))
    elif lvl <= 8:
        pool = t1 + t2 + random.sample(t3, k=min(2, len(t3)))
    else:
        pool = t2 + t3 + random.sample(t1, k=min(3, len(t1)))

    return random.choice(pool)


def append_action_history(v: Villager, max_len: int = 5) -> None:
    """Keep a rolling history of the last `max_len` actions in v['action_log']."""
    last = v.get("last_action", "")
    if not last:
        return

    hist_str = v.get("action_log", "")
    if hist_str:
        items = hist_str.split("||")
    else:
        items = []

    items.append(last)
    if len(items) > max_len:
        items = items[-max_len:]

    v["action_log"] = "||".join(items)
