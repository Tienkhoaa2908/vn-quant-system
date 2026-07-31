"""Stable cross-platform entrypoint for VN Quant Local Terminal v7."""
from __future__ import annotations

from datetime import timedelta, timezone
import zoneinfo

FIXED_VN_TZ = timezone(timedelta(hours=7))


def _load_app():
    try:
        zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    except zoneinfo.ZoneInfoNotFoundError:
        original = zoneinfo.ZoneInfo
        zoneinfo.ZoneInfo = lambda _key: FIXED_VN_TZ  # type: ignore[assignment]
        try:
            from he_thong_dinh_luong import web_console_app_v7 as application
        finally:
            zoneinfo.ZoneInfo = original  # type: ignore[assignment]
        return application
    from he_thong_dinh_luong import web_console_app_v7 as application
    return application


_app = _load_app()
APP_TITLE = _app.APP_TITLE
NICEGUI_VERSION = _app.NICEGUI_VERSION
build_app = _app.build_app
main = _app.main

__all__ = ["APP_TITLE", "NICEGUI_VERSION", "build_app", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
