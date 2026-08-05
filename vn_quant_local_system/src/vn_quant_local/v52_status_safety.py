"""Presentation safety for V52 active-cycle views."""
from __future__ import annotations

from . import performance
from .v52_cycle_management import discarded_plan_ids

_ORIGINAL_PERFORMANCE_STATUS = None


def performance_status_active_cycles_only():
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    if status.get("status") != "ACTIVE":
        return status
    discarded = discarded_plan_ids()
    status["shadow_plans"] = [
        row
        for row in status.get("shadow_plans", [])
        if str(row.get("plan_id") or "") not in discarded
    ]
    status["active_shadow_plan_count"] = len(status["shadow_plans"])
    status["discarded_shadow_plan_count"] = len(
        status.get("discarded_cycle_catalog", [])
    )
    return status


def apply() -> None:
    if getattr(performance, "_v52_status_safety_applied", False):
        return
    global _ORIGINAL_PERFORMANCE_STATUS
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status
    performance.performance_status = performance_status_active_cycles_only
    performance._v52_status_safety_applied = True
