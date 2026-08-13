"""V59 REST-vs-WebSocket broker freshness diagnostics.

The official DNSE SDK StreamPosition model has no source timestamp/account field.
When stream account scope is safe, compare a position event received *after* the
last REST checkpoint against REST quantities. A mismatch is direct evidence that
our REST checkpoint is older than the realtime stream state even without a
source-side modified timestamp.
"""
from __future__ import annotations

from typing import Mapping

from . import source_integrity_v49 as v49
from . import v55_eod_only as v55
from . import v59_fast_realtime as v59

V59_LAG_DIAGNOSTICS_VERSION = "V59_REST_WS_POSITION_DIFF"
_ORIGINAL_STATUS = None


def rest_ws_position_differences_v59() -> dict[str, object]:
    raw = v49.latest_broker_portfolio_v49()
    if raw is None:
        return {
            "status": "NO_REST_CHECKPOINT",
            "difference_count": 0,
            "differences": [],
        }
    rest = v55._public(raw)
    if rest is None:
        return {
            "status": "NO_REST_CHECKPOINT",
            "difference_count": 0,
            "differences": [],
        }
    captured_at = str(rest.get("captured_at") or "")
    rest_qty = {
        str(row.get("symbol") or "").upper(): int(row.get("quantity") or 0)
        for row in rest.get("positions", []) or []
        if isinstance(row, Mapping)
    }
    differences: list[dict[str, object]] = []
    newer_events = 0
    for row in v59._realtime_rows():
        received_at = str(row.get("received_at") or "")
        if captured_at and received_at and received_at <= captured_at:
            continue
        newer_events += 1
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        ws_quantity = int(row.get("quantity") or 0)
        rest_quantity = int(rest_qty.get(symbol, 0))
        if ws_quantity != rest_quantity:
            differences.append(
                {
                    "symbol": symbol,
                    "rest_quantity": rest_quantity,
                    "ws_quantity": ws_quantity,
                    "rest_captured_at": captured_at or None,
                    "ws_received_at": received_at or None,
                    "ws_source_modified_at": row.get("source_modified_at"),
                    "evidence": "NEWER_WS_EVENT_QUANTITY_DIFFERS_FROM_REST_CHECKPOINT",
                }
            )
    return {
        "status": "DIFFERENT" if differences else "NO_DIFFERENCE_OBSERVED",
        "rest_snapshot_id": rest.get("snapshot_id"),
        "rest_captured_at": captured_at or None,
        "newer_ws_position_event_count": newer_events,
        "difference_count": len(differences),
        "differences": differences,
        "rest_checkpoint_lag_evidence": bool(differences),
        "version": V59_LAG_DIAGNOSTICS_VERSION,
    }


def realtime_status_with_lag_v59(*, include_portfolio: bool = True) -> dict[str, object]:
    assert _ORIGINAL_STATUS is not None
    result = dict(_ORIGINAL_STATUS(include_portfolio=include_portfolio))
    result["rest_ws_position_comparison"] = rest_ws_position_differences_v59()
    result["rest_checkpoint_lag_evidence"] = bool(
        result["rest_ws_position_comparison"].get("rest_checkpoint_lag_evidence")
    )
    result["lag_diagnostics_version"] = V59_LAG_DIAGNOSTICS_VERSION
    return result


def apply() -> None:
    if getattr(v59, "_v59_lag_diagnostics_applied", False):
        return
    global _ORIGINAL_STATUS
    _ORIGINAL_STATUS = v59.realtime_status_v59
    v59.realtime_status_v59 = realtime_status_with_lag_v59
    v59.rest_ws_position_differences_v59 = rest_ws_position_differences_v59
    v59.V59_LAG_DIAGNOSTICS_VERSION = V59_LAG_DIAGNOSTICS_VERSION
    v59._v59_lag_diagnostics_applied = True
