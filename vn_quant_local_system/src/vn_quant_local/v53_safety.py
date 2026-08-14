"""Runtime safety for V53 cycle-policy serialization."""
from __future__ import annotations

from typing import Mapping

from . import performance
from . import v53_cycle_cleanup as v53

_ORIGINAL_CYCLE_POLICY_ROWS = None


def cycle_policy_rows_json_safe(
    status: Mapping[str, object],
) -> list[dict[str, object]]:
    assert _ORIGINAL_CYCLE_POLICY_ROWS is not None
    rows = [dict(row) for row in _ORIGINAL_CYCLE_POLICY_ROWS(status)]
    for row in rows:
        row["auto_match_only"] = bool(row.get("auto_match_only"))
        row["explicit_plan_binding"] = bool(
            row.get("explicit_plan_binding")
        )
        row["discardable"] = bool(row.get("discardable"))
        row["discard_reassigns_auto_fills"] = bool(
            row.get("discard_reassigns_auto_fills")
        )
    return rows


def apply() -> None:
    if getattr(performance, "_v53_safety_applied", False):
        return
    global _ORIGINAL_CYCLE_POLICY_ROWS
    _ORIGINAL_CYCLE_POLICY_ROWS = v53._cycle_policy_rows
    v53._cycle_policy_rows = cycle_policy_rows_json_safe
    performance._v53_safety_applied = True
