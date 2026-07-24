"""Kiem tra chat luong du lieu gia ngay."""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping

CAC_COT_BAT_BUOC = (
    "ma",
    "ngay",
    "gia_mo_cua",
    "gia_cao_nhat",
    "gia_thap_nhat",
    "gia_dong_cua",
    "khoi_luong",
)


@dataclass(frozen=True)
class loi_du_lieu:
    dong: int
    quy_tac: str
    noi_dung: str


@dataclass(frozen=True)
class canh_bao_du_lieu:
    dong: int
    quy_tac: str
    noi_dung: str


@dataclass(frozen=True)
class bao_cao_kiem_tra:
    hop_le: bool
    so_dong: int
    so_loi: int
    loi: tuple[loi_du_lieu, ...]
    so_canh_bao: int = 0
    canh_bao: tuple[canh_bao_du_lieu, ...] = ()

    def thanh_tu_dien(self) -> dict[str, object]:
        return {
            "hop_le": self.hop_le,
            "so_dong": self.so_dong,
            "so_loi": self.so_loi,
            "loi": [asdict(muc) for muc in self.loi],
            "so_canh_bao": self.so_canh_bao,
            "canh_bao": [asdict(muc) for muc in self.canh_bao],
        }


def doc_du_lieu_csv(duong_dan: str | Path) -> list[dict[str, str]]:
    with Path(duong_dan).open("r", encoding="utf-8", newline="") as tep:
        bo_doc = csv.DictReader(tep)
        if bo_doc.fieldnames is None:
            raise ValueError("Tep CSV khong co dong tieu de.")
        thieu_cot = [cot for cot in CAC_COT_BAT_BUOC if cot not in bo_doc.fieldnames]
        if thieu_cot:
            raise ValueError(f"Thieu cot bat buoc: {', '.join(thieu_cot)}")
        return [dict(dong) for dong in bo_doc]


def _doc_so(dong: Mapping[str, object], ten_cot: str) -> float:
    gia_tri = float(dong[ten_cot])
    if not math.isfinite(gia_tri):
        raise ValueError(f"{ten_cot} khong phai so huu han")
    return gia_tri


def kiem_tra_cac_dong(
    cac_dong: Iterable[Mapping[str, object]],
    ngay_kiem_tra: date,
    nguong_khoang_ngay: int = 7,
) -> bao_cao_kiem_tra:
    danh_sach = [dict(dong) for dong in cac_dong]
    loi: list[loi_du_lieu] = []
    canh_bao: list[canh_bao_du_lieu] = []
    khoa_da_gap: set[tuple[str, date]] = set()
    ngay_theo_ma: dict[str, list[tuple[date, int]]] = {}

    for so_dong, dong in enumerate(danh_sach, start=2):
        thieu_cot = [cot for cot in CAC_COT_BAT_BUOC if cot not in dong]
        if thieu_cot:
            loi.append(
                loi_du_lieu(
                    so_dong,
                    "thieu_cot",
                    f"Thieu cot bat buoc: {', '.join(thieu_cot)}",
                )
            )
            continue

        try:
            ma = str(dong["ma"]).strip().upper()
            if not ma:
                raise ValueError("ma rong")
            ngay = date.fromisoformat(str(dong["ngay"]).strip()[:10])
            gia_mo_cua = _doc_so(dong, "gia_mo_cua")
            gia_cao_nhat = _doc_so(dong, "gia_cao_nhat")
            gia_thap_nhat = _doc_so(dong, "gia_thap_nhat")
            gia_dong_cua = _doc_so(dong, "gia_dong_cua")
            khoi_luong = _doc_so(dong, "khoi_luong")
        except (KeyError, TypeError, ValueError) as exc:
            loi.append(loi_du_lieu(so_dong, "dinh_dang", f"Khong doc duoc dong: {exc}"))
            continue

        khoa = (ma, ngay)
        if khoa in khoa_da_gap:
            loi.append(loi_du_lieu(so_dong, "trung_ma_va_ngay", f"Trung khoa {ma}, {ngay}"))
        khoa_da_gap.add(khoa)
        ngay_theo_ma.setdefault(ma, []).append((ngay, so_dong))

        cac_gia = {
            "gia_mo_cua": gia_mo_cua,
            "gia_cao_nhat": gia_cao_nhat,
            "gia_thap_nhat": gia_thap_nhat,
            "gia_dong_cua": gia_dong_cua,
        }
        for ten, gia_tri in cac_gia.items():
            if gia_tri <= 0:
                loi.append(loi_du_lieu(so_dong, "gia_khong_duong", f"{ten}={gia_tri}"))

        if gia_cao_nhat < max(gia_mo_cua, gia_dong_cua):
            loi.append(
                loi_du_lieu(
                    so_dong,
                    "gia_cao_nhat_khong_hop_le",
                    "Gia cao nhat nho hon gia mo cua hoac gia dong cua.",
                )
            )
        if gia_thap_nhat > min(gia_mo_cua, gia_dong_cua):
            loi.append(
                loi_du_lieu(
                    so_dong,
                    "gia_thap_nhat_khong_hop_le",
                    "Gia thap nhat lon hon gia mo cua hoac gia dong cua.",
                )
            )
        if khoi_luong < 0:
            loi.append(loi_du_lieu(so_dong, "khoi_luong_am", f"khoi_luong={khoi_luong}"))
        if not khoi_luong.is_integer():
            loi.append(
                loi_du_lieu(
                    so_dong,
                    "khoi_luong_khong_nguyen",
                    f"khoi_luong={khoi_luong}",
                )
            )
        if ngay > ngay_kiem_tra:
            loi.append(
                loi_du_lieu(
                    so_dong,
                    "ngay_sau_ngay_kiem_tra",
                    f"ngay={ngay}, ngay_kiem_tra={ngay_kiem_tra}",
                )
            )

    for ma, cac_ngay in ngay_theo_ma.items():
        cac_ngay_sap_xep = sorted(set(cac_ngay))
        for (ngay_truoc, _), (ngay_sau, dong_sau) in zip(
            cac_ngay_sap_xep, cac_ngay_sap_xep[1:]
        ):
            khoang_cach = (ngay_sau - ngay_truoc).days
            if khoang_cach > nguong_khoang_ngay:
                canh_bao.append(
                    canh_bao_du_lieu(
                        dong_sau,
                        "khoang_ngay_bat_thuong",
                        f"{ma}: {ngay_truoc} den {ngay_sau} cach {khoang_cach} ngay lich; khong tu dien du lieu.",
                    )
                )

    return bao_cao_kiem_tra(
        hop_le=not loi,
        so_dong=len(danh_sach),
        so_loi=len(loi),
        loi=tuple(loi),
        so_canh_bao=len(canh_bao),
        canh_bao=tuple(canh_bao),
    )


def kiem_tra_tep(duong_dan: str | Path, ngay_kiem_tra: date) -> bao_cao_kiem_tra:
    return kiem_tra_cac_dong(doc_du_lieu_csv(duong_dan), ngay_kiem_tra)
