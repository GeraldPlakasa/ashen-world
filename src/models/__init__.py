"""Data models for Ashen World – TypedDict definitions.

Import all model types from here for convenience::

    from src.models import Villager, Bank, WorldPayload
"""

from src.models.villager import Villager
from src.models.bank import Bank
from src.models.world import WorldPayload
from src.models.user import User
from src.models.combat import CombatResult, Enemy, ShopOffer
from src.models.graveyard import GraveyardRecord
from src.models.stats import AllTimeLeader, Champion, YearlyChampions, YearStats
from src.models.building import Building
from src.models.factories import create_default_bank, create_default_villager, create_default_world

__all__ = [
    "Villager",
    "Bank",
    "WorldPayload",
    "User",
    "CombatResult",
    "Enemy",
    "ShopOffer",
    "GraveyardRecord",
    "AllTimeLeader",
    "Champion",
    "YearlyChampions",
    "YearStats",
    "Building",
    "create_default_bank",
    "create_default_villager",
    "create_default_world",
]
