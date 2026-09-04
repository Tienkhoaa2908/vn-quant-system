"""V86 isolated DNSE OpenAPI realtime sidecar.

Runs ONLY in a dedicated Python environment containing ``dnse-sdk-openapi``.
It never imports the canonical workstation runtime, never obtains a Trading Token,
and never subscribes to private order/position channels.

The sidecar writes a sanitized atomic JSON state file consumed by the existing
localhost web. API key/secret are read from the workstation credential file and
are never emitted to state/log output.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, time as dtime, timedelta, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, Mapping

V86 = "V86_DNSE_OPENAPI_REALTIME_SIDECAR"
EXPECTED_DIST = "dnse-sdk-openapi"
EXPECTED_VERSION = "1.4.6"
PINNED_API_VERSION = "2026-05-07"
WS_BASE = "wss://ws-openapi.dnse.com.vn"
REST_BASE = "https://openapi.dnse.com.vn"
VN_TZ = timezone(timedelta(hours=7))
STALE_TICK_SEC = 30.0


def _utc_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _load_json(path: Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _credentials(path: Path) -> tuple[str, str]:
    raw = _load_json(path)
    if not isinstance(raw, Mapping):
        raise ValueError("V86_CREDENTIAL_FILE_INVALID")
    key = str(raw.get("api_key") or "").strip()
    secret = str(raw.get("api_secret") or "").strip()
    if not key or not secret:
        raise ValueError("V86_CREDENTIALS_MISSING")
    return key, secret


def _symbols(path: Path) -> list[str]:
    raw = _load_json(path)
    if isinstance(raw, Mapping):
        raw = raw.get("symbols")
    if not isinstance(raw, list):
        raise ValueError("V86_SYMBOLS_INVALID")
    out: list[str] = []
    for item in raw:
        symbol = str(item or "").strip().upper()
        if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
            continue
        if symbol not in out:
            out.append(symbol)
    if not out:
        raise ValueError("V86_SYMBOLS_EMPTY")
    return out[:40]


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _dist_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def runtime_contract() -> dict[str, object]:
    new = _dist_version(EXPECTED_DIST)
    legacy = _dist_version("dnse")
    return {
        "python": sys.version.split()[0],
        "sdk_distribution": EXPECTED_DIST,
        "sdk_version": new,
        "sdk_version_ok": new == EXPECTED_VERSION,
        "legacy_dnse_distribution_present": legacy is not None,
        "legacy_dnse_distribution_version": legacy,
        "api_version": PINNED_API_VERSION,
        "ws_base": WS_BASE,
        "rest_base": REST_BASE,
    }


def _market_window_vn(now: datetime | None = None) -> bool:
    """Approximate local trading window; not a holiday-calendar assertion."""
    current = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)
    if current.weekday() >= 5:
        return False
    t = current.timetz().replace(tzinfo=None)
    return dtime(9, 0) <= t <= dtime(15, 0)


def _obj_value(obj: object, *names: str) -> object | None:
    for name in names:
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _safe_num(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


class State:
    def __init__(self, path: Path, symbols: list[str], encoding: str) -> None:
        self.path = Path(path)
        self.symbols = symbols
        self.encoding = encoding
        self.started_at = _utc_iso()
        self.last_tick_epoch: float | None = None
        self.last_tick: dict[str, object] | None = None
        self.event_count = 0
        self.reconnect_count = 0
        self.last_reconnect_at: str | None = None
        self.last_error: str | None = None
        self.rest_smoke: dict[str, object] = {"status": "NOT_RUN"}
        self.client: Any = None
        self.exit_requested = False

    def on_trade(self, trade: object) -> None:
        self.event_count += 1
        self.last_tick_epoch = time.time()
        self.last_tick = {
            "symbol": str(_obj_value(trade, "symbol", "s") or "").upper() or None,
            "price": _safe_num(_obj_value(trade, "price", "p", "matchPrice")),
            "volume": _safe_num(_obj_value(trade, "volume", "q", "matchQuantity")),
            "received_at": _utc_iso(),
        }

    def on_reconnected(self, _payload: object) -> None:
        self.reconnect_count += 1
        self.last_reconnect_at = _utc_iso()

    def on_error(self, exc: object) -> None:
        self.last_error = f"{type(exc).__name__}:{exc}" if isinstance(exc, BaseException) else str(exc)

    def snapshot(self, *, final_status: str | None = None) -> dict[str, object]:
        client = self.client
        conn = getattr(client, "_connection", None) if client is not None else None
        transport = bool(conn is not None and getattr(conn, "is_connected", False))
        authenticated = bool(getattr(client, "_is_authenticated", False)) if client is not None else False
        subscriptions = dict(getattr(client, "_subscriptions", {}) or {}) if client is not None else {}
        heartbeat = bool(getattr(client, "is_healthy", False)) if client is not None else False
        last_pong = _safe_num(getattr(client, "_last_pong_time", None)) if client is not None else None
        now = time.time()
        pong_age = max(0.0, now - last_pong) if last_pong else None
        tick_age = max(0.0, now - self.last_tick_epoch) if self.last_tick_epoch else None
        market_window = _market_window_vn()

        if final_status:
            semantic = final_status
        elif not transport or not authenticated:
            semantic = "DEGRADED"
        elif not subscriptions:
            semantic = "DEGRADED_NO_SUBSCRIPTION"
        elif not heartbeat:
            semantic = "DEGRADED_HEARTBEAT"
        elif market_window and (tick_age is None or tick_age > STALE_TICK_SEC):
            semantic = "DEGRADED_STALE_TICK"
        elif market_window:
            semantic = "HEALTHY"
        else:
            semantic = "IDLE_MARKET_CLOSED"

        return {
            "version": V86,
            "status": semantic,
            "updated_at": _utc_iso(),
            "started_at": self.started_at,
            "pid": os.getpid(),
            "runtime": runtime_contract(),
            "encoding": self.encoding,
            "symbols": self.symbols,
            "symbol_count": len(self.symbols),
            "process_alive": not bool(final_status),
            "transport_connected": transport,
            "authenticated": authenticated,
            "subscriptions_active": bool(subscriptions),
            "subscription_channels": sorted(subscriptions),
            "heartbeat_healthy": heartbeat,
            "last_pong_age_sec": round(pong_age, 3) if pong_age is not None else None,
            "event_count": self.event_count,
            "last_tick": self.last_tick,
            "last_tick_age_sec": round(tick_age, 3) if tick_age is not None else None,
            "market_window_expected": market_window,
            "market_window_source": "LOCAL_CLOCK_APPROX_NOT_EXCHANGE_CALENDAR",
            "reconnect_count": self.reconnect_count,
            "last_reconnect_at": self.last_reconnect_at,
            "last_error": self.last_error,
            "rest_smoke": self.rest_smoke,
            "private_order_stream_subscribed": False,
            "private_position_stream_subscribed": False,
            "trading_token_requested": False,
            "orders_sent": False,
            "live_order_ready": False,
        }

    def persist(self, *, final_status: str | None = None) -> None:
        _atomic_json(self.path, self.snapshot(final_status=final_status))


def _rest_smoke(api_key: str, api_secret: str) -> dict[str, object]:
    """Read-only OpenAPI REST smoke pinned to the compatibility date."""
    try:
        from dnse import DNSEClient
        client = DNSEClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url=REST_BASE,
            api_version=PINNED_API_VERSION,
        )
        started = time.perf_counter()
        status, body = client.get_accounts(dry_run=False)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        account_count = None
        if isinstance(body, Mapping):
            value = body.get("accounts") or body.get("data")
            if isinstance(value, list):
                account_count = len(value)
        elif isinstance(body, list):
            account_count = len(body)
        return {
            "status": "SUCCESS" if 200 <= int(status) < 300 else "FAILED",
            "http_status": int(status),
            "latency_ms": round(elapsed_ms, 2),
            "account_count": account_count,
            "api_version": PINNED_API_VERSION,
            "rate_limit_headers_exposed_by_public_sdk": False,
        }
    except Exception as exc:
        return {
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "api_version": PINNED_API_VERSION,
            "rate_limit_headers_exposed_by_public_sdk": False,
        }


async def run(args: argparse.Namespace) -> int:
    contract = runtime_contract()
    if not contract["sdk_version_ok"]:
        raise RuntimeError(f"V86_SDK_VERSION_MISMATCH:{contract['sdk_version']}!={EXPECTED_VERSION}")
    if contract["legacy_dnse_distribution_present"]:
        raise RuntimeError(f"V86_SIDECAR_NOT_ISOLATED:legacy_dnse={contract['legacy_dnse_distribution_version']}")

    api_key, api_secret = _credentials(args.credentials)
    symbols = _symbols(args.symbols_file)
    state = State(args.state, symbols, args.encoding)
    state.rest_smoke = _rest_smoke(api_key, api_secret) if args.rest_smoke else {"status": "SKIPPED"}
    state.persist()

    from dnse import TradingClient

    client = TradingClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url=WS_BASE,
        encoding=args.encoding,
        auto_reconnect=True,
        max_retries=args.max_retries,
        heartbeat_interval=args.heartbeat_interval,
        timeout=args.timeout,
    )
    state.client = client
    client.on("reconnected", state.on_reconnected)
    client.on("error", state.on_error)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def request_stop() -> None:
        state.exit_requested = True
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except (NotImplementedError, RuntimeError):
            pass

    monitor_task: asyncio.Task[None] | None = None
    try:
        await client.connect()
        await client.subscribe_trades(symbols, on_trade=state.on_trade, encoding=args.encoding)
        state.persist()

        async def monitor() -> None:
            while not stop_event.is_set():
                state.persist()
                await asyncio.sleep(args.state_interval)

        monitor_task = asyncio.create_task(monitor())
        if args.duration > 0:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            await stop_event.wait()
        return 0
    except Exception as exc:
        state.last_error = f"{type(exc).__name__}:{exc}"
        state.persist(final_status="ERROR")
        return 2
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        try:
            await client.disconnect()
        except Exception as exc:
            if state.last_error is None:
                state.last_error = f"DISCONNECT:{type(exc).__name__}:{exc}"
        state.persist(final_status="STOPPED")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--symbols-file", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--duration", type=float, default=0.0)
    p.add_argument("--encoding", choices=("json", "msgpack"), default="msgpack")
    p.add_argument("--heartbeat-interval", type=float, default=25.0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--max-retries", type=int, default=10)
    p.add_argument("--state-interval", type=float, default=2.0)
    p.add_argument("--rest-smoke", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
