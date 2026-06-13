"""In-memory sliding-window rate limiter — no Flask-Limiter dependency.

Single-process only (matches the rest of this app's architecture). Used to
slow brute-force attempts on /login. If we ever multi-process, swap to
Flask-Limiter with a Redis backend; the call sites won't have to change.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque

from flask import request


_lock = threading.Lock()
_buckets: dict[tuple[str, str], Deque[float]] = defaultdict(deque)


def _client_ip() -> str:
    # request.remote_addr is what Werkzeug exposes; if you put nginx in front
    # of this, switch to request.headers.get("X-Forwarded-For", remote_addr)
    # AFTER confirming the proxy strips client-supplied XFF headers.
    return request.remote_addr or "unknown"


def hit(scope: str, limit: int, window_seconds: int) -> bool:
    """Record a request and return True if the caller is over the limit.

    Sliding window keyed on (scope, ip). Old entries are evicted lazily.
    """
    key = (scope, _client_ip())
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        return False


def reset(scope: str) -> None:
    """Clear the bucket for this IP+scope (call on successful auth)."""
    key = (scope, _client_ip())
    with _lock:
        _buckets.pop(key, None)
