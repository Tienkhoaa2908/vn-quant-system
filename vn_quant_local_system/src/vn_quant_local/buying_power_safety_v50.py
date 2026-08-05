"""Safety correction for V50 shared buying-power semantics.

When DNSE successfully returns PPSE, that value is authoritative even when it is
lower than ``availableCash`` (for example because of reservations or a
symbol/price restriction).  The planner must not raise it back to the cash
balance.  This module patches V50 after activation while preserving the original
schema and public payload.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from . import buying_power_v50 as v50
from . import weekly_plan
from .core import state_db

_ORIGINAL_PERSIST = None


def authoritative_shared_ppse(
    *,
    status: str,
    items: Sequence[Mapping[str, object]],
    available_cash_vnd: float,
) -> float:
    if str(status) != "SUCCESS":
        return max(float(available_cash_vnd), 0.0)
    successful = [
        row
        for row in items
        if row.get("status") == "SUCCESS"
    ]
    positive = [
        v50._finite_float(row.get("ppse_vnd"))
        for row in successful
        if v50._finite_float(row.get("ppse_vnd")) > 0.0
    ]
    return min(positive) if positive else 0.0


def safe_persist_snapshot(**kwargs):
    assert _ORIGINAL_PERSIST is not None
    result = _ORIGINAL_PERSIST(**kwargs)
    status = str(kwargs.get("status") or "")
    items = list(kwargs.get("items") or [])
    available = float(result.get("available_cash_vnd") or 0.0)
    authoritative = authoritative_shared_ppse(
        status=status,
        items=items,
        available_cash_vnd=available,
    )
    reusable = max(authoritative - available, 0.0)
    effective_source = (
        str(kwargs.get("source") or v50.BUYING_POWER_SOURCE)
        if status == "SUCCESS"
        else v50.FALLBACK_SOURCE
    )
    with state_db() as db:
        db.execute(
            """
            UPDATE buying_power_snapshots_v50
            SET conservative_buying_power_vnd=?,reusable_unsettled_vnd=?,source=?
            WHERE snapshot_id=?
            """,
            (
                authoritative,
                reusable,
                effective_source,
                str(result["snapshot_id"]),
            ),
        )
    result["conservative_buying_power_vnd"] = authoritative
    result["reusable_unsettled_vnd"] = reusable
    result["source"] = effective_source
    return result


def safe_planned_buying_power(
    current_cash_vnd: float,
    weekly_contribution_vnd: float,
) -> float:
    cash = float(current_cash_vnd)
    contribution = float(weekly_contribution_vnd)
    if cash < 0.0:
        raise ValueError("Tiền khả dụng DNSE không được âm")
    if contribution < 0.0:
        raise ValueError("Tiền mới cho planning cycle không được âm")
    snapshot = v50._current_effective_buying_power()
    if snapshot and snapshot.get("status") == "SUCCESS":
        base = max(
            v50._finite_float(snapshot.get("conservative_buying_power_vnd")),
            0.0,
        )
    else:
        base = cash
    return base + contribution


def apply() -> None:
    if getattr(v50, "_v50_authoritative_ppse_safety_applied", False):
        return
    global _ORIGINAL_PERSIST
    _ORIGINAL_PERSIST = v50._persist_snapshot
    v50._persist_snapshot = safe_persist_snapshot
    v50.planned_buying_power_v50 = safe_planned_buying_power
    weekly_plan.planned_buying_power = safe_planned_buying_power
    v50._v50_authoritative_ppse_safety_applied = True
