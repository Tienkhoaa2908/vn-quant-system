"""V59 safety for DNSE StreamPosition account scope.

DNSE SDK 0.5.0 StreamPosition exposes symbol/qty/avg_price but no account number.
Therefore an unscoped position event may only be overlaid onto the selected
portfolio when the API key exposes exactly one account. With multiple accounts,
unscoped events remain audit diagnostics and never mutate the displayed/planner
selected-account state.
"""
from __future__ import annotations

from typing import Mapping

from . import data_sources
from . import source_integrity_v49 as v49
from . import v59_fast_realtime as v59

V59_STREAM_SAFETY_VERSION = "V59_STREAM_ACCOUNT_SCOPE_FAIL_CLOSED"

_ORIGINAL_START = None
_ORIGINAL_ROWS = None
_SINGLE_ACCOUNT_SCOPE = False
_ACCOUNT_COUNT: int | None = None
_SCOPE_ERROR: str | None = None


def _probe_account_scope() -> tuple[bool, int | None, str | None]:
    reader = None
    try:
        reader, _ = data_sources.reader_from_saved_credentials()
        accounts = list(reader.accounts())
        ids = [v49._account_id(row) for row in accounts if isinstance(row, Mapping)]
        valid = [value for value in ids if value]
        return len(valid) == 1, len(valid), None
    except Exception as exc:
        return False, None, f"{type(exc).__name__}:{exc}"
    finally:
        if reader is not None:
            reader.close()


def start_realtime_stream_safe_v59() -> dict[str, object]:
    global _SINGLE_ACCOUNT_SCOPE, _ACCOUNT_COUNT, _SCOPE_ERROR
    assert _ORIGINAL_START is not None
    safe, count, error = _probe_account_scope()
    _SINGLE_ACCOUNT_SCOPE = safe
    _ACCOUNT_COUNT = count
    _SCOPE_ERROR = error
    result = dict(_ORIGINAL_START())
    result.update(stream_scope_status_v59())
    return result


def realtime_rows_safe_v59():
    assert _ORIGINAL_ROWS is not None
    rows = list(_ORIGINAL_ROWS())
    if _SINGLE_ACCOUNT_SCOPE:
        return rows
    return [row for row in rows if row.get("account_token") not in (None, "")]


def stream_scope_status_v59() -> dict[str, object]:
    return {
        "stream_scope_safety_version": V59_STREAM_SAFETY_VERSION,
        "api_account_count": _ACCOUNT_COUNT,
        "single_account_position_scope_safe": _SINGLE_ACCOUNT_SCOPE,
        "scope_probe_error": _SCOPE_ERROR,
        "unscoped_position_events_overlay_allowed": _SINGLE_ACCOUNT_SCOPE,
        "multiple_account_policy": "UNSCOPED_POSITION_EVENTS_DIAGNOSTIC_ONLY",
    }


def realtime_status_safe_v59(*, include_portfolio: bool = True) -> dict[str, object]:
    # v59.realtime_display_portfolio_v59 resolves _realtime_rows dynamically,
    # so replacing v59._realtime_rows is sufficient to make its overlay safe.
    original_status = _ORIGINAL_STATUS
    result = dict(original_status(include_portfolio=include_portfolio))
    result.update(stream_scope_status_v59())
    return result


_ORIGINAL_STATUS = v59.realtime_status_v59


def apply() -> None:
    if getattr(v59, "_v59_stream_safety_applied", False):
        return
    global _ORIGINAL_START, _ORIGINAL_ROWS
    _ORIGINAL_START = v59.start_realtime_stream_v59
    _ORIGINAL_ROWS = v59._realtime_rows
    v59.start_realtime_stream_v59 = start_realtime_stream_safe_v59
    v59._realtime_rows = realtime_rows_safe_v59
    v59.realtime_status_v59 = realtime_status_safe_v59
    v59.stream_scope_status_v59 = stream_scope_status_v59
    v59.V59_STREAM_SAFETY_VERSION = V59_STREAM_SAFETY_VERSION
    v59._v59_stream_safety_applied = True
