"""Route V52 cycle commands through the existing audited performance endpoint."""
from __future__ import annotations

import json
from typing import Mapping

from . import performance
from . import v52_cycle_management as cycle_management

_ORIGINAL_ADD_ACTUAL_CASHFLOW = None


def add_actual_cashflow_v52(
    *,
    flow_type: str,
    amount_vnd: float,
    event_day: str,
    note: str | None = None,
):
    kind = str(flow_type or "").upper()
    if kind not in {"DISCARD_CYCLE", "RESTORE_CYCLE"}:
        assert _ORIGINAL_ADD_ACTUAL_CASHFLOW is not None
        return _ORIGINAL_ADD_ACTUAL_CASHFLOW(
            flow_type=flow_type,
            amount_vnd=amount_vnd,
            event_day=event_day,
            note=note,
        )
    try:
        command = json.loads(str(note or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("PERFORMANCE_CYCLE_COMMAND_INVALID") from exc
    if not isinstance(command, Mapping):
        raise ValueError("PERFORMANCE_CYCLE_COMMAND_INVALID")
    plan_id = str(command.get("plan_id") or "")
    reason = str(command.get("reason") or "")
    if kind == "DISCARD_CYCLE":
        return cycle_management.discard_cycle(
            plan_id=plan_id,
            reason=reason,
        )
    return cycle_management.restore_cycle(
        plan_id=plan_id,
        reason=reason,
    )


def apply() -> None:
    if getattr(performance, "_v52_commands_applied", False):
        return
    global _ORIGINAL_ADD_ACTUAL_CASHFLOW
    _ORIGINAL_ADD_ACTUAL_CASHFLOW = performance.add_actual_cashflow
    performance.add_actual_cashflow = add_actual_cashflow_v52
    performance._v52_commands_applied = True
