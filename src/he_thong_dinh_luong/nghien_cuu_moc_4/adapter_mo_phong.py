"""Adapter ghep target weight OOS lien tuc va goi engine Moc 3 dung mot lan moi chien luoc."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .mo_hinh import DongXepHang


def _xac_thuc_che_do_dong_vi_the(cau_hinh_mo_phong: object) -> None:
    mode = getattr(cau_hinh_mo_phong, "che_do_ma_khong_xuat_hien", None)
    if mode != "muc_tieu_bang_0":
        raise ValueError("Backtest Moc 4 bat buoc che_do_ma_khong_xuat_hien=muc_tieu_bang_0.")


def chuyen_ty_trong_test(
    rankings: Iterable[DongXepHang],
    *,
    ngay_tai_can_bang: Iterable[object] | None = None,
    cac_ma_lien_quan: Iterable[str] | None = None,
    ten_chien_luoc: str = "m4_logistic_oos",
) -> list[object]:
    rows = list(rankings)
    keys = [(x.ngay, x.ma) for x in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Trung khoa (ngay_tin_hieu,ma) trong target weights test.")
    dates = sorted(set(ngay_tai_can_bang) if ngay_tai_can_bang is not None else {x.ngay for x in rows})
    symbols = sorted(set(cac_ma_lien_quan) if cac_ma_lien_quan is not None else {x.ma for x in rows})
    if any(not isinstance(symbol, str) or not symbol for symbol in symbols):
        raise ValueError("cac_ma_lien_quan phai la ma khong rong.")
    if not ten_chien_luoc:
        raise ValueError("ten_chien_luoc khong duoc rong.")

    by_key = {(x.ngay, x.ma): x for x in rows}
    from he_thong_dinh_luong.mo_phong.mo_hinh import ty_trong_muc_tieu

    targets: list[object] = []
    for day in dates:
        for symbol in symbols:
            row = by_key.get((day, symbol))
            weight = row.ty_trong_muc_tieu if row is not None and row.duoc_chon else 0.0
            targets.append(ty_trong_muc_tieu(
                ngay_tin_hieu=day,
                ma=symbol,
                ty_trong=Decimal(str(weight)),
                ten_chien_luoc=ten_chien_luoc,
            ))
    return targets


def chay_backtest_oos_lien_tuc(
    *,
    rankings: Iterable[DongXepHang],
    du_lieu_gia: object,
    cau_hinh_mo_phong: object,
    cac_su_kien: object = (),
    ngay_tai_can_bang: Iterable[object] | None = None,
    cac_ma_lien_quan: Iterable[str] | None = None,
    ten_chien_luoc: str = "m4_logistic_oos",
) -> object:
    _xac_thuc_che_do_dong_vi_the(cau_hinh_mo_phong)
    from he_thong_dinh_luong.mo_phong import chay_mo_phong
    targets = chuyen_ty_trong_test(
        rankings,
        ngay_tai_can_bang=ngay_tai_can_bang,
        cac_ma_lien_quan=cac_ma_lien_quan,
        ten_chien_luoc=ten_chien_luoc,
    )
    return chay_mo_phong(du_lieu_gia, targets, cau_hinh_mo_phong, cac_su_kien)
