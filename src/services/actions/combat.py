"""Combat actions: train, hunt, spar, drill."""
from __future__ import annotations

import random

from src.utils.world_utils import rand_int, season_for_total_day, season_modifier
from src.services.building_service import get_building_level
from src.services.relationship_service import adjust_relationship
from src.services.skill_service import get_train_bonus
from src.models.villager import Villager
from src.models.bank import Bank


def apply_train(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    delta_atk    = rand_int(1, 3)
    delta_def    = rand_int(1, 2)
    delta_hp     = rand_int(0, 2)
    delta_hunger = rand_int(5, 12)
    delta_exp    = rand_int(2, 5)

    w = (weather or "sunny").strip().lower()
    if w == "rain":
        delta_atk = max(1, int(round(delta_atk * 0.90)))
        delta_def = max(1, int(round(delta_def * 0.90)))
        delta_hunger += 1

    if bank is not None:
        lvl_barracks   = get_building_level(bank, "barracks")
        lvl_blacksmith = get_building_level(bank, "blacksmith")
        lvl_granary    = get_building_level(bank, "granary")
        lvl_clinic     = get_building_level(bank, "clinic")

        bonus_mult = 1 + 0.20 * lvl_barracks + 0.15 * lvl_blacksmith
        delta_atk = max(1, int(round(delta_atk * bonus_mult)))
        delta_def = max(1, int(round(delta_def * bonus_mult)))

        if lvl_clinic > 0:
            delta_hp += lvl_clinic

        if lvl_granary > 0:
            delta_hunger = max(
                1, int(round(delta_hunger * (1 - 0.08 * lvl_granary)))
            )

    # Skill bonuses for training
    skill_bonus = get_train_bonus(v)
    delta_atk = max(1, int(round(delta_atk * skill_bonus["atk_mult"])))
    delta_def = max(1, int(round(delta_def * skill_bonus["def_mult"])))
    delta_exp = max(1, int(round(delta_exp * skill_bonus["exp_mult"])))

    v["atk"]    += delta_atk
    v["def"]    += delta_def
    v["hp"]     += delta_hp
    v["hunger"] += delta_hunger
    v["exp"]    += delta_exp


def apply_hunt(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    from src.services.combat_service import create_enemy_for, resolve_combat

    enemy  = create_enemy_for(v)
    combat = resolve_combat(v, enemy, bank, weather=weather)

    won_hunt = (combat["outcome"] == "WIN") or (combat["outcome"] == "DEAD" and combat.get("victory", False))
    if won_hunt:
        v["huntWins"] = int(v.get("huntWins", 0) or 0) + 1
        v["huntWinsYear"] = int(v.get("huntWinsYear", 0) or 0) + 1

        # Phase 2: artifact drop on kill (live killers only — drops on a
        # post-mortem victory go nowhere because the corpse can't carry it).
        if v.get("alive", True):
            try:
                from src.services.artifact_service import drop_for_kill
                from src.services.chronicle_service import record_artifact_drop
                from src.repositories.world_repo import load_day

                day_for_drop = current_day if current_day is not None else load_day()
                drop = drop_for_kill(v, enemy, day_for_drop)
                if drop:
                    record_artifact_drop(
                        killer=v,
                        enemy=enemy,
                        template=drop["template"],
                        equipped=drop["equipped"],
                        day=int(day_for_drop),
                    )
            except Exception:
                # Drops are decorative — never break the sim loop.
                pass

    if combat["outcome"] == "WIN":
        hunger_delta = -rand_int(5, 14)

        if bank is not None:
            lvl_granary = get_building_level(bank, "granary")
            if lvl_granary > 0:
                hunger_delta = int(round(hunger_delta * (1 + 0.10 * lvl_granary)))

        v["hunger"] += hunger_delta

        # Meat/hides from the kill go into the town stockpile.
        meat_gain = 0
        if bank is not None:
            from config import HUNT_FOOD_PER_KILL
            tier_mult = {"common": 1, "elite": 2, "legendary": 3}.get(
                str(enemy.get("tier", "common")).lower(), 1
            )
            # Seasonal hunt yield: game is fat in autumn, scarce in winter.
            season_now = season_for_total_day(int(current_day or 0))
            hunt_mult = season_modifier(season_now, "hunt_food_mult", 1.0)
            meat_gain = max(1, int(round(HUNT_FOOD_PER_KILL * tier_mult * hunt_mult)))
            stock = bank.setdefault("resources", {"food": 0, "wood": 0, "stone": 0, "iron": 0})
            stock["food"] = int(stock.get("food", 0)) + meat_gain

        tax_paid = combat.get("taxPaid", 0)
        extras = []
        if tax_paid > 0:
            extras.append(f"paid {tax_paid} tax")
        if meat_gain > 0:
            extras.append(f"+{meat_gain} food")
        tail = f", {', '.join(extras)}" if extras else ""
        v["last_action"] = f"hunt (WIN vs {enemy['tier']} {enemy['name']}{tail})"

        if not v.get("alive", True) or v.get("hp", 0) <= 0:
            v["alive"] = False
            v["hp"] = 0
            v["last_action"] = f"dead (won hunt vs {enemy['tier']} {enemy['name']}, died from wounds)"

    elif combat["outcome"] == "DEAD":
        if combat.get("victory", False):
            v["last_action"] = f"dead (won vs {enemy['tier']} {enemy['name']} but died from wounds)"
        else:
            v["last_action"] = f"dead (hunt vs {enemy['tier']} {enemy['name']})"

        v["hunger"] += rand_int(3, 10)

    else:  # "LOSS"
        hunger_delta = rand_int(3, 10)

        if bank is not None:
            lvl_granary = get_building_level(bank, "granary")
            if lvl_granary > 0:
                hunger_delta = max(1, int(round(hunger_delta * (1 - 0.05 * lvl_granary))))

        v["hunger"] += hunger_delta
        v["last_action"] = f"hunt (LOSS vs {enemy['tier']} {enemy['name']})"


def apply_spar(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    v_id = v.get("id")
    v_age = int(v.get("age", 0) or 0)
    military_jobs = ["Soldier", "Guard", "Captain", "Commander", "Scout", "Hunter", "Spy"]

    candidates = []
    if all_characters:
        candidates = [
            o for o in all_characters
            if o.get("id") != v_id
            and o.get("alive", True)
            and int(o.get("age", 0) or 0) >= 17
            and int(o.get("hp", 0) or 0) >= 30
        ]

    if not candidates:
        v["atk"] += rand_int(0, 1)
        v["def"] += rand_int(0, 1)
        v["hp"]  -= rand_int(0, 2)
        v["hunger"] += rand_int(4, 8)
        v["exp"] += rand_int(1, 3)
        v["last_action"] = "spar (no partner — solo drills)"
        if v.get("hp", 0) <= 0 and v.get("alive", True):
            v["alive"] = False
            v["hp"] = 0
            v["death_day"] = int(current_day or 0)
            v["last_action"] = "died from solo spar drills (training accident)"
            try:
                from src.services.chronicle_service import record_death
                record_death(v, cause="training accident", day=int(current_day or 0))
            except Exception:
                pass
        return

    def spar_score(o):
        age_close = -abs(int(o.get("age", 0) or 0) - v_age)
        mil_bonus = 5 if o.get("job") in military_jobs else 0
        return age_close + mil_bonus + random.random() * 2
    partner = max(candidates, key=spar_score)

    atk_gain = rand_int(1, 2)
    def_gain = rand_int(1, 2)
    exp_gain = rand_int(2, 4)
    hp_loss = rand_int(1, 4)
    hunger_gain = rand_int(5, 10)

    if bank is not None:
        lvl_b = get_building_level(bank, "barracks")
        if lvl_b > 0:
            atk_gain += lvl_b // 2
            def_gain += lvl_b // 2
            exp_gain += lvl_b

    v["atk"] += atk_gain
    v["def"] += def_gain
    v["exp"] += exp_gain
    v["hp"]  -= hp_loss
    v["hunger"] += hunger_gain

    partner["atk"] = int(partner.get("atk", 0) or 0) + atk_gain
    partner["def"] = int(partner.get("def", 0) or 0) + def_gain
    partner["exp"] = int(partner.get("exp", 0) or 0) + exp_gain
    partner["hp"]  = int(partner.get("hp", 0) or 0) - hp_loss
    partner["hunger"] = int(partner.get("hunger", 0) or 0) + hunger_gain

    rel_delta = rand_int(3, 8)
    adjust_relationship(v, partner, rel_delta)
    adjust_relationship(partner, v, rel_delta)

    v["last_action"] = (
        f"spar with {partner['name']} "
        f"(+{atk_gain} ATK, +{def_gain} DEF, +{rel_delta} relation)"
    )

    # Training accidents — either partner can die from accumulated damage.
    partner_name = partner.get("name", "a sparring partner")
    v_name = v.get("name", "a sparring partner")
    day_for_death = int(current_day or 0)
    try:
        from src.services.chronicle_service import record_death
    except Exception:
        record_death = None

    if v.get("hp", 0) <= 0 and v.get("alive", True):
        v["alive"] = False
        v["hp"] = 0
        v["death_day"] = day_for_death
        v["last_action"] = f"died from spar with {partner_name} (training accident)"
        if record_death is not None:
            try:
                record_death(v, cause=f"sparring accident with {partner_name}", day=day_for_death)
            except Exception:
                pass

    if partner.get("hp", 0) <= 0 and partner.get("alive", True):
        partner["alive"] = False
        partner["hp"] = 0
        partner["death_day"] = day_for_death
        partner["last_action"] = f"died from spar with {v_name} (training accident)"
        if record_death is not None:
            try:
                record_death(partner, cause=f"sparring accident with {v_name}", day=day_for_death)
            except Exception:
                pass


def apply_drill(
    v: Villager,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    lvl_b = get_building_level(bank, "barracks") if bank is not None else 0
    if lvl_b <= 0:
        v["atk"] += rand_int(1, 2)
        v["def"] += rand_int(1, 2)
        v["hunger"] += rand_int(6, 10)
        v["exp"] += rand_int(2, 4)
        v["last_action"] = "drill (no barracks — basic training)"
        return

    base = 1 + lvl_b
    atk_gain = base + rand_int(0, 1)
    def_gain = base + rand_int(0, 1)
    exp_gain = rand_int(3, 6) + lvl_b * 2
    hp_gain = lvl_b
    hunger_gain = rand_int(8, 14)

    if bank is not None:
        lvl_smith = get_building_level(bank, "blacksmith")
        if lvl_smith > 0:
            atk_gain += 1

    skill_bonus = get_train_bonus(v)
    atk_gain = max(1, int(round(atk_gain * skill_bonus["atk_mult"])))
    def_gain = max(1, int(round(def_gain * skill_bonus["def_mult"])))
    exp_gain = max(1, int(round(exp_gain * skill_bonus["exp_mult"])))

    v["atk"] += atk_gain
    v["def"] += def_gain
    v["hp"]  += hp_gain
    v["exp"] += exp_gain
    v["hunger"] += hunger_gain

    v["last_action"] = (
        f"drill at barracks Lvl {lvl_b} "
        f"(+{atk_gain} ATK, +{def_gain} DEF)"
    )
