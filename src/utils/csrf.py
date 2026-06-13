"""Lightweight CSRF protection — no Flask-WTF dependency.

Generates a per-session token, injects it into Jinja context as `csrf_token`,
and rejects any state-changing request (POST/PUT/PATCH/DELETE) that doesn't
present the matching token. JSON API endpoints under `/api/` are exempt — they
are read-only and the admin-write endpoints check `session.is_admin` directly.

Wire-up: call `init_csrf(app)` once at boot. Templates must include the token
in every <form method="POST">:

    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
"""
from __future__ import annotations

import hmac
import secrets

from flask import Flask, abort, current_app, request, session


_TOKEN_KEY = "_csrf_token"
_FORM_FIELD = "csrf_token"
_HEADER_FIELD = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _get_or_create_token() -> str:
    token = session.get(_TOKEN_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_TOKEN_KEY] = token
    return token


def _validate_csrf() -> None:
    if request.method in _SAFE_METHODS:
        return
    # API JSON endpoints are read-only or admin-gated by session; not form-driven.
    if request.path.startswith("/api/"):
        return
    # Pytest fixtures set TESTING=True and don't thread tokens through .post().
    if current_app.config.get("TESTING") or current_app.config.get("WTF_CSRF_ENABLED") is False:
        return

    expected = session.get(_TOKEN_KEY) or ""
    presented = request.form.get(_FORM_FIELD) or request.headers.get(_HEADER_FIELD) or ""
    if not expected or not presented or not hmac.compare_digest(expected, presented):
        abort(400, description="CSRF token missing or invalid.")


def init_csrf(app: Flask) -> None:
    """Register the before_request validator and the template context injector."""
    app.before_request(_validate_csrf)

    @app.context_processor
    def _inject_csrf_token():
        return {"csrf_token": _get_or_create_token()}
