"""Cross-sectional features, metrics và temporal split cho forward prediction."""
from __future__ import annotations

from datetime import date
from math import sqrt
from statistics import fmean
from typing import Sequence

from .du_doan_tien_phuong_contract import DERIVED_FEATURES, REGIME_FEATURES, STOCK_RANK_FEATURES, Metrics, Row

def _derived(row: Row) -> dict[str, float]:
    vol = max(row.features["bien_dong_60"], 1e-12)
    consistency = fmean(1.0 if row.features[name] > 0.0 else 0.0 for name in ("loi_nhuan_20", "loi_nhuan_60", "loi_nhuan_120", "loi_nhuan_250"))
    return {
        "momentum_tren_bien_dong": row.features["dong_luong_12_1"] / vol,
        "suc_manh_tren_bien_dong": row.features["suc_manh_tuong_doi_120"] / vol,
        "do_nhat_quan_momentum": consistency,
    }

def _average_percentile(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    denominator = max(len(values) - 1, 1)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        percentile = ((start + end - 1) / 2.0) / denominator
        for position in range(start, end):
            result[order[position]] = percentile
        start = end
    return result

def _matrix(rows: Sequence[Row]) -> tuple[list[list[float]], tuple[str, ...]]:
    by_day: dict[date, list[int]] = {}
    for index, row in enumerate(rows):
        by_day.setdefault(row.ngay, []).append(index)
    stock_names = STOCK_RANK_FEATURES + DERIVED_FEATURES
    feature_names = tuple(f"rank_{name}" for name in stock_names) + REGIME_FEATURES
    matrix = [[0.0] * len(feature_names) for _ in rows]
    for indexes in by_day.values():
        derived = {index: _derived(rows[index]) for index in indexes}
        for column, name in enumerate(stock_names):
            values = [rows[index].features[name] if name in rows[index].features else derived[index][name] for index in indexes]
            percentiles = _average_percentile(values)
            for local, index in enumerate(indexes):
                matrix[index][column] = percentiles[local]
        offset = len(stock_names)
        for local_column, name in enumerate(REGIME_FEATURES):
            for index in indexes:
                matrix[index][offset + local_column] = float(rows[index].features[name])
    return matrix, feature_names

def _relevance(rows: Sequence[Row], levels: int = 5) -> list[int]:
    result = [0] * len(rows)
    by_day: dict[date, list[int]] = {}
    for index, row in enumerate(rows):
        if row.relative_return is None:
            raise ValueError("RELEVANCE_REQUIRES_LABEL")
        by_day.setdefault(row.ngay, []).append(index)
    for indexes in by_day.values():
        ordered = sorted(indexes, key=lambda index: (float(rows[index].relative_return), rows[index].ma))
        count = len(ordered)
        for position, index in enumerate(ordered):
            result[index] = min(levels - 1, (position * levels) // count)
    return result

def _group_sizes(rows: Sequence[Row]) -> list[int]:
    result: list[int] = []
    current: date | None = None
    count = 0
    for row in rows:
        if current is None:
            current = row.ngay
        if row.ngay != current:
            result.append(count)
            current = row.ngay
            count = 0
        count += 1
    if count:
        result.append(count)
    return result

def _rank(values: Sequence[float]) -> list[float]:
    return _average_percentile(values)

def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    mean_left = fmean(left)
    mean_right = fmean(right)
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    denominator = sqrt(sum((x - mean_left) ** 2 for x in left) * sum((y - mean_right) ** 2 for y in right))
    return numerator / denominator if denominator > 0.0 else 0.0

def _metrics(rows: Sequence[Row], scores: Sequence[float], top_k: int) -> Metrics:
    if len(rows) != len(scores):
        raise ValueError("METRIC_LENGTH_MISMATCH")
    by_day: dict[date, list[int]] = {}
    for index, row in enumerate(rows):
        if row.relative_return is None:
            raise ValueError("METRIC_REQUIRES_LABEL")
        by_day.setdefault(row.ngay, []).append(index)
    daily_ic: list[float] = []
    daily_precision: list[float] = []
    daily_return: list[float] = []
    selections: list[set[str]] = []
    for day in sorted(by_day):
        indexes = by_day[day]
        daily_scores = [float(scores[index]) for index in indexes]
        daily_targets = [float(rows[index].relative_return) for index in indexes]
        daily_ic.append(_pearson(_rank(daily_scores), _rank(daily_targets)))
        selected = sorted(indexes, key=lambda index: (-float(scores[index]), rows[index].ma))[: min(top_k, len(indexes))]
        selections.append({rows[index].ma for index in selected})
        daily_precision.append(fmean(1.0 if float(rows[index].relative_return) > 0.0 else 0.0 for index in selected))
        daily_return.append(fmean(float(rows[index].relative_return) for index in selected))
    turnovers = [1.0 - len(selections[index] & selections[index - 1]) / max(min(top_k, len(selections[index])), 1) for index in range(1, len(selections))]
    return Metrics(
        mean_rank_ic=fmean(daily_ic),
        precision_at_k=fmean(daily_precision),
        top_k_relative_return=fmean(daily_return),
        mean_set_turnover=fmean(turnovers) if turnovers else 0.0,
        day_count=len(by_day),
    )

def _split_history(rows: Sequence[Row], validation_months: int) -> tuple[list[Row], list[Row], date]:
    dates = sorted({row.ngay for row in rows})
    if validation_months < 3:
        raise ValueError("VALIDATION_MONTHS_TOO_SMALL")
    if len(dates) <= validation_months + 12:
        raise ValueError("INSUFFICIENT_HISTORY_FOR_VALIDATION")
    validation_dates = set(dates[-validation_months:])
    validation_start = min(validation_dates)
    train = [row for row in rows if row.ngay not in validation_dates and row.label_end is not None and row.label_end < validation_start]
    validation = [row for row in rows if row.ngay in validation_dates]
    if not train or not validation:
        raise ValueError("TEMPORAL_SPLIT_EMPTY")
    return train, validation, validation_start
