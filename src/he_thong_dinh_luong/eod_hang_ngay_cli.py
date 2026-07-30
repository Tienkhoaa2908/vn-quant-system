"""Entrypoint EOD cross-platform; Viet Nam dung UTC+7 va khong co DST."""
from __future__ import annotations

from datetime import timedelta, timezone
import zoneinfo

FIXED_VN_TZ = timezone(timedelta(hours=7))


def _load_impl():
    try:
        zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    except zoneinfo.ZoneInfoNotFoundError:
        original = zoneinfo.ZoneInfo
        zoneinfo.ZoneInfo = lambda _key: FIXED_VN_TZ  # type: ignore[assignment]
        try:
            from . import eod_hang_ngay_v2 as implementation
        finally:
            zoneinfo.ZoneInfo = original  # type: ignore[assignment]
        return implementation
    from . import eod_hang_ngay_v2 as implementation
    return implementation


_impl = _load_impl()

SCHEMA_VERSION = _impl.SCHEMA_VERSION
CROSSCHECK_POLICIES = _impl.CROSSCHECK_POLICIES
DEFAULT_CROSSCHECK_SAMPLE_SIZE = _impl.DEFAULT_CROSSCHECK_SAMPLE_SIZE
VN_TZ = FIXED_VN_TZ
EodRow = _impl.EodRow
VnstockSource = _impl.VnstockSource
DnseRestSource = _impl.DnseRestSource
Source = _impl.Source
PUB_FILES = _impl.PUB_FILES
PUB_FIELDS = _impl.PUB_FIELDS
FEATURE_PREFIX = _impl.FEATURE_PREFIX
core = _impl.core

_crosscheck = _impl._crosscheck
_csv_bytes = _impl._csv_bytes
_json_bytes = _impl._json_bytes
_sha_bytes = _impl._sha_bytes
_source_from_name = _impl._source_from_name
_accepted_incremental_rows = _impl._accepted_incremental_rows
_primary_incremental_rows = _impl._primary_incremental_rows
_crosscheck_symbols = _impl._crosscheck_symbols
_benchmark_history = _impl._benchmark_history
_benchmark_diagnostics = _impl._benchmark_diagnostics
run = _impl.run
main = _impl.main

__all__ = [
    "SCHEMA_VERSION", "CROSSCHECK_POLICIES", "DEFAULT_CROSSCHECK_SAMPLE_SIZE",
    "VN_TZ", "EodRow", "VnstockSource", "DnseRestSource", "Source",
    "PUB_FILES", "PUB_FIELDS", "FEATURE_PREFIX", "run", "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
