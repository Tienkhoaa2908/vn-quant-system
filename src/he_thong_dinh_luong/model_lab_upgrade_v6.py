"""Model Lab v6: regime-aware linear ranking and prior-only polarity calibration.

This upgrade targets predictive value rather than execution cosmetics:

* Ridge selects between discrete and continuous cross-sectional rank targets.
* Ridge can use market-regime interactions so a common VNINDEX state can alter
  cross-sectional stock ordering.
* The online ensemble may invert a model only after completed prior folds show
  persistent negative IC. Current-fold labels are never used.
* Every v6 predictive policy is post-hoc relative to the 2026-07-30 artifact and
  remains non-actionable until genuinely future holdout evidence is sufficient.
"""
from __future__ import annotations

import csv
import io
import json
from math import isfinite, sqrt
from pathlib import Path
from statistics import fmean, pstdev
from typing import Mapping, Sequence

from . import model_lab_runner as legacy_runner
from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v3 as v3
from . import model_lab_upgrade_v5 as v5
from .model_lab_core import ENSEMBLE_MODEL, model_rank_metrics
from .model_lab_models import _numpy_matrix, _rank_target
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row
from .nghien_cuu_moc_4.du_doan_tien_phuong_features import _rank

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v6"
PREDICTIVE_POLICY_FREEZE_DATE = "2026-07-30"
MINIMUM_FUTURE_PREDICTIVE_FOLDS = 12
MINIMUM_POLARITY_HISTORY = 6
MINIMUM_DIRECTIONAL_CONSISTENCY = 0.60

_MARKET_REGIME_FEATURES = (
    "vnindex_tren_ma250",
    "vnindex_momentum_60",
    "vnindex_bien_dong_20",
    "vnindex_bien_dong_60",
)


def _continuous_rank_target(rows: Sequence[Row]):
    """Return a continuous [0, 1] cross-sectional target for each signal date."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    by_day: dict[object, list[int]] = {}
    for index, row in enumerate(rows):
        if row.relative_return is None:
            raise ValueError("CONTINUOUS_RANK_TARGET_REQUIRES_LABEL")
        by_day.setdefault(row.ngay, []).append(index)
    target = [0.0] * len(rows)
    for indexes in by_day.values():
        ranks = _rank([float(rows[index].relative_return) for index in indexes])
        for local, index in enumerate(indexes):
            target[index] = float(ranks[local])
    return np.asarray(target, dtype=float)


def _ridge_matrix_v6(
    rows: Sequence[Row],
    *,
    include_regime_interactions: bool,
):
    """Build the existing rank matrix plus optional market-regime interactions."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    base, names = _numpy_matrix(rows)
    if not include_regime_interactions:
        return base, tuple(names)
    name_to_index = {name: index for index, name in enumerate(names)}
    stock_indexes = [
        index for index, name in enumerate(names)
        if str(name).startswith("rank_")
    ]
    missing = [name for name in _MARKET_REGIME_FEATURES if name not in name_to_index]
    if missing:
        raise ValueError(f"MODEL_LAB_V6_REGIME_FEATURES_MISSING:{missing}")
    columns = [base]
    interaction_names: list[str] = []
    for regime_name in _MARKET_REGIME_FEATURES:
        regime = base[:, name_to_index[regime_name]].astype(float)
        if regime_name == "vnindex_tren_ma250":
            regime = 2.0 * regime - 1.0
        regime_column = regime.reshape(-1, 1)
        columns.append(base[:, stock_indexes] * regime_column)
        interaction_names.extend(
            f"{names[index]}__x__{regime_name}"
            for index in stock_indexes
        )
    matrix = np.concatenate(columns, axis=1)
    return matrix, tuple(names) + tuple(interaction_names)


def _validation_key_v6(
    rows: Sequence[Row],
    scores: Sequence[float],
) -> tuple[float, float, float, float, float]:
    metrics = model_rank_metrics(rows, scores, min(10, len(rows)))
    mean_ic = float(metrics.get("mean_rank_ic", 0.0) or 0.0)
    ic_std = float(metrics.get("rank_ic_std", 0.0) or 0.0)
    positive_ratio = float(metrics.get("positive_rank_ic_ratio", 0.0) or 0.0)
    top_k_return = float(metrics.get("top_k_relative_return", 0.0) or 0.0)
    turnover = float(metrics.get("mean_set_turnover", 1.0) or 1.0)
    days = max(1, int(metrics.get("day_count", 0) or 0))
    conservative_ic = mean_ic - 0.50 * ic_std / sqrt(days)
    return (
        conservative_ic,
        mean_ic,
        positive_ratio,
        top_k_return,
        -turnover,
    )


def _nondegenerate(values: Sequence[float]) -> bool:
    finite = [float(value) for value in values if isfinite(float(value))]
    return (
        len(finite) == len(values)
        and len(finite) >= 2
        and len(set(finite)) >= 2
        and max(finite) - min(finite) > 1e-12
        and pstdev(finite) > 1e-13
    )


def _predict_ridge_v6(
    train: Sequence[Row],
    validation: Sequence[Row],
    test: Sequence[Row],
    seed: int,
) -> list[float]:
    """Select target granularity, regime interactions and alpha on prior data."""
    del seed
    try:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("SKLEARN_NOT_INSTALLED") from exc

    targets = (
        ("continuous_cross_sectional_rank", _continuous_rank_target),
        ("five_level_relevance", _rank_target),
    )
    best: tuple[
        tuple[float, float, float, float, float, int, float],
        str,
        bool,
        float,
    ] | None = None
    for target_name, target_builder in targets:
        train_y = target_builder(train)
        for interactions in (False, True):
            train_x, _ = _ridge_matrix_v6(
                train,
                include_regime_interactions=interactions,
            )
            validation_x, _ = _ridge_matrix_v6(
                validation,
                include_regime_interactions=interactions,
            )
            for alpha in (5.0, 20.0, 80.0, 200.0):
                model = make_pipeline(
                    StandardScaler(),
                    Ridge(alpha=alpha, fit_intercept=True),
                )
                model.fit(train_x, train_y)
                scores = [float(value) for value in model.predict(validation_x)]
                if not _nondegenerate(scores):
                    continue
                key = (
                    *_validation_key_v6(validation, scores),
                    -int(interactions),
                    -alpha,
                )
                if best is None or key > best[0]:
                    best = (key, target_name, interactions, alpha)
    if best is None:
        raise ValueError("RIDGE_V6_NO_NONDEGENERATE_VALIDATION_CANDIDATE")

    fit_rows = tuple(train) + tuple(validation)
    target_builder = dict(targets)[best[1]]
    fit_y = target_builder(fit_rows)
    fit_x, _ = _ridge_matrix_v6(
        fit_rows,
        include_regime_interactions=best[2],
    )
    test_x, _ = _ridge_matrix_v6(
        test,
        include_regime_interactions=best[2],
    )
    final = make_pipeline(
        StandardScaler(),
        Ridge(alpha=best[3], fit_intercept=True),
    )
    final.fit(fit_x, fit_y)
    values = [float(value) for value in final.predict(test_x)]
    if not _nondegenerate(values):
        raise ValueError("RIDGE_V6_DEGENERATE_TEST_SCORE")
    return values


def _capped_magnitudes(
    quality: Mapping[str, float],
    *,
    max_weight: float,
) -> dict[str, float]:
    total = sum(float(value) for value in quality.values())
    if total <= 0.0:
        return {}
    raw = {name: float(value) / total for name, value in quality.items()}
    if len(raw) == 1:
        name = next(iter(raw))
        return {name: 1.0}
    capped = {name: min(max_weight, value) for name, value in raw.items()}
    remaining = 1.0 - sum(capped.values())
    while remaining > 1e-12:
        room = {
            name: max_weight - value
            for name, value in capped.items()
            if value < max_weight - 1e-12
        }
        if not room:
            break
        room_total = sum(room.values())
        for name, capacity in room.items():
            addition = min(capacity, remaining * capacity / room_total)
            capped[name] += addition
        remaining = 1.0 - sum(capped.values())
    if remaining > 1e-9:
        best = max(capped, key=capped.get)
        capped[best] += remaining
    normalized = sum(capped.values())
    return {
        name: value / normalized
        for name, value in capped.items()
        if value > 0.0
    }


def polarity_online_weights(
    prior_ic: Mapping[str, Sequence[float]],
    available_models: Sequence[str],
    *,
    max_weight: float = 0.55,
    minimum_history: int = MINIMUM_POLARITY_HISTORY,
    minimum_consistency: float = MINIMUM_DIRECTIONAL_CONSISTENCY,
) -> dict[str, float]:
    """Use prior-only IC to retain or invert persistent model direction."""
    models = sorted(
        name for name in available_models
        if name != ENSEMBLE_MODEL
    )
    if not models:
        raise ValueError("MODEL_LAB_ENSEMBLE_NO_BASE_MODELS")
    quality: dict[str, float] = {}
    signs: dict[str, float] = {}
    for name in models:
        history = [
            float(value)
            for value in prior_ic.get(name, ())
            if isfinite(float(value))
        ]
        if len(history) < minimum_history:
            continue
        mean_ic = fmean(history)
        dispersion = pstdev(history) if len(history) > 1 else 0.0
        positive_ratio = fmean(
            1.0 if value > 0.0 else 0.0
            for value in history
        )
        negative_ratio = fmean(
            1.0 if value < 0.0 else 0.0
            for value in history
        )
        lower_magnitude = (
            abs(mean_ic)
            - 0.50 * dispersion / sqrt(len(history))
        )
        if lower_magnitude <= 0.0:
            continue
        if mean_ic > 0.0 and positive_ratio >= minimum_consistency:
            signs[name] = 1.0
        elif mean_ic < 0.0 and negative_ratio >= minimum_consistency:
            signs[name] = -1.0
        else:
            continue
        quality[name] = max(
            1e-6,
            lower_magnitude + 0.25 * abs(mean_ic),
        )
    if not quality:
        fallback = (
            "ridge_ranker"
            if "ridge_ranker" in models
            else (
                "robust_technical_ensemble_v1"
                if "robust_technical_ensemble_v1" in models
                else models[0]
            )
        )
        return {fallback: 1.0}
    magnitudes = _capped_magnitudes(quality, max_weight=max_weight)
    return {
        name: magnitudes[name] * signs[name]
        for name in magnitudes
    }


def polarity_ensemble_scores(
    scores_by_model: Mapping[str, Sequence[float]],
    weights: Mapping[str, float],
) -> list[float]:
    """Average aligned percentiles; negative weight means invert the rank."""
    names = [name for name in weights if name in scores_by_model]
    if not names:
        raise ValueError("MODEL_LAB_ENSEMBLE_SCORES_EMPTY")
    lengths = {len(scores_by_model[name]) for name in names}
    if len(lengths) != 1:
        raise ValueError("MODEL_LAB_ENSEMBLE_LENGTH_MISMATCH")
    ranked = {
        name: _rank([float(value) for value in scores_by_model[name]])
        for name in names
    }
    total = sum(abs(float(weights[name])) for name in names)
    if total <= 0.0:
        raise ValueError("MODEL_LAB_ENSEMBLE_WEIGHT_NONPOSITIVE")
    length = lengths.pop()
    output: list[float] = []
    for index in range(length):
        value = 0.0
        for name in names:
            weight = float(weights[name])
            aligned = (
                ranked[name][index]
                if weight >= 0.0
                else 1.0 - ranked[name][index]
            )
            value += abs(weight) * aligned
        output.append(value / total)
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fields),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _pearson_rank(
    scores: Sequence[float],
    targets: Sequence[float],
) -> float:
    left = _rank([float(value) for value in scores])
    right = _rank([float(value) for value in targets])
    mean_left = fmean(left)
    mean_right = fmean(right)
    numerator = sum(
        (x - mean_left) * (y - mean_right)
        for x, y in zip(left, right)
    )
    denominator = sqrt(
        sum((x - mean_left) ** 2 for x in left)
        * sum((y - mean_right) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0.0 else 0.0


def _compound(rows: Sequence[Mapping[str, object]], field: str) -> float:
    nav = 1.0
    for row in rows:
        nav *= max(1e-9, 1.0 + float(row.get(field, 0.0) or 0.0))
    return nav - 1.0


def future_predictive_holdout_rows(
    predictions: Sequence[Mapping[str, object]],
    periods: Sequence[Mapping[str, object]],
    *,
    freeze_date: str = PREDICTIVE_POLICY_FREEZE_DATE,
    minimum_folds: int = MINIMUM_FUTURE_PREDICTIVE_FOLDS,
) -> list[dict[str, object]]:
    """Evaluate only signal dates strictly after the v6 policy freeze."""
    if minimum_folds <= 0:
        raise ValueError("MODEL_LAB_V6_HOLDOUT_MINIMUM_NONPOSITIVE")
    by_model_day: dict[
        tuple[str, str],
        list[Mapping[str, object]],
    ] = {}
    models: set[str] = set()
    for row in predictions:
        model = str(row.get("model") or "")
        day = str(row.get("test_date") or "")
        if not model:
            continue
        models.add(model)
        if day > freeze_date:
            by_model_day.setdefault((model, day), []).append(row)
    future_periods: dict[str, list[Mapping[str, object]]] = {}
    for row in periods:
        model = str(row.get("model") or "")
        day = str(row.get("signal_date") or "")
        if model and day > freeze_date:
            future_periods.setdefault(model, []).append(row)

    output: list[dict[str, object]] = []
    for model in sorted(models):
        day_groups = sorted(
            (
                (day, rows)
                for (name, day), rows in by_model_day.items()
                if name == model
            ),
            key=lambda item: item[0],
        )
        daily_ic = [
            _pearson_rank(
                [float(row.get("score", 0.0) or 0.0) for row in rows],
                [
                    float(row.get("relative_return", 0.0) or 0.0)
                    for row in rows
                ],
            )
            for _, rows in day_groups
        ]
        model_periods = sorted(
            future_periods.get(model, []),
            key=lambda row: str(row.get("signal_date") or ""),
        )
        fold_count = len(day_groups)
        mean_ic = fmean(daily_ic) if daily_ic else 0.0
        positive_ratio = (
            fmean(1.0 if value > 0.0 else 0.0 for value in daily_ic)
            if daily_ic else 0.0
        )
        net_total = _compound(model_periods, "net_return")
        benchmark_total = _compound(model_periods, "benchmark_return")
        relative_total = (
            (1.0 + net_total) / (1.0 + benchmark_total) - 1.0
            if benchmark_total > -1.0 else 0.0
        )
        mean_turnover = (
            fmean(
                float(row.get("turnover", 0.0) or 0.0)
                for row in model_periods
            )
            if model_periods else 0.0
        )
        enough = fold_count >= minimum_folds
        supports = (
            enough
            and mean_ic >= 0.03
            and positive_ratio >= 0.55
            and net_total > 0.0
            and relative_total > 0.0
            and mean_turnover <= 0.60
        )
        status = (
            "FUTURE_HOLDOUT_SUPPORTS_PREDICTIVE_REFERENCE"
            if supports
            else (
                "FUTURE_HOLDOUT_REJECTS_PREDICTIVE_REFERENCE"
                if enough
                else "INSUFFICIENT_FUTURE_PREDICTIVE_HOLDOUT"
            )
        )
        output.append({
            "model": model,
            "policy_freeze_date": freeze_date,
            "minimum_future_folds": minimum_folds,
            "future_fold_count": fold_count,
            "first_future_signal_date": (
                day_groups[0][0] if day_groups else ""
            ),
            "last_future_signal_date": (
                day_groups[-1][0] if day_groups else ""
            ),
            "mean_rank_ic": mean_ic,
            "positive_rank_ic_ratio": positive_ratio,
            "net_total_return": net_total,
            "benchmark_total_return": benchmark_total,
            "relative_total_return": relative_total,
            "mean_turnover": mean_turnover,
            "status": status,
            "actionable": "false",
        })
    return output


def _historical_reference_gate(
    leaderboard_row: Mapping[str, object],
    momentum_row: Mapping[str, object],
) -> dict[str, bool]:
    return {
        "enough_oos_folds": int(
            float(leaderboard_row.get("oos_folds", 0) or 0)
        ) >= 24,
        "mean_rank_ic_at_least_003": float(
            leaderboard_row.get("mean_rank_ic", 0.0) or 0.0
        ) >= 0.03,
        "positive_rank_ic_ratio_at_least_055": float(
            leaderboard_row.get("positive_rank_ic_ratio", 0.0) or 0.0
        ) >= 0.55,
        "net_total_return_positive": float(
            leaderboard_row.get("net_total_return", 0.0) or 0.0
        ) > 0.0,
        "beats_momentum_rank_ic": float(
            leaderboard_row.get("mean_rank_ic", 0.0) or 0.0
        ) > float(momentum_row.get("mean_rank_ic", 0.0) or 0.0),
        "beats_momentum_net_return": float(
            leaderboard_row.get("net_total_return", 0.0) or 0.0
        ) > float(momentum_row.get("net_total_return", 0.0) or 0.0),
        "no_degenerate_folds": float(
            leaderboard_row.get("degenerate_fold_ratio", 1.0) or 1.0
        ) == 0.0,
    }


def publish_v6_predictive_diagnostics(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    leaderboard = _read_csv(output / "model_leaderboard.csv")
    weights = _read_csv(output / "ensemble_weights_oos.csv")
    predictions = _read_csv(output / "oos_predictions.csv")
    periods = _read_csv(output / "oos_backtest_periods.csv")

    polarity_by_model: dict[str, list[dict[str, str]]] = {}
    for row in weights:
        polarity_by_model.setdefault(
            str(row.get("base_model") or ""),
            [],
        ).append(row)
    polarity_rows: list[dict[str, object]] = []
    for model, rows in sorted(polarity_by_model.items()):
        signed = [float(row.get("weight", 0.0) or 0.0) for row in rows]
        negative = [value for value in signed if value < 0.0]
        positive = [value for value in signed if value > 0.0]
        polarity_rows.append({
            "base_model": model,
            "weighted_fold_count": len(rows),
            "positive_polarity_fold_count": len(positive),
            "negative_polarity_fold_count": len(negative),
            "mean_signed_weight": fmean(signed) if signed else 0.0,
            "mean_absolute_weight": (
                fmean(abs(value) for value in signed) if signed else 0.0
            ),
            "first_negative_polarity_date": next(
                (
                    str(row.get("test_date") or "")
                    for row in rows
                    if float(row.get("weight", 0.0) or 0.0) < 0.0
                ),
                "",
            ),
            "selection_uses_current_fold_label": "false",
            "actionable": "false",
        })
    polarity_fields = (
        "base_model",
        "weighted_fold_count",
        "positive_polarity_fold_count",
        "negative_polarity_fold_count",
        "mean_signed_weight",
        "mean_absolute_weight",
        "first_negative_polarity_date",
        "selection_uses_current_fold_label",
        "actionable",
    )
    _write_csv(
        output / "polarity_evidence_oos.csv",
        polarity_rows,
        polarity_fields,
    )

    holdout = future_predictive_holdout_rows(predictions, periods)
    holdout_fields = (
        "model",
        "policy_freeze_date",
        "minimum_future_folds",
        "future_fold_count",
        "first_future_signal_date",
        "last_future_signal_date",
        "mean_rank_ic",
        "positive_rank_ic_ratio",
        "net_total_return",
        "benchmark_total_return",
        "relative_total_return",
        "mean_turnover",
        "status",
        "actionable",
    )
    _write_csv(
        output / "predictive_v6_future_holdout.csv",
        holdout,
        holdout_fields,
    )

    by_name = {
        str(row.get("model") or ""): row
        for row in leaderboard
    }
    momentum = by_name.get("momentum_baseline", {})
    candidate = by_name.get(ENSEMBLE_MODEL, {})
    gate = (
        _historical_reference_gate(candidate, momentum)
        if candidate and momentum else {}
    )
    historical_pass = bool(gate) and all(gate.values())
    max_future = max(
        (
            int(row["future_fold_count"])
            for row in holdout
            if str(row.get("model") or "") == ENSEMBLE_MODEL
        ),
        default=0,
    )
    future_support = any(
        str(row.get("model") or "") == ENSEMBLE_MODEL
        and row.get("status")
        == "FUTURE_HOLDOUT_SUPPORTS_PREDICTIVE_REFERENCE"
        for row in holdout
    )
    reference_status = (
        "PREDICTIVE_REFERENCE_SUPPORTED_BY_FUTURE_HOLDOUT"
        if historical_pass and future_support
        else (
            "HISTORICAL_REFERENCE_CANDIDATE_AWAITING_FUTURE_HOLDOUT"
            if historical_pass
            else "BELOW_PREDICTIVE_REFERENCE_GATE"
        )
    )

    summary_path = output / "model_lab_summary.json"
    summary = json.loads(
        summary_path.read_text(encoding="utf-8-sig")
    )
    original_champion = str(
        summary.get("research_champion") or "NO_MODEL_APPROVED"
    )
    summary["base_upgrade_schema_version"] = v5.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["predictive_upgrade_v6"] = {
        "ridge_target_candidates": [
            "continuous_cross_sectional_rank",
            "five_level_relevance",
        ],
        "ridge_regime_interactions": list(_MARKET_REGIME_FEATURES),
        "ridge_selection_uses_prior_validation_only": True,
        "polarity_minimum_prior_folds": MINIMUM_POLARITY_HISTORY,
        "polarity_minimum_directional_consistency": (
            MINIMUM_DIRECTIONAL_CONSISTENCY
        ),
        "polarity_selection_uses_current_fold_label": False,
        "policy_provenance": "SELECTED_AFTER_REVIEWING_PRIOR_OOS",
        "policy_freeze_date": PREDICTIVE_POLICY_FREEZE_DATE,
        "minimum_future_predictive_folds": (
            MINIMUM_FUTURE_PREDICTIVE_FOLDS
        ),
        "historical_reference_gate": gate,
        "historical_reference_gate_passed": historical_pass,
        "reference_status": reference_status,
        "future_holdout_count": max_future,
        "future_holdout_support": future_support,
        "research_gate_unchanged": True,
        "actionable": False,
        "files": [
            "polarity_evidence_oos.csv",
            "predictive_v6_future_holdout.csv",
        ],
    }
    summary["v6_historical_champion_before_provenance_block"] = (
        original_champion
    )
    if not future_support:
        summary["research_champion"] = "NO_MODEL_APPROVED"
        summary["champion_reason"] = (
            "V6_POSTHOC_PREDICTIVE_POLICY_REQUIRES_FUTURE_HOLDOUT"
        )
        summary["forward_watchlist_published"] = False
        summary["live_capital_approved"] = False
        deployment = dict(summary.get("deployment_status") or {})
        deployment["forward_watchlist_published"] = False
        deployment["live_capital_approved"] = False
        deployment["v6_posthoc_policy_blocked"] = True
        summary["deployment_status"] = deployment
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    forward_path = output / "forward_model_scores.csv"
    forward_rows = _read_csv(forward_path)
    for row in forward_rows:
        row["research_champion"] = str(summary["research_champion"])
        row["live_capital_approved"] = "false"
    if forward_rows:
        _write_csv(
            forward_path,
            forward_rows,
            tuple(forward_rows[0]),
        )

    with (output / "model_lab_report.txt").open(
        "a",
        encoding="utf-8",
    ) as stream:
        stream.write("\nMODEL LAB UPGRADE V6\n")
        stream.write(
            "Ridge: continuous/discrete rank target and market-regime "
            "interactions selected on strictly prior validation blocks.\n"
        )
        stream.write(
            "Online ensemble: persistent negative prior IC may invert a "
            "model; current-fold labels are never used.\n"
        )
        stream.write(
            f"Predictive reference status: {reference_status}; "
            f"future folds={max_future}; actionable=false.\n"
        )
        if not future_support:
            stream.write(
                "Any historical champion is blocked because v6 was selected "
                "after reviewing prior OOS and requires future holdout.\n"
            )

    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "predictive_reference_status": reference_status,
        "historical_reference_gate_passed": historical_pass,
        "maximum_future_predictive_folds": max_future,
        "future_predictive_holdout_support": future_support,
        "research_champion": summary["research_champion"],
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    original_predictors = v3.PREDICTOR_OVERRIDES
    original_weights = v3.conservative_online_weights
    original_ensemble_scores = legacy_runner.ensemble_scores
    v3.PREDICTOR_OVERRIDES = {
        **dict(original_predictors),
        "ridge_ranker": _predict_ridge_v6,
    }
    v3.conservative_online_weights = polarity_online_weights
    legacy_runner.ensemble_scores = polarity_ensemble_scores
    try:
        result = v5.run_model_lab(**kwargs)
        diagnostics = publish_v6_predictive_diagnostics(
            Path(str(kwargs["output_dir"]))
        )
        return {**result, **diagnostics}
    finally:
        v3.PREDICTOR_OVERRIDES = original_predictors
        v3.conservative_online_weights = original_weights
        legacy_runner.ensemble_scores = original_ensemble_scores


def _parser():
    return v5._parser()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_model_lab(
        input_zip=args.input_zip,
        output_dir=args.output_dir,
        models=tuple(
            item.strip()
            for item in args.models.split(",")
            if item.strip()
        ),
        evaluation_months=args.evaluation_months,
        minimum_train_months=args.minimum_train_months,
        inner_validation_months=args.inner_validation_months,
        top_k=args.top_k,
        turnover_buffer=args.turnover_buffer,
        seed=args.seed,
        strict_dependencies=args.strict_dependencies,
        buy_fee_bps=args.buy_fee_bps,
        sell_fee_bps=args.sell_fee_bps,
        sell_tax_bps=args.sell_tax_bps,
        slippage_bps=args.slippage_bps,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "PREDICTIVE_POLICY_FREEZE_DATE",
    "MINIMUM_FUTURE_PREDICTIVE_FOLDS",
    "MINIMUM_POLARITY_HISTORY",
    "MINIMUM_DIRECTIONAL_CONSISTENCY",
    "_continuous_rank_target",
    "_ridge_matrix_v6",
    "_predict_ridge_v6",
    "polarity_online_weights",
    "polarity_ensemble_scores",
    "future_predictive_holdout_rows",
    "publish_v6_predictive_diagnostics",
    "run_model_lab",
    "main",
]
