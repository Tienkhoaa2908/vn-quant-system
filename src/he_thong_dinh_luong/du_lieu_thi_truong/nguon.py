"""Giao diện chung cho các nguồn dữ liệu thị trường."""

from __future__ import annotations

from typing import Protocol

from .mo_hinh import bang_du_lieu_nguon


class nguon_du_lieu(Protocol):
    ten_nguon: str
    phien_ban: str | None

    def lay_du_lieu(
        self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str
    ) -> bang_du_lieu_nguon:
        """Lấy bảng dữ liệu nguồn cho một mã."""
        ...
