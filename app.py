"""
Ashen World - Flask Application Entry Point

This module creates and configures the Flask application,
registers blueprints, and starts the background simulation.
"""
from __future__ import annotations

import threading

from flask import Flask

from config import AUTO_SIM_ENABLED, ENV_FLASK_SECRET_KEY
from src.services.world_service import (
    auto_simulation_loop,
    advance_one_day,
    compute_year_champions,
)
from src.services.family_tree_service import build_family_graph
from src.routes import register_blueprints

# Re-export for backward compatibility with tests
__all__ = [
    "app",
    "advance_one_day",
    "compute_year_champions",
    "build_family_graph",
]

# ---------------------------------------------------------------------------
#  Create Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = ENV_FLASK_SECRET_KEY

# Register all route blueprints
register_blueprints(app)

# ---------------------------------------------------------------------------
#  Background simulation
# ---------------------------------------------------------------------------

with app.app_context():
    """
    Start background auto-simulation thread at startup (beware debug reloader).
    """
    if AUTO_SIM_ENABLED:
        t = threading.Thread(target=auto_simulation_loop, daemon=True)
        t.start()

# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)

    # For production without auto-reloader:
    # if AUTO_SIM_ENABLED:
    #     t = threading.Thread(target=auto_simulation_loop, daemon=True)
    #     t.start()
    # app.run(debug=True, use_reloader=False)
