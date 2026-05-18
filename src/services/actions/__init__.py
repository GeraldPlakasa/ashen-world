"""Action subsystem — picker + per-handler dispatch.

This package was extracted from the legacy 2k-line `action_service.py`. The
old module remains as a re-export shim, so existing imports continue to work.

Layout:
  - picker.py      — choose_action()
  - utility.py     — handle_level_up(), create_shop_offer(), append_action_history()
  - economic.py    — work / buy_food / buy_gear
  - welfare.py     — rest
  - social.py      — socialize / hangout / visit_tavern / woo
  - combat.py      — train / hunt / spar / drill
  - crime.py       — steal / assault / murder / patrol
  - magic.py       — study / meditate
  - support.py     — mentor / heal_sick / forge_artifact

Adding a new action: drop a new `apply_<name>(v, bank, all_characters,
weather, current_day)` function into the appropriate category module and
register it in `_HANDLERS` below.
"""
from __future__ import annotations

from src.utils.world_utils import clamp

from src.services.actions.picker import choose_action
from src.services.actions.utility import (
    handle_level_up,
    create_shop_offer,
    append_action_history,
)
from src.services.actions import (
    economic,
    welfare,
    social,
    combat,
    crime,
    magic,
    support,
)
from src.models.villager import Villager
from src.models.bank import Bank


# Dispatch table — action slug → handler function.
# Handlers all share the same signature so the dispatch loop is trivial.
_HANDLERS = {
    "train":          combat.apply_train,
    "study":          magic.apply_study,
    "work":           economic.apply_work,
    "rest":           welfare.apply_rest,
    "socialize":      social.apply_socialize,
    "hangout":        social.apply_hangout,
    "steal":          crime.apply_steal,
    "assault":        crime.apply_assault,
    "murder":         crime.apply_murder,
    "patrol":         crime.apply_patrol,
    "buy_food":       economic.apply_buy_food,
    "buy_gear":       economic.apply_buy_gear,
    "mentor":         support.apply_mentor,
    "meditate":       magic.apply_meditate,
    "heal_sick":      support.apply_heal_sick,
    "forge_artifact": support.apply_forge_artifact,
    "spar":           combat.apply_spar,
    "drill":          combat.apply_drill,
    "visit_tavern":   social.apply_visit_tavern,
    "woo":            social.apply_woo,
    "hunt":           combat.apply_hunt,
}


def apply_action(
    v: Villager,
    action: str,
    bank: Bank | None = None,
    all_characters: list[Villager] | None = None,
    weather: str | None = None,
    current_day: int | None = None,
) -> None:
    """Apply the chosen action to the villager (stats, hunger, coins, EXP).

    Unknown actions are silently ignored — but the post-action tail (hunger
    clamp, rep cast, level-up check) still runs so the villager stays in a
    valid state.
    """
    handler = _HANDLERS.get(action)
    if handler is not None:
        handler(v, bank, all_characters, weather, current_day)

    # Common post-action tail — runs regardless of which branch executed.
    v["hunger"] = clamp(v["hunger"], 0, 100)
    # HP has no upper cap — can grow unlimited
    # rep has no cap either — fame grows unbounded, disgrace falls unbounded
    v["rep"] = int(v.get("rep", 0) or 0)
    handle_level_up(v)


__all__ = [
    "choose_action",
    "apply_action",
    "handle_level_up",
    "create_shop_offer",
    "append_action_history",
]
