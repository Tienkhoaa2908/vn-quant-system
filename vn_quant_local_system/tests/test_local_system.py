from __future__ import annotations

from datetime import date
import unittest

from vn_quant_local.broker_portfolio import (
    _candidate_accounts,
    _is_explicit_derivative_account,
)
from vn_quant_local.c3_model import (
    CurrentFeature,
    HistoricalRow,
    _signal_days,
    average_percentile,
    component_weights,
    rank_features,
)
from vn_quant_local.weekly_plan import allocate_buy_orders, capped_inverse_vol_weights


class LocalSystemTests(unittest.TestCase):
    def test_average_percentile_preserves_ties(self) -> None:
        self.assertEqual(average_percentile([1.0, 1.0, 3.0]), [0.25, 0.25, 1.0])

    def test_signal_day_uses_previous_completed_month(self) -> None:
        canonical, preview = _signal_days(
            [date(2026, 6, 30), date(2026, 7, 31), date(2026, 8, 3)],
            today=date(2026, 8, 4),
        )
        self.assertEqual(canonical, date(2026, 7, 31))
        self.assertEqual(preview, date(2026, 8, 3))

    def test_component_weights_ignore_unfinished_labels(self) -> None:
        rows = []
        for month in range(1, 5):
            signal = date(2025, month, 28)
            for index in range(5):
                rows.append(
                    HistoricalRow(
                        signal,
                        date(2025, month + 1, 20),
                        f"S{index}",
                        float(index),
                        float(index),
                        float(4 - index),
                        float(index),
                    )
                )
        weights = component_weights(rows, before_day=date(2025, 3, 1))
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertTrue(all(0.0 <= value <= 0.5 + 1e-12 for value in weights.values()))

    def test_rank_features(self) -> None:
        features = [
            CurrentFeature(
                date(2026, 7, 31),
                f"S{i}",
                10000 + i,
                0.01 + i * 0.001,
                i / 10,
                0.8 + i / 100,
                True,
                10e9,
                0,
                True,
                True,
            )
            for i in range(10)
        ]
        rows = rank_features(
            features,
            {
                "low_volatility": 1 / 3,
                "relative_strength_120": 1 / 3,
                "high_52_week": 1 / 3,
            },
        )
        self.assertEqual(len(rows), 10)
        self.assertEqual([row["rank"] for row in rows], list(range(1, 11)))

    def test_inverse_vol_weights_respect_cap(self) -> None:
        rows = [
            {"symbol": f"S{i}", "volatility_60": 0.01 + i * 0.001}
            for i in range(10)
        ]
        weights = capped_inverse_vol_weights(rows, cap=0.15)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)
        self.assertLessEqual(max(weights.values()), 0.15 + 1e-9)

    def test_multi_buy_diversifies_when_budget_allows(self) -> None:
        candidates = [
            {
                "symbol": "AAA",
                "rank": 1,
                "price_vnd": 50_000,
                "budget_ceiling_vnd": 200_000,
                "underweight_pct": 0.12,
                "target_gap_vnd": 200_000,
            },
            {
                "symbol": "BBB",
                "rank": 2,
                "price_vnd": 60_000,
                "budget_ceiling_vnd": 180_000,
                "underweight_pct": 0.10,
                "target_gap_vnd": 180_000,
            },
            {
                "symbol": "CCC",
                "rank": 3,
                "price_vnd": 70_000,
                "budget_ceiling_vnd": 140_000,
                "underweight_pct": 0.08,
                "target_gap_vnd": 140_000,
            },
        ]
        orders = allocate_buy_orders(
            candidates, budget_vnd=200_000, max_orders=3, cost_bps=0.0
        )
        self.assertEqual([row["symbol"] for row in orders], ["AAA", "BBB", "CCC"])
        self.assertLessEqual(
            sum(row["estimated_cost_vnd"] for row in orders), 200_000
        )

    def test_single_order_baseline_stays_single(self) -> None:
        candidates = [
            {
                "symbol": symbol,
                "rank": index,
                "price_vnd": 50_000,
                "budget_ceiling_vnd": 300_000,
                "underweight_pct": 0.20 - index / 100,
                "target_gap_vnd": 300_000,
            }
            for index, symbol in enumerate(("AAA", "BBB", "CCC"), start=1)
        ]
        orders = allocate_buy_orders(
            candidates, budget_vnd=250_000, max_orders=1, cost_bps=50.0
        )
        self.assertEqual(len(orders), 1)
        self.assertLessEqual(
            sum(row["estimated_cost_vnd"] for row in orders), 250_000
        )

    def test_derivative_registration_flag_does_not_exclude_stock_account(self) -> None:
        account = {
            "id": "0001000001",
            "accountTypeName": "Tài khoản thường",
            "derivativeAccount": True,
        }
        self.assertFalse(_is_explicit_derivative_account(account))
        selected, mode = _candidate_accounts([account])
        self.assertEqual(selected, [account])
        self.assertEqual(mode, "EXCLUDE_EXPLICIT_DERIVATIVE_TYPES")

    def test_explicit_derivative_type_is_excluded_when_stock_account_exists(self) -> None:
        stock = {
            "id": "0001000001",
            "accountTypeName": "Tài khoản ký quỹ",
            "derivativeAccount": True,
        }
        derivative = {
            "id": "0001000002",
            "accountTypeName": "Tài khoản phái sinh",
            "derivativeAccount": True,
        }
        selected, _ = _candidate_accounts([stock, derivative])
        self.assertEqual(selected, [stock])

    def test_unknown_account_type_falls_back_to_identified_account(self) -> None:
        unknown = {"id": "0001000001", "derivativeAccount": True}
        selected, mode = _candidate_accounts([unknown])
        self.assertEqual(selected, [unknown])
        self.assertEqual(mode, "EXCLUDE_EXPLICIT_DERIVATIVE_TYPES")


if __name__ == "__main__":
    unittest.main()
