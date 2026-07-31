"""Cross-platform wrapper for anytime snapshot; Vietnam is fixed UTC+7 without DST."""
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
            from . import anytime_snapshot as implementation
        finally:
            zoneinfo.ZoneInfo = original  # type: ignore[assignment]
        return implementation
    from . import anytime_snapshot as implementation
    return implementation


_impl = _load_impl()
run = _impl.run
main = _impl.main

__all__ = ["run", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
