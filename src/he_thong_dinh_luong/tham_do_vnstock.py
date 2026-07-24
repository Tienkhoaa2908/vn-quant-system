"""Thăm dò nhỏ giao diện và phản hồi thật của Vnstock 4.0.4."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .du_lieu_thi_truong.luu_tru import kho_luu_tru
from .du_lieu_thi_truong.nguon_vnstock import nguon_vnstock
from .du_lieu_thi_truong.quy_trinh import lam_sach_loi, tao_ma_lan_chay


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    bo_phan_tich = argparse.ArgumentParser(
        description="Tham do Vnstock 4.0.4 cho tung ma, khong luu du lieu thi truong day du."
    )
    bo_phan_tich.add_argument("--ma", nargs="+", default=["FPT", "HPG", "MBB"])
    bo_phan_tich.add_argument("--ngay_bat_dau", required=True)
    bo_phan_tich.add_argument("--ngay_ket_thuc", required=True)
    bo_phan_tich.add_argument("--thu_muc_du_lieu", default="du_lieu")
    return bo_phan_tich


def chay() -> int:
    tham_so = tao_bo_phan_tich().parse_args()
    ngay_bat_dau = date.fromisoformat(tham_so.ngay_bat_dau).isoformat()
    ngay_ket_thuc = date.fromisoformat(tham_so.ngay_ket_thuc).isoformat()
    if ngay_bat_dau > ngay_ket_thuc:
        raise SystemExit("ngay_bat_dau phai khong sau ngay_ket_thuc")

    nguon = nguon_vnstock()
    ket_qua: list[dict[str, object]] = []
    for ma_ban_dau in tham_so.ma:
        ma = ma_ban_dau.strip().upper()
        try:
            bang = nguon.lay_du_lieu(ma, ngay_bat_dau, ngay_ket_thuc)
            cac_ngay = sorted(str(dong["time"])[:10] for dong in bang.cac_dong)
            ket_qua.append(
                {
                    "ma": ma,
                    "trang_thai": "thanh_cong",
                    "so_dong": len(bang.cac_dong),
                    "ngay_dau": cac_ngay[0],
                    "ngay_cuoi": cac_ngay[-1],
                    "ten_cot_nguon": list(bang.cac_cot),
                    "kieu_du_lieu": bang.kieu_du_lieu,
                    "don_vi_gia": bang.don_vi_gia,
                    "ghi_chu_khoi_luong": bang.ghi_chu_khoi_luong,
                    "tham_so_gia": bang.tham_so_gia,
                }
            )
        except Exception as exc:
            ket_qua.append(
                {
                    "ma": ma,
                    "trang_thai": "that_bai",
                    "loi": lam_sach_loi(exc),
                }
            )

    ma_lan_chay = tao_ma_lan_chay()
    bao_cao = {
        "ma_lan_chay": ma_lan_chay,
        "nguon": nguon.ten_nguon,
        "phien_ban": nguon.phien_ban,
        "cach_goi": "Market().equity/index(symbol).ohlcv(start, end, interval='1D', source='kbs')",
        "ho_tro_chon_gia_dieu_chinh": False,
        "ten_tham_so_gia": None,
        "ngay_bat_dau": ngay_bat_dau,
        "ngay_ket_thuc": ngay_ket_thuc,
        "trang_thai_tung_ma": ket_qua,
    }
    kho = kho_luu_tru(Path(tham_so.thu_muc_du_lieu))
    duong_dan, _ = kho.ghi_json("tham_do", ma_lan_chay, "ket_qua.json", bao_cao)
    bao_cao["duong_dan_bao_cao"] = str(duong_dan)
    print(json.dumps(bao_cao, ensure_ascii=False, indent=2, sort_keys=True))

    bat_buoc = {"FPT", "HPG", "MBB"}.intersection(
        ma.strip().upper() for ma in tham_so.ma
    )
    that_bai = {
        str(muc["ma"])
        for muc in ket_qua
        if muc["trang_thai"] == "that_bai"
    }
    return 2 if bat_buoc.intersection(that_bai) else 0


if __name__ == "__main__":
    raise SystemExit(chay())
