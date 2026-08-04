from __future__ import annotations

from datetime import date
import unittest

from vn_quant_local.weekly_plan import (
    _completed_month_signal_days,
    classify_sell_history,
)


class SellHistoryTests(unittest.TestCase):
    def test_latest_two_completed_months_drive_exit(self) -> None:
        observations = [
            {
                "signal_day": "2026-06-30",
                "rank": None,
                "status": "INELIGIBLE",
            },
            {
                "signal_day": "2026-05-30",
                "rank": 27,
                "status": "RANKED_OUTSIDE_TOP20",
            },
            {
                "signal_day": "2026-04-29",
                "rank": 8,
                "status": "TOP20",
            },
        ]
        action, reason = classify_sell_history(
            observations, sellable_quantity=10
        )
        self.assertEqual(action, "EXIT_CANDIDATE")
        self.assertEqual(
            reason,
            "OUTSIDE_TOP20_TWO_CONSECUTIVE_COMPLETED_MONTHS",
        )

    def test_one_month_outside_only_is_watch(self) -> None:
        observations = [
            {
                "signal_day": "2026-06-30",
                "rank": 24,
                "status": "RANKED_OUTSIDE_TOP20",
            },
            {
                "signal_day": "2026-05-30",
                "rank": 12,
                "status": "TOP20",
            },
        ]
        action, _ = classify_sell_history(
            observations, sellable_quantity=10
        )
        self.assertEqual(action, "WATCH")

    def test_history_data_gap_cannot_be_sell_candidate(self) -> None:
        observations = [
            {
                "signal_day": "2026-06-30",
                "rank": None,
                "status": "MISSING_EXACT_HISTORY",
            },
            {
                "signal_day": "2026-05-30",
                "rank": 30,
                "status": "RANKED_OUTSIDE_TOP20",
            },
        ]
        action, reason = classify_sell_history(
            observations, sellable_quantity=10
        )
        self.assertEqual(action, "DATA_REVIEW_REQUIRED")
        self.assertEqual(reason, "SELL_HISTORY_HAS_DATA_GAP")

    def test_completed_month_days_exclude_latest_data_month(self) -> None:
        calendar = [
            date(2026, 3, 31),
            date(2026, 4, 29),
            date(2026, 5, 29),
            date(2026, 6, 30),
            date(2026, 7, 31),
        ]
        days = _completed_month_signal_days(calendar, count=3)
        self.assertEqual(
            days,
            [date(2026, 6, 30), date(2026, 5, 29), date(2026, 4, 29)],
        )


if __name__ == "__main__":
    unittest.main()
