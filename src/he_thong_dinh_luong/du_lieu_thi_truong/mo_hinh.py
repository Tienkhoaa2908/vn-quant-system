"""Các mô hình dữ liệu dùng trong luồng thu thập."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


class loi_nguon_du_lieu(RuntimeError):
    """Lỗi từ nguồn dữ liệu, có thể đánh dấu là tạm thời."""

    def __init__(self, noi_dung: str, *, tam_thoi: bool = False) -> None:
        super().__init__(noi_dung)
        self.tam_thoi = tam_thoi


class khong_co_du_lieu(loi_nguon_du_lieu):
    """Nguồn không trả dữ liệu cho mã và khoảng ngày yêu cầu."""


@dataclass(frozen=True)
class bang_du_lieu_nguon:
    ma: str
    cac_cot: tuple[str, ...]
    kieu_du_lieu: dict[str, str]
    cac_dong: tuple[dict[str, Any], ...]
    anh_xa_cot: dict[str, str]
    don_vi_gia: str | None = None
    ghi_chu_khoi_luong: str | None = None
    tham_so_gia: str | None = None


@dataclass(frozen=True)
class trang_thai_ma:
    ma: str
    trang_thai: str
    thoi_diem_chay: str
    ngay_bat_dau: str
    ngay_ket_thuc: str
    so_dong: int
    so_lan_thu: int
    ten_cot_nguon: tuple[str, ...] = ()
    kieu_du_lieu: dict[str, str] | None = None
    don_vi_gia: str | None = None
    duong_dan_tho: str | None = None
    duong_dan_chuan_hoa: str | None = None
    duong_dan_san_sang: str | None = None
    duong_dan_bao_cao: str | None = None
    duong_dan_nhat_ky: str | None = None
    ma_sha256: str | None = None
    ngay_dau: str | None = None
    ngay_cuoi: str | None = None
    canh_bao: tuple[str, ...] = ()
    loi: str | None = None

    def thanh_tu_dien(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ket_qua_lan_chay:
    ma_lan_chay: str
    nguon: str
    phien_ban: str
    ngay_bat_dau: str
    ngay_ket_thuc: str
    trang_thai_tung_ma: tuple[trang_thai_ma, ...]
    duong_dan_nhat_ky: str
    cau_hinh_lan_chay: Mapping[str, Any] = field(default_factory=dict)

    def noi_dung_tong_hop(self) -> dict[str, Any]:
        """Tạo đúng nội dung bất biến được lưu trong ``tong_hop.json``."""
        ket_qua: dict[str, Any] = {
            "ma_lan_chay": self.ma_lan_chay,
            "nguon": self.nguon,
            "phien_ban": self.phien_ban,
            "ngay_bat_dau": self.ngay_bat_dau,
            "ngay_ket_thuc": self.ngay_ket_thuc,
        }
        ket_qua.update(dict(self.cau_hinh_lan_chay))
        ket_qua["trang_thai_tung_ma"] = [
            muc.thanh_tu_dien() for muc in self.trang_thai_tung_ma
        ]
        return ket_qua

    def thanh_tu_dien(self) -> dict[str, Any]:
        """Trả nội dung terminal, dùng cùng cấu hình với tổng hợp trên đĩa."""
        ket_qua = self.noi_dung_tong_hop()
        ket_qua["duong_dan_nhat_ky"] = self.duong_dan_nhat_ky
        return ket_qua
