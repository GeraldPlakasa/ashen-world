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
from src.utils.csrf import init_csrf
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

# Secret key is mandatory — sessions/CSRF/flash all degrade silently if it's
# None, and a 500 buried deep in a request is worse than a fast crash at boot.
if not ENV_FLASK_SECRET_KEY:
    raise RuntimeError(
        "FLASK_SECRET_KEY env var is required. Set it in .env or your shell."
    )
app.secret_key = ENV_FLASK_SECRET_KEY

# Tighten session cookies. SECURE must be opt-in (COOKIE_SECURE=1): browsers
# silently drop Secure cookies on plain-HTTP sites, which kills the session
# and with it every CSRF token. Enable it only once TLS terminates in front
# of this app (e.g. a cloudflared tunnel or nginx with certs).
import os as _bootstrap_os
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_bootstrap_os.environ.get("COOKIE_SECURE", "0") == "1",
)

# CSRF protection on every state-changing request (POST/PUT/PATCH/DELETE).
init_csrf(app)

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

_sim_started_lock = threading.Lock()
_sim_started = False


def start_auto_simulation() -> None:
    """Start the background auto-simulation thread.

    Idempotent within a single process — calling it multiple times only
    spawns the thread once. Both the module-level guard (for `flask run`)
    and the `__main__` block (for `python app.py`) call this, and only
    the first call lands.
    """
    global _sim_started
    if not AUTO_SIM_ENABLED:
        return
    with _sim_started_lock:
        if _sim_started:
            return
        t = threading.Thread(target=auto_simulation_loop, daemon=True)
        t.start()
        _sim_started = True
    logger.info("Auto-simulation thread started")


# ---------------------------------------------------------------------------
#  Auto-start at module import — for entrypoints that never hit __main__
#  (`flask run --debug`, `gunicorn app:app`, etc.).
#
# Decision matrix:
#   * pytest fixtures monkeypatch config.DB_PATH; a background sim thread
#     would race those patches and write temp-DB values back to the real
#     DB. → always skip during pytest.
#   * Werkzeug reloader child (WERKZEUG_RUN_MAIN=true) → start. This is
#     the path used by `flask run --debug` once the child is spawned.
#   * Werkzeug reloader parent (no WERKZEUG_RUN_MAIN, but FLASK_DEBUG set)
#     → skip. The child will own the sim. Without this guard, the parent
#     stat-watcher would spawn its own competing thread.
#   * Plain import without any of the above (e.g. `python app.py`'s parent
#     before app.run, or a hand-rolled smoke script) → skip here. The
#     __main__ block below handles `python app.py`. WSGI hosts that
#     bypass __main__ need to call start_auto_simulation() themselves.
# ---------------------------------------------------------------------------
import os as _os
import sys as _sys

_in_pytest = ("pytest" in _sys.modules) or bool(_os.environ.get("PYTEST_CURRENT_TEST"))
_is_reloader_child = _os.environ.get("WERKZEUG_RUN_MAIN") == "true"

if (not _in_pytest) and _is_reloader_child:
    logger.info("Werkzeug reloader child — starting sim at import")
    start_auto_simulation()

logger.info("Ashen World app module loaded")

# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Ashen World starting up...")

    # Debug mode is gated on FLASK_DEBUG=1 (default OFF). Werkzeug's debugger
    # exposes a Python REPL via PIN — leaving debug on for any host reachable
    # from the network is RCE. Keep this off unless you're actively developing
    # on a local machine.
    debug_mode = _os.environ.get("FLASK_DEBUG", "0") == "1"

    # When debug_mode is on, app.run() spawns a werkzeug reloader: the parent
    # stays alive as a stat-watcher, the child (WERKZEUG_RUN_MAIN=true) runs
    # the real server. Only the child should own the sim thread. The
    # module-level block above already called start_auto_simulation() in the
    # child during import; here we call it again for safety (idempotent).
    if not debug_mode or _is_reloader_child:
        start_auto_simulation()
    else:
        logger.info("Reloader parent — sim will start in the child process")

    app.run(debug=debug_mode)

    # For production without the reloader (e.g. gunicorn app:app), import
    # `app` and call `start_auto_simulation()` once from a launcher script.
