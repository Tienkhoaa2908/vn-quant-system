"""Ranking xac suat, top-K va ty trong deu voi phan thieu la tien mat."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .mo_hinh import DongXepHang, DuDoan
from .walk_forward import xac_thuc_prediction_test


def xep_hang_test(predictions: Iterable[DuDoan], *, top_k: int) -> tuple[list[DongXepHang], dict[object, float]]:
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise ValueError("top_k phai la int duong.")
    rows = list(predictions)
    if any(x.vai_tro_du_lieu != "test" for x in rows):
        raise ValueError("Ranking cuoi chi nhan prediction test.")
    xac_thuc_prediction_test(rows)
    by_day: dict[object, list[DuDoan]] = defaultdict(list)
    for row in rows:
        by_day[row.ngay].append(row)
    rankings: list[DongXepHang] = []
    cash_by_day: dict[object, float] = {}
    for day in sorted(by_day):
        ordered = sorted(by_day[day], key=lambda x: (-x.xac_suat_nhan_1, x.ma))
        selected_count = min(top_k, len(ordered))
        cash_by_day[day] = 1.0 - selected_count / top_k
        for rank, row in enumerate(ordered, start=1):
            selected = rank <= top_k
            rankings.append(DongXepHang(
                fold=row.fold, model_id=row.model_id, ngay=row.ngay, ma=row.ma,
                xac_suat_nhan_1=row.xac_suat_nhan_1, thu_hang=rank,
                duoc_chon=selected, ty_trong_muc_tieu=1.0 / top_k if selected else 0.0,
                nhan=row.nhan, loi_nhuan_tuong_doi=row.loi_nhuan_tuong_doi,
            ))
    return rankings, cash_by_day
