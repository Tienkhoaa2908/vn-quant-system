"""Metric model va ranking chi tren prediction test ngoai mau."""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from statistics import fmean
from typing import Iterable, Sequence

from sklearn.metrics import log_loss, roc_auc_score

from .mo_hinh import DongXepHang, DuDoan


def calibration_equal_width(predictions: Sequence[DuDoan]) -> list[dict[str, object]]:
    bins: list[list[DuDoan]] = [[] for _ in range(10)]
    for row in predictions:
        index = min(int(row.xac_suat_nhan_1 * 10), 9)
        bins[index].append(row)
    result = []
    for index, rows in enumerate(bins):
        if not rows:
            continue
        labeled = [x for x in rows if x.nhan is not None]
        if not labeled:
            continue
        result.append({
            "bin": index,
            "lower": index / 10,
            "upper": (index + 1) / 10,
            "count": len(labeled),
            "mean_probability": fmean(x.xac_suat_nhan_1 for x in labeled),
            "positive_rate": fmean(float(x.nhan) for x in labeled),
        })
    return result


def metric_model_test(predictions: Iterable[DuDoan]) -> dict[str, object]:
    rows = list(predictions)
    if any(x.vai_tro_du_lieu != "test" for x in rows):
        raise ValueError("Metric cuoi chi nhan prediction test.")
    labeled = [x for x in rows if x.nhan is not None]
    if not labeled:
        return {"so_quan_sat": 0, "auc": None, "log_loss": None, "brier": None, "calibration": []}
    y = [int(x.nhan) for x in labeled]
    p = [x.xac_suat_nhan_1 for x in labeled]
    auc = float(roc_auc_score(y, p)) if len(set(y)) == 2 else None
    return {
        "so_quan_sat": len(labeled),
        "so_ma": len({x.ma for x in labeled}),
        "auc": auc,
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": fmean((prob - label) ** 2 for prob, label in zip(p, y, strict=True)),
        "ty_le_lop_duong": fmean(float(label) for label in y),
        "calibration": calibration_equal_width(labeled),
    }


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        average = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = average
        i = j
    return ranks


def spearman_rank_ic(scores: Sequence[float], returns: Sequence[float]) -> float | None:
    if len(scores) != len(returns):
        raise ValueError("scores va returns khac do dai.")
    if len(scores) < 3:
        return None
    x, y = _average_ranks(scores), _average_ranks(returns)
    mx, my = fmean(x), fmean(y)
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx == 0.0 or vy == 0.0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sqrt(vx * vy)


def decile_spread(rows: Sequence[DongXepHang]) -> float | None:
    valid = [x for x in rows if x.loi_nhuan_tuong_doi is not None]
    if len(valid) < 10:
        return None
    ordered = sorted(valid, key=lambda x: (-x.xac_suat_nhan_1, x.ma))
    n = len(ordered)
    q, r = divmod(n, 10)
    sizes = [q + 1 if i < r else q for i in range(10)]
    groups: list[list[DongXepHang]] = []
    offset = 0
    for size in sizes:
        groups.append(ordered[offset:offset + size])
        offset += size
    return fmean(float(x.loi_nhuan_tuong_doi) for x in groups[0]) - fmean(float(x.loi_nhuan_tuong_doi) for x in groups[-1])


def metric_ranking_test(rankings: Iterable[DongXepHang]) -> dict[str, object]:
    rows = list(rankings)
    by_day: dict[object, list[DongXepHang]] = defaultdict(list)
    for row in rows:
        by_day[row.ngay].append(row)
    daily: list[dict[str, object]] = []
    previous: set[str] | None = None
    for day in sorted(by_day):
        day_rows = by_day[day]
        selected = [x for x in day_rows if x.duoc_chon]
        selected_set = {x.ma for x in selected}
        complete = bool(selected) and all(x.nhan is not None and x.loi_nhuan_tuong_doi is not None for x in selected)
        precision = fmean(float(x.nhan) for x in selected) if complete else None
        hit_rate = float(any(x.nhan == 1 for x in selected)) if complete else None
        avg_relative = fmean(float(x.loi_nhuan_tuong_doi) for x in selected) if complete else None
        if previous is None:
            turnover = None
        elif not previous and not selected_set:
            turnover = 0.0
        else:
            turnover = 1.0 - len(previous & selected_set) / max(len(previous), len(selected_set))
        valid_all = [x for x in day_rows if x.loi_nhuan_tuong_doi is not None]
        ic = spearman_rank_ic(
            [x.xac_suat_nhan_1 for x in valid_all],
            [float(x.loi_nhuan_tuong_doi) for x in valid_all],
        ) if valid_all else None
        daily.append({
            "ngay": day.isoformat(), "precision_at_k": precision, "hit_rate_top_k": hit_rate,
            "loi_nhuan_tuong_doi_trung_binh_top_k": avg_relative,
            "decile_spread": decile_spread(day_rows), "spearman_rank_ic": ic,
            "set_turnover": turnover, "so_ma_duoc_chon": len(selected),
        })
        previous = selected_set
    names = [
        "precision_at_k", "hit_rate_top_k", "loi_nhuan_tuong_doi_trung_binh_top_k",
        "decile_spread", "spearman_rank_ic", "set_turnover",
    ]
    aggregate: dict[str, float | None] = {}
    for name in names:
        values = [float(row[name]) for row in daily if row[name] is not None]
        aggregate[name] = fmean(values) if values else None
    return {"theo_ngay": daily, "tong_the": aggregate, "so_ngay_test": len(daily)}
