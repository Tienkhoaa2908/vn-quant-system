from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from he_thong_dinh_luong.portfolio_safety import (
    derive_cash_semantics,
    foreign_trading_params,
    resolve_position_action,
)
from he_thong_dinh_luong.terminal_domain import build_decision_brief


class PortfolioSafetyTests(unittest.TestCase):
    def test_planner_uses_settled_cash_not_broker_buying_power(self) -> None:
        payload = {
            "availableCash": 80_000,
            "totalCash": 11_582,
            "withdrawableCash": 10_000,
        }
        result = derive_cash_semantics(payload)
        self.assertEqual(result.broker_buying_power_vnd, 80_000)
        self.assertEqual(result.planner_cash_vnd, 10_000)
        self.assertEqual(result.status, "PASS_SETTLED_CASH")
        self.assertIn("BROKER_BUYING_POWER_EXCEEDS_SETTLED_PLANNER_CASH", result.warnings)

    def test_missing_total_cash_blocks_planner(self) -> None:
        result = derive_cash_semantics({"availableCash": 100_000})
        self.assertEqual(result.planner_cash_vnd, 0)
        self.assertEqual(result.status, "BLOCKED_TOTAL_CASH_MISSING")

    def test_reduce_action_has_priority_over_overweight(self) -> None:
        action = resolve_position_action(
            target_weight_pct=0,
            current_weight_pct=85.49,
            above_ma250=False,
            trend_score=0.125,
        )
        self.assertEqual(action, "REVIEW_REDUCE_OUTSIDE_TARGET")

    def test_foreign_context_has_time_window(self) -> None:
        now = datetime(2026, 7, 31, 13, 0, tzinfo=timezone(timedelta(hours=7)))
        params = foreign_trading_params(now)
        self.assertEqual(params["type"], "STOCK")
        self.assertLess(params["from"], params["to"])


class DecisionBriefTests(unittest.TestCase):
    def test_brief_prioritizes_actions_and_explains_empty_paper(self) -> None:
        brief = build_decision_brief(
            manifest={"data_status": "LAST_AVAILABLE", "primary_coverage": 0.975},
            quality={"source_error_count": 0},
            model={
                "market_regime": "RISK_OFF",
                "capital_budget_pct": 15,
                "champion_model": "momentum_baseline",
                "robust_validation_status": "PASS",
                "momentum_validation": {"mean_rank_ic": -0.05},
                "robust_reference_validation": {
                    "mean_rank_ic": -0.01,
                    "top_k_relative_return": -0.02,
                },
            },
            predictions=[{
                "symbol": "MBB",
                "ranking_rank": 21,
                "selected_top_k": False,
                "above_ma250": False,
            }],
            allocation=[],
            portfolio_summary={
                "planner_cash_vnd": 10_000,
                "broker_buying_power_vnd": 80_000,
            },
            portfolio_analysis=[{
                "symbol": "MBB",
                "quantity": 3,
                "market_price_vnd": 22_750,
                "market_value_vnd": 68_250,
                "unrealized_pnl_vnd": -150,
                "unrealized_pnl_pct": -0.00219,
                "current_weight_pct": 85.49,
                "target_weight_pct": 0,
                "ranking_rank": 21,
                "trend_score": 0.125,
                "above_ma250": False,
                "return_20": -0.0876,
                "return_60": -0.1036,
                "action": "REVIEW_REDUCE_OUTSIDE_TARGET",
            }],
            paper_metrics={},
        )
        self.assertEqual(brief["model"]["grade"], "RED")
        self.assertEqual(brief["paper"]["state"], "EMPTY")
        self.assertEqual(brief["positions"][0]["action"], "REVIEW_REDUCE_OUTSIDE_TARGET")
        self.assertTrue(any("Ưu tiên tiền mặt" in item["title"] for item in brief["actions"]))
        self.assertTrue(any("10,000" in item["title"] for item in brief["actions"]))


if __name__ == "__main__":
    unittest.main()
