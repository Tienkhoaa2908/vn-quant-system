"""Presentation safety for V52 active-cycle views."""
from __future__ import annotations

from . import performance
from .v52_cycle_management import discarded_plan_ids

_ORIGINAL_PERFORMANCE_STATUS = None


def _pre_execution(
    *,
    status: object,
    execution_day: object,
    latest_market_day: str | None,
) -> bool:
    normalized_status = str(status or "").upper()
    day = str(execution_day or "") or None
    if normalized_status == "EXECUTED":
        return False
    if day is not None and latest_market_day is not None and day <= latest_market_day:
        return False
    return True


def performance_status_active_cycles_only():
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    if status.get("status") != "ACTIVE":
        return status
    discarded = discarded_plan_ids()
    all_shadow_plans = [dict(row) for row in status.get("shadow_plans", [])]
    plan_by_id = {
        str(row.get("plan_id") or ""): row for row in all_shadow_plans
    }
    try:
        latest_market_day = performance._latest_market_day()
    except Exception:
        latest_market_day = None

    discarded_catalog = []
    for raw in status.get("discarded_cycle_catalog", []):
        row = dict(raw)
        plan = plan_by_id.get(str(row.get("plan_id") or ""), {})
        row["execution_day"] = plan.get("execution_day")
        row["shadow_status"] = plan.get("status")
        row["restorable"] = _pre_execution(
            status=plan.get("status"),
            execution_day=plan.get("execution_day"),
            latest_market_day=latest_market_day,
        )
        discarded_catalog.append(row)

    status["discarded_cycle_catalog"] = discarded_catalog
    status["shadow_plans"] = [
        row
        for row in all_shadow_plans
        if str(row.get("plan_id") or "") not in discarded
    ]
    status["active_shadow_plan_count"] = len(status["shadow_plans"])
    status["discarded_shadow_plan_count"] = len(discarded_catalog)
    status["latest_market_day_for_cycle_lock"] = latest_market_day
    return status


def apply() -> None:
    if getattr(performance, "_v52_status_safety_applied", False):
        return
    global _ORIGINAL_PERFORMANCE_STATUS
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status
    performance.performance_status = performance_status_active_cycles_only
    performance._v52_status_safety_applied = True
