"""Cac bo tao ty trong baseline chi de kiem tra engine Moc 3."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Iterable
from .mo_hinh import thanh_gia, ty_trong_muc_tieu


def _theo_ngay(du_lieu_gia: Iterable[thanh_gia]) -> dict[date, list[thanh_gia]]:
    ket_qua: dict[date, list[thanh_gia]] = {}
    for muc in du_lieu_gia:
        ket_qua.setdefault(muc.ngay, []).append(muc)
    for cac_muc in ket_qua.values():
        cac_muc.sort(key=lambda muc: muc.ma)
    return ket_qua


def _chia_deu(ngay: date, cac_ma: list[str], ten: str) -> list[ty_trong_muc_tieu]:
    if not cac_ma:
        return []
    ty_trong = Decimal("1") / Decimal(len(cac_ma))
    return [ty_trong_muc_tieu(ngay, ma, ty_trong, ten) for ma in sorted(cac_ma)]


def baseline_mua_va_giu(du_lieu_gia: Iterable[thanh_gia], *, ngay_tin_hieu: date | None = None, cac_ma: Iterable[str] | None = None) -> list[ty_trong_muc_tieu]:
    theo_ngay = _theo_ngay(du_lieu_gia)
    if not theo_ngay:
        raise ValueError("Khong co du lieu gia cho baseline mua va giu.")
    ngay = ngay_tin_hieu or min(theo_ngay)
    if ngay not in theo_ngay:
        raise ValueError("Ngay tin hieu mua va giu khong co trong du lieu gia.")
    tap_ma = {ma.strip().upper() for ma in cac_ma} if cac_ma is not None else None
    du_dieu_kien = [
        muc.ma for muc in theo_ngay[ngay]
        if (tap_ma is None or muc.ma in tap_ma)
        and muc.thuoc_tap_co_phieu is True
        and muc.dat_thanh_khoan is True
    ]
    return _chia_deu(ngay, du_dieu_kien, "mua_va_giu")


def baseline_can_bang_deu(du_lieu_gia: Iterable[thanh_gia], *, cac_ngay_tai_can_bang: Iterable[date]) -> list[ty_trong_muc_tieu]:
    theo_ngay = _theo_ngay(du_lieu_gia)
    ket_qua: list[ty_trong_muc_tieu] = []
    for ngay in sorted(set(cac_ngay_tai_can_bang)):
        if ngay not in theo_ngay:
            raise ValueError(f"Ngay tai can bang {ngay} khong co trong du lieu gia.")
        cac_ma = [muc.ma for muc in theo_ngay[ngay] if muc.thuoc_tap_co_phieu is True and muc.dat_thanh_khoan is True]
        ket_qua.extend(_chia_deu(ngay, cac_ma, "can_bang_deu"))
    return ket_qua


def baseline_ma250_dong_luong(du_lieu_gia: Iterable[thanh_gia], *, cac_ngay_tai_can_bang: Iterable[date], top_k: int) -> list[ty_trong_muc_tieu]:
    if top_k <= 0:
        raise ValueError("top_k phai lon hon 0.")
    theo_ngay = _theo_ngay(du_lieu_gia)
    ket_qua: list[ty_trong_muc_tieu] = []
    for ngay in sorted(set(cac_ngay_tai_can_bang)):
        if ngay not in theo_ngay:
            raise ValueError(f"Ngay tai can bang {ngay} khong co trong du lieu gia.")
        ung_vien = [muc for muc in theo_ngay[ngay] if muc.thuoc_tap_co_phieu is True and muc.dat_thanh_khoan is True and muc.tren_ma250 is True and muc.dong_luong is not None]
        ung_vien.sort(key=lambda muc: (-muc.dong_luong, muc.ma))
        ket_qua.extend(_chia_deu(ngay, [muc.ma for muc in ung_vien[:top_k]], "ma250_dong_luong"))
    return ket_qua
