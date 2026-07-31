"""Stable entrypoint for VN Quant Local Console v3."""
from he_thong_dinh_luong.web_console_app_v3 import APP_TITLE, NICEGUI_VERSION, build_app, main

__all__ = ["APP_TITLE", "NICEGUI_VERSION", "build_app", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
