from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from he_thong_dinh_luong.extended_history_report_repair_v24 import (
    corrected_model_outcome,
    repair_existing_output,
)


class ExtendedHistoryReportRepairV24Tests(unittest.TestCase):
    def _write_summary(self, model_output: Path) -> None:
        payload = {
            "status": "SUCCESS",
            "upgrade_schema_version": "vn_quant_model_lab_upgrade_v15",
            "historical_reference_model": "NO_MODEL_APPROVED",
            "historical_reference_gate_passed": False,
            "historical_reference_status": "HISTORICAL_REFERENCE_CANDIDATE",
            "evidence_grade": "YELLOW_HISTORICAL_CANDIDATE",
            "walk_forward": {
                "fold_count": 57,
                "first_test_date": "2021-10-29",
                "last_test_date": "2026-06-30",
            },
            "evaluations": {
                "robust_technical_ensemble_v1": {
                    "status": "SUCCESS",
                    "error": None,
                },
                "online_rank_ensemble_v1": {
                    "status": "SUCCESS",
                    "error": None,
                },
            },
            "failures": {},
            "reference_diagnostic": {
                "status": "INSUFFICIENT_POSITIVE_MODELS",
                "positive_evidence_models": ["robust_technical_ensemble_v1"],
            },
            "predictive_upgrade_v6": {
                "reference_status": "BELOW_PREDICTIVE_REFERENCE_GATE",
            },
            "turnover_buffer_future_holdout": {
                "status": "NO_GENUINELY_FUTURE_FOLDS",
            },
        }
        (model_output / "model_lab_summary.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def _write_comparison(self, model_output: Path) -> None:
        fields = [
            "model",
            "status",
            "outer_test_period_count",
            "mean_rank_ic",
            "positive_rank_ic_ratio",
            "base_relative_total_return",
            "stress_relative_total_return",
            "base_mean_turnover",
            "failed_gate_count",
            "failed_gates",
            "gate_passed",
        ]
        with (model_output / "nested_model_historical_validation_v15.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerow({
                "model": "robust_technical_ensemble_v1",
                "status": "HISTORICAL_REFERENCE_CANDIDATE",
                "outer_test_period_count": 51,
                "mean_rank_ic": 0.0117,
                "positive_rank_ic_ratio": 0.5882,
                "base_relative_total_return": 0.0692,
                "stress_relative_total_return": 0.0586,
                "base_mean_turnover": 0.2059,
                "failed_gate_count": 2,
                "failed_gates": "mean_rank_ic_at_least_003|leave_best_period_out_relative_positive",
                "gate_passed": "false",
            })

    def _build_output(self, root: Path) -> Path:
        model_output = root / "model-lab"
        model_output.mkdir(parents=True)
        self._write_summary(model_output)
        self._write_comparison(model_output)
        (model_output / "model_lab_output.zip").write_bytes(b"valid")
        (root / "extended_history_reference_v23.json").write_text(
            json.dumps({
                "schema_version": "extended_history_reference_v23",
                "status": "SUCCESS_NO_MODEL_APPROVED",
                "model_outcome": {
                    "fold_count": 0,
                    "models_success": [],
                },
                "live_capital_approved": False,
                "automatic_live_orders_allowed": False,
            }),
            encoding="utf-8",
        )
        return model_output

    def test_nested_summary_fields_are_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_output = self._build_output(root)
            outcome = corrected_model_outcome(model_output)

        self.assertEqual(outcome["fold_count"], 57)
        self.assertEqual(
            outcome["models_success"],
            ["online_rank_ensemble_v1", "robust_technical_ensemble_v1"],
        )
        self.assertEqual(
            outcome["positive_evidence_models"],
            ["robust_technical_ensemble_v1"],
        )
        self.assertEqual(
            outcome["predictive_reference_status"],
            "BELOW_PREDICTIVE_REFERENCE_GATE",
        )
        self.assertEqual(
            outcome["reference_diagnostic_status"],
            "INSUFFICIENT_POSITIVE_MODELS",
        )
        self.assertEqual(
            outcome["future_holdout_status"],
            "NO_GENUINELY_FUTURE_FOLDS",
        )

    def test_existing_run_is_repaired_without_retraining(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_output(root)
            with patch("subprocess.run") as run:
                report = repair_existing_output(root)

            run.assert_not_called()
            repaired = root / "extended_history_reference_v24.json"
            self.assertTrue(repaired.is_file())
            self.assertTrue(report["metadata_repaired_without_retraining"])
            self.assertFalse(report["model_lab_artifacts_modified"])
            self.assertEqual(report["model_outcome"]["fold_count"], 57)
            self.assertFalse(report["live_capital_approved"])


if __name__ == "__main__":
    unittest.main()
