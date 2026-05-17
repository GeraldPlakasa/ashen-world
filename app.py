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

def start_auto_simulation() -> None:
    """Start the background auto-simulation thread.

    This is intentionally NOT called at module import time anymore — only
    `__main__` (i.e. `python app.py`) or an explicit WSGI hook should call
    it. Previously this fired on every `from app import app`, which caused
    pytest fixtures and ad-hoc smoke scripts to race the live DB and on at
    least one occasion overwrote `total_day` with a temp-DB value, rolling
    the world back several years.

    In `flask --debug` the reloader spawns two processes (parent stat-watcher
    + child marked by `WERKZEUG_RUN_MAIN=true`). We only start the sim in
    the child so a single process owns the daily tick.
    """
    if not AUTO_SIM_ENABLED:
        return
    import os
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    is_non_debug = not app.debug
    if not (is_reloader_child or is_non_debug):
        logger.info("Skipping auto-sim in reloader parent process")
        return
    t = threading.Thread(target=auto_simulation_loop, daemon=True)
    t.start()
    logger.info("Auto-simulation thread started")


logger.info("Ashen World app module loaded")

# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Ashen World starting up...")
    import os

    # `app.run(debug=True)` below spawns a werkzeug reloader: the parent stays
    # alive as a stat-watcher, the child (marked by WERKZEUG_RUN_MAIN=true)
    # runs the real server. Only ONE of them should own the sim thread, or
    # they'll race on the DB and roll total_day around.
    debug_mode = True
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not debug_mode or is_reloader_child:
        start_auto_simulation()
    else:
        logger.info("Reloader parent — sim will start in the child process")

    app.run(debug=debug_mode)

    # For production without the reloader (e.g. gunicorn app:app), import
    # `app` and call `start_auto_simulation()` once from a launcher script.
