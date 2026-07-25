"""Expanding walk-forward monthly voi purge, embargo va test khong chong lan."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Sequence

from .dac_trung import phien_cuoi_thang
from .mo_hinh import CauHinhMoc4, DuDoan, FoldWalkForward, MauMoHinh


def tao_folds(lich_benchmark: Iterable[date], cau_hinh: CauHinhMoc4) -> list[FoldWalkForward]:
    calendar = sorted(set(lich_benchmark))
    month_ends = list(phien_cuoi_thang(calendar))
    required_before_test = cau_hinh.so_thang_train_toi_thieu + cau_hinh.so_thang_validation
    if len(month_ends) <= required_before_test:
        return []
    index = {d: i for i, d in enumerate(calendar)}
    result: list[FoldWalkForward] = []
    used_test_dates: set[date] = set()
    for test_pos in range(required_before_test, len(month_ends)):
        test_date = month_ends[test_pos]
        validation_dates = tuple(month_ends[test_pos - cau_hinh.so_thang_validation:test_pos])
        validation_start = validation_dates[0]
        validation_end = validation_dates[-1]
        purge_end_index = index[validation_start] - 1
        train_end_index = index[validation_start] - cau_hinh.purge_phien - 1
        if train_end_index < 0:
            continue
        train_end = calendar[train_end_index]
        train_dates = tuple(d for d in month_ends[:test_pos - cau_hinh.so_thang_validation] if d <= train_end)
        if len(train_dates) < cau_hinh.so_thang_train_toi_thieu:
            continue
        embargo_dates = tuple(calendar[index[validation_end] + 1:index[validation_end] + 1 + cau_hinh.embargo_phien])
        if embargo_dates and test_date <= embargo_dates[-1]:
            continue
        purge_dates = tuple(calendar[train_end_index + 1:purge_end_index + 1])
        if test_date in used_test_dates:
            raise ValueError("Khoang test chong lan.")
        used_test_dates.add(test_date)
        result.append(FoldWalkForward(
            fold=f"fold_{len(result) + 1:03d}",
            train_dates=train_dates,
            validation_dates=validation_dates,
            test_dates=(test_date,),
            cutoff_train=calendar[index[validation_start] - 1],
            cutoff_validation=calendar[index[test_date] - 1],
            cutoff_refit=calendar[index[test_date] - 1],
            purge_dates=purge_dates,
            embargo_dates=embargo_dates,
        ))
    return result


def loc_mau_theo_fold(samples: Iterable[MauMoHinh], fold: FoldWalkForward) -> dict[str, list[MauMoHinh]]:
    rows = list(samples)
    train = [x for x in rows if x.ngay in fold.train_dates and x.ngay_ket_thuc_nhan <= fold.cutoff_train]
    validation = [x for x in rows if x.ngay in fold.validation_dates and x.ngay_ket_thuc_nhan <= fold.cutoff_validation]
    refit = [x for x in rows if x.ngay in set(fold.train_dates + fold.validation_dates) and x.ngay_ket_thuc_nhan <= fold.cutoff_refit]
    test = [x for x in rows if x.ngay in fold.test_dates]
    return {"train": train, "validation": validation, "refit_train_validation": refit, "test": test}


def xac_thuc_prediction_test(predictions: Sequence[DuDoan]) -> None:
    test_rows = [x for x in predictions if x.vai_tro_du_lieu == "test"]
    keys = [x.khoa() for x in test_rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Trung khoa (ngay,ma) trong prediction test.")
    by_fold: dict[str, set[date]] = {}
    for row in test_rows:
        by_fold.setdefault(row.fold, set()).add(row.ngay)
    folds = sorted(by_fold)
    for i, left in enumerate(folds):
        for right in folds[i + 1:]:
            if by_fold[left] & by_fold[right]:
                raise ValueError("Cac fold test chong lan.")
