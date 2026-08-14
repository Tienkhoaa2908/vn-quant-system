"""V48 auditable corrections for manually confirmed performance events.

The original ledger remains append-only. A correction never updates or deletes a
confirmed row. It appends either EVENT_VOID or EVENT_REPLACEMENT and all NAV,
position and reconciliation calculations consume only the effective event set.
"""
from __future__ import annotations

from datetime import date
import json
import math
from typing import Mapping, Sequence
from uuid import uuid4

from . import performance
from .core import state_db, utc_now

CORRECTIONS_VERSION = "V48_AUDITABLE_EVENT_CORRECTIONS"
EDITABLE_EVENT_TYPES = {"ACTUAL_CASHFLOW", "ACTUAL_FILL"}
CORRECTION_EVENT_TYPES = {"EVENT_VOID", "EVENT_REPLACEMENT"}
VALID_PRICE_UNITS = {"VND", "THOUSAND_VND"}
MIN_REASONABLE_STOCK_PRICE_VND = 1_000.0

_ORIGINAL_PERFORMANCE_STATUS = None


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


def _raw_events() -> list[dict[str, object]]:
    with state_db() as db:
        performance._ensure_schema(db)
        rows = db.execute(
            """
            SELECT * FROM performance_events
            ORDER BY event_day,event_time,event_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def correction_index(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Return the latest append-only correction affecting each target event."""

    result: dict[str, dict[str, object]] = {}
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("event_time") or ""),
            str(row.get("event_id") or ""),
        ),
    )
    for row in ordered:
        event_type = str(row.get("event_type") or "")
        if event_type not in CORRECTION_EVENT_TYPES:
            continue
        details = _json_details(row)
        target = str(details.get("target_event_id") or "")
        if not target:
            continue
        result[target] = {
            "status": "VOIDED" if event_type == "EVENT_VOID" else "REPLACED",
            "correction_event_id": str(row.get("event_id") or ""),
            "replacement_event_id": details.get("replacement_event_id"),
            "reason": details.get("reason"),
            "corrected_at": row.get("event_time"),
        }
    return result


def normalize_fill_price(
    value: object,
    unit: str = "VND",
    *,
    allow_suspicious_low: bool = False,
) -> float:
    normalized_unit = str(unit or "VND").upper()
    if normalized_unit not in VALID_PRICE_UNITS:
        raise ValueError("PERFORMANCE_FILL_PRICE_UNIT_INVALID")
    price = float(value)
    if not math.isfinite(price) or price <= 0:
        raise ValueError("PERFORMANCE_FILL_PRICE_INVALID")
    if normalized_unit == "THOUSAND_VND":
        price *= 1_000.0
    if price < MIN_REASONABLE_STOCK_PRICE_VND and not allow_suspicious_low:
        raise ValueError(
            "PERFORMANCE_FILL_PRICE_SUSPICIOUS_LOW:"
            f"{price:.0f}:ENTER_VND_OR_USE_THOUSAND_VND"
        )
    return price


def valuation_info(
    event: Mapping[str, object],
    market_days: Sequence[str],
) -> dict[str, object]:
    event_type = str(event.get("event_type") or "")
    event_day = str(event.get("event_day") or "")[:10]
    if event_type in CORRECTION_EVENT_TYPES:
        return {"status": "AUDIT_ONLY", "valuation_day": None}
    if event_type not in EDITABLE_EVENT_TYPES:
        return {"status": "SYSTEM_EVENT", "valuation_day": event_day or None}
    ordered = sorted({str(day)[:10] for day in market_days if day})
    if not ordered:
        return {"status": "PENDING_VALUATION", "valuation_day": None}
    latest = ordered[-1]
    if event_day > latest:
        return {"status": "PENDING_VALUATION", "valuation_day": None}
    if event_day in set(ordered):
        return {"status": "APPLIED", "valuation_day": event_day}
    if event_type == "ACTUAL_FILL":
        return {"status": "INVALID_MARKET_DAY", "valuation_day": None}
    next_session = next((day for day in ordered if day >= event_day), None)
    if next_session is None:
        return {"status": "PENDING_VALUATION", "valuation_day": None}
    return {
        "status": "APPLIED_NEXT_SESSION",
        "valuation_day": next_session,
    }


def _market_days_safe() -> list[str]:
    try:
        return list(performance._market_days())
    except Exception:
        return []


def _effective_event_rows_from(
    rows: Sequence[Mapping[str, object]],
    *,
    market_days: Sequence[str] | None = None,
    exclude_event_ids: set[str] | None = None,
    extra_events: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    all_rows = [dict(row) for row in rows]
    if extra_events:
        all_rows.extend(dict(row) for row in extra_events)
    corrected = correction_index(all_rows)
    excluded = set(exclude_event_ids or set())
    calendar = list(market_days if market_days is not None else _market_days_safe())
    effective: list[dict[str, object]] = []
    for raw in all_rows:
        event_id = str(raw.get("event_id") or "")
        event_type = str(raw.get("event_type") or "")
        if (
            event_type not in EDITABLE_EVENT_TYPES
            or event_id in corrected
            or event_id in excluded
        ):
            continue
        info = valuation_info(raw, calendar)
        if info["status"] == "INVALID_MARKET_DAY":
            continue
        row = dict(raw)
        details = _json_details(row)
        original_day = str(row.get("event_day") or "")[:10]
        if info.get("valuation_day"):
            row["event_day"] = str(info["valuation_day"])
        details.update(
            {
                "original_event_day": original_day,
                "valuation_status": info["status"],
                "valuation_day": info.get("valuation_day"),
            }
        )
        effective_time = str(
            details.get("effective_event_time")
            or row.get("event_time")
            or ""
        )
        row["event_time"] = effective_time
        row["details"] = details
        row["details_json"] = json.dumps(
            details, ensure_ascii=False, sort_keys=True
        )
        effective.append(row)
    effective.sort(
        key=lambda row: (
            str(row.get("event_day") or ""),
            str(row.get("event_time") or ""),
            str(row.get("event_id") or ""),
        )
    )
    return effective


def effective_actual_events() -> list[dict[str, object]]:
    return _effective_event_rows_from(_raw_events())


def _opening_position_quantities() -> dict[str, int]:
    return {
        str(row["symbol"]): int(row["quantity"])
        for row in performance._opening_positions()
        if row["classification"] == performance.ADOPTED_AT_START
    }


def _assert_nonnegative_position_history(
    rows: Sequence[Mapping[str, object]],
) -> None:
    positions = _opening_position_quantities()
    for row in sorted(
        rows,
        key=lambda item: (
            str(item.get("event_day") or ""),
            str(item.get("event_time") or ""),
            str(item.get("event_id") or ""),
        ),
    ):
        if str(row.get("event_type") or "") != "ACTUAL_FILL":
            continue
        symbol = str(row.get("symbol") or "").upper()
        quantity = int(row.get("quantity") or 0)
        if str(row.get("side") or "").upper() == "BUY":
            positions[symbol] = positions.get(symbol, 0) + quantity
        else:
            positions[symbol] = positions.get(symbol, 0) - quantity
            if positions[symbol] < 0:
                raise ValueError(
                    "PERFORMANCE_CORRECTION_BREAKS_POSITION_HISTORY:"
                    f"{symbol}"
                )


def _event_by_id(event_id: str) -> dict[str, object]:
    target = str(event_id or "").strip()
    if not target:
        raise ValueError("PERFORMANCE_EVENT_ID_REQUIRED")
    with state_db() as db:
        performance._ensure_schema(db)
        row = db.execute(
            "SELECT * FROM performance_events WHERE event_id=?",
            (target,),
        ).fetchone()
    if row is None:
        raise ValueError("PERFORMANCE_EVENT_NOT_FOUND")
    return dict(row)


def _assert_editable_target(
    target: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> None:
    event_type = str(target.get("event_type") or "")
    source = str(target.get("source") or "")
    event_id = str(target.get("event_id") or "")
    if event_type not in EDITABLE_EVENT_TYPES or not source.startswith(
        "USER_CONFIRMED"
    ):
        raise ValueError("PERFORMANCE_EVENT_NOT_EDITABLE")
    if event_id in correction_index(rows):
        raise ValueError("PERFORMANCE_EVENT_ALREADY_CORRECTED")


def _new_event_row(
    *,
    event_type: str,
    stream: str,
    source: str,
    event_day: str,
    amount_vnd: float = 0.0,
    symbol: str | None = None,
    side: str | None = None,
    quantity: int | None = None,
    price_vnd: float | None = None,
    fees_vnd: float = 0.0,
    taxes_vnd: float = 0.0,
    plan_id: str | None = None,
    note: str | None = None,
    details: Mapping[str, object] | None = None,
    recorded_at: str | None = None,
) -> dict[str, object]:
    timestamp = recorded_at or utc_now()
    payload = {
        "event_type": event_type,
        "stream": stream,
        "source": source,
        "event_day": performance._iso_day(event_day),
        "recorded_at": timestamp,
        "nonce": uuid4().hex,
        "amount_vnd": round(float(amount_vnd), 4),
        "symbol": symbol.upper() if symbol else None,
        "side": side.upper() if side else None,
        "quantity": int(quantity) if quantity is not None else None,
        "price_vnd": round(float(price_vnd), 4) if price_vnd is not None else None,
        "fees_vnd": round(float(fees_vnd), 4),
        "taxes_vnd": round(float(taxes_vnd), 4),
        "plan_id": plan_id,
        "note": note,
        "details": dict(details or {}),
    }
    digest = performance._event_hash(payload)
    return {
        "event_id": "perf-" + digest[:20],
        "event_time": timestamp,
        "event_day": payload["event_day"],
        "event_type": event_type,
        "stream": stream,
        "source": source,
        "amount_vnd": payload["amount_vnd"],
        "symbol": payload["symbol"],
        "side": payload["side"],
        "quantity": payload["quantity"],
        "price_vnd": payload["price_vnd"],
        "fees_vnd": payload["fees_vnd"],
        "taxes_vnd": payload["taxes_vnd"],
        "plan_id": plan_id,
        "note": note,
        "event_hash": digest,
        "details": payload["details"],
        "details_json": json.dumps(
            payload["details"], ensure_ascii=False, sort_keys=True
        ),
    }


def _insert_rows(db, rows: Sequence[Mapping[str, object]]) -> None:
    db.executemany(
        """
        INSERT INTO performance_events(
            event_id,event_time,event_day,event_type,stream,source,
            amount_vnd,symbol,side,quantity,price_vnd,fees_vnd,taxes_vnd,
            plan_id,note,event_hash,details_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                row["event_id"],
                row["event_time"],
                row["event_day"],
                row["event_type"],
                row["stream"],
                row["source"],
                row["amount_vnd"],
                row.get("symbol"),
                row.get("side"),
                row.get("quantity"),
                row.get("price_vnd"),
                row["fees_vnd"],
                row["taxes_vnd"],
                row.get("plan_id"),
                row.get("note"),
                row["event_hash"],
                row["details_json"],
            )
            for row in rows
        ],
    )


def _validate_fill_day(day: str) -> None:
    market_days = _market_days_safe()
    if not market_days:
        return
    latest = market_days[-1]
    if day <= latest and day not in set(market_days):
        raise ValueError("PERFORMANCE_FILL_DAY_NOT_MARKET_SESSION")


def add_actual_cashflow_v48(
    *,
    flow_type: str,
    amount_vnd: float,
    event_day: str,
    note: str | None = None,
) -> dict[str, object]:
    kind = str(flow_type or "").upper()
    if kind in {"VOID_EVENT", "REPLACE_EVENT"}:
        try:
            command = json.loads(str(note or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("PERFORMANCE_CORRECTION_PAYLOAD_INVALID") from exc
        if not isinstance(command, Mapping):
            raise ValueError("PERFORMANCE_CORRECTION_PAYLOAD_INVALID")
        if kind == "VOID_EVENT":
            return void_actual_event(
                event_id=str(command.get("event_id") or ""),
                reason=str(command.get("reason") or ""),
            )
        replacement = command.get("replacement")
        if not isinstance(replacement, Mapping):
            raise ValueError("PERFORMANCE_REPLACEMENT_PAYLOAD_INVALID")
        return replace_actual_event(
            event_id=str(command.get("event_id") or ""),
            replacement=replacement,
            reason=str(command.get("reason") or ""),
        )

    day = performance._iso_day(event_day)
    performance._assert_event_day(day)
    amount = float(amount_vnd)
    if kind not in performance.VALID_CASHFLOW_TYPES or amount <= 0:
        raise ValueError("PERFORMANCE_CASHFLOW_INVALID")
    info = valuation_info(
        {"event_type": "ACTUAL_CASHFLOW", "event_day": day},
        _market_days_safe(),
    )
    event = performance._append_event(
        event_type="ACTUAL_CASHFLOW",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CONFIRMED",
        event_day=day,
        amount_vnd=amount if kind == "DEPOSIT" else -amount,
        note=note,
        details={
            "flow_type": kind,
            "valuation_status_at_entry": info["status"],
        },
    )
    performance.refresh_performance()
    return event


def add_actual_fill_v48(
    *,
    side: str,
    symbol: str,
    quantity: int,
    price_vnd: float,
    event_day: str,
    fees_vnd: float = 0.0,
    taxes_vnd: float = 0.0,
    plan_id: str | None = None,
    note: str | None = None,
    price_unit: str = "VND",
    allow_suspicious_low_price: bool = False,
) -> dict[str, object]:
    day = performance._iso_day(event_day)
    performance._assert_event_day(day)
    _validate_fill_day(day)
    normalized_side = str(side or "").upper()
    ticker = str(symbol or "").strip().upper()
    qty = int(quantity)
    price = normalize_fill_price(
        price_vnd,
        price_unit,
        allow_suspicious_low=allow_suspicious_low_price,
    )
    fees = float(fees_vnd)
    taxes = float(taxes_vnd)
    if normalized_side not in performance.VALID_SIDES or not ticker or qty <= 0:
        raise ValueError("PERFORMANCE_FILL_INVALID")
    if fees < 0 or taxes < 0:
        raise ValueError("PERFORMANCE_FILL_COST_NEGATIVE")
    _, positions = performance._actual_state_until(day)
    if normalized_side == "SELL" and positions.get(ticker, 0) < qty:
        raise ValueError("PERFORMANCE_SELL_EXCEEDS_MODEL_SLEEVE_POSITION")
    gross = qty * price
    info = valuation_info(
        {"event_type": "ACTUAL_FILL", "event_day": day},
        _market_days_safe(),
    )
    event = performance._append_event(
        event_type="ACTUAL_FILL",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CONFIRMED_DNSE_FILL",
        event_day=day,
        amount_vnd=gross,
        symbol=ticker,
        side=normalized_side,
        quantity=qty,
        price_vnd=price,
        fees_vnd=fees,
        taxes_vnd=taxes,
        plan_id=plan_id,
        note=note,
        details={
            "gross_vnd": gross,
            "price_is_confirmed": True,
            "price_input_unit": str(price_unit or "VND").upper(),
            "valuation_status_at_entry": info["status"],
        },
    )
    performance.refresh_performance()
    return event


def void_actual_event(*, event_id: str, reason: str) -> dict[str, object]:
    reason_text = str(reason or "").strip()
    if not reason_text:
        raise ValueError("PERFORMANCE_CORRECTION_REASON_REQUIRED")
    rows = _raw_events()
    target = _event_by_id(event_id)
    _assert_editable_target(target, rows)
    proposed = _effective_event_rows_from(
        rows,
        exclude_event_ids={str(target["event_id"])},
    )
    _assert_nonnegative_position_history(proposed)
    correction = _new_event_row(
        event_type="EVENT_VOID",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CORRECTION",
        event_day=date.today().isoformat(),
        note=reason_text,
        details={
            "correction_kind": "VOID",
            "target_event_id": str(target["event_id"]),
            "reason": reason_text,
        },
    )
    with state_db() as db:
        performance._ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            _insert_rows(db, [correction])
        except Exception:
            db.rollback()
            raise
        else:
            db.commit()
    status = performance.refresh_performance()
    return {
        "status": "SUCCESS",
        "correction": correction,
        "target_event_id": str(target["event_id"]),
        "performance": status,
    }


def _replacement_base_row(
    target: Mapping[str, object],
    replacement: Mapping[str, object],
    reason: str,
    recorded_at: str,
) -> dict[str, object]:
    target_type = str(target["event_type"])
    original_details = _json_details(target)
    logical_time = str(target.get("event_time") or recorded_at)
    if target_type == "ACTUAL_CASHFLOW":
        kind = str(
            replacement.get("flow_type")
            or original_details.get("flow_type")
            or ("DEPOSIT" if float(target["amount_vnd"]) >= 0 else "WITHDRAWAL")
        ).upper()
        amount = abs(float(replacement.get("amount_vnd") or 0.0))
        day = performance._iso_day(
            replacement.get("event_day") or target["event_day"]
        )
        performance._assert_event_day(day)
        if kind not in performance.VALID_CASHFLOW_TYPES or amount <= 0:
            raise ValueError("PERFORMANCE_CASHFLOW_INVALID")
        return _new_event_row(
            event_type="ACTUAL_CASHFLOW",
            stream="ACTUAL_MODEL_SLEEVE",
            source="USER_CONFIRMED_CORRECTION",
            event_day=day,
            amount_vnd=amount if kind == "DEPOSIT" else -amount,
            note=str(replacement.get("note") or target.get("note") or "") or None,
            recorded_at=recorded_at,
            details={
                "flow_type": kind,
                "replaces_event_id": str(target["event_id"]),
                "correction_reason": reason,
                "effective_event_time": logical_time,
            },
        )

    side = str(replacement.get("side") or target.get("side") or "").upper()
    symbol = str(
        replacement.get("symbol") or target.get("symbol") or ""
    ).strip().upper()
    quantity = int(replacement.get("quantity") or 0)
    day = performance._iso_day(
        replacement.get("event_day") or target["event_day"]
    )
    performance._assert_event_day(day)
    _validate_fill_day(day)
    price_unit = str(replacement.get("price_unit") or "VND").upper()
    price = normalize_fill_price(
        replacement.get("price_vnd") or 0.0,
        price_unit,
    )
    fees = float(replacement.get("fees_vnd") or 0.0)
    taxes = float(replacement.get("taxes_vnd") or 0.0)
    if side not in performance.VALID_SIDES or not symbol or quantity <= 0:
        raise ValueError("PERFORMANCE_FILL_INVALID")
    if fees < 0 or taxes < 0:
        raise ValueError("PERFORMANCE_FILL_COST_NEGATIVE")
    gross = quantity * price
    return _new_event_row(
        event_type="ACTUAL_FILL",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CONFIRMED_CORRECTION",
        event_day=day,
        amount_vnd=gross,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price_vnd=price,
        fees_vnd=fees,
        taxes_vnd=taxes,
        plan_id=(
            str(replacement.get("plan_id"))
            if replacement.get("plan_id")
            else target.get("plan_id")
        ),
        note=str(replacement.get("note") or target.get("note") or "") or None,
        recorded_at=recorded_at,
        details={
            "gross_vnd": gross,
            "price_is_confirmed": True,
            "price_input_unit": price_unit,
            "replaces_event_id": str(target["event_id"]),
            "correction_reason": reason,
            "effective_event_time": logical_time,
        },
    )


def replace_actual_event(
    *,
    event_id: str,
    replacement: Mapping[str, object],
    reason: str,
) -> dict[str, object]:
    reason_text = str(reason or "").strip()
    if not reason_text:
        raise ValueError("PERFORMANCE_CORRECTION_REASON_REQUIRED")
    rows = _raw_events()
    target = _event_by_id(event_id)
    _assert_editable_target(target, rows)
    timestamp = utc_now()
    replacement_row = _replacement_base_row(
        target,
        replacement,
        reason_text,
        timestamp,
    )
    correction = _new_event_row(
        event_type="EVENT_REPLACEMENT",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CORRECTION",
        event_day=date.today().isoformat(),
        note=reason_text,
        recorded_at=timestamp,
        details={
            "correction_kind": "REPLACEMENT",
            "target_event_id": str(target["event_id"]),
            "replacement_event_id": str(replacement_row["event_id"]),
            "reason": reason_text,
        },
    )
    proposed = _effective_event_rows_from(
        rows,
        exclude_event_ids={str(target["event_id"])},
        extra_events=[replacement_row],
    )
    _assert_nonnegative_position_history(proposed)
    with state_db() as db:
        performance._ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            _insert_rows(db, [replacement_row, correction])
        except Exception:
            db.rollback()
            raise
        else:
            db.commit()
    status = performance.refresh_performance()
    return {
        "status": "SUCCESS",
        "correction": correction,
        "replacement": replacement_row,
        "target_event_id": str(target["event_id"]),
        "performance": status,
    }


def reconciliation_v48() -> list[dict[str, object]]:
    with state_db() as db:
        performance._ensure_schema(db)
        plans = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_shadow_plans ORDER BY created_at"
            ).fetchall()
        ]
        shadow = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_shadow_trades
                ORDER BY execution_day,trade_id
                """
            ).fetchall()
        ]
    actual = [
        row
        for row in effective_actual_events()
        if str(row.get("event_type")) == "ACTUAL_FILL"
    ]
    used: set[str] = set()
    result: list[dict[str, object]] = []
    for plan in plans:
        plan_id = str(plan["plan_id"])
        for proposed in [row for row in shadow if row["plan_id"] == plan_id]:
            candidates = [
                row
                for row in actual
                if str(row["event_id"]) not in used
                and str(row.get("symbol")) == str(proposed["symbol"])
                and str(row.get("side")) == str(proposed["side"])
                and (
                    str(row.get("plan_id") or "") == plan_id
                    or (
                        not row.get("plan_id")
                        and str(row.get("event_day"))
                        >= str(plan["created_at"])[:10]
                    )
                )
            ]
            matched = candidates[0] if candidates else None
            if matched:
                used.add(str(matched["event_id"]))
            delay = None
            slippage = None
            compliance = 0.0
            status = "MISSED"
            if matched:
                delay = (
                    date.fromisoformat(str(matched["event_day"])[:10])
                    - date.fromisoformat(str(plan["created_at"])[:10])
                ).days
                shadow_price = float(proposed["price_vnd"])
                actual_price = float(matched["price_vnd"])
                sign = 1.0 if proposed["side"] == "BUY" else -1.0
                slippage = (
                    sign * (actual_price / shadow_price - 1.0)
                    if shadow_price > 0
                    else None
                )
                compliance = min(
                    int(matched.get("quantity") or 0)
                    / max(int(proposed["filled_quantity"]), 1),
                    1.0,
                )
                status = (
                    "EXECUTED"
                    if compliance >= 0.999
                    else "PARTIALLY_EXECUTED"
                )
            result.append(
                {
                    "plan_id": plan_id,
                    "week_key": plan["week_key"],
                    "symbol": proposed["symbol"],
                    "side": proposed["side"],
                    "proposed_quantity": proposed["filled_quantity"],
                    "shadow_execution_day": proposed["execution_day"],
                    "shadow_price_vnd": proposed["price_vnd"],
                    "actual_event_id": matched["event_id"] if matched else None,
                    "actual_day": matched["event_day"] if matched else None,
                    "actual_quantity": matched["quantity"] if matched else 0,
                    "actual_price_vnd": matched["price_vnd"] if matched else None,
                    "execution_delay_days": delay,
                    "quantity_compliance": compliance,
                    "price_slippage": slippage,
                    "status": status,
                }
            )
    for row in actual:
        if str(row["event_id"]) in used:
            continue
        result.append(
            {
                "plan_id": row.get("plan_id"),
                "week_key": None,
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "proposed_quantity": 0,
                "shadow_execution_day": None,
                "shadow_price_vnd": None,
                "actual_event_id": row.get("event_id"),
                "actual_day": row.get("event_day"),
                "actual_quantity": row.get("quantity"),
                "actual_price_vnd": row.get("price_vnd"),
                "execution_delay_days": None,
                "quantity_compliance": None,
                "price_slippage": None,
                "status": "EXTRA_OR_UNMATCHED",
            }
        )
    return result


def _annotated_events(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    corrections = correction_index(rows)
    calendar = _market_days_safe()
    result: list[dict[str, object]] = []
    for raw in rows:
        row = dict(raw)
        details = _json_details(row)
        row["details"] = details
        event_id = str(row.get("event_id") or "")
        event_type = str(row.get("event_type") or "")
        if event_type in CORRECTION_EVENT_TYPES:
            correction_status = "AUDIT_ONLY"
            correction = None
        else:
            correction = corrections.get(event_id)
            correction_status = (
                str(correction["status"]) if correction else "ACTIVE"
            )
        info = valuation_info(row, calendar)
        if correction_status in {"VOIDED", "REPLACED"}:
            valuation_status = correction_status
            valuation_day = None
        else:
            valuation_status = str(info["status"])
            valuation_day = info.get("valuation_day")
        row.update(
            {
                "correction_status": correction_status,
                "correction": correction,
                "valuation_status": valuation_status,
                "valuation_day": valuation_day,
                "editable": bool(
                    event_type in EDITABLE_EVENT_TYPES
                    and str(row.get("source") or "").startswith(
                        "USER_CONFIRMED"
                    )
                    and correction is None
                ),
            }
        )
        result.append(row)
    return result


def performance_status_v48() -> dict[str, object]:
    assert _ORIGINAL_PERFORMANCE_STATUS is not None
    status = dict(_ORIGINAL_PERFORMANCE_STATUS())
    if status.get("status") != "ACTIVE":
        status["corrections_version"] = CORRECTIONS_VERSION
        return status
    annotated = _annotated_events(_raw_events())
    status["version"] = CORRECTIONS_VERSION
    status["corrections_version"] = CORRECTIONS_VERSION
    status["events"] = annotated
    status["latest_market_day"] = (
        _market_days_safe()[-1] if _market_days_safe() else None
    )
    status["pending_valuation_count"] = sum(
        row.get("valuation_status") == "PENDING_VALUATION"
        for row in annotated
    )
    limitations = dict(status.get("limitations") or {})
    limitations.update(
        {
            "event_ledger_append_only": True,
            "manual_events_can_be_voided_or_replaced_with_audit": True,
            "direct_event_update_or_delete_allowed": False,
            "suspicious_low_fill_price_is_blocked": True,
        }
    )
    status["limitations"] = limitations
    return status


def apply() -> None:
    global _ORIGINAL_PERFORMANCE_STATUS
    if getattr(performance, "_v48_corrections_applied", False):
        return
    _ORIGINAL_PERFORMANCE_STATUS = performance.performance_status
    performance._actual_events = effective_actual_events
    performance._reconciliation = reconciliation_v48
    performance.add_actual_cashflow = add_actual_cashflow_v48
    performance.add_actual_fill = add_actual_fill_v48
    performance.void_actual_event = void_actual_event
    performance.replace_actual_event = replace_actual_event
    performance.performance_status = performance_status_v48
    performance.OBSERVATORY_VERSION = CORRECTIONS_VERSION
    performance._v48_corrections_applied = True
