"""Entrypoint ổn định cho VN Quant Local Console.

UI thực tế nằm trong ``web_console_app`` để tách khỏi CLI wrapper và cho phép
kiểm thử khởi động bằng HTTP thật. Wrapper cũng giữ lớp tương thích nhỏ cho
NiceGUI 3.14.0, nơi ``ui.banner`` chưa tồn tại.
"""
from __future__ import annotations

from typing import Sequence

from he_thong_dinh_luong.web_console_app import (
    APP_TITLE,
    NICEGUI_VERSION,
    build_app,
    main as _app_main,
)


def _install_nicegui_compat() -> None:
    try:
        from nicegui import ui
    except ImportError:
        return
    if not hasattr(ui, "banner"):
        # Label hỗ trợ cả set_text và classes, đúng hợp đồng mà error banner dùng.
        setattr(ui, "banner", lambda text="": ui.label(text))


def main(argv: Sequence[str] | None = None) -> int:
    _install_nicegui_compat()
    return _app_main(argv)


__all__ = ["APP_TITLE", "NICEGUI_VERSION", "build_app", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
