"""Chuẩn hóa bảng dữ liệu nguồn về lược đồ OHLCV của dự án."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from ..kiem_tra_du_lieu import CAC_COT_BAT_BUOC
from .mo_hinh import bang_du_lieu_nguon


def _chuan_hoa_ngay(gia_tri: Any) -> str:
    if isinstance(gia_tri, datetime):
        return gia_tri.date().isoformat()
    if isinstance(gia_tri, date):
        return gia_tri.isoformat()
    if hasattr(gia_tri, "to_pydatetime"):
        return gia_tri.to_pydatetime().date().isoformat()
    chuoi = str(gia_tri).strip()
    return date.fromisoformat(chuoi[:10]).isoformat()


def _chuan_hoa_gia(gia_tri: Any, ten_cot: str) -> float:
    ket_qua = float(gia_tri)
    if not math.isfinite(ket_qua):
        raise ValueError(f"{ten_cot} khong phai so huu han")
    return ket_qua


def _chuan_hoa_khoi_luong(gia_tri: Any) -> int:
    ket_qua = float(gia_tri)
    if not math.isfinite(ket_qua) or not ket_qua.is_integer():
        raise ValueError(f"khoi_luong khong phai so nguyen huu han: {gia_tri}")
    return int(ket_qua)


def chuan_hoa_bang(bang: bang_du_lieu_nguon) -> list[dict[str, object]]:
    anh_xa_nguoc = {cot_chuan: cot_nguon for cot_nguon, cot_chuan in bang.anh_xa_cot.items()}
    cot_can_anh_xa = tuple(cot for cot in CAC_COT_BAT_BUOC if cot != "ma")
    thieu_anh_xa = [cot for cot in cot_can_anh_xa if cot not in anh_xa_nguoc]
    if thieu_anh_xa:
        raise ValueError(f"Thieu anh xa cot: {', '.join(thieu_anh_xa)}")

    cac_dong_chuan: list[dict[str, object]] = []
    for vi_tri, dong in enumerate(bang.cac_dong, start=1):
        try:
            dong_chuan = {
                "ma": bang.ma.strip().upper(),
                "ngay": _chuan_hoa_ngay(dong[anh_xa_nguoc["ngay"]]),
                "gia_mo_cua": _chuan_hoa_gia(
                    dong[anh_xa_nguoc["gia_mo_cua"]], "gia_mo_cua"
                ),
                "gia_cao_nhat": _chuan_hoa_gia(
                    dong[anh_xa_nguoc["gia_cao_nhat"]], "gia_cao_nhat"
                ),
                "gia_thap_nhat": _chuan_hoa_gia(
                    dong[anh_xa_nguoc["gia_thap_nhat"]], "gia_thap_nhat"
                ),
                "gia_dong_cua": _chuan_hoa_gia(
                    dong[anh_xa_nguoc["gia_dong_cua"]], "gia_dong_cua"
                ),
                "khoi_luong": _chuan_hoa_khoi_luong(
                    dong[anh_xa_nguoc["khoi_luong"]]
                ),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Khong chuan hoa duoc dong nguon {vi_tri}: {exc}") from exc
        cac_dong_chuan.append(dong_chuan)

    cac_dong_chuan.sort(key=lambda dong: (str(dong["ma"]), str(dong["ngay"])))
    return cac_dong_chuan
