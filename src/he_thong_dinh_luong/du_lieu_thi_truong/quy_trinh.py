"""Điều phối luồng tải, lưu, chuẩn hóa và kiểm tra dữ liệu."""

from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from ..kiem_tra_du_lieu import CAC_COT_BAT_BUOC, kiem_tra_cac_dong
from .chuan_hoa import chuan_hoa_bang
from .luu_tru import kho_luu_tru
from .mo_hinh import (
    bang_du_lieu_nguon,
    ket_qua_lan_chay,
    khong_co_du_lieu,
    loi_nguon_du_lieu,
    trang_thai_ma,
)
from .nguon import nguon_du_lieu


def tao_ma_lan_chay() -> str:
    thoi_gian = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{thoi_gian}_{uuid.uuid4().hex[:8]}"


def lam_sach_loi(loi: BaseException) -> str:
    noi_dung = str(loi)
    for ten, gia_tri in os.environ.items():
        if gia_tri and any(tu in ten.upper() for tu in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            noi_dung = noi_dung.replace(gia_tri, "[DA_AN]")
    cac_mau = (
        r"vnstock_[A-Za-z0-9_-]+",
        r"(?i)(api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+",
        r"(?i)bearer\s+[A-Za-z0-9._~-]+",
    )
    for mau in cac_mau:
        noi_dung = re.sub(mau, "[DA_AN]", noi_dung)
    return noi_dung[:2000]


def _lay_voi_thu_lai(
    nguon: nguon_du_lieu,
    ma: str,
    ngay_bat_dau: str,
    ngay_ket_thuc: str,
    so_lan_thu_toi_da: int,
    ham_cho: Callable[[float], None],
) -> tuple[bang_du_lieu_nguon, int]:
    lan_thu = 0
    while True:
        lan_thu += 1
        try:
            bang = nguon.lay_du_lieu(ma, ngay_bat_dau, ngay_ket_thuc)
            if not bang.cac_dong:
                raise khong_co_du_lieu(f"Nguon khong tra du lieu cho {ma}.")
            return bang, lan_thu
        except loi_nguon_du_lieu as exc:
            if not exc.tam_thoi or lan_thu >= so_lan_thu_toi_da:
                raise
            ham_cho(float(2 ** (lan_thu - 1)))


def _ngay_dau_cuoi(cac_dong: list[dict[str, object]]) -> tuple[str | None, str | None]:
    if not cac_dong:
        return None, None
    cac_ngay = [str(dong["ngay"]) for dong in cac_dong]
    return min(cac_ngay), max(cac_ngay)


def chay_quy_trinh(
    nguon: nguon_du_lieu,
    cac_ma: Iterable[str],
    ngay_bat_dau: str,
    ngay_ket_thuc: str,
    thu_muc_du_lieu: str | Path,
    ngay_kiem_tra: date,
    *,
    so_lan_thu_toi_da: int = 3,
    ham_cho: Callable[[float], None] = time.sleep,
    ma_lan_chay: str | None = None,
) -> ket_qua_lan_chay:
    ma_lan_chay = ma_lan_chay or tao_ma_lan_chay()
    kho = kho_luu_tru(thu_muc_du_lieu)
    cac_trang_thai: list[trang_thai_ma] = []

    for ma_ban_dau in cac_ma:
        ma = ma_ban_dau.strip().upper()
        thoi_diem = datetime.now(timezone.utc).isoformat()
        duong_dan_nhat_ky_ma = kho.duong_dan("nhat_ky", ma_lan_chay, f"{ma}.json")
        bang: bang_du_lieu_nguon | None = None
        duong_dan_tho: Path | None = None
        duong_dan_chuan_hoa: Path | None = None
        duong_dan_san_sang: Path | None = None
        duong_dan_bao_cao: Path | None = None
        ma_sha256: str | None = None
        so_lan_thu = 0
        try:
            bang, so_lan_thu = _lay_voi_thu_lai(
                nguon,
                ma,
                ngay_bat_dau,
                ngay_ket_thuc,
                so_lan_thu_toi_da,
                ham_cho,
            )
            du_lieu_tho = {
                "ma": bang.ma,
                "nguon": nguon.ten_nguon,
                "phien_ban": nguon.phien_ban,
                "cac_cot": list(bang.cac_cot),
                "kieu_du_lieu": bang.kieu_du_lieu,
                "don_vi_gia": bang.don_vi_gia,
                "ghi_chu_khoi_luong": bang.ghi_chu_khoi_luong,
                "tham_so_gia": bang.tham_so_gia,
                "du_lieu": list(bang.cac_dong),
            }
            duong_dan_tho, ma_sha256 = kho.ghi_json(
                "tho", ma_lan_chay, f"{ma}.json", du_lieu_tho
            )

            cac_dong_chuan = chuan_hoa_bang(bang)
            duong_dan_chuan_hoa, _ = kho.ghi_csv(
                "chuan_hoa",
                ma_lan_chay,
                f"{ma}.csv",
                cac_dong_chuan,
                CAC_COT_BAT_BUOC,
            )
            bao_cao = kiem_tra_cac_dong(cac_dong_chuan, ngay_kiem_tra)
            duong_dan_bao_cao, _ = kho.ghi_json(
                "bao_cao",
                ma_lan_chay,
                f"{ma}.json",
                bao_cao.thanh_tu_dien(),
            )
            if bao_cao.hop_le:
                duong_dan_san_sang, _ = kho.ghi_csv(
                    "san_sang",
                    ma_lan_chay,
                    f"{ma}.csv",
                    cac_dong_chuan,
                    CAC_COT_BAT_BUOC,
                )
            ngay_dau, ngay_cuoi = _ngay_dau_cuoi(cac_dong_chuan)
            cac_canh_bao = tuple(muc.noi_dung for muc in bao_cao.canh_bao)
            cac_loi = "; ".join(muc.noi_dung for muc in bao_cao.loi) or None
            trang_thai = trang_thai_ma(
                ma=ma,
                trang_thai="thanh_cong" if bao_cao.hop_le else "that_bai",
                thoi_diem_chay=thoi_diem,
                ngay_bat_dau=ngay_bat_dau,
                ngay_ket_thuc=ngay_ket_thuc,
                so_dong=len(cac_dong_chuan),
                so_lan_thu=so_lan_thu,
                ten_cot_nguon=bang.cac_cot,
                kieu_du_lieu=bang.kieu_du_lieu,
                don_vi_gia=bang.don_vi_gia,
                duong_dan_tho=str(duong_dan_tho),
                duong_dan_chuan_hoa=str(duong_dan_chuan_hoa),
                duong_dan_san_sang=(str(duong_dan_san_sang) if duong_dan_san_sang else None),
                duong_dan_bao_cao=str(duong_dan_bao_cao),
                duong_dan_nhat_ky=str(duong_dan_nhat_ky_ma),
                ma_sha256=ma_sha256,
                ngay_dau=ngay_dau,
                ngay_cuoi=ngay_cuoi,
                canh_bao=cac_canh_bao,
                loi=cac_loi,
            )
        except Exception as exc:
            if so_lan_thu == 0:
                so_lan_thu = max(1, getattr(nguon, "so_lan_goi", {}).get(ma, 1))
            trang_thai = trang_thai_ma(
                ma=ma,
                trang_thai="that_bai",
                thoi_diem_chay=thoi_diem,
                ngay_bat_dau=ngay_bat_dau,
                ngay_ket_thuc=ngay_ket_thuc,
                so_dong=(len(bang.cac_dong) if bang is not None else 0),
                so_lan_thu=so_lan_thu,
                ten_cot_nguon=(bang.cac_cot if bang is not None else ()),
                kieu_du_lieu=(bang.kieu_du_lieu if bang is not None else None),
                don_vi_gia=(bang.don_vi_gia if bang is not None else None),
                duong_dan_tho=(str(duong_dan_tho) if duong_dan_tho else None),
                duong_dan_chuan_hoa=(str(duong_dan_chuan_hoa) if duong_dan_chuan_hoa else None),
                duong_dan_san_sang=None,
                duong_dan_bao_cao=(str(duong_dan_bao_cao) if duong_dan_bao_cao else None),
                duong_dan_nhat_ky=str(duong_dan_nhat_ky_ma),
                ma_sha256=ma_sha256,
                loi=lam_sach_loi(exc),
            )

        kho.ghi_json(
            "nhat_ky",
            ma_lan_chay,
            f"{ma}.json",
            trang_thai.thanh_tu_dien(),
        )
        cac_trang_thai.append(trang_thai)

    duong_dan_tong_hop, _ = kho.ghi_json(
        "nhat_ky",
        ma_lan_chay,
        "tong_hop.json",
        {
            "ma_lan_chay": ma_lan_chay,
            "nguon": nguon.ten_nguon,
            "phien_ban": nguon.phien_ban,
            "ngay_bat_dau": ngay_bat_dau,
            "ngay_ket_thuc": ngay_ket_thuc,
            "trang_thai_tung_ma": [muc.thanh_tu_dien() for muc in cac_trang_thai],
        },
    )
    return ket_qua_lan_chay(
        ma_lan_chay=ma_lan_chay,
        trang_thai_tung_ma=tuple(cac_trang_thai),
        duong_dan_nhat_ky=str(duong_dan_tong_hop),
    )
