"""Compatibility runner for the canonical V22 input used by V31.

V22 serializes boolean features as ``true``/``false``.  The original V31
loader delegated every model field to ``float(value)``, which rejected the
boolean market-regime field and consequently removed every otherwise valid
row.  This runner preserves the V31 experiment while parsing canonical boolean
feature values as 1.0/0.0 and exposing field-level exclusion diagnostics.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date
import io
import json
from pathlib import Path
from typing import Sequence
import zipfile

from . import all_history_protocol_v31 as core
from . import all_history_protocol_v31_safe_runner as safe
from . import component_breadth_ablation_v27 as v27

BOOLEAN_TRUE = {"1", "true", "yes", "y"}
BOOLEAN_FALSE = {"0", "false", "no", "n"}


def _finite_feature(value: object, *, name: str) -> float:
    """Parse numeric and canonical CSV boolean feature values."""
    text = str(value or "").strip().lower()
    if text in BOOLEAN_TRUE:
        return 1.0
    if text in BOOLEAN_FALSE:
        return 0.0
    return v27._finite(value, name=name)


def _load_all_history_zip_compatible(
    path: Path,
) -> tuple[list[v27.ResearchRow], dict[str, object], dict[str, object]]:
    """Load all feature/label-complete rows without portfolio filtering."""
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError("V31_INPUT_ZIP_NOT_FOUND")

    exclusions: Counter[str] = Counter()
    invalid_fields: Counter[str] = Counter()
    raw_dates: list[date] = []
    portfolio_eligible_raw = 0
    above_ma250_trainable = 0
    below_ma250_trainable = 0
    portfolio_eligible_trainable = 0
    raw_feature_row_count = 0

    with zipfile.ZipFile(source) as archive:
        required = {"feature_raw.csv", "nhan.csv", "manifest.json"}
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError(
                "V31_INPUT_FILES_MISSING:" + "|".join(sorted(missing))
            )
        manifest = json.loads(
            archive.read("manifest.json").decode("utf-8-sig")
        )
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
                    raise ValueError(
                        f"V31_DUPLICATE_LABEL_KEY:{key[0]}:{key[1]}"
                    )
                labels[key] = dict(label)

        rows: list[v27.ResearchRow] = []
        seen_features: set[tuple[str, str]] = set()
        with archive.open("feature_raw.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            )
            for feature_row in reader:
                raw_feature_row_count += 1
                raw_day = core._date_or_none(feature_row.get("ngay"))
                if raw_day is not None:
                    raw_dates.append(raw_day)
                if core._truthy(feature_row.get("eligible")):
                    portfolio_eligible_raw += 1

                key = (
                    str(feature_row.get("ngay") or ""),
                    str(feature_row.get("ma") or "").upper(),
                )
                if key in seen_features:
                    raise ValueError(
                        f"V31_DUPLICATE_FEATURE_KEY:{key[0]}:{key[1]}"
                    )
                seen_features.add(key)

                if not core._truthy(feature_row.get("hop_le")):
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

                invalid_field = ""
                try:
                    features: dict[str, float] = {}
                    for name in core.MODEL_FEATURE_FIELDS:
                        invalid_field = name
                        features[name] = _finite_feature(
                            feature_row.get(name),
                            name=name,
                        )
                    invalid_field = "signal_or_label"
                    row = v27.ResearchRow(
                        signal_day=v27._parse_date(
                            feature_row.get("ngay"),
                            name="ngay",
                        ),
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
                    invalid_fields[invalid_field or "unknown"] += 1
                    continue

                rows.append(row)
                if core._truthy(feature_row.get("eligible")):
                    portfolio_eligible_trainable += 1
                if core._truthy(feature_row.get("gia_tren_ma250")):
                    above_ma250_trainable += 1
                else:
                    below_ma250_trainable += 1

    rows.sort(key=lambda item: (item.signal_day, item.symbol))
    raw_dates_sorted = sorted(set(raw_dates))
    trainable_dates = sorted({row.signal_day for row in rows})

    coverage: dict[str, object] = {
        "schema_version": "training_coverage_audit_v31_boolean_compat",
        "input_zip": str(source),
        "input_zip_sha256": core._sha256(source),
        "raw_feature_row_count": raw_feature_row_count,
        "raw_first_signal_date": (
            raw_dates_sorted[0].isoformat() if raw_dates_sorted else None
        ),
        "raw_last_signal_date": (
            raw_dates_sorted[-1].isoformat() if raw_dates_sorted else None
        ),
        "raw_signal_month_count": len(raw_dates_sorted),
        "label_row_count": len(labels),
        "model_trainable_row_count": len(rows),
        "model_trainable_first_signal_date": (
            trainable_dates[0].isoformat() if trainable_dates else None
        ),
        "model_trainable_last_signal_date": (
            trainable_dates[-1].isoformat() if trainable_dates else None
        ),
        "model_trainable_signal_month_count": len(trainable_dates),
        "portfolio_eligible_raw_row_count": portfolio_eligible_raw,
        "portfolio_eligible_trainable_row_count": (
            portfolio_eligible_trainable
        ),
        "non_portfolio_eligible_trainable_row_count": (
            len(rows) - portfolio_eligible_trainable
        ),
        "above_ma250_trainable_row_count": above_ma250_trainable,
        "below_or_not_above_ma250_trainable_row_count": (
            below_ma250_trainable
        ),
        "exclusion_reason_counts": dict(sorted(exclusions.items())),
        "invalid_model_field_counts": dict(sorted(invalid_fields.items())),
        "boolean_feature_encoding": "true_false_to_1_0",
        "model_trainable_contract": (
            "FEATURE_COMPLETE_AND_LABEL_COMPLETE_REQUIRED;"
            "PORTFOLIO_ELIGIBILITY_NOT_REQUIRED"
        ),
        "portfolio_eligibility_used_as_training_filter": False,
        "below_ma250_rows_allowed_in_training": True,
        "liquidity_filter_used_as_training_filter": False,
        "open_t1_filter_used_as_training_filter": False,
    }

    if not rows:
        raise ValueError(
            "V31_NO_MODEL_TRAINABLE_ROWS:"
            + json.dumps(
                {
                    "exclusions": coverage["exclusion_reason_counts"],
                    "invalid_fields": coverage["invalid_model_field_counts"],
                    "raw_feature_rows": raw_feature_row_count,
                    "labels": len(labels),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
    return rows, manifest, coverage


def main(argv: Sequence[str] | None = None) -> int:
    core._load_all_history_zip = _load_all_history_zip_compatible
    return safe.main(argv)


__all__ = [
    "_finite_feature",
    "_load_all_history_zip_compatible",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
