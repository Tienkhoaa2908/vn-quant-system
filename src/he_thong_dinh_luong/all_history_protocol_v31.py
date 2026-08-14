"""V31 all-history protocol comparison.

The primary protocol is an expanding, purged walk-forward evaluation. A
secondary diagnostic implements the user's seven-month pooled holdout idea:
each complete seven-month block contributes six months to the final training
pool and one locked month to a test pool; the estimators are fitted once and
score the complete locked test pool once.

The pooled holdout is intentionally labelled non-chronological because later
training blocks can occur after earlier test blocks. It is a robustness
benchmark, not deployable historical P&L evidence. Both protocols train from
feature-complete, label-complete rows regardless of portfolio eligibility, so
MA250 regime, liquidity and T+1 execution policy do not discard otherwise
trainable model observations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path
from typing import Mapping, Sequence
import zipfile

from . import component_breadth_ablation_v27 as v27
from . import factor_diagnostics_v26 as factor_v26
from . import predictive_target_lab_v29 as v29

SCHEMA_VERSION = "all_history_protocol_v31"
REPORT_FILE = "all_history_protocol_v31.json"
COVERAGE_JSON_FILE = "training_coverage_audit_v31.json"
PRIMARY_PROTOCOL = "EXPANDING_PURGED_WALK_FORWARD_ALL_TRAINABLE_HISTORY"
POOLED_PROTOCOL = "POOLED_7_MONTH_6_TRAIN_1_TEST_SINGLE_FIT_DIAGNOSTIC"
MODEL_FEATURE_FIELDS = (
    "dong_luong_12_1",
    "bien_dong_60",
    "suc_manh_tuong_doi_120",
    "khoang_cach_ma60",
    "khoang_cach_ma120",
    "khoang_cach_ma250",
    "loi_nhuan_20",
    "loi_nhuan_60",
    "loi_nhuan_120",
    "loi_nhuan_250",
    "ty_le_dinh_52_tuan",
    "vnindex_tren_ma250",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if not rows and not fields:
        return
    fieldnames = list(fields or rows[0].keys())
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _date_or_none(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _load_all_history_zip(
    path: Path,
) -> tuple[list[v27.ResearchRow], dict[str, object], dict[str, object]]:
    """Load model-trainable rows without applying portfolio eligibility."""
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError("V31_INPUT_ZIP_NOT_FOUND")

    exclusions: Counter[str] = Counter()
    raw_dates: list[date] = []
    portfolio_eligible_raw = 0
    above_ma250_trainable = 0
    below_ma250_trainable = 0
    portfolio_eligible_trainable = 0

    with zipfile.ZipFile(source) as archive:
        required = {"feature_raw.csv", "nhan.csv", "manifest.json"}
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError("V31_INPUT_FILES_MISSING:" + "|".join(sorted(missing)))
        manifest = json.loads(archive.read("manifest.json").decode("utf-8-sig"))
        if not isinstance(manifest, dict):
            raise ValueError("V31_INPUT_MANIFEST_OBJECT_REQUIRED")

        labels: dict[tuple[str, str], dict[str, str]] = {}
        with archive.open("nhan.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            )
            for label in reader:
                key = (
                    str(label.get("ngay") or ""),
                    str(label.get("ma") or "").upper(),
                )
                if key in labels:
                    raise ValueError(f"V31_DUPLICATE_LABEL_KEY:{key[0]}:{key[1]}")
                labels[key] = dict(label)

        rows: list[v27.ResearchRow] = []
        seen_features: set[tuple[str, str]] = set()
        raw_feature_row_count = 0
        with archive.open("feature_raw.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            )
            for feature_row in reader:
                raw_feature_row_count += 1
                raw_day = _date_or_none(feature_row.get("ngay"))
                if raw_day is not None:
                    raw_dates.append(raw_day)
                if _truthy(feature_row.get("eligible")):
                    portfolio_eligible_raw += 1
                key = (
                    str(feature_row.get("ngay") or ""),
                    str(feature_row.get("ma") or "").upper(),
                )
                if key in seen_features:
                    raise ValueError(f"V31_DUPLICATE_FEATURE_KEY:{key[0]}:{key[1]}")
                seen_features.add(key)

                if not _truthy(feature_row.get("hop_le")):
                    exclusions["FEATURE_NOT_COMPLETE"] += 1
                    continue
                label = labels.get(key)
                if label is None:
                    exclusions["LABEL_MISSING"] += 1
                    continue
                required_label = (
                    label.get("ngay_ket_thuc_nhan"),
                    label.get("loi_nhuan_co_phieu"),
                    label.get("loi_nhuan_benchmark"),
                    label.get("loi_nhuan_tuong_doi"),
                )
                if any(value in (None, "") for value in required_label):
                    exclusions["LABEL_INCOMPLETE"] += 1
                    continue
                try:
                    features = {
                        name: v27._finite(feature_row.get(name), name=name)
                        for name in MODEL_FEATURE_FIELDS
                    }
                    row = v27.ResearchRow(
                        signal_day=v27._parse_date(feature_row.get("ngay"), name="ngay"),
                        symbol=str(feature_row.get("ma") or "").upper(),
                        label_end=v27._parse_date(
                            label.get("ngay_ket_thuc_nhan"),
                            name="ngay_ket_thuc_nhan",
                        ),
                        stock_return=v27._finite(
                            label.get("loi_nhuan_co_phieu"),
                            name="loi_nhuan_co_phieu",
                        ),
                        benchmark_return=v27._finite(
                            label.get("loi_nhuan_benchmark"),
                            name="loi_nhuan_benchmark",
                        ),
                        relative_return=v27._finite(
                            label.get("loi_nhuan_tuong_doi"),
                            name="loi_nhuan_tuong_doi",
                        ),
                        features=features,
                    )
                except ValueError:
                    exclusions["MODEL_FIELD_INVALID"] += 1
                    continue

                rows.append(row)
                if _truthy(feature_row.get("eligible")):
                    portfolio_eligible_trainable += 1
                if _truthy(feature_row.get("gia_tren_ma250")):
                    above_ma250_trainable += 1
                else:
                    below_ma250_trainable += 1

    rows.sort(key=lambda item: (item.signal_day, item.symbol))
    if not rows:
        raise ValueError("V31_NO_MODEL_TRAINABLE_ROWS")
    trainable_dates = sorted({row.signal_day for row in rows})
    raw_dates_sorted = sorted(set(raw_dates))
    coverage = {
        "schema_version": "training_coverage_audit_v31",
        "input_zip": str(source),
        "input_zip_sha256": _sha256(source),
        "raw_feature_row_count": raw_feature_row_count,
        "raw_first_signal_date": raw_dates_sorted[0].isoformat() if raw_dates_sorted else None,
        "raw_last_signal_date": raw_dates_sorted[-1].isoformat() if raw_dates_sorted else None,
        "raw_signal_month_count": len(raw_dates_sorted),
        "label_row_count": len(labels),
        "model_trainable_row_count": len(rows),
        "model_trainable_first_signal_date": trainable_dates[0].isoformat(),
        "model_trainable_last_signal_date": trainable_dates[-1].isoformat(),
        "model_trainable_signal_month_count": len(trainable_dates),
        "portfolio_eligible_raw_row_count": portfolio_eligible_raw,
        "portfolio_eligible_trainable_row_count": portfolio_eligible_trainable,
        "non_portfolio_eligible_trainable_row_count": len(rows) - portfolio_eligible_trainable,
        "above_ma250_trainable_row_count": above_ma250_trainable,
        "below_or_not_above_ma250_trainable_row_count": below_ma250_trainable,
        "exclusion_reason_counts": dict(sorted(exclusions.items())),
        "model_trainable_contract": (
            "FEATURE_COMPLETE_AND_LABEL_COMPLETE_REQUIRED;"
            "PORTFOLIO_ELIGIBILITY_NOT_REQUIRED"
        ),
        "portfolio_eligibility_used_as_training_filter": False,
        "below_ma250_rows_allowed_in_training": True,
        "liquidity_filter_used_as_training_filter": False,
        "open_t1_filter_used_as_training_filter": False,
    }
    return rows, manifest, coverage


def _date_bounds(rows: Sequence[v27.ResearchRow]) -> tuple[str | None, str | None, int]:
    dates = sorted({row.signal_day for row in rows})
    if not dates:
        return None, None, 0
    return dates[0].isoformat(), dates[-1].isoformat(), len(dates)


def _primary_fold_audit(
    rows: Sequence[v27.ResearchRow],
    folds: Sequence[v27.Fold],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for index, fold in enumerate(folds, start=1):
        candidate_prior = [
            row
            for row in rows
            if row.signal_day < fold.test_day and row.label_end < fold.test_day
        ]
        assigned_keys = {
            (row.signal_day, row.symbol)
            for row in tuple(fold.train_rows) + tuple(fold.validation_rows)
        }
        purged = [
            row
            for row in candidate_prior
            if (row.signal_day, row.symbol) not in assigned_keys
        ]
        train_first, train_last, train_months = _date_bounds(fold.train_rows)
        val_first, val_last, val_months = _date_bounds(fold.validation_rows)
        output.append({
            "protocol": PRIMARY_PROTOCOL,
            "fold_number": index,
            "test_date": fold.test_day.isoformat(),
            "train_first_date": train_first,
            "train_last_date": train_last,
            "train_month_count": train_months,
            "train_row_count": len(fold.train_rows),
            "validation_first_date": val_first,
            "validation_last_date": val_last,
            "validation_month_count": val_months,
            "validation_row_count": len(fold.validation_rows),
            "test_row_count": len(fold.test_rows),
            "candidate_prior_row_count": len(candidate_prior),
            "purged_row_count": len(purged),
            "final_refit_row_count": len(fold.train_rows) + len(fold.validation_rows),
            "test_rows_used_for_fit": False,
            "future_rows_used_for_fit": False,
            "all_rows_permitted_by_purge_used": True,
        })
    return output


def build_pooled_seven_month_split(
    rows: Sequence[v27.ResearchRow],
    *,
    block_months: int = 7,
    test_slot: int = 7,
    validation_slot: int = 6,
) -> tuple[
    tuple[v27.ResearchRow, ...],
    tuple[v27.ResearchRow, ...],
    tuple[v27.ResearchRow, ...],
    list[dict[str, object]],
    dict[str, object],
]:
    if block_months < 3:
        raise ValueError("V31_BLOCK_MONTHS_TOO_SMALL")
    if not 1 <= test_slot <= block_months:
        raise ValueError("V31_TEST_SLOT_OUT_OF_RANGE")
    if not 1 <= validation_slot <= block_months:
        raise ValueError("V31_VALIDATION_SLOT_OUT_OF_RANGE")
    if test_slot == validation_slot:
        raise ValueError("V31_TEST_AND_VALIDATION_SLOT_MUST_DIFFER")

    dates = sorted({row.signal_day for row in rows})
    full_block_count = len(dates) // block_months
    if full_block_count < 3:
        raise ValueError("V31_TOO_FEW_COMPLETE_SEVEN_MONTH_BLOCKS")

    fit_train_dates: set[date] = set()
    validation_dates: set[date] = set()
    test_dates: set[date] = set()
    block_rows: list[dict[str, object]] = []
    for block_index in range(full_block_count):
        block = dates[block_index * block_months:(block_index + 1) * block_months]
        block_test = block[test_slot - 1]
        block_validation = block[validation_slot - 1]
        block_fit_train = [
            day for day in block
            if day not in {block_test, block_validation}
        ]
        fit_train_dates.update(block_fit_train)
        validation_dates.add(block_validation)
        test_dates.add(block_test)
        block_rows.append({
            "protocol": POOLED_PROTOCOL,
            "block_number": block_index + 1,
            "block_first_date": block[0].isoformat(),
            "block_last_date": block[-1].isoformat(),
            "fit_train_dates": "|".join(day.isoformat() for day in block_fit_train),
            "internal_validation_date": block_validation.isoformat(),
            "locked_test_date": block_test.isoformat(),
            "final_train_month_count_in_block": block_months - 1,
            "test_month_count_in_block": 1,
        })

    remainder_dates = dates[full_block_count * block_months:]
    fit_train_dates.update(remainder_dates)
    for day in remainder_dates:
        block_rows.append({
            "protocol": POOLED_PROTOCOL,
            "block_number": "REMAINDER_TO_FINAL_TRAIN",
            "block_first_date": day.isoformat(),
            "block_last_date": day.isoformat(),
            "fit_train_dates": day.isoformat(),
            "internal_validation_date": "",
            "locked_test_date": "",
            "final_train_month_count_in_block": 1,
            "test_month_count_in_block": 0,
        })

    train_rows = tuple(row for row in rows if row.signal_day in fit_train_dates)
    validation_rows = tuple(row for row in rows if row.signal_day in validation_dates)
    test_rows = tuple(row for row in rows if row.signal_day in test_dates)
    final_train_dates = fit_train_dates | validation_dates
    if final_train_dates & test_dates:
        raise ValueError("V31_POOLED_TRAIN_TEST_OVERLAP")
    if final_train_dates | test_dates != set(dates):
        raise ValueError("V31_POOLED_SPLIT_DID_NOT_USE_ALL_MONTHS")

    summary = {
        "protocol": POOLED_PROTOCOL,
        "block_months": block_months,
        "test_slot_one_based": test_slot,
        "internal_validation_slot_one_based": validation_slot,
        "complete_block_count": full_block_count,
        "remainder_month_count_assigned_to_final_train": len(remainder_dates),
        "fit_train_month_count_before_refit": len(fit_train_dates),
        "internal_validation_month_count": len(validation_dates),
        "final_train_month_count_after_refit": len(final_train_dates),
        "locked_test_month_count": len(test_dates),
        "all_input_months_used_exactly_once_in_final_train_or_test": True,
        "single_fit_after_hyperparameter_selection": True,
        "test_pool_locked_before_fit": True,
        "test_labels_used_for_fit_or_selection": False,
        "chronological_deployment_simulation": False,
        "future_relative_to_some_test_months_can_exist_in_train": True,
        "deployable_historical_pnl_claim": False,
    }
    return train_rows, validation_rows, test_rows, block_rows, summary


def _cross_sectional_percentiles(
    rows: Sequence[v27.ResearchRow],
    values: Sequence[float],
) -> list[float]:
    if len(rows) != len(values):
        raise ValueError("V31_PERCENTILE_LENGTH_MISMATCH")
    output = [0.0] * len(rows)
    by_day: dict[date, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_day[row.signal_day].append(index)
    for indices in by_day.values():
        ranked = v27.average_percentile([float(values[index]) for index in indices])
        for index, value in zip(indices, ranked):
            output[index] = float(value)
    return output


def _pooled_frozen_scores(
    history_rows: Sequence[v27.ResearchRow],
    test_rows: Sequence[v27.ResearchRow],
) -> tuple[list[float], dict[str, float]]:
    weights = v27.shrunk_component_weights(history_rows)
    scores = [0.0] * len(test_rows)
    by_day: dict[date, list[int]] = defaultdict(list)
    for index, row in enumerate(test_rows):
        by_day[row.signal_day].append(index)
    for indices in by_day.values():
        ranked = v27._ranked_components([test_rows[index] for index in indices])
        for index, components in zip(indices, ranked):
            scores[index] = sum(
                weights[name] * components[name]
                for name in v27.STABLE_THREE
            )
    return scores, weights


def _prediction_rows(
    rows: Sequence[v27.ResearchRow],
    model_scores: Mapping[str, Sequence[float]],
    *,
    protocol: str,
    fold_prefix: str,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    by_day: dict[date, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_day[row.signal_day].append(index)
    for model, scores in model_scores.items():
        if len(scores) != len(rows):
            raise ValueError(f"V31_SCORE_LENGTH_MISMATCH:{model}")
        for day, indices in sorted(by_day.items()):
            ordered = sorted(
                indices,
                key=lambda index: (-float(scores[index]), rows[index].symbol),
            )
            rank = {index: position + 1 for position, index in enumerate(ordered)}
            percentiles = v27.average_percentile(
                [float(scores[index]) for index in indices]
            )
            percentile_by_index = {
                index: float(value)
                for index, value in zip(indices, percentiles)
            }
            for index in indices:
                row = rows[index]
                output.append({
                    "protocol": protocol,
                    "model": model,
                    "fold": f"{fold_prefix}_{day.isoformat()}",
                    "test_date": day.isoformat(),
                    "symbol": row.symbol,
                    "score": float(scores[index]),
                    "percentile": percentile_by_index[index],
                    "rank": rank[index],
                    "selected_top_k": "false",
                    "label_end": row.label_end.isoformat(),
                    "stock_return": row.stock_return,
                    "benchmark_return": row.benchmark_return,
                    "relative_return": row.relative_return,
                })
    return output


def build_pooled_predictions(
    train_rows: Sequence[v27.ResearchRow],
    validation_rows: Sequence[v27.ResearchRow],
    test_rows: Sequence[v27.ResearchRow],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    history = tuple(train_rows) + tuple(validation_rows)
    frozen, weights = _pooled_frozen_scores(history, test_rows)
    ridge, ridge_meta = v29._fit_ridge(
        train_rows,
        validation_rows,
        test_rows,
        regime_interactions=False,
    )
    ridge_regime, ridge_regime_meta = v29._fit_ridge(
        train_rows,
        validation_rows,
        test_rows,
        regime_interactions=True,
    )
    safe, safe_meta = v29._fit_bottom_logistic(
        train_rows,
        validation_rows,
        test_rows,
    )
    ridge_rank = _cross_sectional_percentiles(test_rows, ridge)
    safe_rank = _cross_sectional_percentiles(test_rows, safe)
    hybrid = [
        0.5 * left + 0.5 * right
        for left, right in zip(ridge_rank, safe_rank)
    ]
    model_scores = {
        v29.FROZEN_MODEL: frozen,
        v29.RIDGE_MODEL: ridge,
        v29.RIDGE_REGIME_MODEL: ridge_regime,
        v29.BOTTOM_MODEL: safe,
        v29.HYBRID_MODEL: hybrid,
    }
    predictions = _prediction_rows(
        test_rows,
        model_scores,
        protocol=POOLED_PROTOCOL,
        fold_prefix="pooled7",
    )
    metadata = [
        {
            "protocol": POOLED_PROTOCOL,
            "model": v29.FROZEN_MODEL,
            "fit_count": 0,
            "adaptive_weights": json.dumps(weights, sort_keys=True),
            "single_final_fit": False,
            "uses_test_labels": False,
        },
        {
            "protocol": POOLED_PROTOCOL,
            "model": v29.RIDGE_MODEL,
            "fit_count": len(v29.RIDGE_ALPHAS) + 1,
            "single_final_fit": True,
            **ridge_meta,
        },
        {
            "protocol": POOLED_PROTOCOL,
            "model": v29.RIDGE_REGIME_MODEL,
            "fit_count": len(v29.RIDGE_ALPHAS) + 1,
            "single_final_fit": True,
            **ridge_regime_meta,
        },
        {
            "protocol": POOLED_PROTOCOL,
            "model": v29.BOTTOM_MODEL,
            "fit_count": len(v29.LOGISTIC_CS) + 1,
            "single_final_fit": True,
            **safe_meta,
        },
        {
            "protocol": POOLED_PROTOCOL,
            "model": v29.HYBRID_MODEL,
            "fit_count": 0,
            "single_final_fit": False,
            "rank_weight": 0.5,
            "bottom_safe_weight": 0.5,
            "uses_test_labels": False,
        },
    ]
    return predictions, metadata


def _diagnostic_folds_for_test_rows(
    test_rows: Sequence[v27.ResearchRow],
) -> list[v27.Fold]:
    by_day: dict[date, list[v27.ResearchRow]] = defaultdict(list)
    for row in test_rows:
        by_day[row.signal_day].append(row)
    return [
        v27.Fold(
            test_day=day,
            train_rows=(),
            validation_rows=(),
            test_rows=tuple(sorted(day_rows, key=lambda row: row.symbol)),
        )
        for day, day_rows in sorted(by_day.items())
    ]


def _add_protocol(
    rows: Sequence[Mapping[str, object]],
    protocol: str,
) -> list[dict[str, object]]:
    return [{"protocol": protocol, **dict(row)} for row in rows]


def _run_diagnostics(
    predictions: Sequence[Mapping[str, object]],
    folds: Sequence[v27.Fold],
    *,
    protocol: str,
    bootstrap_repetitions: int,
    bootstrap_block_months: int,
    effective_trials: int,
    seed: int,
) -> dict[str, object]:
    diagnostics = factor_v26.analyze_predictions(
        predictions,
        quantiles=5,
        top_k=10,
        rolling_months=12,
    )
    statistical, comparisons = v29._statistical_rows(
        diagnostics,
        folds,
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_months=bootstrap_block_months,
        effective_trials=effective_trials,
        seed=seed,
    )
    decisions, recommendation = v29._decision_rows(statistical, comparisons)
    return {
        "summary_rows": _add_protocol(diagnostics["summary_rows"], protocol),
        "period_rows": _add_protocol(diagnostics["period_rows"], protocol),
        "quantile_rows": _add_protocol(diagnostics["quantile_rows"], protocol),
        "statistical_rows": _add_protocol(statistical, protocol),
        "comparison_rows": _add_protocol(comparisons, protocol),
        "decision_rows": _add_protocol(decisions, protocol),
        "recommendation": recommendation,
    }


def _coverage_csv_rows(coverage: Mapping[str, object]) -> list[dict[str, object]]:
    rows = [
        {"metric": key, "value": value}
        for key, value in coverage.items()
        if key != "exclusion_reason_counts"
    ]
    for reason, count in dict(coverage.get("exclusion_reason_counts", {})).items():
        rows.append({"metric": f"excluded_{reason}", "value": count})
    return rows


def run_all_history_protocol_v31(
    *,
    input_zip: Path,
    output_dir: Path,
    evaluation_months: int = 132,
    minimum_train_months: int = 60,
    inner_validation_months: int = 3,
    pooled_block_months: int = 7,
    pooled_test_slot: int = 7,
    pooled_validation_slot: int = 6,
    bootstrap_repetitions: int = 2000,
    bootstrap_block_months: int = 3,
    effective_trials: int = v29.DEFAULT_EFFECTIVE_TRIALS,
    seed: int = 20260802,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V31_OUTPUT_EXISTS:{destination}")
    if effective_trials < 1:
        raise ValueError("V31_EFFECTIVE_TRIALS_INVALID")

    rows, input_manifest, coverage = _load_all_history_zip(source)
    primary_folds = v27.build_folds(
        rows,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        inner_validation_months=inner_validation_months,
    )
    primary_predictions, primary_selection = v29.build_predictions(primary_folds)
    primary_predictions = [
        {"protocol": PRIMARY_PROTOCOL, **row}
        for row in primary_predictions
    ]
    primary_selection = _add_protocol(primary_selection, PRIMARY_PROTOCOL)
    primary_diagnostics = _run_diagnostics(
        primary_predictions,
        primary_folds,
        protocol=PRIMARY_PROTOCOL,
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_months=bootstrap_block_months,
        effective_trials=effective_trials,
        seed=seed,
    )
    fold_audit = _primary_fold_audit(rows, primary_folds)

    (
        pooled_train,
        pooled_validation,
        pooled_test,
        pooled_blocks,
        pooled_summary,
    ) = build_pooled_seven_month_split(
        rows,
        block_months=pooled_block_months,
        test_slot=pooled_test_slot,
        validation_slot=pooled_validation_slot,
    )
    pooled_predictions, pooled_selection = build_pooled_predictions(
        pooled_train,
        pooled_validation,
        pooled_test,
    )
    pooled_folds = _diagnostic_folds_for_test_rows(pooled_test)
    pooled_diagnostics = _run_diagnostics(
        pooled_predictions,
        pooled_folds,
        protocol=POOLED_PROTOCOL,
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_months=bootstrap_block_months,
        effective_trials=effective_trials,
        seed=seed + 31000,
    )

    destination.mkdir(parents=True)
    try:
        _write_json(destination / COVERAGE_JSON_FILE, coverage)
        _write_csv(
            destination / "training_coverage_audit_v31.csv",
            _coverage_csv_rows(coverage),
        )
        _write_csv(destination / "primary_fold_coverage_v31.csv", fold_audit)
        _write_csv(destination / "pooled_7m_blocks_v31.csv", pooled_blocks)
        _write_csv(destination / "predictions_primary_v31.csv", primary_predictions)
        _write_csv(destination / "predictions_pooled7_v31.csv", pooled_predictions)
        _write_csv(
            destination / "hyperparameter_selection_v31.csv",
            primary_selection + pooled_selection,
        )
        _write_csv(
            destination / "factor_summary_v31.csv",
            primary_diagnostics["summary_rows"] + pooled_diagnostics["summary_rows"],
        )
        _write_csv(
            destination / "factor_periods_v31.csv",
            primary_diagnostics["period_rows"] + pooled_diagnostics["period_rows"],
        )
        _write_csv(
            destination / "factor_quantiles_v31.csv",
            primary_diagnostics["quantile_rows"] + pooled_diagnostics["quantile_rows"],
        )
        _write_csv(
            destination / "statistical_summary_v31.csv",
            primary_diagnostics["statistical_rows"] + pooled_diagnostics["statistical_rows"],
        )
        _write_csv(
            destination / "paired_comparison_v31.csv",
            primary_diagnostics["comparison_rows"] + pooled_diagnostics["comparison_rows"],
        )
        _write_csv(
            destination / "decision_gates_v31.csv",
            primary_diagnostics["decision_rows"] + pooled_diagnostics["decision_rows"],
        )
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "input_zip": str(source),
            "input_zip_sha256": _sha256(source),
            "input_manifest_schema": input_manifest.get("schema_version"),
            "output_dir": str(destination),
            "coverage": coverage,
            "primary_protocol": {
                "name": PRIMARY_PROTOCOL,
                "role": "PRIMARY_DEPLOYMENT_STYLE_RESEARCH_PROTOCOL",
                "fold_count": len(primary_folds),
                "first_test_date": primary_folds[0].test_day.isoformat(),
                "last_test_date": primary_folds[-1].test_day.isoformat(),
                "expanding_history": True,
                "purged_labels": True,
                "test_month_reused_only_in_later_folds_after_label_completion": True,
                "future_rows_used_for_past_prediction": False,
                "recommendation": primary_diagnostics["recommendation"],
            },
            "pooled_seven_month_protocol": {
                **pooled_summary,
                "role": "SECONDARY_NON_CHRONOLOGICAL_ROBUSTNESS_BENCHMARK",
                "test_first_date": min(row.signal_day for row in pooled_test).isoformat(),
                "test_last_date": max(row.signal_day for row in pooled_test).isoformat(),
                "recommendation": pooled_diagnostics["recommendation"],
            },
            "model_names": list(v29.MODEL_NAMES),
            "primary_protocol_is_selection_authority": True,
            "pooled_protocol_can_override_primary": False,
            "portfolio_pnl_after_costs_computed": False,
            "portfolio_pnl_reason": (
                "V31 compares predictive data-split protocols; portfolio P&L must be "
                "evaluated in a subsequent fixed policy ablation."
            ),
            "independent_holdout": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "recommendation": (
                "USE_EXPANDING_WALK_FORWARD_AS_PRIMARY_AND_KEEP_POOLED_7M_AS_"
                "SECONDARY_DIAGNOSTIC"
            ),
            "data_blockers_unchanged": [
                "PRICE_BASIS_CHUA_XAC_NHAN",
                "CORPORATE_ACTIONS_CHUA_DAY_DU",
                "CANDIDATE_UNION_IS_NOT_POINT_IN_TIME",
                "SURVIVORSHIP_BIAS_NOT_RESOLVED",
            ],
        }
        _write_json(destination / REPORT_FILE, report)
        return report
    except Exception:
        for child in sorted(destination.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        destination.rmdir()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.all_history_protocol_v31"
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-months", type=int, default=132)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--pooled-block-months", type=int, default=7)
    parser.add_argument("--pooled-test-slot", type=int, default=7)
    parser.add_argument("--pooled-validation-slot", type=int, default=6)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--bootstrap-block-months", type=int, default=3)
    parser.add_argument(
        "--effective-trials",
        type=int,
        default=v29.DEFAULT_EFFECTIVE_TRIALS,
    )
    parser.add_argument("--seed", type=int, default=20260802)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_all_history_protocol_v31(
            input_zip=args.input_zip,
            output_dir=args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            pooled_block_months=args.pooled_block_months,
            pooled_test_slot=args.pooled_test_slot,
            pooled_validation_slot=args.pooled_validation_slot,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            effective_trials=args.effective_trials,
            seed=args.seed,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=True, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report["status"],
        "output_dir": report["output_dir"],
        "primary_protocol": report["primary_protocol"]["name"],
        "primary_fold_count": report["primary_protocol"]["fold_count"],
        "pooled_test_month_count": report["pooled_seven_month_protocol"][
            "locked_test_month_count"
        ],
        "recommendation": report["recommendation"],
        "live_capital_approved": False,
    }, ensure_ascii=True, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "COVERAGE_JSON_FILE",
    "PRIMARY_PROTOCOL",
    "POOLED_PROTOCOL",
    "MODEL_FEATURE_FIELDS",
    "build_pooled_seven_month_split",
    "build_pooled_predictions",
    "run_all_history_protocol_v31",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
