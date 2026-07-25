"""Bo may mo phong giao dich long-only, khong nhin truoc."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable

from .mo_hinh import (
    MOT,
    SO_KHONG,
    cau_hinh_mo_phong,
    dong_nav,
    dong_so_cai,
    dong_vi_the,
    ket_qua_mo_phong,
    khop_lenh,
    lenh,
    su_kien_doanh_nghiep,
    thanh_gia,
    ty_trong_muc_tieu,
    vi_the,
)

MUOI_NGHIN = Decimal("10000")
SAI_SO_TIEN_MAT = Decimal("0.000000001")


def _lam_tron_xuong_theo_lo(so_luong: Decimal, kich_thuoc_lo: int) -> Decimal:
    if so_luong <= 0:
        return SO_KHONG
    lo = Decimal(kich_thuoc_lo)
    return (so_luong // lo) * lo


def _chi_so_ngay(cac_ngay: list[date]) -> dict[date, int]:
    return {ngay: vi_tri for vi_tri, ngay in enumerate(cac_ngay)}


def _ngay_ke_tiep(cac_ngay: list[date], chi_so: dict[date, int], ngay: date) -> date | None:
    vi_tri = chi_so[ngay] + 1
    return cac_ngay[vi_tri] if vi_tri < len(cac_ngay) else None


def _gia_khop(gia_mo_cua: Decimal, chieu: str, truot_gia_bps: Decimal) -> Decimal:
    ty_le = truot_gia_bps / MUOI_NGHIN
    return gia_mo_cua * (MOT + ty_le if chieu == "MUA" else MOT - ty_le)


def _danh_dau_vi_the(
    ngay: date,
    cac_vi_the: dict[str, vi_the],
    bang_gia: dict[tuple[date, str], thanh_gia],
) -> tuple[Decimal, list[dong_vi_the]]:
    tong = SO_KHONG
    cac_dong: list[dong_vi_the] = []
    for ma in sorted(cac_vi_the):
        vi_tri = cac_vi_the[ma]
        if vi_tri.so_luong <= 0:
            continue
        bar = bang_gia.get((ngay, ma))
        if bar is None:
            raise ValueError(
                f"Khong co bar de dinh gia vi the {ma} tai {ngay}; he thong khong tu dien gia."
            )
        gia_tri = vi_tri.gia_tri_thi_truong(bar.gia_dong_cua)
        tong += gia_tri
        cac_dong.append(
            dong_vi_the(
                ngay=ngay,
                ma=ma,
                so_luong=vi_tri.so_luong,
                gia_von=vi_tri.gia_von,
                gia_dong_cua=bar.gia_dong_cua,
                gia_tri_thi_truong=gia_tri,
                lai_lo_chua_thuc_hien=vi_tri.lai_lo_chua_thuc_hien(
                    bar.gia_dong_cua
                ),
            )
        )
    return tong, cac_dong


def _ap_dung_su_kien(
    ngay: date,
    cac_su_kien: Iterable[su_kien_doanh_nghiep],
    cac_vi_the: dict[str, vi_the],
    cac_lenh_cho: Iterable[lenh] = (),
) -> tuple[Decimal, list[dict[str, object]]]:
    dong_tien = SO_KHONG
    da_ap_dung: list[dict[str, object]] = []
    for su_kien in cac_su_kien:
        vi_tri = cac_vi_the.get(su_kien.ma)
        if su_kien.loai_su_kien in {
            "chia_tach",
            "co_phieu_thuong",
            "chia_tach_hoac_thuong_co_phieu",
        }:
            if su_kien.ngay_hieu_luc != ngay:
                continue
            so_luong_truoc = vi_tri.so_luong if vi_tri else SO_KHONG
            gia_von_truoc = vi_tri.gia_von if vi_tri else SO_KHONG
            if vi_tri and vi_tri.so_luong > 0:
                assert su_kien.ty_le is not None
                vi_tri.so_luong *= su_kien.ty_le
                vi_tri.gia_von /= su_kien.ty_le
            for muc_lenh in cac_lenh_cho:
                if muc_lenh.ma == su_kien.ma and muc_lenh.trang_thai == "cho_khop":
                    muc_lenh.so_luong *= su_kien.ty_le
            da_ap_dung.append(
                {
                    "ngay": ngay,
                    "ma": su_kien.ma,
                    "loai_su_kien": su_kien.loai_su_kien,
                    "so_luong_truoc": so_luong_truoc,
                    "so_luong_sau": vi_tri.so_luong if vi_tri else SO_KHONG,
                    "gia_von_truoc": gia_von_truoc,
                    "gia_von_sau": vi_tri.gia_von if vi_tri else SO_KHONG,
                    "dong_tien": SO_KHONG,
                    "nguon": su_kien.nguon,
                    "phien_ban": su_kien.phien_ban,
                }
            )
        elif su_kien.loai_su_kien == "co_tuc_tien_mat":
            if su_kien.ngay_thanh_toan != ngay:
                continue
            assert su_kien.gia_tri_tien_mat is not None
            so_luong = vi_tri.so_luong if vi_tri else SO_KHONG
            tien = so_luong * su_kien.gia_tri_tien_mat
            dong_tien += tien
            da_ap_dung.append(
                {
                    "ngay": ngay,
                    "ma": su_kien.ma,
                    "loai_su_kien": su_kien.loai_su_kien,
                    "so_luong_truoc": so_luong,
                    "so_luong_sau": so_luong,
                    "gia_von_truoc": vi_tri.gia_von if vi_tri else SO_KHONG,
                    "gia_von_sau": vi_tri.gia_von if vi_tri else SO_KHONG,
                    "dong_tien": tien,
                    "nguon": su_kien.nguon,
                    "phien_ban": su_kien.phien_ban,
                }
            )
    return dong_tien, da_ap_dung


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
) -> list[lenh]:
    cac_ma = set(muc_tieu)
    if cau_hinh.che_do_ma_khong_xuat_hien == "muc_tieu_bang_0":
        cac_ma.update(ma for ma, vt in cac_vi_the.items() if vt.so_luong > 0)
    ket_qua: list[lenh] = []
    so_thu_tu = so_thu_tu_bat_dau
    for ma in sorted(cac_ma):
        trong_so = muc_tieu.get(ma)
        if trong_so is None:
            trong_so = SO_KHONG
        so_luong_hien_tai = cac_vi_the.get(ma, vi_the(ma)).so_luong
        if trong_so == 0 and so_luong_hien_tai <= 0:
            continue
        bar = bang_gia.get((ngay_tin_hieu, ma))
        if bar is None:
            raise ValueError(
                f"Khong co bar tai ngay tin hieu {ngay_tin_hieu} cho {ma}."
            )
        so_luong_muc_tieu = nav_tham_chieu * trong_so / bar.gia_dong_cua
        chenhlech = so_luong_muc_tieu - so_luong_hien_tai
        if chenhlech > 0:
            if bar.thuoc_tap_co_phieu is False or bar.dat_thanh_khoan is False:
                continue
            so_luong = _lam_tron_xuong_theo_lo(
                chenhlech, cau_hinh.kich_thuoc_lo
            )
            chieu = "MUA"
        else:
            can_ban = -chenhlech
            if (
                trong_so == 0
                and cau_hinh.cho_phep_ban_le_khi_dong_vi_the
                and so_luong_hien_tai > 0
            ):
                so_luong = so_luong_hien_tai
            else:
                so_luong = _lam_tron_xuong_theo_lo(
                    can_ban, cau_hinh.kich_thuoc_lo
                )
            chieu = "BAN"
        if so_luong <= 0:
            continue
        so_thu_tu += 1
        muc = lenh(
            ma_lenh=f"L{so_thu_tu:08d}",
            ngay_tin_hieu=ngay_tin_hieu,
            ngay_thuc_thi=ngay_thuc_thi,
            ma=ma,
            chieu=chieu,
            so_luong=so_luong,
        )
        if ngay_thuc_thi is None:
            muc.trang_thai = "het_han"
            muc.ly_do_tu_choi_hoac_het_han = "khong_co_phien_thi_truong_ke_tiep"
        ket_qua.append(muc)
    return ket_qua


def _thuc_thi_lenh(
    ngay: date,
    cac_lenh: list[lenh],
    *,
    tien_mat: Decimal,
    cac_vi_the: dict[str, vi_the],
    bang_gia: dict[tuple[date, str], thanh_gia],
    cau_hinh: cau_hinh_mo_phong,
) -> tuple[Decimal, list[khop_lenh], Decimal, Decimal, Decimal, Decimal]:
    cac_khop: list[khop_lenh] = []
    tien_mua = SO_KHONG
    tien_ban = SO_KHONG
    tong_phi = SO_KHONG
    tong_thue = SO_KHONG
    thu_tu = sorted(cac_lenh, key=lambda muc: (0 if muc.chieu == "BAN" else 1, muc.ma))
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
        gia_tri = gia_khop * muc.so_luong
        phi_bps = cau_hinh.phi_mua_bps if muc.chieu == "MUA" else cau_hinh.phi_ban_bps
        phi = gia_tri * phi_bps / MUOI_NGHIN
        thue = gia_tri * cau_hinh.thue_ban_bps / MUOI_NGHIN if muc.chieu == "BAN" else SO_KHONG
        truot_gia = abs(gia_khop - bar.gia_mo_cua) * muc.so_luong

        if muc.chieu == "BAN":
            vi_tri = cac_vi_the.get(muc.ma)
            if vi_tri is None or muc.so_luong > vi_tri.so_luong:
                muc.trang_thai = "tu_choi"
                muc.ly_do_tu_choi_hoac_het_han = "ban_vuot_vi_the"
                continue
            vi_tri.so_luong -= muc.so_luong
            if vi_tri.so_luong < 0:
                raise AssertionError("Bat bien vi the am bi vi pham.")
            if vi_tri.so_luong == 0:
                vi_tri.gia_von = SO_KHONG
            tien_mat += gia_tri - phi - thue
            tien_ban += gia_tri
        else:
            tong_tien = gia_tri + phi
            if tong_tien > tien_mat + SAI_SO_TIEN_MAT:
                muc.trang_thai = "tu_choi"
                muc.ly_do_tu_choi_hoac_het_han = "khong_du_tien_mat"
                continue
            vi_tri = cac_vi_the.setdefault(muc.ma, vi_the(muc.ma))
            so_luong_moi = vi_tri.so_luong + muc.so_luong
            tong_gia_von = vi_tri.so_luong * vi_tri.gia_von + gia_tri
            vi_tri.so_luong = so_luong_moi
            vi_tri.gia_von = tong_gia_von / so_luong_moi
            tien_mat -= tong_tien
            if tien_mat < -SAI_SO_TIEN_MAT:
                raise AssertionError("Bat bien tien mat am bi vi pham.")
            if tien_mat < 0:
                tien_mat = SO_KHONG
            tien_mua += gia_tri
        tong_phi += phi
        tong_thue += thue
        muc.trang_thai = "da_khop"
        cac_khop.append(
            khop_lenh(
                ma_lenh=muc.ma_lenh,
                ma=muc.ma,
                ngay_khop=ngay,
                chieu=muc.chieu,
                so_luong=muc.so_luong,
                gia_mo_cua=bar.gia_mo_cua,
                gia_khop=gia_khop,
                gia_tri_giao_dich=gia_tri,
                phi=phi,
                thue=thue,
                chi_phi_truot_gia=truot_gia,
            )
        )
    return tien_mat, cac_khop, tien_mua, tien_ban, tong_phi, tong_thue


def chay_mo_phong(
    du_lieu_gia: Iterable[thanh_gia],
    cac_ty_trong: Iterable[ty_trong_muc_tieu],
    cau_hinh: cau_hinh_mo_phong,
    cac_su_kien: Iterable[su_kien_doanh_nghiep] = (),
) -> ket_qua_mo_phong:
    """Chay mo phong xac dinh voi cung dau vao va cau hinh."""
    gia = list(du_lieu_gia)
    ty_trong = list(cac_ty_trong)
    su_kien = list(cac_su_kien)
    if not gia:
        raise ValueError("Du lieu gia rong.")
    if su_kien and cau_hinh.co_so_gia == "dieu_chinh":
        raise ValueError(
            "Du lieu gia dieu_chinh kem corporate actions co nguy co tinh hai lan."
        )
    bang_gia = {(muc.ngay, muc.ma): muc for muc in gia}
    if len(bang_gia) != len(gia):
        raise ValueError("Du lieu gia trung ma va ngay.")
    cac_ngay = sorted({muc.ngay for muc in gia})
    chi_so = _chi_so_ngay(cac_ngay)
    for muc in ty_trong:
        if muc.ngay_tin_hieu not in chi_so:
            raise ValueError(
                f"Ngay tin hieu {muc.ngay_tin_hieu} khong phai ngay co du lieu thi truong."
            )
    for muc in su_kien:
        ngay_su_kien = muc.ngay_thanh_toan if muc.loai_su_kien == "co_tuc_tien_mat" else muc.ngay_hieu_luc
        if ngay_su_kien not in chi_so:
            raise ValueError(
                f"Ngay su kien {ngay_su_kien} khong co trong lich mo phong; khong tu doi ngay."
            )

    muc_tieu_theo_ngay: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for muc in ty_trong:
        muc_tieu_theo_ngay[muc.ngay_tin_hieu][muc.ma] = muc.ty_trong
    su_kien_theo_ngay: dict[date, list[su_kien_doanh_nghiep]] = defaultdict(list)
    for muc in su_kien:
        if muc.ngay_hieu_luc is not None:
            su_kien_theo_ngay[muc.ngay_hieu_luc].append(muc)
        if muc.ngay_thanh_toan is not None and muc.ngay_thanh_toan != muc.ngay_hieu_luc:
            su_kien_theo_ngay[muc.ngay_thanh_toan].append(muc)

    ket_qua = ket_qua_mo_phong(cau_hinh=cau_hinh)
    cac_vi_the: dict[str, vi_the] = {}
    lenh_cho_theo_ngay: dict[date, list[lenh]] = defaultdict(list)
    tien_mat = cau_hinh.von_ban_dau
    nav_truoc = cau_hinh.von_ban_dau

    for ngay in cac_ngay:
        tien_mat_dau_ngay = tien_mat
        dong_tien_su_kien, su_kien_da_ap_dung = _ap_dung_su_kien(
            ngay, su_kien_theo_ngay.get(ngay, ()), cac_vi_the,
            lenh_cho_theo_ngay.get(ngay, ()),
        )
        tien_mat += dong_tien_su_kien
        ket_qua.su_kien_da_ap_dung.extend(su_kien_da_ap_dung)

        tien_mat, cac_khop, tien_mua, tien_ban, phi, thue = _thuc_thi_lenh(
            ngay, lenh_cho_theo_ngay.get(ngay, []), tien_mat=tien_mat,
            cac_vi_the=cac_vi_the, bang_gia=bang_gia, cau_hinh=cau_hinh,
        )
        ket_qua.khop_lenh.extend(cac_khop)
        gia_tri_vi_the, cac_dong_vi_the = _danh_dau_vi_the(ngay, cac_vi_the, bang_gia)
        ket_qua.vi_the_hang_ngay.extend(cac_dong_vi_the)
        nav = tien_mat + gia_tri_vi_the
        loi_nhuan = nav / nav_truoc - MOT if nav_truoc != 0 else None
        ty_trong_tien_mat = tien_mat / nav if nav != 0 else None
        ket_qua.so_cai.append(dong_so_cai(
            ngay, tien_mat_dau_ngay, dong_tien_su_kien, tien_mua, tien_ban,
            phi, thue, tien_mat, gia_tri_vi_the, nav,
        ))
        ket_qua.nav.append(dong_nav(ngay, nav, loi_nhuan, tien_mat, ty_trong_tien_mat))
        nav_truoc = nav

        if ngay in muc_tieu_theo_ngay:
            ket_qua.so_lan_tai_can_bang += 1
            ngay_thuc_thi = _ngay_ke_tiep(cac_ngay, chi_so, ngay)
            cac_lenh_moi = _tao_lenh_tai_can_bang(
                ngay_tin_hieu=ngay, ngay_thuc_thi=ngay_thuc_thi,
                nav_tham_chieu=nav, muc_tieu=muc_tieu_theo_ngay[ngay],
                cac_vi_the=cac_vi_the, bang_gia=bang_gia, cau_hinh=cau_hinh,
                so_thu_tu_bat_dau=len(ket_qua.lenh),
            )
            ket_qua.lenh.extend(cac_lenh_moi)
            if ngay_thuc_thi is not None:
                lenh_cho_theo_ngay[ngay_thuc_thi].extend(cac_lenh_moi)

    if tien_mat < -SAI_SO_TIEN_MAT:
        raise AssertionError("Tien mat cuoi ky am.")
    if any(muc.so_luong < 0 for muc in cac_vi_the.values()):
        raise AssertionError("Vi the cuoi ky am.")
    return ket_qua
