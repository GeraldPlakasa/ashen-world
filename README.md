# Ashen World

A living-village simulation built with Flask. Manage villagers, elections, buildings, and a growing treasury through a web dashboard with real-time updates.

## Features

- Kingdom dashboard with sortable/filterable villager table and pinned character card
- Admin control hall to reset the world, tick days, and run auto-simulation
- Player-made characters (one per user) with custom trait + random trait
- Simulation loop: daily actions, hunger, relationships, marriage/children, leadership elections, corruption, assassination, inheritance
- Economy and buildings: tax policy tied to king traits, treasury balance, construct/upgrade/repair, health decay
- Random world events: plague, famine, invasion, festival, harvest, blessing (12% daily chance)
- Weather system affecting villager actions (sunny/rain)
- Family tree visualization with vis-network
- Leaderboard with yearly champions and all-time records
- JSON API `/api/state` feeding auto-refresh UI for state and building KPIs
- SQLite persistence with automatic schema setup

## Project Structure

```
ashen-world/
├── app.py                    # Flask entrypoint, thin route handlers
├── config.py                 # World constants (traits, jobs, buildings, economy rules)
├── world_utils.py            # Utility functions (pick, clamp, safe_int, exp calculations)
├── villagers.py              # Shim → re-exports from src/services/*
├── villagers_social.py       # Shim → re-exports from src/services/*
├── storage.py                # Shim → re-exports from src/repositories/*
├── buildings.py              # Shim → re-exports from src/services/building_service
├── src/
│   ├── repositories/         # Data persistence layer
│   │   ├── base.py           #   DB connection, schema init
│   │   ├── villager_repo.py  #   Villager CRUD + graveyard
│   │   ├── world_repo.py     #   Day/weather state
│   │   ├── user_repo.py      #   User accounts
│   │   ├── bank_repo.py      #   Treasury/bank state
│   │   └── stats_repo.py     #   Yearly stats + migration
│   ├── services/             # Business logic
│   │   ├── world_service.py        # World orchestration, state locking, day advancement
│   │   ├── family_tree_service.py  # Family tree graph building, graveyard index
│   │   ├── character_service.py    # Player character creation, pinned character data
│   │   ├── villager_service.py     # Villager generation (make_row, generate_characters)
│   │   ├── action_service.py       # Action selection + application
│   │   ├── combat_service.py       # Enemy creation, combat resolution
│   │   ├── simulation_service.py   # Daily loop, immigrants, player inheritance
│   │   ├── election_service.py     # Elections, leadership scoring
│   │   ├── family_service.py       # Birth, childhood, coming-of-age, inheritance
│   │   ├── relationship_service.py # Relationships, marriage, corruption, assassination
│   │   ├── building_service.py     # Tax policy, construction, upgrades, repairs
│   │   └── event_service.py        # Random world events (plague, famine, festival, etc.)
│   ├── models/               # TypedDict data models
│   │   ├── __init__.py       #   Re-exports all types
│   │   ├── villager.py       #   Villager TypedDict
│   │   ├── bank.py           #   Bank TypedDict
│   │   ├── world.py          #   WorldPayload TypedDict
│   │   ├── user.py           #   User TypedDict
│   │   ├── combat.py         #   Enemy, CombatResult, ShopOffer
│   │   ├── graveyard.py      #   GraveyardRecord TypedDict
│   │   ├── stats.py          #   YearStats, Champion, AllTimeLeader
│   │   ├── building.py       #   Building TypedDict
│   │   └── factories.py      #   Default-value factory functions
│   └── routes/               # (reserved for future blueprint split)
├── templates/                # Jinja2 templates (dashboard, admin, auth pages)
├── static/
│   ├── css/style.css         # Dark theme, responsive layout
│   └── js/main.js            # Sorting, filtering, auto-refresh, family tree
├── tests/                    # Pytest test suite (181 tests)
│   ├── conftest.py           # Shared fixtures
│   ├── test_world_utils.py
│   ├── test_buildings.py
│   ├── test_villagers_pure.py
│   ├── test_villagers_social_pure.py
│   ├── test_storage.py
│   └── test_app_integration.py
├── data/                     # Runtime database (auto-created)
├── pytest.ini                # Pytest configuration
├── requirements-dev.txt      # Test dependencies
└── .env                      # Environment variables (create from template)
```

The root-level files `villagers.py`, `villagers_social.py`, `storage.py`, and `buildings.py` are thin shims that re-export from `src/`. This preserves backward compatibility: all existing imports and tests work without changes.

## Requirements

- Python 3.10+
- pip/venv
- Dependencies: `Flask`, `Werkzeug`, `python-dotenv`

## Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install Flask Werkzeug python-dotenv

# Install test dependencies (optional)
pip install -r requirements-dev.txt
```

## Environment Variables

Create a `.env` file in the project root:

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_SECRET_KEY=your_secret_key_here
```

## Run

```bash
python app.py
# Visit http://localhost:5000
```

- Admin login credentials from `.env` file
- Register a user via `/register` to create a player character (max 1 per user)

## Testing

The project includes a comprehensive pytest test suite with 181 tests.

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov=world_utils --cov=app --cov-report=term-missing

# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run specific test file
pytest tests/test_world_utils.py -v
```

### Test Coverage

Run `pytest --cov=src --cov=world_utils --cov=app --cov-report=term-missing` for current coverage numbers.

## Typical Flow

1. Log in as admin -> **Generate** to spawn 50 villagers and reset to Day 1
2. Use **+1 Day** or Start Auto to advance time; UI auto-refreshes via `/api/state`
3. Explore dashboard/leaderboard; create your player character at `/character/new`
4. Watch your character live, work, marry, and potentially become King!

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DAYS_PER_YEAR` | 90 | In-game days per year |
| `AUTO_SIM_SECONDS` | 1.0 | Real seconds per simulated day |
| `ELECTION_INTERVAL_YEARS` | 5 | Years between scheduled elections |
| `MAX_BUILDING_LEVEL` | 3 | Maximum building upgrade level |
| `KING_MAX_TERMS` | 3 | Lifetime term limit for King |

## Events System

Random world events occur during daily simulation, adding dynamic challenges and rewards to the village.

### Event Timing

- **Frequency**: Once per year on a random day
- **Scheduling**: At the start of each year, a random day (1 to 89) is selected for the event
- **Trigger**: When that specific day arrives, the event automatically triggers
- **Strategy**: Build mitigating structures (Clinic, Granary, Walls, etc.) before events occur

This yearly timing creates anticipation and rewards strategic building construction. Event notifications display the Year for easier tracking.

### Event Types

| Event | Weight | Chance | Effect | Mitigating Building |
|-------|--------|--------|--------|---------------------|
| 🌻 **Good Harvest** | 25 | 27.8% | Reduces hunger for all villagers, bonus coins for nature workers (Farmer, Shepherd, etc.), treasury gains 100-300 coins | Granary, Market |
| 🎉 **Festival** | 20 | 22.2% | +2-8 REP for all, HP restore, hunger reduction, treasury gains 50-150 coins | Temple, Tavern |
| ✨ **Blessing** | 15 | 16.7% | +25-50 HP heal for all, 30% chance of +1-3 to ATK/DEF/INT | Temple |
| ⚔️ **Invasion** | 12 | 13.3% | Combat damage (20-50 HP), possible deaths, treasury loses 10-25% | Barracks, Walls |
| 🌾 **Famine** | 10 | 11.1% | +15-30 hunger for 60-80% of villagers, treasury loses 5-15% | Granary |
| ☠️ **Plague** | 8 | 8.9% | -15-40 HP for 40-55% of villagers, possible deaths | Clinic |

### Building Mitigation

Buildings reduce negative event impacts or boost positive ones:

| Building | Effect on Events |
|----------|------------------|
| **Clinic** | Reduces plague severity by 20% per level |
| **Granary** | Reduces famine severity by 20% per level; boosts harvest gains by 20% per level |
| **Market** | Boosts harvest gains by 20% per level |
| **Temple** | Boosts blessing effects by 25% per level; boosts festival effects by 15% per level |
| **Tavern** | Boosts festival effects by 15% per level |
| **Barracks** | Reduces invasion damage by 15% per level |
| **Walls** | Reduces invasion damage by 20% per level |

### Event Banner

When an event occurs, a banner displays on the dashboard showing the latest event message and the day it happened. The banner persists until a new event occurs.

## Data & Persistence

- Primary store: `data/ashen_world.sqlite3` (auto-created)
- Tables: `villagers`, `users`, `world_state`, `bank_state`, `yearly_stats`, `graveyard`
- Bank/world/yearly stats tables seed defaults automatically
- WAL mode enabled for better concurrency

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Full world state + KPIs for dashboard |
| `/api/family-tree/<id>` | GET | vis-network nodes/edges for family graph |

## Security Notes

- Do not ship with default admin credentials
- Generate a strong `FLASK_SECRET_KEY` for production
- Disable `AUTO_SIM_ENABLED` if you don't want the background thread in production

## License

MIT
