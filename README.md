# 🏰 Ashen World

A living-village simulation game built with Flask. Watch villagers live, work, marry, have children, hold elections, and experience world events through an interactive web dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Tests](https://img.shields.io/badge/Tests-181%20passed-brightgreen.svg)

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
├── config.py                 # World constants
├── world_utils.py            # Utility functions
├── src/
│   ├── services/             # Business logic
│   │   ├── simulation_service.py   # Daily loop
│   │   ├── election_service.py     # Elections
│   │   ├── quest_service.py        # Quest system
│   │   ├── family_service.py       # Birth, childhood
│   │   ├── relationship_service.py # Marriage, social
│   │   ├── building_service.py     # Tax, construction
│   │   ├── event_service.py        # World events
│   │   ├── combat_service.py       # Combat resolution
│   │   ├── action_service.py       # Daily actions
│   │   └── achievement_service.py  # Achievement system
│   ├── repositories/         # Data persistence
│   └── models/               # TypedDict models
├── templates/                # Jinja2 templates
├── static/
│   ├── css/                  # Styles
│   └── js/                   # Frontend scripts
├── tests/                    # Pytest suite (181 tests)
└── data/                     # SQLite database (auto-created)
```

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

# Run with coverage
pytest --cov=src --cov=world_utils --cov=app --cov-report=term-missing
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Full world state + KPIs |
| `/api/family-tree/<id>` | GET | Family tree graph data |

## 🛠️ Tech Stack

- **Backend:** Flask, SQLite, Python 3.10+
- **Frontend:** Bootstrap 5, Jinja2, JavaScript
- **Visualization:** vis-network (family trees)
- **Testing:** pytest

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
