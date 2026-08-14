"""Preflight and run the long monthly reference-model evaluation.

V17 correctly refused to shorten the requested protocol, but the underlying
Model Lab error did not explain the actual input coverage.  V18 inspects the
verified input ZIP before spawning Model Lab and publishes an explicit report
with available monthly dates, valid folds after label purge, and the deficit.

No T+1 observation is used as model-quality evidence.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence

from . import extended_history_reference_v17 as v17
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    Row,
    _load_rows,
    _load_verified_input,
)

SCHEMA_VERSION = "extended_history_reference_v18"
PREFLIGHT_FILE = "extended_history_preflight_v18.json"
REPORT_FILE = "extended_history_reference_v18.json"
NESTED_VALIDATION_MONTHS = 6
INNER_VALIDATION_MONTHS = 3


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


def _valid_fold_dates(
    rows: Sequence[Row],
    *,
    evaluation_months: int,
    minimum_train_months: int,
    inner_validation_months: int = INNER_VALIDATION_MONTHS,
) -> tuple[date, ...]:
    dates = sorted({row.ngay for row in rows})
    if not dates:
        return ()
    candidate_test_dates = dates[-min(evaluation_months, len(dates)) :]
    valid: list[date] = []
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
        validation_dates = set(eligible_dates[-inner_validation_months:])
        validation_start = min(validation_dates)
        train_exists = any(
            row.ngay not in validation_dates
            and row.label_end is not None
            and row.label_end < validation_start
            for row in eligible
        )
        validation_exists = any(row.ngay in validation_dates for row in eligible)
        test_exists = any(row.ngay == test_day for row in rows)
        if train_exists and validation_exists and test_exists:
            valid.append(test_day)
    return tuple(valid)


def inspect_history_rows(
    rows: Sequence[Row],
    *,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    """Return an exact monthly-coverage diagnostic for already loaded rows."""
    v17.build_model_lab_command(
        input_zip=Path("input.zip"),
        output_dir=Path("output"),
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    dates = sorted({row.ngay for row in rows})
    if not dates:
        raise ValueError("EXTENDED_HISTORY_NO_LABELED_MONTHLY_DATES")

    requested_valid = _valid_fold_dates(
        rows,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
    )
    reference_valid = _valid_fold_dates(
        rows,
        evaluation_months=len(dates),
        minimum_train_months=24,
    )
    required_valid_folds = minimum_outer_test_periods + NESTED_VALIDATION_MONTHS
    ready = len(requested_valid) >= required_valid_folds
    if len(dates) <= minimum_train_months:
        blocker = "MINIMUM_TRAIN_EXCEEDS_AVAILABLE_LABELED_MONTHS"
    elif not ready:
        blocker = "NOT_ENOUGH_VALID_FOLDS_AFTER_LABEL_END_PURGE"
    else:
        blocker = ""

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "READY" if ready else "INSUFFICIENT_HISTORY",
        "blocker": blocker,
        "first_labeled_signal_date": dates[0].isoformat(),
        "last_labeled_signal_date": dates[-1].isoformat(),
        "available_labeled_monthly_dates": len(dates),
        "requested_evaluation_months": evaluation_months,
        "requested_minimum_train_months": minimum_train_months,
        "inner_validation_months": INNER_VALIDATION_MONTHS,
        "nested_validation_months": NESTED_VALIDATION_MONTHS,
        "minimum_outer_test_periods": minimum_outer_test_periods,
        "minimum_valid_folds_required_before_nested_holdout": required_valid_folds,
        "requested_protocol_valid_fold_count": len(requested_valid),
        "requested_protocol_first_valid_fold": (
            requested_valid[0].isoformat() if requested_valid else None
        ),
        "requested_protocol_last_valid_fold": (
            requested_valid[-1].isoformat() if requested_valid else None
        ),
        "additional_valid_monthly_folds_needed": max(
            0, required_valid_folds - len(requested_valid)
        ),
        "valid_fold_count_with_24_month_train_over_all_available_dates": len(
            reference_valid
        ),
        "estimated_outer_months_with_24_month_train": max(
            0, len(reference_valid) - NESTED_VALIDATION_MONTHS
        ),
        "recommendation": (
            "RUN_EXTENDED_MODEL_LAB"
            if ready
            else "REBUILD_DAILY_PREDICTION_INPUT_WITH_DEEPER_POINT_IN_TIME_HISTORY"
        ),
        "t_plus_one_role": "EXECUTION_ONLY_NOT_MODEL_VALIDATION",
    }


def inspect_input_history(
    input_zip: Path,
    *,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    blobs, manifest, source_sha = _load_verified_input(source)
    history, _, forward_day = _load_rows(blobs)
    report = inspect_history_rows(
        history,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    report.update({
        "input_zip": str(source),
        "input_zip_sha256": source_sha,
        "forward_signal_date": forward_day.isoformat(),
        "input_manifest_schema_version": str(
            manifest.get("schema_version") or manifest.get("phien_ban_luoc_do") or ""
        ),
    })
    return report


def run_extended_history(
    *,
    input_zip: Path,
    output_root: Path,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    minimum_outer_test_periods: int = 48,
    contribution_amount_vnd: int = 500_000,
    contribution_intervals: Sequence[int] = (7, 14),
    initial_capital_vnd: int = 0,
    preflight_only: bool = False,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    destination = Path(output_root).resolve()
    if destination.exists():
        raise FileExistsError(f"EXTENDED_HISTORY_OUTPUT_EXISTS:{destination}")

    preflight = inspect_input_history(
        source,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    if preflight_only or preflight["status"] != "READY":
        destination.mkdir(parents=True)
        status = (
            "PREFLIGHT_READY"
            if preflight["status"] == "READY"
            else "INSUFFICIENT_HISTORY"
        )
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "preflight": preflight,
            "output_root": str(destination),
            "model_lab_started": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(destination / PREFLIGHT_FILE, preflight)
        _write_json(destination / REPORT_FILE, report)
        return report

    result = v17.run_extended_history(
        input_zip=source,
        output_root=destination,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        contribution_amount_vnd=contribution_amount_vnd,
        contribution_intervals=contribution_intervals,
        initial_capital_vnd=initial_capital_vnd,
    )
    report = {
        **result,
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "preflight": preflight,
        "model_lab_started": True,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(destination / PREFLIGHT_FILE, preflight)
    _write_json(destination / REPORT_FILE, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.extended_history_reference_v18"
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    parser.add_argument("--contribution-amount-vnd", type=int, default=500_000)
    parser.add_argument("--contribution-intervals", default="7,14")
    parser.add_argument("--initial-capital-vnd", type=int, default=0)
    parser.add_argument("--preflight-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    intervals = tuple(
        int(value.strip())
        for value in str(args.contribution_intervals).split(",")
        if value.strip()
    )
    try:
        result = run_extended_history(
            input_zip=args.input_zip,
            output_root=args.output_root,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            contribution_amount_vnd=args.contribution_amount_vnd,
            contribution_intervals=intervals,
            initial_capital_vnd=args.initial_capital_vnd,
            preflight_only=args.preflight_only,
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
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"SUCCESS", "PREFLIGHT_READY"} else 2


__all__ = [
    "SCHEMA_VERSION",
    "PREFLIGHT_FILE",
    "REPORT_FILE",
    "inspect_history_rows",
    "inspect_input_history",
    "run_extended_history",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
