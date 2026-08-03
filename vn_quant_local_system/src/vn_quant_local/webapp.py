"""Zero-dependency localhost web UI for the workstation.

Server chỉ bind 127.0.0.1. Credentials DNSE được lưu trong data/state local,
không trả secret về browser và không gửi lệnh broker.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Callable, Mapping
from urllib.parse import urlparse

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
        message = "Chưa có DNSE API Key và API Secret. Mở tab Dữ liệu để nhập và lưu local."
    elif "DNSE_SDK_NOT_INSTALLED" in text:
        message = "Môi trường local chưa có DNSE SDK 0.5.0. Bấm 'Cài DNSE SDK' trong tab Dữ liệu."
    elif "DNSE_SDK_VERSION_MISMATCH" in text:
        message = "Phiên bản DNSE SDK không đúng 0.5.0. Cài lại từ tab Dữ liệu."
    elif "DNSE_SDK_INSTALL_FAILED" in text:
        message = "Không cài được DNSE SDK. Kiểm tra Internet rồi thử lại; vẫn có thể nhập CSV thủ công."
    elif "MANUAL_CSV" in text:
        message = "CSV thủ công không hợp lệ hoặc xung đột với dữ liệu đã có. Xem mã lỗi kỹ thuật bên dưới."
    else:
        message = text or "Thao tác thất bại."
    return {
        "status": "FAILED",
        "message": message,
        "error": technical,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "VNQuantLocal/1.1"

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
            elif path == "/api/status":
                value = workstation_status()
                value["latest_weekly_plan"] = latest_weekly_plan()
                value["data_source"] = credential_status()
                self._send_json(value)
            elif path == "/api/data-source":
                self._send_json(credential_status())
            elif path == "/api/account":
                self._send_json(account_snapshot())
            elif path == "/api/plan/latest":
                self._send_json(latest_weekly_plan() or {})
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
                "/api/actions/model": run_model,
                "/api/actions/plan": create_weekly_plan,
                "/api/data-source/test": test_dnse_connection,
                "/api/data-source/install-sdk": install_dnse_sdk,
                "/api/data-source/clear": clear_credentials,
            }
            if path in actions:
                self._send_json(actions[path]())
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
                        filename=str(body.get("filename") or "manual_ohlcv.csv"),
                        price_unit=str(body.get("price_unit") or "THOUSAND_VND"),
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
