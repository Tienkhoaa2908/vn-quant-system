"""Runtime safety guards for V54 research scope."""
from __future__ import annotations

from . import v54_research_scope as v54

_ORIGINAL_SNAPSHOT_SELLABLE_MAP = None


def snapshot_sellable_map_safe(details):
    """Missing legacy broker tables must not break performance rendering.

    A missing historical snapshot means V54 falls back to the explicit plan row.
    Explicit ``sellable_quantity=0`` and ``WAIT_SELLABLE`` still remain binding.
    """

    assert _ORIGINAL_SNAPSHOT_SELLABLE_MAP is not None
    try:
        return _ORIGINAL_SNAPSHOT_SELLABLE_MAP(details)
    except Exception:
        return {}


def apply() -> None:
    if getattr(v54, "_v54_safety_applied", False):
        return
    global _ORIGINAL_SNAPSHOT_SELLABLE_MAP
    _ORIGINAL_SNAPSHOT_SELLABLE_MAP = v54._snapshot_sellable_map
    v54._snapshot_sellable_map = snapshot_sellable_map_safe
    v54._v54_safety_applied = True
