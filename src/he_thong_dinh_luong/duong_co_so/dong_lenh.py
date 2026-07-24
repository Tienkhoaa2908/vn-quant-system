"""CLI tao du lieu duong co so Moc 2."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping

from ..kiem_tra_du_lieu import CAC_COT_BAT_BUOC
from .chi_bao import (
    CAC_COT_DAU_RA,
    DON_VI_GIA_TRI_GIAO_DICH,
    cau_hinh_duong_co_so,
    tinh_duong_co_so,
)
from .tap_co_phieu import doc_anh_chup_csv


def _lam_sach_loi(loi: BaseException) -> str:
    noi_dung = str(loi)
    for mau in (
        r"vnstock_[A-Za-z0-9_-]+",
        r"(?i)(api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+",
        r"(?i)bearer\s+[A-Za-z0-9._~-]+",
    ):
        noi_dung = re.sub(mau, "[DA_AN]", noi_dung)
    return noi_dung[:2000]


def _doc_csv(duong_dan: Path) -> list[dict[str, str]]:
    with duong_dan.open("r", encoding="utf-8", newline="") as tep:
        bo_doc = csv.DictReader(tep)
        if bo_doc.fieldnames is None:
            raise ValueError(f"Tep CSV khong co dong tieu de: {duong_dan}")
        thieu_cot = [cot for cot in CAC_COT_BAT_BUOC if cot not in bo_doc.fieldnames]
        if thieu_cot:
            raise ValueError(
                f"Tep {duong_dan} thieu cot bat buoc: {', '.join(thieu_cot)}"
            )
        return [dict(dong) for dong in bo_doc]


def doc_du_lieu_san_sang(duong_dan: str | Path) -> list[dict[str, str]]:
    duong_dan = Path(duong_dan)
    if duong_dan.is_file():
        return _doc_csv(duong_dan)
    if not duong_dan.is_dir():
        raise ValueError(f"Khong tim thay duong dan du lieu san sang: {duong_dan}")
    cac_tep = sorted(duong_dan.rglob("*.csv"))
    if not cac_tep:
        raise ValueError(f"Khong co tep CSV nao duoi {duong_dan}")
    ket_qua: list[dict[str, str]] = []
    for tep in cac_tep:
        ket_qua.extend(_doc_csv(tep))
    return ket_qua


def _gia_tri_csv(gia_tri: object) -> object:
    if gia_tri is None:
        return ""
    if isinstance(gia_tri, bool):
        return "true" if gia_tri else "false"
    if isinstance(gia_tri, float):
        if not math.isfinite(gia_tri):
            raise ValueError("Khong the ghi so khong huu han.")
        return format(gia_tri, ".15g")
    return gia_tri


def _ghi_csv_bat_bien(duong_dan: Path, cac_dong: Iterable[Mapping[str, object]]) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    with duong_dan.open("x", encoding="utf-8", newline="") as tep:
        bo_ghi = csv.DictWriter(tep, fieldnames=CAC_COT_DAU_RA, lineterminator="\n")
        bo_ghi.writeheader()
        for dong in cac_dong:
            bo_ghi.writerow({cot: _gia_tri_csv(dong.get(cot)) for cot in CAC_COT_DAU_RA})


def _ghi_json_bat_bien(duong_dan: Path, du_lieu: object) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    with duong_dan.open("x", encoding="utf-8") as tep:
        json.dump(du_lieu, tep, ensure_ascii=False, indent=2, sort_keys=True)
        tep.write("\n")


def _bao_cao(
    cac_dong_dau_vao: list[dict[str, str]],
    cac_dong_dau_ra: list[dict[str, object]],
    cau_hinh: cau_hinh_duong_co_so,
    ngay_bat_dau: date,
    ngay_ket_thuc: date,
) -> dict[str, object]:
    dau_vao_theo_ma: dict[str, list[dict[str, str]]] = {}
    for dong in cac_dong_dau_vao:
        ma = str(dong["ma"]).strip().upper()
        dau_vao_theo_ma.setdefault(ma, []).append(dong)
    dau_ra_theo_ma: dict[str, list[dict[str, object]]] = {}
    for dong in cac_dong_dau_ra:
        dau_ra_theo_ma.setdefault(str(dong["ma"]), []).append(dong)

    trang_thai_tung_ma: list[dict[str, object]] = []
    for ma in sorted(dau_vao_theo_ma):
        cac_dong_vao = sorted(
            dau_vao_theo_ma[ma], key=lambda dong: str(dong["ngay"])
        )
        cac_dong_ra = dau_ra_theo_ma.get(ma, [])
        dong_cuoi = cac_dong_ra[-1] if cac_dong_ra else None
        canh_bao = (
            []
            if cac_dong_ra
            else ["Khong co dong dau ra trong khoang ngay yeu cau."]
        )
        trang_thai_tung_ma.append(
            {
                "ma": ma,
                "so_phien": len(cac_dong_vao),
                "ngay_dau": str(cac_dong_vao[0]["ngay"])[:10],
                "ngay_cuoi": str(cac_dong_vao[-1]["ngay"])[:10],
                "so_dong_dau_ra": len(cac_dong_ra),
                "so_dong_co_ma250": sum(
                    dong["ma250"] is not None for dong in cac_dong_ra
                ),
                "ma250_cuoi": dong_cuoi["ma250"] if dong_cuoi else None,
                "dong_luong_cuoi": dong_cuoi["dong_luong"] if dong_cuoi else None,
                "trang_thai_thanh_khoan": (
                    dong_cuoi["dat_thanh_khoan"] if dong_cuoi else None
                ),
                "canh_bao": canh_bao,
                "loi": [],
            }
        )
    return {
        "trang_thai": "thanh_cong",
        "so_dong": len(cac_dong_dau_ra),
        "ngay_bat_dau": ngay_bat_dau.isoformat(),
        "ngay_ket_thuc": ngay_ket_thuc.isoformat(),
        "don_vi": {
            "gia_dong_cua": "nghin_dong_moi_co_phieu",
            "gia_tri_giao_dich": DON_VI_GIA_TRI_GIAO_DICH,
        },
        "cau_hinh": {
            "cua_so_thanh_khoan": cau_hinh.cua_so_thanh_khoan,
            "so_quan_sat_toi_thieu": cau_hinh.so_quan_sat_toi_thieu,
            "nguong_thanh_khoan": cau_hinh.nguong_thanh_khoan,
            "cua_so_dong_luong": cau_hinh.cua_so_dong_luong,
            "cua_so_ma": 250,
        },
        "trang_thai_tung_ma": trang_thai_tung_ma,
        "gioi_han_du_lieu": (
            "Ket qua chi chung minh giao dien va quy tac khong nhin truoc. "
            "Khong tuyen bo co du lieu thanh vien lich su that neu tep anh chup la gia lap."
        ),
    }


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    bo = argparse.ArgumentParser(description="Tao tap co phieu va duong co so Moc 2.")
    bo.add_argument("--du_lieu_san_sang", required=True)
    bo.add_argument("--anh_chup_tap_co_phieu", required=True)
    bo.add_argument("--ngay_danh_gia")
    bo.add_argument("--ngay_bat_dau")
    bo.add_argument("--ngay_ket_thuc")
    bo.add_argument("--cua_so_thanh_khoan", required=True, type=int)
    bo.add_argument("--so_quan_sat_toi_thieu", required=True, type=int)
    bo.add_argument("--nguong_thanh_khoan", required=True, type=float)
    bo.add_argument("--cua_so_dong_luong", required=True, type=int)
    bo.add_argument("--thu_muc_dau_ra", required=True)
    return bo


def _doc_khoang_ngay(tham_so: argparse.Namespace) -> tuple[date, date]:
    if tham_so.ngay_danh_gia:
        if tham_so.ngay_bat_dau or tham_so.ngay_ket_thuc:
            raise ValueError("Khong dung ngay_danh_gia cung khoang ngay.")
        ngay = date.fromisoformat(tham_so.ngay_danh_gia)
        return ngay, ngay
    if not tham_so.ngay_bat_dau or not tham_so.ngay_ket_thuc:
        raise ValueError("Can ngay_danh_gia hoac day du ngay_bat_dau va ngay_ket_thuc.")
    ngay_bat_dau = date.fromisoformat(tham_so.ngay_bat_dau)
    ngay_ket_thuc = date.fromisoformat(tham_so.ngay_ket_thuc)
    if ngay_bat_dau > ngay_ket_thuc:
        raise ValueError("Ngay bat dau khong duoc sau ngay ket thuc.")
    return ngay_bat_dau, ngay_ket_thuc


def _kiem_tra_dau_ra_trong(thu_muc: Path) -> None:
    cac_tep = (thu_muc / "duong_co_so.csv", thu_muc / "bao_cao.json")
    da_ton_tai = [str(tep) for tep in cac_tep if tep.exists()]
    if da_ton_tai:
        raise FileExistsError(
            "Khong duoc ghi de san pham da ton tai: " + ", ".join(da_ton_tai)
        )


def _ghi_bao_cao_loi(thu_muc: Path, loi: BaseException) -> None:
    try:
        _ghi_json_bat_bien(
            thu_muc / "bao_cao_loi.json",
            {"trang_thai": "that_bai", "loi": _lam_sach_loi(loi)},
        )
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    bo = tao_bo_phan_tich()
    try:
        tham_so = bo.parse_args(argv)
        thu_muc_dau_ra = Path(tham_so.thu_muc_dau_ra)
        ngay_bat_dau, ngay_ket_thuc = _doc_khoang_ngay(tham_so)
        _kiem_tra_dau_ra_trong(thu_muc_dau_ra)
        cau_hinh = cau_hinh_duong_co_so(
            cua_so_thanh_khoan=tham_so.cua_so_thanh_khoan,
            so_quan_sat_toi_thieu=tham_so.so_quan_sat_toi_thieu,
            nguong_thanh_khoan=tham_so.nguong_thanh_khoan,
            cua_so_dong_luong=tham_so.cua_so_dong_luong,
        )
        tap_co_phieu = doc_anh_chup_csv(tham_so.anh_chup_tap_co_phieu)
        cac_dong = doc_du_lieu_san_sang(tham_so.du_lieu_san_sang)
        ket_qua = tinh_duong_co_so(
            cac_dong,
            tap_co_phieu,
            cau_hinh,
            ngay_bat_dau=ngay_bat_dau,
            ngay_ket_thuc=ngay_ket_thuc,
        )
        if not ket_qua:
            raise ValueError("Khong co dong dau ra trong khoang ngay yeu cau.")
        _ghi_csv_bat_bien(thu_muc_dau_ra / "duong_co_so.csv", ket_qua)
        _ghi_json_bat_bien(
            thu_muc_dau_ra / "bao_cao.json",
            _bao_cao(cac_dong, ket_qua, cau_hinh, ngay_bat_dau, ngay_ket_thuc),
        )
        return 0
    except SystemExit:
        raise
    except (ValueError, OSError) as exc:
        thu_muc = Path(getattr(locals().get("tham_so", None), "thu_muc_dau_ra", "."))
        _ghi_bao_cao_loi(thu_muc, exc)
        print(f"Loi: {_lam_sach_loi(exc)}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - hang rao cuoi CLI
        thu_muc = Path(getattr(locals().get("tham_so", None), "thu_muc_dau_ra", "."))
        _ghi_bao_cao_loi(thu_muc, exc)
        print(f"Loi he thong: {_lam_sach_loi(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
