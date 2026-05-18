"""Backwards-compatibility shim.

Action logic now lives in `src.services.actions` (a subpackage split by
category — economic, welfare, social, combat, crime, magic, support).
Callers can keep importing from `src.services.action_service` for the
public API; this module re-exports it.

New code should import directly from `src.services.actions`.
"""
from __future__ import annotations

from src.services.actions import (
    choose_action,
    apply_action,
    handle_level_up,
    create_shop_offer,
    append_action_history,
)

__all__ = [
    "choose_action",
    "apply_action",
    "handle_level_up",
    "create_shop_offer",
    "append_action_history",
]
