from __future__ import annotations

import calendar
from datetime import date
import unittest

from he_thong_dinh_luong.historical_data_requirements_v19 import (
    derive_history_requirements,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months(day: date, count: int) -> date:
    index = day.year * 12 + day.month - 1 + count
    year, zero_month = divmod(index, 12)
    return _month_end(year, zero_month + 1)


def _rows(count: int, start: date = date(2022, 1, 31)) -> list[Row]:
    output: list[Row] = []
    for index in range(count):
        signal = _add_months(start, index)
        label_end = _add_months(signal, 1)
        output.append(
            Row(
                ngay=signal,
                ma="AAA",
                features={"x": 1.0},
                relative_return=0.01,
                label_end=label_end,
            )
        )
    return output


class HistoricalDataRequirementsV19Tests(unittest.TestCase):
    def test_53_month_input_reports_65_additional_months(self) -> None:
        result = derive_history_requirements(_rows(53))
        self.assertEqual(result["status"], "DEEPER_HISTORY_REQUIRED")
        self.assertEqual(
            result["estimated_minimum_total_labeled_monthly_dates"], 118
        )
        self.assertEqual(result["estimated_additional_labeled_months_needed"], 65)
        self.assertEqual(
            result["estimated_required_first_labeled_signal_date"],
            "2016-08-31",
        )
        self.assertEqual(
            result["estimated_required_price_history_start_date"],
            "2015-07-31",
        )
        self.assertFalse(result["current_universe_backfill_allowed_for_research_gate"])
        self.assertEqual(
            result["t_plus_one_role"], "EXECUTION_ONLY_NOT_MODEL_VALIDATION"
        )

    def test_118_month_input_is_ready(self) -> None:
        result = derive_history_requirements(_rows(118, date(2016, 8, 31)))
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["estimated_additional_labeled_months_needed"], 0)

    def test_longer_label_horizon_increases_purge_guard(self) -> None:
        rows = _rows(118, date(2016, 8, 31))
        rows[-1] = Row(
            ngay=rows[-1].ngay,
            ma="AAA",
            features={"x": 1.0},
            relative_return=0.01,
            label_end=_add_months(rows[-1].ngay, 2),
        )
        result = derive_history_requirements(rows)
        self.assertEqual(result["observed_label_purge_guard_months"], 2)
        self.assertEqual(
            result["estimated_minimum_total_labeled_monthly_dates"], 119
        )


if __name__ == "__main__":
    unittest.main()
