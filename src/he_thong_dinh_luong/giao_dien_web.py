"""Entrypoint on dinh cho VN Quant Local Console.

UI thuc te nam trong ``web_console_app`` de tach khoi CLI wrapper va cho phep
kiem thu khoi dong bang HTTP that.
"""
from he_thong_dinh_luong.web_console_app import APP_TITLE, NICEGUI_VERSION, build_app, main

__all__ = ["APP_TITLE", "NICEGUI_VERSION", "build_app", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
