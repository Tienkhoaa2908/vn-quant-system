"""Safety gate for V52 cycle discard.

A pending cycle may be discarded before shadow execution.  Once the execution
session is available, discarding would rewrite observed shadow performance and
create hindsight bias, so the action is rejected even when no actual fill exists.
"""
from __future__ import annotations

from . import performance
from . import v52_cycle_management as cycle_management

_ORIGINAL_DISCARD_CYCLE = None


def discard_cycle_safe(*, plan_id: str, reason: str):
    assert _ORIGINAL_DISCARD_CYCLE is not None
    plan = cycle_management._plan_row(plan_id)
    status = str(plan.get("status") or "").upper()
    execution_day = str(plan.get("execution_day") or "") or None
    try:
        latest_market_day = performance._latest_market_day()
    except Exception:
        latest_market_day = None
    if status == "EXECUTED" or (
        execution_day is not None
        and latest_market_day is not None
        and execution_day <= latest_market_day
    ):
        raise ValueError(
            "PERFORMANCE_CYCLE_SHADOW_ALREADY_EXECUTED:"
            f"{plan['plan_id']}:{execution_day or 'UNKNOWN'}"
        )
    return _ORIGINAL_DISCARD_CYCLE(plan_id=plan_id, reason=reason)


def apply() -> None:
    if getattr(performance, "_v52_discard_safety_applied", False):
        return
    global _ORIGINAL_DISCARD_CYCLE
    _ORIGINAL_DISCARD_CYCLE = cycle_management.discard_cycle
    cycle_management.discard_cycle = discard_cycle_safe
    performance.discard_cycle = discard_cycle_safe
    performance._v52_discard_safety_applied = True
