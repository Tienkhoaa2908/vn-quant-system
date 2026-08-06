"""V55: use local final EOD close as the sole operational valuation.

DNSE remains authoritative for cash, quantity and sellable quantity. Price-like
fields returned by the positions endpoint are ignored because their timestamp
and semantics are not verified. They are not exposed to the UI and are not used
for market value, P&L, NAV, planner weights or performance calculations.
"""
from __future__ import annotations

import json
import math
from typing import Mapping

from . import broker_portfolio, capital_plan, performance, weekly_plan
from . import source_integrity_v49 as v49
from .core import state_db

V55_VERSION = "V55_FINAL_EOD_ONLY_VALUATION"

_ORIGINAL_SYNC = None
_ORIGINAL_LATEST = None


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def official_position(row: Mapping[str, object]) -> dict[str, object]:
    symbol = str(row.get("symbol") or "").upper()
    quantity = max(int(_number(row.get("quantity"), 0.0)), 0)
    average_cost = max(_number(row.get("average_cost_vnd"), 0.0), 0.0)
    price = max(_number(row.get("local_market_price_vnd"), 0.0), 0.0)
    if quantity > 0 and price <= 0:
        raise ValueError(f"V55_FINAL_EOD_PRICE_MISSING:{symbol or 'UNKNOWN'}")
    market_value = quantity * price
    cost_value = quantity * average_cost
    pnl = market_value - cost_value
    pnl_pct = pnl / cost_value if cost_value > 0 else 0.0
    return {
        "price_vnd": round(price, 2),
        "market_value_vnd": round(market_value, 2),
        "pnl_vnd": round(pnl, 2),
        "pnl_pct": pnl_pct,
    }


def _rewrite_snapshot(snapshot_id: str) -> None:
    with state_db() as db:
        v49._ensure_broker_schema_v49(db)
        snapshot = db.execute(
            "SELECT * FROM broker_snapshots WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        if snapshot is None:
            raise ValueError(f"V55_SNAPSHOT_NOT_FOUND:{snapshot_id}")
        positions = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM broker_positions WHERE snapshot_id=? ORDER BY symbol",
                (snapshot_id,),
            ).fetchall()
        ]
        values = []
        for row in positions:
            official = official_position(row)
            values.append(official)
            db.execute(
                """
                UPDATE broker_positions
                SET valuation_price_vnd=?,market_value_vnd=?,
                    unrealized_pnl_vnd=?,unrealized_pnl_pct=?,
                    research_eod_market_value_vnd=?,
                    research_eod_unrealized_pnl_vnd=?,
                    research_eod_unrealized_pnl_pct=?
                WHERE snapshot_id=? AND symbol=?
                """,
                (
                    official["price_vnd"],
                    official["market_value_vnd"],
                    official["pnl_vnd"],
                    official["pnl_pct"],
                    official["market_value_vnd"],
                    official["pnl_vnd"],
                    official["pnl_pct"],
                    snapshot_id,
                    str(row.get("symbol") or ""),
                ),
            )
        stock_value = round(sum(float(row["market_value_vnd"]) for row in values), 2)
        nav = round(max(_number(snapshot["total_cash_vnd"]), 0.0) + stock_value, 2)
        details = json.loads(str(snapshot["details_json"] or "{}"))
        details.update(
            {
                "version": V55_VERSION,
                "valuation_source": "LOCAL_FINAL_EOD_CLOSE_ONLY",
                "broker_market_price_used": False,
                "broker_reference_price_exposed": False,
                "official_valuation_day": snapshot["market_day"],
            }
        )
        db.execute(
            """
            UPDATE broker_snapshots
            SET source=?,stock_value_vnd=?,net_asset_value_vnd=?,
                research_eod_stock_value_vnd=?,research_eod_nav_vnd=?,
                source_freshness=?,details_json=?
            WHERE snapshot_id=?
            """,
            (
                "DNSE_STATE_WITH_FINAL_EOD_V55",
                stock_value,
                nav,
                stock_value,
                nav,
                "DNSE_CASH_QUANTITY_PLUS_FINAL_EOD",
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                snapshot_id,
            ),
        )


def _public(result: Mapping[str, object] | None) -> dict[str, object] | None:
    if result is None:
        return None
    value = dict(result)
    details = dict(value.get("details") or {})
    details.update(
        {
            "version": V55_VERSION,
            "valuation_source": "LOCAL_FINAL_EOD_CLOSE_ONLY",
            "broker_market_price_used": False,
            "broker_reference_price_exposed": False,
        }
    )
    positions = []
    for raw in value.get("positions", []) or []:
        row = dict(raw)
        official = official_position(row)
        row["official_eod_price_vnd"] = official["price_vnd"]
        row["official_eod_market_value_vnd"] = official["market_value_vnd"]
        row["official_eod_unrealized_pnl_vnd"] = official["pnl_vnd"]
        row["official_eod_unrealized_pnl_pct"] = official["pnl_pct"]
        row["valuation_price_vnd"] = official["price_vnd"]
        row["market_value_vnd"] = official["market_value_vnd"]
        row["unrealized_pnl_vnd"] = official["pnl_vnd"]
        row["unrealized_pnl_pct"] = official["pnl_pct"]
        row.pop("broker_market_price_vnd", None)
        row.pop("broker_market_value_vnd", None)
        positions.append(row)
    stock_value = round(sum(float(row["market_value_vnd"]) for row in positions), 2)
    nav = round(max(_number(value.get("total_cash_vnd")), 0.0) + stock_value, 2)
    value["positions"] = positions
    value["stock_value_vnd"] = stock_value
    value["net_asset_value_vnd"] = nav
    value["research_eod_stock_value_vnd"] = stock_value
    value["research_eod_nav_vnd"] = nav
    value["official_eod_stock_value_vnd"] = stock_value
    value["official_eod_nav_vnd"] = nav
    value["official_valuation_day"] = value.get("market_day")
    value.pop("broker_stock_value_vnd", None)
    value.pop("broker_nav_vnd", None)
    value["details"] = details
    value["version"] = V55_VERSION
    return value


def latest_broker_portfolio_v55() -> dict[str, object] | None:
    assert _ORIGINAL_LATEST is not None
    return _public(_ORIGINAL_LATEST())


def sync_broker_portfolio_v55() -> dict[str, object]:
    assert _ORIGINAL_SYNC is not None
    result = dict(_ORIGINAL_SYNC())
    snapshot_id = str(result.get("snapshot_id") or "")
    if not snapshot_id:
        raise RuntimeError("V55_BROKER_SNAPSHOT_ID_MISSING")
    _rewrite_snapshot(snapshot_id)
    latest = latest_broker_portfolio_v55()
    if latest is None:
        raise RuntimeError("V55_BROKER_SNAPSHOT_READBACK_FAILED")
    return latest


def apply() -> None:
    if getattr(broker_portfolio, "_v55_eod_only_applied", False):
        return
    global _ORIGINAL_SYNC, _ORIGINAL_LATEST
    _ORIGINAL_SYNC = broker_portfolio.sync_broker_portfolio
    _ORIGINAL_LATEST = broker_portfolio.latest_broker_portfolio
    broker_portfolio.sync_broker_portfolio = sync_broker_portfolio_v55
    broker_portfolio.latest_broker_portfolio = latest_broker_portfolio_v55
    weekly_plan.latest_broker_portfolio = latest_broker_portfolio_v55
    capital_plan.latest_broker_portfolio = latest_broker_portfolio_v55
    performance.latest_broker_portfolio = latest_broker_portfolio_v55
    broker_portfolio.V55_VERSION = V55_VERSION
    performance.V55_VERSION = V55_VERSION
    broker_portfolio._v55_eod_only_applied = True
