"""Zero-dependency localhost web UI cho VN Quant Local Workstation."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Callable, Mapping
from urllib.parse import urlparse

from .broker_portfolio import latest_broker_portfolio, sync_broker_portfolio
from .c3_model import run_model
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
from .performance import (
    add_actual_cashflow,
    add_actual_fill,
    performance_status,
    refresh_performance,
    start_observatory,
)
from .weekly_plan import create_weekly_plan, latest_weekly_plan

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
    elif "MONTHLY_SIGNAL_MISMATCH" in text:
        message = "Dữ liệu đã sang tháng canonical mới. Chạy C3 lại rồi tạo kế hoạch tuần."
    elif "MONTHLY_CANONICAL" in text:
        message = "Chưa có ranking tháng. Chạy C3 trước khi lập kế hoạch tuần."
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


def _plan_and_refresh(
    *, weekly_budget_vnd: float | None, maximum_buy_orders: int | None
) -> dict[str, object]:
    result = create_weekly_plan(
        weekly_budget_vnd=weekly_budget_vnd,
        maximum_buy_orders=maximum_buy_orders,
    )
    status = performance_status()
    if status.get("status") == "ACTIVE":
        refresh_performance()
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "VNQuantLocal/1.6"

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
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._static("index.html")
            elif path == "/app.js":
                self._static("app.js")
            elif path == "/styles.css":
                self._static("styles.css")
            elif path == "/sell_review_v44_5.js":
                self._static("sell_review_v44_5.js")
            elif path == "/sell_review_v44_5.css":
                self._static("sell_review_v44_5.css")
            elif path == "/performance_v45.js":
                self._static("performance_v45.js")
            elif path == "/performance_v45.css":
                self._static("performance_v45.css")
            elif path == "/api/status":
                value = workstation_status()
                value["latest_weekly_plan"] = latest_weekly_plan()
                value["data_source"] = credential_status()
                value["broker_portfolio"] = latest_broker_portfolio()
                self._send_json(value)
            elif path == "/api/data-source":
                self._send_json(credential_status())
            elif path == "/api/broker":
                self._send_json(latest_broker_portfolio() or {})
            elif path == "/api/account":
                self._send_json(account_snapshot())
            elif path == "/api/plan/latest":
                self._send_json(latest_weekly_plan() or {})
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
                "/api/actions/model": run_model,
                "/api/actions/plan": lambda: _plan_and_refresh(
                    weekly_budget_vnd=(
                        float(body["weekly_budget_vnd"])
                        if body.get("weekly_budget_vnd") not in (None, "")
                        else None
                    ),
                    maximum_buy_orders=(
                        int(body["maximum_buy_orders"])
                        if body.get("maximum_buy_orders") not in (None, "")
                        else None
                    ),
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
                            body.get("weekly_contribution_vnd", 250_000.0)
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
                            body.get("weekly_budget_vnd", 250_000.0)
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
