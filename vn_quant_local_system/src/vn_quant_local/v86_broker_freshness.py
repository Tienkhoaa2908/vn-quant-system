"""V86 broker-state freshness guard for the approved local workstation.

This layer is deliberately read-only. It keeps V55 final-EOD valuation semantics,
does not introduce broker order mutations, and wraps the final V59 selected-account
REST reconcile with explicit freshness/error state.

The key safety behavior is fail-closed during market hours when a previously
non-empty portfolio suddenly reads as empty. The last completed broker snapshot
remains available instead of silently replacing operational holdings with an
ambiguous empty response. A genuine transition to zero positions can be accepted
after the market-hours guard no longer applies or by a later deliberately designed
reconciliation flow.
"""
from __future__ import annotations

from datetime import date, datetime, time
import json
import os
from pathlib import Path
from typing import Callable, Mapping

from . import broker_portfolio, core
from . import source_integrity_v49 as v49
from . import v59_fast_realtime as v59

V86_BROKER_FRESHNESS_VERSION = "V86_BROKER_STATE_FRESHNESS_GUARD"
HEALTH_PATH = core.SYSTEM_ROOT / "data" / "state" / "broker_sync_health_v86.json"
MARKET_GUARD_START = time(8, 45)
MARKET_GUARD_END = time(15, 30)
HOLDINGS_CAPTURE_STALE_SEC = 15 * 60
ABSOLUTE_EOD_STALE_DAYS = 4

_ORIGINAL_READ_SELECTED: Callable | None = None
_ORIGINAL_SYNC: Callable | None = None
_ORIGINAL_STATUS: Callable | None = None


def _now_vn() -> datetime:
    return datetime.now(v49.VN_TZ)


def _market_guard_window(now_vn: datetime | None = None) -> bool:
    current = (now_vn or _now_vn()).astimezone(v49.VN_TZ)
    if current.weekday() >= 5:
        return False
    return MARKET_GUARD_START <= current.time().replace(tzinfo=None) <= MARKET_GUARD_END


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    os.replace(temporary, target)


def _read_health(path: Path | None = None) -> dict[str, object]:
    target = Path(path or HEALTH_PATH)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "version": V86_BROKER_FRESHNESS_VERSION,
            "status": "NOT_YET_OBSERVED",
        }
    return value if isinstance(value, dict) else {
        "version": V86_BROKER_FRESHNESS_VERSION,
        "status": "STATE_INVALID",
    }


def _write_health(payload: Mapping[str, object]) -> None:
    value = {
        "version": V86_BROKER_FRESHNESS_VERSION,
        "read_only": True,
        "automatic_live_orders_allowed": False,
        **dict(payload),
    }
    _atomic_json(HEALTH_PATH, value)


def _safe_error_code(exc: BaseException) -> str:
    text = str(exc)
    known = (
        "DNSE_POSITIONS_EMPTY_DURING_MARKET_HOURS_PRESERVE_LAST_GOOD",
        "DNSE_ACCOUNT_READ_FAILED",
        "DNSE_ACCOUNT_SELECTION_REQUIRED",
        "DNSE_ACCOUNT_SELECTION_INVALID",
        "DNSE_CREDENTIALS_MISSING",
        "DNSE_SDK_NOT_INSTALLED",
        "DNSE_SDK_VERSION_MISMATCH",
        "V55_FINAL_EOD_VALUATION_INCOMPLETE",
    )
    for code in known:
        if code in text:
            return code
    return type(exc).__name__


def _latest_raw_snapshot() -> dict[str, object] | None:
    try:
        return v49.latest_broker_portfolio_v49()
    except Exception:
        return None


def _validate_selected_account(
    selected: Mapping[str, object],
    *,
    previous_position_count: int,
    now_vn: datetime | None = None,
) -> dict[str, object]:
    value = dict(selected)
    raw_count = max(int(value.get("raw_position_count") or 0), 0)
    open_count = max(int(value.get("open_position_count") or 0), 0)

    if previous_position_count > 0 and open_count == 0 and _market_guard_window(now_vn):
        raise ValueError(
            "DNSE_POSITIONS_EMPTY_DURING_MARKET_HOURS_PRESERVE_LAST_GOOD:"
            f"previous={previous_position_count}:raw={raw_count}:open={open_count}"
        )
    return value


def _read_selected_account_v86(reader) -> dict[str, object]:
    assert _ORIGINAL_READ_SELECTED is not None
    selected = _ORIGINAL_READ_SELECTED(reader)
    previous = _latest_raw_snapshot() or {}
    previous_count = max(int(previous.get("position_count") or 0), 0)
    return _validate_selected_account(
        selected,
        previous_position_count=previous_count,
    )


def _parse_iso_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=v49.VN_TZ)
    return parsed.astimezone(v49.VN_TZ)


def _parse_iso_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def broker_freshness_summary(
    latest: Mapping[str, object] | None,
    health: Mapping[str, object] | None,
    *,
    now_vn: datetime | None = None,
) -> dict[str, object]:
    current = (now_vn or _now_vn()).astimezone(v49.VN_TZ)
    snapshot = dict(latest or {})
    sync_health = dict(health or {})
    captured = _parse_iso_datetime(snapshot.get("captured_at"))
    valuation_day = _parse_iso_date(snapshot.get("market_day"))
    capture_age = (
        max((current - captured).total_seconds(), 0.0)
        if captured is not None
        else None
    )
    valuation_age_days = (
        max((current.date() - valuation_day).days, 0)
        if valuation_day is not None
        else None
    )
    flags: list[str] = []
    if snapshot and _market_guard_window(current):
        if capture_age is None or capture_age > HOLDINGS_CAPTURE_STALE_SEC:
            flags.append("HOLDINGS_CAPTURE_STALE_DURING_MARKET_HOURS")
    if valuation_age_days is None or valuation_age_days > ABSOLUTE_EOD_STALE_DAYS:
        flags.append("EOD_VALUATION_ABSOLUTELY_STALE")
    if str(sync_health.get("status") or "").startswith("FAILED"):
        flags.append("LAST_BROKER_SYNC_FAILED")
    if not snapshot:
        flags.append("NO_BROKER_SNAPSHOT")

    return {
        "version": V86_BROKER_FRESHNESS_VERSION,
        "status": "READY" if not flags else "DEGRADED",
        "flags": flags,
        "holdings_captured_at": snapshot.get("captured_at"),
        "holdings_capture_age_sec": round(capture_age, 1) if capture_age is not None else None,
        "valuation_market_day": snapshot.get("market_day"),
        "valuation_age_calendar_days": valuation_age_days,
        "position_count": snapshot.get("position_count"),
        "market_guard_window": _market_guard_window(current),
        "market_guard_source": "LOCAL_CLOCK_APPROX_NOT_EXCHANGE_CALENDAR",
        "absolute_eod_stale_days": ABSOLUTE_EOD_STALE_DAYS,
        "holdings_capture_stale_sec": HOLDINGS_CAPTURE_STALE_SEC,
        "last_sync_status": sync_health.get("status"),
        "last_sync_attempted_at": sync_health.get("attempted_at"),
        "official_valuation_remains_v55_final_eod_only": True,
        "automatic_live_orders_allowed": False,
    }


def _sync_broker_portfolio_v86() -> dict[str, object]:
    assert _ORIGINAL_SYNC is not None
    previous = _latest_raw_snapshot() or {}
    attempted_at = core.utc_now()
    _write_health(
        {
            "status": "SYNCING",
            "attempted_at": attempted_at,
            "previous_snapshot_id": previous.get("snapshot_id"),
            "previous_position_count": previous.get("position_count"),
        }
    )
    try:
        result = dict(_ORIGINAL_SYNC())
    except Exception as exc:
        _write_health(
            {
                "status": "FAILED",
                "attempted_at": attempted_at,
                "failed_at": core.utc_now(),
                "error_code": _safe_error_code(exc),
                "previous_snapshot_id": previous.get("snapshot_id"),
                "previous_captured_at": previous.get("captured_at"),
                "previous_position_count": previous.get("position_count"),
                "last_good_snapshot_should_remain_preferred": True,
            }
        )
        raise

    _write_health(
        {
            "status": "SUCCESS",
            "attempted_at": attempted_at,
            "completed_at": core.utc_now(),
            "snapshot_id": result.get("snapshot_id"),
            "captured_at": result.get("captured_at"),
            "position_count": result.get("position_count"),
            "valuation_market_day": result.get("market_day"),
            "rest_timings_ms": result.get("rest_timings_ms"),
        }
    )
    return result


def _workstation_status_v86() -> dict[str, object]:
    assert _ORIGINAL_STATUS is not None
    value = dict(_ORIGINAL_STATUS())
    health = _read_health()
    latest = None
    try:
        latest = broker_portfolio.latest_broker_portfolio()
    except Exception:
        latest = _latest_raw_snapshot()
    value["broker_sync_health_v86"] = health
    value["broker_freshness_v86"] = broker_freshness_summary(latest, health)
    return value


def apply() -> None:
    if getattr(broker_portfolio, "_v86_broker_freshness_applied", False):
        return
    global _ORIGINAL_READ_SELECTED, _ORIGINAL_SYNC, _ORIGINAL_STATUS
    _ORIGINAL_READ_SELECTED = v59._read_selected_account
    _ORIGINAL_SYNC = broker_portfolio.sync_broker_portfolio
    _ORIGINAL_STATUS = core.workstation_status

    v59._read_selected_account = _read_selected_account_v86
    broker_portfolio.sync_broker_portfolio = _sync_broker_portfolio_v86
    core.workstation_status = _workstation_status_v86

    broker_portfolio.broker_sync_health_v86 = _read_health
    broker_portfolio.broker_freshness_summary_v86 = broker_freshness_summary
    broker_portfolio.V86_BROKER_FRESHNESS_VERSION = V86_BROKER_FRESHNESS_VERSION
    broker_portfolio._v86_broker_freshness_applied = True
