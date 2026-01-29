"""
Backward-compatible shim: re-exports everything from src/services/relationship_service,
src/services/election_service, and src/services/family_service.
"""

# --- relationship helpers ---
from src.services.relationship_service import *  # noqa: F401,F403

# Private names not exported by wildcard
from src.services.relationship_service import (  # noqa: F401
    _family_key,
    _same_family,
    _get_relations_dict,
    _append_last_action,
    _get_by_id,
    _is_spouse_eligible,
    _set_spouses,
    _clear_spouses,
    _is_mutual_spouse,
    _safe_int,
    _get_current_king,
    _demote_queen,
    _mark_dead,
)

# --- election ---
from src.services.election_service import *  # noqa: F401,F403

# --- family / birth / childhood / inheritance ---
from src.services.family_service import *  # noqa: F401,F403

# Private names from family_service
from src.services.family_service import (  # noqa: F401
    _ensure_list_field,
    _traits_list,
    _new_id,
    _unique_child_name,
    _inherit_one_trait,
    _make_child_traits,
    _inherit_stat_small,
    _count_couple_children,
    _count_family_children,
    _birth_probability,
    _spawn_child,
    _assign_job_for_young_adult,
)

# Re-export job group constants so they remain importable from villagers_social
from src.services.relationship_service import (  # noqa: F401
    MILITARY_JOBS,
    LEARNED_JOBS,
    COMMERCE_JOBS,
    CRAFT_JOBS,
    NATURE_JOBS,
)
