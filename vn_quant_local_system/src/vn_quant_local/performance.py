"""V45 Live Performance Observatory.

Bốn lớp được tách riêng:

* toàn bộ tài khoản DNSE từ snapshot read-only;
* actual model sleeve từ opening classification, dòng tiền và fill đã xác nhận;
* plan shadow thực thi plan đầu tiên mỗi ISO week tại giá mở cửa T+1;
* VNINDEX benchmark nhận cùng dòng tiền với shadow.

Không suy diễn giá khớp thật từ average cost và không gửi lệnh broker.
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
    return date.fromisoformat(str(value)[:10]).isoformat()


def _market_connection() -> sqlite3.Connection:
    db = sqlite3.connect(paths().market_db)
    db.row_factory = sqlite3.Row
    return db


def _market_days() -> list[str]:
    with _market_connection() as db:
        rows = db.execute(
            """
            SELECT day FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
            ORDER BY day
            """
        ).fetchall()
    return [str(row[0]) for row in rows]


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


def _asset(symbol: str) -> tuple[str, float]:
    is_index = symbol.upper() in {"VNINDEX", "VN-INDEX", "VN_INDEX"}
    multiplier = 1.0 if is_index else float(
        load_config().get("model", {}).get("price_multiplier", 1000.0)
    )
    return ("INDEX" if is_index else "STOCK", multiplier)


def _price_exact(symbol: str, day: str, field: str = "close") -> float | None:
    if field not in {"open", "close"}:
        raise ValueError("field must be open or close")
    asset, multiplier = _asset(symbol)
    with _market_connection() as db:
        row = db.execute(
            f"""
            SELECT {field} FROM bars
            WHERE upper(asset_type)=? AND upper(symbol)=? AND day=?
            LIMIT 1
            """,
            (asset, symbol.upper(), day),
        ).fetchone()
    if row is None or row[0] is None:
        return None
    value = float(row[0]) * multiplier
    return value if math.isfinite(value) and value > 0 else None


def _price_on_or_before(
    symbol: str, day: str, field: str = "close"
) -> float | None:
    if field not in {"open", "close"}:
        raise ValueError("field must be open or close")
    asset, multiplier = _asset(symbol)
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
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
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
        "price_vnd": (
            round(float(price_vnd), 4) if price_vnd is not None else None
        ),
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
                json.dumps(
                    payload["details"], ensure_ascii=False, sort_keys=True
                ),
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
    day = _iso_day(
        start_day or broker.get("market_day") or _latest_market_day()
    )
    if day not in set(_market_days()):
        raise ValueError("PERFORMANCE_START_DAY_MUST_BE_MARKET_SESSION")
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


def _opening_positions() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        rows = db.execute(
            "SELECT * FROM performance_opening_positions ORDER BY symbol"
        ).fetchall()
    return [dict(row) for row in rows]


def _actual_events() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
        rows = db.execute(
            """
            SELECT * FROM performance_events
            ORDER BY event_day,event_time,event_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _actual_state_until(event_day: str) -> tuple[float, dict[str, int]]:
    config = _config()
    if config is None:
        return 0.0, {}
    cash = float(config["opening_model_cash_vnd"])
    positions = {
        str(row["symbol"]): int(row["quantity"])
        for row in _opening_positions()
        if row["classification"] == ADOPTED_AT_START
    }
    for row in _actual_events():
        if str(row["event_day"]) > event_day:
            break
        if row["event_type"] == "ACTUAL_CASHFLOW":
            cash += float(row["amount_vnd"])
        elif row["event_type"] == "ACTUAL_FILL":
            symbol = str(row["symbol"])
            quantity = int(row["quantity"] or 0)
            gross = float(row["amount_vnd"])
            fees = float(row["fees_vnd"])
            taxes = float(row["taxes_vnd"])
            if row["side"] == "BUY":
                positions[symbol] = positions.get(symbol, 0) + quantity
                cash -= gross + fees
            else:
                positions[symbol] = positions.get(symbol, 0) - quantity
                cash += gross - fees - taxes
    return cash, positions


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
    event = _append_event(
        event_type="ACTUAL_CASHFLOW",
        stream="ACTUAL_MODEL_SLEEVE",
        source="USER_CONFIRMED",
        event_day=event_day,
        amount_vnd=amount if kind == "DEPOSIT" else -amount,
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
    day = _iso_day(event_day)
    if (
        normalized_side not in VALID_SIDES
        or not ticker
        or qty <= 0
        or price <= 0
    ):
        raise ValueError("PERFORMANCE_FILL_INVALID")
    if fees < 0 or taxes < 0:
        raise ValueError("PERFORMANCE_FILL_COST_NEGATIVE")
    _, positions = _actual_state_until(day)
    if normalized_side == "SELL" and positions.get(ticker, 0) < qty:
        raise ValueError("PERFORMANCE_SELL_EXCEEDS_MODEL_SLEEVE_POSITION")
    gross = qty * price
    event = _append_event(
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
        plans = db.execute(
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
        for row in plans:
            week = _week_key(str(row["created_at"]))
            if week in existing:
                continue
            rationale = json.loads(str(row["rationale_json"]))
            position_reviews = list(rationale.get("position_reviews", []))
            exits = list(rationale.get("exit_candidates", [])) or [
                item
                for item in position_reviews
                if item.get("action") == "EXIT_CANDIDATE"
            ]
            execution_day = _next_session(str(row["created_at"])[:10])
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
                    (
                        "PENDING_MARKET_DATA"
                        if execution_day is None
                        else "SELECTED"
                    ),
                    float(row["contribution_vnd"]),
                    json.dumps(
                        {
                            "selection_rule": "FIRST_PLAN_PER_ISO_WEEK",
                            "buy_orders": rationale.get("buy_orders", []),
                            "exit_candidates": exits,
                            "position_reviews": position_reviews,
                            "maximum_buy_orders": rationale.get(
                                "maximum_buy_orders"
                            ),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )
            existing.add(week)


def _rebuild_shadow(config: Mapping[str, object]) -> None:
    latest_day = _latest_market_day()
    cost_rate = float(config["shadow_cost_bps"]) / 10_000.0
    tax_rate = float(config["sell_tax_bps"]) / 10_000.0
    adopted_value = sum(
        float(row["opening_value_vnd"])
        for row in _opening_positions()
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
                """
                SELECT * FROM performance_shadow_plans
                ORDER BY created_at,week_key
                """
            ).fetchall()
        ]
    for plan in plans:
        execution_day = plan.get("execution_day") or _next_session(
            str(plan["created_at"])[:10]
        )
        if not execution_day or str(execution_day) > latest_day:
            continue
        details = json.loads(str(plan["details_json"]))
        cash += float(plan["planned_contribution_vnd"])
        for raw in details.get("exit_candidates", []):
            symbol = str(raw.get("symbol") or "").upper()
            held = positions.get(symbol, 0)
            requested = int(
                raw.get("sellable_quantity")
                or raw.get("quantity")
                or held
            )
            quantity = min(held, requested)
            price = _price_exact(symbol, str(execution_day), "open")
            if quantity <= 0 or price is None:
                continue
            gross = quantity * price
            fees = gross * cost_rate
            taxes = gross * tax_rate
            cash += gross - fees - taxes
            positions[symbol] = held - quantity
            trades.append(
                {
                    "trade_id": f"shadow-{plan['plan_id']}-SELL-{symbol}",
                    "plan_id": str(plan["plan_id"]),
                    "execution_day": str(execution_day),
                    "side": "SELL",
                    "symbol": symbol,
                    "requested_quantity": requested,
                    "filled_quantity": quantity,
                    "price_vnd": price,
                    "gross_vnd": gross,
                    "fees_vnd": fees,
                    "taxes_vnd": taxes,
                    "details": {
                        "execution_rule": "T_PLUS_1_EXACT_OPEN_SELL_FIRST"
                    },
                }
            )
        for raw in details.get("buy_orders", []):
            symbol = str(raw.get("symbol") or "").upper()
            requested = int(raw.get("quantity") or 0)
            price = _price_exact(symbol, str(execution_day), "open")
            if requested <= 0 or price is None:
                continue
            unit_cost = price * (1.0 + cost_rate)
            quantity = min(requested, int(max(cash, 0.0) // unit_cost))
            if quantity <= 0:
                continue
            gross = quantity * price
            fees = gross * cost_rate
            cash -= gross + fees
            positions[symbol] = positions.get(symbol, 0) + quantity
            trades.append(
                {
                    "trade_id": f"shadow-{plan['plan_id']}-BUY-{symbol}",
                    "plan_id": str(plan["plan_id"]),
                    "execution_day": str(execution_day),
                    "side": "BUY",
                    "symbol": symbol,
                    "requested_quantity": requested,
                    "filled_quantity": quantity,
                    "price_vnd": price,
                    "gross_vnd": gross,
                    "fees_vnd": fees,
                    "taxes_vnd": 0.0,
                    "details": {
                        "execution_rule": "T_PLUS_1_EXACT_OPEN",
                        "limited_by_cash": quantity < requested,
                    },
                }
            )
    with state_db() as db:
        _ensure_schema(db)
        db.execute("DELETE FROM performance_shadow_trades")
        db.executemany(
            """
            INSERT INTO performance_shadow_trades(
                trade_id,plan_id,execution_day,side,symbol,
                requested_quantity,filled_quantity,price_vnd,gross_vnd,
                fees_vnd,taxes_vnd,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
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
                    json.dumps(
                        row["details"], ensure_ascii=False, sort_keys=True
                    ),
                )
                for row in trades
            ],
        )
        for plan in plans:
            execution_day = plan.get("execution_day") or _next_session(
                str(plan["created_at"])[:10]
            )
            status = (
                "EXECUTED"
                if execution_day and str(execution_day) <= latest_day
                else "PENDING_MARKET_DATA"
            )
            db.execute(
                """
                UPDATE performance_shadow_plans
                SET execution_day=?,status=? WHERE week_key=?
                """,
                (execution_day, status, plan["week_key"]),
            )


def _stream_events() -> dict[str, list[dict[str, object]]]:
    config = _config()
    if config is None:
        return {}
    events: dict[str, list[dict[str, object]]] = defaultdict(list)
    start_day = str(config["start_day"])
    opening_cash = float(config["opening_model_cash_vnd"])
    adopted = [
        row
        for row in _opening_positions()
        if row["classification"] == ADOPTED_AT_START
    ]
    adopted_value = sum(float(row["opening_value_vnd"]) for row in adopted)
    events["ACTUAL_MODEL_SLEEVE"].append(
        {
            "day": start_day,
            "kind": "OPENING",
            "cash_flow": opening_cash,
            "cash_delta": opening_cash,
            "positions": {
                str(row["symbol"]): int(row["quantity"])
                for row in adopted
            },
        }
    )
    for stream in ("PLAN_SHADOW", "VNINDEX_BENCHMARK"):
        events[stream].append(
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
                {
                    "day": day,
                    "kind": "CASHFLOW",
                    "cash_flow": amount,
                    "cash_delta": amount,
                }
            )
        elif row["event_type"] == "ACTUAL_FILL":
            gross = float(row["amount_vnd"])
            fees = float(row["fees_vnd"])
            taxes = float(row["taxes_vnd"])
            side = str(row["side"])
            events["ACTUAL_MODEL_SLEEVE"].append(
                {
                    "day": day,
                    "kind": "TRADE",
                    "side": side,
                    "symbol": str(row["symbol"]),
                    "quantity": int(row["quantity"] or 0),
                    "cash_delta": (
                        -(gross + fees)
                        if side == "BUY"
                        else gross - fees - taxes
                    ),
                    "cash_flow": 0.0,
                }
            )
    with state_db() as db:
        _ensure_schema(db)
        plans = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_shadow_plans
                ORDER BY execution_day,week_key
                """
            ).fetchall()
        ]
        trades = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_shadow_trades
                ORDER BY execution_day,trade_id
                """
            ).fetchall()
        ]
    for plan in plans:
        if plan["status"] != "EXECUTED" or not plan["execution_day"]:
            continue
        amount = float(plan["planned_contribution_vnd"])
        for stream in ("PLAN_SHADOW", "VNINDEX_BENCHMARK"):
            events[stream].append(
                {
                    "day": str(plan["execution_day"]),
                    "kind": "CASHFLOW",
                    "cash_flow": amount,
                    "cash_delta": amount,
                }
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
                "cash_delta": (
                    -(gross + fees)
                    if side == "BUY"
                    else gross - fees - taxes
                ),
                "cash_flow": 0.0,
            }
        )
    for values in events.values():
        values.sort(
            key=lambda row: (
                str(row["day"]),
                0 if row["kind"] in {"OPENING", "CASHFLOW"} else 1,
            )
        )
    return events


def _calculate_nav_rows(
    config: Mapping[str, object]
) -> list[dict[str, object]]:
    days = [
        day for day in _market_days() if day >= str(config["start_day"])
    ]
    if not days:
        return []
    stream_events = _stream_events()
    rows: list[dict[str, object]] = []
    for stream in (
        "ACTUAL_MODEL_SLEEVE",
        "PLAN_SHADOW",
        "VNINDEX_BENCHMARK",
    ):
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
                if stream == "VNINDEX_BENCHMARK" and flow != 0.0:
                    index_open = _price_exact("VNINDEX", day, "open")
                    if index_open is None:
                        cash += flow
                    elif flow > 0:
                        benchmark_units += flow / index_open
                    else:
                        units_to_sell = min(
                            benchmark_units, -flow / index_open
                        )
                        benchmark_units -= units_to_sell
                        uncovered = -flow - units_to_sell * index_open
                        cash -= max(uncovered, 0.0)
                else:
                    cash += float(event.get("cash_delta") or 0.0)
                if event.get("kind") == "OPENING" and event.get(
                    "positions"
                ):
                    positions.update(
                        {
                            str(key): int(value)
                            for key, value in dict(
                                event["positions"]
                            ).items()
                        }
                    )
                if event.get("kind") == "TRADE":
                    symbol = str(event["symbol"])
                    quantity = int(event["quantity"])
                    if event["side"] == "BUY":
                        positions[symbol] = (
                            positions.get(symbol, 0) + quantity
                        )
                    else:
                        positions[symbol] = (
                            positions.get(symbol, 0) - quantity
                        )
            if stream == "VNINDEX_BENCHMARK":
                invested = benchmark_units * float(
                    _price_exact("VNINDEX", day, "close") or 0.0
                )
            else:
                invested = sum(
                    quantity
                    * float(
                        _price_on_or_before(symbol, day, "close") or 0.0
                    )
                    for symbol, quantity in positions.items()
                    if quantity > 0
                )
            nav = cash + invested
            period_return: float | None = None
            if previous_nav is not None and previous_nav > 0:
                period_return = (nav - external_flow) / previous_nav - 1.0
                cumulative *= 1.0 + period_return
                peak = max(peak, cumulative)
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
                    "cumulative_return": cumulative - 1.0,
                    "drawdown": drawdown,
                    "details": {
                        "position_count": sum(
                            1 for quantity in positions.values() if quantity > 0
                        ),
                        "negative_cash": cash < -1e-6,
                        "negative_position": any(
                            quantity < 0 for quantity in positions.values()
                        ),
                    },
                }
            )
            previous_nav = nav
    return rows


def _whole_dnse_rows(
    config: Mapping[str, object]
) -> list[dict[str, object]]:
    start_day = str(config["start_day"])
    flows: dict[str, float] = defaultdict(float)
    for event in _actual_events():
        if event["event_type"] == "ACTUAL_CASHFLOW":
            flows[str(event["event_day"])] += float(event["amount_vnd"])
    with state_db() as db:
        snapshots = [
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
    latest_by_day: dict[str, dict[str, object]] = {}
    for snapshot in snapshots:
        day = str(
            snapshot.get("market_day")
            or str(snapshot["captured_at"])[:10]
        )
        latest_by_day[day] = snapshot
    result: list[dict[str, object]] = []
    previous_nav: float | None = None
    cumulative = 1.0
    peak = 1.0
    for day in sorted(latest_by_day):
        raw = latest_by_day[day]
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
            INSERT INTO performance_nav(
                stream,valuation_day,nav_vnd,cash_vnd,invested_vnd,
                external_flow_vnd,period_return,cumulative_return,drawdown,
                details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
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
                    json.dumps(
                        row.get("details", {}),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
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
    if (
        len(flows) < 2
        or not any(value < 0 for _, value in flows)
        or not any(value > 0 for _, value in flows)
    ):
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
        else:
            low = middle
            low_value = value
    return (low + high) / 2.0


def _summary_from_nav(
    rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    by_stream: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_stream[str(row["stream"])].append(row)
    result: dict[str, object] = {}
    for stream, values in by_stream.items():
        ordered = sorted(
            values, key=lambda row: str(row["valuation_day"])
        )
        latest = ordered[-1]
        initial_nav = float(ordered[0]["nav_vnd"])
        cashflows: list[tuple[date, float]] = [
            (
                date.fromisoformat(str(ordered[0]["valuation_day"])),
                -initial_nav,
            )
        ]
        for row in ordered[1:]:
            flow = float(row["external_flow_vnd"])
            if abs(flow) > 1e-9:
                cashflows.append(
                    (
                        date.fromisoformat(str(row["valuation_day"])),
                        -flow,
                    )
                )
        cashflows.append(
            (
                date.fromisoformat(str(latest["valuation_day"])),
                float(latest["nav_vnd"]),
            )
        )
        result[stream] = {
            "start_day": ordered[0]["valuation_day"],
            "latest_day": latest["valuation_day"],
            "latest_nav_vnd": latest["nav_vnd"],
            "latest_cash_vnd": latest["cash_vnd"],
            "latest_invested_vnd": latest["invested_vnd"],
            "cumulative_return": latest["cumulative_return"],
            "max_drawdown": min(
                float(row["drawdown"]) for row in ordered
            ),
            "xirr": _xirr(cashflows),
            "negative_cash_detected": any(
                bool(dict(row.get("details", {})).get("negative_cash"))
                for row in ordered
            ),
            "negative_position_detected": any(
                bool(dict(row.get("details", {})).get("negative_position"))
                for row in ordered
            ),
        }
    return result


def _rank_percentiles(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    denominator = max(len(values) - 1, 1)
    result = [0.0] * len(values)
    for position, index in enumerate(order):
        result[index] = position / denominator
    return result


def _pearson(
    left: Sequence[float], right: Sequence[float]
) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean, right_mean = fmean(left), fmean(right)
    numerator = sum(
        (a - left_mean) * (b - right_mean)
        for a, b in zip(left, right)
    )
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left)
        * sum((b - right_mean) ** 2 for b in right)
    )
    return numerator / denominator if denominator > 0 else None


def _signal_scorecard(
    config: Mapping[str, object]
) -> list[dict[str, object]]:
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
    day_index = {day: index for index, day in enumerate(market_days)}
    scorecard: list[dict[str, object]] = []
    for signal_day in signal_days:
        with state_db() as db:
            run = db.execute(
                """
                SELECT r.run_id FROM runs r
                JOIN rankings k ON k.run_id=r.run_id
                WHERE r.status='SUCCESS'
                  AND k.signal_kind='MONTHLY_CANONICAL'
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
                    """
                    SELECT rank,symbol,score FROM rankings
                    WHERE run_id=? AND signal_kind='MONTHLY_CANONICAL'
                    ORDER BY rank
                    """,
                    (run["run_id"],),
                ).fetchall()
            ]
        signal_index = day_index.get(signal_day)
        base_index = _price_exact("VNINDEX", signal_day, "close")
        if signal_index is None or base_index is None:
            continue
        horizons: dict[str, object] = {}
        for label, sessions in (("1W", 5), ("1M", 20), ("3M", 60)):
            target_index = signal_index + sessions
            if target_index >= len(market_days):
                horizons[label] = {"status": "PENDING"}
                continue
            target_day = market_days[target_index]
            index_end = _price_exact("VNINDEX", target_day, "close")
            if index_end is None:
                horizons[label] = {"status": "PENDING"}
                continue
            benchmark_return = index_end / base_index - 1.0
            returns: list[tuple[int, str, float]] = []
            for item in ranking:
                symbol = str(item["symbol"])
                start_price = _price_exact(symbol, signal_day, "close")
                end_price = _price_exact(symbol, target_day, "close")
                if start_price is not None and end_price is not None:
                    returns.append(
                        (
                            int(item["rank"]),
                            symbol,
                            end_price / start_price - 1.0,
                        )
                    )
            top10 = [value for rank, _, value in returns if rank <= 10]
            all_returns = [value for _, _, value in returns]
            rank_scores = [-float(rank) for rank, _, _ in returns]
            rank_ic = _pearson(
                _rank_percentiles(rank_scores),
                _rank_percentiles(all_returns),
            )
            horizons[label] = {
                "status": "COMPLETE",
                "target_day": target_day,
                "top10_mean_return": fmean(top10) if top10 else None,
                "benchmark_return": benchmark_return,
                "top10_excess_return": (
                    fmean(top10) - benchmark_return if top10 else None
                ),
                "top10_win_ratio": (
                    sum(value > benchmark_return for value in top10)
                    / len(top10)
                    if top10
                    else None
                ),
                "rank_ic": rank_ic,
                "sample_count": len(returns),
            }
        scorecard.append(
            {
                "signal_day": signal_day,
                "run_id": str(run["run_id"]),
                "horizons": horizons,
            }
        )
    return scorecard


def _reconciliation() -> list[dict[str, object]]:
    with state_db() as db:
        _ensure_schema(db)
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
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_events
                WHERE event_type='ACTUAL_FILL'
                ORDER BY event_day,event_time,event_id
                """
            ).fetchall()
        ]
    used: set[str] = set()
    result: list[dict[str, object]] = []
    for plan in plans:
        plan_id = str(plan["plan_id"])
        for proposed in [row for row in shadow if row["plan_id"] == plan_id]:
            candidates = [
                row
                for row in actual
                if row["event_id"] not in used
                and str(row["symbol"]) == str(proposed["symbol"])
                and str(row["side"]) == str(proposed["side"])
                and (
                    str(row.get("plan_id") or "") == plan_id
                    or (
                        not row.get("plan_id")
                        and str(row["event_day"])
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
                    date.fromisoformat(str(matched["event_day"]))
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
                    int(matched["quantity"] or 0)
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
                    "actual_event_id": (
                        matched["event_id"] if matched else None
                    ),
                    "actual_day": matched["event_day"] if matched else None,
                    "actual_quantity": matched["quantity"] if matched else 0,
                    "actual_price_vnd": (
                        matched["price_vnd"] if matched else None
                    ),
                    "execution_delay_days": delay,
                    "quantity_compliance": compliance,
                    "price_slippage": slippage,
                    "status": status,
                }
            )
    for row in actual:
        if row["event_id"] in used:
            continue
        result.append(
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
    return result


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
        nav_rows = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_nav
                ORDER BY stream,valuation_day
                """
            ).fetchall()
        ]
        opening = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_opening_positions
                ORDER BY symbol
                """
            ).fetchall()
        ]
        plans = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_shadow_plans
                ORDER BY created_at
                """
            ).fetchall()
        ]
        events = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM performance_events
                ORDER BY event_day,event_time,event_id
                """
            ).fetchall()
        ]
    for row in nav_rows:
        row["details"] = json.loads(str(row.pop("details_json")))
    for row in opening:
        row["details"] = json.loads(str(row.pop("details_json")))
    for row in plans:
        row["details"] = json.loads(str(row.pop("details_json")))
    for row in events:
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
