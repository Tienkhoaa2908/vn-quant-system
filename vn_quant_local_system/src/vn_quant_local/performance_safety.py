"""Runtime safety fixes cho V45.

Module này được package init áp dụng ngay khi import. Nó giữ implementation chính
ổn định nhưng khóa hai edge case:

* XIRR không được công bố khi chưa có thời gian trôi qua;
* hai fill/dòng tiền có cùng nội dung vẫn phải là hai event độc lập.
"""
from __future__ import annotations

from datetime import date
import json
from typing import Mapping, Sequence

from . import performance
from .core import state_db, utc_now


def safe_xirr(
    flows: Sequence[tuple[date, float]],
) -> float | None:
    if (
        len(flows) < 2
        or max(day for day, _ in flows) <= min(day for day, _ in flows)
        or not any(value < 0 for _, value in flows)
        or not any(value > 0 for _, value in flows)
    ):
        return None
    low, high = -0.9999, 10.0
    low_value = performance._xnpv(low, flows)
    high_value = performance._xnpv(high, flows)
    attempts = 0
    while low_value * high_value > 0 and attempts < 8:
        high *= 10.0
        high_value = performance._xnpv(high, flows)
        attempts += 1
    if low_value * high_value > 0:
        return None
    for _ in range(200):
        middle = (low + high) / 2.0
        value = performance._xnpv(middle, flows)
        if abs(value) < 1e-7:
            return middle
        if low_value * value <= 0:
            high = middle
        else:
            low = middle
            low_value = value
    return (low + high) / 2.0


def append_unique_event(
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
) -> dict[str, object]:
    normalized_day = performance._iso_day(event_day)
    recorded_at = utc_now()
    payload = {
        "event_type": event_type,
        "stream": stream,
        "source": source,
        "event_day": normalized_day,
        "recorded_at": recorded_at,
        "amount_vnd": round(float(amount_vnd), 4),
        "symbol": symbol.upper() if symbol else None,
        "side": side,
        "quantity": int(quantity) if quantity is not None else None,
        "price_vnd": (
            round(float(price_vnd), 4) if price_vnd is not None else None
        ),
        "fees_vnd": round(float(fees_vnd), 4),
        "taxes_vnd": round(float(taxes_vnd), 4),
        "plan_id": plan_id,
        "note": note,
        "details": dict(details or {}),
    }
    digest = performance._event_hash(payload)
    event_id = "perf-" + digest[:20]
    with state_db() as db:
        performance._ensure_schema(db)
        db.execute(
            """
            INSERT INTO performance_events(
                event_id,event_time,event_day,event_type,stream,source,
                amount_vnd,symbol,side,quantity,price_vnd,fees_vnd,taxes_vnd,
                plan_id,note,event_hash,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                recorded_at,
                normalized_day,
                event_type,
                stream,
                source,
                payload["amount_vnd"],
                payload["symbol"],
                side,
                payload["quantity"],
                payload["price_vnd"],
                payload["fees_vnd"],
                payload["taxes_vnd"],
                plan_id,
                note,
                digest,
                json.dumps(
                    payload["details"], ensure_ascii=False, sort_keys=True
                ),
            ),
        )
    return {"status": "SUCCESS", "event_id": event_id, **payload}


def apply() -> None:
    performance._xirr = safe_xirr
    performance._append_event = append_unique_event
