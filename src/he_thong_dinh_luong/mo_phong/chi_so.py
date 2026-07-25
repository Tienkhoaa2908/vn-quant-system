"""Tinh chi so loi nhuan, rui ro va chi phi cho ket qua backtest."""
from __future__ import annotations

import math
import statistics
from decimal import Decimal

from .mo_hinh import MOT, SO_KHONG, ket_qua_mo_phong


def _float(gia_tri: Decimal) -> float:
    return float(gia_tri)


def _maximum_drawdown(
    cac_nav: list[Decimal], cac_ngay: list[str]
) -> tuple[Decimal | None, str | None, str | None]:
    if not cac_nav:
        return None, None, None
    dinh = cac_nav[0]
    ngay_dinh = cac_ngay[0]
    drawdown_lon_nhat = SO_KHONG
    bat_dau = cac_ngay[0]
    ket_thuc = cac_ngay[0]
    for nav, ngay in zip(cac_nav, cac_ngay):
        if nav > dinh:
            dinh = nav
            ngay_dinh = ngay
        drawdown = nav / dinh - MOT if dinh != 0 else SO_KHONG
        if drawdown < drawdown_lon_nhat:
            drawdown_lon_nhat = drawdown
            bat_dau = ngay_dinh
            ket_thuc = ngay
    return drawdown_lon_nhat, bat_dau, ket_thuc


def tinh_chi_so(ket_qua: ket_qua_mo_phong) -> dict[str, object]:
    cau_hinh = ket_qua.cau_hinh
    navs = [muc.nav for muc in ket_qua.nav]
    ngay = [muc.ngay.isoformat() for muc in ket_qua.nav]
    loi_nhuan = [
        muc.loi_nhuan_phien
        for muc in ket_qua.nav
        if muc.loi_nhuan_phien is not None
    ]
    nav_cuoi = navs[-1] if navs else cau_hinh.von_ban_dau
    tong_loi_nhuan = nav_cuoi / cau_hinh.von_ban_dau - MOT

    cagr: float | None = None
    bien_dong_nam: float | None = None
    sharpe: float | None = None
    canh_bao: list[str] = []
    if len(loi_nhuan) >= 2:
        so_phien = len(loi_nhuan)
        if nav_cuoi > 0:
            cagr = _float(
                (nav_cuoi / cau_hinh.von_ban_dau)
                ** (Decimal(cau_hinh.so_phien_moi_nam) / Decimal(so_phien))
                - MOT
            )
        cac_loi_nhuan_float = [_float(muc) for muc in loi_nhuan]
        do_lech_chuan = statistics.stdev(cac_loi_nhuan_float)
        if do_lech_chuan > 0:
            bien_dong_nam = do_lech_chuan * math.sqrt(cau_hinh.so_phien_moi_nam)
            lai_phi_rui_ro_phien = (
                (1.0 + _float(cau_hinh.lai_suat_phi_rui_ro))
                ** (1.0 / cau_hinh.so_phien_moi_nam)
                - 1.0
            )
            loi_nhuan_vuot = [
                muc - lai_phi_rui_ro_phien for muc in cac_loi_nhuan_float
            ]
            sharpe = (
                statistics.mean(loi_nhuan_vuot)
                / do_lech_chuan
                * math.sqrt(cau_hinh.so_phien_moi_nam)
            )
        else:
            canh_bao.append(
                "Sharpe khong xac dinh vi phuong sai loi nhuan bang 0."
            )
    else:
        canh_bao.append(
            "Khong du quan sat de tinh CAGR, bien dong nam hoa va Sharpe."
        )

    maximum_drawdown, ngay_dinh, ngay_day = _maximum_drawdown(navs, ngay)
    tong_mua = sum(
        (
            muc.gia_tri_giao_dich
            for muc in ket_qua.khop_lenh
            if muc.chieu == "MUA"
        ),
        SO_KHONG,
    )
    tong_ban = sum(
        (
            muc.gia_tri_giao_dich
            for muc in ket_qua.khop_lenh
            if muc.chieu == "BAN"
        ),
        SO_KHONG,
    )
    phi_mua = sum(
        (muc.phi for muc in ket_qua.khop_lenh if muc.chieu == "MUA"), SO_KHONG
    )
    phi_ban = sum(
        (muc.phi for muc in ket_qua.khop_lenh if muc.chieu == "BAN"), SO_KHONG
    )
    thue_ban = sum(
        (muc.thue for muc in ket_qua.khop_lenh if muc.chieu == "BAN"),
        SO_KHONG,
    )
    truot_gia = sum(
        (muc.chi_phi_truot_gia for muc in ket_qua.khop_lenh), SO_KHONG
    )
    nav_trung_binh = (
        sum(navs, SO_KHONG) / Decimal(len(navs)) if navs else SO_KHONG
    )
    turnover = (
        (tong_mua + tong_ban) / (Decimal("2") * nav_trung_binh)
        if nav_trung_binh > 0
        else None
    )
    ty_trong_tien_mat = [
        muc.ty_trong_tien_mat
        for muc in ket_qua.nav
        if muc.ty_trong_tien_mat is not None
    ]
    tien_mat_trung_binh = (
        sum(ty_trong_tien_mat, SO_KHONG) / Decimal(len(ty_trong_tien_mat))
        if ty_trong_tien_mat
        else None
    )

    return {
        "nav_dau_ky": cau_hinh.von_ban_dau,
        "nav_cuoi_ky": nav_cuoi,
        "tong_loi_nhuan": tong_loi_nhuan,
        "cagr": cagr,
        "bien_dong_nam_hoa": bien_dong_nam,
        "sharpe": sharpe,
        "maximum_drawdown": maximum_drawdown,
        "ngay_bat_dau_drawdown_lon_nhat": ngay_dinh,
        "ngay_ket_thuc_drawdown_lon_nhat": ngay_day,
        "turnover": turnover,
        "tong_gia_tri_mua": tong_mua,
        "tong_gia_tri_ban": tong_ban,
        "tong_phi_mua": phi_mua,
        "tong_phi_ban": phi_ban,
        "tong_thue_ban": thue_ban,
        "tong_chi_phi_truot_gia": truot_gia,
        "so_lenh_tao": len(ket_qua.lenh),
        "so_lenh_khop": sum(muc.trang_thai == "da_khop" for muc in ket_qua.lenh),
        "so_lenh_het_han": sum(
            muc.trang_thai == "het_han" for muc in ket_qua.lenh
        ),
        "so_lenh_tu_choi": sum(
            muc.trang_thai == "tu_choi" for muc in ket_qua.lenh
        ),
        "so_lan_tai_can_bang": ket_qua.so_lan_tai_can_bang,
        "ty_trong_tien_mat_trung_binh": tien_mat_trung_binh,
        "so_phien": len(ket_qua.nav),
        "canh_bao": [*ket_qua.canh_bao, *canh_bao],
        "cong_thuc": {
            "loi_nhuan_phien": "nav_t / nav_t_1 - 1; phien dau so voi von_ban_dau",
            "cagr": "(nav_cuoi/nav_dau)^(so_phien_moi_nam/so_quan_sat)-1",
            "maximum_drawdown": "min(nav_t/dinh_luy_ke_t-1)",
            "sharpe": "mean(r_t-rf_phien)/stdev_mau(r_t)*sqrt(so_phien_moi_nam)",
            "turnover": "(tong_gia_tri_mua+tong_gia_tri_ban)/(2*nav_trung_binh)",
        },
    }
