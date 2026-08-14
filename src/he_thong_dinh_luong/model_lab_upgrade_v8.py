"""Model Lab v8: tail-aware validation and strict net-alpha reference gates.

V7 proved that broad cross-sectional IC can be positive while the investable
Top-K tail still loses to VNINDEX after costs.  This layer therefore:

* adds a top-tail target to Ridge;
* orients validation-selected learners using only prior validation labels;
* emphasizes the investable tail for tree rankers;
* publishes a strict reference gate that requires positive Top-K/net excess,
  positive relative return, controlled turnover, and independent evidence;
* keeps every v8 policy non-actionable until genuinely future holdout exists.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import io
import json
from math import sqrt
from pathlib import Path
from statistics import fmean
from typing import Callable, Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v3 as v3
from . import model_lab_upgrade_v6 as v6
from . import model_lab_upgrade_v7 as v7
from .model_lab_core import ENSEMBLE_MODEL, model_rank_metrics
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v8"
TAIL_POLICY_FREEZE_DATE = "2026-07-31"
MINIMUM_FUTURE_TAIL_FOLDS = 12
VALIDATION_ROUND_TRIP_COST_RATE = 0.006
TAIL_FRACTION = 0.20


def _top_tail_target(rows: Sequence[Row]):
    """Continuous [0, 1] target restricted to the upper cross-sectional tail."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    ranks = v6._continuous_rank_target(rows)
    threshold = 1.0 - TAIL_FRACTION
    return np.clip((ranks - threshold) / TAIL_FRACTION, 0.0, 1.0)


def _tail_relevance(rows: Sequence[Row]) -> list[int]:
    """Five relevance levels with more resolution in the investable upper tail."""
    ranks = [float(value) for value in v6._continuous_rank_target(rows)]
    output: list[int] = []
    for value in ranks:
        if value >= 0.90:
            output.append(4)
        elif value >= 0.80:
            output.append(3)
        elif value >= 0.60:
            output.append(2)
        elif value >= 0.30:
            output.append(1)
        else:
            output.append(0)
    return output


def _tail_validation_key(
    rows: Sequence[Row],
    scores: Sequence[float],
    *,
    top_k: int = 10,
) -> tuple[bool, float, float, float, float, float, float]:
    """Prior-validation objective aligned with a long-only Top-K portfolio."""
    metrics = model_rank_metrics(rows, scores, min(top_k, len(rows)))
    mean_ic = float(metrics.get("mean_rank_ic", 0.0) or 0.0)
    ic_std = float(metrics.get("rank_ic_std", 0.0) or 0.0)
    positive_ic = float(metrics.get("positive_rank_ic_ratio", 0.0) or 0.0)
    top_tail = float(metrics.get("top_k_relative_return", 0.0) or 0.0)
    positive_tail = float(
        metrics.get("positive_top_k_return_ratio", 0.0) or 0.0
    )
    turnover = float(metrics.get("mean_set_turnover", 1.0) or 1.0)
    days = max(1, int(metrics.get("day_count", 0) or 0))
    conservative_ic = mean_ic - 0.50 * ic_std / sqrt(days)
    cost_adjusted_tail = (
        top_tail - VALIDATION_ROUND_TRIP_COST_RATE * turnover
    )
    return (
        cost_adjusted_tail > 0.0,
        cost_adjusted_tail,
        positive_tail,
        conservative_ic,
        mean_ic,
        positive_ic,
        -turnover,
    )


def select_score_orientation(
    rows: Sequence[Row],
    scores: Sequence[float],
) -> float:
    """Choose +1/-1 using only the supplied prior validation block."""
    direct = [float(value) for value in scores]
    inverted = [-value for value in direct]
    return (
        -1.0
        if _tail_validation_key(rows, inverted)
        > _tail_validation_key(rows, direct)
        else 1.0
    )


def _predict_ridge_v8(
    train: Sequence[Row],
    validation: Sequence[Row],
    test: Sequence[Row],
    seed: int,
) -> list[float]:
    """Select target, regime interactions, regularization, and orientation."""
    del seed
    try:
        import numpy as np
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("SKLEARN_NOT_INSTALLED") from exc

    targets: tuple[
        tuple[str, Callable[[Sequence[Row]], object], float],
        ...,
    ] = (
        ("top_tail_rank", _top_tail_target, 4.0),
        ("continuous_cross_sectional_rank", v6._continuous_rank_target, 1.0),
        ("five_level_relevance", v3._rank_target, 1.0),
    )
    best: tuple[
        tuple[object, ...],
        str,
        bool,
        float,
        float,
        float,
    ] | None = None
    for target_name, target_builder, tail_weight in targets:
        train_y = target_builder(train)
        sample_weight = np.ones(len(train), dtype=float)
        if target_name == "top_tail_rank":
            sample_weight = 1.0 + tail_weight * np.asarray(train_y, dtype=float)
        for interactions in (False, True):
            train_x, _ = v6._ridge_matrix_v6(
                train,
                include_regime_interactions=interactions,
            )
            validation_x, _ = v6._ridge_matrix_v6(
                validation,
                include_regime_interactions=interactions,
            )
            for alpha in (2.0, 10.0, 50.0, 200.0):
                model = make_pipeline(
                    StandardScaler(),
                    Ridge(alpha=alpha, fit_intercept=True),
                )
                model.fit(
                    train_x,
                    train_y,
                    ridge__sample_weight=sample_weight,
                )
                raw = [float(value) for value in model.predict(validation_x)]
                if not v6._nondegenerate(raw):
                    continue
                sign = select_score_orientation(validation, raw)
                oriented = [sign * value for value in raw]
                key = (
                    *_tail_validation_key(validation, oriented),
                    -int(interactions),
                    -alpha,
                )
                if best is None or key > best[0]:
                    best = (
                        key,
                        target_name,
                        interactions,
                        alpha,
                        sign,
                        tail_weight,
                    )
    if best is None:
        raise ValueError("RIDGE_V8_NO_NONDEGENERATE_VALIDATION_CANDIDATE")

    fit_rows = tuple(train) + tuple(validation)
    target_builder = {
        name: builder for name, builder, _ in targets
    }[best[1]]
    fit_y = target_builder(fit_rows)
    fit_weight = np.ones(len(fit_rows), dtype=float)
    if best[1] == "top_tail_rank":
        fit_weight = 1.0 + best[5] * np.asarray(fit_y, dtype=float)
    fit_x, _ = v6._ridge_matrix_v6(
        fit_rows,
        include_regime_interactions=best[2],
    )
    test_x, _ = v6._ridge_matrix_v6(
        test,
        include_regime_interactions=best[2],
    )
    final = make_pipeline(
        StandardScaler(),
        Ridge(alpha=best[3], fit_intercept=True),
    )
    final.fit(fit_x, fit_y, ridge__sample_weight=fit_weight)
    values = [best[4] * float(value) for value in final.predict(test_x)]
    if not v6._nondegenerate(values):
        raise ValueError("RIDGE_V8_DEGENERATE_TEST_SCORE")
    return values


@contextmanager
def _patched_v3_targets(
    *,
    rank_target: Callable[[Sequence[Row]], object] | None = None,
    relevance: Callable[[Sequence[Row]], list[int]] | None = None,
):
    original_rank = v3._rank_target
    original_relevance = v3._relevance
    if rank_target is not None:
        v3._rank_target = rank_target
    if relevance is not None:
        v3._relevance = relevance
    try:
        yield
    finally:
        v3._rank_target = original_rank
        v3._relevance = original_relevance


def _orientation_blocks(
    validation: Sequence[Row],
) -> tuple[tuple[Row, ...], tuple[Row, ...]]:
    dates = sorted({row.ngay for row in validation})
    if len(dates) < 2:
        return tuple(validation), tuple(validation)
    orientation_dates = {dates[-1]}
    selection = tuple(
        row for row in validation if row.ngay not in orientation_dates
    )
    orientation = tuple(
        row for row in validation if row.ngay in orientation_dates
    )
    return selection or tuple(validation), orientation or tuple(validation)


def _oriented_predictor(
    base: Callable[
        [Sequence[Row], Sequence[Row], Sequence[Row], int],
        list[float],
    ],
    *,
    rank_target: Callable[[Sequence[Row]], object] | None = None,
    relevance: Callable[[Sequence[Row]], list[int]] | None = None,
):
    """Wrap a learner with a prior-only tail-orientation calibration."""
    def predict(
        train: Sequence[Row],
        validation: Sequence[Row],
        test: Sequence[Row],
        seed: int,
    ) -> list[float]:
        selection, orientation = _orientation_blocks(validation)
        with _patched_v3_targets(
            rank_target=rank_target,
            relevance=relevance,
        ):
            orientation_scores = base(
                train,
                selection,
                orientation,
                seed,
            )
            sign = select_score_orientation(
                orientation,
                orientation_scores,
            )
            raw_test = base(
                train,
                validation,
                test,
                seed,
            )
        values = [sign * float(value) for value in raw_test]
        if not v6._nondegenerate(values):
            raise ValueError("MODEL_LAB_V8_DEGENERATE_TEST_SCORE")
        return values
    return predict


_predict_hist_v8 = _oriented_predictor(
    v3._predict_hist_gb_v3,
    rank_target=_top_tail_target,
)
_predict_lightgbm_v8 = _oriented_predictor(
    v3._predict_lightgbm_v3,
    relevance=_tail_relevance,
)
_predict_xgboost_v8 = _oriented_predictor(
    v3._predict_xgboost_v3,
    relevance=_tail_relevance,
)


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


def strict_reference_gate(
    leaderboard_row: Mapping[str, object],
    *,
    mean_turnover: float,
    positive_component_count: int,
) -> dict[str, bool]:
    """Reference quality must be investable, not merely rank-correlated."""
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
        "top_k_relative_return_positive": float(
            leaderboard_row.get("top_k_relative_return", 0.0) or 0.0
        ) > 0.0,
        "average_net_excess_positive": float(
            leaderboard_row.get("average_net_excess_return", 0.0) or 0.0
        ) > 0.0,
        "positive_net_excess_ratio_at_least_half": float(
            leaderboard_row.get("positive_net_excess_ratio", 0.0) or 0.0
        ) >= 0.50,
        "relative_total_return_positive": float(
            leaderboard_row.get("relative_total_return", 0.0) or 0.0
        ) > 0.0,
        "turnover_controlled": float(mean_turnover) <= 0.60,
        "no_degenerate_folds": float(
            leaderboard_row.get("degenerate_fold_ratio", 1.0) or 1.0
        ) == 0.0,
        "two_independent_positive_components": (
            int(positive_component_count) >= 2
        ),
    }


def _tail_decile_mean(
    rows: Sequence[Mapping[str, object]],
) -> float:
    by_day: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        by_day.setdefault(str(row.get("test_date") or ""), []).append(row)
    values: list[float] = []
    for day_rows in by_day.values():
        if not day_rows:
            continue
        count = max(1, int(round(len(day_rows) * 0.10)))
        selected = sorted(
            day_rows,
            key=lambda row: (
                int(float(row.get("rank", 10**9) or 10**9)),
                str(row.get("symbol") or ""),
            ),
        )[:count]
        values.append(
            fmean(
                float(row.get("relative_return", 0.0) or 0.0)
                for row in selected
            )
        )
    return fmean(values) if values else 0.0


def publish_v8_tail_diagnostics(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    leaderboard = _read_csv(output / "model_leaderboard.csv")
    predictions = _read_csv(output / "oos_predictions.csv")
    periods = _read_csv(output / "oos_backtest_periods.csv")
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))

    by_model_prediction: dict[str, list[dict[str, str]]] = {}
    for row in predictions:
        by_model_prediction.setdefault(
            str(row.get("model") or ""),
            [],
        ).append(row)
    by_model_period: dict[str, list[dict[str, str]]] = {}
    for row in periods:
        by_model_period.setdefault(
            str(row.get("model") or ""),
            [],
        ).append(row)
    positive_components = list(
        summary.get("ensemble_positive_components") or []
    )
    diagnostics: list[dict[str, object]] = []
    strict_gate: dict[str, bool] = {}
    for row in leaderboard:
        model = str(row.get("model") or "")
        model_periods = by_model_period.get(model, [])
        mean_turnover = (
            fmean(
                float(item.get("turnover", 0.0) or 0.0)
                for item in model_periods
            )
            if model_periods else 1.0
        )
        component_count = (
            len(positive_components)
            if model == ENSEMBLE_MODEL else 1
        )
        gate = strict_reference_gate(
            row,
            mean_turnover=mean_turnover,
            positive_component_count=component_count,
        )
        if model == ENSEMBLE_MODEL:
            strict_gate = gate
        diagnostics.append({
            "model": model,
            "oos_folds": row.get("oos_folds", ""),
            "mean_rank_ic": row.get("mean_rank_ic", ""),
            "positive_rank_ic_ratio": row.get(
                "positive_rank_ic_ratio", ""
            ),
            "top_decile_mean_relative_return": _tail_decile_mean(
                by_model_prediction.get(model, [])
            ),
            "top_k_relative_return": row.get(
                "top_k_relative_return", ""
            ),
            "average_net_excess_return": row.get(
                "average_net_excess_return", ""
            ),
            "positive_net_excess_ratio": row.get(
                "positive_net_excess_ratio", ""
            ),
            "relative_total_return": row.get(
                "relative_total_return", ""
            ),
            "mean_turnover": mean_turnover,
            "positive_component_count": component_count,
            "strict_reference_gate_passed": str(
                all(gate.values())
            ).lower(),
            "actionable": "false",
        })
    fields = (
        "model",
        "oos_folds",
        "mean_rank_ic",
        "positive_rank_ic_ratio",
        "top_decile_mean_relative_return",
        "top_k_relative_return",
        "average_net_excess_return",
        "positive_net_excess_ratio",
        "relative_total_return",
        "mean_turnover",
        "positive_component_count",
        "strict_reference_gate_passed",
        "actionable",
    )
    _write_csv(
        output / "tail_quality_diagnostic.csv",
        diagnostics,
        fields,
    )

    holdout = v6.future_predictive_holdout_rows(
        predictions,
        periods,
        freeze_date=TAIL_POLICY_FREEZE_DATE,
        minimum_folds=MINIMUM_FUTURE_TAIL_FOLDS,
    )
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
        output / "predictive_v8_future_holdout.csv",
        holdout,
        holdout_fields,
    )

    historical_pass = bool(strict_gate) and all(strict_gate.values())
    future_support = any(
        str(row.get("model") or "") == ENSEMBLE_MODEL
        and str(row.get("status") or "")
        == "FUTURE_HOLDOUT_SUPPORTS_PREDICTIVE_REFERENCE"
        for row in holdout
    )
    original_champion = str(
        summary.get("research_champion") or "NO_MODEL_APPROVED"
    )
    summary["base_upgrade_schema_version"] = v7.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["predictive_upgrade_v8"] = {
        "objective": "cost_adjusted_top_k_tail_then_rank_ic",
        "tail_fraction": TAIL_FRACTION,
        "validation_round_trip_cost_rate": (
            VALIDATION_ROUND_TRIP_COST_RATE
        ),
        "ridge_target_candidates": [
            "top_tail_rank",
            "continuous_cross_sectional_rank",
            "five_level_relevance",
        ],
        "tree_tail_relevance": True,
        "learner_orientation_uses_prior_validation_only": True,
        "strict_reference_gate": strict_gate,
        "strict_reference_gate_passed": historical_pass,
        "policy_provenance": "SELECTED_AFTER_REVIEWING_2026_07_30_OOS",
        "policy_freeze_date": TAIL_POLICY_FREEZE_DATE,
        "minimum_future_folds": MINIMUM_FUTURE_TAIL_FOLDS,
        "future_holdout_support": future_support,
        "research_gate_relaxed": False,
        "actionable": False,
        "files": [
            "tail_quality_diagnostic.csv",
            "predictive_v8_future_holdout.csv",
        ],
    }
    summary["v8_historical_champion_before_provenance_block"] = (
        original_champion
    )
    if not (historical_pass and future_support):
        summary["research_champion"] = "NO_MODEL_APPROVED"
        summary["champion_reason"] = (
            "V8_TAIL_REFERENCE_GATE_OR_FUTURE_HOLDOUT_NOT_MET"
        )
        summary["forward_watchlist_published"] = False
        summary["research_eligible"] = False
        summary["live_capital_approved"] = False
        summary["deployment_status"] = "NO_MODEL_APPROVED"
        summary["deployment_safety_v8"] = {
            "status": "NO_MODEL_APPROVED",
            "tail_reference_gate_passed": historical_pass,
            "future_holdout_support": future_support,
            "forward_watchlist_published": False,
            "live_capital_approved": False,
            "actionable": False,
        }
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
        row["reference_model"] = str(summary["research_champion"])
        row["selected_top_k"] = "false"
        row["research_approved"] = "false"
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
        stream.write("\nMODEL LAB UPGRADE V8\n")
        stream.write(
            "Selection objective: cost-adjusted Top-K tail before broad "
            "cross-sectional IC.\n"
        )
        stream.write(
            "Ridge includes a weighted top-tail target; trainable learners "
            "calibrate score orientation on prior validation only.\n"
        )
        stream.write(
            f"Strict historical tail gate: {str(historical_pass).lower()}; "
            f"future holdout support: {str(future_support).lower()}; "
            "actionable=false.\n"
        )

    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "strict_tail_reference_gate_passed": historical_pass,
        "future_tail_holdout_support": future_support,
        "research_champion": summary["research_champion"],
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    original_predictors = v3.PREDICTOR_OVERRIDES
    original_ridge = v6._predict_ridge_v6
    v3.PREDICTOR_OVERRIDES = {
        **dict(original_predictors),
        "hist_gradient_boosting_ranker": _predict_hist_v8,
        "lightgbm_ranker": _predict_lightgbm_v8,
        "xgboost_ranker": _predict_xgboost_v8,
    }
    v6._predict_ridge_v6 = _predict_ridge_v8
    try:
        result = v7.run_model_lab(**kwargs)
        diagnostics = publish_v8_tail_diagnostics(
            Path(str(kwargs["output_dir"]))
        )
        return {**result, **diagnostics}
    finally:
        v3.PREDICTOR_OVERRIDES = original_predictors
        v6._predict_ridge_v6 = original_ridge


def _parser():
    return v7._parser()


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
    "TAIL_POLICY_FREEZE_DATE",
    "MINIMUM_FUTURE_TAIL_FOLDS",
    "VALIDATION_ROUND_TRIP_COST_RATE",
    "TAIL_FRACTION",
    "_top_tail_target",
    "_tail_relevance",
    "_tail_validation_key",
    "select_score_orientation",
    "_predict_ridge_v8",
    "strict_reference_gate",
    "publish_v8_tail_diagnostics",
    "run_model_lab",
    "main",
]
