from __future__ import annotations

from decimal import Decimal
import unittest

from he_thong_dinh_luong.contribution_portfolio_v18 import (
    ContributionPlanRequest,
    build_contribution_plan,
)


class ContributionPortfolioV18Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.allocations = [
            {"symbol": "AAA", "rank": "1", "target_weight_pct": "10"},
            {"symbol": "BBB", "rank": "2", "target_weight_pct": "10"},
            {"symbol": "CCC", "rank": "3", "target_weight_pct": "10"},
        ]
        self.predictions = [
            {"symbol": "AAA", "above_ma250": "true", "score": "0.9"},
            {"symbol": "BBB", "above_ma250": "true", "score": "0.8"},
            {"symbol": "CCC", "above_ma250": "true", "score": "0.7"},
        ]
        self.model = {
            "signal_date": "2026-07-30",
            "champion_model": "online_rank_ensemble_v1",
            "capital_budget_pct": 100,
        }
        self.prices = {
            "AAA": Decimal("10000"),
            "BBB": Decimal("20000"),
            "CCC": Decimal("30000"),
        }

    def test_default_quantity_step_is_one_share(self) -> None:
        request = ContributionPlanRequest(extra_cash_vnd=300_000)
        self.assertEqual(request.lot_size, 1)
        plan = build_contribution_plan(
            holdings=[],
            price_vnd=self.prices,
            allocation_rows=self.allocations,
            predictions=self.predictions,
            model=self.model,
            request=request,
        )
        bought = [
            row for row in plan["rows"] if row["recommended_buy_quantity"] > 0
        ]
        self.assertTrue(bought)
        self.assertGreater(plan["estimated_spend_vnd"], 0)
        self.assertLessEqual(plan["estimated_spend_vnd"], 300_000)
        self.assertTrue(any(row["recommended_odd_lot_quantity"] > 0 for row in bought))
        self.assertTrue(plan["odd_lot_supported"])

    def test_cash_below_one_share_is_retained(self) -> None:
        plan = build_contribution_plan(
            holdings=[],
            price_vnd=self.prices,
            allocation_rows=self.allocations,
            predictions=self.predictions,
            model=self.model,
            request=ContributionPlanRequest(extra_cash_vnd=5_000),
        )
        self.assertEqual(plan["estimated_spend_vnd"], 0)
        self.assertEqual(
            plan["contribution_status"],
            "ACCUMULATE_CASH_UNTIL_ONE_SHARE_AFFORDABLE_OR_RISK_ROOM",
        )
        self.assertGreater(
            plan["cash_shortfall_to_cheapest_priced_share_vnd"], 0
        )
        self.assertEqual(
            plan["one_share_blocker"],
            "CASH_BELOW_CHEAPEST_PRICED_SHARE",
        )

    def test_quantity_is_split_into_round_and_odd_lot_orders(self) -> None:
        plan = build_contribution_plan(
            holdings=[],
            price_vnd={"AAA": Decimal("10000")},
            allocation_rows=[
                {"symbol": "AAA", "rank": "1", "target_weight_pct": "100"}
            ],
            predictions=self.predictions,
            model=self.model,
            request=ContributionPlanRequest(
                extra_cash_vnd=1_050_000,
                max_symbol_weight=Decimal("1"),
                max_sector_weight=Decimal("1"),
            ),
        )
        row = plan["rows"][0]
        quantity = row["recommended_buy_quantity"]
        self.assertGreaterEqual(quantity, 100)
        self.assertEqual(
            row["recommended_round_lot_quantity"]
            + row["recommended_odd_lot_quantity"],
            quantity,
        )
        self.assertLess(row["recommended_odd_lot_quantity"], 100)
        self.assertEqual(
            row["execution_route"],
            "ROUND_LOT_AND_ODD_LOT_SEPARATE_ORDERS",
        )
        self.assertLessEqual(plan["estimated_spend_vnd"], 1_050_000)


if __name__ == "__main__":
    unittest.main()
