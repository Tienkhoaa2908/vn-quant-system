"""V59 process-local C3 caches and cheap freshness checks.

The immutable reference archive and 11-year market structures were previously
parsed repeatedly during a single plan request. V59 caches them by file stat and
uses small SQL queries to decide whether canonical/preview work is already
current. Cache invalidation is automatic when the underlying file size/mtime
changes.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import threading
from typing import Callable

from . import c3_model, signal_refresh, weekly_plan, capital_plan
from .core import paths, state_db

V59_MODEL_CACHE_VERSION = "V59_C3_PROCESS_CACHE"

_LOCK = threading.RLock()
_HIST_KEY: tuple[str, int, int] | None = None
_HIST_VALUE = None
_MARKET_KEY: tuple[str, int, int] | None = None
_MARKET_VALUE = None
_REVIEW_KEY: tuple[int, tuple[str, int, int]] | None = None
_REVIEW_VALUE = None

_ORIGINAL_LOAD_HISTORICAL: Callable | None = None
_ORIGINAL_MARKET_ROWS: Callable | None = None
_ORIGINAL_ENSURE_CANONICAL: Callable | None = None
_ORIGINAL_REFRESH_PREVIEW: Callable | None = None
_ORIGINAL_REVIEW: Callable | None = None


def _file_key(path: Path) -> tuple[str, int, int]:
    stat = Path(path).stat()
    return (str(Path(path).resolve()), int(stat.st_size), int(stat.st_mtime_ns))


def load_historical_rows_cached(path: Path):
    global _HIST_KEY, _HIST_VALUE
    assert _ORIGINAL_LOAD_HISTORICAL is not None
    key = _file_key(Path(path))
    with _LOCK:
        if _HIST_KEY == key and _HIST_VALUE is not None:
            return _HIST_VALUE
    value = _ORIGINAL_LOAD_HISTORICAL(Path(path))
    with _LOCK:
        _HIST_KEY = key
        _HIST_VALUE = value
    return value


def market_rows_cached(path: Path):
    global _MARKET_KEY, _MARKET_VALUE
    assert _ORIGINAL_MARKET_ROWS is not None
    key = _file_key(Path(path))
    with _LOCK:
        if _MARKET_KEY == key and _MARKET_VALUE is not None:
            return _MARKET_VALUE
    value = _ORIGINAL_MARKET_ROWS(Path(path))
    with _LOCK:
        _MARKET_KEY = key
        _MARKET_VALUE = value
    return value


def _market_signal_days_fast() -> tuple[str, str]:
    market_db = paths().market_db
    with sqlite3.connect(market_db) as db:
        rows = db.execute(
            """
            SELECT substr(day,1,7) month_key,MAX(day) last_day
            FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
            GROUP BY substr(day,1,7)
            ORDER BY month_key DESC
            LIMIT 2
            """
        ).fetchall()
    if len(rows) < 2:
        raise ValueError("V59_MARKET_REQUIRES_TWO_MONTHS")
    latest_day = str(rows[0][1])
    canonical_day = str(rows[1][1])
    return canonical_day, latest_day


def _stored_canonical_day() -> tuple[str | None, str | None]:
    with state_db() as db:
        row = db.execute(
            """
            SELECT r.run_id,k.signal_day
            FROM runs r JOIN rankings k ON k.run_id=r.run_id
            WHERE r.status='SUCCESS' AND k.signal_kind='MONTHLY_CANONICAL'
            ORDER BY k.signal_day DESC,r.finished_at DESC LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None, None
    return str(row["signal_day"]), str(row["run_id"])


def ensure_canonical_current_v59() -> dict[str, object]:
    assert _ORIGINAL_ENSURE_CANONICAL is not None
    expected, market_day = _market_signal_days_fast()
    stored, run_id = _stored_canonical_day()
    if stored == expected:
        return {
            "status": "ALREADY_CURRENT",
            "canonical": {
                "status": "READY",
                "expected_signal_day": expected,
                "stored_signal_day": stored,
                "market_day": market_day,
                "current": True,
                "run_id": run_id,
                "fast_path": True,
                "version": V59_MODEL_CACHE_VERSION,
            },
        }
    return _ORIGINAL_ENSURE_CANONICAL()


def refresh_latest_preview_v59() -> dict[str, object]:
    assert _ORIGINAL_REFRESH_PREVIEW is not None
    expected, market_day = _market_signal_days_fast()
    latest = signal_refresh.latest_preview_snapshot()
    if (
        latest is not None
        and str(latest.get("market_day") or "") == market_day
        and str(latest.get("canonical_signal_day") or "") == expected
    ):
        result = dict(latest)
        result["status"] = "ALREADY_CURRENT"
        result["fast_path"] = True
        result["version"] = V59_MODEL_CACHE_VERSION
        result["canonical_refresh"] = ensure_canonical_current_v59()
        return result
    return _ORIGINAL_REFRESH_PREVIEW()


def historical_review_cached(*, count: int = 3):
    global _REVIEW_KEY, _REVIEW_VALUE
    assert _ORIGINAL_REVIEW is not None
    key = (int(count), _file_key(paths().market_db))
    with _LOCK:
        if _REVIEW_KEY == key and _REVIEW_VALUE is not None:
            return _REVIEW_VALUE
    value = _ORIGINAL_REVIEW(count=count)
    with _LOCK:
        _REVIEW_KEY = key
        _REVIEW_VALUE = value
    return value


def cache_status_v59() -> dict[str, object]:
    with _LOCK:
        return {
            "version": V59_MODEL_CACHE_VERSION,
            "historical_cached": _HIST_VALUE is not None,
            "market_rows_cached": _MARKET_VALUE is not None,
            "sell_review_cached": _REVIEW_VALUE is not None,
        }


def apply() -> None:
    if getattr(signal_refresh, "_v59_model_cache_applied", False):
        return
    global _ORIGINAL_LOAD_HISTORICAL, _ORIGINAL_MARKET_ROWS
    global _ORIGINAL_ENSURE_CANONICAL, _ORIGINAL_REFRESH_PREVIEW, _ORIGINAL_REVIEW

    _ORIGINAL_LOAD_HISTORICAL = c3_model.load_historical_rows
    _ORIGINAL_MARKET_ROWS = c3_model._market_rows
    _ORIGINAL_ENSURE_CANONICAL = signal_refresh.ensure_canonical_current
    _ORIGINAL_REFRESH_PREVIEW = signal_refresh.refresh_latest_preview
    _ORIGINAL_REVIEW = weekly_plan._historical_monthly_review_snapshots

    c3_model.load_historical_rows = load_historical_rows_cached
    c3_model._market_rows = market_rows_cached
    signal_refresh.load_historical_rows = load_historical_rows_cached
    signal_refresh._market_rows = market_rows_cached
    signal_refresh.ensure_canonical_current = ensure_canonical_current_v59
    signal_refresh.refresh_latest_preview = refresh_latest_preview_v59

    weekly_plan.load_historical_rows = load_historical_rows_cached
    weekly_plan._market_rows = market_rows_cached
    weekly_plan._historical_monthly_review_snapshots = historical_review_cached

    capital_plan.ensure_canonical_current = ensure_canonical_current_v59
    capital_plan.refresh_latest_preview = refresh_latest_preview_v59

    signal_refresh.V59_MODEL_CACHE_VERSION = V59_MODEL_CACHE_VERSION
    signal_refresh.cache_status_v59 = cache_status_v59
    signal_refresh._v59_model_cache_applied = True
