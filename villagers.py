"""
Backward-compatible shim: re-exports everything from src/services/villager_service,
action_service, combat_service, and simulation_service.
"""

from src.services.villager_service import *  # noqa: F401,F403
from src.services.action_service import *  # noqa: F401,F403
from src.services.combat_service import *  # noqa: F401,F403
from src.services.simulation_service import *  # noqa: F401,F403

# Private names from simulation_service used by tests or app.py
from src.services.simulation_service import (  # noqa: F401
    _norm_origin,
    _is_player_char,
    _is_alive,
    _normalize_id_list,
    _demote_to_npc,
    _promote_to_player,
    _find_children,
    _find_siblings,
    _choose_heir,
)

# Re-export hold_election so `from villagers import hold_election` works (app.py uses this)
from src.services.election_service import hold_election  # noqa: F401
