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

# Testing
pip install -r requirements-dev.txt
pytest                          # Run all 181 tests
pytest -v                       # Verbose output
pytest -m unit                  # Unit tests only (fast)
pytest -m integration           # Integration tests only
pytest --cov=world_utils --cov=buildings --cov=storage --cov-report=term-missing
```

## Architecture

### Core Files

The codebase uses a layered architecture. Root-level files (`villagers.py`, `villagers_social.py`, `storage.py`, `buildings.py`) are **backward-compatible shims** that re-export from `src/`. New code should import from `src/` directly.

| Layer | File | Purpose | Key Functions |
|-------|------|---------|---------------|
| Entry | `app.py` | Flask routes, session auth, background auto-sim thread | Thin route handlers only |
| Config | `config.py` | World constants: time, demographics, traits, jobs, buildings | Constants only, no functions |
| Util | `world_utils.py` | Pure utility functions | `pick()`, `rand_int()`, `clamp()`, `pick_weighted()`, `exp_to_next_level()`, `safe_int()`, `is_child()` |
| Model | `src/models/villager.py` | Villager TypedDict (functional form for keyword fields) | `Villager` |
| Model | `src/models/bank.py` | Bank/treasury TypedDict | `Bank` |
| Model | `src/models/world.py` | World state TypedDict | `WorldPayload` |
| Model | `src/models/user.py` | User account TypedDict | `User` |
| Model | `src/models/combat.py` | Combat TypedDicts (functional form for `"def"` field) | `Enemy`, `CombatResult`, `ShopOffer` |
| Model | `src/models/graveyard.py` | Graveyard record TypedDict | `GraveyardRecord` |
| Model | `src/models/stats.py` | Yearly stats TypedDicts | `YearStats`, `Champion`, `YearlyChampions`, `AllTimeLeader` |
| Model | `src/models/building.py` | Building definition TypedDict | `Building` |
| Model | `src/models/factories.py` | Factory functions for default typed dicts | `create_default_villager()`, `create_default_bank()`, `create_default_world()` |
| Service | `src/services/villager_service.py` | Villager generation, ID management | `make_row()`, `generate_characters()`, `reset_id_from_characters()` |
| Service | `src/services/action_service.py` | Action selection and application | `choose_action()`, `apply_action()`, `handle_level_up()`, `create_shop_offer()` |
| Service | `src/services/combat_service.py` | Enemy creation, combat resolution | `create_enemy_for()`, `resolve_combat()`, `apply_starvation_damage()` |
| Service | `src/services/simulation_service.py` | Daily loop, immigrants, player inheritance | `simulate_one_day()`, `maybe_add_immigrants()`, `player_inheritance_phase()` |
| Service | `src/services/election_service.py` | Elections, leadership scoring | `hold_election()`, `leadership_score()`, `get_traits_set()` |
| Service | `src/services/family_service.py` | Birth, childhood, coming-of-age, inheritance | `birth_daily_phase()`, `child_daily_phase()`, `coming_of_age_phase()`, `settle_inheritance_phase()` |
| Service | `src/services/relationship_service.py` | Relationships, marriage, corruption, assassination | `adjust_relationship()`, `spouse_daily_phase()`, `king_assassination_phase()` |
| Service | `src/services/building_service.py` | Tax policy, construction, upgrades, repairs | `update_tax_policy()`, `get_building_level()`, `upgrade_cost()`, `build_building_summary()` |
| Service | `src/services/world_service.py` | World orchestration: state locking, day advancement | `get_current_state()`, `advance_one_day()`, `generate_new_world()`, `compute_year_champions()` |
| Service | `src/services/family_tree_service.py` | Family tree graph building, graveyard index | `build_family_graph()`, `build_graveyard_index_for()`, `find_person()` |
| Service | `src/services/character_service.py` | Player character creation, pinned character data | `create_player_character()`, `get_pinned_character_data()` |
| Repo | `src/repositories/base.py` | SQLite connection, schema init | `db_conn()`, `init_db()` |
| Repo | `src/repositories/villager_repo.py` | Villager CRUD + graveyard | `save_villagers()`, `load_villagers()`, `graveyard_*()` |
| Repo | `src/repositories/world_repo.py` | Day/weather state | `load_day()`, `save_day()`, `load_weather()` |
| Repo | `src/repositories/user_repo.py` | User accounts | `load_users()`, `save_user()` |
| Repo | `src/repositories/bank_repo.py` | Treasury/bank state | `load_bank()`, `save_bank()` |
| Repo | `src/repositories/stats_repo.py` | Yearly stats + migration | `ensure_year_row()`, `finalize_year()`, `get_all_time_leaders()` |

### Project Structure

```
ashen-world/
├── app.py                    # Flask entrypoint, thin route handlers (~520 lines)
├── config.py                 # World constants
├── world_utils.py            # Pure utilities
├── villagers.py              # SHIM → re-exports from src/services/*
├── villagers_social.py       # SHIM → re-exports from src/services/*
├── storage.py                # SHIM → re-exports from src/repositories/*
├── buildings.py              # SHIM → re-exports from src/services/building_service
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
│   │   ├── character_service.py    # Player character creation, pinned data
│   │   ├── villager_service.py     # Villager generation (make_row, generate_characters)
│   │   ├── action_service.py       # Action selection + application
│   │   ├── combat_service.py       # Enemy creation, combat resolution
│   │   ├── simulation_service.py   # Daily loop, immigrants, player inheritance
│   │   ├── election_service.py     # Elections, leadership scoring
│   │   ├── family_service.py       # Birth, childhood, coming-of-age, inheritance
│   │   ├── relationship_service.py # Relationships, marriage, corruption, assassination
│   │   └── building_service.py     # Tax policy, construction, upgrades, repairs
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
├── templates/                # Jinja2 templates
│   ├── landing.html          # Main dashboard
│   ├── admin.html            # Admin control hall
│   ├── leaderboard.html      # Stats and champions
│   ├── family_tree.html      # vis-network graph
│   ├── features.html         # Feature showcase
│   ├── login.html
│   ├── register.html
│   └── create_character.html
├── static/
│   ├── css/style.css         # Dark theme
│   └── js/main.js            # Frontend interactions
├── tests/                    # Pytest suite (181 tests)
│   ├── conftest.py           # Shared fixtures
│   ├── test_world_utils.py
│   ├── test_buildings.py
│   ├── test_villagers_pure.py
│   ├── test_villagers_social_pure.py
│   ├── test_storage.py
│   └── test_app_integration.py
├── data/                     # Runtime database
├── pytest.ini                # Pytest configuration
├── requirements-dev.txt      # Test dependencies
└── .env                      # Environment variables
```

### Key Configuration (config.py)

```python
DAYS_PER_YEAR = 90              # In-game days per year
AUTO_SIM_SECONDS = 1.0          # Real seconds per simulated day
ELECTION_INTERVAL_YEARS = 5     # Years between scheduled elections
MAX_BUILDING_LEVEL = 3          # Maximum building upgrade level
KING_MAX_TERMS = 3              # Lifetime term limit for King
CHILD_MAX_AGE = 16              # Age threshold for adulthood
DYNASTY_BONUS = 1000            # Leadership bonus for same family as previous King
WEATHER_TYPES = ["sunny", "rain"]
```

### Database Schema

SQLite database at `data/ashen_world.sqlite3` (auto-created on first run):

| Table | Purpose |
|-------|---------|
| `villagers` | Stats, family, relationships, job, traits, action history |
| `users` | Registered user accounts |
| `world_state` | Current day, weather state |
| `bank_state` | Treasury balance, tax rate, building levels/health |
| `yearly_stats` | Year-by-year champions and stats snapshots |
| `graveyard` | Archived dead villagers for family tree lookups |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Full world state + KPIs (polled by frontend) |
| `/api/family-tree/<id>` | GET | vis-network nodes/edges for family graph |

### Simulation Flow

Each day tick (`advance_one_day()` in `src/services/world_service.py`):

1. Roll weather (every N days)
2. Choose action for each villager based on traits/stats/weather
3. Apply hunger, starvation damage
4. Resolve combat, loot distribution
5. Handle level-ups, marriages, births (with cooldown)
6. Age increment on year boundary, dead cleanup → graveyard
7. Check scheduled elections (every N years)
8. Emergency election if King dies
9. Player inheritance if owner's character dies
10. Immigrant arrivals
11. Building decay, tax collection, treasury interest

### Threading

`_state_lock = threading.Lock()` in `src/services/world_service.py` guards concurrent database access. Background thread runs `auto_simulation_loop()` when `AUTO_SIM_ENABLED=True`.

## Testing

The project has a pytest test suite with 181 tests organized by module:

| Test File | Tests | Coverage Target |
|-----------|-------|-----------------|
| `test_world_utils.py` | 27 | `clamp`, `exp_to_next_level`, `is_child`, `pick`, `rand_int`, `pick_weighted` |
| `test_buildings.py` | 38 | `get_building_level`, `upgrade_cost`, `apply_tax_on_income`, `update_tax_policy` |
| `test_villagers_pure.py` | 17 | `choose_action`, `make_row`, `generate_characters` |
| `test_villagers_social_pure.py` | 35 | `leadership_score`, `get_traits_set`, `relationship_label`, spouse eligibility |
| `test_storage.py` | 24 | Villager/bank/day persistence, graveyard, year calculations |
| `test_app_integration.py` | 21 | `advance_one_day`, `/api/state`, `compute_year_champions`, `build_family_graph` |

### Test Fixtures (conftest.py)

- `sample_villager` - Minimal villager dict
- `sample_king` - King for election tests
- `sample_female_villager` - Female for marriage tests
- `sample_child` - Child (age <= 16)
- `sample_bank` - Village treasury state
- `sample_bank_with_buildings` - Bank with constructed buildings
- `test_db_connection` - Patches DB_PATH for isolated tests
- `seeded_random` - Deterministic random for reproducible tests
- `flask_client` - Flask test client
- `multiple_villagers` - List of varied villagers

### Test Markers

- `@pytest.mark.unit` - Pure function tests, no database
- `@pytest.mark.integration` - Tests requiring database or Flask

## Environment Variables (.env)

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_SECRET_KEY=your_secret_key_here
```

## Common Development Tasks

### Adding a New Building Type

1. Add to `BUILDINGS` list in `config.py`
2. Add trait-based priority in `building_priority_weights()` in `src/services/building_service.py`
3. Add any special effects in `choose_action()` in `src/services/action_service.py`

### Adding a New Trait

1. Add to `TRAITS` list in `config.py`
2. Add tax modifier in `update_tax_policy()` in `src/services/building_service.py`
3. Add leadership modifier in `leadership_score()` in `src/services/election_service.py`
4. Add action weight modifier in `choose_action()` in `src/services/action_service.py`
5. Add building priority modifier in `building_priority_weights()` in `src/services/building_service.py`

### Adding a New Action

1. Add to weights dict in `choose_action()` in `src/services/action_service.py`
2. Add handler in `apply_action()` in `src/services/action_service.py`
3. Update tests in `test_villagers_pure.py`

### Running Tests Before Committing

```bash
pytest -v  # Ensure all 181 tests pass
```
