"""V59 fast-path + read-only DNSE realtime state.

Goals:
- keep dashboard/status off whole-file SHA256 hot paths;
- reconcile only the persisted selected DNSE sub-account instead of probing every
  account on every sync;
- keep V55 final-EOD valuation semantics;
- subscribe to DNSE private trading streams for position/order/account events;
- expose a local materialized realtime view for diagnostics/UI without granting
  order mutation capability or silently promoting unverified stream state into
  the planner.

REST remains the auditable reconciliation/checkpoint source. WebSocket events
are append-only diagnostics plus a display overlay until account scope and field
semantics are observed on the real workstation.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
import sqlite3
import threading
import time
from typing import Mapping, Sequence

from . import broker_portfolio, capital_plan, core, data_sources, performance, weekly_plan
from . import source_integrity_v49 as v49
from . import v55_eod_only as v55
from .core import account_snapshot, paths, replace_account, state_db, utc_now

V59_VERSION = "V59_FAST_REALTIME_DNSE"
REALTIME_MODE = "DNSE_TRADING_STREAM_READ_ONLY_DIAGNOSTIC"

_STREAM_LOCK = threading.RLock()
_STREAM_THREAD: threading.Thread | None = None
_STREAM_OBJECT = None
_STREAM_STARTED_AT: str | None = None
_STREAM_LAST_ERROR: str | None = None
_STREAM_STATUS = "STOPPED"


def _finite(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _ensure_realtime_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS broker_realtime_events_v59(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            account_token TEXT,
            symbol TEXT,
            source_modified_at TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_broker_realtime_events_v59_received
        ON broker_realtime_events_v59(received_at DESC);
        CREATE INDEX IF NOT EXISTS idx_broker_realtime_events_v59_symbol
        ON broker_realtime_events_v59(symbol,received_at DESC);

        CREATE TABLE IF NOT EXISTS broker_realtime_positions_v59(
            symbol TEXT PRIMARY KEY,
            account_token TEXT,
            quantity INTEGER NOT NULL,
            sellable_quantity INTEGER,
            average_cost_raw REAL,
            source_modified_at TEXT,
            received_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS broker_realtime_account_v59(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            account_token TEXT,
            available_cash_raw REAL,
            total_cash_raw REAL,
            withdrawable_cash_raw REAL,
            source_modified_at TEXT,
            received_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS broker_rest_reconcile_v59(
            snapshot_id TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL,
            selected_account_token TEXT NOT NULL,
            accounts_elapsed_ms REAL NOT NULL,
            balances_elapsed_ms REAL NOT NULL,
            positions_elapsed_ms REAL NOT NULL,
            raw_position_count INTEGER NOT NULL,
            open_position_count INTEGER NOT NULL,
            latest_position_modified_at TEXT,
            details_json TEXT NOT NULL
        );
        """
    )


def _configure_market_db() -> None:
    market_db = paths().market_db
    if not market_db.is_file():
        return
    with sqlite3.connect(market_db) as db:
        db.execute("PRAGMA busy_timeout=30000")
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            pass
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_bars_asset_day_symbol_v59 "
            "ON bars(asset_type,day,symbol)"
        )
        try:
            db.execute("PRAGMA optimize")
        except sqlite3.DatabaseError:
            pass


def fast_market_coverage_v59() -> dict[str, object]:
    """Coverage for UI hot path without hashing the complete market database."""
    p = paths()
    if not p.market_db.is_file():
        return {"status": "MISSING", "path": str(p.market_db)}
    with sqlite3.connect(p.market_db) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT upper(asset_type) asset_type,
                   COUNT(*) row_count,
                   COUNT(DISTINCT symbol) symbol_count,
                   MIN(day) first_day,
                   MAX(day) last_day
            FROM bars
            GROUP BY upper(asset_type)
            ORDER BY upper(asset_type)
            """
        ).fetchall()
        try:
            conflicts = int(db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0])
        except sqlite3.DatabaseError:
            conflicts = 0
    return {
        "status": "READY" if rows else "EMPTY",
        "path": str(p.market_db),
        "sha256": None,
        "sha256_mode": "DEFERRED_MAINTENANCE_ONLY",
        "coverage": [dict(row) for row in rows],
        "conflict_count": conflicts,
        "version": V59_VERSION,
    }


def workstation_status_v59() -> dict[str, object]:
    p = core.ensure_directories()
    ranking = core.latest_ranking_run()
    return {
        "system_root": str(core.SYSTEM_ROOT),
        "repo_root": str(core.REPO_ROOT),
        "market": fast_market_coverage_v59(),
        "reference_zip": {
            "status": "READY" if p.reference_zip.is_file() else "MISSING",
            "path": str(p.reference_zip),
            "sha256": None,
            "sha256_mode": "DEFERRED_MAINTENANCE_ONLY",
        },
        "latest_monthly_ranking": ranking,
        "account": core.account_snapshot(),
        "runtime": {
            "version": V59_VERSION,
            "status_hot_path_hashing": False,
            "market_db_index": "idx_bars_asset_day_symbol_v59",
        },
        "permissions": {
            "research_only": True,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        },
    }


def _account_identity(reader) -> tuple[dict[str, object], float]:
    started = time.perf_counter()
    accounts = list(reader.accounts())
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    selected_token = v49._read_account_selection()
    identities: list[dict[str, object]] = []
    for raw in accounts:
        account_no = v49._account_id(raw)
        if not account_no:
            continue
        token = v49._account_token(account_no)
        identities.append(
            {
                "account_no": account_no,
                "selection_token": token,
                "masked_account": v49._mask_account(account_no),
                "account_fields": sorted(str(key) for key in raw.keys()),
            }
        )
    if selected_token:
        selected = next(
            (row for row in identities if row["selection_token"] == selected_token),
            None,
        )
        if selected is not None:
            return selected, elapsed_ms
    if len(identities) == 1:
        v49._write_account_selection(str(identities[0]["selection_token"]))
        return identities[0], elapsed_ms

    # Selection is ambiguous: use the older expensive probe only as recovery.
    probed = v49._probe_accounts(reader)
    selected = v49._choose_account(probed)
    return {
        "account_no": str(selected["account_no"]),
        "selection_token": str(selected["selection_token"]),
        "masked_account": str(selected["masked_account"]),
        "account_fields": list(selected.get("account_fields") or []),
    }, elapsed_ms


def _read_selected_account(reader) -> dict[str, object]:
    identity, accounts_elapsed = _account_identity(reader)
    account_no = str(identity["account_no"])

    started = time.perf_counter()
    balance = reader.balances(account_no)
    balances_elapsed = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    raw_positions = list(reader.positions(account_no))
    positions_elapsed = (time.perf_counter() - started) * 1000.0

    normalized = [
        row
        for row in (v49.normalize_position_v49(item) for item in raw_positions)
        if row is not None
    ]
    available = v49._find_number(balance, ("availableCash", "available_cash"))
    withdrawable = v49._find_number(
        balance, ("withdrawableCash", "withdrawable_cash")
    )
    total_cash = v49._find_number(balance, ("totalCash", "total_cash"))
    balance_fields = (
        sorted(str(key) for key in balance.keys())
        if isinstance(balance, Mapping)
        else []
    )
    return {
        **identity,
        "balance": balance,
        "normalized_positions": normalized,
        "raw_position_count": len(raw_positions),
        "open_position_count": len(normalized),
        "available_cash_vnd": max(available or 0.0, 0.0),
        "withdrawable_cash_vnd": max(withdrawable or 0.0, 0.0),
        "total_cash_vnd": max(total_cash or 0.0, 0.0),
        "balance_fields": balance_fields,
        "accounts_elapsed_ms": accounts_elapsed,
        "balances_elapsed_ms": balances_elapsed,
        "positions_elapsed_ms": positions_elapsed,
    }


def latest_broker_portfolio_v59() -> dict[str, object] | None:
    raw = v49.latest_broker_portfolio_v49()
    return v55._public(raw) if raw is not None else None


def sync_broker_portfolio_v59() -> dict[str, object]:
    """Fast selected-account REST reconcile while retaining V55 valuation."""
    reader, credential_source = data_sources.reader_from_saved_credentials()
    try:
        selected = _read_selected_account(reader)
    finally:
        reader.close()

    normalized = list(selected["normalized_positions"])
    market_day, local_prices = v49._local_prices(
        [str(row["symbol"]) for row in normalized]
    )
    positions: list[dict[str, object]] = []
    for raw in normalized:
        symbol = str(raw["symbol"])
        quantity = int(raw["quantity"])
        local_price = float(local_prices.get(symbol, 0.0))
        average_cost = v49._price_vnd(float(raw["average_cost_raw"]), local_price)
        market_value = local_price * quantity if local_price > 0 else 0.0
        cost_value = average_cost * quantity
        pnl = market_value - cost_value
        pnl_pct = pnl / cost_value if cost_value > 0 else 0.0
        positions.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "sellable_quantity": int(raw["sellable_quantity"]),
                "average_cost_vnd": round(average_cost, 2),
                "broker_market_price_vnd": round(local_price, 2),
                "local_market_price_vnd": round(local_price, 2),
                "valuation_price_vnd": round(local_price, 2),
                "market_value_vnd": round(market_value, 2),
                "unrealized_pnl_vnd": round(pnl, 2),
                "unrealized_pnl_pct": pnl_pct,
                "account_count": 1,
                "broker_market_value_vnd": round(market_value, 2),
                "research_eod_market_value_vnd": round(market_value, 2),
                "research_eod_unrealized_pnl_vnd": round(pnl, 2),
                "research_eod_unrealized_pnl_pct": pnl_pct,
                "position_status": raw["status"],
                "broker_modified_at": raw["modified_at"],
            }
        )

    available_cash = float(selected["available_cash_vnd"])
    withdrawable_cash = float(selected["withdrawable_cash_vnd"])
    total_cash = float(selected["total_cash_vnd"])
    planner_cash = available_cash
    stock_value = round(sum(float(row["market_value_vnd"]) for row in positions), 2)
    nav = round(total_cash + stock_value, 2)
    snapshot_id = "broker-v59-" + datetime.now(v49.VN_TZ).strftime("%Y%m%d-%H%M%S-%f")
    captured_at = utc_now()
    masked = str(selected["masked_account"])
    modified_values = sorted(
        str(row.get("broker_modified_at") or "")
        for row in positions
        if row.get("broker_modified_at")
    )
    latest_modified = modified_values[-1] if modified_values else None
    timings = {
        "accounts_elapsed_ms": round(float(selected["accounts_elapsed_ms"]), 3),
        "balances_elapsed_ms": round(float(selected["balances_elapsed_ms"]), 3),
        "positions_elapsed_ms": round(float(selected["positions_elapsed_ms"]), 3),
    }
    details = {
        "version": V59_VERSION,
        "credential_source": credential_source,
        "selected_masked_account": masked,
        "selected_account_token": selected["selection_token"],
        "account_selection_mode": "PERSISTED_SELECTED_ACCOUNT_FAST_PATH",
        "raw_account_count": None,
        "selected_raw_position_count": selected["raw_position_count"],
        "selected_open_position_count": selected["open_position_count"],
        "selected_account_fields": selected["account_fields"],
        "selected_balance_fields": selected["balance_fields"],
        "quantity_rule": "OPEN_QUANTITY_PRESERVE_ZERO",
        "sellable_rule": "TRADE_QUANTITY_PRESERVE_ZERO",
        "planner_cash_source": "AVAILABLE_CASH",
        "valuation_source": "LOCAL_FINAL_EOD_CLOSE_ONLY",
        "broker_market_price_used": False,
        "read_only": True,
        "full_account_number_persisted": False,
        "rest_timings_ms": timings,
        "latest_position_modified_at": latest_modified,
    }

    with state_db() as db:
        v49._ensure_broker_schema_v49(db)
        _ensure_realtime_schema(db)
        db.execute(
            """
            INSERT INTO broker_snapshots(
                snapshot_id,captured_at,source,masked_accounts_json,
                total_cash_vnd,available_cash_vnd,withdrawable_cash_vnd,
                planner_cash_vnd,stock_value_vnd,net_asset_value_vnd,
                position_count,market_day,details_json,
                selected_account_token,broker_stock_value_vnd,broker_nav_vnd,
                research_eod_stock_value_vnd,research_eod_nav_vnd,
                source_freshness
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                captured_at,
                "DNSE_SELECTED_ACCOUNT_REST_V59",
                json.dumps([masked], ensure_ascii=False),
                total_cash,
                available_cash,
                withdrawable_cash,
                planner_cash,
                stock_value,
                nav,
                len(positions),
                market_day,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                selected["selection_token"],
                stock_value,
                nav,
                stock_value,
                nav,
                "REST_RECONCILE_AT_REQUEST_TIME",
            ),
        )
        db.executemany(
            """
            INSERT INTO broker_positions(
                snapshot_id,symbol,quantity,sellable_quantity,
                average_cost_vnd,broker_market_price_vnd,
                local_market_price_vnd,valuation_price_vnd,
                market_value_vnd,unrealized_pnl_vnd,unrealized_pnl_pct,
                account_count,broker_market_value_vnd,
                research_eod_market_value_vnd,
                research_eod_unrealized_pnl_vnd,
                research_eod_unrealized_pnl_pct,
                position_status,broker_modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    snapshot_id,
                    row["symbol"],
                    row["quantity"],
                    row["sellable_quantity"],
                    row["average_cost_vnd"],
                    row["broker_market_price_vnd"],
                    row["local_market_price_vnd"],
                    row["valuation_price_vnd"],
                    row["market_value_vnd"],
                    row["unrealized_pnl_vnd"],
                    row["unrealized_pnl_pct"],
                    1,
                    row["broker_market_value_vnd"],
                    row["research_eod_market_value_vnd"],
                    row["research_eod_unrealized_pnl_vnd"],
                    row["research_eod_unrealized_pnl_pct"],
                    row["position_status"],
                    row["broker_modified_at"],
                )
                for row in positions
            ],
        )
        db.execute(
            """
            INSERT INTO broker_rest_reconcile_v59(
                snapshot_id,captured_at,selected_account_token,
                accounts_elapsed_ms,balances_elapsed_ms,positions_elapsed_ms,
                raw_position_count,open_position_count,
                latest_position_modified_at,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                captured_at,
                selected["selection_token"],
                timings["accounts_elapsed_ms"],
                timings["balances_elapsed_ms"],
                timings["positions_elapsed_ms"],
                selected["raw_position_count"],
                selected["open_position_count"],
                latest_modified,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
            ),
        )

    current = account_snapshot()
    replace_account(
        cash_vnd=max(planner_cash, 0.0),
        weekly_contribution_vnd=float(current["account"]["weekly_contribution_vnd"]),
        holdings=[
            {
                "symbol": row["symbol"],
                "quantity": row["quantity"],
                "average_cost": row["average_cost_vnd"],
            }
            for row in positions
        ],
    )
    v55._rewrite_snapshot(snapshot_id, strict=True)
    latest = latest_broker_portfolio_v59()
    if latest is None:
        raise RuntimeError("V59_BROKER_SNAPSHOT_READBACK_FAILED")
    latest["rest_timings_ms"] = timings
    latest["realtime"] = realtime_status_v59(include_portfolio=False)
    return latest


def _message_dict(message: object) -> dict[str, object]:
    model_dump = getattr(message, "model_dump", None)
    if callable(model_dump):
        try:
            value = model_dump(by_alias=True)
        except TypeError:
            value = model_dump()
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
    if isinstance(message, Mapping):
        return {str(key): item for key, item in message.items()}
    try:
        return {
            str(key): value
            for key, value in vars(message).items()
            if not str(key).startswith("_")
        }
    except TypeError:
        return {"repr": repr(message)}


def _stream_account_token(payload: Mapping[str, object]) -> str | None:
    account_no = str(
        v49._first_present(
            payload,
            (
                "accountNo",
                "account_no",
                "account",
                "investorAccountId",
                "investor_account_id",
            ),
            "",
        )
        or ""
    ).strip()
    return v49._account_token(account_no) if account_no else None


def _stream_modified_at(payload: Mapping[str, object]) -> str | None:
    value = v49._first_present(
        payload,
        (
            "modifiedDate",
            "modified_date",
            "modified_at",
            "updatedAt",
            "updated_at",
            "timestamp",
            "time",
        ),
        None,
    )
    return str(value) if value not in (None, "") else None


def _record_stream_event(event_type: str, message: object) -> None:
    payload = _message_dict(message)
    received_at = utc_now()
    symbol = str(
        v49._first_present(payload, ("symbol", "ticker", "instrument"), "") or ""
    ).strip().upper() or None
    account_token = _stream_account_token(payload)
    modified_at = _stream_modified_at(payload)

    with state_db() as db:
        _ensure_realtime_schema(db)
        db.execute(
            """
            INSERT INTO broker_realtime_events_v59(
                received_at,event_type,account_token,symbol,
                source_modified_at,payload_json
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                received_at,
                event_type,
                account_token,
                symbol,
                modified_at,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            ),
        )

        if event_type == "POSITION" and symbol:
            quantity = int(
                max(
                    v49._finite_float(
                        v49._first_present(
                            payload,
                            (
                                "openQuantity",
                                "open_quantity",
                                "quantity",
                                "qty",
                                "open_qty",
                            ),
                            0,
                        )
                    ),
                    0.0,
                )
            )
            sellable_raw = v49._first_present(
                payload,
                (
                    "tradeQuantity",
                    "trade_quantity",
                    "sellableQuantity",
                    "sellable_quantity",
                    "availableQuantity",
                    "available_quantity",
                    "sellable_qty",
                    "trade_qty",
                ),
                None,
            )
            sellable = (
                None
                if sellable_raw is None
                else min(max(int(v49._finite_float(sellable_raw)), 0), quantity)
            )
            average_cost_raw = v49._finite_float(
                v49._first_present(
                    payload,
                    (
                        "costPrice",
                        "cost_price",
                        "averagePrice",
                        "average_price",
                        "avgPrice",
                        "avg_price",
                    ),
                    0.0,
                )
            )
            db.execute(
                """
                INSERT INTO broker_realtime_positions_v59(
                    symbol,account_token,quantity,sellable_quantity,
                    average_cost_raw,source_modified_at,received_at,payload_json
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET
                    account_token=excluded.account_token,
                    quantity=excluded.quantity,
                    sellable_quantity=excluded.sellable_quantity,
                    average_cost_raw=excluded.average_cost_raw,
                    source_modified_at=excluded.source_modified_at,
                    received_at=excluded.received_at,
                    payload_json=excluded.payload_json
                """,
                (
                    symbol,
                    account_token,
                    quantity,
                    sellable,
                    average_cost_raw,
                    modified_at,
                    received_at,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )

        if event_type == "ACCOUNT":
            available = v49._find_number(
                payload, ("availableCash", "available_cash", "available")
            )
            total = v49._find_number(
                payload, ("totalCash", "total_cash", "balance")
            )
            withdrawable = v49._find_number(
                payload, ("withdrawableCash", "withdrawable_cash")
            )
            db.execute(
                """
                INSERT INTO broker_realtime_account_v59(
                    singleton,account_token,available_cash_raw,total_cash_raw,
                    withdrawable_cash_raw,source_modified_at,received_at,payload_json
                ) VALUES(1,?,?,?,?,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    account_token=excluded.account_token,
                    available_cash_raw=excluded.available_cash_raw,
                    total_cash_raw=excluded.total_cash_raw,
                    withdrawable_cash_raw=excluded.withdrawable_cash_raw,
                    source_modified_at=excluded.source_modified_at,
                    received_at=excluded.received_at,
                    payload_json=excluded.payload_json
                """,
                (
                    account_token,
                    available,
                    total,
                    withdrawable,
                    modified_at,
                    received_at,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )


def _stream_worker(api_key: str, api_secret: str) -> None:
    global _STREAM_OBJECT, _STREAM_LAST_ERROR, _STREAM_STATUS
    try:
        from dnse import DnseTradingStream

        stream = DnseTradingStream(api_key=api_key, api_secret=api_secret)
        with _STREAM_LOCK:
            _STREAM_OBJECT = stream
            _STREAM_STATUS = "RUNNING"
            _STREAM_LAST_ERROR = None

        async def on_position(message):
            _record_stream_event("POSITION", message)

        async def on_order(message):
            _record_stream_event("ORDER", message)

        async def on_account(message):
            _record_stream_event("ACCOUNT", message)

        stream.subscribe_positions(on_position)
        stream.subscribe_orders(on_order)
        subscribe_account = getattr(stream, "subscribe_account", None)
        if callable(subscribe_account):
            subscribe_account(on_account)
        stream.run()
        with _STREAM_LOCK:
            if _STREAM_STATUS != "STOPPING":
                _STREAM_STATUS = "STOPPED"
    except Exception as exc:  # pragma: no cover - network/runtime path
        with _STREAM_LOCK:
            _STREAM_LAST_ERROR = f"{type(exc).__name__}:{exc}"
            _STREAM_STATUS = "ERROR"
    finally:
        with _STREAM_LOCK:
            _STREAM_OBJECT = None


def start_realtime_stream_v59() -> dict[str, object]:
    global _STREAM_THREAD, _STREAM_STARTED_AT, _STREAM_LAST_ERROR, _STREAM_STATUS
    with _STREAM_LOCK:
        if _STREAM_THREAD is not None and _STREAM_THREAD.is_alive():
            return realtime_status_v59(include_portfolio=False)
        credentials, source = data_sources._credentials_or_raise()
        _STREAM_STARTED_AT = utc_now()
        _STREAM_LAST_ERROR = None
        _STREAM_STATUS = "STARTING"
        _STREAM_THREAD = threading.Thread(
            target=_stream_worker,
            args=(credentials["api_key"], credentials["api_secret"]),
            name="vnquant-dnse-trading-stream",
            daemon=True,
        )
        _STREAM_THREAD.start()
    result = realtime_status_v59(include_portfolio=False)
    result["credential_source"] = source
    return result


def stop_realtime_stream_v59() -> dict[str, object]:
    global _STREAM_STATUS
    with _STREAM_LOCK:
        _STREAM_STATUS = "STOPPING"
        stream = _STREAM_OBJECT
        thread = _STREAM_THREAD
    if stream is not None:
        for name in ("stop", "close"):
            method = getattr(stream, name, None)
            if callable(method):
                try:
                    method()
                    break
                except Exception:
                    continue
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)
    with _STREAM_LOCK:
        if thread is None or not thread.is_alive():
            _STREAM_STATUS = "STOPPED"
    return realtime_status_v59(include_portfolio=False)


def _selected_token() -> str | None:
    return v49._read_account_selection()


def _realtime_rows() -> list[dict[str, object]]:
    selected_token = _selected_token()
    with state_db() as db:
        _ensure_realtime_schema(db)
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM broker_realtime_positions_v59 ORDER BY symbol"
            ).fetchall()
        ]
    if not selected_token:
        return rows
    scoped = [
        row
        for row in rows
        if row.get("account_token") in (None, "", selected_token)
    ]
    return scoped


def realtime_display_portfolio_v59() -> dict[str, object] | None:
    """Overlay WS position quantities onto the last REST/EOD snapshot for UI only."""
    raw = v49.latest_broker_portfolio_v49()
    if raw is None:
        return None
    base = v55._public(raw)
    if base is None:
        return None
    captured_at = str(base.get("captured_at") or "")
    market_day = str(base.get("market_day") or "")
    by_symbol = {str(row["symbol"]): dict(row) for row in base.get("positions", [])}
    applied = 0
    unverified_scope = 0
    selected_token = _selected_token()
    for realtime in _realtime_rows():
        received_at = str(realtime.get("received_at") or "")
        if captured_at and received_at and received_at <= captured_at:
            continue
        symbol = str(realtime.get("symbol") or "").upper()
        if not symbol:
            continue
        account_token = realtime.get("account_token")
        if account_token in (None, ""):
            unverified_scope += 1
        elif selected_token and account_token != selected_token:
            continue
        quantity = max(int(realtime.get("quantity") or 0), 0)
        existing = by_symbol.get(symbol, {})
        price = float(existing.get("official_eod_price_vnd") or 0.0)
        if price <= 0 and market_day:
            price = v55._eod_price(symbol, market_day)
        average_cost = float(existing.get("average_cost_vnd") or 0.0)
        raw_cost = float(realtime.get("average_cost_raw") or 0.0)
        if raw_cost > 0:
            average_cost = v49._price_vnd(raw_cost, price)
        sellable_raw = realtime.get("sellable_quantity")
        sellable = (
            int(existing.get("sellable_quantity") or 0)
            if sellable_raw is None
            else max(min(int(sellable_raw), quantity), 0)
        )
        if quantity <= 0:
            by_symbol.pop(symbol, None)
            applied += 1
            continue
        market_value = price * quantity if price > 0 else 0.0
        cost_value = average_cost * quantity
        pnl = market_value - cost_value
        pnl_pct = pnl / cost_value if cost_value > 0 else 0.0
        by_symbol[symbol] = {
            **existing,
            "symbol": symbol,
            "quantity": quantity,
            "sellable_quantity": sellable,
            "average_cost_vnd": round(average_cost, 2),
            "official_eod_price_vnd": round(price, 2),
            "valuation_price_vnd": round(price, 2),
            "market_value_vnd": round(market_value, 2),
            "unrealized_pnl_vnd": round(pnl, 2),
            "unrealized_pnl_pct": pnl_pct,
            "realtime_received_at": received_at,
            "realtime_source_modified_at": realtime.get("source_modified_at"),
            "realtime_account_scope_verified": bool(account_token),
        }
        applied += 1
    positions = sorted(
        by_symbol.values(),
        key=lambda row: (-float(row.get("market_value_vnd") or 0.0), str(row.get("symbol"))),
    )
    stock_value = round(sum(float(row.get("market_value_vnd") or 0.0) for row in positions), 2)
    nav = round(float(base.get("total_cash_vnd") or 0.0) + stock_value, 2)
    return {
        **base,
        "positions": positions,
        "position_count": len(positions),
        "stock_value_vnd": stock_value,
        "net_asset_value_vnd": nav,
        "official_eod_stock_value_vnd": stock_value,
        "official_eod_nav_vnd": nav,
        "display_state_source": "REST_CHECKPOINT_PLUS_WS_POSITION_OVERLAY",
        "realtime_overlay_count": applied,
        "realtime_unverified_scope_count": unverified_scope,
        "planner_uses_ws_state": False,
        "automatic_live_orders_allowed": False,
    }


def realtime_status_v59(*, include_portfolio: bool = True) -> dict[str, object]:
    with _STREAM_LOCK:
        thread_alive = bool(_STREAM_THREAD is not None and _STREAM_THREAD.is_alive())
        status = _STREAM_STATUS
        started_at = _STREAM_STARTED_AT
        last_error = _STREAM_LAST_ERROR
    selected_token = _selected_token()
    with state_db() as db:
        _ensure_realtime_schema(db)
        count = int(db.execute("SELECT COUNT(*) FROM broker_realtime_events_v59").fetchone()[0])
        latest_event = db.execute(
            "SELECT * FROM broker_realtime_events_v59 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        latest_rest = db.execute(
            "SELECT * FROM broker_rest_reconcile_v59 ORDER BY captured_at DESC LIMIT 1"
        ).fetchone()
    latest_event_dict = dict(latest_event) if latest_event is not None else None
    latest_rest_dict = dict(latest_rest) if latest_rest is not None else None
    ws_modified = (
        str(latest_event_dict.get("source_modified_at") or "")
        if latest_event_dict
        else ""
    )
    rest_modified = (
        str(latest_rest_dict.get("latest_position_modified_at") or "")
        if latest_rest_dict
        else ""
    )
    result: dict[str, object] = {
        "status": status,
        "version": V59_VERSION,
        "mode": REALTIME_MODE,
        "thread_alive": thread_alive,
        "started_at": started_at,
        "last_error": last_error,
        "event_count": count,
        "last_event_at": latest_event_dict.get("received_at") if latest_event_dict else None,
        "last_event_type": latest_event_dict.get("event_type") if latest_event_dict else None,
        "last_event_symbol": latest_event_dict.get("symbol") if latest_event_dict else None,
        "last_ws_source_modified_at": ws_modified or None,
        "last_rest_position_modified_at": rest_modified or None,
        "ws_newer_than_rest_modified": bool(ws_modified and rest_modified and ws_modified > rest_modified),
        "selected_account_token_present": bool(selected_token),
        "planner_uses_ws_state": False,
        "rest_checkpoint_is_audit_source": True,
        "automatic_live_orders_allowed": False,
    }
    if latest_rest_dict:
        result["last_rest_snapshot_id"] = latest_rest_dict.get("snapshot_id")
        result["last_rest_captured_at"] = latest_rest_dict.get("captured_at")
        result["rest_timings_ms"] = {
            "accounts": latest_rest_dict.get("accounts_elapsed_ms"),
            "balances": latest_rest_dict.get("balances_elapsed_ms"),
            "positions": latest_rest_dict.get("positions_elapsed_ms"),
        }
    if include_portfolio:
        result["portfolio"] = realtime_display_portfolio_v59()
    return result


def apply() -> None:
    if getattr(broker_portfolio, "_v59_fast_realtime_applied", False):
        return
    _configure_market_db()
    with state_db() as db:
        _ensure_realtime_schema(db)

    core.market_coverage = fast_market_coverage_v59
    core.workstation_status = workstation_status_v59
    broker_portfolio.sync_broker_portfolio = sync_broker_portfolio_v59
    broker_portfolio.latest_broker_portfolio = latest_broker_portfolio_v59
    weekly_plan.latest_broker_portfolio = latest_broker_portfolio_v59
    capital_plan.latest_broker_portfolio = latest_broker_portfolio_v59
    performance.latest_broker_portfolio = latest_broker_portfolio_v59

    broker_portfolio.realtime_status = realtime_status_v59
    broker_portfolio.realtime_display_portfolio = realtime_display_portfolio_v59
    broker_portfolio.start_realtime_stream = start_realtime_stream_v59
    broker_portfolio.stop_realtime_stream = stop_realtime_stream_v59
    broker_portfolio.V59_VERSION = V59_VERSION
    broker_portfolio._v59_fast_realtime_applied = True
