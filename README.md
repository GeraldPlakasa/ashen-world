# 🏰 Ashen World

A living-village simulation game built with Flask. Watch villagers live, work, marry, have children, hold elections, and experience world events through an interactive web dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Tests](https://img.shields.io/badge/Tests-461%20passed-brightgreen.svg)

## ✨ Features

### 🎭 Village Life Simulation
- **50+ unique villagers** with names, traits, jobs, and personalities
- **Daily actions**: work, train, study, hunt, socialize, rest, buy food/gear
- **Dynamic relationships**: friendships, rivalries, and romance
- **Marriage & family**: weddings, children, family trees, inheritance

### 👑 Governance System
- **King elections** every 5 years with trait-based voting
- **Tax policy** influenced by King's personality (Greedy, Generous, Wise)
- **Term limits** (max 3 terms) and emergency elections
- **Queen consort** system with succession rules

### ⚔️ Combat & Progression
- **Hunting system** with enemy scaling by villager level
- **Combat stats**: ATK, DEF, HP with gear bonuses
- **Level progression** (1-100) with XP from all activities
- **Achievements**: 9 unique achievements to unlock

### 🏆 Quest System (6 Types)
| Quest | Description |
|-------|-------------|
| Hunt the Beast | Combat-focused party quest |
| Diplomatic Mission | Negotiation and reputation |
| Explore Unknown Lands | Discovery and survival |
| Trade Expedition | Commerce and profit |
| Rescue Mission | Save captured villagers |
| Treasure Hunt | Find hidden riches |

### 🌪️ World Events (8 Types)
| Event | Effect |
|-------|--------|
| Plague | Health damage, possible deaths |
| Famine | Hunger increase, food shortage |
| Festival | Happiness boost, relationship gains |
| Invasion | Combat event, village defense |
| Good Harvest | Food surplus, coin bonus |
| Blessing | Health restoration |
| Windfall | Treasury bonus |
| Storm | Building damage |

### 🛠️ Skills (25 Skills, 5 Categories)
| Category | Skills |
|----------|--------|
| Combat | Bladesong, Hawkeye, Bloodrage, Bulwark, Battlemaster |
| Craft | Forgeblessed, Transmutation, Gilded Hands, Artificer, Brewcraft |
| Social | Silver Tongue, Commanding Presence, Dealmaker, Dreadgaze, Heartspark |
| Survival | Pathfinder, Herbweaver, Iron Constitution, Wayfarer, Beastbond |
| Knowledge | Lorekeeper, Arcane Attunement, Chirurgeon, Polyglot, Chronicle |

### 🏗️ Buildings (12 Types)
| Building | Effect |
|----------|--------|
| Marketplace | Trade bonuses |
| Library | Study bonuses |
| Barracks | Military training |
| Granary | Food storage |
| Clinic | Health recovery, plague resistance |
| City Walls | Defense bonus |
| Temple | Blessing effects |
| Blacksmith | Gear production |
| Treasury | Interest on savings |
| Royal Court | Election influence |
| Tax Office | Tax efficiency |
| Tavern | Socialization bonus |

### 📊 Admin Dashboard
- **Analytics charts**: population trends, treasury, births/deaths
- **Distribution charts**: jobs, gender, age, skills, traits
- **Quest & event tracking**: success rates, history
- **Auto-simulation**: configurable speed
- **Villager inspector**: detailed stats view

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/GeraldPlakasa/ashen-world.git
cd ashen-world

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install Flask Werkzeug python-dotenv

# Configure environment
cat > .env << EOF
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
EOF

# Run the game
python app.py
```

Visit `http://localhost:5000` in your browser.

## 🎮 How to Play

1. **Login as Admin** → Use credentials from `.env`
2. **Generate World** → Click "Generate" to spawn 50 villagers
3. **Start Simulation** → Use "+1 Day" or "Start Auto"
4. **Create Character** → Register and create your player character
5. **Watch & Explore** → Family trees, leaderboards, quest history

## 📁 Project Structure

```
ashen-world/
├── app.py                    # Flask entrypoint
├── config.py                 # World constants & settings
├── src/
│   ├── services/             # Business logic (15 services)
│   │   ├── simulation_service.py   # Daily simulation loop
│   │   ├── election_service.py     # King elections
│   │   ├── quest_service.py        # Quest system
│   │   ├── family_service.py       # Birth, childhood
│   │   ├── relationship_service.py # Marriage, social bonds
│   │   ├── building_service.py     # Tax, construction
│   │   ├── event_service.py        # World events
│   │   ├── combat_service.py       # Combat & hunting
│   │   ├── action_service.py       # Daily villager actions
│   │   ├── achievement_service.py  # Achievement tracking
│   │   ├── skill_service.py        # Skill learning & bonuses
│   │   ├── villager_service.py     # Villager creation
│   │   ├── character_service.py    # Player characters
│   │   ├── family_tree_service.py  # Family graph building
│   │   └── world_service.py        # World orchestration
│   ├── repositories/         # Data persistence (8 repos)
│   │   ├── base.py                 # DB connection & schema
│   │   ├── villager_repo.py        # Villager CRUD
│   │   ├── relationship_repo.py    # Social bonds
│   │   ├── achievement_repo.py     # Achievement tracking
│   │   ├── vote_repo.py            # Election votes
│   │   ├── bank_repo.py            # Treasury & buildings
│   │   ├── world_repo.py           # World state & weather
│   │   └── stats_repo.py           # Yearly statistics
│   ├── routes/               # Flask blueprints (7 routes)
│   ├── models/               # TypedDict definitions
│   └── utils/                # Helpers & logging
├── templates/                # Jinja2 templates (12 pages)
├── static/                   # CSS & JavaScript
├── tests/                    # Pytest suite (461 tests)
├── scripts/                  # Migration scripts
└── data/                     # SQLite database & logs
```

## 🗄️ Database Schema

### Core Tables (6)
| Table | Columns | Purpose |
|-------|---------|---------|
| `villagers` | 37 | Active villager records |
| `graveyard` | 14 | Deceased villager identities |
| `bank_state` | 2 | Treasury, buildings, quest history |
| `world_state` | 2 | Day counter, weather |
| `yearly_stats` | 25+ | Historical statistics |
| `users` | 4 | Player accounts |

### Normalized Tables (3)
| Table | Purpose |
|-------|---------|
| `villager_relationships` | Social bonds (villager_id, other_id, score) |
| `villager_achievements` | Achievement tracking |
| `villager_votes` | Election vote history |

## ⚙️ Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DAYS_PER_YEAR` | 90 | In-game days per year |
| `AUTO_SIM_SECONDS` | 1.0 | Real seconds per simulated day |
| `ELECTION_INTERVAL_YEARS` | 5 | Years between elections |
| `QUEST_INTERVAL_YEARS` | 2 | Years between quests |
| `MAX_BUILDING_LEVEL` | 3 | Maximum building upgrade level |
| `KING_MAX_TERMS` | 3 | Lifetime term limit for King |
| `LOG_LEVEL` | INFO | Logging verbosity |

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Current world state + KPIs |
| `/api/analytics` | GET | Historical data for charts |
| `/api/family-tree/<id>` | GET | Family tree graph data |

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests (461 tests)
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_quest.py -v
```

## 📋 Logging

Logs are written to `data/logs/ashen_world.log` with rotation:
- Max 5MB per file, 3 backup files
- Configurable via `LOG_LEVEL` env var

## 📜 Migrations

```bash
# Normalize JSON fields to separate tables
python scripts/migrate_normalize_json.py

# Drop old JSON columns
python scripts/migrate_drop_json_columns.py

# Fix integer column types
python scripts/migrate_fix_int_columns.py
```

## 🛠️ Tech Stack

- **Backend:** Flask 3.0+, SQLite, Python 3.10+
- **Frontend:** Bootstrap 5, Chart.js, Jinja2
- **Visualization:** vis-network (family trees)
- **Testing:** pytest (461 tests)
- **Logging:** Python logging with rotation

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 👨‍💻 Author

**Gerald Plakasa**
- GitHub: [@GeraldPlakasa](https://github.com/GeraldPlakasa)
- DEV.to: [@geraldplakasa](https://dev.to/geraldplakasa)

---

*Watch your villagers thrive, struggle, and build their own stories in Ashen World!* 🏰
