"""Ap dung chia tach va chot quyen co tuc tien mat."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Iterable
from .mo_hinh import SO_KHONG, lenh, su_kien_doanh_nghiep, vi_the


def _ap_dung_su_kien(
    ngay: date,
    cac_su_kien: Iterable[su_kien_doanh_nghiep],
    cac_vi_the: dict[str, vi_the],
    cac_lenh_cho: Iterable[lenh],
    *,
    nghia_vu_co_tuc: dict[tuple[object, ...], tuple[Decimal, Decimal]],
    da_chot_quyen: set[tuple[object, ...]],
    da_thanh_toan: set[tuple[object, ...]],
    da_ap_dung_chia_tach: set[tuple[object, ...]],
) -> tuple[Decimal, list[dict[str, object]]]:
    dong_tien = SO_KHONG
    da_ap_dung: list[dict[str, object]] = []
    for su_kien in sorted(cac_su_kien, key=lambda muc: (muc.ma, muc.loai_su_kien, muc.khoa())):
        khoa = su_kien.khoa()
        vi_tri = cac_vi_the.get(su_kien.ma)
        if su_kien.loai_su_kien in {"chia_tach", "co_phieu_thuong", "chia_tach_hoac_thuong_co_phieu"}:
            if su_kien.ngay_hieu_luc != ngay or khoa in da_ap_dung_chia_tach:
                continue
            assert su_kien.ty_le is not None
            so_luong_truoc = vi_tri.so_luong if vi_tri else SO_KHONG
            gia_von_truoc = vi_tri.gia_von if vi_tri else SO_KHONG
            if vi_tri and vi_tri.so_luong > 0:
                vi_tri.so_luong *= su_kien.ty_le
                vi_tri.gia_von /= su_kien.ty_le
            for muc_lenh in cac_lenh_cho:
                if muc_lenh.ma == su_kien.ma and muc_lenh.trang_thai == "cho_khop":
                    muc_lenh.so_luong *= su_kien.ty_le
                    assert muc_lenh.so_luong_yeu_cau is not None
                    muc_lenh.so_luong_yeu_cau *= su_kien.ty_le
                    muc_lenh.so_luong_bi_giam *= su_kien.ty_le
            da_ap_dung_chia_tach.add(khoa)
            da_ap_dung.append({
                "ngay": ngay, "hanh_dong": "ap_dung_ty_le", "ma": su_kien.ma,
                "loai_su_kien": su_kien.loai_su_kien, "so_luong_truoc": so_luong_truoc,
                "so_luong_sau": vi_tri.so_luong if vi_tri else SO_KHONG,
                "gia_von_truoc": gia_von_truoc,
                "gia_von_sau": vi_tri.gia_von if vi_tri else SO_KHONG,
                "dong_tien": SO_KHONG, "nguon": su_kien.nguon, "phien_ban": su_kien.phien_ban,
            })
            continue
        if su_kien.loai_su_kien != "co_tuc_tien_mat":
            continue
        assert su_kien.gia_tri_tien_mat is not None
        if su_kien.ngay_hieu_luc == ngay and khoa not in da_chot_quyen:
            so_luong_chot = vi_tri.so_luong if vi_tri else SO_KHONG
            so_tien_phai_tra = so_luong_chot * su_kien.gia_tri_tien_mat
            nghia_vu_co_tuc[khoa] = (so_luong_chot, so_tien_phai_tra)
            da_chot_quyen.add(khoa)
            da_ap_dung.append({
                "ngay": ngay, "hanh_dong": "chot_quyen", "ma": su_kien.ma,
                "loai_su_kien": su_kien.loai_su_kien,
                "so_luong_duoc_huong": so_luong_chot,
                "gia_tri_tien_mat_moi_co_phieu": su_kien.gia_tri_tien_mat,
                "dong_tien": SO_KHONG, "ngay_thanh_toan": su_kien.ngay_thanh_toan,
                "nguon": su_kien.nguon, "phien_ban": su_kien.phien_ban,
            })
        if su_kien.ngay_thanh_toan == ngay and khoa not in da_thanh_toan:
            if khoa not in nghia_vu_co_tuc:
                raise AssertionError("Co tuc chua duoc chot quyen truoc khi thanh toan.")
            so_luong_chot, tien = nghia_vu_co_tuc[khoa]
            dong_tien += tien
            da_thanh_toan.add(khoa)
            da_ap_dung.append({
                "ngay": ngay, "hanh_dong": "thanh_toan", "ma": su_kien.ma,
                "loai_su_kien": su_kien.loai_su_kien,
                "so_luong_duoc_huong": so_luong_chot,
                "gia_tri_tien_mat_moi_co_phieu": su_kien.gia_tri_tien_mat,
                "dong_tien": tien, "ngay_hieu_luc": su_kien.ngay_hieu_luc,
                "nguon": su_kien.nguon, "phien_ban": su_kien.phien_ban,
            })
    return dong_tien, da_ap_dung
