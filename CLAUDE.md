# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo. Optimized so an agentic AI can orient quickly and act without re-discovering layout each session.

## Project Overview

**Ashen World** is a living-village simulation built with Flask + SQLite. A background thread advances a daily tick where ~50 NPCs work, marry, fight, hold elections, suffer events, complete quests, find magical artifacts, and (eventually) die into the graveyard. A web dashboard renders state; logged-in users may create one player character that lives inside that simulation.

Single process, single database. No queues, no external services.

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
pytest                          # Run full suite (~460 tests)
pytest -v                       # Verbose output
pytest -m unit                  # Unit tests only (no DB)
pytest -m integration           # Integration tests (DB / Flask)
pytest tests/test_artifact_service.py    # Single file
pytest --cov=src --cov=app --cov-report=term-missing

# DB maintenance (data/ashen_world.sqlite3)
python scripts/db_maintenance.py status
python scripts/db_maintenance.py vacuum
python scripts/db_maintenance.py integrity
python scripts/db_maintenance.py cleanup
python scripts/db_maintenance.py backup
```

## Architecture

Layered: **routes → services → repositories → SQLite**, with shared **models** (TypedDicts), **config** (constants only), and **utils** (pure helpers). Services hold all business logic; routes are thin; repos are the only place that touches the DB. The historical root-level shims (`villagers.py`, `villagers_social.py`, `storage.py`, `buildings.py`, `world_utils.py`) **are gone** — import from `src/` directly.

### Entry / framework

| File | Purpose |
|------|---------|
| `app.py` | Flask app factory. Registers blueprints via `register_blueprints()`, starts background sim thread (only in reloader child to avoid double-running), tracks page views via `before_request`. |
| `config.py` | Constants only — paths, sim timing, demographics, traits, jobs, buildings, artifact templates, weather, log config, schema field lists (`FIELDNAMES`, `INT_FIELDS`). No functions. |

### Routes (Flask Blueprints)

All registered in `src/routes/__init__.py`. Each blueprint is a thin handler — call services, render templates, never touch the DB directly.

| Blueprint | File | Routes |
|-----------|------|--------|
| `main_bp` | `main_routes.py` | `/`, `/features` |
| `auth_bp` | `auth_routes.py` | `/register`, `/login`, `/logout` |
| `admin_bp` | `admin_routes.py` | `/admin` (GET/POST: generate, +1 day) |
| `character_bp` | `character_routes.py` | `/character/new` |
| `family_bp` | `family_routes.py` | `/families`, `/family-tree`, `/api/family-tree/<int>` |
| `stats_bp` | `stats_routes.py` | `/leaderboard`, `/quests`, `/history/csv`, `/quests/csv` |
| `api_bp` | `api_routes.py` | `/api/state`, `/api/analytics`, `/api/character/<int>`, `/api/player-stats` |
| `chronicle_bp` | `chronicle_routes.py` | `/chronicle`, `/api/chronicle` |
| `artifact_bp` | `artifact_routes.py` | `/artifacts`, `/artifacts/<int>`, `/api/artifacts` |
| `map_bp` | `map_routes.py` | `/map` (top-down village layout) |

Auth pattern: `session.get("logged_in")` for any user, `session.get("is_admin")` gates admin views. The `auth_bp` falls back to env-based admin credentials (`ADMIN_USERNAME`/`ADMIN_PASSWORD`) when the password DB miss.

### Services (`src/services/`)

| Service | Purpose | Key entrypoints |
|---------|---------|-----------------|
| `world_service.py` | Orchestration: state lock, day advancement, world generation, year champions | `get_current_state()`, `advance_one_day()`, `generate_new_world()`, `compute_year_champions()`, `auto_simulation_loop()` |
| `simulation_service.py` | One-day master loop: per-villager actions, immigrants, player inheritance | `simulate_one_day()`, `maybe_add_immigrants()`, `player_inheritance_phase()` |
| `villager_service.py` | Villager generation + ID management | `make_row()`, `generate_characters()`, `reset_id_from_characters()` |
| `action_service.py` | Per-villager action selection + apply (work/hunt/rest/meditate/etc.), level-ups, shop offers | `choose_action()`, `apply_action()`, `handle_level_up()`, `create_shop_offer()` |
| `combat_service.py` | Enemy creation + combat resolution + starvation damage. Hooks `artifact_service.drop_for_kill` on win | `create_enemy_for()`, `resolve_combat()`, `apply_starvation_damage()` |
| `family_service.py` | Birth, childhood, coming-of-age, inheritance | `birth_daily_phase()`, `child_daily_phase()`, `coming_of_age_phase()`, `settle_inheritance_phase()` |
| `relationship_service.py` | Relationship deltas, marriage, corruption, king assassination | `adjust_relationship()`, `spouse_daily_phase()`, `king_assassination_phase()` |
| `election_service.py` | Scheduled + emergency elections, leadership scoring | `hold_election()`, `leadership_score()`, `get_traits_set()` |
| `building_service.py` | Tax policy, construction, upgrades, decay/repairs, building summary | `update_tax_policy()`, `get_building_level()`, `upgrade_cost()`, `build_building_summary()` |
| `event_service.py` | Yearly random event (PLAGUE / FAMINE / FESTIVAL / INVASION / GOOD_HARVEST / BLESSING). One per year on a randomized day | `roll_event_for_year()`, `apply_event()`, `get_event_history()` |
| `quest_service.py` | King-issued quests every `QUEST_INTERVAL_YEARS`, party formation, success roll, rewards | `maybe_run_quest()`, `recruit_party()`, `resolve_quest()` |
| `character_service.py` | Player character creation + pinned-character payload for landing page | `create_player_character()`, `get_pinned_character_data()`, `get_character_detail()` |
| `family_tree_service.py` | vis-network graph build, graveyard index | `build_family_graph()`, `build_graveyard_index_for()`, `find_person()`, `get_all_families()` |
| `skill_service.py` | Skill catalog (`SKILLS` dict), per-villager skill rolls, parsing | `parse_skills()`, `get_skill_info()`, `roll_birth_skills()` |
| `achievement_service.py` | Achievement catalog (`ACHIEVEMENTS` dict), checks at milestones, reward application | `check_achievements()`, `trigger_survivor_achievement()` |
| `artifact_service.py` | Magical artifacts: template lookup, drop rolling, equip, effective stats, forging eligibility, inheritance | `roll_drop_for_tier()`, `drop_for_kill()`, `effective_stats()`, `auto_equip_if_better()`, `can_forge()`, `settle_artifact_inheritance()` |
| `chronicle_service.py` | In-world Town Crier — turns sim events into narrative log entries (best-effort, never raises). New `justice` category covers crimes + trial verdicts. | `record_election()`, `record_marriage()`, `record_birth()`, `record_death()`, `record_world_event()`, `record_artifact_drop()`, `record_artifact_inheritance()`, `record_quest()`, `record_crime()`, `record_trial_verdict()` |
| `disease_service.py` | Persistent per-villager illness (cough/fever/plague), infection chains via daily contact, healer-driven cures, immunity tracking. Runs `daily_disease_phase()` in the sim loop. | `infect()`, `cure()`, `try_transmit()`, `find_sick_in_circle()`, `daily_disease_phase()` |
| `trade_service.py` | King-driven foreign trade. Imports food/wood/stone/iron when local stocks are low; exports surplus once thresholds are crossed. Trait-modulated (Greedy resists, Generous buys readily, Ambitious favors materials). | `maybe_king_imports_resources()`, `maybe_king_exports_resources()` |
| `justice_service.py` | Crime & Justice: open pending cases when crimes (theft / assault / murder) are witnessed; per-day trial phase where the King issues verdicts (fine / exile / execution) modulated by traits and recidivism. Bumps yearly stat counters for the Leaderboard + admin Justice tab. | `maybe_witness_and_record()`, `verdict_for_king()`, `apply_verdict()`, `crime_trial_phase()` |

### Repositories (`src/repositories/`) — data persistence layer

| Repo | Tables | Purpose |
|------|--------|---------|
| `base.py` | (all) | `db_conn()` context manager, `init_db()`, schema migrations (idempotent column adds), thread-local persistent connection (WAL + 30s busy_timeout) |
| `villager_repo.py` | `villagers`, `graveyard` | Villager CRUD + graveyard upsert/cleanup. `save_villagers()` is bulk-optimized — do NOT call repeatedly per villager |
| `world_repo.py` | `world_state` | Day/weather payload, `compute_year_and_day()` |
| `user_repo.py` | `users` | User accounts, password hashing |
| `bank_repo.py` | `bank_state` | Treasury, tax rate, resources (food/wood/stone/iron), building levels/health, election + event + quest message cache, **`pending_crimes`** docket (open cases awaiting trial) |
| `stats_repo.py` | `yearly_stats` | Per-year row: champions, tax averages, treasury start/end, all-time leaders, end-of-year resource snapshot, **justice counters** (`crimes_committed`, `trials_held`, `fines_collected`, `exiles`, `executions`). `bump_yearly_justice()` is the atomic accumulator. |
| `relationship_repo.py` | `villager_relationships` | Normalized score per `(villager_id, other_id)` |
| `achievement_repo.py` | `villager_achievements` | Normalized achievement IDs per villager |
| `vote_repo.py` | `villager_votes` | Normalized king-vote history |
| `site_stats_repo.py` | `site_stats` | Daily counters: `page_view`, `char_creation`, `user_registration` |
| `chronicle_repo.py` | `chronicle_events` | Narrative event log: write, list, filter by category/year/importance |
| `artifact_repo.py` | `artifacts` | Per-instance artifact rows (templates live in `config.ARTIFACT_TEMPLATES`) |

### Models (`src/models/`) — TypedDict definitions

`Villager`, `Bank`, `WorldPayload`, `User`, `Enemy`, `CombatResult`, `ShopOffer`, `GraveyardRecord`, `YearStats`, `Champion`, `YearlyChampions`, `AllTimeLeader`, `Building`. `factories.py` exports `create_default_villager()`, `create_default_bank()`, `create_default_world()` for safe defaults. `Villager` and `CombatResult` use the **functional** TypedDict form because they have keyword-clashing fields (`def`, etc.).

### Utils (`src/utils/`)

| File | Purpose |
|------|---------|
| `world_utils.py` | Pure helpers: `pick()`, `rand_int()`, `clamp()`, `pick_weighted()`, `exp_to_next_level()`, `safe_int()`, `is_child()` |
| `logger.py` | Centralized logging — rotating file handler in `data/logs/ashen_world.log` (5 MB × 3 files). Use `get_logger(__name__)` everywhere |

## Project Structure

```
ashen-world/
├── app.py                        # Flask entrypoint (~90 lines, thin)
├── config.py                     # All world/sim constants (~640 lines incl. artifact templates)
├── pytest.ini                    # Markers: unit, integration
├── requirements-dev.txt
├── scripts/
│   └── db_maintenance.py         # CLI: status / vacuum / integrity / cleanup / backup
├── src/
│   ├── routes/                   # 10 Flask blueprints (see Routes table)
│   ├── services/                 # 20 service modules (see Services table)
│   ├── repositories/             # 12 repo modules (see Repositories table)
│   ├── models/                   # TypedDicts + factories
│   └── utils/
│       ├── world_utils.py        # Pure helpers
│       └── logger.py             # Rotating file logger
├── templates/                    # Jinja2
│   ├── _sidebar.html             # Shared nav partial
│   ├── landing.html              # Dashboard
│   ├── admin.html                # Admin control hall
│   ├── leaderboard.html          # Year champions + all-time leaders
│   ├── families.html             # Family list
│   ├── family_tree.html          # vis-network graph
│   ├── chronicle.html            # Town Crier feed
│   ├── artifacts.html            # Artifact catalog
│   ├── artifact_detail.html      # Single artifact lineage
│   ├── quest_history.html        # Quest log
│   ├── map.html                  # Top-down village map view
│   ├── features.html             # Feature showcase
│   ├── login.html / register.html / create_character.html
├── static/
│   ├── css/style.css             # Dark theme
│   ├── css/game.css              # Game-specific styling
│   ├── js/main.js                # Frontend interactions / polling
│   ├── js/admin-charts.js        # Chart.js for /admin
│   ├── js/theme.js               # Theme toggling
│   └── images/logo.png
├── tests/                        # 22 files / ~460 tests (see Testing)
├── data/                         # Runtime: SQLite DB + logs/ (gitignored)
├── CLAUDE.md                     # This file
└── .env                          # Environment variables (gitignored)
```

## Key Configuration (`config.py`)

```python
# Time / sim
DAYS_PER_YEAR = 90
AUTO_SIM_ENABLED = True
AUTO_SIM_SECONDS = 1.0           # real seconds per simulated day

# Politics
ELECTION_INTERVAL_YEARS = 5
KING_MAX_TERMS = 3               # consecutive terms only
DYNASTY_BONUS = 1000             # leadership bonus for prev king's family
QUEST_INTERVAL_YEARS = 3

# Demographics / lifecycle
CHILD_MAX_AGE = 16
BIRTH_BASE_P = 0.006
BIRTH_COOLDOWN_DAYS = 45
COUPLE_DECAY = 0.55
FAMILY_DECAY = 0.85
MAX_DEAD_YEARS = 25
MAX_GRAVEYARD_YEARS = 200

# Economy / buildings
MAX_BUILDING_LEVEL = 3
REPAIR_THRESHOLD = 60            # repair if health < 60%

# Weather
WEATHER_CHANGE_DAYS = 5
WEATHER_RAIN_CHANCE = 0.35
WEATHER_TYPES = ["sunny", "rain"]

# Magic
MAGIC_JOBS = ["Wizard", "Sorcerer", "Bard", "Cleric", "Druid", "Alchemist"]
MINOR_MAGIC_JOBS = ["Priest", "Healer", "Herbalist", "Scholar"]

# Artifacts
ARTIFACT_SLOTS = ["weapon", "armor", "ring", "amulet", "tome"]
ARTIFACT_RARITY_ORDER = {"common": 1, "uncommon": 2, "rare": 3, "legendary": 4}
ARTIFACT_TEMPLATES = [...]       # ~60+ items by slug

# Logging
LOG_FILE   = data/logs/ashen_world.log
LOG_LEVEL  = env LOG_LEVEL or "INFO"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

# Persistence
FIELDNAMES = [...]               # All villager DB columns (drives schema)
INT_FIELDS = [...]               # Subset stored as INTEGER (incl. equip_*, last_forge_day)
```

## Database Schema

SQLite at `data/ashen_world.sqlite3` (WAL mode, busy_timeout=30s). `init_db()` is idempotent and runs once per DB path; `_ensure_*_columns()` migrate forward by adding missing columns.

| Table | Purpose |
|-------|---------|
| `villagers` | Stats, family, relationships, job, traits, action history, disease state, **`crime_record`** (JSON list of past crimes & verdicts). Columns auto-derived from `config.FIELDNAMES` (TEXT default, INTEGER for `INT_FIELDS`) |
| `users` | Registered user accounts (username PK, password hash) |
| `world_state` | Key/value JSON: `day_payload` = `{total_day, year, day_in_year, weather, next_weather_roll_day}` |
| `bank_state` | Key/value JSON: `bank_payload` = treasury, tax rate, resources (food/wood/stone/iron), building levels/health, election+event+quest cache, **`pending_crimes`** docket |
| `yearly_stats` | One row per year: champions, deaths, births, taxes, treasury, wealthiest family, population_end, end-of-year stockpile, **justice counters** (`crimes_committed`, `trials_held`, `fines_collected`, `exiles`, `executions`) |
| `graveyard` | Archived dead villagers (lightweight identity for family tree lookups after pruning) |
| `villager_relationships` | Normalized `(villager_id, other_id) → score` (replaces JSON blob) |
| `villager_achievements` | Normalized `(villager_id, achievement_id, earned_day)` |
| `villager_votes` | Normalized `(villager_id, king_id, vote_day)` |
| `event_history` | Persistent event log (`PLAGUE`/`FAMINE`/etc.) — feeds `/api/analytics` |
| `site_stats` | Daily counters per `(stat_type, stat_date)` |
| `chronicle_events` | In-world narrative log: day, year, category, headline, body, actors (JSON), importance 1-5 |
| `artifacts` | Per-instance artifact rows: slug, owner_id, acquired_day, forged_history (JSON), condition, destroyed |

Indexes are created in `_ensure_indexes()` — covers `villagers.alive/owner/family`, normalized join columns, chronicle filters, artifact lookups.

## Simulation Flow

`advance_one_day()` (in `world_service.py`) holds `_state_lock` and runs `simulate_one_day()` from `simulation_service.py`, which performs roughly:

1. Roll weather (every `WEATHER_CHANGE_DAYS` days) → save to world_state.
2. **Sorted action pass:** `simulate_one_day()` sorts characters so Guard/Captain/Soldier/Commander act FIRST. This makes any `patrol` action visible to subsequent crime witness rolls in the same tick. For each alive villager: `choose_action()` → `apply_action()` (work/hunt/rest/meditate/study/theft/assault/murder/patrol/...). Hunting kicks off combat via `combat_service`; victories may roll an artifact drop via `artifact_service.drop_for_kill()`. Crimes call `justice_service.maybe_witness_and_record()` which may open a pending case on the bank.
3. Apply starvation damage (`combat_service.apply_starvation_damage`).
4. Disease progression (`disease_service.daily_disease_phase`) — HP drain, lethality rolls, recovery, ambient infection.
5. Food consumption (`consume_food_phase`) — village-wide draw from the shared stockpile.
6. Passive MP regen (magic / minor-magic jobs).
7. Spouse daily phase, marriages, births (with `BIRTH_COOLDOWN_DAYS` gate).
8. King corruption + assassination chance (`relationship_service.king_assassination_phase`) and rival coup phase.
9. **Crime trial phase (`justice_service.crime_trial_phase`)** — if there are pending cases AND a sitting King, every case is judged; verdicts bump the yearly stat counters.
10. Player inheritance if the user's character died (`player_inheritance_phase`).
11. Elder decay (70+ HP/stat penalties).
12. Year boundary: age++, run `coming_of_age_phase`, prune very-old dead, copy survivors to graveyard.
13. Scheduled election every `ELECTION_INTERVAL_YEARS`; emergency election if king died this tick.
14. Roll yearly random event when its scheduled day matches today (`event_service.apply_event`).
15. Maybe run a quest (`quest_service.maybe_run_quest`) every `QUEST_INTERVAL_YEARS`.
16. Immigrant arrivals.
17. Building decay, construction, upgrade, repair, tax collection, treasury interest (`building_service`).
18. King may import / export resources (`trade_service.maybe_king_imports_resources`, `maybe_king_exports_resources`).
19. Settle artifact inheritance for any villager who died today (`artifact_service.settle_artifact_inheritance`).
20. Chronicle service emits narrative entries throughout (best-effort, never raises).
21. Save: `save_villagers()`, `save_bank()`, `save_day()`, `update_year_daily()` / `finalize_year()` on year roll.

## Threading & Concurrency

- **`_state_lock = threading.Lock()`** in `world_service.py` serializes the entire daily tick + admin actions.
- A daemon thread runs `auto_simulation_loop()` only in the **reloader child** (`WERKZEUG_RUN_MAIN=true`) or in non-debug mode — prevents duplicate sim loops in `flask --debug`.
- DB connection is **thread-local persistent** (`base.py::_get_persistent_conn`) with WAL + 30s `busy_timeout`. Don't open connections directly — always use `with db_conn() as conn:`.

## Testing

Pytest suite in `tests/` — 22 files, ~460 tests. Run with `pytest`.

| Test file | Covers |
|-----------|--------|
| `test_world_utils.py` | `clamp`, `pick`, `pick_weighted`, `safe_int`, etc. |
| `test_buildings.py` | Levels, upgrade cost, tax application, policy |
| `test_villagers_pure.py` | `make_row`, `generate_characters`, action selection |
| `test_villagers_social_pure.py` | Leadership scoring, relationship labels, marriage eligibility |
| `test_villager_service.py` | Generation edge cases |
| `test_storage.py` | Villager/bank/day persistence + graveyard + year math |
| `test_normalized_repos.py` | `villager_relationships` / `_achievements` / `_votes` repos |
| `test_app_integration.py` | `advance_one_day`, `/api/state`, year champions, family graph |
| `test_simulation_service.py` | One-day loop integration |
| `test_combat_service.py` | Enemy creation, combat resolution, starvation |
| `test_family_service.py` | Births, coming-of-age, inheritance |
| `test_family_tree_service.py` | Graph building, ancestor/descendant traversal |
| `test_relationship_service.py` | Score deltas, marriage, assassination |
| `test_election_service.py` | Scheduled + emergency, term limits, dynasty bonus |
| `test_event_service.py` | Yearly event scheduling + effects |
| `test_quest.py` | Party recruitment, success rolls, rewards |
| `test_skills.py` | Skill rolls + lookups |
| `test_achievement_service.py` | Achievement checks + reward application |
| `test_character_service.py` | Player character creation + pinned data |
| `test_effects.py` | Trait + skill stat-mod aggregation |

### Fixtures (`conftest.py`)

`sample_villager`, `sample_king`, `sample_female_villager`, `sample_child`, `sample_bank`, `sample_bank_with_buildings`, `test_db_connection` (patches `DB_PATH`), `seeded_random`, `flask_client`, `multiple_villagers`.

### Markers

- `@pytest.mark.unit` — pure functions, no DB
- `@pytest.mark.integration` — requires DB or Flask client

## Environment Variables (`.env`)

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_SECRET_KEY=your_secret_key_here
LOG_LEVEL=INFO              # optional: DEBUG, INFO, WARNING, ERROR
```

## Common Development Tasks

### Adding a new action

1. Add weight in `choose_action()` (`action_service.py`) — keyed by trait/job/weather.
2. Add handler branch in `apply_action()` — read `v["job"]`, mutate stats, append to `action_log`.
3. If it can record narrative drama, call `chronicle_service.record_*()`.
4. Add unit tests in `test_villagers_pure.py`.

### Adding a new trait

1. Append to `TRAITS` in `config.py`.
2. Tax modifier in `update_tax_policy()` (`building_service.py`).
3. Leadership modifier in `leadership_score()` (`election_service.py`).
4. Action weight + apply effects in `choose_action()` / `apply_action()`.
5. Building priority in `building_priority_weights()` (`building_service.py`).

### Adding a new building type

1. Append to `BUILDINGS` in `config.py` (slug, cost, prerequisites).
2. Add trait priority in `building_priority_weights()`.
3. If it gates new actions/jobs, branch in `choose_action()` and check via `get_building_level(bank, slug)`.

### Adding a new artifact

1. Append a template dict to `ARTIFACT_TEMPLATES` in `config.py`: `slug`, `name`, `slot` ∈ `ARTIFACT_SLOTS`, `rarity` ∈ `ARTIFACT_RARITY_ORDER`, `stat_mods` ∈ `{atk, def, int, hp, mp, rep}`, `flavor`, `binding` ∈ `{"none", "soulbound"}`.
2. No code change needed — `artifact_service` reads templates dynamically. Drop chance is governed by `_TIER_DROP_CHANCE` and `_TIER_RARITY_WEIGHTS`.

### Adding a chronicle category

1. Add a `record_*()` helper in `chronicle_service.py` that calls `_safe_record(category=...)`.
2. Call it from the relevant service. **Always call inside a try/except — chronicle writes must never break the sim loop**; `_safe_record` already swallows but the caller-site lookups (e.g. building name) can still raise.
3. The `/chronicle` page automatically lists distinct categories via `chronicle_repo.list_categories()`.

### Adding a new route

1. Either extend an existing blueprint or create a new file in `src/routes/`.
2. Register the new blueprint in `src/routes/__init__.py::register_blueprints`.
3. Keep handlers thin: call `get_current_state()` + a service, render template. Never import from another blueprint.

### Adding a new crime type

1. Add the slug + severity to `CRIME_SEVERITY` (and `CRIME_BASE_WITNESS_CHANCE`, `CRIME_FINE_AMOUNT`) in `config.py`.
2. Add a `choose_action()` weight gate (trait + age + rep) in `action_service.py`. Use `if weight > THRESHOLD: weights[<slug>] = ...` — do NOT seed the default weights dict, or floor logic will dilute everyone's pool.
3. Add the `apply_action()` branch. At the end, call `justice_service.maybe_witness_and_record(bank, criminal, victim, "<slug>", characters, current_day)` in a try/except.
4. Update `verdict_for_king()` base weights if the new severity needs a fresh tier (otherwise it falls back to the existing severity buckets).
5. Add a chronicle template in `chronicle_service.record_crime()`.

### Adding a yearly stat counter

1. Add the column to `_ensure_yearly_columns()` in `base.py` (idempotent ALTER).
2. Add an atomic bumper helper in `stats_repo.py` (`bump_yearly_*`) that does `INSERT OR IGNORE` then `UPDATE ... SET col = COALESCE(col, 0) + ?`.
3. Surface it on `templates/leaderboard.html` (per-reign card + current-reign strip) and/or the admin `/api/analytics` payload + a new `tab-*` panel.

### Running tests before committing

```bash
pytest -v                  # full suite
pytest -m unit             # quick smoke
pytest -k "artifact"       # focus area
```

## Conventions & Pitfalls

- **Never create root-level shims again.** The old `villagers.py` / `villagers_social.py` / `storage.py` / `buildings.py` / `world_utils.py` are deleted. Import directly from `src/`.
- **Always go through services.** Routes and templates should never import from `src/repositories/` directly (chronicle widgets are the only minor exception).
- **`save_villagers()` is bulk.** Don't call it inside a per-villager loop — it writes the full population in one transaction. Mutate the in-memory list, then save once at the end of the tick.
- **Chronicle hooks must be best-effort.** Wrap in `try/except`; the simulation loop is more important than narrative.
- **Schema migrations are forward-only and column-add only.** When adding a villager field, append it to `FIELDNAMES` (and `INT_FIELDS` if numeric) — `_ensure_villagers_columns()` will add it on next startup. Same pattern for `_ensure_yearly_columns()` and `_ensure_graveyard_columns()`.
- **Day vs. year.** `total_day` is monotonic global; `(year, day_in_year)` is derived via `compute_year_and_day(total_day)`. Most chronicle/event APIs take `total_day` and convert internally.
- **Equipped artifacts are stored on the villager** as columns `equip_weapon` … `equip_tome` (artifact id, 0 = empty). Stats use `artifact_service.effective_stats(v)` for base + mods; do NOT mutate base stats with equip bonuses.
- **Festival events are filtered** out of "Recent News" on landing/api_state because they crowd out signal events; they still appear in the chronicle.
- **`init_db()` is cached** per DB path. Tests that swap `config.DB_PATH` must call `reset_init_cache()` (in `base.py`) — the `test_db_connection` fixture does this.
- **PowerShell shell** is the default on this machine; chained commands need `;` not `&&`. The Bash tool is also available for POSIX scripts.
- **Guards act first.** `simulate_one_day()` sorts the action loop so jobs in `{Guard, Captain, Soldier, Commander}` run before everyone else. This is load-bearing for `justice_service.witness_chance()` — patrollers must have their `last_action` stamped before crimes are rolled later in the tick. Don't change the sort without rethinking the witness pipeline.
- **`pending_crimes` is on the bank.** Open court cases live in `bank["pending_crimes"]` (a JSON list). The trial phase clears the list when a King is sitting; if there's no king, cases accumulate until an election seats one — this is intentional drama, not a bug.
- **Justice stat bumps are best-effort.** `_bump_stats()` in `justice_service.py` swallows all exceptions — never let a stat-write break the trial phase. Always pass `int()`-cast values to `bump_yearly_justice()`.
- **Crime weights are conditional.** `assault`, `murder`, `patrol` are NOT in the default `weights` dict — they're only inserted by `choose_action()` when gating passes. This avoids the 0.05 floor diluting everyone's action pool. Follow the same pattern when adding rare/conditional actions.
