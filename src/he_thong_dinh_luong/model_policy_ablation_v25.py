"""V25 sensitivity analysis for one-month policy tests and rolling training.

The predictive target remains one 20-session month.  V25 does not shorten that
label and does not relax any historical gate.  It adds two diagnostics:

* re-score an existing OOS prediction archive with six prior months selecting
  the turnover cap for exactly the next one month;
* retrain the same model families with expanding, rolling-60 or rolling-72
  training windows while keeping monthly test folds, label-end purge, DNSE
  base/stress costs and the v15 gate unchanged.

These experiments are post-review sensitivity analyses, not an independent
holdout and never approve live capital.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from datetime import date
import io
import json
from pathlib import Path
import shutil
from typing import Callable, Iterator, Mapping, Sequence

from . import model_lab_runner as legacy_runner
from . import model_lab_upgrade_v13 as v13
from . import model_lab_upgrade_v15 as v15
from .model_lab_core import DEFAULT_MODELS, WalkForwardFold
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row

SCHEMA_VERSION = "model_policy_ablation_v25"
REPORT_FILE = "model_policy_ablation_v25.json"
DEFAULT_TRAIN_MODES = ("rolling_60", "rolling_72")
VALID_TRAIN_MODES = {"expanding", "rolling_60", "rolling_72"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and not fields:
        raise ValueError("V25_CSV_FIELDS_REQUIRED")
    fieldnames = list(fields or rows[0].keys())
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"V25_JSON_OBJECT_REQUIRED:{Path(path).name}")
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


def build_walk_forward_folds_v25(
    rows: Sequence[Row],
    *,
    evaluation_months: int,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
    train_window_months: int | None = None,
) -> list[WalkForwardFold]:
    """Build expanding or rolling monthly folds with label-end purge.

    ``train_window_months=None`` reproduces the expanding contract.  A rolling
    window keeps only the most recent N distinct train signal dates after the
    validation boundary purge.  Validation and test remain monthly.
    """
    if evaluation_months < 3:
        raise ValueError("V25_EVALUATION_MONTHS_TOO_SMALL")
    if minimum_train_months < 12:
        raise ValueError("V25_MINIMUM_TRAIN_MONTHS_TOO_SMALL")
    if inner_validation_months < 1:
        raise ValueError("V25_INNER_VALIDATION_MONTHS_TOO_SMALL")
    if train_window_months is not None and train_window_months < minimum_train_months:
        raise ValueError("V25_TRAIN_WINDOW_BELOW_MINIMUM_TRAIN")

    dates = sorted({row.ngay for row in rows})
    if len(dates) <= minimum_train_months:
        raise ValueError("V25_INSUFFICIENT_DATES")
    candidate_test_dates = dates[-min(evaluation_months, len(dates)):]
    folds: list[WalkForwardFold] = []

    for test_day in candidate_test_dates:
        eligible = [
            row
            for row in rows
            if row.ngay < test_day
            and row.label_end is not None
            and row.label_end < test_day
        ]
        eligible_dates = sorted({row.ngay for row in eligible})
        if len(eligible_dates) < minimum_train_months + inner_validation_months:
            continue

        validation_dates_ordered = eligible_dates[-inner_validation_months:]
        validation_dates = set(validation_dates_ordered)
        validation_start = validation_dates_ordered[0]
        train_pool = [
            row
            for row in eligible
            if row.ngay not in validation_dates
            and row.label_end is not None
            and row.label_end < validation_start
        ]
        train_dates_ordered = sorted({row.ngay for row in train_pool})
        if train_window_months is not None:
            train_dates_ordered = train_dates_ordered[-train_window_months:]
        if len(train_dates_ordered) < minimum_train_months:
            continue
        selected_train_dates = set(train_dates_ordered)
        train = tuple(row for row in train_pool if row.ngay in selected_train_dates)
        validation = tuple(row for row in eligible if row.ngay in validation_dates)
        test = tuple(row for row in rows if row.ngay == test_day)
        if not train or not validation or not test:
            continue
        folds.append(
            WalkForwardFold(
                fold_id=f"wf_{test_day.isoformat()}",
                test_day=test_day,
                train_rows=train,
                validation_rows=validation,
                test_rows=test,
            )
        )

    if len(folds) < 3:
        raise ValueError("V25_TOO_FEW_VALID_FOLDS")
    return folds


def _train_window_for_mode(mode: str) -> int | None:
    normalized = str(mode).strip().lower()
    if normalized == "expanding":
        return None
    if normalized == "rolling_60":
        return 60
    if normalized == "rolling_72":
        return 72
    raise ValueError(f"V25_UNKNOWN_TRAIN_MODE:{mode}")


@contextmanager
def _patched_fold_builder(train_window_months: int | None) -> Iterator[None]:
    original = legacy_runner.build_walk_forward_folds

    def builder(
        rows: Sequence[Row],
        *,
        evaluation_months: int,
        minimum_train_months: int = 24,
        inner_validation_months: int = 3,
    ) -> list[WalkForwardFold]:
        return build_walk_forward_folds_v25(
            rows,
            evaluation_months=evaluation_months,
            minimum_train_months=minimum_train_months,
            inner_validation_months=inner_validation_months,
            train_window_months=train_window_months,
        )

    legacy_runner.build_walk_forward_folds = builder
    try:
        yield
    finally:
        legacy_runner.build_walk_forward_folds = original


def _cost_from_summary(summary: Mapping[str, object]) -> tuple[int, v13.DnseCashCostConfig]:
    nested = summary.get("dnse_cash_cost_contract_v13")
    raw = nested if isinstance(nested, dict) else {}
    backtest = summary.get("backtest_contract")
    backtest_map = backtest if isinstance(backtest, dict) else {}
    costs = backtest_map.get("costs")
    costs_map = costs if isinstance(costs, dict) else {}
    top_k = int(float(costs_map.get("top_k", backtest_map.get("top_k", 10)) or 10))
    return top_k, v13.DnseCashCostConfig(
        broker_buy_fee_bps=float(raw.get("broker_buy_fee_bps", 0.0) or 0.0),
        broker_sell_fee_bps=float(raw.get("broker_sell_fee_bps", 0.0) or 0.0),
        exchange_buy_fee_bps=float(raw.get("exchange_buy_fee_bps", 2.7) or 2.7),
        exchange_sell_fee_bps=float(raw.get("exchange_sell_fee_bps", 2.7) or 2.7),
        sell_tax_bps=float(raw.get("sell_tax_bps", 10.0) or 10.0),
        transfer_fee_vnd_per_share=float(
            raw.get("transfer_fee_vnd_per_share", 0.3) or 0.3
        ),
        transfer_reference_price_vnd=float(
            raw.get("transfer_reference_price_vnd", 10_000.0) or 10_000.0
        ),
        slippage_bps=float(raw.get("base_slippage_bps_each_side", 5.0) or 5.0),
        stress_slippage_bps=float(
            raw.get("stress_slippage_bps_each_side", 10.0) or 10.0
        ),
    )


def _compact_result(result: Mapping[str, object]) -> dict[str, object]:
    rows = list(result.get("summary_rows", []))
    return {
        "status": result.get("status"),
        "historical_reference_model": result.get("historical_reference_model"),
        "historical_reference_gate_passed": result.get(
            "historical_reference_gate_passed"
        ),
        "validation_months": result.get("validation_months"),
        "test_months": result.get("test_months"),
        "minimum_outer_test_periods": result.get("minimum_outer_test_periods"),
        "candidate_diagnostics": rows,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def rescore_existing_model_output(
    model_output: Path,
    output_dir: Path,
    *,
    validation_months: int = 6,
    test_months: int = 1,
    minimum_outer_test_periods: int = 48,
    replacement_caps: Sequence[int] = v13.DEFAULT_REPLACEMENT_CAPS,
) -> dict[str, object]:
    source = Path(model_output).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_dir():
        raise ValueError("V25_MODEL_OUTPUT_NOT_FOUND")
    if destination.exists():
        raise FileExistsError(f"V25_OUTPUT_EXISTS:{destination}")
    predictions = _read_csv(source / "oos_predictions.csv")
    summary = _read_json(source / "model_lab_summary.json")
    top_k, cost = _cost_from_summary(summary)
    result = v15.model_wise_nested_evaluation(
        predictions,
        top_k=top_k,
        replacement_caps=replacement_caps,
        validation_months=validation_months,
        test_months=test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        cost=cost,
    )
    destination.mkdir(parents=True)
    for name, key in (
        ("model_comparison_v25.csv", "summary_rows"),
        ("policy_selection_v25.csv", "selection_rows"),
        ("outer_test_periods_v25.csv", "outer_rows"),
        ("outer_test_stress_periods_v25.csv", "stress_rows"),
    ):
        rows = list(result.get(key, []))
        if rows:
            _write_csv(destination / name, rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "experiment": "EXISTING_OOS_POLICY_TEST_ONE_MONTH",
        "source_model_output": str(source),
        "source_prediction_row_count": len(predictions),
        "policy_validation_months": validation_months,
        "policy_test_months": test_months,
        "predictive_label_horizon": "20_SESSIONS_UNCHANGED",
        "model_test_fold": "ONE_MONTH_UNCHANGED",
        "training_reused": True,
        "sensitivity_analysis_only": True,
        "independent_holdout": False,
        "result": _compact_result(result),
        "technical_validation_only": True,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(destination / REPORT_FILE, report)
    return {**report, "output_dir": str(destination)}


def run_training_ablation(
    input_zip: Path,
    output_root: Path,
    *,
    modes: Sequence[str] = DEFAULT_TRAIN_MODES,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
    nested_validation_months: int = 6,
    nested_test_months: int = 1,
    minimum_outer_test_periods: int = 48,
    seed: int = 20260731,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    root = Path(output_root).resolve()
    if not source.is_file():
        raise ValueError("V25_INPUT_ZIP_NOT_FOUND")
    if root.exists():
        raise FileExistsError(f"V25_OUTPUT_ROOT_EXISTS:{root}")
    normalized_modes = tuple(dict.fromkeys(str(mode).strip().lower() for mode in modes))
    if not normalized_modes or any(mode not in VALID_TRAIN_MODES for mode in normalized_modes):
        raise ValueError("V25_INVALID_TRAIN_MODES")
    staging = root.with_name(f".{root.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    results: dict[str, object] = {}
    try:
        for mode in normalized_modes:
            window = _train_window_for_mode(mode)
            destination = staging / mode
            with _patched_fold_builder(window):
                run = v15.run_model_lab(
                    input_zip=source,
                    output_dir=destination,
                    models=DEFAULT_MODELS,
                    evaluation_months=evaluation_months,
                    minimum_train_months=minimum_train_months,
                    inner_validation_months=inner_validation_months,
                    nested_validation_months=nested_validation_months,
                    nested_test_months=nested_test_months,
                    minimum_outer_test_periods=minimum_outer_test_periods,
                    seed=seed,
                    strict_dependencies=True,
                )
            summary = _read_json(destination / "model_lab_summary.json")
            nested = summary.get("nested_model_validation_v15")
            nested_map = nested if isinstance(nested, dict) else {}
            results[mode] = {
                "train_window_months": window,
                "status": nested_map.get("status"),
                "historical_reference_model": nested_map.get(
                    "historical_reference_model"
                ),
                "historical_reference_gate_passed": nested_map.get(
                    "historical_reference_gate_passed"
                ),
                "model_details": nested_map.get("model_details", {}),
                "runner_result": run,
            }
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "experiment": "TRAIN_WINDOW_AND_ONE_MONTH_POLICY_ABLATION",
            "input_zip": str(source),
            "modes": list(normalized_modes),
            "evaluation_months": evaluation_months,
            "minimum_train_months": minimum_train_months,
            "inner_validation_months": inner_validation_months,
            "nested_validation_months": nested_validation_months,
            "nested_test_months": nested_test_months,
            "minimum_outer_test_periods": minimum_outer_test_periods,
            "predictive_label_horizon": "20_SESSIONS_UNCHANGED",
            "model_test_fold": "ONE_MONTH_UNCHANGED",
            "results": results,
            "sensitivity_analysis_only": True,
            "independent_holdout": False,
            "technical_validation_only": True,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(staging / REPORT_FILE, report)
        staging.replace(root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {**report, "output_root": str(root)}


def _parse_modes(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.model_policy_ablation_v25"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("rescore")
    score.add_argument("--model-output", type=Path, required=True)
    score.add_argument("--output-dir", type=Path, required=True)
    score.add_argument("--validation-months", type=int, default=6)
    score.add_argument("--test-months", type=int, default=1)
    score.add_argument("--minimum-outer-test-periods", type=int, default=48)
    run = sub.add_parser("run")
    run.add_argument("--input-zip", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--modes", default="rolling_60,rolling_72")
    run.add_argument("--evaluation-months", type=int, default=72)
    run.add_argument("--minimum-train-months", type=int, default=60)
    run.add_argument("--inner-validation-months", type=int, default=3)
    run.add_argument("--nested-validation-months", type=int, default=6)
    run.add_argument("--nested-test-months", type=int, default=1)
    run.add_argument("--minimum-outer-test-periods", type=int, default=48)
    run.add_argument("--seed", type=int, default=20260731)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "rescore":
            result = rescore_existing_model_output(
                args.model_output,
                args.output_dir,
                validation_months=args.validation_months,
                test_months=args.test_months,
                minimum_outer_test_periods=args.minimum_outer_test_periods,
            )
        else:
            result = run_training_ablation(
                args.input_zip,
                args.output_root,
                modes=_parse_modes(args.modes),
                evaluation_months=args.evaluation_months,
                minimum_train_months=args.minimum_train_months,
                inner_validation_months=args.inner_validation_months,
                nested_validation_months=args.nested_validation_months,
                nested_test_months=args.nested_test_months,
                minimum_outer_test_periods=args.minimum_outer_test_periods,
                seed=args.seed,
            )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "build_walk_forward_folds_v25",
    "rescore_existing_model_output",
    "run_training_ablation",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
