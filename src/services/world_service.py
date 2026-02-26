"""High-level world orchestration: state reading, day advancement, world generation."""
from __future__ import annotations

import threading
import time

from src.models import Villager, Bank
from src.models.stats import YearlyChampions

from config import (
    DAYS_PER_YEAR,
    AUTO_SIM_ENABLED,
    AUTO_SIM_SECONDS,
    ELECTION_INTERVAL_YEARS,
    MAX_DEAD_YEARS,
)
from src.repositories.villager_repo import (
    save_villagers,
    load_villagers,
    graveyard_upsert_from_villager,
)
from src.repositories.world_repo import (
    load_day,
    save_day,
    compute_year_and_day,
    load_world_payload,
    save_world_payload,
    load_weather,
)
from src.repositories.bank_repo import load_bank, save_bank
from src.repositories.stats_repo import (
    ensure_year_row,
    update_year_daily,
    finalize_year,
    clear_yearly_stats,
)
from src.services.villager_service import generate_characters
from src.services.simulation_service import simulate_one_day
from src.services.election_service import hold_election
from src.services.building_service import (
    update_tax_policy,
    maybe_construct_building,
    maybe_upgrade_building,
    decay_buildings,
    maybe_repair_buildings,
)
from src.services.family_service import settle_inheritance_phase

_state_lock = threading.Lock()


def compute_year_champions(characters: list[Villager]) -> YearlyChampions:
    """Compute the champion categories for a given year from the character list."""
    # prefer alive, fallback to all
    pool = [c for c in characters if c.get("alive", True)]
    if not pool:
        pool = characters[:]

    def top_by(key: str):
        if not pool:
            return {"id": None, "name": None, "value": 0}
        best = max(pool, key=lambda c: int(c.get(key, 0) or 0))
        return {
            "id": int(best.get("id", 0) or 0),
            "name": best.get("name") or "\u2014",
            "value": int(best.get(key, 0) or 0),
        }

    return {
        "most_atk": top_by("atk"),
        "most_int": top_by("int"),
        "richest":  top_by("coins"),
        "top_hunter": top_by("huntWinsYear"),
    }


def get_current_state() -> tuple[list[Villager], Bank, int, int, int, str]:
    """
    Thread-safe helper: read current characters + world time.

    Returns:
        (characters, bank, year, day_in_year, total_day, weather)
    """
    with _state_lock:
        characters = load_villagers()
        total_day = load_day()
        bank = load_bank()
        weather = load_weather()

    year, day_in_year = compute_year_and_day(total_day)
    return characters, bank, year, day_in_year, total_day, weather


def load_characters_locked() -> list[Villager]:
    """Thread-safe helper: load current characters only."""
    with _state_lock:
        return load_villagers()


def advance_one_day() -> tuple:
    """
    Advance the world by one day in a thread-safe way.

    Handles year rollover, elections, tax policy, daily simulation,
    building operations, treasury interest, and dead villager pruning.

    Returns:
        (ok, message, year, day_in_year, total_day)
    """
    with _state_lock:
        characters = load_villagers()
        bank = load_bank()

        if not characters:
            return (
                False,
                "No villagers yet. Generate a population first.",
                None,
                None,
                None,
            )

        old_total_day = load_day()
        if old_total_day < 1:
            old_total_day = 1

        new_total_day = old_total_day + 1

        yr_now, day_now = compute_year_and_day(new_total_day)

        # If day_in_year == 0, we are on the first day of a new year.
        if day_now == 0:
            ensure_year_row(yr_now, treasury_start=int(bank.get("balance", 0) or 0))
        else:
            ensure_year_row(yr_now)

        # --- For yearly stats: snapshot BEFORE simulation ---
        before_ids = {int(v.get("id", 0) or 0) for v in characters if int(v.get("id", 0) or 0) > 0}
        before_alive_ids = {int(v.get("id", 0) or 0) for v in characters if v.get("alive", True) and int(v.get("id", 0) or 0) > 0}

        # Track King at the start of the day (before any elections / deaths)
        prev_king = next(
            (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
            None,
        )
        prev_king_id = prev_king.get("id") if prev_king else None

        # --- Year boundary check ---
        old_year_idx = (old_total_day - 1) // DAYS_PER_YEAR
        new_year_idx = (new_total_day - 1) // DAYS_PER_YEAR
        crossed_year = new_year_idx > old_year_idx

        if crossed_year:

            old_year = old_year_idx + 1

            # compute champions for the year that just ended
            champions = compute_year_champions(characters)
            finalize_year(old_year, champions=champions)

            # One in-world year passed -> everyone ages by +1
            for v in characters:
                if v.get("alive", True):
                    v["age"] = int(v.get("age", 0) or 0) + 1
                v["huntWinsYear"] = 0

            # Compute the new year number (1-based)
            new_year = new_year_idx + 1

            # Scheduled election: every ELECTION_INTERVAL_YEARS
            if new_year % ELECTION_INTERVAL_YEARS == 0:
                winner, election_msg = hold_election(
                    characters,
                    current_day=new_total_day,
                )
                if winner and election_msg:
                    bank["last_election_year"] = int(new_year)
                    bank["last_election_message"] = election_msg

        # Update tax policy based on current (possibly new) King traits
        bank = update_tax_policy(characters, bank, log_it=False)

        # --- Daily simulation (combat, income, deaths, etc.) ---
        characters, bank, corruption_today = simulate_one_day(characters, bank, current_day=new_total_day)

        for v in characters:
            if not v.get("alive", True) or v.get("hp", 0) <= 0:
                v["alive"] = False
                if v.get("hp", 0) < 0:
                    v["hp"] = 0

                try:
                    dd = int(v.get("death_day", 0) or 0)
                except (TypeError, ValueError):
                    dd = 0
                if dd <= 0:
                    v["death_day"] = new_total_day

        settle_inheritance_phase(characters, bank, current_day=new_total_day)

        # -------------------------------------------------------------------
        #  Emergency election: if the King died today, or no living King exists
        # -------------------------------------------------------------------
        current_king = next(
            (v for v in characters if v.get("job") == "King" and v.get("alive", True)),
            None,
        )

        king_died_today = False
        if prev_king_id is not None:
            prev_after = next(
                (v for v in characters if v.get("id") == prev_king_id),
                None,
            )
            if prev_after is not None and not prev_after.get("alive", True):
                king_died_today = True

        if (current_king is None and characters) or king_died_today:
            winner_em, emergency_msg = hold_election(
                characters,
                current_day=new_total_day,
            )
            if winner_em and emergency_msg:
                yr, _ = compute_year_and_day(new_total_day)
                bank["last_election_year"] = int(yr)
                bank["last_election_message"] = f"[Emergency] {emergency_msg}"
                bank = update_tax_policy(characters, bank, log_it=False)

        # --- Yearly stats bucket for CURRENT year (after elections/emergency) ---
        yr_now, _ = compute_year_and_day(new_total_day)

        # -------------------------------------------------------------------
        #  Buildings + treasury interest
        # -------------------------------------------------------------------
        bank, build_event = maybe_construct_building(characters, bank, new_total_day)
        bank, upgrade_event = maybe_upgrade_building(characters, bank, new_total_day)
        bank, decay_events = decay_buildings(bank, new_total_day)
        bank, repair_event = maybe_repair_buildings(characters, bank, new_total_day)

        # Treasury passive: small daily interest on bank balance
        levels = bank.get("building_levels") or {}
        lvl_treasury = int(levels.get("treasury", 0) or 0)
        if lvl_treasury > 0 and bank.get("balance", 0) > 0:
            interest_rate = 0.003 * lvl_treasury  # 0.3% per level per day
            interest = max(1, int(bank["balance"] * interest_rate))
            bank["balance"] += interest

        # Prune (archive to graveyard first)
        max_dead_days = MAX_DEAD_YEARS * DAYS_PER_YEAR

        pruned_characters = []
        for v in characters:
            if v.get("alive", True):
                pruned_characters.append(v)
                continue

            try:
                death_day = int(v.get("death_day", 0) or 0)
            except (TypeError, ValueError):
                death_day = 0

            if death_day <= 0:
                pruned_characters.append(v)
                continue

            if new_total_day - death_day < max_dead_days:
                pruned_characters.append(v)
                continue

            try:
                graveyard_upsert_from_villager(v)
            except Exception as exc:
                print("[prune] graveyard_upsert failed:", exc)

            # DO NOT append (means pruned)

        characters = pruned_characters

        # --- For yearly stats: compute immigrants/deaths TODAY ---
        after_ids = {int(v.get("id", 0) or 0) for v in characters if int(v.get("id", 0) or 0) > 0}
        after_alive_ids = {int(v.get("id", 0) or 0) for v in characters if v.get("alive", True) and int(v.get("id", 0) or 0) > 0}

        immigrants_today = len(after_ids - before_ids)
        deaths_today = len(before_alive_ids - after_alive_ids)

        final_king = next((v for v in characters if v.get("job") == "King" and v.get("alive", True)), None)
        king_id = int(final_king.get("id", 0) or 0) if final_king else None
        king_name = final_king.get("name") if final_king else None

        update_year_daily(
            year=yr_now,
            king_id=king_id,
            king_name=king_name,
            deaths_today=deaths_today,
            immigrants_today=immigrants_today,
            tax_rate_today=float(bank.get("tax_rate", 0.10) or 0.10),
            treasury_end=int(bank.get("balance", 0) or 0),
            corruption_today=corruption_today,
        )

        # Persist updated state
        save_villagers(characters)
        save_day(new_total_day)
        save_bank(bank)

    year, day_in_year = compute_year_and_day(new_total_day)
    msg = f"Simulated +1 day of actions (Year {year}, Day {day_in_year})."

    return True, msg, year, day_in_year, new_total_day


def generate_new_world(count: int = 50) -> tuple[int, int]:
    """
    Reset the world: generate a fresh population, reset day to 1,
    clear bank and stats.

    Returns:
        (year, day_in_year)
    """
    with _state_lock:
        characters = generate_characters(count)
        save_villagers(characters)

        # total_day = 1 -> Year 1, Day 0
        save_day(1)

        # Reset village bank
        save_bank({
            "tax_rate": 0.10,
            "balance": 0,
            "building_levels": {},
            "building_health": {},
            "last_election_year": None,
            "last_election_message": "",
        })

        clear_yearly_stats()

        # Reset weather to default
        payload = load_world_payload()
        payload["weather"] = "sunny"
        payload["next_weather_roll_day"] = 1
        save_world_payload(payload)

    return compute_year_and_day(1)


def auto_simulation_loop() -> None:
    """
    Background loop: automatically advance the world every AUTO_SIM_SECONDS.
    Runs as long as the process is alive and AUTO_SIM_ENABLED is True.
    """
    if not AUTO_SIM_ENABLED:
        return

    while True:
        time.sleep(AUTO_SIM_SECONDS)
        try:
            advance_one_day()
        except Exception as exc:
            print("[auto_simulation_loop] Error:", exc)
