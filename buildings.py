"""
Backward-compatible shim: re-exports everything from src/services/building_service.
"""
from src.services.building_service import *  # noqa: F401,F403

# Private names are not exported by wildcard import, so re-export explicitly
from src.services.building_service import (  # noqa: F401
    _ensure_building_dicts,
    _find_building,
)
