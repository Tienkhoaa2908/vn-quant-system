"""V59 read-only DNSE market stream for a local realtime trading screen.

The stream is display/diagnostic only. Live ticks, quotes and security metadata
must never replace the V55 final-EOD close used by research/performance/NAV.
"""
from __future__ import annotations

import json
import math
import sqlite3
import threading
from typing import Mapping, Sequence

from . import data_sources
from .core import state_db, utc_now
from . import v59_fast_realtime as broker_rt

V59_MARKET_VERSION = "V59_DNSE_MARKET_STREAM_READ_ONLY"
MAX_STREAM_SYMBOLS = 30

_LOCK = threading.RLock()
_THREAD: threading.Thread | None = None
_STREAM = None
_STATUS = "STOPPED"
_STARTED_AT: str | None = None
_LAST_ERROR: str | None = None
_SUBSCRIBED: tuple[str, ...] = ()


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_realtime_events_v59(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            symbol TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_market_realtime_events_v59_received
        ON market_realtime_events_v59(received_at DESC);

        CREATE TABLE IF NOT EXISTS market_realtime_current_v59(
            symbol TEXT PRIMARY KEY,
            last_price REAL,
            last_volume REAL,
            bid_price REAL,
            bid_volume REAL,
            ask_price REAL,
            ask_volume REAL,
            reference_price REAL,
            ceiling_price REAL,
            floor_price REAL,
            expected_price REAL,
            trade_received_at TEXT,
            quote_received_at TEXT,
            security_received_at TEXT,
            expected_received_at TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )


def _message_dict(message: object) -> dict[str, object]:
    return broker_rt._message_dict(message)


def _first(payload: Mapping[str, object], names: Sequence[str]) -> object:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return None


def _symbol(payload: Mapping[str, object]) -> str | None:
    value = _first(payload, ("symbol", "ticker", "instrument"))
    text = str(value or "").strip().upper()
    return text or None


def _price(payload: Mapping[str, object], *names: str) -> float | None:
    return _finite(_first(payload, names))


def _record(event_type: str, message: object) -> None:
    payload = _message_dict(message)
    symbol = _symbol(payload)
    received_at = utc_now()
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            "INSERT INTO market_realtime_events_v59(received_at,event_type,symbol,payload_json) VALUES(?,?,?,?)",
            (
                received_at,
                event_type,
                symbol,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            ),
        )
        if not symbol:
            return
        db.execute(
            "INSERT INTO market_realtime_current_v59(symbol,updated_at) VALUES(?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET updated_at=excluded.updated_at",
            (symbol, received_at),
        )
        if event_type == "TRADE":
            db.execute(
                """
                UPDATE market_realtime_current_v59
                SET last_price=COALESCE(?,last_price),
                    last_volume=COALESCE(?,last_volume),
                    trade_received_at=?,updated_at=?
                WHERE symbol=?
                """,
                (
                    _price(payload, "price", "lastPrice", "last_price"),
                    _price(payload, "volume", "qty", "quantity"),
                    received_at,
                    received_at,
                    symbol,
                ),
            )
        elif event_type == "QUOTE":
            db.execute(
                """
                UPDATE market_realtime_current_v59
                SET bid_price=COALESCE(?,bid_price),
                    bid_volume=COALESCE(?,bid_volume),
                    ask_price=COALESCE(?,ask_price),
                    ask_volume=COALESCE(?,ask_volume),
                    quote_received_at=?,updated_at=?
                WHERE symbol=?
                """,
                (
                    _price(payload, "bidPrice", "bid_price", "bid"),
                    _price(payload, "bidVolume", "bid_volume", "bidQty", "bid_qty"),
                    _price(payload, "askPrice", "ask_price", "ask"),
                    _price(payload, "askVolume", "ask_volume", "askQty", "ask_qty"),
                    received_at,
                    received_at,
                    symbol,
                ),
            )
        elif event_type == "SECURITY":
            db.execute(
                """
                UPDATE market_realtime_current_v59
                SET reference_price=COALESCE(?,reference_price),
                    ceiling_price=COALESCE(?,ceiling_price),
                    floor_price=COALESCE(?,floor_price),
                    security_received_at=?,updated_at=?
                WHERE symbol=?
                """,
                (
                    _price(payload, "refPrice", "ref_price", "referencePrice", "reference_price"),
                    _price(payload, "ceiling", "ceilingPrice", "ceiling_price"),
                    _price(payload, "floor", "floorPrice", "floor_price"),
                    received_at,
                    received_at,
                    symbol,
                ),
            )
        elif event_type == "EXPECTED":
            db.execute(
                """
                UPDATE market_realtime_current_v59
                SET expected_price=COALESCE(?,expected_price),
                    expected_received_at=?,updated_at=?
                WHERE symbol=?
                """,
                (
                    _price(payload, "price", "expectedPrice", "expected_price"),
                    received_at,
                    received_at,
                    symbol,
                ),
            )


def _preview_symbols(limit: int = 20) -> list[str]:
    with state_db() as db:
        try:
            row = db.execute(
                "SELECT rows_json FROM preview_snapshots ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        except sqlite3.DatabaseError:
            row = None
    if row is None:
        return []
    try:
        values = json.loads(str(row[0]))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    result: list[str] = []
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, Mapping):
                continue
            symbol = str(item.get("symbol") or "").strip().upper()
            if symbol and symbol not in result:
                result.append(symbol)
            if len(result) >= limit:
                break
    return result


def desired_symbols_v59() -> tuple[str, ...]:
    holdings: list[str] = []
    try:
        portfolio = broker_rt.latest_broker_portfolio_v59()
    except Exception:
        portfolio = None
    if isinstance(portfolio, Mapping):
        for row in portfolio.get("positions", []) or []:
            if not isinstance(row, Mapping):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol and symbol not in holdings:
                holdings.append(symbol)
    combined = holdings + [s for s in _preview_symbols(20) if s not in holdings]
    return tuple(combined[:MAX_STREAM_SYMBOLS])


def _worker(api_key: str, api_secret: str, symbols: tuple[str, ...]) -> None:
    global _STREAM, _STATUS, _LAST_ERROR
    try:
        from dnse import DnseMarketStream

        stream = DnseMarketStream(api_key=api_key, api_secret=api_secret)
        with _LOCK:
            _STREAM = stream
            _STATUS = "RUNNING"
            _LAST_ERROR = None

        async def on_trade(message):
            _record("TRADE", message)

        async def on_quote(message):
            _record("QUOTE", message)

        async def on_security(message):
            _record("SECURITY", message)

        async def on_expected(message):
            _record("EXPECTED", message)

        stream.subscribe_trades(list(symbols), on_trade)
        stream.subscribe_quotes(list(symbols), on_quote)
        subscribe_security = getattr(stream, "subscribe_security_def", None)
        if callable(subscribe_security):
            subscribe_security(list(symbols), on_security)
        subscribe_expected = getattr(stream, "subscribe_expected_price", None)
        if callable(subscribe_expected):
            subscribe_expected(list(symbols), on_expected)
        stream.run()
        with _LOCK:
            if _STATUS != "STOPPING":
                _STATUS = "STOPPED"
    except Exception as exc:  # pragma: no cover - live network/runtime
        with _LOCK:
            _LAST_ERROR = f"{type(exc).__name__}:{exc}"
            _STATUS = "ERROR"
    finally:
        with _LOCK:
            _STREAM = None


def start_market_realtime_v59(*, force_restart: bool = False) -> dict[str, object]:
    global _THREAD, _STARTED_AT, _LAST_ERROR, _STATUS, _SUBSCRIBED
    desired = desired_symbols_v59()
    with _LOCK:
        running = bool(_THREAD is not None and _THREAD.is_alive())
        current_symbols = _SUBSCRIBED
    if running and not force_restart and desired == current_symbols:
        return market_realtime_status_v59()
    if running:
        stop_market_realtime_v59()
    if not desired:
        with _LOCK:
            _SUBSCRIBED = ()
            _STATUS = "WAITING_FOR_SYMBOLS"
        return market_realtime_status_v59()

    credentials, source = data_sources._credentials_or_raise()
    with _LOCK:
        _SUBSCRIBED = desired
        _STARTED_AT = utc_now()
        _LAST_ERROR = None
        _STATUS = "STARTING"
        _THREAD = threading.Thread(
            target=_worker,
            args=(credentials["api_key"], credentials["api_secret"], desired),
            name="vnquant-dnse-market-stream",
            daemon=True,
        )
        _THREAD.start()
    result = market_realtime_status_v59()
    result["credential_source"] = source
    return result


def stop_market_realtime_v59() -> dict[str, object]:
    global _STATUS
    with _LOCK:
        _STATUS = "STOPPING"
        stream = _STREAM
        thread = _THREAD
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
    with _LOCK:
        if thread is None or not thread.is_alive():
            _STATUS = "STOPPED"
    return market_realtime_status_v59()


def market_realtime_status_v59() -> dict[str, object]:
    with _LOCK:
        thread_alive = bool(_THREAD is not None and _THREAD.is_alive())
        status = _STATUS
        started_at = _STARTED_AT
        last_error = _LAST_ERROR
        subscribed = _SUBSCRIBED
    with state_db() as db:
        _ensure_schema(db)
        event_count = int(db.execute("SELECT COUNT(*) FROM market_realtime_events_v59").fetchone()[0])
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM market_realtime_current_v59 ORDER BY symbol"
            ).fetchall()
        ]
        latest = db.execute(
            "SELECT received_at,event_type,symbol FROM market_realtime_events_v59 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "status": status,
        "version": V59_MARKET_VERSION,
        "thread_alive": thread_alive,
        "started_at": started_at,
        "last_error": last_error,
        "subscribed_symbols": list(subscribed),
        "subscribed_symbol_count": len(subscribed),
        "event_count": event_count,
        "last_event": dict(latest) if latest is not None else None,
        "quotes": rows,
        "valuation_policy": "LIVE_QUOTES_DISPLAY_ONLY_FINAL_EOD_REMAINS_CANONICAL",
        "automatic_live_orders_allowed": False,
    }
