from __future__ import annotations

import unittest

from vn_quant_local import broker_portfolio, capital_plan, performance, weekly_plan
from vn_quant_local import buying_power_v50 as v50


class V50BuyingPowerTests(unittest.TestCase):
    def test_non_margin_package_is_selected_for_symbol(self) -> None:
        packages = [
            {
                "id": 9,
                "name": "Margin",
                "type": "M",
                "loanProducts": [{"symbol": "FPT"}],
            },
            {
                "id": 3,
                "name": "Cash",
                "type": "N",
                "loanProducts": [{"symbol": "FPT"}],
            },
        ]
        selected = v50.select_non_margin_package(packages, "FPT")
        self.assertIsNotNone(selected)
        self.assertEqual(selected["id"], "3")
        self.assertEqual(selected["type"], "N")

    def test_non_margin_package_does_not_apply_to_other_symbol(self) -> None:
        packages = [
            {
                "id": 3,
                "type": "N",
                "loanProducts": [{"symbol": "FPT"}],
            }
        ]
        self.assertIsNone(v50.select_non_margin_package(packages, "HPG"))

    def test_ppse_response_is_normalized(self) -> None:
        result = v50.normalize_ppse_response(
            {"ppse": 72500.0, "qmax": 3, "price": 24000.0},
            symbol="MBB",
            price_vnd=23900.0,
            loan_package_id="3",
        )
        self.assertEqual(result["ppse_vnd"], 72500.0)
        self.assertEqual(result["qmax"], 3)
        self.assertEqual(result["price_vnd"], 24000.0)
        self.assertEqual(result["loan_package_id"], "3")

    def test_planner_uses_ppse_instead_of_available_cash(self) -> None:
        original = v50._current_effective_buying_power
        v50._current_effective_buying_power = lambda: {
            "status": "SUCCESS",
            "conservative_buying_power_vnd": 72000.0,
        }
        try:
            self.assertEqual(v50.planned_buying_power_v50(945.0, 0.0), 72000.0)
            self.assertEqual(v50.planned_buying_power_v50(945.0, 250000.0), 322000.0)
        finally:
            v50._current_effective_buying_power = original

    def test_planner_falls_back_to_available_cash_when_ppse_unavailable(self) -> None:
        original = v50._current_effective_buying_power
        v50._current_effective_buying_power = lambda: {
            "status": "UNAVAILABLE",
            "conservative_buying_power_vnd": 0.0,
        }
        try:
            self.assertEqual(v50.planned_buying_power_v50(945.0, 0.0), 945.0)
        finally:
            v50._current_effective_buying_power = original

    def test_qmax_caps_candidate_quantity(self) -> None:
        original = v50._current_effective_buying_power
        v50._current_effective_buying_power = lambda: {
            "status": "SUCCESS",
            "items": [
                {
                    "symbol": "FPT",
                    "status": "SUCCESS",
                    "ppse_vnd": 100000.0,
                    "qmax": 2,
                    "loan_package_id": "3",
                }
            ],
        }
        try:
            orders = v50.allocate_buy_orders_v50(
                [
                    {
                        "symbol": "FPT",
                        "rank": 1,
                        "price_vnd": 10000.0,
                        "budget_ceiling_vnd": 100000.0,
                        "underweight_pct": 0.2,
                        "target_gap_vnd": 100000.0,
                    }
                ],
                budget_vnd=100000.0,
                max_orders=1,
                cost_bps=0.0,
            )
        finally:
            v50._current_effective_buying_power = original
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["quantity"], 2)
        self.assertEqual(orders[0]["dnse_qmax"], 2)

    def test_runtime_bindings_are_active(self) -> None:
        self.assertIs(broker_portfolio.latest_broker_portfolio, v50.latest_broker_portfolio_v50)
        self.assertIs(weekly_plan.latest_broker_portfolio, v50.latest_broker_portfolio_v50)
        self.assertIs(capital_plan.latest_broker_portfolio, v50.latest_broker_portfolio_v50)
        self.assertIs(performance.latest_broker_portfolio, v50.latest_broker_portfolio_v50)
        self.assertIs(weekly_plan.planned_buying_power, v50.planned_buying_power_v50)
        self.assertIs(weekly_plan.allocate_buy_orders, v50.allocate_buy_orders_v50)
        self.assertIs(capital_plan.create_weekly_plan, v50.create_weekly_plan_v50)


if __name__ == "__main__":
    unittest.main()
