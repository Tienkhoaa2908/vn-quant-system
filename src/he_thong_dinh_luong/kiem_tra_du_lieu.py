"""Kiem tra chat luong du lieu gia ngay."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

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
class LoiDuLieu:
    dong: int
    quy_tac: str
    noi_dung: str


@dataclass(frozen=True)
class BaoCaoKiemTra:
    hop_le: bool
    so_dong: int
    so_loi: int
    loi: tuple[LoiDuLieu, ...]

    def thanh_tu_dien(self) -> dict[str, object]:
        return {
            "hop_le": self.hop_le,
            "so_dong": self.so_dong,
            "so_loi": self.so_loi,
            "loi": [asdict(muc) for muc in self.loi],
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


def kiem_tra_cac_dong(
    cac_dong: Iterable[dict[str, str]], ngay_kiem_tra: date
) -> BaoCaoKiemTra:
    danh_sach = list(cac_dong)
    loi: list[LoiDuLieu] = []
    khoa_da_gap: set[tuple[str, date]] = set()

    for so_dong, dong in enumerate(danh_sach, start=2):
        try:
            ma = dong["ma"].strip()
            ngay = date.fromisoformat(dong["ngay"].strip())
            gia_mo_cua = float(dong["gia_mo_cua"])
            gia_cao_nhat = float(dong["gia_cao_nhat"])
            gia_thap_nhat = float(dong["gia_thap_nhat"])
            gia_dong_cua = float(dong["gia_dong_cua"])
            khoi_luong = float(dong["khoi_luong"])
        except (KeyError, TypeError, ValueError) as exc:
            loi.append(LoiDuLieu(so_dong, "dinh_dang", f"Khong doc duoc dong: {exc}"))
            continue

        khoa = (ma, ngay)
        if khoa in khoa_da_gap:
            loi.append(LoiDuLieu(so_dong, "trung_ma_va_ngay", f"Trung khoa {ma}, {ngay}"))
        khoa_da_gap.add(khoa)

        cac_gia = {
            "gia_mo_cua": gia_mo_cua,
            "gia_cao_nhat": gia_cao_nhat,
            "gia_thap_nhat": gia_thap_nhat,
            "gia_dong_cua": gia_dong_cua,
        }
        for ten, gia_tri in cac_gia.items():
            if gia_tri <= 0:
                loi.append(LoiDuLieu(so_dong, "gia_khong_duong", f"{ten}={gia_tri}"))

        if gia_cao_nhat < max(gia_mo_cua, gia_dong_cua):
            loi.append(LoiDuLieu(so_dong, "gia_cao_nhat_khong_hop_le", "Gia cao nhat nho hon gia mo cua hoac gia dong cua."))

        if gia_thap_nhat > min(gia_mo_cua, gia_dong_cua):
            loi.append(LoiDuLieu(so_dong, "gia_thap_nhat_khong_hop_le", "Gia thap nhat lon hon gia mo cua hoac gia dong cua."))

        if khoi_luong < 0:
            loi.append(LoiDuLieu(so_dong, "khoi_luong_am", f"khoi_luong={khoi_luong}"))

        if ngay > ngay_kiem_tra:
            loi.append(LoiDuLieu(so_dong, "ngay_sau_ngay_kiem_tra", f"ngay={ngay}, ngay_kiem_tra={ngay_kiem_tra}"))

    return BaoCaoKiemTra(hop_le=not loi, so_dong=len(danh_sach), so_loi=len(loi), loi=tuple(loi))


def kiem_tra_tep(duong_dan: str | Path, ngay_kiem_tra: date) -> BaoCaoKiemTra:
    return kiem_tra_cac_dong(doc_du_lieu_csv(duong_dan), ngay_kiem_tra)
