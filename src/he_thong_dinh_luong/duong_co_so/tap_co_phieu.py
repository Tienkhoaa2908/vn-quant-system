"""Tap co phieu theo tung thoi diem, khong su dung anh chup tuong lai."""
from __future__ import annotations

import csv
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

CAC_COT_ANH_CHUP = ("ngay_hieu_luc", "ma", "nguon", "phien_ban")


@dataclass(frozen=True, order=True)
class thanh_vien_tap_co_phieu:
    ngay_hieu_luc: date
    ma: str
    nguon: str
    phien_ban: str | None = None


@dataclass(frozen=True)
class anh_chup_da_chon:
    ngay_hieu_luc: date
    thanh_vien: tuple[thanh_vien_tap_co_phieu, ...]

    @property
    def cac_ma(self) -> tuple[str, ...]:
        return tuple(muc.ma for muc in self.thanh_vien)

    @property
    def nguon(self) -> str:
        return "|".join(sorted({muc.nguon for muc in self.thanh_vien}))

    @property
    def phien_ban(self) -> str | None:
        cac_phien_ban = sorted({muc.phien_ban for muc in self.thanh_vien if muc.phien_ban})
        return "|".join(cac_phien_ban) or None


class chi_muc_tap_co_phieu:
    """Chi muc bat bien cua cac anh chup thanh vien theo ngay hieu luc."""

    def __init__(self, cac_ban_ghi: Iterable[thanh_vien_tap_co_phieu]) -> None:
        theo_ngay: dict[date, list[thanh_vien_tap_co_phieu]] = {}
        khoa_da_gap: set[tuple[date, str]] = set()
        for muc in cac_ban_ghi:
            ma = muc.ma.strip().upper()
            nguon = muc.nguon.strip()
            if not ma:
                raise ValueError("Ma co phieu trong anh chup khong duoc rong.")
            if not nguon:
                raise ValueError("Nguon anh chup khong duoc rong.")
            khoa = (muc.ngay_hieu_luc, ma)
            if khoa in khoa_da_gap:
                raise ValueError(
                    f"Trung thanh vien theo ngay hieu luc va ma: {muc.ngay_hieu_luc}, {ma}."
                )
            khoa_da_gap.add(khoa)
            theo_ngay.setdefault(muc.ngay_hieu_luc, []).append(
                thanh_vien_tap_co_phieu(
                    ngay_hieu_luc=muc.ngay_hieu_luc,
                    ma=ma,
                    nguon=nguon,
                    phien_ban=(muc.phien_ban.strip() or None) if muc.phien_ban else None,
                )
            )
        if not theo_ngay:
            raise ValueError("Khong co anh chup tap co phieu nao.")
        self._cac_ngay = tuple(sorted(theo_ngay))
        self._theo_ngay = {
            ngay: tuple(sorted(cac_muc, key=lambda muc: muc.ma))
            for ngay, cac_muc in theo_ngay.items()
        }

    def chon(self, ngay_danh_gia: date) -> anh_chup_da_chon:
        vi_tri = bisect_right(self._cac_ngay, ngay_danh_gia) - 1
        if vi_tri < 0:
            raise ValueError(
                f"Khong co anh chup tap co phieu co ngay hieu luc khong lon hon {ngay_danh_gia}."
            )
        ngay_hieu_luc = self._cac_ngay[vi_tri]
        return anh_chup_da_chon(ngay_hieu_luc, self._theo_ngay[ngay_hieu_luc])


def doc_anh_chup_csv(duong_dan: str | Path) -> chi_muc_tap_co_phieu:
    cac_ban_ghi: list[thanh_vien_tap_co_phieu] = []
    with Path(duong_dan).open("r", encoding="utf-8", newline="") as tep:
        bo_doc = csv.DictReader(tep)
        if bo_doc.fieldnames is None:
            raise ValueError("Tep anh chup tap co phieu khong co dong tieu de.")
        thieu_cot = [cot for cot in CAC_COT_ANH_CHUP if cot not in bo_doc.fieldnames]
        if thieu_cot:
            raise ValueError(f"Thieu cot anh chup bat buoc: {', '.join(thieu_cot)}")
        for so_dong, dong in enumerate(bo_doc, start=2):
            try:
                ngay_hieu_luc = date.fromisoformat(str(dong["ngay_hieu_luc"]).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Ngay hieu luc khong hop le tai dong {so_dong}.") from exc
            cac_ban_ghi.append(
                thanh_vien_tap_co_phieu(
                    ngay_hieu_luc=ngay_hieu_luc,
                    ma=str(dong["ma"] or ""),
                    nguon=str(dong["nguon"] or ""),
                    phien_ban=str(dong["phien_ban"] or "") or None,
                )
            )
    return chi_muc_tap_co_phieu(cac_ban_ghi)
