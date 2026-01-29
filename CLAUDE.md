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

| File | Purpose | Key Functions |
|------|---------|---------------|
| `app.py` | Flask routes, session auth, background auto-sim thread | `advance_one_day()`, `get_current_state()`, `build_family_graph()` |
| `villagers.py` | Villager generation, daily simulation, action system | `simulate_one_day()`, `choose_action()`, `make_row()`, `generate_characters()` |
| `villagers_social.py` | Elections, relationships, marriage/children, inheritance | `hold_election()`, `leadership_score()`, `settle_marriage()`, `settle_inheritance_phase()` |
| `storage.py` | SQLite persistence layer with WAL mode | `save_villagers()`, `load_villagers()`, `save_bank()`, `load_bank()`, `graveyard_*()` |
| `buildings.py` | Tax policy, construction, upgrades, repairs | `update_tax_policy()`, `get_building_level()`, `upgrade_cost()`, `apply_tax_on_income()` |
| `config.py` | World constants: time, demographics, traits, jobs, buildings | Constants only, no functions |
| `world_utils.py` | Pure utility functions | `pick()`, `rand_int()`, `clamp()`, `pick_weighted()`, `exp_to_next_level()`, `is_child()` |

### Project Structure

```
ashen-world/
├── app.py                 # Flask entrypoint (1400+ lines)
├── config.py              # World constants
├── storage.py             # SQLite persistence
├── villagers.py           # Simulation logic
├── villagers_social.py    # Social/election logic
├── buildings.py           # Building/tax logic
├── world_utils.py         # Pure utilities
├── templates/             # Jinja2 templates
│   ├── landing.html       # Main dashboard
│   ├── admin.html         # Admin control hall
│   ├── leaderboard.html   # Stats and champions
│   ├── family_tree.html   # vis-network graph
│   ├── features.html      # Feature showcase
│   ├── login.html
│   ├── register.html
│   └── create_character.html
├── static/
│   ├── css/style.css      # Dark theme
│   └── js/main.js         # Frontend interactions
├── tests/                 # Pytest suite (181 tests)
│   ├── conftest.py        # Shared fixtures
│   ├── test_world_utils.py
│   ├── test_buildings.py
│   ├── test_villagers_pure.py
│   ├── test_villagers_social_pure.py
│   ├── test_storage.py
│   └── test_app_integration.py
├── data/                  # Runtime database
├── pytest.ini             # Pytest configuration
├── requirements-dev.txt   # Test dependencies
└── .env                   # Environment variables
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

Each day tick (`advance_one_day()` in app.py):

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

`_state_lock = threading.Lock()` in app.py guards concurrent database access. Background thread runs `auto_simulation_loop()` when `AUTO_SIM_ENABLED=True`.

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
2. Add trait-based priority in `building_priority_weights()` in `buildings.py`
3. Add any special effects in `choose_action()` in `villagers.py`

### Adding a New Trait

1. Add to `TRAITS` list in `config.py`
2. Add tax modifier in `update_tax_policy()` in `buildings.py`
3. Add leadership modifier in `leadership_score()` in `villagers_social.py`
4. Add action weight modifier in `choose_action()` in `villagers.py`
5. Add building priority modifier in `building_priority_weights()` in `buildings.py`

### Adding a New Action

1. Add to weights dict in `choose_action()` in `villagers.py`
2. Add handler in `simulate_one_day()` in `villagers.py`
3. Update tests in `test_villagers_pure.py`

### Running Tests Before Committing

```bash
pytest -v  # Ensure all 181 tests pass
```
