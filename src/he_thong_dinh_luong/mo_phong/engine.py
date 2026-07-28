"""Bo may mo phong giao dich long-only, khong nhin truoc."""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable

from .khop_lenh import SAI_SO_TIEN_MAT, _lam_tron_xuong_theo_lo, _thuc_thi_lenh
from .mo_hinh import (
    CO_SO_GIA_CHUA_XAC_NHAN, CO_SO_GIA_DIEU_CHINH, MOT,
    PRICE_BASIS_UNCONFIRMED, SO_KHONG, cau_hinh_mo_phong,
    dong_nav, dong_so_cai, dong_vi_the,
    ket_qua_mo_phong, lenh, su_kien_doanh_nghiep, thanh_gia,
    ty_trong_muc_tieu, vi_the,
)
from .su_kien_doanh_nghiep import _ap_dung_su_kien


def _chi_so_ngay(cac_ngay: list[date]) -> dict[date, int]:
    return {ngay: vi_tri for vi_tri, ngay in enumerate(cac_ngay)}


def _ngay_ke_tiep(cac_ngay: list[date], chi_so: dict[date, int], ngay: date) -> date | None:
    vi_tri = chi_so[ngay] + 1
    return cac_ngay[vi_tri] if vi_tri < len(cac_ngay) else None


def _danh_dau_vi_the(
    ngay: date,
    cac_vi_the: dict[str, vi_the],
    bang_gia: dict[tuple[date, str], thanh_gia],
) -> tuple[Decimal, Decimal, list[dong_vi_the]]:
    tong_gia_tri = SO_KHONG
    tong_lai_lo_chua_thuc_hien = SO_KHONG
    cac_dong: list[dong_vi_the] = []
    for ma in sorted(cac_vi_the):
        vi_tri = cac_vi_the[ma]
        if vi_tri.so_luong <= 0:
            continue
        bar = bang_gia.get((ngay, ma))
        if bar is None:
            raise ValueError(f"Khong co bar de dinh gia vi the {ma} tai {ngay}; he thong khong tu dien gia.")
        gia_tri = vi_tri.gia_tri_thi_truong(bar.gia_dong_cua)
        lai_lo = vi_tri.lai_lo_chua_thuc_hien(bar.gia_dong_cua)
        tong_gia_tri += gia_tri
        tong_lai_lo_chua_thuc_hien += lai_lo
        cac_dong.append(dong_vi_the(
            ngay=ngay, ma=ma, so_luong=vi_tri.so_luong, gia_von=vi_tri.gia_von,
            gia_dong_cua=bar.gia_dong_cua, gia_tri_thi_truong=gia_tri,
            lai_lo_chua_thuc_hien=lai_lo,
        ))
    return tong_gia_tri, tong_lai_lo_chua_thuc_hien, cac_dong


def _tao_lenh_tai_can_bang(
    *,
    ngay_tin_hieu: date,
    ngay_thuc_thi: date | None,
    nav_tham_chieu: Decimal,
    muc_tieu: dict[str, Decimal],
    cac_vi_the: dict[str, vi_the],
    bang_gia: dict[tuple[date, str], thanh_gia],
    cau_hinh: cau_hinh_mo_phong,
    so_thu_tu_bat_dau: int,
) -> tuple[list[lenh], list[str]]:
    cac_ma = set(muc_tieu)
    if cau_hinh.che_do_ma_khong_xuat_hien == "muc_tieu_bang_0":
        cac_ma.update(ma for ma, vt in cac_vi_the.items() if vt.so_luong > 0)
    ket_qua: list[lenh] = []
    canh_bao: list[str] = []
    so_thu_tu = so_thu_tu_bat_dau
    for ma in sorted(cac_ma):
        trong_so = muc_tieu.get(ma, SO_KHONG)
        so_luong_hien_tai = cac_vi_the.get(ma, vi_the(ma)).so_luong
        if trong_so == 0 and so_luong_hien_tai <= 0:
            continue
        bar = bang_gia.get((ngay_tin_hieu, ma))
        if bar is None:
            raise ValueError(f"Khong co bar tai ngay tin hieu {ngay_tin_hieu} cho {ma}.")
        so_luong_muc_tieu = nav_tham_chieu * trong_so / bar.gia_dong_cua
        chenh_lech = so_luong_muc_tieu - so_luong_hien_tai
        if chenh_lech == 0:
            continue
        if chenh_lech > 0:
            so_luong = _lam_tron_xuong_theo_lo(chenh_lech, cau_hinh.kich_thuoc_lo)
            chieu = "MUA"
        else:
            can_ban = -chenh_lech
            if trong_so == 0 and cau_hinh.cho_phep_ban_le_khi_dong_vi_the and so_luong_hien_tai > 0:
                so_luong = so_luong_hien_tai
            else:
                so_luong = _lam_tron_xuong_theo_lo(can_ban, cau_hinh.kich_thuoc_lo)
            chieu = "BAN"
        if so_luong <= 0:
            continue
        so_thu_tu += 1
        muc = lenh(
            ma_lenh=f"L{so_thu_tu:08d}", ngay_tin_hieu=ngay_tin_hieu,
            ngay_thuc_thi=ngay_thuc_thi, ma=ma, chieu=chieu,
            so_luong=so_luong, so_luong_yeu_cau=so_luong,
        )
        eligibility = bar.thuoc_tap_co_phieu is True and bar.dat_thanh_khoan is True
        if chieu == "MUA" and not eligibility:
            muc.trang_thai = "tu_choi"
            muc.ly_do_tu_choi_hoac_het_han = "eligibility_khong_dat_fail_closed"
        elif chieu == "BAN" and not eligibility:
            canh_bao.append(
                f"{ngay_tin_hieu} {ma}: cho phep giam/dong vi the du eligibility khong dat "
                f"(membership={bar.thuoc_tap_co_phieu}, liquidity={bar.dat_thanh_khoan})."
            )
        if ngay_thuc_thi is None and muc.trang_thai == "cho_khop":
            muc.trang_thai = "het_han"
            muc.ly_do_tu_choi_hoac_het_han = "khong_co_phien_thi_truong_ke_tiep"
        ket_qua.append(muc)
    return ket_qua, canh_bao


def chay_mo_phong(
    du_lieu_gia: Iterable[thanh_gia],
    cac_ty_trong: Iterable[ty_trong_muc_tieu],
    cau_hinh: cau_hinh_mo_phong,
    cac_su_kien: Iterable[su_kien_doanh_nghiep] = (),
) -> ket_qua_mo_phong:
    if not isinstance(cau_hinh, cau_hinh_mo_phong):
        raise TypeError("cau_hinh phai la cau_hinh_mo_phong da duoc xac thuc.")
    gia = list(du_lieu_gia)
    ty_trong = list(cac_ty_trong)
    su_kien = list(cac_su_kien)
    if not gia:
        raise ValueError("Du lieu gia rong.")
    if su_kien and cau_hinh.co_so_gia == CO_SO_GIA_DIEU_CHINH:
        raise ValueError("Du lieu gia dieu_chinh kem corporate actions co nguy co tinh hai lan.")
    if su_kien and cau_hinh.co_so_gia == CO_SO_GIA_CHUA_XAC_NHAN:
        raise ValueError(
            f"{PRICE_BASIS_UNCONFIRMED}: engine khong ap dung corporate actions "
            "khi co_so_gia=CHUA_XAC_NHAN."
        )
    khoa_su_kien = [muc.khoa() for muc in su_kien]
    if len(set(khoa_su_kien)) != len(khoa_su_kien):
        raise ValueError("Trung su kien doanh nghiep.")
    bang_gia = {(muc.ngay, muc.ma): muc for muc in gia}
    if len(bang_gia) != len(gia):
        raise ValueError("Du lieu gia trung ma va ngay.")
    cac_ngay = sorted({muc.ngay for muc in gia})
    chi_so = _chi_so_ngay(cac_ngay)
    for muc in ty_trong:
        if muc.ngay_tin_hieu not in chi_so:
            raise ValueError(f"Ngay tin hieu {muc.ngay_tin_hieu} khong phai ngay co du lieu thi truong.")
    for muc in su_kien:
        cac_ngay_bat_buoc = [muc.ngay_hieu_luc]
        if muc.loai_su_kien == "co_tuc_tien_mat":
            cac_ngay_bat_buoc.append(muc.ngay_thanh_toan)
        for ngay_su_kien in cac_ngay_bat_buoc:
            if ngay_su_kien not in chi_so:
                raise ValueError(f"Ngay su kien {ngay_su_kien} khong co trong lich mo phong; khong tu doi ngay.")

    muc_tieu_theo_ngay: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for muc in ty_trong:
        muc_tieu_theo_ngay[muc.ngay_tin_hieu][muc.ma] = muc.ty_trong
    su_kien_theo_ngay: dict[date, list[su_kien_doanh_nghiep]] = defaultdict(list)
    for muc in su_kien:
        assert muc.ngay_hieu_luc is not None
        su_kien_theo_ngay[muc.ngay_hieu_luc].append(muc)
        if muc.ngay_thanh_toan is not None and muc.ngay_thanh_toan != muc.ngay_hieu_luc:
            su_kien_theo_ngay[muc.ngay_thanh_toan].append(muc)

    ket_qua = ket_qua_mo_phong(cau_hinh=cau_hinh)
    cac_vi_the: dict[str, vi_the] = {}
    lenh_cho_theo_ngay: dict[date, list[lenh]] = defaultdict(list)
    tien_mat = nav_truoc = cau_hinh.von_ban_dau
    nghia_vu_co_tuc: dict[tuple[object, ...], tuple[Decimal, Decimal]] = {}
    da_chot_quyen: set[tuple[object, ...]] = set()
    da_thanh_toan: set[tuple[object, ...]] = set()
    da_ap_dung_chia_tach: set[tuple[object, ...]] = set()
    realized_luy_ke = co_tuc_luy_ke = SO_KHONG
    phi_mua_luy_ke = phi_ban_luy_ke = thue_ban_luy_ke = SO_KHONG

    for ngay in cac_ngay:
        tien_mat_dau_ngay = tien_mat
        dong_tien_su_kien, su_kien_da_ap_dung = _ap_dung_su_kien(
            ngay, su_kien_theo_ngay.get(ngay, ()), cac_vi_the,
            lenh_cho_theo_ngay.get(ngay, ()), nghia_vu_co_tuc=nghia_vu_co_tuc,
            da_chot_quyen=da_chot_quyen, da_thanh_toan=da_thanh_toan,
            da_ap_dung_chia_tach=da_ap_dung_chia_tach,
        )
        tien_mat += dong_tien_su_kien
        co_tuc_luy_ke += dong_tien_su_kien
        ket_qua.su_kien_da_ap_dung.extend(su_kien_da_ap_dung)
        (
            tien_mat, cac_khop, tien_mua, tien_ban, phi_mua, phi_ban,
            thue_ban, chi_phi_truot_gia, realized,
        ) = _thuc_thi_lenh(
            ngay, lenh_cho_theo_ngay.get(ngay, []), tien_mat=tien_mat,
            cac_vi_the=cac_vi_the, bang_gia=bang_gia, cau_hinh=cau_hinh,
        )
        ket_qua.khop_lenh.extend(cac_khop)
        realized_luy_ke += realized
        phi_mua_luy_ke += phi_mua
        phi_ban_luy_ke += phi_ban
        thue_ban_luy_ke += thue_ban
        gia_tri_vi_the, unrealized, cac_dong_vi_the = _danh_dau_vi_the(ngay, cac_vi_the, bang_gia)
        ket_qua.vi_the_hang_ngay.extend(cac_dong_vi_the)
        nav = tien_mat + gia_tri_vi_the
        nav_doi_soat = (
            cau_hinh.von_ban_dau + realized_luy_ke + unrealized + co_tuc_luy_ke
            - phi_mua_luy_ke - phi_ban_luy_ke - thue_ban_luy_ke
        )
        chenh_lech = nav - nav_doi_soat
        if abs(chenh_lech) > SAI_SO_TIEN_MAT:
            raise AssertionError(f"So cai khong doi soat voi NAV tai {ngay}: {chenh_lech}.")
        loi_nhuan = nav / nav_truoc - MOT if nav_truoc != 0 else None
        ty_trong_tien_mat = tien_mat / nav if nav != 0 else None
        ket_qua.so_cai.append(dong_so_cai(
            ngay=ngay, tien_mat_dau_ngay=tien_mat_dau_ngay,
            dong_tien_su_kien=dong_tien_su_kien, tien_mua=tien_mua,
            tien_ban=tien_ban, phi=phi_mua + phi_ban, thue=thue_ban,
            tien_mat_cuoi_ngay=tien_mat, gia_tri_vi_the=gia_tri_vi_the, nav=nav,
            lai_lo_da_thuc_hien=realized,
            lai_lo_da_thuc_hien_luy_ke=realized_luy_ke,
            lai_lo_chua_thuc_hien=unrealized,
            co_tuc_tien_mat=dong_tien_su_kien,
            co_tuc_tien_mat_luy_ke=co_tuc_luy_ke,
            chi_phi_truot_gia=chi_phi_truot_gia,
            phi_mua=phi_mua, phi_ban=phi_ban, thue_ban=thue_ban,
            phi_mua_luy_ke=phi_mua_luy_ke,
            phi_ban_luy_ke=phi_ban_luy_ke,
            thue_ban_luy_ke=thue_ban_luy_ke,
            chenh_lech_doi_soat=chenh_lech,
        ))
        ket_qua.nav.append(dong_nav(ngay, nav, loi_nhuan, tien_mat, ty_trong_tien_mat))
        nav_truoc = nav
        if ngay in muc_tieu_theo_ngay:
            ket_qua.so_lan_tai_can_bang += 1
            ngay_thuc_thi = _ngay_ke_tiep(cac_ngay, chi_so, ngay)
            cac_lenh_moi, canh_bao = _tao_lenh_tai_can_bang(
                ngay_tin_hieu=ngay, ngay_thuc_thi=ngay_thuc_thi,
                nav_tham_chieu=nav, muc_tieu=muc_tieu_theo_ngay[ngay],
                cac_vi_the=cac_vi_the, bang_gia=bang_gia, cau_hinh=cau_hinh,
                so_thu_tu_bat_dau=len(ket_qua.lenh),
            )
            ket_qua.canh_bao.extend(canh_bao)
            ket_qua.lenh.extend(cac_lenh_moi)
            if ngay_thuc_thi is not None:
                lenh_cho_theo_ngay[ngay_thuc_thi].extend(cac_lenh_moi)
    if tien_mat < -SAI_SO_TIEN_MAT:
        raise AssertionError("Tien mat cuoi ky am.")
    if any(muc.so_luong < 0 for muc in cac_vi_the.values()):
        raise AssertionError("Vi the cuoi ky am.")
    return ket_qua
