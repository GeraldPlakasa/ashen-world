# Ashen World

A living-village simulation built with Flask. Manage villagers, elections, buildings, and a growing treasury through a web dashboard with real-time updates.

## Features
- Kingdom dashboard with sortable/filterable villager table and pinned character card
- Admin control hall to reset the world, tick days, and run auto-simulation
- Player-made characters (one per user) with custom trait + random trait
- Simulation loop: daily actions, hunger, relationships, marriage/children, leadership elections, corruption, assassination, inheritance for player characters
- Economy and buildings: tax policy tied to king traits, treasury balance, construct/upgrade/repair, health decay
- JSON API `/api/state` feeding auto-refresh UI for state and building KPIs
- SQLite persistence with automatic schema setup and legacy CSV compatibility helpers

## Project Structure
- `app.py` — Flask entrypoint, routes, background auto-sim thread, session/auth handling
- `config.py` — world constants (admin credentials, auto-sim interval, traits, jobs, buildings, economy rules)
- `storage.py` — SQLite helpers and migrations for villagers, users, world state, bank state, yearly stats (aliases `save_to_csv`/`load_from_csv`)
- `villagers.py`, `villagers_social.py`, `buildings.py`, `world_utils.py` — simulation logic (actions, elections, inheritance, buildings, helpers)
- `templates/` — landing dashboard, admin, leaderboard, auth, and create-character pages
- `static/css/style.css`, `static/js/main.js` — styling and front-end interactions (sorting/filtering, pinned card, auto-refresh controls)
- `data/` — runtime database `ashen_world.sqlite3` (created on first run)

## Requirements
- Python 3.10+
- pip/venv
- Dependencies: `Flask`, `Werkzeug` (SQLite is stdlib)

## Setup
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install Flask Werkzeug
# Optional: pip freeze > requirements.txt
```

## Run
```bash
python app.py
# visit http://localhost:5000
```
- Admin login from `config.py`: `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- Register a user via `/register` to create a player character (max 1 per user)

## Typical Flow
1) Log in as admin → **Generate** to spawn 50 villagers and reset to Day 1  
2) Use **+1 Day** or Start Auto to advance time; UI auto-refreshes via `/api/state`  
3) Explore dashboard/leaderboard; create your player character at `/character/new`

## Configuration
- `AUTO_SIM_ENABLED`, `AUTO_SIM_SECONDS` control the background loop
- Change `app.secret_key` in `app.py` before production
- Adjust admin credentials and world/balance knobs in `config.py` (tax, births, elections, building costs, etc.)

## Data & Persistence
- Primary store: `data/ashen_world.sqlite3` (auto-created)
- Bank/world/yearly stats tables seed defaults automatically
- Legacy CSV paths remain aliased for compatibility via `save_to_csv` / `load_from_csv`

## Testing & Maintenance
- No automated tests yet; manual verify dashboard, admin, leaderboard, and auto-refresh
- To hard reset, stop the server and clear `data/` (this wipes all progress)
- Freeze dependencies after changes: `pip freeze > requirements.txt`

## Security Notes
- Do not ship with default admin credentials or the hardcoded `app.secret_key`
- Disable `AUTO_SIM_ENABLED` if you don’t want the background thread in production
