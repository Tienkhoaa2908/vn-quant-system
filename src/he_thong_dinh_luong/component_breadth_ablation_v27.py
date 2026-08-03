"""V27 component-stability and fixed-breadth portfolio ablation.

V27 is deliberately lightweight. It does not retrain LightGBM, XGBoost or
Torch. It rebuilds deterministic cross-sectional scores from the frozen V22
feature/label input, audits individual components and candidate blends, then
reuses the V15 chronological portfolio evaluator at fixed Top-K breadths.

The experiment was designed after reviewing V23/V25/V26 results. Therefore it
is a post-review sensitivity analysis, not an independent holdout. It can
recommend the next research step but can never approve research quality, live
capital or automatic orders.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import io
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence
import zipfile

from . import factor_diagnostics_v26 as factor_v26
from . import model_lab_upgrade_v15 as v15
from .model_policy_ablation_v25 import _cost_from_summary

SCHEMA_VERSION = "component_breadth_ablation_v27"
REPORT_FILE = "component_breadth_ablation_v27.json"
DEFAULT_BREADTHS = (10, 15, 20, 30)
DEFAULT_COMPONENTS = (
    "momentum_12_1",
    "relative_strength_120",
    "momentum_over_volatility",
    "trend_structure",
    "low_volatility",
    "momentum_consistency",
    "high_52_week",
)
CURRENT_WEIGHTS: Mapping[str, float] = {
    "momentum_12_1": 0.28,
    "relative_strength_120": 0.22,
    "momentum_over_volatility": 0.18,
    "trend_structure": 0.12,
    "low_volatility": 0.10,
    "momentum_consistency": 0.10,
}
STABLE_THREE = ("low_volatility", "relative_strength_120", "high_52_week")
STABLE_TWO = ("low_volatility", "relative_strength_120")
CANDIDATE_MODELS = (
    "C0_CURRENT_ROBUST",
    "C1_STABLE_3_EQUAL",
    "C2_STABLE_2_EQUAL",
    "C3_STABLE_3_PAST_IC_SHRUNK",
)


@dataclass(frozen=True)
class ResearchRow:
    signal_day: date
    symbol: str
    label_end: date
    stock_return: float
    benchmark_return: float
    relative_return: float
    features: Mapping[str, float]


@dataclass(frozen=True)
class Fold:
    test_day: date
    train_rows: tuple[ResearchRow, ...]
    validation_rows: tuple[ResearchRow, ...]
    test_rows: tuple[ResearchRow, ...]


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"V27_JSON_OBJECT_REQUIRED:{Path(path).name}")
    return value


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and not fields:
        return
    fieldnames = list(fields or rows[0].keys())
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _finite(value: object, *, name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"V27_MISSING_NUMERIC:{name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V27_NON_FINITE:{name}")
    return number


def _parse_date(value: object, *, name: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"V27_MISSING_DATE:{name}")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"V27_INVALID_DATE:{name}:{text}") from exc


def average_percentile(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(
        range(len(values)),
        key=lambda index: (float(values[index]), index),
    )
    denominator = max(len(values) - 1, 1)
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while (
            end < len(order)
            and float(values[order[end]]) == float(values[order[start]])
        ):
            end += 1
        percentile = ((start + end - 1) / 2.0) / denominator
        for position in range(start, end):
            result[order[position]] = percentile
        start = end
    return result


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        return 0.0
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0.0 else 0.0


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _pearson(average_percentile(left), average_percentile(right))


def _raw_components(features: Mapping[str, float]) -> dict[str, float]:
    momentum = float(features["dong_luong_12_1"])
    volatility = max(abs(float(features["bien_dong_60"])), 1e-6)
    trend = fmean(
        float(features[name])
        for name in (
            "khoang_cach_ma60",
            "khoang_cach_ma120",
            "khoang_cach_ma250",
        )
    )
    consistency = fmean(
        1.0 if float(features[name]) > 0.0 else 0.0
        for name in (
            "loi_nhuan_20",
            "loi_nhuan_60",
            "loi_nhuan_120",
            "loi_nhuan_250",
        )
    )
    return {
        "momentum_12_1": momentum,
        "relative_strength_120": float(features["suc_manh_tuong_doi_120"]),
        "momentum_over_volatility": momentum / volatility,
        "trend_structure": trend,
        "low_volatility": -volatility,
        "momentum_consistency": consistency,
        "high_52_week": float(features["ty_le_dinh_52_tuan"]),
    }


def _load_input_zip(
    path: Path,
) -> tuple[list[ResearchRow], dict[str, object]]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError("V27_INPUT_ZIP_NOT_FOUND")
    with zipfile.ZipFile(source) as archive:
        required = {"feature_raw.csv", "nhan.csv", "manifest.json"}
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError(
                "V27_INPUT_FILES_MISSING:" + "|".join(sorted(missing))
            )
        manifest = json.loads(
            archive.read("manifest.json").decode("utf-8-sig")
        )
        if not isinstance(manifest, dict):
            raise ValueError("V27_INPUT_MANIFEST_OBJECT_REQUIRED")
        with archive.open("nhan.csv") as raw:
            labels = {
                (
                    str(row.get("ngay") or ""),
                    str(row.get("ma") or "").upper(),
                ): row
                for row in csv.DictReader(
                    io.TextIOWrapper(
                        raw,
                        encoding="utf-8-sig",
                        newline="",
                    )
                )
            }
        rows: list[ResearchRow] = []
        feature_names = {
            "dong_luong_12_1",
            "bien_dong_60",
            "suc_manh_tuong_doi_120",
            "khoang_cach_ma60",
            "khoang_cach_ma120",
            "khoang_cach_ma250",
            "loi_nhuan_20",
            "loi_nhuan_60",
            "loi_nhuan_120",
            "loi_nhuan_250",
            "ty_le_dinh_52_tuan",
            "vnindex_tren_ma250",
        }
        with archive.open("feature_raw.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    newline="",
                )
            )
            for feature_row in reader:
                if not _truthy(feature_row.get("hop_le")):
                    continue
                if not _truthy(feature_row.get("eligible")):
                    continue
                key = (
                    str(feature_row.get("ngay") or ""),
                    str(feature_row.get("ma") or "").upper(),
                )
                label = labels.get(key)
                if label is None:
                    continue
                required_label = (
                    label.get("ngay_ket_thuc_nhan"),
                    label.get("loi_nhuan_co_phieu"),
                    label.get("loi_nhuan_benchmark"),
                    label.get("loi_nhuan_tuong_doi"),
                )
                if any(value in (None, "") for value in required_label):
                    continue
                try:
                    features = {
                        name: _finite(feature_row.get(name), name=name)
                        for name in feature_names
                    }
                    rows.append(
                        ResearchRow(
                            signal_day=_parse_date(
                                feature_row.get("ngay"),
                                name="ngay",
                            ),
                            symbol=str(
                                feature_row.get("ma") or ""
                            ).upper(),
                            label_end=_parse_date(
                                label.get("ngay_ket_thuc_nhan"),
                                name="ngay_ket_thuc_nhan",
                            ),
                            stock_return=_finite(
                                label.get("loi_nhuan_co_phieu"),
                                name="loi_nhuan_co_phieu",
                            ),
                            benchmark_return=_finite(
                                label.get("loi_nhuan_benchmark"),
                                name="loi_nhuan_benchmark",
                            ),
                            relative_return=_finite(
                                label.get("loi_nhuan_tuong_doi"),
                                name="loi_nhuan_tuong_doi",
                            ),
                            features=features,
                        )
                    )
                except ValueError:
                    continue
    rows.sort(key=lambda row: (row.signal_day, row.symbol))
    if not rows:
        raise ValueError("V27_NO_USABLE_ROWS")
    return rows, manifest


def build_folds(
    rows: Sequence[ResearchRow],
    *,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
) -> list[Fold]:
    if evaluation_months < 3:
        raise ValueError("V27_EVALUATION_MONTHS_TOO_SMALL")
    if minimum_train_months < 12:
        raise ValueError("V27_MINIMUM_TRAIN_MONTHS_TOO_SMALL")
    if inner_validation_months < 1:
        raise ValueError("V27_INNER_VALIDATION_MONTHS_TOO_SMALL")
    dates = sorted({row.signal_day for row in rows})
    candidate_dates = dates[-min(evaluation_months, len(dates)):]
    folds: list[Fold] = []
    for test_day in candidate_dates:
        eligible = [
            row
            for row in rows
            if row.signal_day < test_day and row.label_end < test_day
        ]
        eligible_dates = sorted({row.signal_day for row in eligible})
        if (
            len(eligible_dates)
            < minimum_train_months + inner_validation_months
        ):
            continue
        validation_ordered = eligible_dates[-inner_validation_months:]
        validation_dates = set(validation_ordered)
        validation_start = validation_ordered[0]
        train_pool = [
            row
            for row in eligible
            if row.signal_day not in validation_dates
            and row.label_end < validation_start
        ]
        train_dates = sorted({row.signal_day for row in train_pool})
        if len(train_dates) < minimum_train_months:
            continue
        test_rows = tuple(
            row for row in rows if row.signal_day == test_day
        )
        if not test_rows:
            continue
        folds.append(
            Fold(
                test_day=test_day,
                train_rows=tuple(train_pool),
                validation_rows=tuple(
                    row
                    for row in eligible
                    if row.signal_day in validation_dates
                ),
                test_rows=test_rows,
            )
        )
    if len(folds) < 3:
        raise ValueError("V27_TOO_FEW_VALID_FOLDS")
    return folds


def _monthly_component_ics(
    rows: Sequence[ResearchRow],
    component_names: Sequence[str],
) -> dict[str, list[float]]:
    by_day: dict[date, list[ResearchRow]] = {}
    for row in rows:
        by_day.setdefault(row.signal_day, []).append(row)
    output = {name: [] for name in component_names}
    for day_rows in by_day.values():
        if len(day_rows) < 5:
            continue
        raw = [_raw_components(row.features) for row in day_rows]
        returns = [row.relative_return for row in day_rows]
        for name in component_names:
            output[name].append(
                _spearman([item[name] for item in raw], returns)
            )
    return output


def shrunk_component_weights(
    rows: Sequence[ResearchRow],
    *,
    components: Sequence[str] = STABLE_THREE,
    shrinkage_to_equal: float = 0.50,
    max_component_weight: float = 0.50,
) -> dict[str, float]:
    if not 0.0 <= shrinkage_to_equal <= 1.0:
        raise ValueError("V27_INVALID_SHRINKAGE")
    if not 0.0 < max_component_weight <= 1.0:
        raise ValueError("V27_INVALID_COMPONENT_CAP")
    names = tuple(components)
    if not names:
        raise ValueError("V27_EMPTY_COMPONENT_SET")
    ic_history = _monthly_component_ics(rows, names)
    means = {
        name: fmean(ic_history[name]) if ic_history[name] else 0.0
        for name in names
    }
    positive = {
        name: max(value, 0.0)
        for name, value in means.items()
    }
    positive_total = sum(positive.values())
    empirical = (
        {
            name: positive[name] / positive_total
            for name in names
        }
        if positive_total > 0.0
        else {name: 1.0 / len(names) for name in names}
    )
    equal = 1.0 / len(names)
    raw = {
        name: (
            shrinkage_to_equal * equal
            + (1.0 - shrinkage_to_equal) * empirical[name]
        )
        for name in names
    }
    capped = {
        name: min(value, max_component_weight)
        for name, value in raw.items()
    }
    total = sum(capped.values())
    if total <= 0.0:
        raise ValueError("V27_COMPONENT_WEIGHT_NORMALIZATION_FAILED")
    return {name: capped[name] / total for name in names}


def _ranked_components(
    rows: Sequence[ResearchRow],
) -> list[dict[str, float]]:
    raw = [_raw_components(row.features) for row in rows]
    ranked = [dict() for _ in rows]
    for name in DEFAULT_COMPONENTS:
        values = average_percentile([item[name] for item in raw])
        for index, value in enumerate(values):
            ranked[index][name] = value
    return ranked


def _score_candidates(
    fold: Fold,
) -> tuple[
    dict[str, list[float]],
    dict[str, float],
    list[dict[str, float]],
]:
    ranked = _ranked_components(fold.test_rows)
    history = tuple(fold.train_rows) + tuple(fold.validation_rows)
    adaptive = shrunk_component_weights(history)
    scores: dict[str, list[float]] = {
        "C0_CURRENT_ROBUST": [
            sum(
                CURRENT_WEIGHTS[name] * components[name]
                for name in CURRENT_WEIGHTS
            )
            for components in ranked
        ],
        "C1_STABLE_3_EQUAL": [
            fmean(components[name] for name in STABLE_THREE)
            for components in ranked
        ],
        "C2_STABLE_2_EQUAL": [
            fmean(components[name] for name in STABLE_TWO)
            for components in ranked
        ],
        "C3_STABLE_3_PAST_IC_SHRUNK": [
            sum(
                adaptive[name] * components[name]
                for name in STABLE_THREE
            )
            for components in ranked
        ],
    }
    return scores, adaptive, ranked


def _prediction_rows_for_scores(
    fold: Fold,
    model_scores: Mapping[str, Sequence[float]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for model, scores in model_scores.items():
        if len(scores) != len(fold.test_rows):
            raise ValueError(f"V27_SCORE_LENGTH_MISMATCH:{model}")
        order = sorted(
            range(len(scores)),
            key=lambda index: (
                -float(scores[index]),
                fold.test_rows[index].symbol,
            ),
        )
        rank = {
            index: position + 1
            for position, index in enumerate(order)
        }
        percentiles = average_percentile(
            [float(value) for value in scores]
        )
        for index, row in enumerate(fold.test_rows):
            output.append(
                {
                    "model": model,
                    "fold": f"wf_{fold.test_day.isoformat()}",
                    "test_date": fold.test_day.isoformat(),
                    "symbol": row.symbol,
                    "score": float(scores[index]),
                    "percentile": percentiles[index],
                    "rank": rank[index],
                    "selected_top_k": "false",
                    "label_end": row.label_end.isoformat(),
                    "stock_return": row.stock_return,
                    "benchmark_return": row.benchmark_return,
                    "relative_return": row.relative_return,
                }
            )
    return output


def build_predictions(
    folds: Sequence[Fold],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    candidate_rows: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    for fold in folds:
        scores, adaptive, ranked = _score_candidates(fold)
        candidate_rows.extend(
            _prediction_rows_for_scores(fold, scores)
        )
        component_scores = {
            f"F_{component.upper()}": [
                item[component] for item in ranked
            ]
            for component in DEFAULT_COMPONENTS
        }
        component_rows.extend(
            _prediction_rows_for_scores(fold, component_scores)
        )
        weight_rows.append(
            {
                "test_date": fold.test_day.isoformat(),
                **{
                    f"weight_{name}": adaptive[name]
                    for name in STABLE_THREE
                },
                "uses_test_labels": "false",
            }
        )
    return candidate_rows, component_rows, weight_rows


def _component_correlations(
    folds: Sequence[Fold],
) -> list[dict[str, object]]:
    pair_values: dict[tuple[str, str], list[float]] = {}
    for left_index, left in enumerate(DEFAULT_COMPONENTS):
        for right in DEFAULT_COMPONENTS[left_index:]:
            pair_values[(left, right)] = []
    for fold in folds:
        raw = [_raw_components(row.features) for row in fold.test_rows]
        for left, right in pair_values:
            pair_values[(left, right)].append(
                _spearman(
                    [item[left] for item in raw],
                    [item[right] for item in raw],
                )
            )
    return [
        {
            "component_left": left,
            "component_right": right,
            "mean_cross_sectional_rank_correlation": (
                fmean(values) if values else 0.0
            ),
            "period_count": len(values),
        }
        for (left, right), values in sorted(pair_values.items())
    ]


def _quantile_shape(
    quantile_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[float]] = {}
    for row in quantile_rows:
        key = (
            str(row.get("model") or ""),
            int(row.get("quantile", 0) or 0),
        )
        grouped.setdefault(key, []).append(
            float(row.get("mean_relative_return", 0.0) or 0.0)
        )
    models = sorted({model for model, _ in grouped})
    output: list[dict[str, object]] = []
    for model in models:
        record: dict[str, object] = {"model": model}
        means: dict[int, float] = {}
        compounds: dict[int, float] = {}
        for quantile in range(1, 6):
            values = grouped.get((model, quantile), [])
            means[quantile] = fmean(values) if values else 0.0
            nav = 1.0
            for value in values:
                nav *= 1.0 + value
            compounds[quantile] = nav - 1.0
            record[f"q{quantile}_mean_relative_return"] = means[quantile]
            record[f"q{quantile}_compound_relative_return"] = (
                compounds[quantile]
            )
        record["adjacent_monotonic_pair_ratio"] = sum(
            means[index + 1] >= means[index]
            for index in range(1, 5)
        ) / 4.0
        record["q5_minus_q1_mean_relative_return"] = (
            means[5] - means[1]
        )
        record["q5_not_materially_below_q2_q3"] = (
            means[5] >= max(means[2], means[3]) - 0.0025
        )
        output.append(record)
    return output


def _regime_summary(
    period_rows: Sequence[Mapping[str, object]],
    folds: Sequence[Fold],
) -> list[dict[str, object]]:
    regime_by_day = {
        fold.test_day.isoformat(): (
            "RISK_ON"
            if median(
                float(row.features["vnindex_tren_ma250"])
                for row in fold.test_rows
            )
            >= 0.5
            else "RISK_OFF"
        )
        for fold in folds
    }
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in period_rows:
        day = str(row.get("test_date") or "")
        model = str(row.get("model") or "")
        regime = regime_by_day.get(day, "UNKNOWN")
        grouped.setdefault((model, regime), []).append(
            float(row.get("rank_ic", 0.0) or 0.0)
        )
    return [
        {
            "model": model,
            "regime": regime,
            "period_count": len(values),
            "mean_rank_ic": fmean(values) if values else 0.0,
            "positive_rank_ic_ratio": (
                sum(value > 0.0 for value in values) / len(values)
                if values
                else 0.0
            ),
        }
        for (model, regime), values in sorted(grouped.items())
    ]


def _signal_gates(
    summary_rows: Sequence[Mapping[str, object]],
    quantile_shape_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    shape_by_model = {
        str(row.get("model") or ""): row
        for row in quantile_shape_rows
    }
    output: list[dict[str, object]] = []
    for row in summary_rows:
        model = str(row.get("model") or "")
        if model not in CANDIDATE_MODELS:
            continue
        shape = shape_by_model.get(model, {})
        gate = {
            "mean_rank_ic_at_least_003": float(
                row.get("mean_rank_ic", 0.0) or 0.0
            )
            >= 0.03,
            "positive_rank_ic_ratio_at_least_055": float(
                row.get("positive_rank_ic_ratio", 0.0) or 0.0
            )
            >= 0.55,
            "second_half_mean_rank_ic_non_negative": float(
                row.get("second_half_mean_rank_ic", 0.0) or 0.0
            )
            >= 0.0,
            "top_minus_bottom_compound_positive": float(
                row.get(
                    "top_minus_bottom_compound_difference",
                    0.0,
                )
                or 0.0
            )
            > 0.0,
            "leave_best_top_minus_bottom_positive": float(
                row.get(
                    "leave_best_period_out_top_minus_bottom_compound_difference",
                    0.0,
                )
                or 0.0
            )
            > 0.0,
            "q5_not_materially_below_q2_q3": bool(
                shape.get("q5_not_materially_below_q2_q3", False)
            ),
        }
        output.append(
            {
                "model": model,
                **gate,
                "signal_gate_passed": all(gate.values()),
                "failed_signal_gates": "|".join(
                    key
                    for key, value in gate.items()
                    if not value
                ),
            }
        )
    return output


def _normalize_breadths(values: Sequence[int]) -> tuple[int, ...]:
    result = tuple(sorted(set(int(value) for value in values)))
    if not result or any(value < 5 or value > 50 for value in result):
        raise ValueError("V27_INVALID_BREADTHS")
    return result


def _portfolio_evaluations(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
    cost: object,
    validation_months: int,
    test_months: int,
    minimum_outer_test_periods: int,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    results: dict[str, object] = {}
    summary_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    stress_rows: list[dict[str, object]] = []
    for breadth in _normalize_breadths(breadths):
        evaluation = v15.model_wise_nested_evaluation(
            prediction_rows,
            top_k=breadth,
            candidate_models=CANDIDATE_MODELS,
            validation_months=validation_months,
            test_months=test_months,
            minimum_outer_test_periods=minimum_outer_test_periods,
            cost=cost,
        )
        for key, destination in (
            ("summary_rows", summary_rows),
            ("selection_rows", selection_rows),
            ("outer_rows", outer_rows),
            ("stress_rows", stress_rows),
        ):
            for raw in evaluation.get(key, []):
                destination.append(
                    {"breadth": breadth, **dict(raw)}
                )
        results[str(breadth)] = {
            "status": evaluation.get("status"),
            "historical_reference_model": evaluation.get(
                "historical_reference_model"
            ),
            "historical_reference_gate_passed": evaluation.get(
                "historical_reference_gate_passed"
            ),
            "model_details": evaluation.get("model_details", {}),
        }
    return (
        results,
        summary_rows,
        selection_rows,
        outer_rows,
        stress_rows,
    )


def _decision_rows(
    signal_rows: Sequence[Mapping[str, object]],
    portfolio_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], str]:
    signal_by_model = {
        str(row.get("model") or ""): bool(
            row.get("signal_gate_passed")
        )
        for row in signal_rows
    }
    baseline = next(
        (
            row
            for row in portfolio_rows
            if int(row.get("breadth", 0) or 0) == 10
            and str(row.get("model") or "")
            == "C0_CURRENT_ROBUST"
        ),
        None,
    )
    baseline_drawdown = float(
        baseline.get("base_max_drawdown", -1.0)
        if baseline
        else -1.0
    )
    output: list[dict[str, object]] = []
    for row in portfolio_rows:
        model = str(row.get("model") or "")
        gate = {
            "signal_gate_passed": signal_by_model.get(model, False),
            "base_relative_total_return_positive": float(
                row.get("base_relative_total_return", 0.0) or 0.0
            )
            > 0.0,
            "stress_relative_total_return_positive": float(
                row.get("stress_relative_total_return", 0.0) or 0.0
            )
            > 0.0,
            "positive_monthly_excess_at_least_half": float(
                row.get("base_positive_net_excess_ratio", 0.0) or 0.0
            )
            >= 0.50,
            "leave_best_month_out_relative_positive": float(
                row.get(
                    "base_leave_best_period_out_relative_total_return",
                    0.0,
                )
                or 0.0
            )
            > 0.0,
            "drawdown_not_worse_than_current_top10": float(
                row.get("base_max_drawdown", -1.0) or -1.0
            )
            >= baseline_drawdown,
        }
        output.append(
            {
                "breadth": int(row.get("breadth", 0) or 0),
                "model": model,
                **gate,
                "v27_decision_gate_passed": all(gate.values()),
                "failed_v27_decision_gates": "|".join(
                    key
                    for key, value in gate.items()
                    if not value
                ),
            }
        )
    if any(bool(row["v27_decision_gate_passed"]) for row in output):
        recommendation = "RUN_V28_FULL_WALK_FORWARD"
    elif any(
        bool(row.get("signal_gate_passed"))
        for row in signal_rows
    ):
        recommendation = "KEEP_SCORE_OPTIMIZE_PORTFOLIO"
    else:
        recommendation = "REDESIGN_TARGET_AND_FEATURES"
    return output, recommendation


def run_v27(
    input_zip: Path,
    model_output: Path,
    output_dir: Path,
    *,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
    nested_validation_months: int = 6,
    nested_test_months: int = 3,
    minimum_outer_test_periods: int = 48,
    breadths: Sequence[int] = DEFAULT_BREADTHS,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    model_root = Path(model_output).resolve()
    destination = Path(output_dir).resolve()
    if not model_root.is_dir():
        raise ValueError("V27_MODEL_OUTPUT_NOT_FOUND")
    summary_path = model_root / "model_lab_summary.json"
    if not summary_path.is_file():
        raise ValueError("V27_MODEL_SUMMARY_NOT_FOUND")
    if destination.exists():
        raise FileExistsError(f"V27_OUTPUT_EXISTS:{destination}")

    rows, input_manifest = _load_input_zip(source)
    folds = build_folds(
        rows,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        inner_validation_months=inner_validation_months,
    )
    candidate_rows, component_rows, adaptive_rows = build_predictions(folds)
    factor = factor_v26.analyze_predictions(
        candidate_rows + component_rows,
        quantiles=5,
        top_k=10,
        rolling_months=12,
    )
    factor_summary = list(factor.get("summary_rows", []))
    factor_periods = list(factor.get("period_rows", []))
    factor_quantiles = list(factor.get("quantile_rows", []))
    quantile_shape = _quantile_shape(factor_quantiles)
    signal_rows = _signal_gates(factor_summary, quantile_shape)
    correlation_rows = _component_correlations(folds)
    regime_rows = _regime_summary(factor_periods, folds)

    _, cost = _cost_from_summary(_read_json(summary_path))
    (
        portfolio_results,
        portfolio_rows,
        selection_rows,
        outer_rows,
        stress_rows,
    ) = _portfolio_evaluations(
        candidate_rows,
        breadths=breadths,
        cost=cost,
        validation_months=nested_validation_months,
        test_months=nested_test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    decision_rows, recommendation = _decision_rows(
        signal_rows,
        portfolio_rows,
    )

    destination.mkdir(parents=True)
    try:
        files = {
            "candidate_predictions_v27.csv": candidate_rows,
            "adaptive_component_weights_v27.csv": adaptive_rows,
            "factor_summary_v27.csv": factor_summary,
            "factor_periods_v27.csv": factor_periods,
            "factor_quantiles_v27.csv": factor_quantiles,
            "quantile_shape_v27.csv": quantile_shape,
            "signal_gates_v27.csv": signal_rows,
            "component_correlation_v27.csv": correlation_rows,
            "regime_summary_v27.csv": regime_rows,
            "portfolio_comparison_v27.csv": portfolio_rows,
            "policy_selection_v27.csv": selection_rows,
            "outer_test_periods_v27.csv": outer_rows,
            "outer_test_stress_periods_v27.csv": stress_rows,
            "decision_gates_v27.csv": decision_rows,
        }
        for name, output_rows in files.items():
            _write_csv(destination / name, output_rows)
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "experiment": (
                "COMPONENT_STABILITY_AND_FIXED_BREADTH_ABLATION"
            ),
            "input_zip": str(source),
            "input_zip_sha256": _sha256(source),
            "input_manifest_schema_version": input_manifest.get(
                "schema_version"
            ),
            "source_model_output": str(model_root),
            "source_model_summary_sha256": _sha256(summary_path),
            "usable_input_row_count": len(rows),
            "walk_forward_fold_count": len(folds),
            "walk_forward_first_test_date": (
                folds[0].test_day.isoformat()
            ),
            "walk_forward_last_test_date": (
                folds[-1].test_day.isoformat()
            ),
            "candidate_models": list(CANDIDATE_MODELS),
            "component_models": [
                f"F_{name.upper()}"
                for name in DEFAULT_COMPONENTS
            ],
            "breadths": list(_normalize_breadths(breadths)),
            "evaluation_months": evaluation_months,
            "minimum_train_months": minimum_train_months,
            "inner_validation_months": inner_validation_months,
            "nested_validation_months": nested_validation_months,
            "nested_test_months": nested_test_months,
            "minimum_outer_test_periods": minimum_outer_test_periods,
            "predictive_label_horizon": "20_SESSIONS_UNCHANGED",
            "model_test_fold": "ONE_MONTH_UNCHANGED",
            "turnover_policy_baseline": (
                "SIX_PRIOR_MONTHS_SELECT_CAP_FOR_THREE_MONTHS"
            ),
            "factor_diagnostics": {
                "summary_rows": factor_summary,
                "quantile_shape_rows": quantile_shape,
                "signal_gate_rows": signal_rows,
            },
            "portfolio_results": portfolio_results,
            "decision_gate_rows": decision_rows,
            "recommendation": recommendation,
            "requires_confirmation_before_v28": True,
            "required_next_output": (
                "component_breadth_ablation_v27.json "
                "and decision_gates_v27.csv"
            ),
            "heavy_models_retrained": False,
            "rolling_72_required": False,
            "sensitivity_analysis_only": True,
            "independent_holdout": False,
            "technical_validation_only": True,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(destination / REPORT_FILE, report)
    except Exception:
        for path in destination.glob("*"):
            if path.is_file():
                path.unlink()
        destination.rmdir()
        raise
    return {**report, "output_dir": str(destination)}


def _parse_breadths(value: str) -> tuple[int, ...]:
    return tuple(
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "python -m "
            "he_thong_dinh_luong.component_breadth_ablation_v27"
        )
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--nested-validation-months", type=int, default=6)
    parser.add_argument("--nested-test-months", type=int, default=3)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    parser.add_argument(
        "--breadths",
        type=_parse_breadths,
        default=DEFAULT_BREADTHS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_v27(
            args.input_zip,
            args.model_output,
            args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            nested_validation_months=args.nested_validation_months,
            nested_test_months=args.nested_test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            breadths=args.breadths,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "output_dir": result["output_dir"],
                "report": str(
                    Path(result["output_dir"]) / REPORT_FILE
                ),
                "walk_forward_fold_count": result[
                    "walk_forward_fold_count"
                ],
                "recommendation": result["recommendation"],
                "requires_confirmation_before_v28": True,
                "live_capital_approved": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "ResearchRow",
    "Fold",
    "average_percentile",
    "build_folds",
    "shrunk_component_weights",
    "build_predictions",
    "run_v27",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
