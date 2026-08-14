"""Predictive-value upgrade for the leakage-safe VN Quant Model Lab.

The v3 layer keeps the existing publication and quality-gate contracts, while
adding validation-selected learners, a conservative prior-only ensemble, and
non-actionable consensus diagnostics. Optional ML libraries remain lazy imports.
"""
from __future__ import annotations

import argparse
import csv
import json
from math import isfinite, sqrt
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Mapping, Sequence

from . import model_lab_runner as legacy_runner
from . import model_lab_runner_v2 as quality_runner
from .model_lab_core import DEFAULT_MODELS, ENSEMBLE_MODEL, model_rank_metrics
from .model_lab_models import (
    Predictor,
    _group_sizes,
    _numpy_matrix,
    _qid,
    _rank_target,
    _relevance,
)
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v3"


def _validation_key(rows: Sequence[Row], scores: Sequence[float]) -> tuple[float, float, float, float]:
    """Score a candidate only on the strictly prior validation block."""
    metrics = model_rank_metrics(rows, scores, min(10, len(rows)))
    mean_ic = float(metrics.get("mean_rank_ic", 0.0) or 0.0)
    ic_std = float(metrics.get("rank_ic_std", 0.0) or 0.0)
    positive_ratio = float(metrics.get("positive_rank_ic_ratio", 0.0) or 0.0)
    top_k_return = float(metrics.get("top_k_relative_return", 0.0) or 0.0)
    days = max(1, len({row.ngay for row in rows}))
    conservative_ic = mean_ic - 0.50 * ic_std / sqrt(days)
    return conservative_ic, mean_ic, positive_ratio, top_k_return


def _nondegenerate(values: Sequence[float]) -> bool:
    finite = [float(value) for value in values if isfinite(float(value))]
    return (
        len(finite) == len(values)
        and len(finite) >= 2
        and len(set(finite)) >= 2
        and max(finite) - min(finite) > 1e-12
        and pstdev(finite) > 1e-13
    )


def _predict_ridge_v3(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    del seed
    try:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("SKLEARN_NOT_INSTALLED") from exc
    train_x, _ = _numpy_matrix(train)
    train_y = _rank_target(train)
    validation_x, _ = _numpy_matrix(validation)
    best: tuple[tuple[float, float, float, float], float] | None = None
    for alpha in (1.0, 5.0, 20.0, 80.0):
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha, fit_intercept=True))
        model.fit(train_x, train_y)
        scores = [float(value) for value in model.predict(validation_x)]
        key = _validation_key(validation, scores)
        if best is None or key > best[0]:
            best = (key, alpha)
    assert best is not None
    fit_rows = tuple(train) + tuple(validation)
    fit_x, _ = _numpy_matrix(fit_rows)
    fit_y = _rank_target(fit_rows)
    test_x, _ = _numpy_matrix(test)
    final = make_pipeline(StandardScaler(), Ridge(alpha=best[1], fit_intercept=True))
    final.fit(fit_x, fit_y)
    return [float(value) for value in final.predict(test_x)]


def _predict_hist_gb_v3(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
    except ImportError as exc:
        raise ValueError("SKLEARN_NOT_INSTALLED") from exc
    train_x, _ = _numpy_matrix(train)
    train_y = _rank_target(train)
    validation_x, _ = _numpy_matrix(validation)
    candidates = (
        {"max_leaf_nodes": 7, "max_depth": 3, "min_samples_leaf": 40, "l2_regularization": 20.0},
        {"max_leaf_nodes": 15, "max_depth": 4, "min_samples_leaf": 60, "l2_regularization": 20.0},
        {"max_leaf_nodes": 15, "max_depth": 3, "min_samples_leaf": 80, "l2_regularization": 40.0},
    )
    best: tuple[tuple[float, float, float, float], Mapping[str, object]] | None = None
    for params in candidates:
        model = HistGradientBoostingRegressor(
            learning_rate=0.035,
            max_iter=260,
            early_stopping=False,
            random_state=seed,
            **params,
        )
        model.fit(train_x, train_y)
        scores = [float(value) for value in model.predict(validation_x)]
        key = _validation_key(validation, scores)
        if best is None or key > best[0]:
            best = (key, params)
    assert best is not None
    fit_rows = tuple(train) + tuple(validation)
    fit_x, _ = _numpy_matrix(fit_rows)
    fit_y = _rank_target(fit_rows)
    test_x, _ = _numpy_matrix(test)
    final = HistGradientBoostingRegressor(
        learning_rate=0.035,
        max_iter=260,
        early_stopping=False,
        random_state=seed,
        **best[1],
    )
    final.fit(fit_x, fit_y)
    return [float(value) for value in final.predict(test_x)]


def _predict_lightgbm_v3(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    try:
        from lightgbm import LGBMRanker, early_stopping
    except ImportError as exc:
        raise ValueError("LIGHTGBM_NOT_INSTALLED") from exc
    train_x, _ = _numpy_matrix(train)
    train_y = _relevance(train)
    validation_x, _ = _numpy_matrix(validation)
    validation_y = _relevance(validation)
    candidates = (
        {"num_leaves": 7, "max_depth": 3, "min_child_samples": 40, "reg_lambda": 15.0},
        {"num_leaves": 15, "max_depth": 4, "min_child_samples": 60, "reg_lambda": 30.0},
    )
    best: tuple[tuple[float, float, float, float], Mapping[str, object], int] | None = None
    for params in candidates:
        model = LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            n_estimators=700,
            learning_rate=0.025,
            feature_fraction=0.8,
            bagging_fraction=0.9,
            bagging_freq=1,
            random_state=seed,
            n_jobs=1,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
            **params,
        )
        model.fit(
            train_x,
            train_y,
            group=_group_sizes(train),
            eval_set=[(validation_x, validation_y)],
            eval_group=[_group_sizes(validation)],
            eval_metric="ndcg",
            eval_at=[5, 10],
            callbacks=[early_stopping(40, verbose=False)],
        )
        scores = [float(value) for value in model.predict(validation_x)]
        key = _validation_key(validation, scores) if _nondegenerate(scores) else (-999.0,) * 4
        rounds = max(20, int(getattr(model, "best_iteration_", 0) or 0))
        if best is None or key > best[0]:
            best = (key, params, rounds)
    assert best is not None
    fit_rows = tuple(train) + tuple(validation)
    fit_x, _ = _numpy_matrix(fit_rows)
    fit_y = _relevance(fit_rows)
    test_x, _ = _numpy_matrix(test)
    final = LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=best[2],
        learning_rate=0.025,
        feature_fraction=0.8,
        bagging_fraction=0.9,
        bagging_freq=1,
        random_state=seed,
        n_jobs=1,
        verbosity=-1,
        deterministic=True,
        force_col_wise=True,
        **best[1],
    )
    final.fit(fit_x, fit_y, group=_group_sizes(fit_rows))
    values = [float(value) for value in final.predict(test_x)]
    if not _nondegenerate(values):
        raise ValueError("LIGHTGBM_DEGENERATE_TEST_SCORE")
    return values


def _predict_xgboost_v3(
    train: Sequence[Row], validation: Sequence[Row], test: Sequence[Row], seed: int,
) -> list[float]:
    try:
        from xgboost import XGBRanker
    except ImportError as exc:
        raise ValueError("XGBOOST_NOT_INSTALLED") from exc
    train_x, _ = _numpy_matrix(train)
    train_y = _relevance(train)
    validation_x, _ = _numpy_matrix(validation)
    validation_y = _relevance(validation)
    candidates = (
        {"max_depth": 2, "min_child_weight": 1.0, "reg_lambda": 10.0, "reg_alpha": 0.0},
        {"max_depth": 3, "min_child_weight": 1.0, "reg_lambda": 20.0, "reg_alpha": 0.1},
        {"max_depth": 3, "min_child_weight": 5.0, "reg_lambda": 30.0, "reg_alpha": 0.2},
    )
    best: tuple[tuple[float, float, float, float], Mapping[str, object], int] | None = None
    for params in candidates:
        model = XGBRanker(
            objective="rank:ndcg",
            eval_metric="ndcg@10",
            n_estimators=700,
            learning_rate=0.025,
            subsample=0.9,
            colsample_bytree=0.85,
            tree_method="hist",
            lambdarank_pair_method="topk",
            lambdarank_num_pair_per_sample=10,
            random_state=seed,
            n_jobs=1,
            verbosity=0,
            early_stopping_rounds=40,
            **params,
        )
        model.fit(
            train_x,
            train_y,
            qid=_qid(train),
            eval_set=[(validation_x, validation_y)],
            eval_qid=[_qid(validation)],
            verbose=False,
        )
        scores = [float(value) for value in model.predict(validation_x)]
        key = _validation_key(validation, scores) if _nondegenerate(scores) else (-999.0,) * 4
        rounds = max(20, int(getattr(model, "best_iteration", 0) or 0) + 1)
        if best is None or key > best[0]:
            best = (key, params, rounds)
    assert best is not None
    fit_rows = tuple(train) + tuple(validation)
    fit_x, _ = _numpy_matrix(fit_rows)
    fit_y = _relevance(fit_rows)
    test_x, _ = _numpy_matrix(test)
    final = XGBRanker(
        objective="rank:ndcg",
        eval_metric="ndcg@10",
        n_estimators=best[2],
        learning_rate=0.025,
        subsample=0.9,
        colsample_bytree=0.85,
        tree_method="hist",
        lambdarank_pair_method="topk",
        lambdarank_num_pair_per_sample=10,
        random_state=seed,
        n_jobs=1,
        verbosity=0,
        **best[1],
    )
    final.fit(fit_x, fit_y, qid=_qid(fit_rows), verbose=False)
    values = [float(value) for value in final.predict(test_x)]
    if not _nondegenerate(values):
        raise ValueError("XGBOOST_DEGENERATE_TEST_SCORE")
    return values


PREDICTOR_OVERRIDES: Mapping[str, Predictor] = {
    "ridge_ranker": _predict_ridge_v3,
    "hist_gradient_boosting_ranker": _predict_hist_gb_v3,
    "lightgbm_ranker": _predict_lightgbm_v3,
    "xgboost_ranker": _predict_xgboost_v3,
}


def conservative_online_weights(
    prior_ic: Mapping[str, Sequence[float]],
    available_models: Sequence[str],
    *,
    max_weight: float = 0.55,
    minimum_history: int = 6,
) -> dict[str, float]:
    """Use only completed prior folds and never equal-weight negative models."""
    models = sorted(name for name in available_models if name != ENSEMBLE_MODEL)
    if not models:
        raise ValueError("MODEL_LAB_ENSEMBLE_NO_BASE_MODELS")
    quality: dict[str, float] = {}
    for name in models:
        history = [float(value) for value in prior_ic.get(name, ()) if isfinite(float(value))]
        if len(history) < minimum_history:
            continue
        mean_ic = fmean(history)
        positive_ratio = fmean(1.0 if value > 0.0 else 0.0 for value in history)
        dispersion = pstdev(history) if len(history) > 1 else 0.0
        lower_score = mean_ic - 0.50 * dispersion / sqrt(len(history))
        if mean_ic > 0.0 and positive_ratio >= 0.50:
            quality[name] = max(1e-6, lower_score + 0.25 * mean_ic)
    if not quality:
        fallback = "momentum_baseline" if "momentum_baseline" in models else models[0]
        return {fallback: 1.0}
    total = sum(quality.values())
    raw = {name: value / total for name, value in quality.items()}
    capped = {name: min(max_weight, value) for name, value in raw.items()}
    remaining = 1.0 - sum(capped.values())
    while remaining > 1e-12:
        room = {name: max_weight - value for name, value in capped.items() if value < max_weight - 1e-12}
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
    return {name: value / normalized for name, value in capped.items() if value > 0.0}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _quartiles(values: Sequence[float]) -> tuple[float, float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0, 0.0
    low = ordered[max(0, int(0.25 * (len(ordered) - 1)))]
    high = ordered[min(len(ordered) - 1, int(0.75 * (len(ordered) - 1)))]
    return low, high


def publish_reference_diagnostics(output_dir: Path) -> dict[str, object]:
    """Publish a consensus diagnostic without converting weak evidence into a signal."""
    output = Path(output_dir)
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    leaderboard = _read_csv(output / "model_leaderboard.csv")
    forward = _read_csv(output / "forward_model_scores.csv")
    qualified: list[str] = []
    positive: list[str] = []
    for row in leaderboard:
        name = str(row.get("model") or "")
        if name == ENSEMBLE_MODEL or row.get("status") != "SUCCESS":
            continue
        if row.get("forward_score_status") != "PASS":
            continue
        qualified.append(name)
        try:
            mean_ic = float(row.get("mean_rank_ic") or 0.0)
            ratio = float(row.get("positive_rank_ic_ratio") or 0.0)
        except ValueError:
            continue
        if mean_ic > 0.0 and ratio >= 0.50:
            positive.append(name)
    source_models = positive if len(positive) >= 2 else qualified
    by_symbol: dict[str, list[float]] = {}
    for row in forward:
        if str(row.get("model") or "") not in source_models:
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        try:
            value = float(row.get("percentile") or 0.0)
        except ValueError:
            continue
        if symbol and isfinite(value):
            by_symbol.setdefault(symbol, []).append(value)
    status = "REFERENCE_CANDIDATE" if len(positive) >= 2 else "INSUFFICIENT_POSITIVE_MODELS"
    rows: list[dict[str, object]] = []
    for symbol, values in by_symbol.items():
        q1, q3 = _quartiles(values)
        rows.append({
            "symbol": symbol,
            "consensus_percentile": fmean(values),
            "median_percentile": median(values),
            "rank_dispersion_iqr": q3 - q1,
            "model_count": len(values),
            "positive_evidence_model_count": len(positive),
            "top_quintile_agreement": sum(1 for value in values if value >= 0.80),
            "reference_status": status,
            "actionable": "false",
        })
    rows.sort(key=lambda row: (-float(row["consensus_percentile"]), float(row["rank_dispersion_iqr"]), str(row["symbol"])))
    fields = (
        "symbol", "consensus_percentile", "median_percentile", "rank_dispersion_iqr",
        "model_count", "positive_evidence_model_count", "top_quintile_agreement",
        "reference_status", "actionable",
    )
    _write_csv(output / "reference_consensus_diagnostic.csv", rows, fields)
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["validation_selected_learners"] = sorted(PREDICTOR_OVERRIDES)
    summary["ensemble_contract_v3"] = {
        "prior_only": True,
        "minimum_history_folds": 6,
        "negative_or_unstable_models_receive_zero_weight": True,
        "fallback": "momentum_baseline_only",
    }
    summary["reference_diagnostic"] = {
        "status": status,
        "source_models": source_models,
        "positive_evidence_models": positive,
        "symbol_count": len(rows),
        "actionable": False,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path = output / "model_lab_report.txt"
    with report_path.open("a", encoding="utf-8") as stream:
        stream.write("\nMODEL LAB UPGRADE V3\n")
        stream.write(f"Reference diagnostic: {status}\n")
        stream.write(f"Positive-evidence models: {','.join(positive) or 'none'}\n")
        stream.write("Consensus diagnostic is non-actionable and does not relax the research gate.\n")
    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "reference_diagnostic_status": status,
        "reference_diagnostic_models": source_models,
        "positive_evidence_models": positive,
        "reference_symbol_count": len(rows),
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    overrides = dict(PREDICTOR_OVERRIDES)
    custom = kwargs.pop("predictor_overrides", None)
    if isinstance(custom, Mapping):
        overrides.update(custom)
    original_weights = legacy_runner.online_ensemble_weights
    legacy_runner.online_ensemble_weights = conservative_online_weights
    try:
        result = quality_runner.run_model_lab(**kwargs, predictor_overrides=overrides)
        diagnostics = publish_reference_diagnostics(Path(str(kwargs["output_dir"])))
        return {**result, **diagnostics, "upgrade_schema_version": SCHEMA_VERSION}
    finally:
        legacy_runner.online_ensemble_weights = original_weights


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.model_lab")
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--evaluation-months", type=int, default=24)
    parser.add_argument("--minimum-train-months", type=int, default=24)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--strict-dependencies", action="store_true")
    parser.add_argument("--buy-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-tax-bps", type=float, default=100.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_model_lab(
        input_zip=args.input_zip,
        output_dir=args.output_dir,
        models=tuple(item.strip() for item in args.models.split(",") if item.strip()),
        evaluation_months=args.evaluation_months,
        minimum_train_months=args.minimum_train_months,
        inner_validation_months=args.inner_validation_months,
        top_k=args.top_k,
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
    "PREDICTOR_OVERRIDES",
    "conservative_online_weights",
    "publish_reference_diagnostics",
    "run_model_lab",
    "main",
]
