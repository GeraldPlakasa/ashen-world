"""TypedDict for the User data structure."""

from __future__ import annotations

from typing import TypedDict


class User(TypedDict):
    username: str
    email: str
    password_hash: str
