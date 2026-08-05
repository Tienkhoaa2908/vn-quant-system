"""Runtime safety guards for V54 research scope."""
from __future__ import annotations

from . import v52_status_safety
from . import v54_research_scope as v54

_ORIGINAL_SNAPSHOT_SELLABLE_MAP = None
_ORIGINAL_STATUS_DISCARDED_PLAN_IDS = None


def snapshot_sellable_map_safe(details):
    """Missing legacy broker tables must not break performance rendering."""

    assert _ORIGINAL_SNAPSHOT_SELLABLE_MAP is not None
    try:
        return _ORIGINAL_SNAPSHOT_SELLABLE_MAP(details)
    except Exception:
        return {}


def sellability_zero_first(row, *, snapshot_sellable):
    """The immutable plan row is authoritative when it records sellability.

    In particular, explicit ``sellable_quantity=0`` must never be replaced by a
    historical broker snapshot parsed by an older workstation version.
    """

    requested = 0
    for key in ("quantity", "requested_quantity", "sellable_quantity"):
        if key in row and row.get(key) is not None:
            requested = v54._nonnegative_int(row.get(key))
            if requested > 0:
                break

    action = str(row.get("action") or "").upper()
    reason = str(row.get("reason") or "").upper()
    if action == "WAIT_SELLABLE" or "NOT_SELLABLE" in reason:
        return requested, 0, "PLAN_CLASSIFIED_WAIT_SELLABLE"

    if "sellable_quantity" in row and row.get("sellable_quantity") is not None:
        executable = min(
            requested,
            v54._nonnegative_int(row.get("sellable_quantity")),
        )
        return requested, executable, "PLAN_EXPLICIT_SELLABLE_QUANTITY"

    if snapshot_sellable is not None:
        executable = min(requested, max(int(snapshot_sellable), 0))
        return requested, executable, "BROKER_SNAPSHOT_AT_PLAN"

    return requested, requested, "LEGACY_NO_SELLABILITY_FIELD"


def apply() -> None:
    if getattr(v54, "_v54_safety_applied", False):
        return
    global _ORIGINAL_SNAPSHOT_SELLABLE_MAP
    global _ORIGINAL_STATUS_DISCARDED_PLAN_IDS
    _ORIGINAL_SNAPSHOT_SELLABLE_MAP = v54._snapshot_sellable_map
    _ORIGINAL_STATUS_DISCARDED_PLAN_IDS = v52_status_safety.discarded_plan_ids
    v54._snapshot_sellable_map = snapshot_sellable_map_safe
    v54._sellability = sellability_zero_first
    v52_status_safety.discarded_plan_ids = v54.operationally_excluded_plan_ids
    v54._v54_safety_applied = True
