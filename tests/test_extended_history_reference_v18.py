from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong.extended_history_reference_v18 import (
    inspect_history_rows,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row


def _next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _rows(month_count: int) -> list[Row]:
    result: list[Row] = []
    day = date(2015, 1, 1)
    for _ in range(month_count):
        result.append(
            Row(
                ngay=day,
                ma="AAA",
                features={},
                relative_return=0.01,
                label_end=_next_month(day),
            )
        )
        day = _next_month(day)
    return result


class ExtendedHistoryPreflightV18Tests(unittest.TestCase):
    def test_short_input_reports_coverage_before_model_lab(self) -> None:
        report = inspect_history_rows(
            _rows(50),
            evaluation_months=72,
            minimum_train_months=60,
            minimum_outer_test_periods=48,
        )
        self.assertEqual(report["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(
            report["blocker"],
            "MINIMUM_TRAIN_EXCEEDS_AVAILABLE_LABELED_MONTHS",
        )
        self.assertEqual(report["available_labeled_monthly_dates"], 50)
        self.assertEqual(report["requested_protocol_valid_fold_count"], 0)
        self.assertGreater(report["additional_valid_monthly_folds_needed"], 0)
        self.assertEqual(
            report["recommendation"],
            "REBUILD_DAILY_PREDICTION_INPUT_WITH_DEEPER_POINT_IN_TIME_HISTORY",
        )

    def test_deep_input_is_ready_for_48_outer_months(self) -> None:
        report = inspect_history_rows(
            _rows(125),
            evaluation_months=72,
            minimum_train_months=60,
            minimum_outer_test_periods=48,
        )
        self.assertEqual(report["status"], "READY")
        self.assertGreaterEqual(
            report["requested_protocol_valid_fold_count"],
            report["minimum_valid_folds_required_before_nested_holdout"],
        )
        self.assertEqual(report["additional_valid_monthly_folds_needed"], 0)
        self.assertEqual(report["recommendation"], "RUN_EXTENDED_MODEL_LAB")
        self.assertEqual(
            report["t_plus_one_role"],
            "EXECUTION_ONLY_NOT_MODEL_VALIDATION",
        )


if __name__ == "__main__":
    unittest.main()
