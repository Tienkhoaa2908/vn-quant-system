"""Run a leakage-safe multi-model research tournament and publish artifacts."""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
import json
from pathlib import Path
from statistics import fmean
from typing import Callable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .model_lab_core import (
    BASE_MODELS,
    DEFAULT_MODELS,
    ENSEMBLE_MODEL,
    SCHEMA_VERSION,
    BacktestConfig,
    ModelEvaluation,
    Outcome,
    backtest_top_k,
    build_walk_forward_folds,
    candidate_gate,
    ensemble_scores,
    model_rank_metrics,
    online_ensemble_weights,
    select_research_champion,
)
from .model_lab_models import MODEL_SPECS, Predictor, model_availability, predict_model
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    Row,
    _csv_rows,
    _hash_file,
    _load_rows,
    _load_verified_input,
    _parse_date,
    _parse_float,
)
from .nghien_cuu_moc_4.du_doan_tien_phuong_features import _rank


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _csv_bytes(rows: Sequence[Mapping[str, object]], fields: Sequence[str] | None = None) -> bytes:
    if not rows and not fields:
        raise ValueError("MODEL_LAB_CSV_FIELDS_REQUIRED_FOR_EMPTY_ROWS")
    fieldnames = list(fields or rows[0].keys())
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue().encode("utf-8-sig")


def _load_outcomes(blob: bytes) -> dict[tuple[date, str], Outcome]:
    result: dict[tuple[date, str], Outcome] = {}
    for raw in _csv_rows(blob, "nhan.csv"):
        day = _parse_date(raw.get("ngay"), "nhan.ngay")
        label_end = _parse_date(raw.get("ngay_ket_thuc_nhan"), "nhan.ngay_ket_thuc_nhan", allow_empty=True)
        symbol = str(raw.get("ma") or "").strip().upper()
        stock_return = _parse_float(raw.get("loi_nhuan_co_phieu", ""), "nhan.loi_nhuan_co_phieu", allow_empty=True)
        benchmark_return = _parse_float(raw.get("loi_nhuan_benchmark", ""), "nhan.loi_nhuan_benchmark", allow_empty=True)
        relative_return = _parse_float(raw.get("loi_nhuan_tuong_doi", ""), "nhan.loi_nhuan_tuong_doi", allow_empty=True)
        if day is None or label_end is None or not symbol:
            continue
        if stock_return is None or benchmark_return is None or relative_return is None:
            continue
        key = (day, symbol)
        if key in result:
            raise ValueError(f"MODEL_LAB_OUTCOME_DUPLICATE:{day}:{symbol}")
        result[key] = Outcome(
            day=day,
            symbol=symbol,
            label_end=label_end,
            stock_return=float(stock_return),
            benchmark_return=float(benchmark_return),
            relative_return=float(relative_return),
        )
    if not result:
        raise ValueError("MODEL_LAB_OUTCOMES_EMPTY")
    return result


def _dependency_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for package in ("scikit-learn", "lightgbm", "xgboost", "torch"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = None
    return result


def _daily_ic(rows: Sequence[Row], scores: Sequence[float]) -> float:
    metrics = model_rank_metrics(rows, scores, min(10, len(rows)))
    return float(metrics["mean_rank_ic"])


def _split_final_train(history: Sequence[Row], forward_day: date, validation_months: int = 3) -> tuple[list[Row], list[Row]]:
    eligible = [row for row in history if row.label_end is not None and row.label_end < forward_day]
    dates = sorted({row.ngay for row in eligible})
    if len(dates) <= validation_months + 12:
        raise ValueError("MODEL_LAB_FINAL_TRAIN_TOO_SHORT")
    validation_dates = set(dates[-validation_months:])
    validation_start = min(validation_dates)
    train = [
        row for row in eligible
        if row.ngay not in validation_dates
        and row.label_end is not None
        and row.label_end < validation_start
    ]
    validation = [row for row in eligible if row.ngay in validation_dates]
    if not train or not validation:
        raise ValueError("MODEL_LAB_FINAL_SPLIT_EMPTY")
    return train, validation


def _grade(evaluations: Mapping[str, ModelEvaluation], champion: str) -> str:
    if champion == "NO_MODEL_APPROVED":
        return "RED_NO_PREDICTIVE_VALUE"
    selected = evaluations[champion]
    rank_ic = float(selected.metrics.get("mean_rank_ic", 0.0) or 0.0)
    excess = float(selected.backtest.get("average_net_excess_return", 0.0) or 0.0)
    stable = float(selected.metrics.get("positive_rank_ic_ratio", 0.0) or 0.0)
    if rank_ic >= 0.03 and excess > 0.0 and stable >= 0.60:
        return "GREEN_PAPER_CANDIDATE"
    return "YELLOW_WEAK_POSITIVE_EVIDENCE"


def run_model_lab(
    *,
    input_zip: Path,
    output_dir: Path,
    models: Sequence[str] = DEFAULT_MODELS,
    evaluation_months: int = 24,
    minimum_train_months: int = 24,
    inner_validation_months: int = 3,
    top_k: int = 10,
    seed: int = 20260731,
    strict_dependencies: bool = False,
    buy_fee_bps: float = 15.0,
    sell_fee_bps: float = 15.0,
    sell_tax_bps: float = 100.0,
    slippage_bps: float = 10.0,
    predictor_overrides: Mapping[str, Predictor] | None = None,
) -> dict[str, object]:
    requested = tuple(dict.fromkeys(str(name).strip() for name in models if str(name).strip()))
    unknown = sorted(set(requested) - set(DEFAULT_MODELS))
    if unknown:
        raise ValueError(f"MODEL_LAB_UNKNOWN_MODELS:{unknown}")
    if "momentum_baseline" not in requested:
        raise ValueError("MODEL_LAB_MOMENTUM_BASELINE_REQUIRED")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    blobs, input_manifest, input_sha = _load_verified_input(Path(input_zip))
    history, forward_rows, forward_day = _load_rows(blobs)
    outcomes = _load_outcomes(blobs["nhan.csv"])
    folds = build_walk_forward_folds(
        history,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        inner_validation_months=inner_validation_months,
    )
    backtest_config = BacktestConfig(
        top_k=top_k,
        buy_fee_bps=buy_fee_bps,
        sell_fee_bps=sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps,
    )
    base_requested = [name for name in requested if name in BASE_MODELS]
    availability = model_availability(base_requested)
    if predictor_overrides:
        for name in predictor_overrides:
            if name in availability:
                availability[name] = {**availability[name], "available": True, "reason": None, "overridden": True}
    missing = [name for name in base_requested if not availability[name]["available"]]
    if strict_dependencies and missing:
        raise ValueError(f"MODEL_LAB_DEPENDENCIES_MISSING:{missing}")

    oos_rows: list[Row] = []
    oos_scores: dict[str, list[float]] = {name: [] for name in requested}
    oos_prediction_rows: list[dict[str, object]] = []
    ensemble_weight_rows: list[dict[str, object]] = []
    prior_ic: dict[str, list[float]] = {name: [] for name in base_requested}
    failures: dict[str, str] = {
        name: str(availability[name]["reason"])
        for name in missing
    }
    completed_folds: dict[str, int] = {name: 0 for name in requested}

    for fold_index, fold in enumerate(folds):
        fold_scores: dict[str, list[float]] = {}
        for name in base_requested:
            if name in failures:
                continue
            try:
                scores = predict_model(
                    name,
                    train_rows=fold.train_rows,
                    validation_rows=fold.validation_rows,
                    test_rows=fold.test_rows,
                    seed=seed + fold_index,
                    overrides=predictor_overrides,
                )
            except Exception as exc:
                failures[name] = f"{type(exc).__name__}:{exc}"
                continue
            fold_scores[name] = scores
        if ENSEMBLE_MODEL in requested:
            available_for_ensemble = sorted(fold_scores)
            if available_for_ensemble:
                weights = online_ensemble_weights(prior_ic, available_for_ensemble)
                fold_scores[ENSEMBLE_MODEL] = ensemble_scores(fold_scores, weights)
                for name, weight in sorted(weights.items()):
                    ensemble_weight_rows.append({
                        "fold": fold.fold_id,
                        "test_date": fold.test_day.isoformat(),
                        "base_model": name,
                        "weight": weight,
                        "prior_fold_count": len(prior_ic.get(name, ())),
                    })
            else:
                failures[ENSEMBLE_MODEL] = "NO_BASE_MODEL_AVAILABLE"
        for name, scores in fold_scores.items():
            completed_folds[name] += 1
            oos_scores[name].extend(scores)
            percentiles = _rank(scores)
            order = sorted(range(len(scores)), key=lambda index: (-scores[index], fold.test_rows[index].ma))
            rank_by_index = {index: rank + 1 for rank, index in enumerate(order)}
            for index, row in enumerate(fold.test_rows):
                outcome = outcomes.get((row.ngay, row.ma))
                if outcome is None:
                    raise ValueError(f"MODEL_LAB_OUTCOME_MISSING:{row.ngay}:{row.ma}")
                oos_prediction_rows.append({
                    "model": name,
                    "fold": fold.fold_id,
                    "test_date": row.ngay.isoformat(),
                    "symbol": row.ma,
                    "score": scores[index],
                    "percentile": percentiles[index],
                    "rank": rank_by_index[index],
                    "selected_top_k": str(rank_by_index[index] <= min(top_k, len(scores))).lower(),
                    "label_end": outcome.label_end.isoformat(),
                    "stock_return": outcome.stock_return,
                    "benchmark_return": outcome.benchmark_return,
                    "relative_return": outcome.relative_return,
                })
        # Update histories only after all current-fold predictions and ensemble
        # weights have been fixed.  Current labels cannot affect current weights.
        for name, scores in fold_scores.items():
            if name in prior_ic:
                prior_ic[name].append(_daily_ic(fold.test_rows, scores))
        oos_rows.extend(fold.test_rows)

    expected_fold_count = len(folds)
    evaluations: dict[str, ModelEvaluation] = {}
    period_rows: list[dict[str, object]] = []
    nav_rows: list[dict[str, object]] = []
    for name in requested:
        if name in failures or completed_folds.get(name, 0) != expected_fold_count:
            error = failures.get(name) or f"INCOMPLETE_FOLDS:{completed_folds.get(name, 0)}/{expected_fold_count}"
            evaluations[name] = ModelEvaluation(name, "SKIPPED" if name in missing else "FAILED", {}, {}, {}, error)
            continue
        scores = oos_scores[name]
        metrics = model_rank_metrics(oos_rows, scores, top_k)
        backtest, model_period_rows, model_nav_rows = backtest_top_k(
            model=name,
            rows=oos_rows,
            scores=scores,
            outcomes=outcomes,
            config=backtest_config,
        )
        period_rows.extend(model_period_rows)
        nav_rows.extend(model_nav_rows)
        evaluations[name] = ModelEvaluation(name, "SUCCESS", metrics, backtest, {})

    baseline = evaluations.get("momentum_baseline")
    if baseline is None or baseline.status != "SUCCESS":
        raise ValueError("MODEL_LAB_BASELINE_FAILED")
    evaluations_with_gates: dict[str, ModelEvaluation] = {}
    for name, evaluation in evaluations.items():
        if evaluation.status != "SUCCESS":
            evaluations_with_gates[name] = evaluation
            continue
        gate = (
            {"baseline_reference": True}
            if name == "momentum_baseline"
            else candidate_gate(evaluation.metrics, evaluation.backtest, baseline.metrics, baseline.backtest)
        )
        evaluations_with_gates[name] = ModelEvaluation(
            name, evaluation.status, evaluation.metrics, evaluation.backtest, gate, evaluation.error,
        )
    evaluations = evaluations_with_gates
    champion, champion_reason = select_research_champion(evaluations)
    grade = _grade(evaluations, champion)

    final_train, final_validation = _split_final_train(history, forward_day)
    forward_scores: dict[str, list[float]] = {}
    for name in base_requested:
        evaluation = evaluations.get(name)
        if evaluation is None or evaluation.status != "SUCCESS":
            continue
        try:
            forward_scores[name] = predict_model(
                name,
                train_rows=final_train,
                validation_rows=final_validation,
                test_rows=forward_rows,
                seed=seed + 100_000,
                overrides=predictor_overrides,
            )
        except Exception as exc:
            failures[f"forward:{name}"] = f"{type(exc).__name__}:{exc}"
    if ENSEMBLE_MODEL in requested and forward_scores:
        final_weights = online_ensemble_weights(prior_ic, sorted(forward_scores))
        forward_scores[ENSEMBLE_MODEL] = ensemble_scores(forward_scores, final_weights)
    else:
        final_weights = {}
    reference_model = (
        champion
        if champion != "NO_MODEL_APPROVED" and champion in forward_scores
        else ENSEMBLE_MODEL if ENSEMBLE_MODEL in forward_scores
        else "momentum_baseline"
    )
    forward_rows_output: list[dict[str, object]] = []
    for name, scores in sorted(forward_scores.items()):
        percentiles = _rank(scores)
        ordered = sorted(range(len(scores)), key=lambda index: (-scores[index], forward_rows[index].ma))
        ranks = {index: rank + 1 for rank, index in enumerate(ordered)}
        for index, row in enumerate(forward_rows):
            forward_rows_output.append({
                "signal_date": forward_day.isoformat(),
                "model": name,
                "symbol": row.ma,
                "score": scores[index],
                "percentile": percentiles[index],
                "rank": ranks[index],
                "selected_top_k": str(ranks[index] <= min(top_k, len(scores))).lower(),
                "research_champion": champion,
                "reference_model": reference_model,
                "live_capital_approved": "false",
            })

    leaderboard: list[dict[str, object]] = []
    for name in requested:
        evaluation = evaluations[name]
        spec = MODEL_SPECS.get(name)
        metrics = evaluation.metrics
        backtest = evaluation.backtest
        leaderboard.append({
            "model": name,
            "family": "ensemble" if name == ENSEMBLE_MODEL else spec.family if spec else "unknown",
            "dependency": "multiple" if name == ENSEMBLE_MODEL else spec.dependency if spec else "",
            "status": evaluation.status,
            "oos_folds": completed_folds.get(name, 0),
            "mean_rank_ic": metrics.get("mean_rank_ic", ""),
            "positive_rank_ic_ratio": metrics.get("positive_rank_ic_ratio", ""),
            "precision_at_k": metrics.get("precision_at_k", ""),
            "top_k_relative_return": metrics.get("top_k_relative_return", ""),
            "mean_set_turnover": metrics.get("mean_set_turnover", ""),
            "net_total_return": backtest.get("total_return", ""),
            "relative_total_return": backtest.get("relative_total_return", ""),
            "cagr": backtest.get("cagr", ""),
            "sharpe": backtest.get("sharpe", ""),
            "max_drawdown": backtest.get("max_drawdown", ""),
            "average_net_excess_return": backtest.get("average_net_excess_return", ""),
            "positive_net_excess_ratio": backtest.get("positive_net_excess_ratio", ""),
            "gate_passed": str(all(evaluation.gate.values())).lower() if evaluation.gate else "false",
            "error": evaluation.error or "",
        })
    leaderboard.sort(key=lambda row: (
        row["status"] != "SUCCESS",
        -float(row["relative_total_return"] or -999.0) if row["relative_total_return"] != "" else 999.0,
        str(row["model"]),
    ))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "input_zip_sha256": input_sha,
        "input_manifest_schema": input_manifest.get("manifest_schema_version"),
        "signal_date": forward_day.isoformat(),
        "requested_models": list(requested),
        "availability": availability,
        "dependency_versions": _dependency_versions(),
        "walk_forward": {
            "fold_count": len(folds),
            "first_test_date": folds[0].test_day.isoformat(),
            "last_test_date": folds[-1].test_day.isoformat(),
            "evaluation_months_requested": evaluation_months,
            "minimum_train_months": minimum_train_months,
            "inner_validation_months": inner_validation_months,
            "label_end_purge": True,
        },
        "backtest_contract": {
            "type": "monthly_label_horizon_close_to_close",
            "execution_engine_used": False,
            "warning": "Not exact T+1 execution; use as model discrimination evidence before execution-engine validation.",
            "top_k": top_k,
            "costs": backtest_config.__dict__,
        },
        "research_champion": champion,
        "champion_reason": champion_reason,
        "reference_model_for_forward_watchlist": reference_model,
        "evidence_grade": grade,
        "deployment_status": "PAPER_ONLY" if champion != "NO_MODEL_APPROVED" else "NO_MODEL_APPROVED",
        "live_capital_approved": False,
        "research_eligible": False,
        "final_ensemble_weights": final_weights,
        "failures": failures,
        "evaluations": {
            name: {
                "status": evaluation.status,
                "metrics": evaluation.metrics,
                "backtest": evaluation.backtest,
                "gate": evaluation.gate,
                "error": evaluation.error,
            }
            for name, evaluation in evaluations.items()
        },
        "limitations": [
            "technical_candidate_union_not_point_in_time",
            "price_basis_unconfirmed",
            "corporate_action_inventory_incomplete",
            "label_backtest_close_to_close_not_exact_t1_execution",
            "sector_cap_not_enforced_without_trusted_sector_master",
            "deep_learning_does_not_imply_alpha",
        ],
    }
    report_lines = [
        "VN QUANT MODEL LAB",
        f"Signal date: {forward_day.isoformat()}",
        f"OOS folds: {len(folds)}",
        f"Research champion: {champion}",
        f"Reason: {champion_reason}",
        f"Evidence grade: {grade}",
        f"Forward reference: {reference_model}",
        "Live capital approved: false",
        "",
        "LEADERBOARD",
    ]
    for row in leaderboard:
        report_lines.append(
            f"{row['model']}: {row['status']} | Rank IC={row['mean_rank_ic']} | "
            f"Relative total={row['relative_total_return']} | Sharpe={row['sharpe']} | "
            f"Gate={row['gate_passed']}"
        )
    report_lines.extend([
        "",
        "Backtest is monthly close(T)-to-close(T+H) label-horizon evidence with estimated costs.",
        "It is not the exact T+1 execution engine and cannot approve live capital by itself.",
        "",
    ])

    destination.mkdir(parents=True)
    files: dict[str, bytes] = {
        "model_leaderboard.csv": _csv_bytes(leaderboard),
        "oos_predictions.csv": _csv_bytes(oos_prediction_rows),
        "oos_backtest_periods.csv": _csv_bytes(period_rows),
        "oos_nav.csv": _csv_bytes(nav_rows),
        "ensemble_weights_oos.csv": _csv_bytes(
            ensemble_weight_rows,
            ("fold", "test_date", "base_model", "weight", "prior_fold_count"),
        ),
        "forward_model_scores.csv": _csv_bytes(forward_rows_output),
        "model_lab_summary.json": _json_bytes(summary),
        "model_lab_report.txt": ("\n".join(report_lines)).encode("utf-8"),
    }
    file_records: dict[str, dict[str, object]] = {}
    for name, payload in files.items():
        path = destination / name
        path.write_bytes(payload)
        file_records[name] = {"sha256": sha256(payload).hexdigest(), "size": len(payload)}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "signal_date": forward_day.isoformat(),
        "research_champion": champion,
        "evidence_grade": grade,
        "live_capital_approved": False,
        "credentials_recorded": False,
        "files": file_records,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
    archive_path = destination / "model_lab_output.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(destination.iterdir()):
            if path.is_file() and path != archive_path:
                archive.write(path, arcname=path.name)
    return {
        "status": "SUCCESS",
        "research_champion": champion,
        "champion_reason": champion_reason,
        "evidence_grade": grade,
        "fold_count": len(folds),
        "models_success": [name for name, item in evaluations.items() if item.status == "SUCCESS"],
        "models_skipped_or_failed": {name: item.error for name, item in evaluations.items() if item.status != "SUCCESS"},
        "output_dir": str(destination),
        "output_zip": str(archive_path),
        "output_zip_sha256": _hash_file(archive_path),
        "live_capital_approved": False,
    }


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
    try:
        result = run_model_lab(
            input_zip=args.input_zip,
            output_dir=args.output_dir,
            models=tuple(name.strip() for name in args.models.split(",") if name.strip()),
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
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
