# 🏰 Ashen World

A living-village simulation game built with Flask. Watch villagers live, work, marry, have children, hold elections, and experience world events through an interactive web dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Tests](https://img.shields.io/badge/Tests-461%20passed-brightgreen.svg)

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

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install Flask Werkzeug python-dotenv
```

### Configuration

Create a `.env` file in the project root:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_SECRET_KEY=your_secret_key_here
```

### Run

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

## 🎮 How to Play

1. **Login as Admin** → Use credentials from `.env`
2. **Generate World** → Click "Generate" in Admin Hall to spawn 50 villagers
3. **Start Simulation** → Click "Start Auto" or use "+1 Day" to advance time
4. **Create Character** → Register a user account and create your player character
5. **Watch & Explore** → Dashboard auto-refreshes, explore family trees and leaderboards

## 📁 Project Structure

```
ashen-world/
├── app.py                    # Flask entrypoint
├── config.py                 # World constants & settings
├── src/
│   ├── services/             # Business logic
│   │   ├── simulation_service.py   # Daily simulation loop
│   │   ├── election_service.py     # King elections
│   │   ├── quest_service.py        # Quest system
│   │   ├── family_service.py       # Birth, childhood
│   │   ├── relationship_service.py # Marriage, social bonds
│   │   ├── building_service.py     # Tax, construction
│   │   ├── event_service.py        # World events (plague, famine, etc)
│   │   ├── combat_service.py       # Combat & hunting
│   │   ├── action_service.py       # Daily villager actions
│   │   ├── achievement_service.py  # Achievement tracking
│   │   ├── skill_service.py        # Skill learning
│   │   └── villager_service.py     # Villager creation
│   ├── repositories/         # Data persistence (SQLite)
│   │   ├── base.py                 # DB connection & init
│   │   ├── villager_repo.py        # Villager CRUD
│   │   ├── relationship_repo.py    # Normalized relationships
│   │   ├── achievement_repo.py     # Normalized achievements
│   │   ├── vote_repo.py            # Normalized votes
│   │   ├── bank_repo.py            # Treasury & buildings
│   │   ├── world_repo.py           # World state
│   │   └── stats_repo.py           # Yearly statistics
│   ├── routes/               # Flask blueprints
│   ├── models/               # TypedDict definitions
│   └── utils/                # Helper functions
├── templates/                # Jinja2 templates
├── static/
│   ├── css/                  # Styles
│   └── js/                   # Frontend scripts
├── tests/                    # Pytest suite (461 tests)
├── scripts/                  # Migration & maintenance scripts
└── data/                     # SQLite database (auto-created)
```

## 🗄️ Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `villagers` | Active villager records (37 columns) |
| `graveyard` | Deceased villager identities |
| `bank_state` | Treasury, buildings, tax policy |
| `world_state` | Day counter, weather |
| `yearly_stats` | Historical statistics by year |
| `users` | Player accounts |

### Normalized Tables (v2.0+)

| Table | Purpose |
|-------|---------|
| `villager_relationships` | Social bonds (villager_id, other_id, score) |
| `villager_achievements` | Achievement tracking (villager_id, achievement_id) |
| `villager_votes` | Election vote history (villager_id, king_id) |

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

## 🧪 Testing

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_quest.py

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

### Test Categories

- **Unit tests** (`@pytest.mark.unit`): Pure function tests
- **Integration tests** (`@pytest.mark.integration`): Database & service tests

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Full world state + KPIs |
| `/api/family-tree/<id>` | GET | Family tree graph data |

## 🛠️ Tech Stack

- **Backend:** Flask, SQLite, Python 3.10+
- **Frontend:** Bootstrap 5, Jinja2, JavaScript
- **Visualization:** vis-network (family trees)
- **Testing:** pytest (461 tests)

## 📜 Migrations

For existing databases, run migrations in order:

```bash
# 1. Normalize JSON fields to separate tables
python scripts/migrate_normalize_json.py

# 2. Drop old JSON columns (optional, after verifying)
python scripts/migrate_drop_json_columns.py

# 3. Fix integer columns if needed
python scripts/migrate_fix_int_columns.py
```

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
