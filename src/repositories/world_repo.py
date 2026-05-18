from __future__ import annotations

import json

import config
from src.repositories.base import db_conn, init_db
from src.models.world import WorldPayload
from src.utils.world_utils import season_for_day

def compute_year_and_day(total_day: int) -> tuple[int, int]:
    """Convert a total_day counter into a (year, day_in_year) tuple."""
    if total_day < 1:
        total_day = 1
    year_index = (total_day - 1) // config.DAYS_PER_YEAR
    year = year_index + 1
    day_in_year = (total_day - 1) % config.DAYS_PER_YEAR
    return year, day_in_year


def load_day() -> int:
    """
    Read world time from SQLite (day_payload JSON).
    Returns total_day (>=1)
    """
    init_db()
    with db_conn() as conn:
        cur = conn.execute("SELECT value FROM world_state WHERE key='day_payload' LIMIT 1;")
        row = cur.fetchone()
        if not row:
            return 1
        try:
            payload = json.loads(row["value"])
            return max(1, int(payload.get("total_day", 1)))
        except Exception:
            return 1


def save_day(day: int) -> None:
    """Persist the day counter to SQLite, rolling weather if needed."""
    init_db()
    if day < 1:
        day = 1
    year, day_in_year = compute_year_and_day(day)

    # Load existing payload
    payload = load_world_payload()

    # Update day
    payload["total_day"] = int(day)
    year, day_in_year = compute_year_and_day(day)
    payload["year"] = int(year)
    payload["day_in_year"] = int(day_in_year)
    payload["season"] = season_for_day(day_in_year)

    # Roll weather BEFORE saving (avoid stale reads). Pass the season so the
    # rain-chance roll can use the season-specific base rate.
    weather_today = _roll_weather_if_needed(day, payload)
    payload["weather"] = weather_today

    save_world_payload(payload)


def load_world_payload() -> WorldPayload:
    """
    Returns the full world payload stored in world_state.day_payload.
    """
    init_db()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT value FROM world_state WHERE key='day_payload' LIMIT 1;"
        ).fetchone()
        if not row:
            return {
                "total_day": 1, "year": 1, "day_in_year": 0,
                "weather": "sunny", "next_weather_roll_day": 1,
                "season": season_for_day(0),
            }
        try:
            data = json.loads(row["value"])
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        # Defaults
        data.setdefault("total_day", 1)
        data.setdefault("year", 1)
        data.setdefault("day_in_year", 0)
        data.setdefault("weather", "sunny")
        data.setdefault("next_weather_roll_day", 1)
        # Season is derived from day_in_year — always recompute on read so old
        # payloads (pre-seasons) get a valid value without a migration step.
        data["season"] = season_for_day(int(data.get("day_in_year", 0) or 0))
        return data


def save_world_payload(payload: WorldPayload) -> None:
    """
    Persists the full world payload back to SQLite (world_state.day_payload).
    """
    init_db()
    if not isinstance(payload, dict):
        payload = {}
    total_day = int(payload.get("total_day", 1) or 1)
    if total_day < 1:
        total_day = 1

    year, day_in_year = compute_year_and_day(total_day)
    payload["total_day"] = int(total_day)
    payload["year"] = int(year)
    payload["day_in_year"] = int(day_in_year)
    payload["season"] = season_for_day(day_in_year)

    # Make sure weather keys exist
    payload.setdefault("weather", "sunny")
    payload.setdefault("next_weather_roll_day", 1)

    with db_conn() as conn:
        conn.execute(
            "UPDATE world_state SET value=? WHERE key='day_payload';",
            (json.dumps(payload, ensure_ascii=False),),
        )


def load_weather() -> str:
    """
    Returns current weather ("sunny" / "rain").
    """
    payload = load_world_payload()
    w = (payload.get("weather") or "sunny").strip().lower()
    return w if w in config.WEATHER_TYPES else "sunny"


def load_season() -> str:
    """Returns the current season slug ("spring" / "summer" / ...)."""
    payload = load_world_payload()
    s = (payload.get("season") or "").strip().lower()
    return s if s in config.SEASONS else config.SEASONS[0]


def _roll_weather_if_needed(current_day: int, payload: dict) -> str:
    """Internal helper to roll weather based on current payload.

    Rain chance is season-aware: winters are wet (often shown as snow), summers
    are dry. Falls back to the legacy global WEATHER_RAIN_CHANCE if the season
    has no rain_chance override.
    """
    day = int(current_day or payload.get("total_day", 1) or 1)
    next_roll = int(payload.get("next_weather_roll_day", 1) or 1)
    weather = (payload.get("weather") or "sunny").strip().lower()

    if day < next_roll:
        return weather

    # Season-aware rain chance. Falls back to global WEATHER_RAIN_CHANCE.
    season = (payload.get("season") or "").strip().lower()
    rain_chance = float(config.WEATHER_RAIN_CHANCE)
    s_table = config.SEASON_MODIFIERS.get(season)
    if s_table and "rain_chance" in s_table:
        try:
            rain_chance = float(s_table["rain_chance"])
        except (TypeError, ValueError):
            pass

    import random as _random
    weather = "rain" if _random.random() < rain_chance else "sunny"

    # Schedule next roll
    payload["next_weather_roll_day"] = day + int(config.WEATHER_CHANGE_DAYS or 5)
    return weather

# maybe_roll_weather removed (unused)
