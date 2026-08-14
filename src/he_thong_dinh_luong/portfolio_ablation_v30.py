"""V30 portfolio-policy ablation for the V29 predictive challenger.

V30 consumes the immutable V29 artifact instead of retraining predictive models.
It verifies the V29 lineage and predictive gate, then evaluates the frozen C3
baseline and the passing bottom-tail logistic challenger across fixed portfolio
breadths. Within each breadth, only the voluntary replacement cap is selected
from the strictly-prior validation block by the V15 evaluator.

This remains a post-selection sensitivity analysis. It can freeze a portfolio
policy for paper/future-holdout observation, but it cannot establish an
independent holdout, approve research quality, approve live capital, or send
orders.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
from statistics import fmean
from typing import Mapping, Sequence
import zipfile

from . import model_lab_upgrade_v15 as v15
from . import predictive_target_lab_v29 as v29
from .model_lab_upgrade_v13 import DEFAULT_REPLACEMENT_CAPS
from .model_policy_ablation_v25 import _cost_from_summary

SCHEMA_VERSION = "portfolio_ablation_v30"
REPORT_FILE = "portfolio_ablation_v30.json"
FROZEN_MODEL = v29.FROZEN_MODEL
CHALLENGER_MODEL = v29.BOTTOM_MODEL
DEFAULT_BREADTHS = (10, 15, 20, 30)
REQUIRED_V29_FILES = {
    v29.REPORT_FILE,
    "predictions_v29.csv",
    "decision_gates_v29.csv",
    "hyperparameter_selection_v29.csv",
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"V30_JSON_OBJECT_REQUIRED:{Path(path).name}")
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


def _read_csv_bytes(value: bytes) -> list[dict[str, str]]:
    with io.StringIO(value.decode("utf-8-sig"), newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and not fields:
        raise ValueError("V30_CSV_FIELDS_REQUIRED")
    if fields is None:
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    else:
        fieldnames = list(fields)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _safe_member_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"V30_UNSAFE_V29_MEMBER:{name}")
    basename = path.name
    if not basename:
        raise ValueError(f"V30_EMPTY_V29_MEMBER:{name}")
    return basename


def _load_v29_artifact(
    artifact_zip: Path,
    *,
    expected_artifact_sha256: str | None = None,
    expected_input_sha256: str | None = None,
) -> tuple[
    dict[str, object],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, object],
]:
    source = Path(artifact_zip).resolve()
    if not source.is_file():
        raise ValueError("V30_V29_ARTIFACT_NOT_FOUND")
    artifact_sha = _sha256(source)
    if expected_artifact_sha256 and artifact_sha != expected_artifact_sha256:
        raise ValueError("V30_V29_ARTIFACT_SHA256_MISMATCH")

    members: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = _safe_member_basename(info.filename)
            if basename in members:
                raise ValueError(f"V30_DUPLICATE_V29_BASENAME:{basename}")
            members[basename] = (info.filename, archive.read(info))

    missing = REQUIRED_V29_FILES - set(members)
    if missing:
        raise ValueError(
            "V30_V29_FILES_MISSING:" + "|".join(sorted(missing))
        )
    report_bytes = members[v29.REPORT_FILE][1]
    report = json.loads(report_bytes.decode("utf-8-sig"))
    if not isinstance(report, dict):
        raise ValueError("V30_V29_REPORT_OBJECT_REQUIRED")
    predictions_bytes = members["predictions_v29.csv"][1]
    decisions_bytes = members["decision_gates_v29.csv"][1]
    selection_bytes = members["hyperparameter_selection_v29.csv"][1]
    predictions = _read_csv_bytes(predictions_bytes)
    decisions = _read_csv_bytes(decisions_bytes)
    selections = _read_csv_bytes(selection_bytes)

    _validate_v29_evidence(
        report,
        predictions,
        decisions,
        expected_input_sha256=expected_input_sha256,
    )
    selection_columns = set(selections[0]) if selections else set()
    required_logit_columns = {
        "selected_c",
        "validation_bottom20_recall",
        "validation_mean_rank_ic",
    }
    metadata = {
        "artifact_zip": str(source),
        "artifact_zip_sha256": artifact_sha,
        "report_member": members[v29.REPORT_FILE][0],
        "report_sha256": _bytes_sha256(report_bytes),
        "predictions_member": members["predictions_v29.csv"][0],
        "predictions_sha256": _bytes_sha256(predictions_bytes),
        "decision_gates_sha256": _bytes_sha256(decisions_bytes),
        "hyperparameter_selection_sha256": _bytes_sha256(selection_bytes),
        "hyperparameter_selection_audit_complete": (
            required_logit_columns <= selection_columns
        ),
        "missing_logit_hyperparameter_columns": sorted(
            required_logit_columns - selection_columns
        ),
    }
    return report, predictions, selections, metadata


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _finite(value: object, *, name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"V30_MISSING_NUMERIC:{name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V30_NON_FINITE:{name}")
    return number


def _validate_v29_evidence(
    report: Mapping[str, object],
    predictions: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    *,
    expected_input_sha256: str | None,
) -> None:
    if report.get("schema_version") != v29.SCHEMA_VERSION:
        raise ValueError("V30_V29_SCHEMA_MISMATCH")
    if report.get("status") != "SUCCESS":
        raise ValueError("V30_V29_STATUS_NOT_SUCCESS")
    if report.get("recommendation") != (
        "PROMOTE_PASSING_CHALLENGER_TO_V30_PORTFOLIO_ABLATION"
    ):
        raise ValueError("V30_V29_RECOMMENDATION_NOT_PROMOTABLE")
    passing = tuple(str(value) for value in report.get("passing_models", []))
    if passing != (CHALLENGER_MODEL,):
        raise ValueError("V30_V29_PASSING_MODEL_SET_UNEXPECTED")
    if bool(report.get("frozen_v28_candidate_modified")):
        raise ValueError("V30_FROZEN_V28_WAS_MODIFIED")
    if bool(report.get("future_holdout_clock_reset")):
        raise ValueError("V30_FUTURE_HOLDOUT_CLOCK_RESET")
    if bool(report.get("research_eligible")):
        raise ValueError("V30_V29_RESEARCH_ELIGIBILITY_UNEXPECTED")
    if bool(report.get("live_capital_approved")):
        raise ValueError("V30_V29_LIVE_CAPITAL_UNEXPECTED")
    if bool(report.get("automatic_live_orders_allowed")):
        raise ValueError("V30_V29_AUTOMATIC_ORDER_UNEXPECTED")
    if expected_input_sha256 and report.get("input_zip_sha256") != expected_input_sha256:
        raise ValueError("V30_V29_INPUT_SHA256_MISMATCH")

    decision_by_model = {
        str(row.get("model") or ""): row for row in decisions
    }
    challenger_decision = decision_by_model.get(CHALLENGER_MODEL)
    if challenger_decision is None or not _truthy(
        challenger_decision.get("predictive_challenger_gate_passed")
    ):
        raise ValueError("V30_V29_CHALLENGER_GATE_NOT_PASSED")

    required_models = {FROZEN_MODEL, CHALLENGER_MODEL}
    seen_models = {str(row.get("model") or "") for row in predictions}
    if not required_models <= seen_models:
        raise ValueError("V30_V29_REQUIRED_PREDICTIONS_MISSING")
    filtered = [
        row for row in predictions
        if str(row.get("model") or "") in required_models
    ]
    keys: set[tuple[str, str, str]] = set()
    symbols_by_model_day: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in filtered:
        model = str(row.get("model") or "")
        day = str(row.get("test_date") or "")
        symbol = str(row.get("symbol") or "")
        if not model or not day or not symbol:
            raise ValueError("V30_V29_PREDICTION_KEY_MISSING")
        key = (model, day, symbol)
        if key in keys:
            raise ValueError("V30_V29_DUPLICATE_PREDICTION")
        keys.add(key)
        symbols_by_model_day[(model, day)].add(symbol)
        _finite(row.get("score"), name="score")
        _finite(row.get("rank"), name="rank")
        _finite(row.get("stock_return"), name="stock_return")
        _finite(row.get("benchmark_return"), name="benchmark_return")
        _finite(row.get("relative_return"), name="relative_return")

    dates = sorted({day for _, day in symbols_by_model_day})
    expected_folds = int(report.get("walk_forward_fold_count", 0) or 0)
    if len(dates) != expected_folds:
        raise ValueError("V30_V29_FOLD_COUNT_MISMATCH")
    for day in dates:
        frozen_symbols = symbols_by_model_day[(FROZEN_MODEL, day)]
        challenger_symbols = symbols_by_model_day[(CHALLENGER_MODEL, day)]
        if frozen_symbols != challenger_symbols:
            raise ValueError(f"V30_V29_SYMBOL_SET_MISMATCH:{day}")


def _normalize_breadths(values: Sequence[int]) -> tuple[int, ...]:
    breadths = tuple(sorted(set(int(value) for value in values)))
    if not breadths or any(value < 5 or value > 50 for value in breadths):
        raise ValueError("V30_INVALID_BREADTHS")
    if 10 not in breadths:
        raise ValueError("V30_BREADTH_10_REQUIRED_FOR_FROZEN_BASELINE")
    return breadths


def _normalize_caps(values: Sequence[int], *, maximum_breadth: int) -> tuple[int, ...]:
    caps = tuple(sorted(set(int(value) for value in values)))
    if not caps or any(value < 0 or value > maximum_breadth for value in caps):
        raise ValueError("V30_INVALID_REPLACEMENT_CAPS")
    return caps


def _portfolio_evaluations(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
    replacement_caps: Sequence[int],
    cost: object,
    validation_months: int,
    test_months: int,
    minimum_outer_test_periods: int,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    summary_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    stress_rows: list[dict[str, object]] = []
    compact: dict[str, object] = {}
    for breadth in _normalize_breadths(breadths):
        evaluation = v15.model_wise_nested_evaluation(
            prediction_rows,
            top_k=breadth,
            replacement_caps=replacement_caps,
            candidate_models=(FROZEN_MODEL, CHALLENGER_MODEL),
            validation_months=validation_months,
            test_months=test_months,
            minimum_outer_test_periods=minimum_outer_test_periods,
            cost=cost,
        )
        for source_name, destination in (
            ("summary_rows", summary_rows),
            ("selection_rows", selection_rows),
            ("outer_rows", outer_rows),
            ("stress_rows", stress_rows),
        ):
            for row in evaluation.get(source_name, []):
                destination.append({"breadth": breadth, **dict(row)})
        compact[str(breadth)] = {
            "status": evaluation.get("status"),
            "historical_reference_model": evaluation.get(
                "historical_reference_model"
            ),
            "historical_reference_gate_passed": evaluation.get(
                "historical_reference_gate_passed"
            ),
            "model_details": evaluation.get("model_details", {}),
        }
    return summary_rows, selection_rows, outer_rows, stress_rows, compact


def _period_map(
    rows: Sequence[Mapping[str, object]],
    *,
    breadth: int,
    model: str,
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for row in rows:
        if int(row.get("breadth", 0) or 0) != breadth:
            continue
        if str(row.get("model") or "") != model:
            continue
        day = str(row.get("signal_date") or "")
        if not day:
            raise ValueError("V30_OUTER_SIGNAL_DATE_MISSING")
        if day in result:
            raise ValueError(f"V30_DUPLICATE_OUTER_PERIOD:{model}:{breadth}:{day}")
        result[day] = row
    return result


def _paired_delta_stats(
    challenger_rows: Mapping[str, Mapping[str, object]],
    baseline_rows: Mapping[str, Mapping[str, object]],
    *,
    repetitions: int,
    block_months: int,
    seed: int,
) -> dict[str, object]:
    dates = sorted(set(challenger_rows) & set(baseline_rows))
    if len(dates) < 3:
        raise ValueError("V30_TOO_FEW_PAIRED_PORTFOLIO_PERIODS")
    deltas = [
        _finite(
            challenger_rows[day].get("net_excess_return"),
            name="net_excess_return",
        )
        - _finite(
            baseline_rows[day].get("net_excess_return"),
            name="net_excess_return",
        )
        for day in dates
    ]
    nw = v29._newey_west_mean(deltas, lag=3)
    bootstrap = v29._moving_block_bootstrap(
        deltas,
        block_length=block_months,
        repetitions=repetitions,
        seed=seed,
    )
    return {
        "paired_period_count": len(dates),
        "mean_net_excess_delta": nw["mean"],
        "newey_west_delta_standard_error": nw["standard_error"],
        "newey_west_delta_t_stat": nw["t_stat"],
        "delta_one_sided_p_value": nw["one_sided_p_value"],
        "bootstrap_delta_lower_90": bootstrap["lower_90"],
        "bootstrap_delta_upper_90": bootstrap["upper_90"],
        "bootstrap_probability_delta_positive": bootstrap[
            "probability_mean_positive"
        ],
        "leave_best_3_mean_net_excess_delta": v29._leave_best_mean(deltas, 3),
    }


def _paired_comparisons(
    outer_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
    bootstrap_repetitions: int,
    bootstrap_block_months: int,
    seed: int,
) -> list[dict[str, object]]:
    baseline_top10 = _period_map(
        outer_rows,
        breadth=10,
        model=FROZEN_MODEL,
    )
    output: list[dict[str, object]] = []
    for breadth in _normalize_breadths(breadths):
        challenger = _period_map(
            outer_rows,
            breadth=breadth,
            model=CHALLENGER_MODEL,
        )
        same_breadth = _period_map(
            outer_rows,
            breadth=breadth,
            model=FROZEN_MODEL,
        )
        for baseline_name, baseline_breadth, baseline_rows, offset in (
            ("SAME_BREADTH_C3", breadth, same_breadth, 0),
            ("FROZEN_C3_TOP10", 10, baseline_top10, 1000),
        ):
            stats = _paired_delta_stats(
                challenger,
                baseline_rows,
                repetitions=bootstrap_repetitions,
                block_months=bootstrap_block_months,
                seed=seed + offset + breadth,
            )
            output.append({
                "challenger_model": CHALLENGER_MODEL,
                "challenger_breadth": breadth,
                "baseline_model": FROZEN_MODEL,
                "baseline_breadth": baseline_breadth,
                "comparison": baseline_name,
                **stats,
            })
    return output


def _summary_index(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[int, str], Mapping[str, object]]:
    return {
        (
            int(row.get("breadth", 0) or 0),
            str(row.get("model") or ""),
        ): row
        for row in rows
    }


def _comparison_index(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[int, str], Mapping[str, object]]:
    return {
        (
            int(row.get("challenger_breadth", 0) or 0),
            str(row.get("comparison") or ""),
        ): row
        for row in rows
    }


def _decision_rows(
    summary_rows: Sequence[Mapping[str, object]],
    comparison_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
) -> tuple[list[dict[str, object]], str, list[int], list[tuple[int, int]]]:
    summaries = _summary_index(summary_rows)
    comparisons = _comparison_index(comparison_rows)
    frozen_top10 = summaries.get((10, FROZEN_MODEL))
    if frozen_top10 is None:
        raise ValueError("V30_FROZEN_TOP10_SUMMARY_MISSING")
    frozen_worst_relative = min(
        _finite(
            frozen_top10.get("base_relative_total_return"),
            name="base_relative_total_return",
        ),
        _finite(
            frozen_top10.get("stress_relative_total_return"),
            name="stress_relative_total_return",
        ),
    )

    decisions: list[dict[str, object]] = []
    for breadth in _normalize_breadths(breadths):
        row = summaries.get((breadth, CHALLENGER_MODEL))
        same = summaries.get((breadth, FROZEN_MODEL))
        paired_same = comparisons.get((breadth, "SAME_BREADTH_C3"))
        paired_top10 = comparisons.get((breadth, "FROZEN_C3_TOP10"))
        if row is None or same is None or paired_same is None or paired_top10 is None:
            raise ValueError(f"V30_PORTFOLIO_EVIDENCE_MISSING:{breadth}")
        challenger_worst_relative = min(
            _finite(
                row.get("base_relative_total_return"),
                name="base_relative_total_return",
            ),
            _finite(
                row.get("stress_relative_total_return"),
                name="stress_relative_total_return",
            ),
        )
        same_worst_relative = min(
            _finite(
                same.get("base_relative_total_return"),
                name="base_relative_total_return",
            ),
            _finite(
                same.get("stress_relative_total_return"),
                name="stress_relative_total_return",
            ),
        )
        gates = {
            "v29_predictive_gate_passed": True,
            "v15_portfolio_gate_passed": _truthy(row.get("gate_passed")),
            "base_relative_total_return_positive": _finite(
                row.get("base_relative_total_return"),
                name="base_relative_total_return",
            ) > 0.0,
            "stress_relative_total_return_positive": _finite(
                row.get("stress_relative_total_return"),
                name="stress_relative_total_return",
            ) > 0.0,
            "positive_monthly_net_excess_at_least_half": _finite(
                row.get("base_positive_net_excess_ratio"),
                name="base_positive_net_excess_ratio",
            ) >= 0.50,
            "mean_turnover_at_most_half": _finite(
                row.get("base_mean_turnover"),
                name="base_mean_turnover",
            ) <= 0.50,
            "leave_best_month_out_relative_positive": _finite(
                row.get("base_leave_best_period_out_relative_total_return"),
                name="base_leave_best_period_out_relative_total_return",
            ) > 0.0,
            "worst_case_not_materially_below_same_breadth_c3": (
                challenger_worst_relative >= same_worst_relative - 0.02
            ),
            "worst_case_not_materially_below_frozen_c3_top10": (
                challenger_worst_relative >= frozen_worst_relative - 0.02
            ),
            "paired_probability_vs_same_breadth_c3_at_least_070": _finite(
                paired_same.get("bootstrap_probability_delta_positive"),
                name="bootstrap_probability_delta_positive",
            ) >= 0.70,
            "paired_probability_vs_frozen_top10_at_least_070": _finite(
                paired_top10.get("bootstrap_probability_delta_positive"),
                name="bootstrap_probability_delta_positive",
            ) >= 0.70,
            "leave_best_3_delta_vs_frozen_top10_non_negative": _finite(
                paired_top10.get("leave_best_3_mean_net_excess_delta"),
                name="leave_best_3_mean_net_excess_delta",
            ) >= 0.0,
        }
        passed = all(gates.values())
        decisions.append({
            "model": CHALLENGER_MODEL,
            "breadth": breadth,
            "challenger_worst_case_relative_total_return": (
                challenger_worst_relative
            ),
            "same_breadth_c3_worst_case_relative_total_return": (
                same_worst_relative
            ),
            "frozen_c3_top10_worst_case_relative_total_return": (
                frozen_worst_relative
            ),
            **gates,
            "v30_portfolio_gate_passed": passed,
            "failed_v30_gates": "|".join(
                name for name, value in gates.items() if not value
            ),
            "independent_holdout": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "actionable": False,
        })

    passing = sorted(
        int(row["breadth"])
        for row in decisions
        if bool(row["v30_portfolio_gate_passed"])
    )
    configured = list(_normalize_breadths(breadths))
    adjacent: list[tuple[int, int]] = []
    passing_set = set(passing)
    for left, right in zip(configured, configured[1:]):
        if left in passing_set and right in passing_set:
            adjacent.append((left, right))
    if adjacent:
        recommendation = "FREEZE_V29_LOGIT_POLICY_FOR_FUTURE_HOLDOUT"
    elif passing:
        recommendation = "KEEP_SINGLE_V30_POLICY_AS_PAPER_DIAGNOSTIC_ONLY"
    else:
        recommendation = "KEEP_V29_MODEL_REDESIGN_PORTFOLIO_POLICY"
    return decisions, recommendation, passing, adjacent


def _parse_int_list(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def run_v30(
    *,
    v29_artifact_zip: Path,
    model_output: Path,
    output_dir: Path,
    expected_v29_sha256: str | None = None,
    expected_input_sha256: str | None = None,
    breadths: Sequence[int] = DEFAULT_BREADTHS,
    replacement_caps: Sequence[int] = DEFAULT_REPLACEMENT_CAPS,
    validation_months: int = 6,
    test_months: int = 3,
    minimum_outer_test_periods: int = 48,
    bootstrap_repetitions: int = 2000,
    bootstrap_block_months: int = 3,
    seed: int = 20260802,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V30_OUTPUT_EXISTS:{destination}")
    normalized_breadths = _normalize_breadths(breadths)
    normalized_caps = _normalize_caps(
        replacement_caps,
        maximum_breadth=min(normalized_breadths),
    )
    if validation_months < 3 or test_months < 1:
        raise ValueError("V30_NESTED_WINDOW_INVALID")
    if minimum_outer_test_periods < 12:
        raise ValueError("V30_MINIMUM_OUTER_TEST_TOO_SMALL")
    if bootstrap_repetitions < 100 or bootstrap_block_months < 1:
        raise ValueError("V30_BOOTSTRAP_CONFIG_INVALID")

    v29_report, predictions, selections, artifact_metadata = _load_v29_artifact(
        v29_artifact_zip,
        expected_artifact_sha256=expected_v29_sha256,
        expected_input_sha256=expected_input_sha256,
    )
    filtered_predictions = [
        dict(row)
        for row in predictions
        if str(row.get("model") or "") in {FROZEN_MODEL, CHALLENGER_MODEL}
    ]

    model_root = Path(model_output).resolve()
    summary_path = model_root / "model_lab_summary.json"
    if not summary_path.is_file():
        raise ValueError("V30_MODEL_SUMMARY_NOT_FOUND")
    model_summary = _read_json(summary_path)
    _, cost = _cost_from_summary(model_summary)

    (
        portfolio_rows,
        policy_rows,
        outer_rows,
        stress_rows,
        compact_results,
    ) = _portfolio_evaluations(
        filtered_predictions,
        breadths=normalized_breadths,
        replacement_caps=normalized_caps,
        cost=cost,
        validation_months=validation_months,
        test_months=test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    paired_rows = _paired_comparisons(
        outer_rows,
        breadths=normalized_breadths,
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_months=bootstrap_block_months,
        seed=seed,
    )
    decision_rows, recommendation, passing_breadths, adjacent_pairs = (
        _decision_rows(
            portfolio_rows,
            paired_rows,
            breadths=normalized_breadths,
        )
    )

    destination.mkdir(parents=True)
    try:
        outputs = {
            "portfolio_comparison_v30.csv": portfolio_rows,
            "policy_selection_v30.csv": policy_rows,
            "outer_test_periods_v30.csv": outer_rows,
            "outer_test_stress_periods_v30.csv": stress_rows,
            "paired_portfolio_comparison_v30.csv": paired_rows,
            "decision_gates_v30.csv": decision_rows,
        }
        for name, rows in outputs.items():
            _write_csv(destination / name, rows)
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "experiment": (
                "POST_V29_FIXED_BREADTH_AND_TURNOVER_POLICY_ABLATION"
            ),
            "source_v29": artifact_metadata,
            "source_v29_report_schema": v29_report.get("schema_version"),
            "source_v29_input_zip_sha256": v29_report.get(
                "input_zip_sha256"
            ),
            "source_v29_passing_models": v29_report.get("passing_models"),
            "source_v29_selection_row_count": len(selections),
            "source_model_output": str(model_root),
            "source_model_summary_sha256": _sha256(summary_path),
            "candidate_models": [FROZEN_MODEL, CHALLENGER_MODEL],
            "breadths": list(normalized_breadths),
            "replacement_caps": list(normalized_caps),
            "nested_validation_months": validation_months,
            "nested_test_months": test_months,
            "minimum_outer_test_periods": minimum_outer_test_periods,
            "bootstrap_repetitions": bootstrap_repetitions,
            "bootstrap_block_months": bootstrap_block_months,
            "portfolio_results": compact_results,
            "passing_breadths": passing_breadths,
            "adjacent_passing_breadth_pairs": [
                list(pair) for pair in adjacent_pairs
            ],
            "recommendation": recommendation,
            "policy_freeze_is_for_future_holdout_only": (
                recommendation
                == "FREEZE_V29_LOGIT_POLICY_FOR_FUTURE_HOLDOUT"
            ),
            "predictive_models_retrained": False,
            "v29_predictive_gate_reused": True,
            "replacement_cap_selected_only_from_prior_validation": True,
            "breadth_selected_after_outer_review": True,
            "post_selection_sensitivity_analysis": True,
            "future_holdout_clock_reset": False,
            "independent_holdout": False,
            "technical_validation_only": True,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "actionable": False,
            "requires_confirmation_before_candidate_freeze": True,
            "data_blockers_unchanged": list(
                v29_report.get("data_blockers_unchanged", [])
            ),
            "decision_rows": decision_rows,
            "paired_comparison_rows": paired_rows,
        }
        _write_json(destination / REPORT_FILE, report)
        return {**report, "output_dir": str(destination)}
    except Exception:
        for path in sorted(destination.glob("*")):
            if path.is_file():
                path.unlink()
        destination.rmdir()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.portfolio_ablation_v30"
    )
    parser.add_argument("--v29-artifact-zip", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v29-sha256")
    parser.add_argument("--expected-input-sha256")
    parser.add_argument(
        "--breadths",
        type=_parse_int_list,
        default=DEFAULT_BREADTHS,
    )
    parser.add_argument(
        "--replacement-caps",
        type=_parse_int_list,
        default=DEFAULT_REPLACEMENT_CAPS,
    )
    parser.add_argument("--validation-months", type=int, default=6)
    parser.add_argument("--test-months", type=int, default=3)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--bootstrap-block-months", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260802)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_v30(
            v29_artifact_zip=args.v29_artifact_zip,
            model_output=args.model_output,
            output_dir=args.output_dir,
            expected_v29_sha256=args.expected_v29_sha256,
            expected_input_sha256=args.expected_input_sha256,
            breadths=args.breadths,
            replacement_caps=args.replacement_caps,
            validation_months=args.validation_months,
            test_months=args.test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            seed=args.seed,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result["status"],
        "output_dir": result["output_dir"],
        "passing_breadths": result["passing_breadths"],
        "recommendation": result["recommendation"],
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "FROZEN_MODEL",
    "CHALLENGER_MODEL",
    "DEFAULT_BREADTHS",
    "run_v30",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
