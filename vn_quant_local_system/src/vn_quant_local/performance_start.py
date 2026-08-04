"""Khởi tạo V45 bằng một transaction đã kiểm tra schema.

Tách riêng entrypoint này để snapshot mở đầu chỉ được ghi một lần và toàn bộ
config/opening positions cùng commit hoặc cùng rollback.
"""
from __future__ import annotations

import json
from typing import Mapping

from .broker_portfolio import latest_broker_portfolio
from .core import load_config, state_db, utc_now
from .performance import (
    ADOPTED_AT_START,
    LEGACY_EXCLUDED,
    OBSERVATORY_VERSION,
    VALID_CLASSIFICATIONS,
    _ensure_schema,
    _iso_day,
    _latest_market_day,
    performance_status,
    refresh_performance,
)


def start_observatory(
    *,
    classifications: Mapping[str, str] | None = None,
    start_day: str | None = None,
    opening_model_cash_vnd: float | None = None,
) -> dict[str, object]:
    with state_db() as db:
        _ensure_schema(db)
        if db.execute(
            "SELECT 1 FROM performance_config WHERE singleton=1"
        ).fetchone() is not None:
            raise ValueError("PERFORMANCE_ALREADY_STARTED")

    broker = latest_broker_portfolio()
    if not broker:
        raise ValueError("PERFORMANCE_REQUIRES_BROKER_SNAPSHOT")

    day = _iso_day(
        start_day or broker.get("market_day") or _latest_market_day()
    )
    classification_map = {
        str(key).upper(): str(value).upper()
        for key, value in (classifications or {}).items()
    }
    positions: list[dict[str, object]] = []
    adopted_value = 0.0
    for raw in broker.get("positions", []):
        symbol = str(raw.get("symbol") or "").upper()
        classification = classification_map.get(symbol, LEGACY_EXCLUDED)
        if classification not in VALID_CLASSIFICATIONS:
            raise ValueError(
                f"PERFORMANCE_CLASSIFICATION_INVALID:{symbol}:{classification}"
            )
        quantity = int(raw.get("quantity") or 0)
        price = float(raw.get("valuation_price_vnd") or 0.0)
        value = quantity * price
        if classification == ADOPTED_AT_START:
            adopted_value += value
        positions.append(
            {
                "symbol": symbol,
                "classification": classification,
                "quantity": quantity,
                "opening_price_vnd": price,
                "opening_value_vnd": value,
                "details": {
                    "broker_average_cost_vnd": raw.get("average_cost_vnd"),
                    "broker_snapshot_id": broker["snapshot_id"],
                },
            }
        )

    broker_cash = float(broker.get("planner_cash_vnd") or 0.0)
    model_cash = (
        broker_cash
        if opening_model_cash_vnd is None
        else float(opening_model_cash_vnd)
    )
    if model_cash < 0:
        raise ValueError("PERFORMANCE_OPENING_CASH_NEGATIVE")

    performance_cfg = load_config().get("performance", {})
    if not isinstance(performance_cfg, Mapping):
        performance_cfg = {}
    cost_bps = float(performance_cfg.get("shadow_cost_bps", 50.0))
    tax_bps = float(performance_cfg.get("sell_tax_bps", 10.0))
    started_at = utc_now()
    details = {
        "opening_broker_nav_vnd": float(
            broker.get("net_asset_value_vnd") or 0.0
        ),
        "opening_broker_cash_vnd": broker_cash,
        "opening_adopted_value_vnd": adopted_value,
        "legacy_default": LEGACY_EXCLUDED,
        "actual_fill_price_source": "USER_CONFIRMED_ONLY",
        "shadow_execution": "FIRST_PLAN_PER_ISO_WEEK_AT_NEXT_SESSION_OPEN",
        "benchmark": "VNINDEX_SAME_SHADOW_CASH_FLOWS",
    }

    with state_db() as db:
        _ensure_schema(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                """
                INSERT INTO performance_config(
                    singleton,status,version,started_at,start_day,
                    opening_broker_snapshot_id,opening_model_cash_vnd,
                    shadow_cost_bps,sell_tax_bps,details_json
                ) VALUES(1,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "ACTIVE",
                    OBSERVATORY_VERSION,
                    started_at,
                    day,
                    str(broker["snapshot_id"]),
                    model_cash,
                    cost_bps,
                    tax_bps,
                    json.dumps(
                        details, ensure_ascii=False, sort_keys=True
                    ),
                ),
            )
            db.executemany(
                """
                INSERT INTO performance_opening_positions(
                    symbol,classification,quantity,opening_price_vnd,
                    opening_value_vnd,details_json
                ) VALUES(?,?,?,?,?,?)
                """,
                [
                    (
                        row["symbol"],
                        row["classification"],
                        row["quantity"],
                        row["opening_price_vnd"],
                        row["opening_value_vnd"],
                        json.dumps(
                            row["details"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                    for row in positions
                ],
            )
        except Exception:
            db.rollback()
            raise
        else:
            db.commit()

    refresh_performance()
    return performance_status()
