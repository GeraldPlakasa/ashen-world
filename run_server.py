"""Production launcher: bind to all interfaces and start the sim thread.

`python3 app.py` serves localhost only; this entrypoint is what the systemd
unit runs. Flask's built-in threaded server is enough for this hobby-scale
deployment; swap to waitress/gunicorn behind nginx if traffic ever matters.
"""
import os

from app import app, start_auto_simulation

if __name__ == "__main__":
    start_auto_simulation()
    port = int(os.getenv("PORT", "3002"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
