"""V59 localhost web runtime.

This wrapper keeps the existing UI/routes but adds DNSE private+market realtime
streams and removes deep market/performance refreshes from the interactive plan
hot path. Explicit market/model/performance buttons remain available.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import time
from typing import Mapping
from urllib.parse import urlparse

from . import webapp as base
from .v59_fast_realtime import (
    realtime_status_v59,
    start_realtime_stream_v59,
    stop_realtime_stream_v59,
)
from .v59_market_stream import (
    market_realtime_status_v59,
    start_market_realtime_v59,
    stop_market_realtime_v59,
)
from .v59_model_cache import cache_status_v59

V59_WEB_VERSION = "V59_FAST_REALTIME_WEB"


def _combined_realtime(*, include_portfolio: bool = True) -> dict[str, object]:
    private = realtime_status_v59(include_portfolio=include_portfolio)
    market = market_realtime_status_v59()
    return {
        "status": "SUCCESS",
        "version": V59_WEB_VERSION,
        "private": private,
        "market": market,
        "portfolio": private.get("portfolio") if include_portfolio else None,
        "model_cache": cache_status_v59(),
        "automatic_live_orders_allowed": False,
        "live_market_prices_are_display_only": True,
        "official_valuation_source": "LOCAL_FINAL_EOD_CLOSE_ONLY",
    }


def _sync_broker_fast() -> dict[str, object]:
    started = time.perf_counter()
    result = dict(base.sync_broker_portfolio())
    result["interactive_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    result["performance_refresh_deferred"] = True
    result["performance_refresh_reason"] = "V59_INTERACTIVE_LATENCY"
    try:
        start_realtime_stream_v59()
    except Exception as exc:
        result["private_stream_start_error"] = f"{type(exc).__name__}:{exc}"
    try:
        start_market_realtime_v59(force_restart=True)
    except Exception as exc:
        result["market_stream_start_error"] = f"{type(exc).__name__}:{exc}"
    result["realtime"] = _combined_realtime(include_portfolio=False)
    return result


def _select_broker_fast(selection_token: str) -> dict[str, object]:
    selection = base.select_broker_account(selection_token)
    result = _sync_broker_fast()
    result["selection"] = selection
    return result


def _plan_fast(
    *,
    new_capital_vnd: float,
    maximum_buy_orders: int | None,
    trigger_type: str | None,
    note: str | None,
) -> dict[str, object]:
    """Create a plan from current local market state + fresh selected-account REST.

    Deep OHLC reconciliation is intentionally not implicit. The explicit market
    sync/model buttons own network-heavy data refresh. The plan records the
    exact local freshness status it used.
    """
    started = time.perf_counter()
    broker_sync = _sync_broker_fast()
    market_state = base.market_source_integrity_status()
    result = dict(
        base.create_capital_plan(
            new_capital_vnd=new_capital_vnd,
            maximum_buy_orders=maximum_buy_orders,
            trigger_type=trigger_type,
            note=note,
        )
    )
    result["preflight"] = {
        "market_sync": {
            "status": "SKIPPED_INTERACTIVE_FAST_PATH",
            "reason": "USE_EXPLICIT_MARKET_SYNC_FOR_NETWORK_RECONCILIATION",
            "source_integrity": market_state,
        },
        "broker_snapshot_id": broker_sync.get("snapshot_id"),
        "broker_captured_at": broker_sync.get("captured_at"),
        "broker_rest_timings_ms": broker_sync.get("rest_timings_ms"),
        "signals": base.signal_refresh_status(),
        "model_cache": cache_status_v59(),
        "performance_refresh_deferred": True,
    }
    result["interactive_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return result


# Existing Handler resolves these module globals at request time.
base._sync_broker_and_refresh = _sync_broker_fast
base._select_broker_and_refresh = _select_broker_fast
base._plan_and_refresh = _plan_fast


class Handler(base.Handler):
    server_version = "VNQuantLocal/5.9"

    def _root_with_v59_assets(self) -> None:
        target = base.WEB_ROOT / "index.html"
        html = target.read_text(encoding="utf-8")
        html = html.replace(
            "</head>",
            '  <link rel="stylesheet" href="/realtime_v59.css">\n</head>',
        )
        html = html.replace(
            "</body>",
            '  <script src="/realtime_v59.js"></script>\n</body>',
        )
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._root_with_v59_assets()
                return
            if path in {"/realtime_v59.js", "/realtime_v59.css"}:
                self._static(path.lstrip("/"))
                return
            if path == "/api/realtime":
                self._send_json(_combined_realtime(include_portfolio=True))
                return
            if path == "/api/realtime/status":
                self._send_json(_combined_realtime(include_portfolio=False))
                return
            super().do_GET()
        except Exception as exc:
            self._send_json(base._friendly_error(exc), 500)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/actions/realtime-start":
                private = start_realtime_stream_v59()
                market = start_market_realtime_v59(force_restart=True)
                self._send_json(
                    {
                        "status": "SUCCESS",
                        "private": private,
                        "market": market,
                        "automatic_live_orders_allowed": False,
                    }
                )
                return
            if path == "/api/actions/realtime-stop":
                market = stop_market_realtime_v59()
                private = stop_realtime_stream_v59()
                self._send_json(
                    {"status": "SUCCESS", "private": private, "market": market}
                )
                return
            super().do_POST()
        except Exception as exc:
            self._send_json(base._friendly_error(exc), 500)


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Workstation chỉ được bind localhost")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"VN Quant Local Workstation V59: http://{host}:{port}")
    print("DNSE realtime là read-only; định giá chính thức vẫn dùng final EOD.")
    print("Nhấn Ctrl+C để dừng.")
    try:
        try:
            start_realtime_stream_v59()
        except Exception as exc:
            print(f"[v59] private realtime chưa khởi động: {type(exc).__name__}:{exc}")
        try:
            start_market_realtime_v59()
        except Exception as exc:
            print(f"[v59] market realtime chưa khởi động: {type(exc).__name__}:{exc}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            stop_market_realtime_v59()
        except Exception:
            pass
        try:
            stop_realtime_stream_v59()
        except Exception:
            pass
        server.server_close()


if __name__ == "__main__":
    run()
