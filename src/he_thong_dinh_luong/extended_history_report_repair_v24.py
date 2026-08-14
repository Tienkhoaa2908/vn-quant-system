"""Repair V23 summary metadata from an already-completed Model Lab run.

V23 correctly preserves a valid ``NO_MODEL_APPROVED`` outcome, but early V23
reports read several diagnostics from obsolete top-level summary keys.  Current
Model Lab stores them under ``walk_forward``, ``evaluations``,
``reference_diagnostic``, ``predictive_upgrade_v6`` and
``turnover_buffer_future_holdout``.  This module reconstructs a corrected report
without retraining or modifying any Model Lab artifact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import extended_history_reference_v23 as v23

SCHEMA_VERSION = "extended_history_report_repair_v24"
REPORT_FILE = "extended_history_reference_v24.json"


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"EXTENDED_HISTORY_JSON_OBJECT_REQUIRED:{path.name}")
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


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _successful_models(summary: Mapping[str, object]) -> list[str]:
    legacy = _string_list(summary.get("models_success"))
    if legacy:
        return sorted(set(legacy))
    evaluations = _mapping(summary.get("evaluations"))
    return sorted(
        str(model)
        for model, raw in evaluations.items()
        if str(_mapping(raw).get("status") or "") == "SUCCESS"
        and not _mapping(raw).get("error")
    )


def _failed_models(summary: Mapping[str, object]) -> dict[str, object]:
    legacy = summary.get("models_skipped_or_failed")
    if isinstance(legacy, dict) and legacy:
        return dict(legacy)
    failures = summary.get("failures")
    return dict(failures) if isinstance(failures, dict) else {}


def corrected_model_outcome(
    model_output: Path,
    *,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    output = Path(model_output).resolve()
    outcome = v23.verify_model_lab_outcome(
        output,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    summary = _read_json(output / "model_lab_summary.json")

    walk_forward = _mapping(summary.get("walk_forward"))
    reference = _mapping(summary.get("reference_diagnostic"))
    predictive_v6 = _mapping(summary.get("predictive_upgrade_v6"))
    future = _mapping(summary.get("turnover_buffer_future_holdout"))

    fold_count = int(
        walk_forward.get("fold_count")
        or summary.get("fold_count")
        or 0
    )
    models_success = _successful_models(summary)
    models_failed = _failed_models(summary)
    positive_models = _string_list(
        reference.get("positive_evidence_models")
        or summary.get("positive_evidence_models")
    )
    predictive_status = str(
        predictive_v6.get("reference_status")
        or summary.get("predictive_reference_status")
        or ""
    )
    reference_status = str(
        reference.get("status")
        or summary.get("reference_diagnostic_status")
        or ""
    )
    future_status = str(
        future.get("status")
        or summary.get("future_holdout_status")
        or ""
    )

    if fold_count < minimum_outer_test_periods:
        raise ValueError(
            f"EXTENDED_HISTORY_WALK_FORWARD_FOLDS_TOO_FEW:{fold_count}"
            f"<{minimum_outer_test_periods}"
        )
    if not models_success:
        raise ValueError("EXTENDED_HISTORY_NO_SUCCESSFUL_MODELS_RECORDED")

    return {
        **outcome,
        "fold_count": fold_count,
        "walk_forward_first_test_date": str(
            walk_forward.get("first_test_date") or ""
        ),
        "walk_forward_last_test_date": str(
            walk_forward.get("last_test_date") or ""
        ),
        "models_success": models_success,
        "models_skipped_or_failed": models_failed,
        "positive_evidence_models": positive_models,
        "predictive_reference_status": predictive_status,
        "reference_diagnostic_status": reference_status,
        "future_holdout_status": future_status,
    }


def repair_existing_output(
    output_root: Path,
    *,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    root = Path(output_root).resolve()
    if not root.is_dir():
        raise ValueError("EXTENDED_HISTORY_OUTPUT_ROOT_NOT_FOUND")
    source_report_path = root / v23.REPORT_FILE
    if not source_report_path.is_file():
        raise ValueError("EXTENDED_HISTORY_V23_REPORT_NOT_FOUND")
    model_output = root / "model-lab"
    if not model_output.is_dir():
        raise ValueError("EXTENDED_HISTORY_MODEL_OUTPUT_NOT_FOUND")

    source_report = _read_json(source_report_path)
    if str(source_report.get("status") or "") not in {
        "SUCCESS_APPROVED_REFERENCE",
        "SUCCESS_NO_MODEL_APPROVED",
    }:
        raise ValueError("EXTENDED_HISTORY_V23_REPORT_NOT_SUCCESSFUL")

    corrected = corrected_model_outcome(
        model_output,
        minimum_outer_test_periods=minimum_outer_test_periods,
    )
    report = {
        **source_report,
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(source_report.get("schema_version") or ""),
        "model_outcome": corrected,
        "metadata_repaired_without_retraining": True,
        "model_lab_artifacts_modified": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    destination = root / REPORT_FILE
    if destination.exists():
        raise FileExistsError(f"EXTENDED_HISTORY_V24_REPORT_EXISTS:{destination}")
    _write_json(destination, report)
    return {
        **report,
        "output_root": str(root),
        "report_path": str(destination),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.extended_history_report_repair_v24"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = repair_existing_output(
            args.output_root,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
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
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "corrected_model_outcome",
    "repair_existing_output",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
