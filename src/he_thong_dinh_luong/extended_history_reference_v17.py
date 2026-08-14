"""Run the frozen v15 protocol on a longer monthly history.

This workflow deliberately separates three questions:

* model quality: monthly time-weighted outer-test performance;
* investor experience: terminal wealth and XIRR under periodic contributions;
* execution: T+1 fill, lot size and fees, which are not predictive labels.

The runner fails closed when fewer than the requested 48 monthly outer-test
periods are produced. It never silently accepts the previous 18-month sample.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Mapping, Sequence
from zipfile import BadZipFile, ZipFile

from .contribution_evaluation_v17 import (
    evaluate_archive,
    generate_periodic_contributions,
)

SCHEMA_VERSION = "extended_history_reference_v17"
EXPECTED_MODEL_SCHEMA = "vn_quant_model_lab_upgrade_v15"
EXPECTED_MODEL = "online_rank_ensemble_v1"


def build_model_lab_command(
    *,
    input_zip: Path,
    output_dir: Path,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    minimum_outer_test_periods: int = 48,
) -> tuple[str, ...]:
    if evaluation_months < minimum_outer_test_periods + 6:
        raise ValueError("EXTENDED_HISTORY_EVALUATION_WINDOW_TOO_SMALL")
    if minimum_train_months < 36:
        raise ValueError("EXTENDED_HISTORY_MINIMUM_TRAIN_TOO_SMALL")
    if minimum_outer_test_periods < 48:
        raise ValueError("EXTENDED_HISTORY_REQUIRES_AT_LEAST_48_OUTER_MONTHS")
    return (
        sys.executable,
        "-m",
        "he_thong_dinh_luong.model_lab",
        "--input-zip",
        str(Path(input_zip).resolve()),
        "--output-dir",
        str(Path(output_dir).resolve()),
        "--evaluation-months",
        str(evaluation_months),
        "--minimum-train-months",
        str(minimum_train_months),
        "--inner-validation-months",
        "3",
        "--top-k",
        "10",
        "--turnover-buffer",
        "5",
        "--dnse-broker-buy-fee-bps",
        "0",
        "--dnse-broker-sell-fee-bps",
        "0",
        "--exchange-buy-fee-bps",
        "2.7",
        "--exchange-sell-fee-bps",
        "2.7",
        "--transfer-fee-vnd-per-share",
        "0.3",
        "--transfer-reference-price-vnd",
        "10000",
        "--sell-tax-bps",
        "10",
        "--slippage-bps",
        "5",
        "--stress-slippage-bps",
        "10",
        "--nested-validation-months",
        "6",
        "--nested-test-months",
        "3",
        "--minimum-outer-test-periods",
        str(minimum_outer_test_periods),
        "--replacement-caps",
        "0,1,2,3,4,5",
        "--strict-dependencies",
    )


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"EXTENDED_HISTORY_JSON_OBJECT_REQUIRED:{path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def verify_extended_model_lab(
    output_dir: Path,
    *,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    output = Path(output_dir)
    summary = _read_json(output / "model_lab_summary.json")
    if summary.get("upgrade_schema_version") != EXPECTED_MODEL_SCHEMA:
        raise ValueError("EXTENDED_HISTORY_MODEL_SCHEMA_MISMATCH")
    if summary.get("historical_reference_model") != EXPECTED_MODEL:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_MODEL_CHANGED")
    comparison = _read_csv(output / "nested_model_historical_validation_v15.csv")
    rows = [row for row in comparison if row.get("model") == EXPECTED_MODEL]
    if len(rows) != 1:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_ROW_INVALID")
    row = rows[0]
    period_count = int(float(row.get("outer_test_period_count") or 0))
    if period_count < minimum_outer_test_periods:
        raise ValueError(
            f"EXTENDED_HISTORY_INSUFFICIENT_OUTER_MONTHS:{period_count}"
            f"<{minimum_outer_test_periods}"
        )
    period_rows = [
        item
        for item in _read_csv(output / "nested_model_outer_test_periods_v15.csv")
        if item.get("model") == EXPECTED_MODEL
        and (item.get("cost_scenario") or "BASE") == "BASE"
    ]
    if len(period_rows) != period_count:
        raise ValueError("EXTENDED_HISTORY_PERIOD_COUNT_MISMATCH")
    horizons: list[int] = []
    for item in period_rows:
        signal = date.fromisoformat(str(item["signal_date"]))
        label_end = date.fromisoformat(str(item["label_end"]))
        horizon = (label_end - signal).days
        if horizon < 20 or horizon > 45:
            raise ValueError(
                f"EXTENDED_HISTORY_NOT_MONTHLY_HORIZON:{signal}:{label_end}"
            )
        horizons.append(horizon)
    return {
        "period_count": period_count,
        "evaluation_start": period_rows[0]["signal_date"],
        "evaluation_end": period_rows[-1]["label_end"],
        "minimum_horizon_days": min(horizons),
        "maximum_horizon_days": max(horizons),
        "mean_rank_ic": float(row.get("mean_rank_ic") or 0),
        "positive_rank_ic_ratio": float(row.get("positive_rank_ic_ratio") or 0),
        "base_net_total_return": float(row.get("base_net_total_return") or 0),
        "base_benchmark_total_return": float(
            row.get("base_benchmark_total_return") or 0
        ),
        "base_relative_total_return": float(
            row.get("base_relative_total_return") or 0
        ),
        "stress_relative_total_return": float(
            row.get("stress_relative_total_return") or 0
        ),
        "base_mean_turnover": float(row.get("base_mean_turnover") or 0),
        "gate_passed": str(row.get("gate_passed") or "").lower() == "true",
    }


def _period_range(model_lab_zip: Path) -> tuple[date, date]:
    try:
        with ZipFile(model_lab_zip) as archive:
            rows = [
                dict(row)
                for row in csv.DictReader(
                    StringIO(
                        archive.read(
                            "nested_model_outer_test_periods_v15.csv"
                        ).decode("utf-8-sig")
                    )
                )
            ]
    except BadZipFile as exc:
        raise ValueError("EXTENDED_HISTORY_INVALID_MODEL_ZIP") from exc
    selected = [
        row
        for row in rows
        if row.get("model") == EXPECTED_MODEL
        and (row.get("cost_scenario") or "BASE") == "BASE"
    ]
    if not selected:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_PERIODS_MISSING")
    return (
        min(date.fromisoformat(row["signal_date"]) for row in selected),
        max(date.fromisoformat(row["signal_date"]) for row in selected),
    )


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


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
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    destination = Path(output_root).resolve()
    if not source.is_file():
        raise ValueError("EXTENDED_HISTORY_INPUT_ZIP_NOT_FOUND")
    if destination.exists():
        raise FileExistsError(f"EXTENDED_HISTORY_OUTPUT_EXISTS:{destination}")
    if contribution_amount_vnd <= 0:
        raise ValueError("EXTENDED_HISTORY_CONTRIBUTION_AMOUNT_INVALID")
    intervals = tuple(sorted(set(int(value) for value in contribution_intervals)))
    if not intervals or any(value <= 0 for value in intervals):
        raise ValueError("EXTENDED_HISTORY_CONTRIBUTION_INTERVAL_INVALID")

    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    model_output = staging / "model-lab"
    command = build_model_lab_command(
        input_zip=source,
        output_dir=model_output,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    environment = os.environ.copy()
    environment.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    })
    try:
        completed = subprocess.run(
            command,
            env=environment,
            check=False,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"EXTENDED_HISTORY_MODEL_LAB_FAILED:{completed.returncode}"
            )
        verification = verify_extended_model_lab(
            model_output,
            minimum_outer_test_periods=minimum_outer_test_periods,
        )
        model_zip = model_output / "model_lab_output.zip"
        start, end = _period_range(model_zip)
        scenarios: dict[str, object] = {}
        for interval in intervals:
            events = generate_periodic_contributions(
                start=start,
                end=end,
                amount_vnd=contribution_amount_vnd,
                every_days=interval,
            )
            scenario_dir = staging / f"contribution-every-{interval}-days"
            result = evaluate_archive(
                model_lab_output=model_zip,
                output_dir=scenario_dir,
                contribution_rows=events,
                initial_capital_vnd=initial_capital_vnd,
                minimum_periods=minimum_outer_test_periods,
                model=EXPECTED_MODEL,
            )
            scenarios[f"every_{interval}_days"] = {
                key: value
                for key, value in result.items()
                if key not in {"output_dir", "output_zip"}
            }
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "input_zip_sha256": sha256(source.read_bytes()).hexdigest(),
            "model_protocol": {
                "model": EXPECTED_MODEL,
                "evaluation_months_requested": evaluation_months,
                "minimum_train_months": minimum_train_months,
                "nested_validation_months": 6,
                "nested_test_months": 3,
                "minimum_outer_test_periods": minimum_outer_test_periods,
                "replacement_caps": [0, 1, 2, 3, 4, 5],
                "top_k": 10,
                "t_plus_one_role": "EXECUTION_ONLY_NOT_MODEL_VALIDATION",
            },
            "model_evidence": verification,
            "contribution_amount_vnd": contribution_amount_vnd,
            "contribution_scenarios": scenarios,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(staging / "extended_history_reference_v17.json", report)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        **report,
        "output_root": str(destination),
        "model_lab_output_zip": str(destination / "model-lab" / "model_lab_output.zip"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.extended_history_reference_v17"
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    parser.add_argument("--contribution-amount-vnd", type=int, default=500_000)
    parser.add_argument("--contribution-intervals", default="7,14")
    parser.add_argument("--initial-capital-vnd", type=int, default=0)
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
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "build_model_lab_command",
    "verify_extended_model_lab",
    "run_extended_history",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
