"""Derive the research-grade history required by the locked monthly protocol.

This module does not train a model and does not contact DNSE account APIs.  It
inspects a verified ``daily_prediction_input.zip`` and turns the fold contract
into an explicit historical-data target.  The purpose is to prevent a short
input from failing deep inside Model Lab or being silently relabelled as a long
history evaluation.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date
import json
from pathlib import Path
from typing import Sequence

from .extended_history_reference_v18 import inspect_input_history
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    Row,
    _load_rows,
    _load_verified_input,
)

SCHEMA_VERSION = "historical_data_requirements_v19"
DEFAULT_INNER_VALIDATION_MONTHS = 3
DEFAULT_NESTED_VALIDATION_MONTHS = 6
DEFAULT_WARMUP_CALENDAR_MONTHS = 13


def _month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def _subtract_months(day: date, count: int) -> date:
    index = _month_index(day) - int(count)
    year, zero_month = divmod(index, 12)
    month = zero_month + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def _observed_label_guard_months(rows: Sequence[Row]) -> int:
    lags = [
        _month_index(row.label_end) - _month_index(row.ngay)
        for row in rows
        if row.label_end is not None and row.label_end >= row.ngay
    ]
    return max(1, max(lags, default=1))


def derive_history_requirements(
    rows: Sequence[Row],
    *,
    minimum_train_months: int = 60,
    inner_validation_months: int = DEFAULT_INNER_VALIDATION_MONTHS,
    nested_validation_months: int = DEFAULT_NESTED_VALIDATION_MONTHS,
    minimum_outer_test_periods: int = 48,
    warmup_calendar_months: int = DEFAULT_WARMUP_CALENDAR_MONTHS,
) -> dict[str, object]:
    """Translate the locked fold contract into a dated acquisition target."""
    dates = sorted({row.ngay for row in rows})
    if not dates:
        raise ValueError("HISTORY_REQUIREMENTS_NO_LABELED_DATES")
    if minimum_train_months < 12:
        raise ValueError("HISTORY_REQUIREMENTS_TRAIN_TOO_SHORT")
    if min(inner_validation_months, nested_validation_months) < 1:
        raise ValueError("HISTORY_REQUIREMENTS_VALIDATION_INVALID")
    if minimum_outer_test_periods < 12:
        raise ValueError("HISTORY_REQUIREMENTS_OUTER_TOO_SHORT")
    if warmup_calendar_months < 12:
        raise ValueError("HISTORY_REQUIREMENTS_WARMUP_TOO_SHORT")

    label_guard = _observed_label_guard_months(rows)
    required_valid_folds = nested_validation_months + minimum_outer_test_periods
    minimum_total_labeled_dates = (
        minimum_train_months
        + inner_validation_months
        + label_guard
        + required_valid_folds
    )
    available = len(dates)
    additional = max(0, minimum_total_labeled_dates - available)
    last_labeled = dates[-1]
    required_first_labeled = _subtract_months(
        last_labeled, minimum_total_labeled_dates - 1
    )
    required_price_start = _subtract_months(
        required_first_labeled, warmup_calendar_months
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "READY" if additional == 0 else "DEEPER_HISTORY_REQUIRED",
        "available_labeled_monthly_dates": available,
        "current_first_labeled_signal_date": dates[0].isoformat(),
        "current_last_labeled_signal_date": last_labeled.isoformat(),
        "minimum_train_months": minimum_train_months,
        "inner_validation_months": inner_validation_months,
        "observed_label_purge_guard_months": label_guard,
        "nested_validation_months": nested_validation_months,
        "minimum_outer_test_periods": minimum_outer_test_periods,
        "minimum_valid_folds_required": required_valid_folds,
        "estimated_minimum_total_labeled_monthly_dates": minimum_total_labeled_dates,
        "estimated_additional_labeled_months_needed": additional,
        "estimated_required_first_labeled_signal_date": (
            required_first_labeled.isoformat()
        ),
        "estimated_required_price_history_start_date": required_price_start.isoformat(),
        "required_price_contract": (
            "POINT_IN_TIME_ALL_ELIGIBLE_SYMBOLS_WITH_ADJUSTED_PRICES_OR_"
            "UNADJUSTED_PRICES_PLUS_PIT_CORPORATE_ACTIONS"
        ),
        "required_universe_contract": (
            "POINT_IN_TIME_MEMBERSHIP_OR_DYNAMIC_LIQUIDITY_UNIVERSE_BUILT_"
            "ONLY_FROM_INFORMATION_AVAILABLE_AT_EACH_SIGNAL_DATE"
        ),
        "current_universe_backfill_allowed_for_research_gate": False,
        "t_plus_one_role": "EXECUTION_ONLY_NOT_MODEL_VALIDATION",
        "recommendation": (
            "RUN_LOCKED_EXTENDED_MODEL_LAB"
            if additional == 0
            else "ACQUIRE_AND_BUILD_DEEPER_POINT_IN_TIME_RESEARCH_INPUT"
        ),
    }


def inspect_input_requirements(
    input_zip: Path,
    *,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    blobs, manifest, source_sha = _load_verified_input(source)
    rows, _, forward_day = _load_rows(blobs)
    v18 = inspect_input_history(
        source,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    requirements = derive_history_requirements(
        rows,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": requirements["status"],
        "input_zip": str(source),
        "input_zip_sha256": source_sha,
        "input_manifest_schema_version": str(
            manifest.get("schema_version")
            or manifest.get("phien_ban_luoc_do")
            or ""
        ),
        "forward_signal_date": forward_day.isoformat(),
        "v18_preflight": v18,
        "requirements": requirements,
        "model_lab_started": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.historical_data_requirements_v19"
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_input_requirements(
            args.input_zip,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
        )
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        _write_json(args.output_json, result)
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
    return 0 if result.get("status") == "READY" else 2


__all__ = [
    "SCHEMA_VERSION",
    "derive_history_requirements",
    "inspect_input_requirements",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
