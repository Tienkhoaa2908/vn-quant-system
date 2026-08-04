"""Zero-dependency localhost web UI cho VN Quant Local Workstation."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Callable, Mapping
from urllib.parse import parse_qs, urlparse

from .broker_portfolio import latest_broker_portfolio, sync_broker_portfolio
from .capital_plan import (
    capital_plan_history,
    create_capital_plan,
    latest_capital_plan,
)
from .core import (
    SYSTEM_ROOT,
    account_snapshot,
    bootstrap_local_data,
    replace_account,
    workstation_status,
)
from .data_sources import (
    clear_credentials,
    credential_status,
    import_manual_csv,
    install_dnse_sdk,
    save_credentials,
    sync_incremental_market_data_local,
    test_dnse_connection,
)
from .market_overview import market_overview
from .performance import (
    add_actual_cashflow,
    add_actual_fill,
    performance_status,
    refresh_performance,
    start_observatory,
)
from .signal_refresh import (
    ensure_canonical_current,
    refresh_latest_preview,
    signal_refresh_status,
)

WEB_ROOT = SYSTEM_ROOT / "web"
MAX_JSON_BODY_BYTES = 20 * 1024 * 1024


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _friendly_error(exc: Exception) -> dict[str, object]:
    technical = f"{type(exc).__name__}:{exc}"
    text = str(exc)
    if "DNSE_CREDENTIALS_MISSING" in text:
        message = "Chưa có đủ DNSE API Key và API Secret. Nhập lại trong tab Dữ liệu."
    elif "DNSE_TIMEZONE_DATA_MISSING" in text or "No time zone found" in text:
        message = "Windows Python đang thiếu dữ liệu múi giờ. Bấm 'Cài/Sửa DNSE runtime' rồi thử lại."
    elif "DNSE_SDK_NOT_INSTALLED" in text:
        message = "Môi trường local chưa có DNSE SDK 0.5.0. Bấm 'Cài/Sửa DNSE runtime'."
    elif "DNSE_SDK_VERSION_MISMATCH" in text:
        message = "Phiên bản DNSE SDK không đúng 0.5.0. Bấm 'Cài/Sửa DNSE runtime'."
    elif "DNSE_RUNTIME_INSTALL" in text:
        message = "Không cài được DNSE SDK hoặc tzdata. Kiểm tra Internet rồi thử lại."
    elif "DNSE_ACCOUNT_LIST_EMPTY" in text:
        message = "DNSE xác thực được nhưng danh sách tiểu khoản không có mã định danh hợp lệ."
    elif "DNSE_ACCOUNT_READ_FAILED" in text:
        message = "DNSE trả danh sách tiểu khoản nhưng không đọc được số dư hoặc vị thế. Kiểm tra quyền đọc tài khoản của API Key."
    elif "DNSE" in text and (
        "401" in text or "403" in text or "AUTH" in text.upper()
    ):
        message = "DNSE từ chối xác thực hoặc API key chưa có quyền đọc tài khoản/danh mục."
    elif "MANUAL_CSV" in text:
        message = "CSV thủ công không hợp lệ hoặc xung đột với dữ liệu đã có."
    elif "CANONICAL_REFRESH_FAILED" in text:
        message = "Không tạo được canonical của tháng hoàn tất mới nhất. Kiểm tra dữ liệu giá rồi thử lại."
    elif "PREVIEW" in text:
        message = "Không tính được latest preview. Kiểm tra dữ liệu phiên mới nhất và lịch sử 250 phiên."
    elif "MONTHLY_SIGNAL_MISMATCH" in text:
        message = "Canonical và lịch sử sell-review không đồng nhất. Cập nhật đánh giá thị trường rồi tạo lại kế hoạch."
    elif "MONTHLY_CANONICAL" in text:
        message = "Chưa có ranking canonical tháng. Cập nhật đánh giá thị trường trước."
    elif "CAPITAL_PLAN_TRIGGER_INVALID" in text:
        message = "Loại sự kiện tạo kế hoạch vốn không hợp lệ."
    elif "PERFORMANCE_ALREADY_STARTED" in text:
        message = "Observatory đã được khởi tạo. Snapshot mở đầu là bất biến."
    elif "PERFORMANCE_REQUIRES_BROKER_SNAPSHOT" in text:
        message = "Cần đồng bộ danh mục DNSE trước khi bắt đầu theo dõi hiệu quả."
    elif "PERFORMANCE_NOT_STARTED" in text:
        message = "Chưa khởi tạo tab Hiệu quả."
    elif "PERFORMANCE" in text:
        message = "Dữ liệu nhập cho Observatory không hợp lệ hoặc chưa đầy đủ."
    else:
        message = text or "Thao tác thất bại."
    return {"status": "FAILED", "message": message, "error": technical}


def _sync_broker_and_refresh() -> dict[str, object]:
    result = sync_broker_portfolio()
    status = performance_status()
    if status.get("status") == "ACTIVE":
        refresh_performance()
    return result


def _refresh_market_signals() -> dict[str, object]:
    market_sync = sync_incremental_market_data_local()
    canonical = ensure_canonical_current()
    preview = refresh_latest_preview()
    return {
        "status": "SUCCESS",
        "message": "Đã đồng bộ dữ liệu và cập nhật latest preview.",
        "market_sync": market_sync,
        "canonical": canonical,
        "preview": {
            key: preview.get(key)
            for key in (
                "status",
                "snapshot_id",
                "created_at",
                "market_day",
                "canonical_signal_day",
                "market_risk_on",
            )
        },
    }


def _refresh_canonical() -> dict[str, object]:
    market_sync = sync_incremental_market_data_local()
    canonical = ensure_canonical_current()
    preview = refresh_latest_preview()
    return {
        "status": "SUCCESS",
        "message": (
            "Canonical đã cập nhật và preview đã được tính lại."
            if canonical.get("status") == "REFRESHED"
            else "Canonical đã đúng tháng hoàn tất mới nhất; preview đã được làm mới."
        ),
        "market_sync": market_sync,
        "canonical": canonical,
        "preview_snapshot_id": preview.get("snapshot_id"),
        "preview_market_day": preview.get("market_day"),
    }


def _plan_and_refresh(
    *,
    new_capital_vnd: float,
    maximum_buy_orders: int | None,
    trigger_type: str | None,
    note: str | None,
) -> dict[str, object]:
    # Fail closed: kế hoạch mới phải dùng dữ liệu giá và broker snapshot vừa được
    # đồng bộ, sau đó capital_plan tự khóa canonical + preview snapshot.
    market_sync = sync_incremental_market_data_local()
    broker_sync = sync_broker_portfolio()
    result = create_capital_plan(
        new_capital_vnd=new_capital_vnd,
        maximum_buy_orders=maximum_buy_orders,
        trigger_type=trigger_type,
        note=note,
    )
    result["preflight"] = {
        "market_sync": market_sync,
        "broker_snapshot_id": broker_sync.get("snapshot_id"),
        "broker_captured_at": broker_sync.get("captured_at"),
        "signals": signal_refresh_status(),
    }
    status = performance_status()
    if status.get("status") == "ACTIVE":
        refresh_performance()
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "VNQuantLocal/1.8"

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, value: object, status: int = 200) -> None:
        self._send(status, _json_bytes(value), "application/json; charset=utf-8")

    def _read_json(self) -> object:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > MAX_JSON_BODY_BYTES:
            raise ValueError("REQUEST_BODY_TOO_LARGE")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _static(self, relative: str) -> None:
        target = (WEB_ROOT / relative).resolve()
        root = WEB_ROOT.resolve()
        if root not in target.parents and target != root:
            self._send_json({"error": "invalid path"}, 400)
            return
        if not target.is_file():
            self._send_json({"error": "not found"}, 404)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), content_type)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/":
                self._static("index.html")
            elif path in {
                "/app.js",
                "/styles.css",
                "/sell_review_v44_5.js",
                "/sell_review_v44_5.css",
                "/performance_v45.js",
                "/performance_v45.css",
                "/planning_v46.js",
                "/planning_v46.css",
                "/signal_v47.js",
                "/signal_v47.css",
            }:
                self._static(path.lstrip("/"))
            elif path == "/api/status":
                value = workstation_status()
                latest = latest_capital_plan()
                value["latest_capital_plan"] = latest
                value["latest_weekly_plan"] = latest
                value["data_source"] = credential_status()
                value["broker_portfolio"] = latest_broker_portfolio()
                value["signal_refresh"] = signal_refresh_status()
                self._send_json(value)
            elif path == "/api/data-source":
                self._send_json(credential_status())
            elif path == "/api/broker":
                self._send_json(latest_broker_portfolio() or {})
            elif path == "/api/account":
                self._send_json(account_snapshot())
            elif path == "/api/plan/latest":
                self._send_json(latest_capital_plan() or {})
            elif path == "/api/plans":
                limit = int((query.get("limit") or ["50"])[0])
                self._send_json({"plans": capital_plan_history(limit)})
            elif path == "/api/market-overview":
                limit = int((query.get("limit") or ["30"])[0])
                self._send_json(market_overview(limit))
            elif path == "/api/signal-status":
                self._send_json(signal_refresh_status())
            elif path == "/api/performance":
                self._send_json(performance_status())
            elif path == "/api/docs":
                docs = []
                for file in sorted((SYSTEM_ROOT / "docs").glob("*.md")):
                    docs.append(
                        {
                            "name": file.name,
                            "content": file.read_text(encoding="utf-8"),
                        }
                    )
                self._send_json({"documents": docs})
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:
            self._send_json(_friendly_error(exc), 500)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if not isinstance(body, Mapping):
                body = {}
            actions: dict[str, Callable[[], object]] = {
                "/api/actions/bootstrap": lambda: bootstrap_local_data(
                    overwrite=bool(body.get("overwrite", False))
                ),
                "/api/actions/sync": sync_incremental_market_data_local,
                "/api/actions/sync-broker": _sync_broker_and_refresh,
                "/api/actions/model": _refresh_market_signals,
                "/api/actions/market-refresh": _refresh_market_signals,
                "/api/actions/canonical": _refresh_canonical,
                "/api/actions/plan": lambda: _plan_and_refresh(
                    new_capital_vnd=float(
                        body.get("new_capital_vnd")
                        if body.get("new_capital_vnd") not in (None, "")
                        else body.get("weekly_budget_vnd") or 0.0
                    ),
                    maximum_buy_orders=(
                        int(body["maximum_buy_orders"])
                        if body.get("maximum_buy_orders") not in (None, "")
                        else None
                    ),
                    trigger_type=str(body.get("trigger_type") or "") or None,
                    note=str(body.get("note") or "") or None,
                ),
                "/api/data-source/test": test_dnse_connection,
                "/api/data-source/install-sdk": install_dnse_sdk,
                "/api/data-source/clear": clear_credentials,
                "/api/performance/refresh": refresh_performance,
            }
            if path in actions:
                self._send_json(actions[path]())
            elif path == "/api/performance/start":
                classifications = body.get("classifications", {})
                if not isinstance(classifications, Mapping):
                    raise ValueError("PERFORMANCE_CLASSIFICATIONS_INVALID")
                self._send_json(
                    start_observatory(
                        classifications={
                            str(key): str(value)
                            for key, value in classifications.items()
                        },
                        start_day=(
                            str(body.get("start_day"))
                            if body.get("start_day")
                            else None
                        ),
                        opening_model_cash_vnd=(
                            float(body["opening_model_cash_vnd"])
                            if body.get("opening_model_cash_vnd") not in (None, "")
                            else None
                        ),
                    )
                )
            elif path == "/api/performance/cashflow":
                self._send_json(
                    add_actual_cashflow(
                        flow_type=str(body.get("flow_type") or ""),
                        amount_vnd=float(body.get("amount_vnd") or 0.0),
                        event_day=str(body.get("event_day") or ""),
                        note=str(body.get("note") or "") or None,
                    )
                )
            elif path == "/api/performance/fill":
                self._send_json(
                    add_actual_fill(
                        side=str(body.get("side") or ""),
                        symbol=str(body.get("symbol") or ""),
                        quantity=int(body.get("quantity") or 0),
                        price_vnd=float(body.get("price_vnd") or 0.0),
                        event_day=str(body.get("event_day") or ""),
                        fees_vnd=float(body.get("fees_vnd") or 0.0),
                        taxes_vnd=float(body.get("taxes_vnd") or 0.0),
                        plan_id=str(body.get("plan_id") or "") or None,
                        note=str(body.get("note") or "") or None,
                    )
                )
            elif path == "/api/data-source/credentials":
                self._send_json(
                    save_credentials(
                        str(body.get("api_key") or ""),
                        str(body.get("api_secret") or ""),
                    )
                )
            elif path == "/api/data-source/import-csv":
                self._send_json(
                    import_manual_csv(
                        str(body.get("content") or ""),
                        filename=str(
                            body.get("filename") or "manual_ohlcv.csv"
                        ),
                        price_unit=str(
                            body.get("price_unit") or "THOUSAND_VND"
                        ),
                    )
                )
            elif path == "/api/account":
                holdings = body.get("holdings", [])
                if not isinstance(holdings, list):
                    raise ValueError("holdings phải là array")
                self._send_json(
                    replace_account(
                        cash_vnd=float(body.get("cash_vnd", 0.0)),
                        weekly_contribution_vnd=float(
                            body.get(
                                "weekly_contribution_vnd", 250_000.0
                            )
                        ),
                        holdings=holdings,
                    )
                )
            elif path == "/api/account/budget":
                current = account_snapshot()
                self._send_json(
                    replace_account(
                        cash_vnd=float(current["account"]["cash_vnd"]),
                        weekly_contribution_vnd=float(
                            body.get("new_capital_vnd")
                            if body.get("new_capital_vnd") not in (None, "")
                            else body.get("weekly_budget_vnd", 250_000.0)
                        ),
                        holdings=current["holdings"],
                    )
                )
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:
            self._send_json(_friendly_error(exc), 500)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[web] {self.address_string()} - {fmt % args}")


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Workstation chỉ được bind localhost")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"VN Quant Local Workstation: http://{host}:{port}")
    print("Nhấn Ctrl+C để dừng.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
