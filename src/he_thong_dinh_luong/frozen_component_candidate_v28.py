"""V28 frozen component candidate verification and forward watchlist.

V27 found one post-review candidate/breadth combination that passed the
historical diagnostic gates: ``C3_STABLE_3_PAST_IC_SHRUNK`` at fixed Top-10.
V28 does not treat that result as an independent confirmation. It rebuilds the
same chronology from source input, verifies the frozen candidate against the
V27 artifact, publishes a non-actionable forward watchlist, and requires a
genuinely future holdout before any research-reference or live-capital approval.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
import shutil
from typing import Mapping, Sequence
import zipfile

from . import component_breadth_ablation_v27 as v27
from . import component_breadth_ablation_v27_runner as v27_runner


SCHEMA_VERSION = "frozen_component_candidate_v28"
REPORT_FILE = "frozen_component_candidate_v28.json"
FROZEN_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
FROZEN_BREADTH = 10
MINIMUM_FUTURE_HOLDOUT_MONTHS = 12
SCORE_TOLERANCE = 1e-12
METRIC_TOLERANCE = 1e-10


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"V28_JSON_OBJECT_REQUIRED:{Path(path).name}")
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and not fields:
        return
    fieldnames = list(fields or rows[0].keys())
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(
        buffer.getvalue(),
        encoding="utf-8-sig",
        newline="",
    )


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def _finite(value: object, *, name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"V28_MISSING_NUMERIC:{name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V28_NON_FINITE:{name}")
    return number


def _number_or_value(value: object) -> object:
    if value in (None, ""):
        return value
    text = str(value)
    if text.strip().lower() in {"true", "false"}:
        return text.strip().lower() == "true"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number.is_integer() and "." not in text and "e" not in text.lower():
        return int(number)
    return number


def _candidate_gate_row(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    matches = [
        dict(row)
        for row in rows
        if str(row.get("model") or "") == FROZEN_MODEL
        and int(float(row.get("breadth", 0) or 0)) == FROZEN_BREADTH
    ]
    if len(matches) != 1:
        raise ValueError("V28_FROZEN_CANDIDATE_GATE_ROW_NOT_UNIQUE")
    row = matches[0]
    if not _truthy(row.get("v27_decision_gate_passed")):
        raise ValueError("V28_FROZEN_CANDIDATE_DID_NOT_PASS_V27")
    if not _truthy(row.get("fixed_breadth_fully_feasible")):
        raise ValueError("V28_FROZEN_BREADTH_NOT_FULLY_FEASIBLE")
    if int(float(row.get(
        "availability_capped_outer_period_count",
        0,
    ) or 0)) != 0:
        raise ValueError("V28_FROZEN_BREADTH_USED_CASH_SLOT_HOTFIX")
    return row


def _filter_model(
    rows: Sequence[Mapping[str, object]],
    *,
    model_key: str = "model",
) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in rows
        if str(row.get(model_key) or "") == FROZEN_MODEL
    ]


def _prediction_key(row: Mapping[str, object]) -> tuple[str, str]:
    return (
        str(row.get("test_date") or ""),
        str(row.get("symbol") or ""),
    )


def compare_prediction_rows(
    source_rows: Sequence[Mapping[str, object]],
    rebuilt_rows: Sequence[Mapping[str, object]],
    *,
    tolerance: float = SCORE_TOLERANCE,
) -> dict[str, object]:
    source = {
        _prediction_key(row): row
        for row in source_rows
        if str(row.get("model") or "") == FROZEN_MODEL
    }
    rebuilt = {
        _prediction_key(row): row
        for row in rebuilt_rows
        if str(row.get("model") or "") == FROZEN_MODEL
    }
    if not source or set(source) != set(rebuilt):
        raise ValueError("V28_PREDICTION_KEY_SET_MISMATCH")
    maximum_score_difference = 0.0
    for key in sorted(source):
        left = source[key]
        right = rebuilt[key]
        score_difference = abs(
            _finite(left.get("score"), name="source_score")
            - _finite(right.get("score"), name="rebuilt_score")
        )
        maximum_score_difference = max(
            maximum_score_difference,
            score_difference,
        )
        if score_difference > tolerance:
            raise ValueError(
                "V28_PREDICTION_SCORE_MISMATCH:"
                f"{key[0]}:{key[1]}:{score_difference}"
            )
        if int(float(left.get("rank", 0) or 0)) != int(
            float(right.get("rank", 0) or 0)
        ):
            raise ValueError(
                f"V28_PREDICTION_RANK_MISMATCH:{key[0]}:{key[1]}"
            )
        if str(left.get("label_end") or "") != str(
            right.get("label_end") or ""
        ):
            raise ValueError(
                f"V28_PREDICTION_FIELD_MISMATCH:label_end:{key[0]}:{key[1]}"
            )
        for field in (
            "stock_return",
            "benchmark_return",
            "relative_return",
        ):
            difference = abs(
                _finite(left.get(field), name=field)
                - _finite(right.get(field), name=field)
            )
            if difference > tolerance:
                raise ValueError(
                    f"V28_PREDICTION_FIELD_MISMATCH:{field}:{key[0]}:{key[1]}"
                )
    return {
        "status": "MATCH",
        "row_count": len(source),
        "maximum_score_difference": maximum_score_difference,
        "score_tolerance": tolerance,
    }


def compare_weight_rows(
    source_rows: Sequence[Mapping[str, object]],
    rebuilt_rows: Sequence[Mapping[str, object]],
    *,
    tolerance: float = SCORE_TOLERANCE,
) -> dict[str, object]:
    source = {
        str(row.get("test_date") or ""): row
        for row in source_rows
    }
    rebuilt = {
        str(row.get("test_date") or ""): row
        for row in rebuilt_rows
    }
    if not source or set(source) != set(rebuilt):
        raise ValueError("V28_WEIGHT_DATE_SET_MISMATCH")
    fields = (
        "weight_low_volatility",
        "weight_relative_strength_120",
        "weight_high_52_week",
    )
    maximum_difference = 0.0
    for day in sorted(source):
        for field in fields:
            difference = abs(
                _finite(source[day].get(field), name=field)
                - _finite(rebuilt[day].get(field), name=field)
            )
            maximum_difference = max(maximum_difference, difference)
            if difference > tolerance:
                raise ValueError(
                    f"V28_WEIGHT_MISMATCH:{day}:{field}:{difference}"
                )
        if _truthy(source[day].get("uses_test_labels")):
            raise ValueError(f"V28_SOURCE_WEIGHT_USES_TEST_LABELS:{day}")
        if _truthy(rebuilt[day].get("uses_test_labels")):
            raise ValueError(f"V28_REBUILT_WEIGHT_USES_TEST_LABELS:{day}")
    return {
        "status": "MATCH",
        "row_count": len(source),
        "maximum_weight_difference": maximum_difference,
        "weight_tolerance": tolerance,
    }


def _portfolio_candidate_row(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    matches = [
        dict(row)
        for row in rows
        if str(row.get("model") or "") == FROZEN_MODEL
        and int(float(row.get("breadth", 0) or 0)) == FROZEN_BREADTH
    ]
    if len(matches) != 1:
        raise ValueError("V28_PORTFOLIO_CANDIDATE_ROW_NOT_UNIQUE")
    return matches[0]


def compare_metric_row(
    source_rows: Sequence[Mapping[str, object]],
    rebuilt_rows: Sequence[Mapping[str, object]],
    *,
    tolerance: float = METRIC_TOLERANCE,
) -> dict[str, object]:
    source = _portfolio_candidate_row(source_rows)
    rebuilt = _portfolio_candidate_row(rebuilt_rows)
    fields = (
        "base_relative_total_return",
        "stress_relative_total_return",
        "base_leave_best_period_out_relative_total_return",
        "base_mean_turnover",
        "base_max_drawdown",
        "mean_rank_ic",
        "positive_rank_ic_ratio",
    )
    maximum_difference = 0.0
    for field in fields:
        difference = abs(
            _finite(source.get(field), name=field)
            - _finite(rebuilt.get(field), name=field)
        )
        maximum_difference = max(maximum_difference, difference)
        if difference > tolerance:
            raise ValueError(
                f"V28_METRIC_MISMATCH:{field}:{difference}"
            )
    return {
        "status": "MATCH",
        "maximum_metric_difference": maximum_difference,
        "metric_tolerance": tolerance,
    }


def _load_labeled_rows_compatible(
    input_zip: Path,
) -> tuple[list[v27.ResearchRow], dict[str, object]]:
    original = v27._finite
    v27._ORIGINAL_V27_FINITE = original  # type: ignore[attr-defined]
    v27._finite = v27_runner._finite_with_v22_boolean
    try:
        rows, manifest = v27._load_input_zip(input_zip)
    finally:
        v27._finite = original
        try:
            delattr(v27, "_ORIGINAL_V27_FINITE")
        except AttributeError:
            pass
    return rows, manifest


def _forward_reason_is_eligible(value: object) -> bool:
    reasons = {
        item.strip()
        for item in str(value or "").split("|")
        if item.strip()
    }
    return not (reasons - {"thieu_open_t1"})


def _load_forward_features(
    input_zip: Path,
) -> tuple[date, list[dict[str, object]]]:
    with zipfile.ZipFile(input_zip) as archive:
        with archive.open("feature_raw.csv") as raw:
            rows = [
                dict(row)
                for row in csv.DictReader(
                    io.TextIOWrapper(
                        raw,
                        encoding="utf-8-sig",
                        newline="",
                    )
                )
            ]
    dates = sorted(
        {
            date.fromisoformat(str(row.get("ngay") or ""))
            for row in rows
            if str(row.get("ngay") or "")
        }
    )
    if not dates:
        raise ValueError("V28_FORWARD_DATE_NOT_FOUND")
    forward_day = dates[-1]
    output: list[dict[str, object]] = []
    for row in rows:
        if str(row.get("ngay") or "") != forward_day.isoformat():
            continue
        if not _truthy(row.get("hop_le")):
            continue
        if not _forward_reason_is_eligible(row.get("ly_do_eligibility")):
            continue
        output.append(
            {
                "signal_date": forward_day.isoformat(),
                "symbol": str(row.get("ma") or "").upper(),
                "low_volatility_raw": -max(
                    abs(_finite(
                        row.get("bien_dong_60"),
                        name="bien_dong_60",
                    )),
                    1e-6,
                ),
                "relative_strength_120_raw": _finite(
                    row.get("suc_manh_tuong_doi_120"),
                    name="suc_manh_tuong_doi_120",
                ),
                "high_52_week_raw": _finite(
                    row.get("ty_le_dinh_52_tuan"),
                    name="ty_le_dinh_52_tuan",
                ),
                "eligibility_without_t1": True,
                "open_t1_required_for_execution": True,
                "open_t1_available": _truthy(row.get("open_t1_hop_le")),
                "market_regime": (
                    "RISK_ON"
                    if _truthy(row.get("vnindex_tren_ma250"))
                    else "RISK_OFF"
                ),
            }
        )
    output.sort(key=lambda row: str(row["symbol"]))
    if len(output) < FROZEN_BREADTH:
        raise ValueError("V28_FORWARD_INSUFFICIENT_ELIGIBLE_SYMBOLS")
    regimes = {str(row["market_regime"]) for row in output}
    if len(regimes) != 1:
        raise ValueError("V28_FORWARD_MARKET_REGIME_INCONSISTENT")
    return forward_day, output


def _forward_history(
    rows: Sequence[v27.ResearchRow],
    *,
    forward_day: date,
    inner_validation_months: int,
    minimum_train_months: int,
) -> tuple[v27.ResearchRow, ...]:
    eligible = [
        row
        for row in rows
        if row.signal_day < forward_day
        and row.label_end < forward_day
    ]
    eligible_dates = sorted({row.signal_day for row in eligible})
    if len(eligible_dates) < minimum_train_months + inner_validation_months:
        raise ValueError("V28_FORWARD_HISTORY_TOO_SHORT")
    validation_dates_ordered = eligible_dates[-inner_validation_months:]
    validation_dates = set(validation_dates_ordered)
    validation_start = validation_dates_ordered[0]
    train_rows = [
        row
        for row in eligible
        if row.signal_day not in validation_dates
        and row.label_end < validation_start
    ]
    train_dates = {row.signal_day for row in train_rows}
    if len(train_dates) < minimum_train_months:
        raise ValueError("V28_FORWARD_TRAIN_TOO_SHORT")
    validation_rows = [
        row
        for row in eligible
        if row.signal_day in validation_dates
    ]
    return tuple(train_rows + validation_rows)


def _score_forward(
    rows: Sequence[Mapping[str, object]],
    weights: Mapping[str, float],
) -> list[dict[str, object]]:
    fields = (
        ("low_volatility", "low_volatility_raw"),
        ("relative_strength_120", "relative_strength_120_raw"),
        ("high_52_week", "high_52_week_raw"),
    )
    ranked: dict[str, list[float]] = {}
    for component, field in fields:
        ranked[component] = v27.average_percentile(
            [_finite(row.get(field), name=field) for row in rows]
        )
    scores = [
        sum(
            float(weights[component]) * ranked[component][index]
            for component, _ in fields
        )
        for index in range(len(rows))
    ]
    order = sorted(
        range(len(rows)),
        key=lambda index: (
            -scores[index],
            str(rows[index].get("symbol") or ""),
        ),
    )
    rank_by_index = {
        index: position + 1
        for position, index in enumerate(order)
    }
    output: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        rank = rank_by_index[index]
        output.append(
            {
                **dict(row),
                "model": FROZEN_MODEL,
                "score": scores[index],
                "rank": rank,
                "selected_top_10_watchlist": rank <= FROZEN_BREADTH,
                "weight_low_volatility": weights["low_volatility"],
                "weight_relative_strength_120": weights[
                    "relative_strength_120"
                ],
                "weight_high_52_week": weights["high_52_week"],
                "execution_status": "WAIT_FOR_EXACT_T1_OPEN",
                "actionable": False,
            }
        )
    output.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))
    return output


def _selected_row(
    rows: Sequence[Mapping[str, object]],
    *,
    model: str,
    breadth: int | None = None,
) -> dict[str, object]:
    matches = [
        dict(row)
        for row in rows
        if str(row.get("model") or "") == model
        and (
            breadth is None
            or int(float(row.get("breadth", 0) or 0)) == breadth
        )
    ]
    if len(matches) != 1:
        raise ValueError(
            f"V28_EXPECTED_ONE_ROW:{model}:{breadth}:{len(matches)}"
        )
    return matches[0]


def run_v28(
    input_zip: Path,
    v27_output_dir: Path,
    model_output: Path,
    output_dir: Path,
    *,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
    nested_validation_months: int = 6,
    nested_test_months: int = 3,
    minimum_outer_test_periods: int = 48,
    freeze_date: date = date(2026, 8, 2),
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    v27_root = Path(v27_output_dir).resolve()
    model_root = Path(model_output).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_file():
        raise ValueError("V28_INPUT_ZIP_NOT_FOUND")
    if not v27_root.is_dir():
        raise ValueError("V28_V27_OUTPUT_NOT_FOUND")
    if not model_root.is_dir():
        raise ValueError("V28_MODEL_OUTPUT_NOT_FOUND")
    if destination.exists():
        raise FileExistsError(f"V28_OUTPUT_EXISTS:{destination}")

    v27_report_path = v27_root / v27.REPORT_FILE
    if not v27_report_path.is_file():
        raise ValueError("V28_V27_REPORT_NOT_FOUND")
    v27_report = _read_json(v27_report_path)
    if str(v27_report.get("status") or "") != "SUCCESS":
        raise ValueError("V28_V27_STATUS_NOT_SUCCESS")
    if str(v27_report.get("recommendation") or "") != (
        "RUN_V28_FULL_WALK_FORWARD"
    ):
        raise ValueError("V28_V27_RECOMMENDATION_NOT_READY")
    if str(v27_report.get("input_zip_sha256") or "") != _sha256(source):
        raise ValueError("V28_INPUT_SHA_MISMATCH_V27")
    if _truthy(v27_report.get("research_eligible")):
        raise ValueError("V28_V27_MUST_REMAIN_TECHNICAL_ONLY")
    if _truthy(v27_report.get("live_capital_approved")):
        raise ValueError("V28_V27_LIVE_CAPITAL_MUST_BE_FALSE")

    source_decision_rows = _read_csv(
        v27_root / "decision_gates_v27.csv"
    )
    source_gate = _candidate_gate_row(source_decision_rows)

    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    rebuild_dir = staging / "v27_rebuild"
    try:
        rebuild_report = v27_runner.run_v27_compatible(
            source,
            model_root,
            rebuild_dir,
            evaluation_months=evaluation_months,
            minimum_train_months=minimum_train_months,
            inner_validation_months=inner_validation_months,
            nested_validation_months=nested_validation_months,
            nested_test_months=nested_test_months,
            minimum_outer_test_periods=minimum_outer_test_periods,
            breadths=(FROZEN_BREADTH,),
        )
        if str(rebuild_report.get("status") or "") != "SUCCESS":
            raise ValueError("V28_REBUILD_NOT_SUCCESS")

        rebuilt_decision_rows = _read_csv(
            rebuild_dir / "decision_gates_v27.csv"
        )
        rebuilt_gate = _candidate_gate_row(rebuilt_decision_rows)

        prediction_check = compare_prediction_rows(
            _read_csv(v27_root / "candidate_predictions_v27.csv"),
            _read_csv(rebuild_dir / "candidate_predictions_v27.csv"),
        )
        weight_check = compare_weight_rows(
            _read_csv(v27_root / "adaptive_component_weights_v27.csv"),
            _read_csv(rebuild_dir / "adaptive_component_weights_v27.csv"),
        )
        metric_check = compare_metric_row(
            _read_csv(v27_root / "portfolio_comparison_v27.csv"),
            _read_csv(rebuild_dir / "portfolio_comparison_v27.csv"),
        )

        rebuilt_predictions = _filter_model(
            _read_csv(rebuild_dir / "candidate_predictions_v27.csv")
        )
        rebuilt_weights = _read_csv(
            rebuild_dir / "adaptive_component_weights_v27.csv"
        )
        rebuilt_outer = _filter_model(
            _read_csv(rebuild_dir / "outer_test_periods_v27.csv")
        )
        rebuilt_stress = _filter_model(
            _read_csv(
                rebuild_dir / "outer_test_stress_periods_v27.csv"
            )
        )
        rebuilt_policy = _filter_model(
            _read_csv(rebuild_dir / "policy_selection_v27.csv")
        )
        portfolio_row = _selected_row(
            _read_csv(rebuild_dir / "portfolio_comparison_v27.csv"),
            model=FROZEN_MODEL,
            breadth=FROZEN_BREADTH,
        )
        factor_row = _selected_row(
            _read_csv(rebuild_dir / "factor_summary_v27.csv"),
            model=FROZEN_MODEL,
        )
        quantile_row = _selected_row(
            _read_csv(rebuild_dir / "quantile_shape_v27.csv"),
            model=FROZEN_MODEL,
        )
        signal_gate_row = _selected_row(
            _read_csv(rebuild_dir / "signal_gates_v27.csv"),
            model=FROZEN_MODEL,
        )
        regime_rows = _read_csv(rebuild_dir / "regime_summary_v27.csv")
        risk_on_row = next(
            (
                dict(row)
                for row in regime_rows
                if str(row.get("model") or "") == FROZEN_MODEL
                and str(row.get("regime") or "") == "RISK_ON"
            ),
            {},
        )
        risk_off_row = next(
            (
                dict(row)
                for row in regime_rows
                if str(row.get("model") or "") == FROZEN_MODEL
                and str(row.get("regime") or "") == "RISK_OFF"
            ),
            {},
        )
        if not risk_on_row or not risk_off_row:
            raise ValueError("V28_REGIME_DIAGNOSTIC_MISSING")

        labeled_rows, input_manifest = _load_labeled_rows_compatible(
            source
        )
        forward_day, forward_features = _load_forward_features(source)
        if forward_day >= freeze_date:
            raise ValueError(
                "V28_FREEZE_DATE_MUST_BE_AFTER_FORWARD_SIGNAL"
            )
        forward_history = _forward_history(
            labeled_rows,
            forward_day=forward_day,
            inner_validation_months=inner_validation_months,
            minimum_train_months=minimum_train_months,
        )
        forward_weights = v27.shrunk_component_weights(
            forward_history,
            components=v27.STABLE_THREE,
            shrinkage_to_equal=0.50,
            max_component_weight=0.50,
        )
        forward_watchlist = _score_forward(
            forward_features,
            forward_weights,
        )
        forward_regime = str(forward_watchlist[0]["market_regime"])

        verification_rows = [
            {
                "check": "source_v27_decision_gate",
                "status": "PASS",
                "detail": (
                    f"{FROZEN_MODEL}|top_{FROZEN_BREADTH}|"
                    f"{source_gate.get('v27_decision_gate_passed')}"
                ),
            },
            {
                "check": "rebuilt_v27_decision_gate",
                "status": "PASS",
                "detail": (
                    f"{FROZEN_MODEL}|top_{FROZEN_BREADTH}|"
                    f"{rebuilt_gate.get('v27_decision_gate_passed')}"
                ),
            },
            {
                "check": "prediction_rebuild",
                "status": "PASS",
                "detail": json.dumps(
                    prediction_check,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "check": "adaptive_weight_rebuild",
                "status": "PASS",
                "detail": json.dumps(
                    weight_check,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "check": "portfolio_metric_rebuild",
                "status": "PASS",
                "detail": json.dumps(
                    metric_check,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "check": "forward_watchlist",
                "status": "PASS",
                "detail": (
                    f"signal_date={forward_day.isoformat()}|"
                    f"candidate_count={len(forward_watchlist)}|"
                    f"selected_count="
                    f"{sum(bool(row['selected_top_10_watchlist']) for row in forward_watchlist)}|"
                    f"market_regime={forward_regime}"
                ),
            },
        ]

        _write_csv(
            staging / "frozen_candidate_predictions_v28.csv",
            rebuilt_predictions,
        )
        _write_csv(
            staging / "frozen_candidate_weights_v28.csv",
            rebuilt_weights,
        )
        _write_csv(
            staging / "frozen_candidate_outer_periods_v28.csv",
            rebuilt_outer,
        )
        _write_csv(
            staging / "frozen_candidate_outer_stress_periods_v28.csv",
            rebuilt_stress,
        )
        _write_csv(
            staging / "frozen_candidate_policy_selection_v28.csv",
            rebuilt_policy,
        )
        _write_csv(
            staging / "forward_watchlist_v28.csv",
            forward_watchlist,
        )
        _write_csv(
            staging / "verification_v28.csv",
            verification_rows,
        )

        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS_FROZEN_FORWARD_CANDIDATE",
            "candidate": {
                "model": FROZEN_MODEL,
                "breadth": FROZEN_BREADTH,
                "component_set": list(v27.STABLE_THREE),
                "weight_method": (
                    "PAST_COMPLETED_MONTHLY_IC_POSITIVE_ONLY_"
                    "SHRUNK_50_PERCENT_TO_EQUAL_CAP_50_PERCENT"
                ),
                "model_test_fold": "ONE_MONTH",
                "predictive_label_horizon": "20_SESSIONS",
                "portfolio_policy": (
                    "SIX_PRIOR_MONTHS_SELECT_REPLACEMENT_CAP_"
                    "FOR_THREE_MONTH_OUTER_BLOCK"
                ),
            },
            "freeze_date": freeze_date.isoformat(),
            "input_zip": str(source),
            "input_zip_sha256": _sha256(source),
            "input_manifest_schema_version": input_manifest.get(
                "schema_version"
            ),
            "source_v27_output": str(v27_root),
            "source_v27_report_sha256": _sha256(v27_report_path),
            "source_model_output": str(model_root),
            "walk_forward_fold_count": int(
                rebuild_report["walk_forward_fold_count"]
            ),
            "walk_forward_first_test_date": rebuild_report[
                "walk_forward_first_test_date"
            ],
            "walk_forward_last_test_date": rebuild_report[
                "walk_forward_last_test_date"
            ],
            "outer_test_period_count": int(float(
                portfolio_row["outer_test_period_count"]
            )),
            "historical_metrics": {
                key: _number_or_value(value)
                for key, value in portfolio_row.items()
                if key in {
                    "model",
                    "status",
                    "outer_test_period_count",
                    "mean_rank_ic",
                    "positive_rank_ic_ratio",
                    "base_net_total_return",
                    "base_benchmark_total_return",
                    "base_relative_total_return",
                    "stress_relative_total_return",
                    "base_average_net_excess_return",
                    "base_positive_net_excess_ratio",
                    "base_mean_turnover",
                    "base_max_drawdown",
                    "base_leave_best_period_out_relative_total_return",
                    "base_best_positive_excess_contribution_share",
                    "outer_block_positive_net_excess_ratio",
                    "gate_passed",
                    "failed_gates",
                }
            },
            "signal_metrics_all_57_folds": {
                key: _number_or_value(value)
                for key, value in factor_row.items()
                if key in {
                    "model",
                    "period_count",
                    "first_test_date",
                    "last_test_date",
                    "mean_rank_ic",
                    "median_rank_ic",
                    "positive_rank_ic_ratio",
                    "first_half_mean_rank_ic",
                    "second_half_mean_rank_ic",
                    "rolling_ic_minimum",
                    "rolling_ic_maximum",
                    "top_minus_bottom_compound_difference",
                    "leave_best_period_out_top_minus_bottom_compound_difference",
                }
            },
            "quantile_shape": dict(quantile_row),
            "signal_gate": dict(signal_gate_row),
            "regime_diagnostic": {
                "risk_on": {
                    key: _number_or_value(value)
                    for key, value in risk_on_row.items()
                },
                "risk_off": {
                    key: _number_or_value(value)
                    for key, value in risk_off_row.items()
                },
                "regime_overlay_not_yet_approved": True,
            },
            "verification": {
                "prediction_rebuild": prediction_check,
                "adaptive_weight_rebuild": weight_check,
                "portfolio_metric_rebuild": metric_check,
                "source_gate": dict(source_gate),
                "rebuilt_gate": dict(rebuilt_gate),
            },
            "forward_watchlist": {
                "signal_date": forward_day.isoformat(),
                "candidate_count": len(forward_watchlist),
                "selected_count": sum(
                    bool(row["selected_top_10_watchlist"])
                    for row in forward_watchlist
                ),
                "weights": forward_weights,
                "market_regime": forward_regime,
                "regime_overlay_status": (
                    "CASH_REGIME_ACTIVE_DIAGNOSTIC"
                    if forward_regime == "RISK_OFF"
                    else "RISK_ON_RANKING_DIAGNOSTIC"
                ),
                "t1_open_available_at_publication": False,
                "execution_allowed": False,
                "genuinely_future_holdout_period": False,
                "reason": (
                    "SIGNAL_DATE_PRECEDES_V28_FREEZE_AND_T1_OPEN_IS_MISSING"
                ),
            },
            "selection_disclosure": {
                "candidate_selected_after_reviewing_v23_v25_v26_v27": True,
                "candidate_count_reviewed_in_v27": 4,
                "breadth_count_reviewed_in_v27": 4,
                "multiple_testing_adjusted": False,
                "independent_holdout": False,
                "historical_reference_approved": False,
                "historical_gate_is_diagnostic_only": True,
            },
            "future_holdout": {
                "required": True,
                "minimum_months": MINIMUM_FUTURE_HOLDOUT_MONTHS,
                "freeze_date": freeze_date.isoformat(),
                "signal_date_must_be_strictly_after_v28_freeze": True,
                "candidate_and_protocol_must_remain_unchanged": True,
                "status": "NOT_STARTED",
            },
            "technical_validation_only": True,
            "research_eligible": False,
            "paper_watch_candidate": True,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "contribution_evaluation_allowed": False,
            "contribution_skip_reason": (
                "NO_INDEPENDENT_FUTURE_HOLDOUT_FOR_FROZEN_CANDIDATE"
            ),
        }
        _write_json(staging / REPORT_FILE, report)
        shutil.rmtree(rebuild_dir)
        os.replace(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {**report, "output_dir": str(destination)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "python -m "
            "he_thong_dinh_luong.frozen_component_candidate_v28"
        )
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--v27-output-dir", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--nested-validation-months", type=int, default=6)
    parser.add_argument("--nested-test-months", type=int, default=3)
    parser.add_argument(
        "--minimum-outer-test-periods",
        type=int,
        default=48,
    )
    parser.add_argument(
        "--freeze-date",
        type=date.fromisoformat,
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_v28(
            args.input_zip,
            args.v27_output_dir,
            args.model_output,
            args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            nested_validation_months=args.nested_validation_months,
            nested_test_months=args.nested_test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            freeze_date=args.freeze_date,
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
    print(
        json.dumps(
            {
                "status": result["status"],
                "output_dir": result["output_dir"],
                "candidate": result["candidate"],
                "walk_forward_fold_count": result[
                    "walk_forward_fold_count"
                ],
                "outer_test_period_count": result[
                    "outer_test_period_count"
                ],
                "forward_signal_date": result[
                    "forward_watchlist"
                ]["signal_date"],
                "forward_market_regime": result[
                    "forward_watchlist"
                ]["market_regime"],
                "future_holdout_status": result[
                    "future_holdout"
                ]["status"],
                "live_capital_approved": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "FROZEN_MODEL",
    "FROZEN_BREADTH",
    "compare_prediction_rows",
    "compare_weight_rows",
    "run_v28",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
