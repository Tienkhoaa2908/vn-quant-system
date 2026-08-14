"""Publish long-history Model Lab outcomes without forcing the frozen v15 winner.

V17 treated any change from ``online_rank_ensemble_v1`` as an execution error.
That is incorrect for a longer out-of-sample experiment: a successful run may
legitimately conclude that no candidate passes the historical reference gate.
V23 preserves that negative result and its artifacts while keeping every live
capital and automatic-order flag disabled.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Mapping, Sequence

from .contribution_evaluation_v17 import (
    evaluate_archive,
    generate_periodic_contributions,
)
from . import extended_history_reference_v17 as v17
from . import extended_history_reference_v18 as v18

SCHEMA_VERSION = "extended_history_reference_v23"
REPORT_FILE = "extended_history_reference_v23.json"
PREFLIGHT_FILE = v18.PREFLIGHT_FILE
NO_MODEL_APPROVED = "NO_MODEL_APPROVED"
SUCCESS_STATUSES = {
    "SUCCESS_APPROVED_REFERENCE",
    "SUCCESS_NO_MODEL_APPROVED",
    "PREFLIGHT_READY",
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


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"EXTENDED_HISTORY_JSON_OBJECT_REQUIRED:{path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() == "true"


def _period_rows(
    output_dir: Path,
    *,
    model: str,
) -> list[dict[str, str]]:
    rows = _read_csv(Path(output_dir) / "nested_model_outer_test_periods_v15.csv")
    return [
        row
        for row in rows
        if row.get("model") == model
        and (row.get("cost_scenario") or "BASE") == "BASE"
    ]


def _verify_period_horizons(rows: Sequence[Mapping[str, str]]) -> dict[str, object]:
    if not rows:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_PERIODS_MISSING")
    ordered = sorted(rows, key=lambda row: str(row.get("signal_date") or ""))
    horizons: list[int] = []
    for row in ordered:
        signal = date.fromisoformat(str(row["signal_date"]))
        label_end = date.fromisoformat(str(row["label_end"]))
        horizon = (label_end - signal).days
        if horizon < 20 or horizon > 45:
            raise ValueError(
                f"EXTENDED_HISTORY_NOT_MONTHLY_HORIZON:{signal}:{label_end}"
            )
        horizons.append(horizon)
    return {
        "evaluation_start": ordered[0]["signal_date"],
        "evaluation_end": ordered[-1]["label_end"],
        "minimum_horizon_days": min(horizons),
        "maximum_horizon_days": max(horizons),
    }


def verify_model_lab_outcome(
    output_dir: Path,
    *,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    """Verify a successful Model Lab run, including a valid negative outcome."""
    output = Path(output_dir)
    summary = _read_json(output / "model_lab_summary.json")
    if summary.get("upgrade_schema_version") != v17.EXPECTED_MODEL_SCHEMA:
        raise ValueError("EXTENDED_HISTORY_MODEL_SCHEMA_MISMATCH")

    model_zip = output / "model_lab_output.zip"
    if not model_zip.is_file() or model_zip.stat().st_size <= 0:
        raise ValueError("EXTENDED_HISTORY_MODEL_ZIP_MISSING")

    comparison = _read_csv(output / "nested_model_historical_validation_v15.csv")
    if not comparison:
        raise ValueError("EXTENDED_HISTORY_MODEL_COMPARISON_EMPTY")

    reference_model = str(summary.get("historical_reference_model") or "")
    gate_passed = _bool(summary.get("historical_reference_gate_passed"))
    if gate_passed and reference_model == NO_MODEL_APPROVED:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_STATE_INCONSISTENT")
    if not gate_passed and reference_model != NO_MODEL_APPROVED:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_STATE_INCONSISTENT")

    period_counts = {
        str(row.get("model") or ""): int(
            float(row.get("outer_test_period_count") or 0)
        )
        for row in comparison
        if str(row.get("model") or "")
    }
    maximum_period_count = max(period_counts.values(), default=0)
    if maximum_period_count < minimum_outer_test_periods:
        raise ValueError(
            f"EXTENDED_HISTORY_INSUFFICIENT_OUTER_MONTHS:{maximum_period_count}"
            f"<{minimum_outer_test_periods}"
        )

    models_success = [str(value) for value in summary.get("models_success", [])]
    models_failed = summary.get("models_skipped_or_failed", {})
    if not isinstance(models_failed, dict):
        models_failed = {}

    base: dict[str, object] = {
        "model_lab_status": str(summary.get("status") or ""),
        "evidence_grade": str(summary.get("evidence_grade") or ""),
        "historical_reference_status": str(
            summary.get("historical_reference_status") or ""
        ),
        "historical_reference_model": reference_model,
        "historical_reference_gate_passed": gate_passed,
        "fold_count": int(summary.get("fold_count") or 0),
        "maximum_outer_test_period_count": maximum_period_count,
        "minimum_outer_test_periods_required": minimum_outer_test_periods,
        "models_success": models_success,
        "models_skipped_or_failed": models_failed,
        "positive_evidence_models": [
            str(value) for value in summary.get("positive_evidence_models", [])
        ],
        "predictive_reference_status": str(
            summary.get("predictive_reference_status") or ""
        ),
        "reference_diagnostic_status": str(
            summary.get("reference_diagnostic_status") or ""
        ),
        "future_holdout_status": str(summary.get("future_holdout_status") or ""),
        "model_lab_output_zip_sha256": sha256(model_zip.read_bytes()).hexdigest(),
        "actionable": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }

    if reference_model == NO_MODEL_APPROVED:
        candidates = [
            {
                "model": str(row.get("model") or ""),
                "status": str(row.get("status") or ""),
                "outer_test_period_count": int(
                    float(row.get("outer_test_period_count") or 0)
                ),
                "mean_rank_ic": float(row.get("mean_rank_ic") or 0),
                "positive_rank_ic_ratio": float(
                    row.get("positive_rank_ic_ratio") or 0
                ),
                "base_relative_total_return": float(
                    row.get("base_relative_total_return") or 0
                ),
                "stress_relative_total_return": float(
                    row.get("stress_relative_total_return") or 0
                ),
                "base_mean_turnover": float(row.get("base_mean_turnover") or 0),
                "failed_gate_count": int(float(row.get("failed_gate_count") or 0)),
                "failed_gates": str(row.get("failed_gates") or ""),
                "gate_passed": _bool(row.get("gate_passed")),
            }
            for row in comparison
        ]
        return {
            **base,
            "outcome": "NO_MODEL_APPROVED",
            "status": "SUCCESS_NO_MODEL_APPROVED",
            "candidate_diagnostics": candidates,
            "contribution_evaluation_allowed": False,
            "contribution_skip_reason": "NO_APPROVED_REFERENCE_MODEL",
        }

    rows = [row for row in comparison if row.get("model") == reference_model]
    if len(rows) != 1:
        raise ValueError("EXTENDED_HISTORY_REFERENCE_ROW_INVALID")
    row = rows[0]
    period_count = int(float(row.get("outer_test_period_count") or 0))
    if period_count < minimum_outer_test_periods:
        raise ValueError(
            f"EXTENDED_HISTORY_INSUFFICIENT_OUTER_MONTHS:{period_count}"
            f"<{minimum_outer_test_periods}"
        )
    periods = _period_rows(output, model=reference_model)
    if len(periods) != period_count:
        raise ValueError("EXTENDED_HISTORY_PERIOD_COUNT_MISMATCH")
    horizon = _verify_period_horizons(periods)
    return {
        **base,
        **horizon,
        "outcome": "APPROVED_REFERENCE",
        "status": "SUCCESS_APPROVED_REFERENCE",
        "period_count": period_count,
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
        "contribution_evaluation_allowed": True,
    }


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
    if contribution_amount_vnd <= 0:
        raise ValueError("EXTENDED_HISTORY_CONTRIBUTION_AMOUNT_INVALID")
    intervals = tuple(sorted(set(int(value) for value in contribution_intervals)))
    if not intervals or any(value <= 0 for value in intervals):
        raise ValueError("EXTENDED_HISTORY_CONTRIBUTION_INTERVAL_INVALID")

    preflight = v18.inspect_input_history(
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
            "model_lab_started": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(destination / PREFLIGHT_FILE, preflight)
        _write_json(destination / REPORT_FILE, report)
        return report

    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    model_output = staging / "model-lab"
    command = v17.build_model_lab_command(
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
        completed = subprocess.run(command, env=environment, check=False, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"EXTENDED_HISTORY_MODEL_LAB_FAILED:{completed.returncode}"
            )
        outcome = verify_model_lab_outcome(
            model_output,
            minimum_outer_test_periods=minimum_outer_test_periods,
        )
        scenarios: dict[str, object] = {}
        if outcome["outcome"] == "APPROVED_REFERENCE":
            model = str(outcome["historical_reference_model"])
            start = date.fromisoformat(str(outcome["evaluation_start"]))
            end = date.fromisoformat(
                max(
                    row["signal_date"]
                    for row in _period_rows(model_output, model=model)
                )
            )
            model_zip = model_output / "model_lab_output.zip"
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
                    model=model,
                )
                scenarios[f"every_{interval}_days"] = {
                    key: value
                    for key, value in result.items()
                    if key not in {"output_dir", "output_zip"}
                }

        report = {
            "schema_version": SCHEMA_VERSION,
            "status": outcome["status"],
            "input_zip_sha256": sha256(source.read_bytes()).hexdigest(),
            "preflight": preflight,
            "model_lab_started": True,
            "model_protocol": {
                "evaluation_months_requested": evaluation_months,
                "minimum_train_months": minimum_train_months,
                "nested_validation_months": 6,
                "nested_test_months": 3,
                "minimum_outer_test_periods": minimum_outer_test_periods,
                "replacement_caps": [0, 1, 2, 3, 4, 5],
                "top_k": 10,
                "t_plus_one_role": "EXECUTION_ONLY_NOT_MODEL_VALIDATION",
            },
            "model_outcome": outcome,
            "contribution_amount_vnd": contribution_amount_vnd,
            "contribution_scenarios": scenarios,
            "technical_validation_only": True,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(staging / PREFLIGHT_FILE, preflight)
        _write_json(staging / REPORT_FILE, report)
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
        prog="python -m he_thong_dinh_luong.extended_history_reference_v23"
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
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in SUCCESS_STATUSES else 2


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "verify_model_lab_outcome",
    "run_extended_history",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
