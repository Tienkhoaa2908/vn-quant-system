"""Stable entrypoint for VN Quant Local Terminal v7."""
from __future__ import annotations

from he_thong_dinh_luong.web_console_app_v7 import (
    APP_TITLE,
    NICEGUI_VERSION,
    build_app,
    main,
)

__all__ = ["APP_TITLE", "NICEGUI_VERSION", "build_app", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
