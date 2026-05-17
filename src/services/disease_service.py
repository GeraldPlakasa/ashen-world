"""Persistent disease state for villagers.

Per-villager illness with infection chains, immunity after recovery, and
healer-driven cures. Three tiers (cough/fever/plague) defined in config.
Daily phase progresses each sick villager: HP loss, lethality, recovery.
Transmission rolls live in action_service hooks (socialize/hangout/etc.).
"""
from __future__ import annotations

import json
import random
from typing import Iterable

from config import (
    DISEASES,
    DISEASE_AMBIENT_CHANCE,
    DISEASE_AMBIENT_WEIGHTS,
    HEALER_JOBS,
)
from src.models.villager import Villager
from src.models.bank import Bank


def _immunities(v: Villager) -> set[str]:
    """Parse the JSON immunities field into a set."""
    raw = v.get("immunities") or "[]"
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        data = []
    if not isinstance(data, list):
        return set()
    return {str(x) for x in data if x}


def _store_immunities(v: Villager, imms: Iterable[str]) -> None:
    v["immunities"] = json.dumps(sorted(set(imms)))


def is_sick(v: Villager) -> bool:
    return bool((v.get("disease") or "").strip())


def has_immunity(v: Villager, disease: str) -> bool:
    return disease in _immunities(v)


def _grant_immunity(v: Villager, disease: str) -> None:
    imms = _immunities(v)
    imms.add(disease)
    _store_immunities(v, imms)


def infect(v: Villager, disease: str, current_day: int) -> bool:
    """Set v's disease state. Returns True if infection actually took.
    Won't infect dead, already-sick, or immune villagers.
    """
    if not v.get("alive", True):
        return False
    if disease not in DISEASES:
        return False
    if is_sick(v):
        return False
    if has_immunity(v, disease):
        return False
    v["disease"] = disease
    v["disease_day"] = int(current_day)
    return True


def _pick_ambient_disease() -> str:
    """Weighted pick among the ambient disease pool."""
    keys = list(DISEASE_AMBIENT_WEIGHTS.keys())
    weights = [DISEASE_AMBIENT_WEIGHTS[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def try_transmit(source: Villager, target: Villager, current_day: int, kind: str = "contact") -> bool:
    """Roll for transmission from a sick source to an exposed target.
    `kind`: "contact" (socialize/hangout/work near) or "spouse" (cohabiting).
    Returns True if infection occurred.
    """
    if not source or not target:
        return False
    disease = (source.get("disease") or "").strip()
    if not disease or disease not in DISEASES:
        return False
    if not target.get("alive", True) or is_sick(target) or has_immunity(target, disease):
        return False
    rates = DISEASES[disease]
    rate = rates["spouse_transmission"] if kind == "spouse" else rates["transmission_rate"]
    if random.random() < rate:
        return infect(target, disease, current_day)
    return False


def cure(patient: Villager, healer: Villager | None = None, current_day: int = 0) -> str | None:
    """Clear the patient's disease and grant them immunity. Returns the
    disease slug that was cured, or None if no effect.
    """
    disease = (patient.get("disease") or "").strip()
    if not disease:
        return None
    patient["disease"] = ""
    patient["disease_day"] = 0
    _grant_immunity(patient, disease)
    return disease


def cure_chance(patient: Villager, healer: Villager, bank: Bank | None) -> float:
    """Per-attempt cure chance modulated by healer INT and Clinic/Temple."""
    disease = (patient.get("disease") or "").strip()
    if not disease or disease not in DISEASES:
        return 0.0
    base = DISEASES[disease]["cure_chance_base"]

    # INT scaling: every 25 INT adds +10%, capped at +40%
    intel = max(0, int(healer.get("int", 0) or 0))
    int_bonus = min(0.40, (intel / 25) * 0.10)

    # Building bonuses
    bldg_bonus = 0.0
    if bank is not None:
        try:
            from src.services.building_service import get_building_level
            clinic_lvl = int(get_building_level(bank, "clinic") or 0)
            temple_lvl = int(get_building_level(bank, "temple") or 0)
            bldg_bonus = 0.08 * clinic_lvl
            if healer.get("job") in ("Cleric", "Priest"):
                bldg_bonus += 0.05 * temple_lvl
        except Exception:
            pass

    return max(0.0, min(0.95, base + int_bonus + bldg_bonus))


def find_sick_in_circle(healer: Villager, characters: list[Villager], limit: int = 1) -> list[Villager]:
    """Pick up to `limit` sick villagers a healer might attend to.
    Priority: spouse → family → relationship score > 30 → anyone sick.
    """
    spouse_id = int(healer.get("spouseId", 0) or 0)
    fam = (healer.get("family") or "").strip()
    sid = int(healer.get("id", 0) or 0)

    def is_candidate(v: Villager) -> bool:
        if v is healer:
            return False
        if not v.get("alive", True):
            return False
        return is_sick(v)

    # 1) spouse
    if spouse_id > 0:
        for v in characters:
            if int(v.get("id", 0) or 0) == spouse_id and is_candidate(v):
                return [v]

    # 2) same family
    fam_sick = [v for v in characters if is_candidate(v) and (v.get("family") or "").strip() == fam]
    if fam_sick:
        return fam_sick[:limit]

    # 3) anyone sick
    other_sick = [v for v in characters if is_candidate(v)]
    if other_sick:
        # Cheap deterministic-ish picks: shuffle by id mod for variety
        other_sick.sort(key=lambda v: (int(v.get("id", 0) or 0) + sid) % 100)
        return other_sick[:limit]

    return []


def daily_disease_phase(characters: list[Villager], bank: Bank, current_day: int) -> dict:
    """Daily progression:
      - Each sick villager loses HP, may die (lethal_chance), may recover.
      - Ambient infection: very small chance per villager per day.
      - Clinic adds a passive flat-recovery boost.
    Returns a small summary {newly_sick, recovered, deaths}.
    """
    summary = {"newly_sick": 0, "recovered": 0, "deaths": 0}

    try:
        from src.services.building_service import get_building_level
        clinic_lvl = int(get_building_level(bank, "clinic") or 0) if bank else 0
    except Exception:
        clinic_lvl = 0
    passive_recover_bonus = 0.04 * clinic_lvl  # Lv1=+4%, Lv2=+8%, Lv3=+12%

    for v in characters:
        if not v.get("alive", True):
            continue

        disease = (v.get("disease") or "").strip()
        if disease and disease in DISEASES:
            params = DISEASES[disease]
            day_caught = int(v.get("disease_day", 0) or 0)
            days_sick = max(0, current_day - day_caught)

            # HP drain
            lo, hi = params["daily_hp_loss"]
            dmg = random.randint(lo, hi)
            # Healers in good buildings shouldn't die to coughs trivially —
            # high-HP villagers tank more easily.
            v["hp"] = max(0, int(v.get("hp", 0) or 0) - dmg)

            # Lethality (chance per day, only if past midpoint of disease arc)
            if days_sick >= params["duration_days"] // 2:
                if random.random() < params["lethal_chance"]:
                    v["hp"] = 0
                    v["alive"] = False
                    v["death_day"] = int(current_day)
                    last = v.get("last_action") or ""
                    v["last_action"] = f"died of {params['name'].lower()}"
                    summary["deaths"] += 1
                    # Try to chronicle the death
                    try:
                        from src.services.chronicle_service import record_death
                        record_death(v, cause=params["name"].lower(), day=int(current_day))
                    except Exception:
                        pass
                    continue

            # Auto-death from HP zero (separate from lethal_chance — happens
            # if HP drain alone pushes them to zero)
            if v.get("hp", 0) <= 0 and v.get("alive", True):
                v["alive"] = False
                v["hp"] = 0
                v["death_day"] = int(current_day)
                v["last_action"] = f"succumbed to {params['name'].lower()}"
                summary["deaths"] += 1
                try:
                    from src.services.chronicle_service import record_death
                    record_death(v, cause=params["name"].lower(), day=int(current_day))
                except Exception:
                    pass
                continue

            # Recovery — chance rises past full duration, and Clinic helps.
            recover_p = params["recover_chance"] + passive_recover_bonus
            if days_sick >= params["duration_days"]:
                recover_p += 0.20
            if random.random() < recover_p:
                _grant_immunity(v, disease)
                v["disease"] = ""
                v["disease_day"] = 0
                last = v.get("last_action") or ""
                v["last_action"] = (last + " / " if last else "") + f"recovered from {params['name'].lower()}"
                summary["recovered"] += 1
        else:
            # Ambient infection check (only for non-sick, non-immune)
            if random.random() < DISEASE_AMBIENT_CHANCE:
                disease = _pick_ambient_disease()
                if not has_immunity(v, disease):
                    if infect(v, disease, current_day):
                        summary["newly_sick"] += 1
                        last = v.get("last_action") or ""
                        v["last_action"] = (last + " / " if last else "") + f"caught {DISEASES[disease]['name'].lower()}"
                        try:
                            from src.services.chronicle_service import record_disease_outbreak
                            record_disease_outbreak(v, disease, int(current_day))
                        except Exception:
                            pass

    return summary
