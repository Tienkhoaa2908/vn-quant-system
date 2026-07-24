"""Tinh thanh khoan, MA250 va dong luong theo tung ma, khong nhin truoc."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

from ..kiem_tra_du_lieu import CAC_COT_BAT_BUOC
from .tap_co_phieu import chi_muc_tap_co_phieu

DON_VI_GIA_TRI_GIAO_DICH = "nghin_dong"
CAC_COT_DAU_RA = (
    "ma",
    "ngay",
    "thuoc_tap_co_phieu",
    "ngay_hieu_luc_tap_co_phieu",
    "nguon_tap_co_phieu",
    "phien_ban_tap_co_phieu",
    "gia_tri_giao_dich",
    "gia_tri_giao_dich_trung_binh",
    "dat_thanh_khoan",
    "ma250",
    "tren_ma250",
    "dong_luong",
    "trang_thai_lich_su",
)


@dataclass(frozen=True)
class cau_hinh_duong_co_so:
    cua_so_thanh_khoan: int
    so_quan_sat_toi_thieu: int
    nguong_thanh_khoan: float
    cua_so_dong_luong: int

    def __post_init__(self) -> None:
        if self.cua_so_thanh_khoan <= 0:
            raise ValueError("Cua so thanh khoan phai lon hon 0.")
        if not 1 <= self.so_quan_sat_toi_thieu <= self.cua_so_thanh_khoan:
            raise ValueError("So quan sat toi thieu phai nam trong cua so thanh khoan.")
        if not math.isfinite(self.nguong_thanh_khoan) or self.nguong_thanh_khoan < 0:
            raise ValueError("Nguong thanh khoan phai la so huu han khong am.")
        if self.cua_so_dong_luong <= 0:
            raise ValueError("Cua so dong luong phai lon hon 0.")


def _doc_so(dong: Mapping[str, object], ten_cot: str) -> float:
    try:
        gia_tri = float(dong[ten_cot])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Khong doc duoc {ten_cot}.") from exc
    if not math.isfinite(gia_tri):
        raise ValueError(f"{ten_cot} khong phai so huu han.")
    return gia_tri


def _chuan_hoa_du_lieu(
    cac_dong: Iterable[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    theo_ma: dict[str, list[dict[str, object]]] = {}
    khoa_da_gap: set[tuple[str, date]] = set()
    for so_dong, dong_ban_dau in enumerate(cac_dong, start=2):
        dong = dict(dong_ban_dau)
        thieu_cot = [cot for cot in CAC_COT_BAT_BUOC if cot not in dong]
        if thieu_cot:
            raise ValueError(
                f"Dong {so_dong} thieu cot bat buoc: {', '.join(thieu_cot)}."
            )
        ma = str(dong["ma"]).strip().upper()
        if not ma:
            raise ValueError(f"Ma rong tai dong {so_dong}.")
        try:
            ngay = date.fromisoformat(str(dong["ngay"]).strip()[:10])
        except ValueError as exc:
            raise ValueError(f"Ngay khong hop le tai dong {so_dong}.") from exc
        gia_dong_cua = _doc_so(dong, "gia_dong_cua")
        khoi_luong = _doc_so(dong, "khoi_luong")
        if gia_dong_cua <= 0:
            raise ValueError(f"Gia dong cua phai duong tai {ma}, {ngay}.")
        if khoi_luong < 0 or not khoi_luong.is_integer():
            raise ValueError(f"Khoi luong phai la so nguyen khong am tai {ma}, {ngay}.")
        khoa = (ma, ngay)
        if khoa in khoa_da_gap:
            raise ValueError(f"Trung ma va ngay: {ma}, {ngay}.")
        khoa_da_gap.add(khoa)
        theo_ma.setdefault(ma, []).append(
            {
                "ma": ma,
                "ngay": ngay,
                "gia_dong_cua": gia_dong_cua,
                "khoi_luong": int(khoi_luong),
            }
        )
    if not theo_ma:
        raise ValueError("Du lieu san sang khong co dong nao.")
    for cac_dong_ma in theo_ma.values():
        cac_dong_ma.sort(key=lambda dong: dong["ngay"])
    return theo_ma


def tinh_duong_co_so(
    cac_dong: Iterable[Mapping[str, object]],
    tap_co_phieu: chi_muc_tap_co_phieu,
    cau_hinh: cau_hinh_duong_co_so,
    *,
    ngay_bat_dau: date | None = None,
    ngay_ket_thuc: date | None = None,
) -> list[dict[str, object]]:
    if ngay_bat_dau and ngay_ket_thuc and ngay_bat_dau > ngay_ket_thuc:
        raise ValueError("Ngay bat dau khong duoc sau ngay ket thuc.")
    theo_ma = _chuan_hoa_du_lieu(cac_dong)
    ket_qua: list[dict[str, object]] = []

    for ma in sorted(theo_ma):
        lich_su_gia: list[float] = []
        cua_so_gia_tri: deque[float] = deque()
        tong_gia_tri = 0.0
        for dong in theo_ma[ma]:
            ngay = dong["ngay"]
            gia_dong_cua = float(dong["gia_dong_cua"])
            gia_tri_giao_dich = gia_dong_cua * int(dong["khoi_luong"])

            cua_so_gia_tri.append(gia_tri_giao_dich)
            tong_gia_tri += gia_tri_giao_dich
            if len(cua_so_gia_tri) > cau_hinh.cua_so_thanh_khoan:
                tong_gia_tri -= cua_so_gia_tri.popleft()
            du_thanh_khoan = len(cua_so_gia_tri) >= cau_hinh.so_quan_sat_toi_thieu
            gia_tri_trung_binh = (
                tong_gia_tri / len(cua_so_gia_tri) if du_thanh_khoan else None
            )
            dat_thanh_khoan = (
                gia_tri_trung_binh >= cau_hinh.nguong_thanh_khoan
                if gia_tri_trung_binh is not None
                else None
            )

            lich_su_gia.append(gia_dong_cua)
            du_ma250 = len(lich_su_gia) >= 250
            ma250 = sum(lich_su_gia[-250:]) / 250 if du_ma250 else None
            tren_ma250 = gia_dong_cua >= ma250 if ma250 is not None else None

            du_dong_luong = len(lich_su_gia) > cau_hinh.cua_so_dong_luong
            dong_luong = (
                gia_dong_cua
                / lich_su_gia[-cau_hinh.cua_so_dong_luong - 1]
                - 1.0
                if du_dong_luong
                else None
            )

            if ngay_bat_dau and ngay < ngay_bat_dau:
                continue
            if ngay_ket_thuc and ngay > ngay_ket_thuc:
                continue

            anh_chup = tap_co_phieu.chon(ngay)
            thuoc_tap = ma in set(anh_chup.cac_ma)
            trang_thai = ";".join(
                (
                    f"thanh_khoan={'du' if du_thanh_khoan else 'thieu'}",
                    f"ma250={'du' if du_ma250 else 'thieu'}",
                    f"dong_luong={'du' if du_dong_luong else 'thieu'}",
                )
            )
            ket_qua.append(
                {
                    "ma": ma,
                    "ngay": ngay.isoformat(),
                    "thuoc_tap_co_phieu": thuoc_tap,
                    "ngay_hieu_luc_tap_co_phieu": anh_chup.ngay_hieu_luc.isoformat(),
                    "nguon_tap_co_phieu": anh_chup.nguon,
                    "phien_ban_tap_co_phieu": anh_chup.phien_ban,
                    "gia_tri_giao_dich": gia_tri_giao_dich,
                    "gia_tri_giao_dich_trung_binh": gia_tri_trung_binh,
                    "dat_thanh_khoan": dat_thanh_khoan,
                    "ma250": ma250,
                    "tren_ma250": tren_ma250,
                    "dong_luong": dong_luong,
                    "trang_thai_lich_su": trang_thai,
                }
            )
    ket_qua.sort(key=lambda dong: (str(dong["ma"]), str(dong["ngay"])))
    return ket_qua
