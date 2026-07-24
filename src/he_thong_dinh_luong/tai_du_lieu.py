"""Lệnh tải thật nhỏ cho dữ liệu thị trường theo ngày."""

from __future__ import annotations

import argparse
import json
from datetime import date

from .du_lieu_thi_truong.nguon_vnstock import nguon_vnstock
from .du_lieu_thi_truong.quy_trinh import chay_quy_trinh
from .du_lieu_thi_truong.tham_so_vnstock import SO_NEN_MAC_DINH, so_nguyen_duong

MA_BAT_BUOC = {"FPT", "HPG", "MBB"}


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    bo_phan_tich = argparse.ArgumentParser(
        description="Tai du lieu ngay bang Vnstock 4.0.4, xu ly doc lap theo tung ma.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    bo_phan_tich.add_argument("--ma", nargs="+", required=True)
    bo_phan_tich.add_argument("--ngay_bat_dau", required=True)
    bo_phan_tich.add_argument("--ngay_ket_thuc", required=True)
    bo_phan_tich.add_argument("--ngay_kiem_tra")
    bo_phan_tich.add_argument(
        "--so_nen",
        type=so_nguyen_duong,
        default=SO_NEN_MAC_DINH,
        help="So nen toi da yeu cau Vnstock tra cho moi ma.",
    )
    bo_phan_tich.add_argument("--thu_muc_du_lieu", default="du_lieu")
    return bo_phan_tich


def chay() -> int:
    tham_so = tao_bo_phan_tich().parse_args()
    ngay_bat_dau = date.fromisoformat(tham_so.ngay_bat_dau)
    ngay_ket_thuc = date.fromisoformat(tham_so.ngay_ket_thuc)
    ngay_kiem_tra = (
        date.fromisoformat(tham_so.ngay_kiem_tra)
        if tham_so.ngay_kiem_tra
        else date.today()
    )
    if ngay_bat_dau > ngay_ket_thuc:
        raise SystemExit("ngay_bat_dau phai khong sau ngay_ket_thuc")
    if ngay_ket_thuc > ngay_kiem_tra:
        raise SystemExit("ngay_ket_thuc khong duoc sau ngay_kiem_tra")

    cac_ma = tuple(dict.fromkeys(ma.strip().upper() for ma in tham_so.ma if ma.strip()))
    ket_qua = chay_quy_trinh(
        nguon_vnstock(so_nen=tham_so.so_nen),
        cac_ma,
        ngay_bat_dau.isoformat(),
        ngay_ket_thuc.isoformat(),
        tham_so.thu_muc_du_lieu,
        ngay_kiem_tra,
    )
    bao_cao = ket_qua.thanh_tu_dien()
    bao_cao["so_nen_yeu_cau"] = tham_so.so_nen
    print(json.dumps(bao_cao, ensure_ascii=False, indent=2, sort_keys=True))

    trang_thai = {muc.ma: muc.trang_thai for muc in ket_qua.trang_thai_tung_ma}
    bat_buoc_trong_lan_chay = MA_BAT_BUOC.intersection(cac_ma)
    if bat_buoc_trong_lan_chay:
        return 2 if any(trang_thai.get(ma) != "thanh_cong" for ma in bat_buoc_trong_lan_chay) else 0
    return 2 if any(gia_tri != "thanh_cong" for gia_tri in trang_thai.values()) else 0


if __name__ == "__main__":
    raise SystemExit(chay())
