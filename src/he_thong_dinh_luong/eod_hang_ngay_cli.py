"""Entrypoint EOD cross-platform; Viet Nam dung UTC+7 va khong co DST."""
from __future__ import annotations

from datetime import timedelta, timezone
import zoneinfo


def _load_impl():
    try:
        zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    except zoneinfo.ZoneInfoNotFoundError:
        original = zoneinfo.ZoneInfo
        zoneinfo.ZoneInfo = lambda _key: timezone(timedelta(hours=7))  # type: ignore[assignment]
        try:
            from . import eod_hang_ngay_v2 as implementation
        finally:
            zoneinfo.ZoneInfo = original  # type: ignore[assignment]
        return implementation
    from . import eod_hang_ngay_v2 as implementation
    return implementation


_impl = _load_impl()

SCHEMA_VERSION = _impl.SCHEMA_VERSION
VN_TZ = _impl.VN_TZ
EodRow = _impl.EodRow
VnstockSource = _impl.VnstockSource
Source = _impl.Source
PUB_FILES = _impl.PUB_FILES
PUB_FIELDS = _impl.PUB_FIELDS
FEATURE_PREFIX = _impl.FEATURE_PREFIX
core = _impl.core

_crosscheck = _impl._crosscheck
_csv_bytes = _impl._csv_bytes
_json_bytes = _impl._json_bytes
_sha_bytes = _impl._sha_bytes
_accepted_incremental_rows = _impl._accepted_incremental_rows
_benchmark_history = _impl._benchmark_history
run = _impl.run
main = _impl.main

__all__ = [
    "SCHEMA_VERSION", "VN_TZ", "EodRow", "VnstockSource", "Source",
    "PUB_FILES", "PUB_FIELDS", "FEATURE_PREFIX", "run", "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
