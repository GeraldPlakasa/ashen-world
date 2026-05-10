"""
Ashen World - Flask Application Entry Point

This module creates and configures the Flask application,
registers blueprints, and starts the background simulation.
"""
from __future__ import annotations

import threading

from flask import Flask

from flask import request as flask_request

from config import AUTO_SIM_ENABLED, ENV_FLASK_SECRET_KEY
from src.utils.logger import get_logger
from src.repositories.site_stats_repo import increment_stat
from src.services.world_service import (
    auto_simulation_loop,
    advance_one_day,
    compute_year_champions,
)
from src.services.family_tree_service import build_family_graph
from src.routes import register_blueprints

logger = get_logger(__name__)

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


@app.before_request
def track_page_view():
    """Track page views (skip static files and API calls)."""
    path = flask_request.path
    if path.startswith("/static") or path.startswith("/api/"):
        return
    try:
        increment_stat("page_view")
    except Exception:
        pass

# ---------------------------------------------------------------------------
#  Background simulation
# ---------------------------------------------------------------------------

with app.app_context():
    """
    Start background auto-simulation thread at startup.
    In debug mode Flask's reloader spawns TWO processes — the parent (stat-watcher)
    and the child (WERKZEUG_RUN_MAIN=true).  We only start the sim thread in the
    child to avoid running two competing simulation loops against the same database.
    """
    import os
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    is_non_debug = not app.debug

    logger.info("Ashen World starting up...")
    if AUTO_SIM_ENABLED and (is_reloader_child or is_non_debug):
        t = threading.Thread(target=auto_simulation_loop, daemon=True)
        t.start()
        logger.info("Auto-simulation thread started")
    elif AUTO_SIM_ENABLED:
        logger.info("Skipping auto-sim in reloader parent process")

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
