"""Adapter ghep target weight OOS lien tuc va goi engine Moc 3 dung mot lan moi chien luoc."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
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
    if any(not isinstance(day, date) for day in dates):
        raise ValueError("ngay_tai_can_bang phai la date.")
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


def _cat_gia_oos(du_lieu_gia: object, *, oos_start: date | None, oos_end: date | None) -> list[object]:
    rows = list(du_lieu_gia)
    if not rows:
        raise ValueError("Du lieu gia OOS rong.")
    if (oos_start is None) != (oos_end is None):
        raise ValueError("oos_start va oos_end phai cung duoc truyen.")
    if oos_start is None or oos_end is None:
        return rows
    if oos_start > oos_end:
        raise ValueError("oos_start khong duoc sau oos_end.")
    sliced = [row for row in rows if oos_start <= getattr(row, "ngay") <= oos_end]
    if not sliced:
        raise ValueError("Khong co du lieu gia trong cua so OOS.")
    return sliced


def chay_backtest_oos_lien_tuc(
    *,
    rankings: Iterable[DongXepHang],
    du_lieu_gia: object,
    cau_hinh_mo_phong: object,
    cac_su_kien: object = (),
    ngay_tai_can_bang: Iterable[object] | None = None,
    cac_ma_lien_quan: Iterable[str] | None = None,
    ten_chien_luoc: str = "m4_logistic_oos",
    oos_start: date | None = None,
    oos_end: date | None = None,
) -> object:
    """Chay mot engine duy nhat tren cua so OOS; lich su train khong duoc dua vao engine."""
    _xac_thuc_che_do_dong_vi_the(cau_hinh_mo_phong)
    from he_thong_dinh_luong.mo_phong import chay_mo_phong

    targets = chuyen_ty_trong_test(
        rankings,
        ngay_tai_can_bang=ngay_tai_can_bang,
        cac_ma_lien_quan=cac_ma_lien_quan,
        ten_chien_luoc=ten_chien_luoc,
    )
    prices = _cat_gia_oos(du_lieu_gia, oos_start=oos_start, oos_end=oos_end)
    events = list(cac_su_kien)
    if oos_start is not None and oos_end is not None:
        if any(not (oos_start <= target.ngay_tin_hieu <= oos_end) for target in targets):
            raise ValueError("Target weight nam ngoai cua so OOS.")
        events = [event for event in events if oos_start <= event.ngay_hieu_luc <= oos_end]
    return chay_mo_phong(prices, targets, cau_hinh_mo_phong, events)


def cat_ket_qua_metric_oos(
    result: object,
    *,
    oos_start: date,
    metric_start: date,
    oos_end: date,
) -> object:
    """Cat ket qua engine truoc khi tinh metric; van giu von khoi tao duy nhat."""
    if not (oos_start <= metric_start <= oos_end):
        raise ValueError("Cua so metric OOS khong hop le.")
    from he_thong_dinh_luong.mo_phong.mo_hinh import ket_qua_mo_phong

    sliced = ket_qua_mo_phong(cau_hinh=result.cau_hinh)
    sliced.lenh = [row for row in result.lenh if oos_start <= row.ngay_tin_hieu <= oos_end]
    sliced.khop_lenh = [row for row in result.khop_lenh if metric_start <= row.ngay_khop <= oos_end]
    sliced.vi_the_hang_ngay = [row for row in result.vi_the_hang_ngay if metric_start <= row.ngay <= oos_end]
    sliced.so_cai = [row for row in result.so_cai if metric_start <= row.ngay <= oos_end]
    sliced.nav = [row for row in result.nav if metric_start <= row.ngay <= oos_end]
    sliced.su_kien_da_ap_dung = [
        row for row in result.su_kien_da_ap_dung
        if metric_start <= date.fromisoformat(str(row.get("ngay", row.get("ngay_hieu_luc")))[:10]) <= oos_end
    ]
    sliced.so_lan_tai_can_bang = result.so_lan_tai_can_bang
    sliced.canh_bao = list(result.canh_bao)
    return sliced


def metric_backtest_oos(
    result: object,
    *,
    oos_start: date,
    metric_start: date,
    oos_end: date,
) -> dict[str, object]:
    from he_thong_dinh_luong.mo_phong import tinh_chi_so

    sliced = cat_ket_qua_metric_oos(
        result, oos_start=oos_start, metric_start=metric_start, oos_end=oos_end,
    )
    metrics = tinh_chi_so(sliced)
    metrics.update({
        "oos_start": oos_start.isoformat(),
        "ngay_bat_dau_metric": metric_start.isoformat(),
        "ngay_ket_thuc_metric": oos_end.isoformat(),
    })
    return metrics
