"""V32 portfolio ablation on the canonical V31 all-history predictions.

V32 does not retrain predictive models. It:
* verifies the immutable V31 artifact and V22 input lineage;
* restores portfolio eligibility from the canonical V22 feature file;
* evaluates C3, ridge-regime, full-regime logit, and two regime-gated
  logit policies on the primary chronological V31 predictions;
* selects only the turnover replacement cap from strictly-prior validation;
* reports base and stress modeled transaction-cost returns.

The result is a label-return portfolio proxy, not an exact cash ledger. The
source artifact has no executed quantities, exchange, sectors, or exact T+1
execution prices. Lot size, sector caps, inverse-volatility sizing, and
corporate-action-complete accounting are therefore not claimed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
from statistics import fmean
from typing import Mapping, Sequence
import zipfile

from . import all_history_protocol_v31 as v31
from . import model_lab_upgrade_v15 as v15
from . import model_lab_upgrade_v13 as v13
from . import portfolio_ablation_v30 as v30
from . import predictive_target_lab_v29 as v29

SCHEMA_VERSION = "portfolio_ablation_v32"
REPORT_FILE = "portfolio_ablation_v32.json"

FROZEN_MODEL = v29.FROZEN_MODEL
RIDGE_REGIME_MODEL = v29.RIDGE_REGIME_MODEL
LOGIT_MODEL = v29.BOTTOM_MODEL
LOGIT_ON_C3_OFF = "V32_LOGIT_RISK_ON_C3_RISK_OFF"
LOGIT_ON_RIDGE_OFF = "V32_LOGIT_RISK_ON_RIDGE_RISK_OFF"

SOURCE_MODELS = (FROZEN_MODEL, RIDGE_REGIME_MODEL, LOGIT_MODEL)
CANDIDATE_MODELS = (
    FROZEN_MODEL,
    RIDGE_REGIME_MODEL,
    LOGIT_MODEL,
    LOGIT_ON_C3_OFF,
    LOGIT_ON_RIDGE_OFF,
)
DEFAULT_BREADTHS = (10, 15, 20, 30)
DEFAULT_REPLACEMENT_CAPS = (0, 1, 2, 3, 4, 5)
REQUIRED_V31_FILES = {
    v31.REPORT_FILE,
    "predictions_primary_v31.csv",
    "decision_gates_v31.csv",
    "statistical_summary_v31.csv",
    "analysis_bundle_manifest_v31.json",
}
PRIMARY_PROTOCOL = v31.PRIMARY_PROTOCOL


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _boolean_number(value: object, *, name: str) -> float:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return 1.0
    if text in {"0", "false", "no", "n"}:
        return 0.0
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"V32_INVALID_BOOLEAN_FEATURE:{name}:{text}") from exc
    if number not in {0.0, 1.0}:
        raise ValueError(f"V32_INVALID_BOOLEAN_FEATURE:{name}:{text}")
    return number


def _finite(value: object, *, name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"V32_MISSING_NUMERIC:{name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V32_NON_FINITE:{name}")
    return number


def _safe_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"V32_UNSAFE_ZIP_MEMBER:{name}")
    if not path.name:
        raise ValueError(f"V32_EMPTY_ZIP_MEMBER:{name}")
    return path.name


def _read_csv_bytes(value: bytes) -> list[dict[str, str]]:
    with io.StringIO(value.decode("utf-8-sig"), newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


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


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and fields is None:
        raise ValueError(f"V32_CSV_ROWS_EMPTY:{path.name}")
    if fields is None:
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for field in row:
                if field not in seen:
                    seen.add(field)
                    fieldnames.append(field)
    else:
        fieldnames = list(fields)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _load_flat_zip(path: Path) -> dict[str, tuple[str, bytes]]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"V32_ZIP_NOT_FOUND:{source}")
    members: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = _safe_basename(info.filename)
            if basename in members:
                raise ValueError(f"V32_DUPLICATE_ZIP_BASENAME:{basename}")
            members[basename] = (info.filename, archive.read(info))
    return members


def _load_v31_artifact(
    artifact_zip: Path,
    *,
    expected_sha256: str | None,
    expected_input_sha256: str | None,
) -> tuple[
    dict[str, object],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, object],
]:
    source = Path(artifact_zip).resolve()
    artifact_sha = _sha256(source)
    if expected_sha256 and artifact_sha != expected_sha256:
        raise ValueError("V32_V31_ARTIFACT_SHA256_MISMATCH")
    members = _load_flat_zip(source)
    missing = REQUIRED_V31_FILES - set(members)
    if missing:
        raise ValueError(
            "V32_V31_REQUIRED_FILES_MISSING:" + "|".join(sorted(missing))
        )

    report_bytes = members[v31.REPORT_FILE][1]
    report = json.loads(report_bytes.decode("utf-8-sig"))
    if not isinstance(report, dict):
        raise ValueError("V32_V31_REPORT_OBJECT_REQUIRED")
    if report.get("schema_version") != v31.SCHEMA_VERSION:
        raise ValueError("V32_V31_SCHEMA_MISMATCH")
    if report.get("status") != "SUCCESS":
        raise ValueError("V32_V31_STATUS_NOT_SUCCESS")
    primary = dict(report.get("primary_protocol") or {})
    if primary.get("name") != PRIMARY_PROTOCOL:
        raise ValueError("V32_V31_PRIMARY_PROTOCOL_MISMATCH")
    if bool(primary.get("future_rows_used_for_past_prediction")):
        raise ValueError("V32_V31_FUTURE_LEAKAGE_FLAGGED")
    if expected_input_sha256 and report.get("input_zip_sha256") != expected_input_sha256:
        raise ValueError("V32_V31_INPUT_SHA256_MISMATCH")

    predictions = _read_csv_bytes(members["predictions_primary_v31.csv"][1])
    decisions = _read_csv_bytes(members["decision_gates_v31.csv"][1])
    statistics = _read_csv_bytes(members["statistical_summary_v31.csv"][1])
    metadata = {
        "artifact_zip": str(source),
        "artifact_zip_sha256": artifact_sha,
        "report_member": members[v31.REPORT_FILE][0],
        "report_sha256": _bytes_sha256(report_bytes),
        "predictions_sha256": _bytes_sha256(
            members["predictions_primary_v31.csv"][1]
        ),
        "decision_gates_sha256": _bytes_sha256(
            members["decision_gates_v31.csv"][1]
        ),
        "statistical_summary_sha256": _bytes_sha256(
            members["statistical_summary_v31.csv"][1]
        ),
        "analysis_manifest_sha256": _bytes_sha256(
            members["analysis_bundle_manifest_v31.json"][1]
        ),
    }
    return report, predictions, decisions, statistics, metadata


def _load_v22_policy_contract(
    input_zip: Path,
    *,
    expected_sha256: str | None,
) -> tuple[set[tuple[str, str]], dict[str, float], dict[str, object]]:
    source = Path(input_zip).resolve()
    if not source.is_file():
        raise ValueError("V32_V22_INPUT_NOT_FOUND")
    input_sha = _sha256(source)
    if expected_sha256 and input_sha != expected_sha256:
        raise ValueError("V32_V22_INPUT_SHA256_MISMATCH")

    with zipfile.ZipFile(source) as archive:
        required = {"feature_raw.csv", "manifest.json"}
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError(
                "V32_V22_REQUIRED_FILES_MISSING:" + "|".join(sorted(missing))
            )
        manifest_bytes = archive.read("manifest.json")
        manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
        if not isinstance(manifest, dict):
            raise ValueError("V32_V22_MANIFEST_OBJECT_REQUIRED")

        eligible: set[tuple[str, str]] = set()
        regime_values: dict[str, set[float]] = defaultdict(set)
        feature_rows = 0
        with archive.open("feature_raw.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            )
            required_columns = {
                "ngay",
                "ma",
                "eligible",
                "vnindex_tren_ma250",
            }
            columns = set(reader.fieldnames or ())
            if not required_columns <= columns:
                raise ValueError(
                    "V32_V22_FEATURE_COLUMNS_MISSING:"
                    + "|".join(sorted(required_columns - columns))
                )
            for row in reader:
                feature_rows += 1
                day = str(row.get("ngay") or "")
                symbol = str(row.get("ma") or "").upper()
                if not day or not symbol:
                    raise ValueError("V32_V22_FEATURE_KEY_MISSING")
                raw_regime = row.get("vnindex_tren_ma250")
                if raw_regime not in (None, ""):
                    regime_values[day].add(
                        _boolean_number(raw_regime, name="vnindex_tren_ma250")
                    )
                if _truthy(row.get("eligible")):
                    eligible.add((day, symbol))

    regime: dict[str, float] = {}
    for day, values in regime_values.items():
        if len(values) != 1:
            raise ValueError(f"V32_V22_REGIME_CONFLICT:{day}:{sorted(values)}")
        regime[day] = next(iter(values))

    metadata = {
        "input_zip": str(source),
        "input_zip_sha256": input_sha,
        "manifest_sha256": _bytes_sha256(manifest_bytes),
        "manifest_schema": (
            manifest.get("schema_version")
            or manifest.get("contract_version")
            or manifest.get("schema")
        ),
        "raw_feature_row_count": feature_rows,
        "eligible_key_count": len(eligible),
        "regime_day_count": len(regime),
    }
    return eligible, regime, metadata


def _recompute_rank(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        converted = dict(row)
        grouped[
            (
                str(converted.get("model") or ""),
                str(converted.get("test_date") or ""),
            )
        ].append(converted)
    result: list[dict[str, object]] = []
    for (_, _), day_rows in sorted(grouped.items()):
        ordered = sorted(
            day_rows,
            key=lambda row: (
                -_finite(row.get("score"), name="score"),
                str(row.get("symbol") or ""),
            ),
        )
        denominator = max(len(ordered) - 1, 1)
        for index, row in enumerate(ordered, start=1):
            row["rank"] = index
            row["percentile"] = 1.0 - (index - 1) / denominator
            row["selected_top_k"] = "false"
            result.append(row)
    result.sort(
        key=lambda row: (
            str(row.get("test_date") or ""),
            str(row.get("model") or ""),
            int(row.get("rank", 10**9) or 10**9),
            str(row.get("symbol") or ""),
        )
    )
    return result


def _eligible_primary_predictions(
    predictions: Sequence[Mapping[str, object]],
    *,
    eligible_keys: set[tuple[str, str]],
    regime_by_day: Mapping[str, float],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_model_key: dict[str, dict[tuple[str, str], dict[str, object]]] = {
        model: {} for model in SOURCE_MODELS
    }
    source_key_sets: dict[str, set[tuple[str, str]]] = {
        model: set() for model in SOURCE_MODELS
    }

    for raw in predictions:
        protocol = str(raw.get("protocol") or "")
        if protocol and protocol != PRIMARY_PROTOCOL:
            continue
        model = str(raw.get("model") or "")
        if model not in SOURCE_MODELS:
            continue
        day = str(raw.get("test_date") or "")
        symbol = str(raw.get("symbol") or "").upper()
        if not day or not symbol:
            raise ValueError("V32_V31_PREDICTION_KEY_MISSING")
        key = (day, symbol)
        if key in by_model_key[model]:
            raise ValueError(f"V32_DUPLICATE_PREDICTION:{model}:{day}:{symbol}")
        converted = dict(raw)
        converted["symbol"] = symbol
        for name in (
            "score",
            "stock_return",
            "benchmark_return",
            "relative_return",
        ):
            _finite(converted.get(name), name=name)
        by_model_key[model][key] = converted
        source_key_sets[model].add(key)

    if any(not values for values in source_key_sets.values()):
        raise ValueError("V32_SOURCE_MODEL_PREDICTIONS_MISSING")
    reference_keys = source_key_sets[FROZEN_MODEL]
    for model, keys in source_key_sets.items():
        if keys != reference_keys:
            raise ValueError(f"V32_SOURCE_MODEL_KEY_SET_MISMATCH:{model}")

    eligible_prediction_keys = sorted(reference_keys & eligible_keys)
    dates = sorted({day for day, _ in eligible_prediction_keys})
    if not dates:
        raise ValueError("V32_NO_ELIGIBLE_PRIMARY_PREDICTIONS")
    missing_regime = [day for day in dates if day not in regime_by_day]
    if missing_regime:
        raise ValueError(
            "V32_REGIME_DAYS_MISSING:" + "|".join(missing_regime[:20])
        )

    output: list[dict[str, object]] = []
    for model in SOURCE_MODELS:
        for key in eligible_prediction_keys:
            output.append(dict(by_model_key[model][key]))

    gated_sources = {
        LOGIT_ON_C3_OFF: (LOGIT_MODEL, FROZEN_MODEL),
        LOGIT_ON_RIDGE_OFF: (LOGIT_MODEL, RIDGE_REGIME_MODEL),
    }
    gated_counts: dict[str, dict[str, int]] = {}
    for gated_model, (risk_on_model, risk_off_model) in gated_sources.items():
        counts = {"RISK_ON": 0, "RISK_OFF": 0}
        for day, symbol in eligible_prediction_keys:
            risk_on = float(regime_by_day[day]) >= 0.5
            source_model = risk_on_model if risk_on else risk_off_model
            source_row = by_model_key[source_model][(day, symbol)]
            converted = dict(source_row)
            converted["model"] = gated_model
            converted["source_model_by_regime"] = source_model
            converted["market_regime"] = "RISK_ON" if risk_on else "RISK_OFF"
            output.append(converted)
            counts[converted["market_regime"]] += 1
        gated_counts[gated_model] = counts

    ranked = _recompute_rank(output)
    by_day_count: dict[str, int] = defaultdict(int)
    for day, _ in eligible_prediction_keys:
        by_day_count[day] += 1
    metadata = {
        "source_prediction_key_count_per_model": len(reference_keys),
        "eligible_prediction_key_count_per_model": len(eligible_prediction_keys),
        "excluded_noneligible_prediction_key_count_per_model": (
            len(reference_keys) - len(eligible_prediction_keys)
        ),
        "eligible_first_test_date": dates[0],
        "eligible_last_test_date": dates[-1],
        "eligible_test_month_count": len(dates),
        "minimum_eligible_symbol_count_per_month": min(by_day_count.values()),
        "maximum_eligible_symbol_count_per_month": max(by_day_count.values()),
        "gated_source_row_counts": gated_counts,
        "candidate_models": list(CANDIDATE_MODELS),
    }
    return ranked, metadata


def _portfolio_evaluations(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
    replacement_caps: Sequence[int],
    validation_months: int,
    test_months: int,
    minimum_outer_test_periods: int,
    cost: v13.DnseCashCostConfig,
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
    normalized_breadths = v30._normalize_breadths(breadths)
    normalized_caps = v30._normalize_caps(
        replacement_caps,
        maximum_breadth=min(normalized_breadths),
    )
    for breadth in normalized_breadths:
        evaluation = v15.model_wise_nested_evaluation(
            prediction_rows,
            top_k=breadth,
            replacement_caps=normalized_caps,
            candidate_models=CANDIDATE_MODELS,
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
            raise ValueError("V32_OUTER_SIGNAL_DATE_MISSING")
        if day in result:
            raise ValueError(f"V32_DUPLICATE_OUTER_PERIOD:{model}:{breadth}:{day}")
        result[day] = row
    return result


def _paired_comparisons(
    outer_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
    bootstrap_repetitions: int,
    bootstrap_block_months: int,
    seed: int,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    c3_top10 = _period_map(outer_rows, breadth=10, model=FROZEN_MODEL)
    for breadth in v30._normalize_breadths(breadths):
        c3_same = _period_map(
            outer_rows,
            breadth=breadth,
            model=FROZEN_MODEL,
        )
        for model_index, model in enumerate(CANDIDATE_MODELS):
            if model == FROZEN_MODEL:
                continue
            challenger = _period_map(
                outer_rows,
                breadth=breadth,
                model=model,
            )
            for (
                comparison,
                baseline_breadth,
                baseline_rows,
                offset,
            ) in (
                ("SAME_BREADTH_C3", breadth, c3_same, 0),
                ("FROZEN_C3_TOP10", 10, c3_top10, 10000),
            ):
                stats = v30._paired_delta_stats(
                    challenger,
                    baseline_rows,
                    repetitions=bootstrap_repetitions,
                    block_months=bootstrap_block_months,
                    seed=seed + offset + breadth * 100 + model_index,
                )
                output.append(
                    {
                        "challenger_model": model,
                        "challenger_breadth": breadth,
                        "baseline_model": FROZEN_MODEL,
                        "baseline_breadth": baseline_breadth,
                        "comparison": comparison,
                        **stats,
                    }
                )
    return output


def _v31_gate_map(
    decisions: Sequence[Mapping[str, object]],
) -> dict[str, bool]:
    result = {model: False for model in CANDIDATE_MODELS}
    for row in decisions:
        if str(row.get("protocol") or PRIMARY_PROTOCOL) != PRIMARY_PROTOCOL:
            continue
        model = str(row.get("model") or "")
        if model in result:
            result[model] = _truthy(
                row.get("predictive_challenger_gate_passed")
            )
    result[FROZEN_MODEL] = False
    result[LOGIT_ON_C3_OFF] = False
    result[LOGIT_ON_RIDGE_OFF] = False
    return result


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
) -> dict[tuple[int, str, str], Mapping[str, object]]:
    return {
        (
            int(row.get("challenger_breadth", 0) or 0),
            str(row.get("challenger_model") or ""),
            str(row.get("comparison") or ""),
        ): row
        for row in rows
    }


def _decision_rows(
    summary_rows: Sequence[Mapping[str, object]],
    paired_rows: Sequence[Mapping[str, object]],
    *,
    breadths: Sequence[int],
    v31_gate_by_model: Mapping[str, bool],
) -> tuple[list[dict[str, object]], str]:
    summaries = _summary_index(summary_rows)
    comparisons = _comparison_index(paired_rows)
    c3_top10 = summaries.get((10, FROZEN_MODEL))
    if c3_top10 is None:
        raise ValueError("V32_C3_TOP10_SUMMARY_MISSING")
    c3_top10_worst = min(
        _finite(c3_top10.get("base_relative_total_return"), name="base_relative"),
        _finite(
            c3_top10.get("stress_relative_total_return"),
            name="stress_relative",
        ),
    )

    decisions: list[dict[str, object]] = []
    for breadth in v30._normalize_breadths(breadths):
        c3_same = summaries.get((breadth, FROZEN_MODEL))
        if c3_same is None:
            raise ValueError(f"V32_C3_SUMMARY_MISSING:{breadth}")
        c3_same_worst = min(
            _finite(c3_same.get("base_relative_total_return"), name="base_relative"),
            _finite(
                c3_same.get("stress_relative_total_return"),
                name="stress_relative",
            ),
        )
        for model in CANDIDATE_MODELS:
            row = summaries.get((breadth, model))
            if row is None:
                raise ValueError(f"V32_SUMMARY_MISSING:{model}:{breadth}")
            if model == FROZEN_MODEL:
                decisions.append(
                    {
                        "model": model,
                        "breadth": breadth,
                        "role": "BASELINE",
                        "v15_portfolio_gate_passed": _truthy(
                            row.get("gate_passed")
                        ),
                        "portfolio_diagnostic_gate_passed": _truthy(
                            row.get("gate_passed")
                        ),
                        "v32_historical_promotion_gate_passed": False,
                        "failed_v32_gates": "BASELINE_NOT_CHALLENGER",
                        "research_eligible": False,
                        "live_capital_approved": False,
                        "actionable": False,
                    }
                )
                continue

            same = comparisons.get((breadth, model, "SAME_BREADTH_C3"))
            top10 = comparisons.get((breadth, model, "FROZEN_C3_TOP10"))
            if same is None or top10 is None:
                raise ValueError(f"V32_PAIRED_EVIDENCE_MISSING:{model}:{breadth}")
            worst = min(
                _finite(row.get("base_relative_total_return"), name="base_relative"),
                _finite(
                    row.get("stress_relative_total_return"),
                    name="stress_relative",
                ),
            )
            diagnostic_gates = {
                "v15_portfolio_gate_passed": _truthy(row.get("gate_passed")),
                "base_relative_total_return_positive": _finite(
                    row.get("base_relative_total_return"),
                    name="base_relative_total_return",
                )
                > 0.0,
                "stress_relative_total_return_positive": _finite(
                    row.get("stress_relative_total_return"),
                    name="stress_relative_total_return",
                )
                > 0.0,
                "positive_monthly_net_excess_at_least_half": _finite(
                    row.get("base_positive_net_excess_ratio"),
                    name="base_positive_net_excess_ratio",
                )
                >= 0.50,
                "mean_turnover_at_most_half": _finite(
                    row.get("base_mean_turnover"),
                    name="base_mean_turnover",
                )
                <= 0.50,
                "leave_best_month_out_relative_positive": _finite(
                    row.get("base_leave_best_period_out_relative_total_return"),
                    name="leave_best_relative",
                )
                > 0.0,
                "worst_case_not_materially_below_same_breadth_c3": (
                    worst >= c3_same_worst - 0.02
                ),
                "worst_case_not_materially_below_c3_top10": (
                    worst >= c3_top10_worst - 0.02
                ),
                "paired_probability_vs_same_c3_at_least_070": _finite(
                    same.get("bootstrap_probability_delta_positive"),
                    name="bootstrap_probability_delta_positive",
                )
                >= 0.70,
                "paired_probability_vs_c3_top10_at_least_070": _finite(
                    top10.get("bootstrap_probability_delta_positive"),
                    name="bootstrap_probability_delta_positive",
                )
                >= 0.70,
                "leave_best_3_delta_vs_c3_top10_non_negative": _finite(
                    top10.get("leave_best_3_mean_net_excess_delta"),
                    name="leave_best_3_mean_net_excess_delta",
                )
                >= 0.0,
            }
            diagnostic_passed = all(diagnostic_gates.values())
            predictive_gate = bool(v31_gate_by_model.get(model, False))
            promotion_passed = diagnostic_passed and predictive_gate
            failed = [
                name for name, value in diagnostic_gates.items() if not value
            ]
            if not predictive_gate:
                failed.append("v31_predictive_gate_not_passed_or_posthoc_policy")
            decisions.append(
                {
                    "model": model,
                    "breadth": breadth,
                    "role": (
                        "POST_V31_REGIME_GATED_POLICY"
                        if model in {LOGIT_ON_C3_OFF, LOGIT_ON_RIDGE_OFF}
                        else "V31_SOURCE_MODEL"
                    ),
                    "challenger_worst_case_relative_total_return": worst,
                    "same_breadth_c3_worst_case_relative_total_return": (
                        c3_same_worst
                    ),
                    "c3_top10_worst_case_relative_total_return": c3_top10_worst,
                    "v31_predictive_gate_passed": predictive_gate,
                    **diagnostic_gates,
                    "portfolio_diagnostic_gate_passed": diagnostic_passed,
                    "v32_historical_promotion_gate_passed": promotion_passed,
                    "failed_v32_gates": "|".join(failed),
                    "post_selection_policy": model
                    in {LOGIT_ON_C3_OFF, LOGIT_ON_RIDGE_OFF},
                    "independent_holdout": False,
                    "research_eligible": False,
                    "live_capital_approved": False,
                    "actionable": False,
                }
            )

    passing_diagnostics = [
        row
        for row in decisions
        if row.get("role") != "BASELINE"
        and bool(row.get("portfolio_diagnostic_gate_passed"))
    ]
    if passing_diagnostics:
        recommendation = (
            "PAPER_OBSERVE_BEST_V32_POLICY_NO_HISTORICAL_PROMOTION"
        )
    else:
        recommendation = "KEEP_C3_AND_REDESIGN_REGIME_PORTFOLIO_POLICY"
    return decisions, recommendation


def _parse_int_list(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def run_v32(
    *,
    v31_artifact_zip: Path,
    v22_input_zip: Path,
    output_dir: Path,
    expected_v31_sha256: str | None = None,
    expected_input_sha256: str | None = None,
    breadths: Sequence[int] = DEFAULT_BREADTHS,
    replacement_caps: Sequence[int] = DEFAULT_REPLACEMENT_CAPS,
    validation_months: int = 6,
    test_months: int = 3,
    minimum_outer_test_periods: int = 48,
    bootstrap_repetitions: int = 2000,
    bootstrap_block_months: int = 3,
    seed: int = 20260803,
    broker_buy_fee_bps: float = 0.0,
    broker_sell_fee_bps: float = 0.0,
    exchange_buy_fee_bps: float = 2.7,
    exchange_sell_fee_bps: float = 2.7,
    sell_tax_bps: float = 10.0,
    transfer_fee_vnd_per_share: float = 0.3,
    transfer_reference_price_vnd: float = 10_000.0,
    slippage_bps: float = 5.0,
    stress_slippage_bps: float = 10.0,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V32_OUTPUT_EXISTS:{destination}")
    normalized_breadths = v30._normalize_breadths(breadths)
    normalized_caps = v30._normalize_caps(
        replacement_caps,
        maximum_breadth=min(normalized_breadths),
    )
    if validation_months < 3 or test_months < 1:
        raise ValueError("V32_NESTED_WINDOW_INVALID")
    if minimum_outer_test_periods < 12:
        raise ValueError("V32_MINIMUM_OUTER_TEST_TOO_SMALL")
    if bootstrap_repetitions < 100 or bootstrap_block_months < 1:
        raise ValueError("V32_BOOTSTRAP_CONFIG_INVALID")

    (
        v31_report,
        predictions,
        v31_decisions,
        v31_statistics,
        v31_metadata,
    ) = _load_v31_artifact(
        v31_artifact_zip,
        expected_sha256=expected_v31_sha256,
        expected_input_sha256=expected_input_sha256,
    )
    eligible_keys, regime_by_day, v22_metadata = _load_v22_policy_contract(
        v22_input_zip,
        expected_sha256=expected_input_sha256,
    )
    eligible_predictions, policy_metadata = _eligible_primary_predictions(
        predictions,
        eligible_keys=eligible_keys,
        regime_by_day=regime_by_day,
    )
    if (
        int(policy_metadata["minimum_eligible_symbol_count_per_month"])
        < max(normalized_breadths)
    ):
        raise ValueError(
            "V32_INSUFFICIENT_ELIGIBLE_SYMBOLS_FOR_MAX_BREADTH:"
            + json.dumps(policy_metadata, sort_keys=True)
        )

    cost = v13.DnseCashCostConfig(
        broker_buy_fee_bps=broker_buy_fee_bps,
        broker_sell_fee_bps=broker_sell_fee_bps,
        exchange_buy_fee_bps=exchange_buy_fee_bps,
        exchange_sell_fee_bps=exchange_sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        transfer_fee_vnd_per_share=transfer_fee_vnd_per_share,
        transfer_reference_price_vnd=transfer_reference_price_vnd,
        slippage_bps=slippage_bps,
        stress_slippage_bps=stress_slippage_bps,
    )

    (
        portfolio_rows,
        selection_rows,
        outer_rows,
        stress_rows,
        compact,
    ) = _portfolio_evaluations(
        eligible_predictions,
        breadths=normalized_breadths,
        replacement_caps=normalized_caps,
        validation_months=validation_months,
        test_months=test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        cost=cost,
    )
    paired_rows = _paired_comparisons(
        outer_rows,
        breadths=normalized_breadths,
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_months=bootstrap_block_months,
        seed=seed,
    )
    v31_gate_by_model = _v31_gate_map(v31_decisions)
    decision_rows, recommendation = _decision_rows(
        portfolio_rows,
        paired_rows,
        breadths=normalized_breadths,
        v31_gate_by_model=v31_gate_by_model,
    )

    destination.mkdir(parents=True)
    try:
        outputs = {
            "eligible_predictions_v32.csv": eligible_predictions,
            "portfolio_comparison_v32.csv": portfolio_rows,
            "policy_selection_v32.csv": selection_rows,
            "outer_test_periods_v32.csv": outer_rows,
            "outer_test_stress_periods_v32.csv": stress_rows,
            "paired_portfolio_comparison_v32.csv": paired_rows,
            "decision_gates_v32.csv": decision_rows,
        }
        for name, rows in outputs.items():
            _write_csv(destination / name, rows)

        diagnostic_passing = [
            {
                "model": str(row.get("model") or ""),
                "breadth": int(row.get("breadth", 0) or 0),
            }
            for row in decision_rows
            if row.get("role") != "BASELINE"
            and bool(row.get("portfolio_diagnostic_gate_passed"))
        ]
        promotion_passing = [
            {
                "model": str(row.get("model") or ""),
                "breadth": int(row.get("breadth", 0) or 0),
            }
            for row in decision_rows
            if bool(row.get("v32_historical_promotion_gate_passed"))
        ]
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "experiment": (
                "POST_V31_ELIGIBILITY_RESTORED_REGIME_POLICY_PORTFOLIO_ABLATION"
            ),
            "source_v31": v31_metadata,
            "source_v31_report_schema": v31_report.get("schema_version"),
            "source_v31_primary_protocol": dict(
                v31_report.get("primary_protocol") or {}
            ).get("name"),
            "source_v31_recommendation": v31_report.get("recommendation"),
            "source_v31_statistical_row_count": len(v31_statistics),
            "source_v22": v22_metadata,
            "policy_input_audit": policy_metadata,
            "candidate_models": list(CANDIDATE_MODELS),
            "source_models": list(SOURCE_MODELS),
            "regime_gated_models": [
                LOGIT_ON_C3_OFF,
                LOGIT_ON_RIDGE_OFF,
            ],
            "breadths": list(normalized_breadths),
            "replacement_caps": list(normalized_caps),
            "nested_validation_months": validation_months,
            "nested_test_months": test_months,
            "minimum_outer_test_periods": minimum_outer_test_periods,
            "bootstrap_repetitions": bootstrap_repetitions,
            "bootstrap_block_months": bootstrap_block_months,
            "cost_contract": cost.as_contract(),
            "portfolio_results": compact,
            "diagnostic_passing_policies": diagnostic_passing,
            "historical_promotion_passing_policies": promotion_passing,
            "recommendation": recommendation,
            "portfolio_return_proxy_after_modeled_costs_computed": True,
            "portfolio_pnl_after_costs_computed": True,
            "exact_cash_ledger_pnl_computed": False,
            "return_basis": (
                "EQUAL_WEIGHT_MONTHLY_LABEL_RETURN_PROXY_WITH_TURNOVER_COSTS"
            ),
            "stock_return_source": "V22_FORWARD_LABEL_RETURN",
            "benchmark_return_source": "V22_FORWARD_VNINDEX_LABEL_RETURN",
            "portfolio_eligibility_restored_from_v22": True,
            "ma250_liquidity_open_t1_eligibility_filter_applied": True,
            "exact_t1_open_execution_price_applied": False,
            "lot_size_100_applied": False,
            "inverse_volatility_allocation_applied": False,
            "single_name_cap_15_percent_applied": False,
            "sector_cap_25_percent_applied": False,
            "sector_data_available": False,
            "corporate_actions_complete": False,
            "exact_execution_cost_claimed": False,
            "predictive_models_retrained": False,
            "replacement_cap_selected_only_from_prior_validation": True,
            "breadth_selected_after_outer_review": True,
            "post_selection_sensitivity_analysis": True,
            "independent_holdout": False,
            "future_holdout_clock_reset": False,
            "technical_validation_only": True,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "actionable": False,
            "data_blockers_unchanged": list(
                v31_report.get("data_blockers_unchanged", [])
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
        prog="python -m he_thong_dinh_luong.portfolio_ablation_v32"
    )
    parser.add_argument("--v31-artifact-zip", type=Path, required=True)
    parser.add_argument("--v22-input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v31-sha256")
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
    parser.add_argument("--seed", type=int, default=20260803)
    parser.add_argument("--broker-buy-fee-bps", type=float, default=0.0)
    parser.add_argument("--broker-sell-fee-bps", type=float, default=0.0)
    parser.add_argument("--exchange-buy-fee-bps", type=float, default=2.7)
    parser.add_argument("--exchange-sell-fee-bps", type=float, default=2.7)
    parser.add_argument("--sell-tax-bps", type=float, default=10.0)
    parser.add_argument(
        "--transfer-fee-vnd-per-share",
        type=float,
        default=0.3,
    )
    parser.add_argument(
        "--transfer-reference-price-vnd",
        type=float,
        default=10_000.0,
    )
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--stress-slippage-bps", type=float, default=10.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_v32(
            v31_artifact_zip=args.v31_artifact_zip,
            v22_input_zip=args.v22_input_zip,
            output_dir=args.output_dir,
            expected_v31_sha256=args.expected_v31_sha256,
            expected_input_sha256=args.expected_input_sha256,
            breadths=args.breadths,
            replacement_caps=args.replacement_caps,
            validation_months=args.validation_months,
            test_months=args.test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            seed=args.seed,
            broker_buy_fee_bps=args.broker_buy_fee_bps,
            broker_sell_fee_bps=args.broker_sell_fee_bps,
            exchange_buy_fee_bps=args.exchange_buy_fee_bps,
            exchange_sell_fee_bps=args.exchange_sell_fee_bps,
            sell_tax_bps=args.sell_tax_bps,
            transfer_fee_vnd_per_share=args.transfer_fee_vnd_per_share,
            transfer_reference_price_vnd=args.transfer_reference_price_vnd,
            slippage_bps=args.slippage_bps,
            stress_slippage_bps=args.stress_slippage_bps,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                    "live_capital_approved": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "output_dir": result["output_dir"],
                "diagnostic_passing_policies": result[
                    "diagnostic_passing_policies"
                ],
                "historical_promotion_passing_policies": result[
                    "historical_promotion_passing_policies"
                ],
                "recommendation": result["recommendation"],
                "portfolio_pnl_after_costs_computed": True,
                "exact_cash_ledger_pnl_computed": False,
                "live_capital_approved": False,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "FROZEN_MODEL",
    "RIDGE_REGIME_MODEL",
    "LOGIT_MODEL",
    "LOGIT_ON_C3_OFF",
    "LOGIT_ON_RIDGE_OFF",
    "CANDIDATE_MODELS",
    "_load_v31_artifact",
    "_load_v22_policy_contract",
    "_eligible_primary_predictions",
    "run_v32",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
