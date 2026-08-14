from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.extended_history_reference_v23 import (
    verify_model_lab_outcome,
)


class ExtendedHistoryReferenceV23Tests(unittest.TestCase):
    def _write_csv(
        self,
        path: Path,
        rows: list[dict[str, object]],
        fields: list[str],
    ) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def _negative_output(self, root: Path) -> None:
        summary = {
            "upgrade_schema_version": "vn_quant_model_lab_upgrade_v15",
            "status": "SUCCESS",
            "evidence_grade": "YELLOW_WEAK_POSITIVE_EVIDENCE",
            "historical_reference_status": "HISTORICAL_REFERENCE_CANDIDATE",
            "historical_reference_model": "NO_MODEL_APPROVED",
            "historical_reference_gate_passed": False,
            "fold_count": 57,
            "models_success": ["momentum_baseline", "robust_technical_ensemble_v1"],
            "models_skipped_or_failed": {},
            "positive_evidence_models": ["robust_technical_ensemble_v1"],
            "predictive_reference_status": "BELOW_PREDICTIVE_REFERENCE_GATE",
            "reference_diagnostic_status": "INSUFFICIENT_POSITIVE_MODELS",
            "future_holdout_status": "NO_GENUINELY_FUTURE_FOLDS",
        }
        (root / "model_lab_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        (root / "model_lab_output.zip").write_bytes(b"not-empty")
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
        self._write_csv(
            root / "nested_model_historical_validation_v15.csv",
            [
                {
                    "model": "robust_technical_ensemble_v1",
                    "status": "HISTORICAL_REFERENCE_CANDIDATE",
                    "outer_test_period_count": 51,
                    "mean_rank_ic": 0.02,
                    "positive_rank_ic_ratio": 0.53,
                    "base_relative_total_return": 0.08,
                    "stress_relative_total_return": 0.04,
                    "base_mean_turnover": 0.31,
                    "failed_gate_count": 2,
                    "failed_gates": "mean_rank_ic_at_least_003|positive_rank_ic_ratio_at_least_055",
                    "gate_passed": "false",
                },
                {
                    "model": "momentum_baseline",
                    "status": "REJECTED",
                    "outer_test_period_count": 51,
                    "mean_rank_ic": -0.01,
                    "positive_rank_ic_ratio": 0.45,
                    "base_relative_total_return": -0.02,
                    "stress_relative_total_return": -0.04,
                    "base_mean_turnover": 0.20,
                    "failed_gate_count": 6,
                    "failed_gates": "many",
                    "gate_passed": "false",
                },
            ],
            fields,
        )

    def test_no_model_approved_is_a_successful_negative_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._negative_output(root)
            result = verify_model_lab_outcome(
                root,
                minimum_outer_test_periods=48,
            )
        self.assertEqual(result["status"], "SUCCESS_NO_MODEL_APPROVED")
        self.assertEqual(result["outcome"], "NO_MODEL_APPROVED")
        self.assertFalse(result["contribution_evaluation_allowed"])
        self.assertEqual(
            result["contribution_skip_reason"],
            "NO_APPROVED_REFERENCE_MODEL",
        )
        self.assertEqual(result["maximum_outer_test_period_count"], 51)
        self.assertFalse(result["live_capital_approved"])

    def test_inconsistent_no_model_gate_still_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._negative_output(root)
            path = root / "model_lab_summary.json"
            summary = json.loads(path.read_text(encoding="utf-8"))
            summary["historical_reference_gate_passed"] = True
            path.write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "EXTENDED_HISTORY_REFERENCE_STATE_INCONSISTENT",
            ):
                verify_model_lab_outcome(root)

    def test_negative_outcome_still_requires_48_outer_months(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._negative_output(root)
            path = root / "nested_model_historical_validation_v15.csv"
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                row["outer_test_period_count"] = "47"
            self._write_csv(path, rows, list(rows[0]))
            with self.assertRaisesRegex(
                ValueError,
                "EXTENDED_HISTORY_INSUFFICIENT_OUTER_MONTHS:47<48",
            ):
                verify_model_lab_outcome(root)


if __name__ == "__main__":
    unittest.main()
