# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ashen World is a living-village simulation built with Flask and SQLite. Features a web dashboard where admin users manage an evolving civilization with NPCs that live, work, marry, have children, hold elections, and experience events. Players can create one custom character and participate in the world's economy, politics, and social dynamics.

## Commands

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install Flask Werkzeug python-dotenv

# Run
python app.py
# Visit http://localhost:5000
```

No formal test/lint setup exists yet.

## Architecture

### Core Files

- **app.py** - Flask routes, session auth, background auto-simulation thread. Entry point via `app.run()`. Key function: `advance_one_day()` runs the core simulation tick.
- **villagers.py** - Villager generation, daily simulation logic, action system (hunt, rest, work, train, shop, duel, etc.). Core function: `simulate_one_day()`.
- **villagers_social.py** - Elections, relationships, marriage/children, inheritance. Key functions: `hold_election()`, `settle_marriage()`, `player_inheritance_phase()`.
- **storage.py** - SQLite persistence layer with WAL mode. Tables: villagers, users, world, bank, yearly_stats, graveyard, weather.
- **buildings.py** - Tax policy, construction, upgrades, repairs. King traits modify tax rates.
- **config.py** - All world constants: time settings, demographics, traits pool (20), jobs pool (50+), building types (12), election/leadership rules.
- **world_utils.py** - Utility functions: `pick()`, `rand_int()`, `clamp()`, `pick_weighted()`.

### Key Configuration (config.py)

- `DAYS_PER_YEAR = 90` (in-game years)
- `AUTO_SIM_SECONDS = 1.0` (real seconds per simulated day)
- `ELECTION_INTERVAL_YEARS = 5`
- `MAX_BUILDING_LEVEL = 3`
- `WEATHER_TYPES = ["sunny", "rain"]`

### Database

SQLite database at `data/ashen_world.sqlite3` (auto-created on first run). Schema includes:
- `villagers` - stats, family, relationships, job, traits, action history
- `graveyard` - archived dead villagers for family tree lookups
- `yearly_stats` - year-by-year champions and stats snapshots

### Frontend

- **templates/** - Jinja2 templates (landing, admin, leaderboard, family_tree, features, auth pages)
- **static/js/main.js** - Table sorting/filtering, pinned card rendering, auto-refresh via `/api/state`, rain animation, vis-network family tree
- **static/css/style.css** - Dark theme, responsive layout

### Threading

`_state_lock = threading.Lock()` in app.py guards concurrent database access. Background thread runs `auto_simulation_loop()` when `AUTO_SIM_ENABLED=True`.

### API Endpoints

- `GET /api/state` - Full world state + KPIs (polled by frontend for auto-refresh)
- `GET /api/family-tree/<id>` - vis-network nodes/edges for family graph

### Simulation Flow

Each day tick (`advance_one_day()`):
1. Roll weather
2. Choose action for each villager based on traits/stats
3. Apply hunger, starvation damage
4. Resolve combat, loot
5. Handle level-ups, marriages, births (with cooldown)
6. Age increment, dead cleanup → graveyard
7. Check elections (every N years)
8. Player inheritance if owner dies
9. Immigrant arrivals
10. Building decay, tax collection

## Environment Variables (.env)

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ashenworld
FLASK_SECRET_KEY=inisupersecretkeyashenworld
```
