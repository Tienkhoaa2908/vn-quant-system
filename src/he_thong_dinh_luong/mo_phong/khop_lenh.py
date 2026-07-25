"""Dinh co suc mua va khop lenh gia lap cho Moc 3."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from .mo_hinh import MOT, SO_KHONG, cau_hinh_mo_phong, khop_lenh, lenh, thanh_gia, vi_the

MUOI_NGHIN = Decimal("10000")
SAI_SO_TIEN_MAT = Decimal("0.000000001")


def _lam_tron_xuong_theo_lo(so_luong: Decimal, kich_thuoc_lo: int) -> Decimal:
    if so_luong <= 0:
        return SO_KHONG
    lo = Decimal(kich_thuoc_lo)
    return (so_luong // lo) * lo


def _gia_khop(gia_mo_cua: Decimal, chieu: str, truot_gia_bps: Decimal) -> Decimal:
    ty_le = truot_gia_bps / MUOI_NGHIN
    ket_qua = gia_mo_cua * (MOT + ty_le if chieu == "MUA" else MOT - ty_le)
    if ket_qua <= 0:
        raise ValueError("Gia khop phai duong.")
    return ket_qua


def _thuc_thi_lenh(
    ngay: date,
    cac_lenh: list[lenh],
    *,
    tien_mat: Decimal,
    cac_vi_the: dict[str, vi_the],
    bang_gia: dict[tuple[date, str], thanh_gia],
    cau_hinh: cau_hinh_mo_phong,
) -> tuple[Decimal, list[khop_lenh], Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    cac_khop: list[khop_lenh] = []
    tien_mua = tien_ban = SO_KHONG
    phi_mua = phi_ban = thue_ban = SO_KHONG
    tong_truot_gia = lai_lo_da_thuc_hien = SO_KHONG
    thu_tu = sorted(cac_lenh, key=lambda muc: (0 if muc.chieu == "BAN" else 1, muc.ma, muc.ma_lenh))
    for muc in thu_tu:
        if muc.trang_thai != "cho_khop":
            continue
        bar = bang_gia.get((ngay, muc.ma))
        if bar is None:
            muc.trang_thai = "het_han"
            muc.ly_do_tu_choi_hoac_het_han = "thieu_bar_ngay_thuc_thi"
            continue
        if bar.gia_mo_cua is None:
            muc.trang_thai = "het_han"
            muc.ly_do_tu_choi_hoac_het_han = "thieu_gia_mo_cua_ngay_thuc_thi"
            continue
        gia_khop = _gia_khop(bar.gia_mo_cua, muc.chieu, cau_hinh.truot_gia_bps)
        assert muc.so_luong_yeu_cau is not None
        if muc.chieu == "MUA":
            chi_phi_moi_cp = gia_khop * (MOT + cau_hinh.phi_mua_bps / MUOI_NGHIN)
            if chi_phi_moi_cp <= 0:
                raise ValueError("Chi phi mua moi co phieu phai duong.")
            toi_da = _lam_tron_xuong_theo_lo(tien_mat / chi_phi_moi_cp, cau_hinh.kich_thuoc_lo)
            chap_nhan = _lam_tron_xuong_theo_lo(min(muc.so_luong_yeu_cau, toi_da), cau_hinh.kich_thuoc_lo)
            muc.so_luong = chap_nhan
            muc.so_luong_bi_giam = muc.so_luong_yeu_cau - chap_nhan
            if muc.so_luong_bi_giam > 0:
                muc.ly_do_giam = "gioi_han_suc_mua_sau_phi_va_truot_gia"
            if chap_nhan <= 0:
                muc.trang_thai = "tu_choi"
                muc.ly_do_tu_choi_hoac_het_han = "khong_du_tien_mat_cho_mot_lo"
                continue
        elif muc.so_luong <= 0:
            muc.trang_thai = "tu_choi"
            muc.ly_do_tu_choi_hoac_het_han = "so_luong_khong_duong"
            continue
        gia_tri = gia_khop * muc.so_luong
        if gia_tri <= 0:
            raise ValueError("Gia tri giao dich phai duong.")
        truot_gia = abs(gia_khop - bar.gia_mo_cua) * muc.so_luong
        if muc.chieu == "BAN":
            vi_tri = cac_vi_the.get(muc.ma)
            if vi_tri is None or muc.so_luong > vi_tri.so_luong:
                muc.trang_thai = "tu_choi"
                muc.ly_do_tu_choi_hoac_het_han = "ban_vuot_vi_the"
                continue
            phi = gia_tri * cau_hinh.phi_ban_bps / MUOI_NGHIN
            thue = gia_tri * cau_hinh.thue_ban_bps / MUOI_NGHIN
            tien_rong = gia_tri - phi - thue
            if tien_rong < 0:
                raise ValueError("Phi va thue tao tien ban rong am.")
            lai_lo_da_thuc_hien += (gia_khop - vi_tri.gia_von) * muc.so_luong
            vi_tri.so_luong -= muc.so_luong
            if vi_tri.so_luong < 0:
                raise AssertionError("Bat bien vi the am bi vi pham.")
            if vi_tri.so_luong == 0:
                vi_tri.gia_von = SO_KHONG
            tien_mat += tien_rong
            tien_ban += gia_tri
            phi_ban += phi
            thue_ban += thue
        else:
            phi = gia_tri * cau_hinh.phi_mua_bps / MUOI_NGHIN
            thue = SO_KHONG
            tong_tien = gia_tri + phi
            if tong_tien > tien_mat + SAI_SO_TIEN_MAT:
                raise AssertionError("Bo dinh co suc mua de tien mat am.")
            vi_tri = cac_vi_the.setdefault(muc.ma, vi_the(muc.ma))
            so_luong_moi = vi_tri.so_luong + muc.so_luong
            vi_tri.gia_von = (vi_tri.so_luong * vi_tri.gia_von + gia_tri) / so_luong_moi
            vi_tri.so_luong = so_luong_moi
            tien_mat -= tong_tien
            if tien_mat < -SAI_SO_TIEN_MAT:
                raise AssertionError("Bat bien tien mat am bi vi pham.")
            if tien_mat < 0:
                tien_mat = SO_KHONG
            tien_mua += gia_tri
            phi_mua += phi
        tong_truot_gia += truot_gia
        muc.trang_thai = "da_khop"
        cac_khop.append(khop_lenh(
            ma_lenh=muc.ma_lenh, ma=muc.ma, ngay_khop=ngay, chieu=muc.chieu,
            so_luong=muc.so_luong, gia_mo_cua=bar.gia_mo_cua, gia_khop=gia_khop,
            gia_tri_giao_dich=gia_tri, phi=phi, thue=thue,
            chi_phi_truot_gia=truot_gia, so_luong_yeu_cau=muc.so_luong_yeu_cau,
            so_luong_bi_giam=muc.so_luong_bi_giam, ly_do_giam=muc.ly_do_giam,
        ))
    return tien_mat, cac_khop, tien_mua, tien_ban, phi_mua, phi_ban, thue_ban, tong_truot_gia, lai_lo_da_thuc_hien
