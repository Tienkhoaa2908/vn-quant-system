"""Read-only bridge from the V86 realtime sidecar state into web :8787."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

STATE_RELATIVE = Path("data/state/dnse_realtime_v86.json")
MAX_STATE_AGE_SEC = 12.0


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def read_v86_realtime_status(system_root: Path) -> dict[str, object]:
    path = Path(system_root).resolve() / STATE_RELATIVE
    if not path.is_file():
        return {
            "version": "V86_DNSE_OPENAPI_REALTIME_BRIDGE",
            "status": "NOT_INSTALLED_OR_NOT_STARTED",
            "state_file_present": False,
            "sidecar_state_age_sec": None,
            "process_alive": False,
            "transport_connected": False,
            "authenticated": False,
            "subscriptions_active": False,
            "heartbeat_healthy": False,
            "live_order_ready": False,
            "message": "V86 sidecar chưa tạo state. Chạy sidecar riêng; web 8787 không tự khởi động legacy stream.",
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "version": "V86_DNSE_OPENAPI_REALTIME_BRIDGE",
            "status": "STATE_INVALID",
            "state_file_present": True,
            "live_order_ready": False,
            "error": f"{type(exc).__name__}:{exc}",
        }
    if not isinstance(raw, Mapping):
        return {
            "version": "V86_DNSE_OPENAPI_REALTIME_BRIDGE",
            "status": "STATE_INVALID",
            "state_file_present": True,
            "live_order_ready": False,
        }

    result = dict(raw)
    result["bridge_version"] = "V86_DNSE_OPENAPI_REALTIME_BRIDGE"
    result["state_file_present"] = True
    result["state_path"] = str(path)
    updated = _parse_time(raw.get("updated_at"))
    age = None
    if updated is not None:
        age = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds())
    result["sidecar_state_age_sec"] = round(age, 3) if age is not None else None

    process_claimed = bool(raw.get("process_alive"))
    if process_claimed and (age is None or age > MAX_STATE_AGE_SEC):
        result["status"] = "DEGRADED_STALE_PROCESS_STATE"
        result["process_alive"] = False
        result["transport_connected"] = False
        result["authenticated"] = False
        result["subscriptions_active"] = False
        result["heartbeat_healthy"] = False
        result["message"] = "State sidecar đã quá cũ; không được coi HTTP 200 là realtime khỏe."
    elif str(result.get("status") or "").startswith("HEALTHY"):
        result["message"] = "OpenAPI sidecar khỏe; web chỉ đọc state, không sở hữu WebSocket."
    elif result.get("status") == "IDLE_MARKET_CLOSED":
        result["message"] = "Sidecar kết nối/auth khỏe; ngoài cửa sổ thị trường nên tick freshness không dùng làm lỗi."
    else:
        result.setdefault("message", "Realtime chưa đạt HEALTHY; mọi live-order authority vẫn bị khóa.")

    result["live_order_ready"] = False
    result["trading_token_requested"] = False
    result["orders_sent"] = False
    return result
