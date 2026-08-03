from __future__ import annotations

import calendar
from datetime import date
import unittest

from he_thong_dinh_luong.contribution_evaluation_v17 import (
    evaluate_monthly_contributions,
    generate_periodic_contributions,
)


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def add_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + offset
    return index // 12, index % 12 + 1


def periods(count: int, strategy_return: float = 0.02, benchmark_return: float = 0.01):
    rows = []
    for index in range(count):
        sy, sm = add_month(2020, 1, index)
        ey, em = add_month(2020, 1, index + 1)
        rows.append({
            "signal_date": month_end(sy, sm).isoformat(),
            "label_end": month_end(ey, em).isoformat(),
            "net_return": strategy_return,
            "benchmark_return": benchmark_return,
        })
    return rows


class ContributionEvaluationV17Tests(unittest.TestCase):
    def test_48_months_passes_and_reports_twr_mwr_and_terminal_wealth(self) -> None:
        rows = periods(48)
        events = generate_periodic_contributions(
            start=date(2020, 1, 31),
            end=date(2023, 12, 31),
            amount_vnd=500_000,
            every_days=14,
        )
        result = evaluate_monthly_contributions(
            period_rows=rows,
            contribution_rows=events,
            initial_capital_vnd=1_000_000,
            minimum_periods=48,
        )
        self.assertEqual(result["status"], "EXTENDED_MONTHLY_HISTORY_READY")
        self.assertTrue(result["monthly_horizon_verified"])
        self.assertTrue(result["historical_gate_passed"])
        self.assertGreater(result["time_weighted_return"], result["benchmark_time_weighted_return"])
        self.assertGreater(result["terminal_wealth_advantage_vnd"], 0)
        self.assertIsNotNone(result["money_weighted_return_xirr"])
        self.assertEqual(result["t_plus_one_role"], "EXECUTION_ONLY_NOT_MODEL_VALIDATION")

    def test_18_months_is_explicitly_insufficient_for_extended_gate(self) -> None:
        result = evaluate_monthly_contributions(
            period_rows=periods(18),
            contribution_rows=[{"contribution_date": "2020-01-31", "amount_vnd": 500_000}],
            minimum_periods=48,
        )
        self.assertEqual(result["status"], "INSUFFICIENT_MONTHLY_HISTORY")
        self.assertFalse(result["historical_gate_passed"])

    def test_t_plus_one_period_is_rejected_as_model_evaluation(self) -> None:
        with self.assertRaisesRegex(ValueError, "CONTRIBUTION_NOT_MONTHLY_HORIZON"):
            evaluate_monthly_contributions(
                period_rows=[{
                    "signal_date": "2026-07-30",
                    "label_end": "2026-07-31",
                    "net_return": 0.01,
                    "benchmark_return": 0.0,
                }],
                contribution_rows=[],
                minimum_periods=12,
            )

    def test_contributions_between_signals_accumulate_to_next_month(self) -> None:
        result = evaluate_monthly_contributions(
            period_rows=periods(12),
            contribution_rows=[
                {"contribution_date": "2020-02-01", "amount_vnd": 300_000},
                {"contribution_date": "2020-02-15", "amount_vnd": 400_000},
            ],
            minimum_periods=12,
        )
        feb_signal = result["monthly_rows"][1]
        self.assertEqual(feb_signal["external_cash_flow_vnd"], 700_000)

    def test_contribution_after_last_signal_is_not_backfilled(self) -> None:
        result = evaluate_monthly_contributions(
            period_rows=periods(12),
            contribution_rows=[
                {"contribution_date": "2025-01-01", "amount_vnd": 900_000},
            ],
            minimum_periods=12,
        )
        self.assertEqual(result["unmapped_contributions_vnd"], 900_000)
        self.assertEqual(result["mapped_contributions_vnd"], 0)


if __name__ == "__main__":
    unittest.main()
