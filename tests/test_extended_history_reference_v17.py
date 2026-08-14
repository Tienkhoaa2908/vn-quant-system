from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.extended_history_reference_v17 import (
    build_model_lab_command,
    verify_extended_model_lab,
)


class ExtendedHistoryCommandTests(unittest.TestCase):
    def test_command_freezes_long_monthly_protocol(self) -> None:
        command = build_model_lab_command(
            input_zip=Path("input.zip"),
            output_dir=Path("output"),
            evaluation_months=72,
            minimum_train_months=60,
            minimum_outer_test_periods=48,
        )
        text = " ".join(command)
        self.assertIn("--evaluation-months 72", text)
        self.assertIn("--minimum-train-months 60", text)
        self.assertIn("--nested-validation-months 6", text)
        self.assertIn("--nested-test-months 3", text)
        self.assertIn("--minimum-outer-test-periods 48", text)
        self.assertIn("--replacement-caps 0,1,2,3,4,5", text)
        self.assertIn("--strict-dependencies", command)

    def test_short_protocol_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "EXTENDED_HISTORY_REQUIRES_AT_LEAST_48_OUTER_MONTHS",
        ):
            build_model_lab_command(
                input_zip=Path("input.zip"),
                output_dir=Path("output"),
                evaluation_months=72,
                minimum_train_months=60,
                minimum_outer_test_periods=18,
            )


class ExtendedHistoryVerificationTests(unittest.TestCase):
    def write_fixture(self, root: Path, period_count: int) -> None:
        (root / "model_lab_summary.json").write_text(
            json.dumps({
                "upgrade_schema_version": "vn_quant_model_lab_upgrade_v15",
                "historical_reference_model": "online_rank_ensemble_v1",
            }),
            encoding="utf-8",
        )
        comparison = root / "nested_model_historical_validation_v15.csv"
        with comparison.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "model", "outer_test_period_count", "mean_rank_ic",
                    "positive_rank_ic_ratio", "base_net_total_return",
                    "base_benchmark_total_return", "base_relative_total_return",
                    "stress_relative_total_return", "base_mean_turnover",
                    "gate_passed",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "model": "online_rank_ensemble_v1",
                "outer_test_period_count": period_count,
                "mean_rank_ic": 0.04,
                "positive_rank_ic_ratio": 0.58,
                "base_net_total_return": 0.5,
                "base_benchmark_total_return": 0.3,
                "base_relative_total_return": 0.15,
                "stress_relative_total_return": 0.14,
                "base_mean_turnover": 0.35,
                "gate_passed": "true",
            })
        periods = root / "nested_model_outer_test_periods_v15.csv"
        with periods.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "model", "cost_scenario", "signal_date", "label_end",
                ],
            )
            writer.writeheader()
            year = 2020
            month = 1
            for _ in range(period_count):
                next_month = month + 1
                next_year = year
                if next_month == 13:
                    next_month = 1
                    next_year += 1
                writer.writerow({
                    "model": "online_rank_ensemble_v1",
                    "cost_scenario": "BASE",
                    "signal_date": f"{year:04d}-{month:02d}-01",
                    "label_end": f"{next_year:04d}-{next_month:02d}-01",
                })
                year, month = next_year, next_month

    def test_48_monthly_periods_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, 48)
            result = verify_extended_model_lab(
                root,
                minimum_outer_test_periods=48,
            )
        self.assertEqual(result["period_count"], 48)
        self.assertGreaterEqual(result["minimum_horizon_days"], 20)
        self.assertLessEqual(result["maximum_horizon_days"], 45)

    def test_18_months_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, 18)
            with self.assertRaisesRegex(
                ValueError,
                "EXTENDED_HISTORY_INSUFFICIENT_OUTER_MONTHS:18<48",
            ):
                verify_extended_model_lab(
                    root,
                    minimum_outer_test_periods=48,
                )


if __name__ == "__main__":
    unittest.main()
