"""Ad-hoc death-monitor script for the rebalance test.

Polls the live DB every 60s. For each tick reports:
  - current day / year
  - alive count
  - new deaths since prior poll, classified by cause string
"""
import sqlite3
import time
import json
import sys

DB = "data/ashen_world.sqlite3"
INTERVAL = 60
TICKS = int(sys.argv[1]) if len(sys.argv) > 1 else 6  # one tick per minute


def classify(last_action: str) -> str:
    s = (last_action or "").lower()
    if "won vs" in s and "wounds" in s:
        return "won-died-from-wounds"
    if "hunt vs" in s or "hunt (loss" in s:
        return "hunt-killed"
    if "spar" in s:
        return "spar"
    if "peacefully" in s:
        return "peaceful"
    if "exiled" in s:
        return "exile"
    if "executed" in s:
        return "execution"
    if "plague" in s or "disease" in s or "succumbed" in s:
        return "disease"
    if "murder" in s:
        return "murder"
    return "other"


def snapshot():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('SELECT value FROM world_state WHERE key="day_payload"')
    day = json.loads(cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM villagers WHERE alive='true'")
    alive = cur.fetchone()[0]
    cur.execute(
        "SELECT id, death_day, last_action FROM villagers "
        "WHERE alive='false' AND CAST(death_day AS INTEGER) > 0"
    )
    dead = {int(r[0]): (int(r[1]), r[2] or "") for r in cur.fetchall()}
    conn.close()
    return day, alive, dead


prev = None
prev_dead_ids = set()
print(f"=== monitor start ===", flush=True)
for i in range(TICKS + 1):
    day, alive, dead = snapshot()
    new_dead_ids = set(dead.keys()) - prev_dead_ids
    new_deaths = [(dead[did][0], dead[did][1]) for did in new_dead_ids]
    new_deaths.sort()
    bucket = {}
    for _, la in new_deaths:
        c = classify(la)
        bucket[c] = bucket.get(c, 0) + 1

    line = (
        f"[poll {i:02d}] day={day['total_day']} (y{day['year']} d{day['day_in_year']} {day['season']:>6}) "
        f"alive={alive:3d}  new_deaths={len(new_deaths):2d}"
    )
    if bucket:
        line += "  " + " ".join(f"{k}={v}" for k, v in sorted(bucket.items(), key=lambda x: -x[1]))
    print(line, flush=True)

    prev = (day, alive)
    prev_dead_ids = set(dead.keys())

    if i < TICKS:
        time.sleep(INTERVAL)

print("=== monitor end ===", flush=True)
