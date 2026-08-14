"""V29 predictive-target research lab for the frozen V22 history.

This module opens a separate research branch from the frozen V28 candidate. It
compares the frozen C3 score against pre-registered predictive challengers:

* ridge regression on monthly cross-sectional rank targets;
* ridge regression with market-regime interactions;
* logistic bottom-tail avoidance;
* an equal-weight hybrid of rank prediction and bottom-tail safety.

Every fold uses the V27 purged chronology. Hyperparameters are selected only on
the strictly-prior validation block. Results are diagnostic, post-selection,
and cannot approve research quality, live capital, or automatic orders.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import random
from statistics import fmean, median
from typing import Mapping, Sequence

from . import component_breadth_ablation_v27 as v27
from . import factor_diagnostics_v26 as factor_v26

SCHEMA_VERSION = "predictive_target_lab_v29"
REPORT_FILE = "predictive_target_lab_v29.json"
FROZEN_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
RIDGE_MODEL = "V29_RIDGE_MONTHLY_RANK"
RIDGE_REGIME_MODEL = "V29_RIDGE_RANK_REGIME_INTERACTION"
BOTTOM_MODEL = "V29_LOGIT_BOTTOM20_SAFE"
HYBRID_MODEL = "V29_HYBRID_RANK_AND_BOTTOM_SAFE"
MODEL_NAMES = (
    FROZEN_MODEL,
    RIDGE_MODEL,
    RIDGE_REGIME_MODEL,
    BOTTOM_MODEL,
    HYBRID_MODEL,
)
FEATURE_NAMES = tuple(v27.DEFAULT_COMPONENTS)
RIDGE_ALPHAS = (1.0, 10.0, 100.0)
LOGISTIC_CS = (0.1, 1.0, 10.0)
BOTTOM_FRACTION = 0.20
DEFAULT_EFFECTIVE_TRIALS = 32


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(
        buffer.getvalue(),
        encoding="utf-8-sig",
        newline="",
    )


def _group_rows(
    rows: Sequence[v27.ResearchRow],
) -> list[tuple[object, list[v27.ResearchRow]]]:
    grouped: dict[object, list[v27.ResearchRow]] = defaultdict(list)
    for row in rows:
        grouped[row.signal_day].append(row)
    return [
        (day, sorted(day_rows, key=lambda item: item.symbol))
        for day, day_rows in sorted(grouped.items())
    ]


def _design_matrix(
    rows: Sequence[v27.ResearchRow],
    *,
    regime_interactions: bool,
) -> list[list[float]]:
    by_key: dict[tuple[object, str], list[float]] = {}
    for _, day_rows in _group_rows(rows):
        ranked = v27._ranked_components(day_rows)
        for row, components in zip(day_rows, ranked):
            base = [float(components[name]) for name in FEATURE_NAMES]
            regime = (
                1.0
                if float(row.features["vnindex_tren_ma250"]) >= 0.5
                else 0.0
            )
            values = (
                base + [regime] + [value * regime for value in base]
                if regime_interactions
                else base
            )
            by_key[(row.signal_day, row.symbol)] = values
    return [by_key[(row.signal_day, row.symbol)] for row in rows]


def _monthly_rank_targets(rows: Sequence[v27.ResearchRow]) -> list[float]:
    target_by_key: dict[tuple[object, str], float] = {}
    for _, day_rows in _group_rows(rows):
        ranks = v27.average_percentile(
            [float(row.relative_return) for row in day_rows]
        )
        for row, value in zip(day_rows, ranks):
            target_by_key[(row.signal_day, row.symbol)] = float(value)
    return [target_by_key[(row.signal_day, row.symbol)] for row in rows]


def _safe_targets(rows: Sequence[v27.ResearchRow]) -> list[int]:
    ranked = _monthly_rank_targets(rows)
    return [1 if value > BOTTOM_FRACTION else 0 for value in ranked]


def _mean_monthly_ic(
    rows: Sequence[v27.ResearchRow],
    scores: Sequence[float],
) -> float:
    if len(rows) != len(scores):
        raise ValueError("V29_SCORE_LENGTH_MISMATCH")
    grouped: dict[object, list[tuple[float, float]]] = defaultdict(list)
    for row, score in zip(rows, scores):
        grouped[row.signal_day].append((float(score), row.relative_return))
    values = [
        v27._spearman(
            [score for score, _ in pairs],
            [value for _, value in pairs],
        )
        for pairs in grouped.values()
        if len(pairs) >= 5
    ]
    return fmean(values) if values else 0.0


def _bottom_tail_recall(
    rows: Sequence[v27.ResearchRow],
    safe_scores: Sequence[float],
) -> float:
    if len(rows) != len(safe_scores):
        raise ValueError("V29_SAFE_SCORE_LENGTH_MISMATCH")
    recalls: list[float] = []
    grouped: dict[object, list[tuple[v27.ResearchRow, float]]] = defaultdict(list)
    for row, score in zip(rows, safe_scores):
        grouped[row.signal_day].append((row, float(score)))
    for pairs in grouped.values():
        count = max(1, math.ceil(len(pairs) * BOTTOM_FRACTION))
        actual = {
            row.symbol
            for row, _ in sorted(
                pairs,
                key=lambda item: (item[0].relative_return, item[0].symbol),
            )[:count]
        }
        predicted = {
            row.symbol
            for row, _ in sorted(
                pairs,
                key=lambda item: (item[1], item[0].symbol),
            )[:count]
        }
        recalls.append(len(actual & predicted) / len(actual))
    return fmean(recalls) if recalls else 0.0


def _fit_ridge(
    train_rows: Sequence[v27.ResearchRow],
    validation_rows: Sequence[v27.ResearchRow],
    test_rows: Sequence[v27.ResearchRow],
    *,
    regime_interactions: bool,
) -> tuple[list[float], dict[str, object]]:
    try:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("V29_SKLEARN_NOT_INSTALLED") from exc

    train_x = _design_matrix(
        train_rows,
        regime_interactions=regime_interactions,
    )
    validation_x = _design_matrix(
        validation_rows,
        regime_interactions=regime_interactions,
    )
    test_x = _design_matrix(
        test_rows,
        regime_interactions=regime_interactions,
    )
    train_y = _monthly_rank_targets(train_rows)

    choices: list[tuple[float, float]] = []
    for alpha in RIDGE_ALPHAS:
        model = make_pipeline(
            StandardScaler(),
            Ridge(alpha=alpha, fit_intercept=True),
        )
        model.fit(train_x, train_y)
        validation_scores = [
            float(value) for value in model.predict(validation_x)
        ]
        choices.append(
            (_mean_monthly_ic(validation_rows, validation_scores), alpha)
        )
    validation_ic, selected_alpha = max(
        choices,
        key=lambda item: (item[0], -item[1]),
    )
    fit_rows = tuple(train_rows) + tuple(validation_rows)
    fit_x = _design_matrix(
        fit_rows,
        regime_interactions=regime_interactions,
    )
    fit_y = _monthly_rank_targets(fit_rows)
    model = make_pipeline(
        StandardScaler(),
        Ridge(alpha=selected_alpha, fit_intercept=True),
    )
    model.fit(fit_x, fit_y)
    scores = [float(value) for value in model.predict(test_x)]
    return scores, {
        "selected_alpha": selected_alpha,
        "validation_mean_rank_ic": validation_ic,
        "regime_interactions": regime_interactions,
        "uses_test_labels": False,
    }


def _fit_bottom_logistic(
    train_rows: Sequence[v27.ResearchRow],
    validation_rows: Sequence[v27.ResearchRow],
    test_rows: Sequence[v27.ResearchRow],
) -> tuple[list[float], dict[str, object]]:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("V29_SKLEARN_NOT_INSTALLED") from exc

    train_x = _design_matrix(train_rows, regime_interactions=False)
    validation_x = _design_matrix(
        validation_rows,
        regime_interactions=False,
    )
    test_x = _design_matrix(test_rows, regime_interactions=False)
    train_y = _safe_targets(train_rows)
    if len(set(train_y)) < 2:
        raise ValueError("V29_BOTTOM_TARGET_SINGLE_CLASS")

    choices: list[tuple[float, float, float]] = []
    for c_value in LOGISTIC_CS:
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=c_value,
                class_weight="balanced",
                max_iter=2000,
                solver="liblinear",
                random_state=20260802,
            ),
        )
        model.fit(train_x, train_y)
        safe_scores = [
            float(value)
            for value in model.predict_proba(validation_x)[:, 1]
        ]
        recall = _bottom_tail_recall(validation_rows, safe_scores)
        rank_ic = _mean_monthly_ic(validation_rows, safe_scores)
        choices.append((recall, rank_ic, c_value))
    recall, validation_ic, selected_c = max(
        choices,
        key=lambda item: (item[0], item[1], -item[2]),
    )
    fit_rows = tuple(train_rows) + tuple(validation_rows)
    fit_x = _design_matrix(fit_rows, regime_interactions=False)
    fit_y = _safe_targets(fit_rows)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=selected_c,
            class_weight="balanced",
            max_iter=2000,
            solver="liblinear",
            random_state=20260802,
        ),
    )
    model.fit(fit_x, fit_y)
    scores = [float(value) for value in model.predict_proba(test_x)[:, 1]]
    return scores, {
        "selected_c": selected_c,
        "validation_bottom20_recall": recall,
        "validation_mean_rank_ic": validation_ic,
        "uses_test_labels": False,
    }


def _percentile_scores(values: Sequence[float]) -> list[float]:
    return [float(value) for value in v27.average_percentile(values)]


def _fold_scores(
    fold: v27.Fold,
) -> tuple[dict[str, list[float]], list[dict[str, object]]]:
    frozen = v27._score_candidates(fold)[0][FROZEN_MODEL]
    ridge, ridge_meta = _fit_ridge(
        fold.train_rows,
        fold.validation_rows,
        fold.test_rows,
        regime_interactions=False,
    )
    ridge_regime, ridge_regime_meta = _fit_ridge(
        fold.train_rows,
        fold.validation_rows,
        fold.test_rows,
        regime_interactions=True,
    )
    safe, safe_meta = _fit_bottom_logistic(
        fold.train_rows,
        fold.validation_rows,
        fold.test_rows,
    )
    ridge_rank = _percentile_scores(ridge)
    safe_rank = _percentile_scores(safe)
    hybrid = [
        0.5 * left + 0.5 * right
        for left, right in zip(ridge_rank, safe_rank)
    ]
    metadata = [
        {
            "test_date": fold.test_day.isoformat(),
            "model": RIDGE_MODEL,
            **ridge_meta,
        },
        {
            "test_date": fold.test_day.isoformat(),
            "model": RIDGE_REGIME_MODEL,
            **ridge_regime_meta,
        },
        {
            "test_date": fold.test_day.isoformat(),
            "model": BOTTOM_MODEL,
            **safe_meta,
        },
        {
            "test_date": fold.test_day.isoformat(),
            "model": HYBRID_MODEL,
            "rank_weight": 0.5,
            "bottom_safe_weight": 0.5,
            "uses_test_labels": False,
        },
    ]
    return {
        FROZEN_MODEL: [float(value) for value in frozen],
        RIDGE_MODEL: ridge,
        RIDGE_REGIME_MODEL: ridge_regime,
        BOTTOM_MODEL: safe,
        HYBRID_MODEL: hybrid,
    }, metadata


def build_predictions(
    folds: Sequence[v27.Fold],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    predictions: list[dict[str, object]] = []
    selections: list[dict[str, object]] = []
    for fold in folds:
        scores, metadata = _fold_scores(fold)
        predictions.extend(v27._prediction_rows_for_scores(fold, scores))
        selections.extend(metadata)
    return predictions, selections


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _newey_west_mean(
    values: Sequence[float],
    *,
    lag: int = 3,
) -> dict[str, float]:
    sequence = [float(value) for value in values]
    count = len(sequence)
    if count < 3:
        return {
            "mean": fmean(sequence) if sequence else 0.0,
            "standard_error": 0.0,
            "t_stat": 0.0,
            "one_sided_p_value": 1.0,
        }
    mean_value = fmean(sequence)
    centered = [value - mean_value for value in sequence]
    gamma_zero = sum(value * value for value in centered) / count
    long_run = gamma_zero
    maximum_lag = min(max(0, lag), count - 1)
    for offset in range(1, maximum_lag + 1):
        covariance = sum(
            centered[index] * centered[index - offset]
            for index in range(offset, count)
        ) / count
        weight = 1.0 - offset / (maximum_lag + 1.0)
        long_run += 2.0 * weight * covariance
    standard_error = math.sqrt(max(long_run / count, 0.0))
    t_stat = mean_value / standard_error if standard_error > 0.0 else 0.0
    return {
        "mean": mean_value,
        "standard_error": standard_error,
        "t_stat": t_stat,
        "one_sided_p_value": 1.0 - _normal_cdf(t_stat),
    }


def _moving_block_bootstrap(
    values: Sequence[float],
    *,
    block_length: int,
    repetitions: int,
    seed: int,
) -> dict[str, float]:
    sequence = [float(value) for value in values]
    if not sequence:
        return {
            "lower_90": 0.0,
            "upper_90": 0.0,
            "probability_mean_positive": 0.0,
        }
    if block_length < 1 or repetitions < 100:
        raise ValueError("V29_BOOTSTRAP_CONFIG_INVALID")
    generator = random.Random(seed)
    count = len(sequence)
    means: list[float] = []
    for _ in range(repetitions):
        sample: list[float] = []
        while len(sample) < count:
            start = generator.randrange(count)
            sample.extend(
                sequence[(start + offset) % count]
                for offset in range(block_length)
            )
        means.append(fmean(sample[:count]))
    means.sort()
    lower_index = max(0, math.floor(0.05 * (repetitions - 1)))
    upper_index = min(
        repetitions - 1,
        math.ceil(0.95 * (repetitions - 1)),
    )
    return {
        "lower_90": means[lower_index],
        "upper_90": means[upper_index],
        "probability_mean_positive": (
            sum(value > 0.0 for value in means) / repetitions
        ),
    }


def _leave_best_mean(values: Sequence[float], count: int) -> float:
    sequence = sorted((float(value) for value in values), reverse=True)
    remaining = sequence[min(max(count, 0), len(sequence)):]
    return fmean(remaining) if remaining else 0.0


def _regime_by_date(folds: Sequence[v27.Fold]) -> dict[str, str]:
    return {
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


def _statistical_rows(
    diagnostics: Mapping[str, object],
    folds: Sequence[v27.Fold],
    *,
    bootstrap_repetitions: int,
    bootstrap_block_months: int,
    effective_trials: int,
    seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    periods = [dict(row) for row in diagnostics.get("period_rows", [])]
    regime = _regime_by_date(folds)
    by_model: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in periods:
        by_model[str(row.get("model") or "")].append(row)
    frozen_by_date = {
        str(row.get("test_date") or ""): float(row.get("rank_ic") or 0.0)
        for row in by_model.get(FROZEN_MODEL, [])
    }
    summary_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    for model in MODEL_NAMES:
        model_rows = sorted(
            by_model.get(model, []),
            key=lambda row: str(row.get("test_date") or ""),
        )
        values = [float(row.get("rank_ic") or 0.0) for row in model_rows]
        nw = _newey_west_mean(values, lag=3)
        bootstrap = _moving_block_bootstrap(
            values,
            block_length=bootstrap_block_months,
            repetitions=bootstrap_repetitions,
            seed=seed + sum(ord(char) for char in model),
        )
        adjusted_p = min(
            1.0,
            1.0 - (1.0 - nw["one_sided_p_value"]) ** effective_trials,
        )
        risk_on = [
            float(row.get("rank_ic") or 0.0)
            for row in model_rows
            if regime.get(str(row.get("test_date") or "")) == "RISK_ON"
        ]
        risk_off = [
            float(row.get("rank_ic") or 0.0)
            for row in model_rows
            if regime.get(str(row.get("test_date") or "")) == "RISK_OFF"
        ]
        midpoint = len(values) // 2
        summary_rows.append({
            "model": model,
            "period_count": len(values),
            "mean_rank_ic": nw["mean"],
            "median_rank_ic": median(values) if values else 0.0,
            "positive_rank_ic_ratio": (
                sum(value > 0.0 for value in values) / len(values)
                if values
                else 0.0
            ),
            "newey_west_lag": 3,
            "newey_west_standard_error": nw["standard_error"],
            "newey_west_t_stat": nw["t_stat"],
            "one_sided_p_value": nw["one_sided_p_value"],
            "effective_trials": effective_trials,
            "sidak_adjusted_one_sided_p_value": adjusted_p,
            "bootstrap_block_months": bootstrap_block_months,
            "bootstrap_repetitions": bootstrap_repetitions,
            "bootstrap_mean_ic_lower_90": bootstrap["lower_90"],
            "bootstrap_mean_ic_upper_90": bootstrap["upper_90"],
            "bootstrap_probability_mean_positive": bootstrap[
                "probability_mean_positive"
            ],
            "leave_best_1_mean_rank_ic": _leave_best_mean(values, 1),
            "leave_best_3_mean_rank_ic": _leave_best_mean(values, 3),
            "leave_best_6_mean_rank_ic": _leave_best_mean(values, 6),
            "first_half_mean_rank_ic": (
                fmean(values[:midpoint]) if midpoint else 0.0
            ),
            "second_half_mean_rank_ic": (
                fmean(values[midpoint:]) if values[midpoint:] else 0.0
            ),
            "risk_on_period_count": len(risk_on),
            "risk_on_mean_rank_ic": fmean(risk_on) if risk_on else 0.0,
            "risk_off_period_count": len(risk_off),
            "risk_off_mean_rank_ic": fmean(risk_off) if risk_off else 0.0,
        })
        if model == FROZEN_MODEL:
            continue
        deltas = [
            float(row.get("rank_ic") or 0.0)
            - frozen_by_date[str(row.get("test_date") or "")]
            for row in model_rows
            if str(row.get("test_date") or "") in frozen_by_date
        ]
        paired_nw = _newey_west_mean(deltas, lag=3)
        paired_bootstrap = _moving_block_bootstrap(
            deltas,
            block_length=bootstrap_block_months,
            repetitions=bootstrap_repetitions,
            seed=seed + 10000 + sum(ord(char) for char in model),
        )
        comparison_rows.append({
            "challenger": model,
            "baseline": FROZEN_MODEL,
            "paired_period_count": len(deltas),
            "mean_rank_ic_delta": paired_nw["mean"],
            "newey_west_delta_standard_error": paired_nw["standard_error"],
            "newey_west_delta_t_stat": paired_nw["t_stat"],
            "delta_one_sided_p_value": paired_nw["one_sided_p_value"],
            "delta_bootstrap_lower_90": paired_bootstrap["lower_90"],
            "delta_bootstrap_upper_90": paired_bootstrap["upper_90"],
            "delta_bootstrap_probability_positive": paired_bootstrap[
                "probability_mean_positive"
            ],
        })
    return summary_rows, comparison_rows


def _decision_rows(
    statistical_rows: Sequence[Mapping[str, object]],
    comparison_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], str]:
    summary = {
        str(row.get("model") or ""): row
        for row in statistical_rows
    }
    comparisons = {
        str(row.get("challenger") or ""): row
        for row in comparison_rows
    }
    frozen = summary[FROZEN_MODEL]
    decisions: list[dict[str, object]] = []
    for model in MODEL_NAMES:
        if model == FROZEN_MODEL:
            continue
        row = summary[model]
        paired = comparisons[model]
        gates = {
            "mean_ic_above_frozen_by_005": (
                float(row["mean_rank_ic"])
                >= float(frozen["mean_rank_ic"]) + 0.005
            ),
            "positive_ic_ratio_at_least_055": (
                float(row["positive_rank_ic_ratio"]) >= 0.55
            ),
            "second_half_ic_non_negative": (
                float(row["second_half_mean_rank_ic"]) >= 0.0
            ),
            "leave_best_3_ic_positive": (
                float(row["leave_best_3_mean_rank_ic"]) > 0.0
            ),
            "paired_delta_bootstrap_probability_at_least_080": (
                float(paired["delta_bootstrap_probability_positive"]) >= 0.80
            ),
            "risk_off_not_worse_than_frozen_by_01": (
                float(row["risk_off_mean_rank_ic"])
                >= float(frozen["risk_off_mean_rank_ic"]) - 0.01
            ),
        }
        passed = all(gates.values())
        decisions.append({
            "model": model,
            **gates,
            "predictive_challenger_gate_passed": passed,
            "failed_predictive_gates": "|".join(
                name for name, value in gates.items() if not value
            ),
            "independent_holdout": False,
            "research_eligible": False,
            "live_capital_approved": False,
        })
    recommendation = (
        "PROMOTE_PASSING_CHALLENGER_TO_V30_PORTFOLIO_ABLATION"
        if any(row["predictive_challenger_gate_passed"] for row in decisions)
        else "NO_CHALLENGER_PASSED_REDESIGN_FEATURES_OR_WAIT_FOR_NEW_DATA"
    )
    return decisions, recommendation


def run_predictive_target_lab(
    *,
    input_zip: Path,
    output_dir: Path,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
    bootstrap_repetitions: int = 2000,
    bootstrap_block_months: int = 3,
    effective_trials: int = DEFAULT_EFFECTIVE_TRIALS,
    seed: int = 20260802,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V29_OUTPUT_EXISTS:{destination}")
    if effective_trials < 1:
        raise ValueError("V29_EFFECTIVE_TRIALS_INVALID")
    rows, input_manifest = v27._load_input_zip(source)
    folds = v27.build_folds(
        rows,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        inner_validation_months=inner_validation_months,
    )
    predictions, selection_rows = build_predictions(folds)
    diagnostics = factor_v26.analyze_predictions(
        predictions,
        quantiles=5,
        top_k=10,
        rolling_months=12,
    )
    statistical_rows, comparison_rows = _statistical_rows(
        diagnostics,
        folds,
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_months=bootstrap_block_months,
        effective_trials=effective_trials,
        seed=seed,
    )
    decision_rows, recommendation = _decision_rows(
        statistical_rows,
        comparison_rows,
    )
    destination.mkdir(parents=True)
    try:
        _write_csv(destination / "predictions_v29.csv", predictions)
        _write_csv(destination / "hyperparameter_selection_v29.csv", selection_rows)
        _write_csv(
            destination / "factor_summary_v29.csv",
            diagnostics["summary_rows"],
        )
        _write_csv(
            destination / "factor_periods_v29.csv",
            diagnostics["period_rows"],
        )
        _write_csv(
            destination / "factor_quantiles_v29.csv",
            diagnostics["quantile_rows"],
        )
        _write_csv(destination / "statistical_summary_v29.csv", statistical_rows)
        _write_csv(destination / "paired_comparison_v29.csv", comparison_rows)
        _write_csv(destination / "decision_gates_v29.csv", decision_rows)
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "experiment": "POST_SELECTION_PREDICTIVE_TARGET_RESEARCH_ONLY",
            "input_zip": str(source),
            "input_zip_sha256": _sha256(source),
            "input_manifest_schema": input_manifest.get("schema_version"),
            "output_dir": str(destination),
            "usable_input_row_count": len(rows),
            "walk_forward_fold_count": len(folds),
            "walk_forward_first_test_date": folds[0].test_day.isoformat(),
            "walk_forward_last_test_date": folds[-1].test_day.isoformat(),
            "models": list(MODEL_NAMES),
            "feature_names": list(FEATURE_NAMES),
            "targets": {
                RIDGE_MODEL: "MONTHLY_CROSS_SECTIONAL_RELATIVE_RETURN_PERCENTILE",
                RIDGE_REGIME_MODEL: "MONTHLY_CROSS_SECTIONAL_RELATIVE_RETURN_PERCENTILE",
                BOTTOM_MODEL: "SAFE_NOT_IN_BOTTOM_20_PERCENT_RELATIVE_RETURN",
                HYBRID_MODEL: "EQUAL_WEIGHT_RIDGE_RANK_AND_BOTTOM_SAFE",
            },
            "hyperparameter_contract": {
                "ridge_alphas": list(RIDGE_ALPHAS),
                "logistic_cs": list(LOGISTIC_CS),
                "selection_uses_only_prior_validation": True,
            },
            "statistical_contract": {
                "newey_west_lag": 3,
                "bootstrap_repetitions": bootstrap_repetitions,
                "bootstrap_block_months": bootstrap_block_months,
                "effective_trials": effective_trials,
                "effective_trials_is_conservative_user_config": True,
                "dsr_claimed": False,
                "pbo_claimed": False,
            },
            "recommendation": recommendation,
            "passing_models": [
                str(row["model"])
                for row in decision_rows
                if row["predictive_challenger_gate_passed"]
            ],
            "frozen_v28_candidate_modified": False,
            "future_holdout_clock_reset": False,
            "independent_holdout": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "requires_confirmation_before_v30": True,
            "data_blockers_unchanged": [
                "PRICE_BASIS_CHUA_XAC_NHAN",
                "CORPORATE_ACTIONS_CHUA_DAY_DU",
                "CANDIDATE_UNION_IS_NOT_POINT_IN_TIME",
                "SURVIVORSHIP_BIAS_NOT_RESOLVED",
            ],
            "statistical_rows": statistical_rows,
            "paired_comparison_rows": comparison_rows,
            "decision_rows": decision_rows,
        }
        _write_json(destination / REPORT_FILE, report)
        return report
    except Exception:
        for path in sorted(destination.glob("*")):
            if path.is_file():
                path.unlink()
        destination.rmdir()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.predictive_target_lab_v29"
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--bootstrap-block-months", type=int, default=3)
    parser.add_argument(
        "--effective-trials",
        type=int,
        default=DEFAULT_EFFECTIVE_TRIALS,
    )
    parser.add_argument("--seed", type=int, default=20260802)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_predictive_target_lab(
            input_zip=args.input_zip,
            output_dir=args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            effective_trials=args.effective_trials,
            seed=args.seed,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report["status"],
        "output_dir": report["output_dir"],
        "walk_forward_fold_count": report["walk_forward_fold_count"],
        "recommendation": report["recommendation"],
        "passing_models": report["passing_models"],
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "MODEL_NAMES",
    "FEATURE_NAMES",
    "build_predictions",
    "run_predictive_target_lab",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
