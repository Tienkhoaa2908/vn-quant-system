"""Adapter ghep mot chuoi target weight OOS va goi engine Moc 3 dung mot lan."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .mo_hinh import DongXepHang


def chuyen_ty_trong_test(rankings: Iterable[DongXepHang]) -> list[object]:
    rows = [x for x in rankings if x.duoc_chon]
    keys = [(x.ngay, x.ma) for x in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Trung khoa (ngay_tin_hieu,ma) trong target weights test.")
    from he_thong_dinh_luong.mo_phong.mo_hinh import ty_trong_muc_tieu
    return [ty_trong_muc_tieu(
        ngay_tin_hieu=x.ngay,
        ma=x.ma,
        ty_trong=Decimal(str(x.ty_trong_muc_tieu)),
        ten_chien_luoc="m4_logistic_oos",
    ) for x in sorted(rows, key=lambda r: (r.ngay, r.ma))]


def chay_backtest_oos_lien_tuc(*, rankings: Iterable[DongXepHang], du_lieu_gia: object, cau_hinh_mo_phong: object, cac_su_kien: object = ()) -> object:
    from he_thong_dinh_luong.mo_phong import chay_mo_phong
    targets = chuyen_ty_trong_test(rankings)
    return chay_mo_phong(du_lieu_gia, targets, cau_hinh_mo_phong, cac_su_kien)
