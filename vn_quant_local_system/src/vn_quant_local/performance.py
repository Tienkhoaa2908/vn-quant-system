"""V45 Live Performance Observatory.

Theo dõi bốn lớp tách biệt:

* toàn bộ tài khoản DNSE từ snapshot read-only;
* actual model sleeve từ opening classification, dòng tiền và fill đã xác nhận;
* plan shadow thực thi output kế hoạch đầu tiên mỗi tuần tại T+1 open;
* VNINDEX benchmark nhận cùng dòng tiền với shadow.

Không suy diễn giá khớp thật từ average cost của broker và không gửi lệnh.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from hashlib import sha256
import json
import math
import sqlite3
from statistics import fmean
from typing import Mapping, Sequence

from .broker_portfolio import latest_broker_portfolio
from .core import load_config, paths, state_db, utc_now

OBSERVATORY_VERSION = "V45_LIVE_PERFORMANCE_OBSERVATORY"
LEGACY_EXCLUDED = "LEGACY_EXCLUDED"
ADOPTED_AT_START = "ADOPTED_AT_START"
VALID_CLASSIFICATIONS = {LEGACY_EXCLUDED, ADOPTED_AT_START}
VALID_CASHFLOW_TYPES = {"DEPOSIT", "WITHDRAWAL"}
VALID_SIDES = {"BUY", "SELL"}


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS performance_config(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            status TEXT NOT NULL,
            version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            start_day TEXT NOT NULL,
            opening_broker_snapshot_id TEXT NOT NULL,
            opening_model_cash_vnd REAL NOT NULL,
            shadow_cost_bps REAL NOT NULL,
            sell_tax_bps REAL NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS performance_opening_positions(
            symbol TEXT PRIMARY KEY,
            classification TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            opening_price_vnd REAL NOT NULL,
            opening_value_vnd REAL NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS performance_events(
            event_id TEXT PRIMARY KEY,
            event_time TEXT NOT NULL,
            event_day TEXT NOT NULL,
            event_type TEXT NOT NULL,
            stream TEXT NOT NULL,
            source TEXT NOT NULL,
            amount_vnd REAL NOT NULL,
            symbol TEXT,
            side TEXT,
            quantity INTEGER,
            price_vnd REAL,
            fees_vnd REAL NOT NULL,
            taxes_vnd REAL NOT NULL,
            plan_id TEXT,
            note TEXT,
            event_hash TEXT NOT NULL UNIQUE,
            details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_performance_events_day
        ON performance_events(event_day,event_type);

        CREATE TABLE IF NOT EXISTS performance_shadow_plans(
            week_key TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            execution_day TEXT,
            status TEXT NOT NULL,
            planned_contribution_vnd REAL NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS performance_shadow_trades(
            trade_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            execution_day TEXT NOT NULL,
            side TEXT NOT NULL,
            symbol TEXT NOT NULL,
            requested_quantity INTEGER NOT NULL,
            filled_quantity INTEGER NOT NULL,
            price_vnd REAL NOT NULL,
            gross_vnd REAL NOT NULL,
            fees_vnd REAL NOT NULL,
            taxes_vnd REAL NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS performance_nav(
            stream TEXT NOT NULL,
            valuation_day TEXT NOT NULL,
            nav_vnd REAL NOT NULL,
            cash_vnd REAL NOT NULL,
            invested_vnd REAL NOT NULL,
            external_flow_vnd REAL NOT NULL,
            period_return REAL,
            cumulative_return REAL,
            drawdown REAL,
            details_json TEXT NOT NULL,
            PRIMARY KEY(stream,valuation_day)
        );
        """
    )


def _config() -> dict[str, object] | None:
    with state_db() as db:
        _ensure_schema(db)
        row = db.execute(
            "SELECT * FROM performance_config WHERE singleton=1"
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["details"] = json.loads(str(result.pop("details_json")))
    return result


def _iso_day(value: object | None) -> str:
    if value in (None, ""):
        return datetime.now().astimezone().date().isoformat()
    text = str(value)
    return date.fromisoformat(text[:10]).isoformat()


def _market_connection() -> sqlite3.Connection:
    db = sqlite3.connect(paths().market_db)
    db.row_factory = sqlite3.Row
    return db


def _market_days() -> list[str]:
    with _market_connection() as db:
        return [
            str(row[0])
            for row in db.execute(
                """
                SELECT day FROM bars
                WHERE upper(asset_type)='INDEX'
                  AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
                ORDER BY day
                """
            ).fetchall()
        ]


def _latest_market_day() -> str:
    days = _market_days()
    if not days:
        raise ValueError("PERFORMANCE_MARKET_CALENDAR_EMPTY")
    return days[-1]


def _next_session(after_day: str) -> str | None:
    with _market_connection() as db:
        row = db.execute(
            """
            SELECT MIN(day) FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
              AND day>?
            """,
            (after_day,),
        ).fetchone()
    return str(row[0]) if row and row[0] else None


def _price(symbol: str, day: str, field: str = "close") -> float | None:
    if field not in {"open", "close"}:
        raise ValueError("field must be open or close")
    asset = "INDEX" if symbol.upper() in {"VNINDEX", "VN-INDEX", "VN_INDEX"} else "STOCK"
    multiplier = 1.0 if asset == "INDEX" else float(
        load_config().get("model", {}).get("price_multiplier", 1000.0)
    )
    with _market_connection() as db:
        row = db.execute(
            f"""
            SELECT {field} FROM bars
            WHERE upper(asset_type)=? AND upper(symbol)=? AND day<=?
            ORDER BY day DESC LIMIT 1
            """,
            (asset, symbol.upper(), day),
        ).fetchone()
    if row is None or row[0] is None:
        return None
    value = float(row[0]) * multiplier
    return value if math.isfinite(value) and value > 0 else None


def _event_hash(payload: Mapping[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _append_event(
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
    normalized_day = _iso_day(event_day)
    payload = {
        "event_type": event_type,
        "stream": stream,
        "source": source,
        "event_day": normalized_day,
        "amount_vnd": round(float(amount_vnd), 4),
        "symbol": symbol.upper() if symbol else None,
        "side": side,
        "quantity": int(quantity) if quantity is not None else None,
        "price_vnd": round(float(price_vnd), 4) if price_vnd is not None else None,
        "fees_vnd": round(float(fees_vnd), 4),
        "taxes_vnd": round(float(taxes_vnd), 4),
        "plan_id": plan_id,
        "note": note,
        "details": dict(details or {}),
    }
    digest = _event_hash(payload)
    event_id = "perf-" + digest[:20]
    event_time = utc_now()
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            """
            INSERT OR IGNORE INTO performance_events(
                event_id,event_time,event_day,event_type,stream,source,
                amount_vnd,symbol,side,quantity,price_vnd,fees_vnd,taxes_vnd,
                plan_id,note,event_hash,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                event_time,
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
                json.dumps(payload["details"], ensure_ascii=False, sort_keys=True),
            ),
        )
    return {"status": "SUCCESS", "event_id": event_id, **payload}


def start_observatory(
    *,
    classifications: Mapping[str, str] | None = None,
    start_day: str | None = None,
    opening_model_cash_vnd: float | None = None,
) -> dict[str, object]:
    if _config() is not None:
        raise ValueError("PERFORMANCE_ALREADY_STARTED")
    broker = latest_broker_portfolio()
    if not broker:
        raise ValueError("PERFORMANCE_REQUIRES_BROKER_SNAPSHOT")
    day = _iso_day(start_day or broker.get("market_day") or _latest_market_day())
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
            raise ValueError(f"PERFORMANCE_CLASSIFICATION_INVALID:{symbol}:{classification}")
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
    model_cash = broker_cash if opening_model_cash_vnd is None else float(opening_model_cash_vnd)
    if model_cash < 0:
        raise ValueError("PERFORMANCE_OPENING_CASH_NEGATIVE")
    performance_cfg = load_config().get("performance", {})
    cost_bps = float(performance_cfg.get("shadow_cost_bps", 50.0)) if isinstance(performance_cfg, Mapping) else 50.0
    tax_bps = float(performance_cfg.get("sell_tax_bps", 10.0)) if isinstance(performance_cfg, Mapping) else 10.0
    started_at = utc_now()
    details = {
        "opening_broker_nav_vnd": float(broker.get("net_asset_value_vnd") or 0.0),
        "opening_broker_cash_vnd": broker_cash,
        "opening_adopted_value_vnd": adopted_value,
        "legacy_default": LEGACY_EXCLUDED,
        "actual_fill_price_source": "USER_CONFIRMED_ONLY",
        "shadow_execution": "FIRST_PLAN_PER_ISO_WEEK_AT_NEXT_SESSION_OPEN",
        "benchmark": "VNINDEX_SAME_SHADOW_CASH_FLOWS",
    }
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            "INSERT INTO performance_config VALUES(1,?,?,?,?,?,?,?,?)",
            (
                "ACTIVE",
                OBSERVATORY_VERSION,
                started_at,
                day,
                str(broker["snapshot_id"]),
                model_cash,
                cost_bps,
                tax_bps,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
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
                    json.dumps(row["details"], ensure_ascii=False, sort_keys=True),
                )
                for row in positions
            ],
        )
    refresh_performance()
    return performance_status()


def add_actual_cashflow(
    *,
    flow_type: str,
    amount_vnd: float,
    event_day: str,
    note: str | None = None,
) -> dict[str, object]:
    if _config() is None:
        raise ValueError("PERFORMANCE_NOT_STARTED")
    kind = str(flow_type).upper()
    amount = float(amount_vnd)
    if kind not in VALID_CASHFLOW_TYPES or amount <= 0:
        raise ValueError("PERFORMANCE_CASHFLOW_INVALID")
    signed = amount if kind == "DEPOSIT" else -amount
    event = _append_event(
        event_type="ACTUAL_CASHFLOW",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CONFIRMED",
        event_day=event_day,
        amount_vnd=signed,
        note=note,
        details={"flow_type": kind},
    )
    refresh_performance()
    return event


def add_actual_fill(
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
) -> dict[str, object]:
    if _config() is None:
        raise ValueError("PERFORMANCE_NOT_STARTED")
    normalized_side = str(side).upper()
    ticker = str(symbol).strip().upper()
    qty = int(quantity)
    price = float(price_vnd)
    fees = float(fees_vnd)
    taxes = float(taxes_vnd)
    if normalized_side not in VALID_SIDES or not ticker or qty <= 0 or price <= 0:
        raise ValueError("PERFORMANCE_FILL_INVALID")
    if fees < 0 or taxes < 0:
        raise ValueError("PERFORMANCE_FILL_COST_NEGATIVE")
    gross = qty * price
    event = _append_event(
        event_type="ACTUAL_FILL",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CONFIRMED_DNSE_FILL",
        event_day=event_day,
        amount_vnd=gross,
        symbol=ticker,
        side=normalized_side,
        quantity=qty,
        price_vnd=price,
        fees_vnd=fees,
        taxes_vnd=taxes,
        plan_id=plan_id,
        note=note,
        details={"gross_vnd": gross, "price_is_confirmed": True},
    )
    refresh_performance()
    return event


def _week_key(timestamp: str) -> str:
    day = date.fromisoformat(str(timestamp)[:10])
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _sync_shadow_plan_selection(config: Mapping[str, object]) -> None:
    start_day = str(config["start_day"])
    with state_db() as db:
        _ensure_schema(db)
        rows = db.execute(
            """
            SELECT * FROM weekly_plans
            WHERE substr(created_at,1,10)>=?
            ORDER BY created_at,plan_id
            """,
            (start_day,),
        ).fetchall()
        existing = {
            str(row["week_key"])
            for row in db.execute(
                "SELECT week_key FROM performance_shadow_plans"
            ).fetchall()
        }
        for row in rows:
            week = _week_key(str(row["created_at"]))
            if week in existing:
                continue
            rationale = json.loads(str(row["rationale_json"]))
            contribution = float(row["contribution_vnd"])
            execution_day = _next_session(str(row["created_at"])[:10])
            status = "PENDING_MARKET_DATA" if execution_day is None else "SELECTED"
            db.execute(
                """
                INSERT INTO performance_shadow_plans(
                    week_key,plan_id,created_at,execution_day,status,
                    planned_contribution_vnd,details_json
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    week,
                    str(row["plan_id"]),
                    str(row["created_at"]),
                    execution_day,
                    status,
                    contribution,
                    json.dumps(
                        {
                            "selection_rule": "FIRST_PLAN_PER_ISO_WEEK",
                            "buy_orders": rationale.get("buy_orders", []),
                            "exit_candidates": rationale.get("exit_candidates", []),
                            "position_reviews": rationale.get("position_reviews", []),
                            "maximum_buy_orders": rationale.get("maximum_buy_orders"),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )
            existing.add(week)


def _opening_positions() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_opening_positions ORDER BY symbol"
            ).fetchall()
        ]


def _actual_events() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_events ORDER BY event_day,event_time,event_id"
            ).fetchall()
        ]


def _rebuild_shadow(config: Mapping[str, object]) -> None:
    start_day = str(config["start_day"])
    latest_day = _latest_market_day()
    cost_rate = float(config["shadow_cost_bps"]) / 10_000.0
    tax_rate = float(config["sell_tax_bps"]) / 10_000.0
    opening = _opening_positions()
    adopted_value = sum(
        float(row["opening_value_vnd"])
        for row in opening
        if row["classification"] == ADOPTED_AT_START
    )
    cash = float(config["opening_model_cash_vnd"]) + adopted_value
    positions: dict[str, int] = {}
    trades: list[dict[str, object]] = []
    with state_db() as db:
        _ensure_schema(db)
        plans = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM performance_shadow_plans ORDER BY created_at,week_key"
            ).fetchall()
        ]
    for plan in plans:
        execution_day = plan.get("execution_day")
        if not execution_day:
            candidate = _next_session(str(plan["created_at"])[:10])
            if candidate:
                execution_day = candidate
        if not execution_day or str(execution_day) > latest_day:
            continue
        details = json.loads(str(plan["details_json"]))
        cash += float(plan["planned_contribution_vnd"])
        for raw in details.get("exit_candidates", []):
            symbol = str(raw.get("symbol") or "").upper()
            requested = int(raw.get("sellable_quantity") or raw.get("quantity") or 0)
            held = positions.get(symbol, 0)
            qty = min(held, requested if requested > 0 else held)
            if qty <= 0:
                continue
            price = _price(symbol, str(execution_day), "open")
            if not price:
                continue
            gross = qty * price
            fees = gross * cost_rate
            taxes = gross * tax_rate
            cash += gross - fees - taxes
            positions[symbol] = held - qty
            trades.append(
                {
                    "trade_id": f"shadow-{plan['plan_id']}-SELL-{symbol}",
                    "plan_id": str(plan["plan_id"]),
                    "execution_day": str(execution_day),
                    "side": "SELL",
                    "symbol": symbol,
                    "requested_quantity": requested,
                    "filled_quantity": qty,
                    "price_vnd": price,
                    "gross_vnd": gross,
                    "fees_vnd": fees,
                    "taxes_vnd": taxes,
                    "details": {"execution_rule": "T_PLUS_1_OPEN_SELL_FIRST"},
                }
            )
        for raw in details.get("buy_orders", []):
            symbol = str(raw.get("symbol") or "").upper()
            requested = int(raw.get("quantity") or 0)
            if requested <= 0:
                continue
            price = _price(symbol, str(execution_day), "open")
            if not price:
                continue
            unit_cost = price * (1.0 + cost_rate)
            affordable = int(cash // unit_cost)
            qty = min(requested, affordable)
            if qty <= 0:
                continue
            gross = qty * price
            fees = gross * cost_rate
            cash -= gross + fees
            positions[symbol] = positions.get(symbol, 0) + qty
            trades.append(
                {
                    "trade_id": f"shadow-{plan['plan_id']}-BUY-{symbol}",
                    "plan_id": str(plan["plan_id"]),
                    "execution_day": str(execution_day),
                    "side": "BUY",
                    "symbol": symbol,
                    "requested_quantity": requested,
                    "filled_quantity": qty,
                    "price_vnd": price,
                    "gross_vnd": gross,
                    "fees_vnd": fees,
                    "taxes_vnd": 0.0,
                    "details": {
                        "execution_rule": "T_PLUS_1_OPEN",
                        "limited_by_cash": qty < requested,
                    },
                }
            )
    with state_db() as db:
        _ensure_schema(db)
        db.execute("DELETE FROM performance_shadow_trades")
        db.executemany(
            """
            INSERT INTO performance_shadow_trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    row["trade_id"],
                    row["plan_id"],
                    row["execution_day"],
                    row["side"],
                    row["symbol"],
                    row["requested_quantity"],
                    row["filled_quantity"],
                    row["price_vnd"],
                    row["gross_vnd"],
                    row["fees_vnd"],
                    row["taxes_vnd"],
                    json.dumps(row["details"], ensure_ascii=False, sort_keys=True),
                )
                for row in trades
            ],
        )
        for plan in plans:
            execution_day = plan.get("execution_day") or _next_session(str(plan["created_at"])[:10])
            status = (
                "EXECUTED"
                if execution_day and str(execution_day) <= latest_day
                else "PENDING_MARKET_DATA"
            )
            db.execute(
                "UPDATE performance_shadow_plans SET execution_day=?,status=? WHERE week_key=?",
                (execution_day, status, plan["week_key"]),
            )


def _stream_events() -> dict[str, list[dict[str, object]]]:
    config = _config()
    if not config:
        return {}
    events: dict[str, list[dict[str, object]]] = defaultdict(list)
    start_day = str(config["start_day"])
    opening_cash = float(config["opening_model_cash_vnd"])
    adopted = [
        row for row in _opening_positions() if row["classification"] == ADOPTED_AT_START
    ]
    events["ACTUAL_MODEL_SLEEVE"].append(
        {
            "day": start_day,
            "kind": "OPENING",
            "cash_flow": opening_cash,
            "cash_delta": opening_cash,
            "positions": {
                str(row["symbol"]): int(row["quantity"]) for row in adopted
            },
        }
    )
    adopted_value = sum(float(row["opening_value_vnd"]) for row in adopted)
    events["PLAN_SHADOW"].append(
        {
            "day": start_day,
            "kind": "OPENING",
            "cash_flow": opening_cash + adopted_value,
            "cash_delta": opening_cash + adopted_value,
            "positions": {},
        }
    )
    events["VNINDEX_BENCHMARK"].append(
        {
            "day": start_day,
            "kind": "OPENING",
            "cash_flow": opening_cash + adopted_value,
            "cash_delta": opening_cash + adopted_value,
        }
    )
    for row in _actual_events():
        day = str(row["event_day"])
        if row["event_type"] == "ACTUAL_CASHFLOW":
            amount = float(row["amount_vnd"])
            events["ACTUAL_MODEL_SLEEVE"].append(
                {"day": day, "kind": "CASHFLOW", "cash_flow": amount, "cash_delta": amount}
            )
        elif row["event_type"] == "ACTUAL_FILL":
            side = str(row["side"])
            gross = float(row["amount_vnd"])
            fees = float(row["fees_vnd"])
            taxes = float(row["taxes_vnd"])
            qty = int(row["quantity"] or 0)
            events["ACTUAL_MODEL_SLEEVE"].append(
                {
                    "day": day,
                    "kind": "TRADE",
                    "side": side,
                    "symbol": str(row["symbol"]),
                    "quantity": qty,
                    "cash_delta": -(gross + fees) if side == "BUY" else gross - fees - taxes,
                    "cash_flow": 0.0,
                }
            )
    with state_db() as db:
        _ensure_schema(db)
        plans = [dict(row) for row in db.execute("SELECT * FROM performance_shadow_plans ORDER BY execution_day,week_key").fetchall()]
        trades = [dict(row) for row in db.execute("SELECT * FROM performance_shadow_trades ORDER BY execution_day,trade_id").fetchall()]
    for plan in plans:
        if plan["status"] != "EXECUTED" or not plan["execution_day"]:
            continue
        amount = float(plan["planned_contribution_vnd"])
        for stream in ("PLAN_SHADOW", "VNINDEX_BENCHMARK"):
            events[stream].append(
                {"day": str(plan["execution_day"]), "kind": "CASHFLOW", "cash_flow": amount, "cash_delta": amount}
            )
    for row in trades:
        side = str(row["side"])
        gross = float(row["gross_vnd"])
        fees = float(row["fees_vnd"])
        taxes = float(row["taxes_vnd"])
        events["PLAN_SHADOW"].append(
            {
                "day": str(row["execution_day"]),
                "kind": "TRADE",
                "side": side,
                "symbol": str(row["symbol"]),
                "quantity": int(row["filled_quantity"]),
                "cash_delta": -(gross + fees) if side == "BUY" else gross - fees - taxes,
                "cash_flow": 0.0,
            }
        )
    for values in events.values():
        values.sort(key=lambda row: (str(row["day"]), 0 if row["kind"] in {"OPENING", "CASHFLOW"} else 1))
    return events


def _calculate_nav_rows(config: Mapping[str, object]) -> list[dict[str, object]]:
    days = [day for day in _market_days() if day >= str(config["start_day"])]
    if not days:
        return []
    stream_events = _stream_events()
    rows: list[dict[str, object]] = []
    for stream in ("ACTUAL_MODEL_SLEEVE", "PLAN_SHADOW", "VNINDEX_BENCHMARK"):
        events_by_day: dict[str, list[dict[str, object]]] = defaultdict(list)
        for event in stream_events.get(stream, []):
            events_by_day[str(event["day"])].append(event)
        cash = 0.0
        positions: dict[str, int] = {}
        benchmark_units = 0.0
        previous_nav: float | None = None
        cumulative = 1.0
        peak = 1.0
        for day in days:
            external_flow = 0.0
            for event in events_by_day.get(day, []):
                flow = float(event.get("cash_flow") or 0.0)
                external_flow += flow
                cash += float(event.get("cash_delta") or 0.0)
                if event.get("kind") == "OPENING" and event.get("positions"):
                    positions.update({str(k): int(v) for k, v in dict(event["positions"]).items()})
                if event.get("kind") == "TRADE":
                    symbol = str(event["symbol"])
                    qty = int(event["quantity"])
                    if event["side"] == "BUY":
                        positions[symbol] = positions.get(symbol, 0) + qty
                    else:
                        positions[symbol] = max(positions.get(symbol, 0) - qty, 0)
                if stream == "VNINDEX_BENCHMARK" and flow > 0:
                    index_open = _price("VNINDEX", day, "open")
                    if index_open:
                        invest = min(cash, flow)
                        benchmark_units += invest / index_open
                        cash -= invest
                elif stream == "VNINDEX_BENCHMARK" and flow < 0:
                    index_open = _price("VNINDEX", day, "open")
                    needed = min(-flow, benchmark_units * (index_open or 0.0))
                    if index_open and needed > 0:
                        benchmark_units -= needed / index_open
            if stream == "VNINDEX_BENCHMARK":
                price = _price("VNINDEX", day, "close") or 0.0
                invested = benchmark_units * price
            else:
                invested = sum(
                    quantity * float(_price(symbol, day, "close") or 0.0)
                    for symbol, quantity in positions.items()
                    if quantity > 0
                )
            nav = cash + invested
            period_return: float | None = None
            if previous_nav is not None and previous_nav > 0:
                period_return = (nav - external_flow) / previous_nav - 1.0
                cumulative *= 1.0 + period_return
                peak = max(peak, cumulative)
            cumulative_return = cumulative - 1.0
            drawdown = cumulative / peak - 1.0 if peak > 0 else 0.0
            rows.append(
                {
                    "stream": stream,
                    "valuation_day": day,
                    "nav_vnd": nav,
                    "cash_vnd": cash,
                    "invested_vnd": invested,
                    "external_flow_vnd": external_flow,
                    "period_return": period_return,
                    "cumulative_return": cumulative_return,
                    "drawdown": drawdown,
                    "details": {
                        "position_count": sum(1 for quantity in positions.values() if quantity > 0),
                        "negative_cash": cash < -1e-6,
                    },
                }
            )
            previous_nav = nav
    return rows


def _whole_dnse_rows(config: Mapping[str, object]) -> list[dict[str, object]]:
    start_day = str(config["start_day"])
    flows = defaultdict(float)
    for event in _actual_events():
        if event["event_type"] == "ACTUAL_CASHFLOW":
            flows[str(event["event_day"])] += float(event["amount_vnd"])
    with state_db() as db:
        rows = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM broker_snapshots
                WHERE COALESCE(market_day,substr(captured_at,1,10))>=?
                ORDER BY captured_at
                """,
                (start_day,),
            ).fetchall()
        ]
    result: list[dict[str, object]] = []
    previous_nav: float | None = None
    cumulative = 1.0
    peak = 1.0
    seen_day: set[str] = set()
    for raw in rows:
        day = str(raw.get("market_day") or raw["captured_at"][:10])
        if day in seen_day:
            if result:
                result.pop()
        seen_day.add(day)
        nav = float(raw["net_asset_value_vnd"])
        flow = flows.get(day, 0.0)
        period_return = None
        if previous_nav is not None and previous_nav > 0:
            period_return = (nav - flow) / previous_nav - 1.0
            cumulative *= 1.0 + period_return
            peak = max(peak, cumulative)
        result.append(
            {
                "stream": "WHOLE_DNSE",
                "valuation_day": day,
                "nav_vnd": nav,
                "cash_vnd": float(raw["planner_cash_vnd"]),
                "invested_vnd": float(raw["stock_value_vnd"]),
                "external_flow_vnd": flow,
                "period_return": period_return,
                "cumulative_return": cumulative - 1.0,
                "drawdown": cumulative / peak - 1.0,
                "details": {"snapshot_id": raw["snapshot_id"]},
            }
        )
        previous_nav = nav
    return result


def _store_nav_rows(rows: Sequence[Mapping[str, object]]) -> None:
    with state_db() as db:
        _ensure_schema(db)
        db.execute("DELETE FROM performance_nav")
        db.executemany(
            """
            INSERT INTO performance_nav VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    row["stream"],
                    row["valuation_day"],
                    row["nav_vnd"],
                    row["cash_vnd"],
                    row["invested_vnd"],
                    row["external_flow_vnd"],
                    row["period_return"],
                    row["cumulative_return"],
                    row["drawdown"],
                    json.dumps(row.get("details", {}), ensure_ascii=False, sort_keys=True),
                )
                for row in rows
            ],
        )


def _xnpv(rate: float, flows: Sequence[tuple[date, float]]) -> float:
    origin = flows[0][0]
    return sum(
        amount / ((1.0 + rate) ** ((day - origin).days / 365.0))
        for day, amount in flows
    )


def _xirr(flows: Sequence[tuple[date, float]]) -> float | None:
    if len(flows) < 2 or not any(value < 0 for _, value in flows) or not any(value > 0 for _, value in flows):
        return None
    low, high = -0.9999, 10.0
    low_value, high_value = _xnpv(low, flows), _xnpv(high, flows)
    attempts = 0
    while low_value * high_value > 0 and attempts < 8:
        high *= 10.0
        high_value = _xnpv(high, flows)
        attempts += 1
    if low_value * high_value > 0:
        return None
    for _ in range(200):
        middle = (low + high) / 2.0
        value = _xnpv(middle, flows)
        if abs(value) < 1e-7:
            return middle
        if low_value * value <= 0:
            high = middle
            high_value = value
        else:
            low = middle
            low_value = value
    return (low + high) / 2.0


def _summary_from_nav(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_stream: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_stream[str(row["stream"])].append(row)
    result: dict[str, object] = {}
    for stream, values in by_stream.items():
        values = sorted(values, key=lambda row: str(row["valuation_day"]))
        latest = values[-1]
        initial_nav = float(values[0]["nav_vnd"])
        flow_rows = [
            (date.fromisoformat(str(values[0]["valuation_day"])), -initial_nav)
        ]
        for row in values[1:]:
            flow = float(row["external_flow_vnd"])
            if abs(flow) > 1e-9:
                flow_rows.append((date.fromisoformat(str(row["valuation_day"])), -flow))
        flow_rows.append((date.fromisoformat(str(latest["valuation_day"])), float(latest["nav_vnd"])))
        result[stream] = {
            "start_day": values[0]["valuation_day"],
            "latest_day": latest["valuation_day"],
            "latest_nav_vnd": latest["nav_vnd"],
            "latest_cash_vnd": latest["cash_vnd"],
            "latest_invested_vnd": latest["invested_vnd"],
            "cumulative_return": latest["cumulative_return"],
            "max_drawdown": min(float(row["drawdown"]) for row in values),
            "xirr": _xirr(flow_rows),
            "negative_cash_detected": any(bool(json.loads(str(row["details_json"])).get("negative_cash")) if "details_json" in row.keys() else False for row in values),
        }
    return result


def _rank_percentiles(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    result = [0.0] * len(values)
    denominator = max(len(values) - 1, 1)
    for position, index in enumerate(order):
        result[index] = position / denominator
    return result


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    lm, rm = fmean(left), fmean(right)
    numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return numerator / denominator if denominator > 0 else None


def _signal_scorecard(config: Mapping[str, object]) -> list[dict[str, object]]:
    start_day = str(config["start_day"])
    with state_db() as db:
        signal_days = [
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT signal_day FROM rankings
                WHERE signal_kind='MONTHLY_CANONICAL' AND signal_day>=?
                ORDER BY signal_day
                """,
                (start_day,),
            ).fetchall()
        ]
    market_days = _market_days()
    position = {day: index for index, day in enumerate(market_days)}
    scorecard: list[dict[str, object]] = []
    for signal_day in signal_days:
        with state_db() as db:
            run = db.execute(
                """
                SELECT r.run_id FROM runs r JOIN rankings k ON k.run_id=r.run_id
                WHERE r.status='SUCCESS' AND k.signal_kind='MONTHLY_CANONICAL'
                  AND k.signal_day=?
                ORDER BY r.finished_at DESC LIMIT 1
                """,
                (signal_day,),
            ).fetchone()
            if run is None:
                continue
            ranking = [
                dict(row)
                for row in db.execute(
                    "SELECT rank,symbol,score FROM rankings WHERE run_id=? AND signal_kind='MONTHLY_CANONICAL' ORDER BY rank",
                    (run["run_id"],),
                ).fetchall()
            ]
        signal_index = position.get(signal_day)
        if signal_index is None:
            continue
        base_index = _price("VNINDEX", signal_day, "close")
        horizons: dict[str, object] = {}
        for label, sessions in (("1W", 5), ("1M", 20), ("3M", 60)):
            target_index = signal_index + sessions
            if target_index >= len(market_days):
                horizons[label] = {"status": "PENDING"}
                continue
            target_day = market_days[target_index]
            index_end = _price("VNINDEX", target_day, "close")
            benchmark_return = (
                index_end / base_index - 1.0 if base_index and index_end else None
            )
            returns: list[tuple[int, str, float]] = []
            for item in ranking:
                start_price = _price(str(item["symbol"]), signal_day, "close")
                end_price = _price(str(item["symbol"]), target_day, "close")
                if start_price and end_price:
                    returns.append((int(item["rank"]), str(item["symbol"]), end_price / start_price - 1.0))
            top10 = [value for rank, _, value in returns if rank <= 10]
            all_returns = [value for _, _, value in returns]
            ranks = [-float(rank) for rank, _, _ in returns]
            ic = _pearson(_rank_percentiles(ranks), _rank_percentiles(all_returns))
            horizons[label] = {
                "status": "COMPLETE",
                "target_day": target_day,
                "top10_mean_return": fmean(top10) if top10 else None,
                "benchmark_return": benchmark_return,
                "top10_excess_return": fmean(top10) - benchmark_return if top10 and benchmark_return is not None else None,
                "top10_win_ratio": sum(value > benchmark_return for value in top10) / len(top10) if top10 and benchmark_return is not None else None,
                "rank_ic": ic,
                "sample_count": len(returns),
            }
        scorecard.append({"signal_day": signal_day, "run_id": str(run["run_id"]), "horizons": horizons})
    return scorecard


def _reconciliation() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        plans = [dict(row) for row in db.execute("SELECT * FROM performance_shadow_plans ORDER BY created_at").fetchall()]
        shadow = [dict(row) for row in db.execute("SELECT * FROM performance_shadow_trades ORDER BY execution_day").fetchall()]
        actual = [dict(row) for row in db.execute("SELECT * FROM performance_events WHERE event_type='ACTUAL_FILL' ORDER BY event_day,event_time").fetchall()]
    actual_used: set[str] = set()
    rows: list[dict[str, object]] = []
    for plan in plans:
        plan_id = str(plan["plan_id"])
        plan_trades = [row for row in shadow if row["plan_id"] == plan_id]
        for proposed in plan_trades:
            candidates = [
                row
                for row in actual
                if row["event_id"] not in actual_used
                and str(row["symbol"]) == str(proposed["symbol"])
                and str(row["side"]) == str(proposed["side"])
                and (
                    str(row.get("plan_id") or "") == plan_id
                    or (
                        not row.get("plan_id")
                        and str(row["event_day"]) >= str(plan["created_at"])[:10]
                    )
                )
            ]
            matched = candidates[0] if candidates else None
            if matched:
                actual_used.add(str(matched["event_id"]))
            delay = None
            slippage = None
            compliance = 0.0
            status = "MISSED"
            if matched:
                delay = (
                    date.fromisoformat(str(matched["event_day"]))
                    - date.fromisoformat(str(plan["created_at"])[:10])
                ).days
                shadow_price = float(proposed["price_vnd"])
                actual_price = float(matched["price_vnd"])
                side_sign = 1.0 if proposed["side"] == "BUY" else -1.0
                slippage = side_sign * (actual_price / shadow_price - 1.0) if shadow_price > 0 else None
                compliance = min(
                    int(matched["quantity"] or 0) / max(int(proposed["filled_quantity"]), 1),
                    1.0,
                )
                status = "EXECUTED" if compliance >= 0.999 else "PARTIALLY_EXECUTED"
            rows.append(
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
        if row["event_id"] not in actual_used:
            rows.append(
                {
                    "plan_id": row.get("plan_id"),
                    "week_key": None,
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "proposed_quantity": 0,
                    "shadow_execution_day": None,
                    "shadow_price_vnd": None,
                    "actual_event_id": row["event_id"],
                    "actual_day": row["event_day"],
                    "actual_quantity": row["quantity"],
                    "actual_price_vnd": row["price_vnd"],
                    "execution_delay_days": None,
                    "quantity_compliance": None,
                    "price_slippage": None,
                    "status": "EXTRA_OR_UNMATCHED",
                }
            )
    return rows


def refresh_performance() -> dict[str, object]:
    config = _config()
    if config is None:
        return {"status": "NOT_STARTED", "version": OBSERVATORY_VERSION}
    _sync_shadow_plan_selection(config)
    _rebuild_shadow(config)
    nav_rows = _calculate_nav_rows(config) + _whole_dnse_rows(config)
    _store_nav_rows(nav_rows)
    return performance_status()


def performance_status() -> dict[str, object]:
    config = _config()
    if config is None:
        broker = latest_broker_portfolio()
        return {
            "status": "NOT_STARTED",
            "version": OBSERVATORY_VERSION,
            "broker_ready": bool(broker),
            "broker": broker,
            "default_classification": LEGACY_EXCLUDED,
            "classifications": sorted(VALID_CLASSIFICATIONS),
        }
    with state_db() as db:
        _ensure_schema(db)
        nav_rows = [dict(row) for row in db.execute("SELECT * FROM performance_nav ORDER BY stream,valuation_day").fetchall()]
        opening = [dict(row) for row in db.execute("SELECT * FROM performance_opening_positions ORDER BY symbol").fetchall()]
        plans = [dict(row) for row in db.execute("SELECT * FROM performance_shadow_plans ORDER BY created_at").fetchall()]
        events = [dict(row) for row in db.execute("SELECT * FROM performance_events ORDER BY event_day,event_time").fetchall()]
    for row in nav_rows:
        row["details"] = json.loads(str(row.pop("details_json")))
    for row in opening:
        row["details"] = json.loads(str(row.pop("details_json")))
    for row in plans:
        row["details"] = json.loads(str(row.pop("details_json")))
    series: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in nav_rows:
        series[str(row["stream"])].append(row)
    return {
        "status": "ACTIVE",
        "version": OBSERVATORY_VERSION,
        "config": config,
        "opening_positions": opening,
        "summary": _summary_from_nav(nav_rows),
        "series": dict(series),
        "shadow_plans": plans,
        "events": events,
        "reconciliation": _reconciliation(),
        "signal_scorecard": _signal_scorecard(config),
        "latest_broker": latest_broker_portfolio(),
        "limitations": {
            "actual_fill_requires_confirmation": True,
            "broker_average_cost_is_not_used_as_fill_price": True,
            "whole_dnse_twr_requires_confirmed_external_cashflows": True,
            "automatic_live_orders_allowed": False,
        },
        "research_only": True,
        "live_capital_approved": False,
    }
