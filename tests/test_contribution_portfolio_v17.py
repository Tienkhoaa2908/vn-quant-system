from __future__ import annotations

from decimal import Decimal
import unittest

from he_thong_dinh_luong.contribution_portfolio_v17 import (
    ContributionPlanRequest,
    build_contribution_plan,
)
from he_thong_dinh_luong.portfolio_planner import Holding


class ContributionPortfolioV17Tests(unittest.TestCase):
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
            "OLD": Decimal("50000"),
        }

    def test_small_contribution_accumulates_when_no_lot_is_affordable(self) -> None:
        plan = build_contribution_plan(
            holdings=[],
            price_vnd=self.prices,
            allocation_rows=self.allocations,
            predictions=self.predictions,
            model=self.model,
            request=ContributionPlanRequest(extra_cash_vnd=300_000),
        )
        self.assertEqual(plan["estimated_spend_vnd"], 0)
        self.assertEqual(
            plan["contribution_status"],
            "ACCUMULATE_CASH_UNTIL_EXECUTABLE_LOT",
        )
        self.assertGreater(plan["cash_shortfall_to_next_lot_vnd"], 0)
        self.assertTrue(all(row["recommended_buy_quantity"] == 0 for row in plan["rows"]))

    def test_buy_only_allocator_uses_existing_portfolio_and_buys_underweight(self) -> None:
        plan = build_contribution_plan(
            holdings=[
                Holding("AAA", 1000, Decimal("9000")),
                Holding("OLD", 100, Decimal("45000")),
            ],
            price_vnd=self.prices,
            allocation_rows=self.allocations,
            predictions=self.predictions,
            model=self.model,
            request=ContributionPlanRequest(extra_cash_vnd=10_000_000),
        )
        by_symbol = {row["symbol"]: row for row in plan["rows"]}
        self.assertEqual(by_symbol["AAA"]["recommended_buy_quantity"], 0)
        self.assertGreater(
            by_symbol["BBB"]["recommended_buy_quantity"]
            + by_symbol["CCC"]["recommended_buy_quantity"],
            0,
        )
        self.assertIn("OLD", {row["symbol"] for row in plan["outside_target_holdings"]})
        self.assertLessEqual(plan["estimated_spend_vnd"], 10_000_000)
        self.assertFalse(plan["automatic_live_orders_allowed"])

    def test_regime_cash_budget_can_hold_new_money_as_cash(self) -> None:
        model = dict(self.model)
        model["capital_budget_pct"] = 25
        plan = build_contribution_plan(
            holdings=[Holding("AAA", 1000, Decimal("9000"))],
            price_vnd=self.prices,
            allocation_rows=self.allocations,
            predictions=self.predictions,
            model=model,
            request=ContributionPlanRequest(extra_cash_vnd=1_000_000),
        )
        self.assertEqual(plan["deployable_cash_vnd"], 0)
        self.assertEqual(
            plan["contribution_status"],
            "HELD_AS_CASH_BY_REGIME_OR_EXISTING_OVERWEIGHT",
        )

    def test_symbol_cap_is_hard_even_when_target_is_larger(self) -> None:
        plan = build_contribution_plan(
            holdings=[],
            price_vnd=self.prices,
            allocation_rows=[{"symbol": "AAA", "rank": "1", "target_weight_pct": "100"}],
            predictions=self.predictions,
            model=self.model,
            request=ContributionPlanRequest(
                extra_cash_vnd=20_000_000,
                max_symbol_weight=Decimal("0.15"),
            ),
        )
        row = plan["rows"][0]
        self.assertLessEqual(row["post_weight_pct"], 15.0)

    def test_known_sector_cap_is_hard(self) -> None:
        plan = build_contribution_plan(
            holdings=[],
            price_vnd=self.prices,
            allocation_rows=self.allocations,
            predictions=self.predictions,
            model=self.model,
            sector_by_symbol={"AAA": "BANK", "BBB": "BANK", "CCC": "INDUSTRIAL"},
            request=ContributionPlanRequest(
                extra_cash_vnd=30_000_000,
                max_symbol_weight=Decimal("0.20"),
                max_sector_weight=Decimal("0.25"),
            ),
        )
        bank_value = sum(
            row["post_value_vnd"]
            for row in plan["rows"]
            if row["sector"] == "BANK"
        )
        self.assertLessEqual(bank_value / plan["total_after_contribution_vnd"], 0.25)

    def test_sector_required_fails_closed_when_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "CONTRIBUTION_SECTOR_MISSING"):
            build_contribution_plan(
                holdings=[],
                price_vnd=self.prices,
                allocation_rows=self.allocations,
                predictions=self.predictions,
                model=self.model,
                request=ContributionPlanRequest(
                    extra_cash_vnd=5_000_000,
                    require_sector_data=True,
                ),
            )


if __name__ == "__main__":
    unittest.main()
