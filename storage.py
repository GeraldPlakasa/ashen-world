"""
Backward-compatible shim: re-exports everything from src/repositories/*.

Existing imports like ``from storage import save_villagers`` keep working.
"""

# Keep DB_PATH importable from storage so test monkeypatching works:
#   monkeypatch.setattr(storage, "DB_PATH", ...)
from config import DB_PATH  # noqa: F401

# --- model types (convenience re-exports) ---
from src.models import (  # noqa: F401
    Villager,
    Bank,
    WorldPayload,
    User,
    GraveyardRecord,
)

# --- base helpers ---
from src.repositories.base import (  # noqa: F401
    db_conn,
    init_db,
)

# --- villagers & graveyard ---
from src.repositories.villager_repo import (  # noqa: F401
    save_villagers,
    load_villagers,
    save_to_csv,
    load_from_csv,
    graveyard_upsert_from_villager,
    graveyard_get,
    graveyard_get_many,
)

# --- world / day / weather ---
from src.repositories.world_repo import (  # noqa: F401
    compute_year_and_day,
    load_day,
    save_day,
    load_world_payload,
    save_world_payload,
    load_weather,
    maybe_roll_weather,
)

# --- users ---
from src.repositories.user_repo import (  # noqa: F401
    load_users,
    save_user,
)

# --- bank ---
from src.repositories.bank_repo import (  # noqa: F401
    load_bank,
    save_bank,
)

# --- yearly stats ---
from src.repositories.stats_repo import (  # noqa: F401
    clear_yearly_stats,
    get_year_entry,
    list_yearly_history,
    ensure_year_row,
    update_year_daily,
    finalize_year,
    get_all_time_leader,
    get_all_time_leaders,
    migrate_legacy_files_to_sqlite,
)
