"""V51 intent-based reconciliation and DNSE cash-contract integrity.

This layer is intentionally based on V49.  It does not enable V50 PPSE and does
not change C3, preview guard, allocation, sell policy, shadow execution, or NAV
formulas.

It fixes two source/accounting defects:

* cash used by the planner must satisfy the documented balance invariant
  ``availableCash <= totalCash``.  A recursively discovered value near NAV is
  rejected and the planner falls back to valid cash already present in DNSE;
* actual fills are reconciled against immutable plan intents immediately.  A
  fill recorded before T+1 shadow execution is therefore MATCHED_SHADOW_PENDING,
  not EXTRA_OR_UNMATCHED.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import json
import math
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from . import broker_portfolio, capital_plan, performance, source_integrity_v49, weekly_plan
from .core import state_db

V51_VERSION = "V51_INTENT_RECONCILIATION_CASH_INTEGRITY"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_ORIGINAL_PROBE = None
_ORIGINAL_SYNC_BROKER = None
_ORIGINAL_LATEST_BROKER = None
_ORIGINAL_PERFORMANCE_STATUS = None
_CASH_DIAGNOSTICS: dict[str, dict[str, object]] = {}


def _optional_nonnegative(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0:
        return None
    return number


def validate_cash_contract(
    *,
    total_cash_vnd: object,
    available_cash_vnd: object,
    withdrawable_cash_vnd: object,
) -> dict[str, object]:
    """Return cash safe for planning under the DNSE balance field contract.

    DNSE documents ``availableCash`` as cash after debt/fees and ``totalCash``
    as total cash.  Therefore a reported available value materially above total
    cash is not accepted as cash for stock planning.  It may be another nested
    account metric discovered by a recursive parser.
    """

    total = _optional_nonnegative(total_cash_vnd)
    available = _optional_nonnegative(available_cash_vnd)
    withdrawable = _optional_nonnegative(withdrawable_cash_vnd)

    if total is not None:
        tolerance = max(1.0, total * 0.001)
        if available is None:
            usable = total
            status = "TOTAL_CASH_ONLY"
        elif available > total + tolerance:
            usable = total
            status = "REJECT_AVAILABLE_EXCEEDS_TOTAL_CASH"
        else:
            usable = min(available, total)
            status = "AVAILABLE_WITHIN_TOTAL_CASH"
        valid_withdrawable = min(withdrawable or 0.0, total)
    elif available is not None:
        usable = available
        valid_withdrawable = min(withdrawable or 0.0, available)
        status = "AVAILABLE_WITHOUT_TOTAL_CASH"
    elif withdrawable is not None:
        usable = withdrawable
        valid_withdrawable = withdrawable
        status = "WITHDRAWABLE_FALLBACK"
    else:
        usable = 0.0
        valid_withdrawable = 0.0
        status = "NO_VALID_CASH_FIELD"

    return {
        "version": V51_VERSION,
        "status": status,
        "reported_total_cash_vnd": total,
        "reported_available_cash_vnd": available,
        "reported_withdrawable_cash_vnd": withdrawable,
        "validated_available_cash_vnd": max(usable, 0.0),
        "validated_withdrawable_cash_vnd": max(valid_withdrawable, 0.0),
        "planner_cash_vnd": max(usable, 0.0),
        "available_cash_must_not_exceed_total_cash": True,
        "uses_ppse": False,
    }


def _probe_accounts_v51(reader) -> list[dict[str, object]]:
    assert _ORIGINAL_PROBE is not None
    rows = [dict(row) for row in _ORIGINAL_PROBE(reader)]
    for row in rows:
        balance = row.get("balance")
        total = source_integrity_v49._find_number(
            balance, ("totalCash", "total_cash")
        )
        available = source_integrity_v49._find_number(
            balance, ("availableCash", "available_cash")
        )
        withdrawable = source_integrity_v49._find_number(
            balance, ("withdrawableCash", "withdrawable_cash")
        )
        diagnostic = validate_cash_contract(
            total_cash_vnd=total,
            available_cash_vnd=available,
            withdrawable_cash_vnd=withdrawable,
        )
        row["reported_available_cash_vnd"] = available
        row["reported_withdrawable_cash_vnd"] = withdrawable
        row["reported_total_cash_vnd"] = total
        row["available_cash_vnd"] = diagnostic["validated_available_cash_vnd"]
        row["withdrawable_cash_vnd"] = diagnostic[
            "validated_withdrawable_cash_vnd"
        ]
        row["total_cash_vnd"] = max(total or 0.0, 0.0)
        row["planner_cash_vnd"] = diagnostic["planner_cash_vnd"]
        row["cash_integrity"] = diagnostic
        token = str(row.get("selection_token") or "")
        if token:
            _CASH_DIAGNOSTICS[token] = diagnostic
    return rows


def _annotate_latest_cash(result: Mapping[str, object] | None) -> dict[str, object] | None:
    if result is None:
        return None
    value = dict(result)
    details = dict(value.get("details") or {})
    diagnostic = details.get("cash_integrity")
    if not isinstance(diagnostic, Mapping):
        diagnostic = validate_cash_contract(
            total_cash_vnd=value.get("total_cash_vnd"),
            available_cash_vnd=value.get("available_cash_vnd"),
            withdrawable_cash_vnd=value.get("withdrawable_cash_vnd"),
        )
        diagnostic = {**diagnostic, "status": "LEGACY_SNAPSHOT_DERIVED_" + str(diagnostic["status"])}
    diagnostic = dict(diagnostic)
    value["reported_available_cash_vnd"] = diagnostic.get(
        "reported_available_cash_vnd"
    )
    value["reported_withdrawable_cash_vnd"] = diagnostic.get(
        "reported_withdrawable_cash_vnd"
    )
    value["cash_integrity"] = diagnostic
    value["available_cash_vnd"] = float(
        diagnostic.get("validated_available_cash_vnd") or 0.0
    )
    value["withdrawable_cash_vnd"] = float(
        diagnostic.get("validated_withdrawable_cash_vnd") or 0.0
    )
    value["planner_cash_vnd"] = float(diagnostic.get("planner_cash_vnd") or 0.0)
    value["planning_cash_vnd"] = value["planner_cash_vnd"]
    details["cash_integrity"] = diagnostic
    details["planner_cash_source"] = "V51_VALIDATED_DNSE_CASH_CONTRACT"
    value["details"] = details
    value["version"] = V51_VERSION
    return value


def _latest_broker_v51() -> dict[str, object] | None:
    assert _ORIGINAL_LATEST_BROKER is not None
    return _annotate_latest_cash(_ORIGINAL_LATEST_BROKER())


def _sync_broker_v51() -> dict[str, object]:
    assert _ORIGINAL_SYNC_BROKER is not None
    result = dict(_ORIGINAL_SYNC_BROKER())
    details = dict(result.get("details") or {})
    token = str(details.get("selected_account_token") or "")
    diagnostic = _CASH_DIAGNOSTICS.get(token)
    if diagnostic:
        snapshot_id = str(result.get("snapshot_id") or "")
        details["cash_integrity"] = diagnostic
        details["planner_cash_source"] = "V51_VALIDATED_DNSE_CASH_CONTRACT"
        with state_db() as db:
            db.execute(
                """
                UPDATE broker_snapshots
                SET available_cash_vnd=?,withdrawable_cash_vnd=?,
                    planner_cash_vnd=?,details_json=?
                WHERE snapshot_id=?
                """,
                (
                    float(diagnostic["validated_available_cash_vnd"]),
                    float(diagnostic["validated_withdrawable_cash_vnd"]),
                    float(diagnostic["planner_cash_vnd"]),
                    json.dumps(details, ensure_ascii=False, sort_keys=True),
                    snapshot_id,
                ),
            )
    latest = _latest_broker_v51()
    if latest is None:
        raise RuntimeError("V51_BROKER_SNAPSHOT_READBACK_FAILED")
    return latest


def _json_details(row: Mapping[str, object]) -> dict[str, object]:
    value = row.get("details")
    if isinstance(value, Mapping):
        return dict(value)
    raw = row.get("details_json")
    if raw in (None, ""):
        return {}
    try:
        decoded = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _parse_datetime(value: object) -> datetime:
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.min.replace(tzinfo=VN_TZ)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TZ)
    return parsed


def _display_time_vn(value: object) -> str:
    parsed = _parse_datetime(value).astimezone(VN_TZ)
    if parsed.year <= 1:
        return "Không rõ giờ"
    return parsed.strftime("%d/%m/%Y %H:%M:%S")


def extract_plan_intents(
    plans: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    intents: dict[tuple[str, str, str], dict[str, object]] = {}
    for raw_plan in plans:
        plan = dict(raw_plan)
        details = _json_details(plan)
        plan_id = str(plan.get("plan_id") or "")
        if not plan_id:
            continue
        cycle_id = str(details.get("cycle_id") or "") or (
            str(plan.get("week_key") or "").removeprefix("CYCLE:") or None
        )
        created_at = str(plan.get("created_at") or "")
        rows: list[tuple[str, Mapping[str, object]]] = []
        rows.extend(("BUY", row) for row in details.get("buy_orders", []) if isinstance(row, Mapping))
        rows.extend(("SELL", row) for row in details.get("exit_candidates", []) if isinstance(row, Mapping))
        for side, row in rows:
            symbol = str(row.get("symbol") or "").upper()
            if not symbol:
                continue
            quantity = int(
                row.get("quantity")
                or row.get("sellable_quantity")
                or row.get("requested_quantity")
                or 0
            )
            if quantity <= 0:
                continue
            key = (plan_id, side, symbol)
            if key not in intents:
                intents[key] = {
                    "intent_id": f"{plan_id}:{side}:{symbol}",
                    "plan_id": plan_id,
                    "cycle_id": cycle_id,
                    "week_key": plan.get("week_key"),
                    "created_at": created_at,
                    "execution_day": plan.get("execution_day"),
                    "plan_status": plan.get("status"),
                    "side": side,
                    "symbol": symbol,
                    "planned_quantity": 0,
                    "planning_price_vnd": float(row.get("price_vnd") or 0.0),
                    "estimated_value_vnd": 0.0,
                }
            intents[key]["planned_quantity"] = int(intents[key]["planned_quantity"]) + quantity
            intents[key]["estimated_value_vnd"] = float(intents[key]["estimated_value_vnd"]) + float(
                row.get("estimated_cost_vnd") or row.get("market_value_vnd") or 0.0
            )
    return sorted(
        intents.values(),
        key=lambda row: (
            _parse_datetime(row["created_at"]),
            str(row["plan_id"]),
            str(row["side"]),
            str(row["symbol"]),
        ),
    )


def reconcile_intents(
    *,
    plans: Sequence[Mapping[str, object]],
    shadow_trades: Sequence[Mapping[str, object]],
    actual_fills: Sequence[Mapping[str, object]],
    latest_market_day: str | None,
) -> list[dict[str, object]]:
    intents = extract_plan_intents(plans)
    intent_by_key = {
        (str(row["plan_id"]), str(row["side"]), str(row["symbol"])): row
        for row in intents
    }
    assigned: dict[str, list[dict[str, object]]] = defaultdict(list)
    remaining = {
        str(row["intent_id"]): int(row["planned_quantity"])
        for row in intents
    }
    unmatched: list[dict[str, object]] = []

    ordered_actual = sorted(
        (dict(row) for row in actual_fills),
        key=lambda row: (
            _parse_datetime(row.get("event_time")),
            str(row.get("event_id") or ""),
        ),
    )

    for fill in ordered_actual:
        side = str(fill.get("side") or "").upper()
        symbol = str(fill.get("symbol") or "").upper()
        explicit_plan = str(fill.get("plan_id") or "")
        quantity_left = int(fill.get("quantity") or 0)
        if quantity_left <= 0:
            continue
        candidates: list[dict[str, object]] = []
        match_method = ""
        if explicit_plan:
            exact = intent_by_key.get((explicit_plan, side, symbol))
            if exact is not None:
                candidates = [exact]
                match_method = "EXPLICIT_PLAN_ID"
        else:
            event_time = _parse_datetime(fill.get("event_time"))
            candidates = [
                row
                for row in intents
                if row["side"] == side
                and row["symbol"] == symbol
                and remaining[str(row["intent_id"])] > 0
                and _parse_datetime(row["created_at"]) <= event_time
            ]
            candidates.sort(
                key=lambda row: _parse_datetime(row["created_at"]), reverse=True
            )
            if candidates:
                candidates = [candidates[0]]
                match_method = "AUTO_NEWEST_OPEN_INTENT"

        if not candidates:
            unmatched.append({**fill, "unmatched_quantity": quantity_left, "unmatched_reason": "NO_ELIGIBLE_PLAN_INTENT"})
            continue

        intent = candidates[0]
        intent_id = str(intent["intent_id"])
        allocated = min(quantity_left, remaining[intent_id])
        if allocated > 0:
            assigned[intent_id].append(
                {
                    "event_id": str(fill.get("event_id") or ""),
                    "event_day": str(fill.get("event_day") or "")[:10],
                    "event_time": str(fill.get("event_time") or ""),
                    "quantity": allocated,
                    "price_vnd": float(fill.get("price_vnd") or 0.0),
                    "fees_vnd": float(fill.get("fees_vnd") or 0.0),
                    "taxes_vnd": float(fill.get("taxes_vnd") or 0.0),
                    "match_method": match_method,
                }
            )
            remaining[intent_id] -= allocated
            quantity_left -= allocated
        if quantity_left > 0:
            unmatched.append({**fill, "unmatched_quantity": quantity_left, "unmatched_reason": "QUANTITY_EXCEEDS_OPEN_PLAN_INTENT"})

    shadow_by_key: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for raw in shadow_trades:
        row = dict(raw)
        shadow_by_key[(str(row.get("plan_id") or ""), str(row.get("side") or ""), str(row.get("symbol") or ""))].append(row)

    result: list[dict[str, object]] = []
    for intent in intents:
        intent_id = str(intent["intent_id"])
        fills = assigned.get(intent_id, [])
        actual_quantity = sum(int(row["quantity"]) for row in fills)
        actual_notional = sum(float(row["price_vnd"]) * int(row["quantity"]) for row in fills)
        actual_vwap = actual_notional / actual_quantity if actual_quantity > 0 else None
        shadow_rows = shadow_by_key.get(
            (str(intent["plan_id"]), str(intent["side"]), str(intent["symbol"])),
            [],
        )
        shadow_quantity = sum(int(row.get("filled_quantity") or 0) for row in shadow_rows)
        shadow_notional = sum(
            float(row.get("price_vnd") or 0.0) * int(row.get("filled_quantity") or 0)
            for row in shadow_rows
        )
        shadow_price = shadow_notional / shadow_quantity if shadow_quantity > 0 else None
        execution_day = str(intent.get("execution_day") or "") or None
        shadow_pending = shadow_quantity <= 0 and (
            execution_day is None
            or latest_market_day is None
            or execution_day > latest_market_day
        )
        planned_quantity = int(intent["planned_quantity"])
        if actual_quantity >= planned_quantity and actual_quantity > 0:
            status = "MATCHED_COMPLETE_SHADOW_PENDING" if shadow_pending else "MATCHED_COMPLETE"
        elif actual_quantity > 0:
            status = "MATCHED_PARTIAL_SHADOW_PENDING" if shadow_pending else "MATCHED_PARTIAL"
        else:
            status = "PLANNED_SHADOW_PENDING" if shadow_pending else "MISSED"
        first_actual_day = min((row["event_day"] for row in fills), default=None)
        delay = None
        if first_actual_day:
            delay = (
                date.fromisoformat(first_actual_day)
                - _parse_datetime(intent["created_at"]).date()
            ).days
        sign = 1.0 if intent["side"] == "BUY" else -1.0
        slippage = (
            sign * (float(actual_vwap) / float(shadow_price) - 1.0)
            if actual_vwap is not None and shadow_price not in (None, 0.0)
            else None
        )
        result.append(
            {
                "intent_id": intent_id,
                "plan_id": intent["plan_id"],
                "cycle_id": intent.get("cycle_id"),
                "week_key": intent.get("week_key"),
                "cycle_created_at": intent["created_at"],
                "cycle_created_at_vn": _display_time_vn(intent["created_at"]),
                "side": intent["side"],
                "symbol": intent["symbol"],
                "proposed_quantity": planned_quantity,
                "planned_quantity": planned_quantity,
                "actual_quantity": actual_quantity,
                "actual_price_vnd": actual_vwap,
                "actual_vwap_vnd": actual_vwap,
                "actual_event_ids": [row["event_id"] for row in fills],
                "actual_day": first_actual_day,
                "shadow_quantity": shadow_quantity,
                "shadow_execution_day": execution_day,
                "shadow_price_vnd": shadow_price,
                "shadow_pending": shadow_pending,
                "execution_delay_days": delay,
                "quantity_compliance": min(actual_quantity / max(planned_quantity, 1), 1.0),
                "remaining_quantity": max(planned_quantity - actual_quantity, 0),
                "price_slippage": slippage,
                "match_method": ",".join(sorted({str(row["match_method"]) for row in fills})) or None,
                "status": status,
            }
        )

    for fill in unmatched:
        result.append(
            {
                "intent_id": None,
                "plan_id": fill.get("plan_id"),
                "cycle_id": None,
                "week_key": None,
                "cycle_created_at": None,
                "cycle_created_at_vn": None,
                "side": fill.get("side"),
                "symbol": fill.get("symbol"),
                "proposed_quantity": 0,
                "planned_quantity": 0,
                "actual_quantity": int(fill.get("unmatched_quantity") or 0),
                "actual_price_vnd": fill.get("price_vnd"),
                "actual_vwap_vnd": fill.get("price_vnd"),
                "actual_event_ids": [fill.get("event_id")],
                "actual_day": fill.get("event_day"),
                "shadow_quantity": 0,
                "shadow_execution_day": None,
                "shadow_price_vnd": None,
                "shadow_pending": False,
                "execution_delay_days": None,
                "quantity_compliance": None,
                "remaining_quantity": 0,
                "price_slippage": None,
                "match_method": None,
                "unmatched_reason": fill.get("unmatched_reason"),
                "status": "OUTSIDE_PLAN_CONFIRMED",
            }
        )
    return result


def _load_reconciliation_inputs() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], str | None]:
    with state_db() as db:
        performance._ensure_schema(db)
        plans = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_shadow_plans ORDER BY created_at,week_key"
            ).fetchall()
        ]
        shadow = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_shadow_trades ORDER BY execution_day,trade_id"
            ).fetchall()
        ]
    actual = [
        dict(row)
        for row in performance._actual_events()
        if str(row.get("event_type") or "") == "ACTUAL_FILL"
    ]
    try:
        market_days = list(performance._market_days())
        latest_day = market_days[-1] if market_days else None
    except Exception:
        latest_day = None
    return plans, shadow, actual, latest_day


def reconciliation_v51() -> list[dict[str, object]]:
    plans, shadow, actual, latest_day = _load_reconciliation_inputs()
    return reconcile_intents(
        plans=plans,
        shadow_trades=shadow,
        actual_fills=actual,
        latest_market_day=latest_day,
    )


def build_cycle_catalog(
    plans: Sequence[Mapping[str, object]],
    reconciliation: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows_by_plan: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in reconciliation:
        plan_id = str(row.get("plan_id") or "")
        if plan_id and row.get("intent_id"):
            rows_by_plan[plan_id].append(dict(row))
    ordered_plans = sorted(
        (dict(row) for row in plans),
        key=lambda row: _parse_datetime(row.get("created_at")),
        reverse=True,
    )
    newest_plan_id = str(ordered_plans[0].get("plan_id") or "") if ordered_plans else ""
    result: list[dict[str, object]] = []
    for index, plan in enumerate(ordered_plans):
        details = _json_details(plan)
        plan_id = str(plan.get("plan_id") or "")
        intents = rows_by_plan.get(plan_id, [])
        planned = sum(int(row.get("planned_quantity") or 0) for row in intents)
        actual = sum(int(row.get("actual_quantity") or 0) for row in intents)
        remaining = sum(int(row.get("remaining_quantity") or 0) for row in intents)
        if intents and remaining <= 0:
            status = "ACTUAL_COMPLETE"
        elif actual > 0:
            status = "IN_PROGRESS"
        elif intents:
            status = "OPEN"
        else:
            status = "NO_TRADE_INTENT"
        cycle_id = str(details.get("cycle_id") or "") or (
            str(plan.get("week_key") or "").removeprefix("CYCLE:") or None
        )
        symbols = [str(row["symbol"]) for row in intents]
        prefix = "MỚI NHẤT" if plan_id == newest_plan_id else "CŨ"
        suffix = plan_id[-6:] if plan_id else "------"
        display_time = _display_time_vn(plan.get("created_at"))
        display_label = (
            f"{prefix} · {display_time} · {len(intents)} lệnh · "
            f"{', '.join(symbols) or 'không có lệnh'} · còn {remaining} cp · plan …{suffix}"
        )
        result.append(
            {
                "plan_id": plan_id,
                "cycle_id": cycle_id,
                "week_key": plan.get("week_key"),
                "created_at": plan.get("created_at"),
                "created_at_vn": display_time,
                "execution_day": plan.get("execution_day"),
                "shadow_status": plan.get("status"),
                "newest": plan_id == newest_plan_id,
                "age_index": index,
                "status": status,
                "planned_quantity": planned,
                "actual_quantity": actual,
                "remaining_quantity": remaining,
                "new_capital_vnd": float(plan.get("planned_contribution_vnd") or details.get("new_capital_vnd") or 0.0),
                "symbols": symbols,
                "display_label": display_label,
                "intents": [
                    {
                        "intent_id": row.get("intent_id"),
                        "side": row.get("side"),
                        "symbol": row.get("symbol"),
                        "planned_quantity": row.get("planned_quantity"),
                        "actual_quantity": row.get("actual_quantity"),
                        "remaining_quantity": row.get("remaining_quantity"),
                        "status": row.get("status"),
                    }
                    for row in intents
                ],
            }
        )
    return result


def performance_status_v51() -> dict[str, object]:
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    status["v51_version"] = V51_VERSION
    if status.get("status") != "ACTIVE":
        return status
    plans, _, _, _ = _load_reconciliation_inputs()
    reconciliation = reconciliation_v51()
    status["reconciliation"] = reconciliation
    status["cycle_catalog"] = build_cycle_catalog(plans, reconciliation)
    limitations = dict(status.get("limitations") or {})
    limitations.update(
        {
            "reconciliation_uses_plan_intent_before_shadow_execution": True,
            "multiple_actual_fills_are_aggregated": True,
            "unmatched_status_requires_no_eligible_plan_intent": True,
            "planner_cash_rejects_available_above_total_cash": True,
            "ppse_enabled": False,
        }
    )
    status["limitations"] = limitations
    return status


def apply() -> None:
    if getattr(performance, "_v51_integrity_applied", False):
        return
    global _ORIGINAL_PROBE, _ORIGINAL_SYNC_BROKER, _ORIGINAL_LATEST_BROKER
    global _ORIGINAL_PERFORMANCE_STATUS

    _ORIGINAL_PROBE = source_integrity_v49._probe_accounts
    _ORIGINAL_SYNC_BROKER = broker_portfolio.sync_broker_portfolio
    _ORIGINAL_LATEST_BROKER = broker_portfolio.latest_broker_portfolio
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status

    source_integrity_v49._probe_accounts = _probe_accounts_v51
    broker_portfolio.sync_broker_portfolio = _sync_broker_v51
    broker_portfolio.latest_broker_portfolio = _latest_broker_v51
    weekly_plan.latest_broker_portfolio = _latest_broker_v51
    capital_plan.latest_broker_portfolio = _latest_broker_v51
    performance.latest_broker_portfolio = _latest_broker_v51

    performance._reconciliation = reconciliation_v51
    performance.performance_status = performance_status_v51
    performance.V51_VERSION = V51_VERSION
    performance._v51_integrity_applied = True
