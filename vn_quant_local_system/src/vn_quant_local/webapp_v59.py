"""V86 compatibility web runtime on the historical V59 module path.

The approved localhost server still imports ``vn_quant_local.webapp_v59`` for
backward compatibility, but V86 removes all WebSocket ownership from this web
process. Fast REST/account/plan behavior is preserved. Realtime health is read
from the isolated V86 OpenAPI sidecar state only.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import time
from typing import Mapping
from urllib.parse import urlparse

from . import webapp as base
from .v59_model_cache import cache_status_v59
from he_thong_dinh_luong.local_workstation_v86_bridge import read_v86_realtime_status

V86_LEGACY_WS_DISABLED = True
V59_WEB_VERSION = "V86_COMPAT_WEB_NO_LEGACY_WS"


def _realtime_status() -> dict[str, object]:
    value = dict(read_v86_realtime_status(base.SYSTEM_ROOT))
    value["web_runtime"] = V59_WEB_VERSION
    value["web_process_owns_websocket"] = False
    value["legacy_v59_websocket_disabled"] = True
    value["automatic_live_orders_allowed"] = False
    value["live_order_ready"] = False
    return value


def _sync_broker_fast() -> dict[str, object]:
    started = time.perf_counter()
    result = dict(base.sync_broker_portfolio())
    result["interactive_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    result["performance_refresh_deferred"] = True
    result["performance_refresh_reason"] = "V59_INTERACTIVE_LATENCY"
    result["realtime"] = _realtime_status()
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
    """Create a plan from local market state + fresh selected-account REST.

    Deep OHLC reconciliation remains explicit. V86 changes only realtime
    transport ownership; it does not change research, ranking, or plan policy.
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
        "realtime": broker_sync.get("realtime"),
    }
    result["interactive_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return result


# Existing Handler resolves these globals at request time. Keep the proven fast
# REST/account path without granting the web process any realtime transport.
base._sync_broker_and_refresh = _sync_broker_fast
base._select_broker_and_refresh = _select_broker_fast
base._plan_and_refresh = _plan_fast


class Handler(base.Handler):
    server_version = "VNQuantLocal/8.6"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in {"/api/realtime", "/api/realtime/status"}:
                self._send_json(_realtime_status())
                return
            super().do_GET()
        except Exception as exc:
            self._send_json(base._friendly_error(exc), 500)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in {"/api/actions/realtime-start", "/api/actions/realtime-stop"}:
                self._send_json(
                    {
                        "status": "DISABLED_V86_SIDECAR_OWNED",
                        "message": (
                            "Legacy V59 realtime controls are disabled. "
                            "Run the isolated V86 sidecar in its own Git Bash terminal."
                        ),
                        "web_process_owns_websocket": False,
                        "legacy_v59_websocket_disabled": True,
                        "automatic_live_orders_allowed": False,
                        "live_order_ready": False,
                    },
                    409,
                )
                return
            super().do_POST()
        except Exception as exc:
            self._send_json(base._friendly_error(exc), 500)


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Workstation chỉ được bind localhost")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"VN Quant Local Workstation V86 compatibility web: http://{host}:{port}")
    print("Web process không sở hữu WebSocket; realtime do isolated V86 sidecar cung cấp.")
    print("DNSE account/portfolio REST legacy vẫn được giữ nguyên; live order vẫn khóa.")
    print("Nhấn Ctrl+C để dừng web.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
