"""Momentum baseline OOS dung dong_luong_12_1, khong hoc tham so tu test."""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
from statistics import fmean
from typing import Iterable, Mapping, Sequence

from sklearn.metrics import roc_auc_score

from .mo_hinh import DongFeature, DongXepHang, DuDoan, MauMoHinh


def diem_momentum(feature: DongFeature) -> float | None:
    value = feature.gia_tri.get("dong_luong_12_1")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if isfinite(result) else None


def du_doan_baseline_test(
    *,
    fold: str,
    samples: Sequence[MauMoHinh],
    model_id: str | None = None,
    momentum_theo_khoa: Mapping[tuple[object, str], float] | None = None,
) -> tuple[DuDoan, ...]:
    """Chuan hoa momentum theo ngay ve [0,1] chi de luu score/metric; thu tu khong doi."""
    if not fold:
        raise ValueError("fold baseline khong duoc rong.")
    identifier = model_id or f"{fold}_momentum_baseline"
    by_day: dict[object, list[MauMoHinh]] = defaultdict(list)
    momentum = momentum_theo_khoa or {}
    for sample in samples:
        value = momentum.get((sample.ngay, sample.ma), getattr(sample, "dong_luong_12_1", None))
        if value is None or not isfinite(float(value)):
            continue
        by_day[sample.ngay].append(sample)
    result: list[DuDoan] = []
    for day in sorted(by_day):
        rows = by_day[day]
        values = [float(momentum.get((x.ngay, x.ma), getattr(x, "dong_luong_12_1", None))) for x in rows]
        lower, upper = min(values), max(values)
        for sample, value in sorted(zip(rows, values, strict=True), key=lambda pair: pair[0].ma):
            score = 0.5 if upper == lower else (value - lower) / (upper - lower)
            result.append(DuDoan(
                fold=fold,
                model_id=identifier,
                vai_tro_du_lieu="test",
                ngay=sample.ngay,
                ma=sample.ma,
                xac_suat_nhan_1=score,
                nhan=sample.nhan,
                loi_nhuan_tuong_doi=sample.loi_nhuan_tuong_doi,
            ))
    return tuple(result)


def xep_hang_baseline_test(
    predictions: Iterable[DuDoan],
    *,
    top_k: int,
) -> tuple[list[DongXepHang], dict[object, float]]:
    from .xep_hang import xep_hang_test
    return xep_hang_test(predictions, top_k=top_k)


def metric_baseline_test(predictions: Iterable[DuDoan]) -> dict[str, object]:
    rows = list(predictions)
    if any(row.vai_tro_du_lieu != "test" for row in rows):
        raise ValueError("Metric baseline chi nhan test.")
    keys = [(row.ngay, row.ma) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Trung (ngay,ma) trong baseline test.")
    fold_model: dict[str, str] = {}
    for row in rows:
        if not row.fold or not row.model_id:
            raise ValueError("fold/model_id baseline khong hop le.")
        if row.fold in fold_model and fold_model[row.fold] != row.model_id:
            raise ValueError("Mot fold baseline chi duoc co mot model_id.")
        fold_model[row.fold] = row.model_id
        if not isfinite(row.xac_suat_nhan_1) or not 0.0 <= row.xac_suat_nhan_1 <= 1.0:
            raise ValueError("Score baseline phai huu han trong [0,1].")
        if row.nhan not in {None, 0, 1}:
            raise ValueError("Nhan baseline khong hop le.")
        if row.loi_nhuan_tuong_doi is not None and not isfinite(row.loi_nhuan_tuong_doi):
            raise ValueError("Relative return baseline phai huu han.")
    labeled = [row for row in rows if row.nhan is not None]
    if not labeled:
        return {
            "so_quan_sat": 0,
            "auc": None,
            "diem_trung_binh": None,
            "ghi_chu": "Score la bien doi don dieu cua dong_luong_12_1; khong phai probability calibrate.",
        }
    y = [int(row.nhan) for row in labeled]
    score = [float(row.xac_suat_nhan_1) for row in labeled]
    return {
        "so_quan_sat": len(labeled),
        "so_ma": len({row.ma for row in labeled}),
        "auc": float(roc_auc_score(y, score)) if len(set(y)) == 2 else None,
        "diem_trung_binh": fmean(score),
        "ghi_chu": "Score la bien doi don dieu cua dong_luong_12_1; khong phai probability calibrate.",
    }
