import unittest
from datetime import date

from he_thong_dinh_luong.tail_risk_overlay_v56 import (
    OVERLAYS,
    OverlaySpec,
    can_buy_symbol,
    risk_trigger,
    segment_metrics,
)


class TailRiskOverlayV56Tests(unittest.TestCase):
    def test_baseline_never_triggers(self):
        self.assertIsNone(
            risk_trigger(
                OVERLAYS[0],
                close_price=80.0,
                average_cost=100.0,
                position_quantity=10,
                portfolio_nav=1000.0,
                moving_average=None,
            )
        )

    def test_nav_loss_budget_targets_portfolio_damage(self):
        spec = OverlaySpec("NAVLOSS_100", nav_loss_budget=0.01)
        trigger = risk_trigger(
            spec,
            close_price=90.0,
            average_cost=100.0,
            position_quantity=2,
            portfolio_nav=2000.0,
            moving_average=None,
        )
        self.assertIsNotNone(trigger)
        self.assertAlmostEqual(trigger["position_loss_nav"], -0.01)
        self.assertIn("NAV_LOSS_BUDGET", trigger["reason"])

    def test_ma_confirmation_requires_close_below_ma(self):
        spec = OverlaySpec(
            "STOP_10_MA20",
            stock_stop_loss=0.10,
            ma_confirmation_days=20,
        )
        self.assertIsNone(
            risk_trigger(
                spec,
                close_price=89.0,
                average_cost=100.0,
                position_quantity=1,
                portfolio_nav=1000.0,
                moving_average=88.0,
            )
        )
        self.assertIsNotNone(
            risk_trigger(
                spec,
                close_price=89.0,
                average_cost=100.0,
                position_quantity=1,
                portfolio_nav=1000.0,
                moving_average=95.0,
            )
        )

    def test_cooldown_releases_only_on_new_monthly_signal(self):
        cooldown = {"VPI": 12}
        self.assertFalse(
            can_buy_symbol(
                "VPI",
                current_signal_index=12,
                cooldown_signal_index=cooldown,
            )
        )
        self.assertTrue(
            can_buy_symbol(
                "VPI",
                current_signal_index=13,
                cooldown_signal_index=cooldown,
            )
        )

    def test_segment_metrics_rebases_drawdown(self):
        rows = [
            {"day": "2022-01-03", "unit_price": 1.0, "worst_position_loss_nav": -0.01, "worst_position_return": -0.05, "largest_symbol_weight": 0.10},
            {"day": "2022-01-04", "unit_price": 1.1, "worst_position_loss_nav": -0.02, "worst_position_return": -0.08, "largest_symbol_weight": 0.12},
            {"day": "2022-01-05", "unit_price": 0.99, "worst_position_loss_nav": -0.03, "worst_position_return": -0.10, "largest_symbol_weight": 0.11},
        ]
        metrics = segment_metrics(rows, start=date(2022, 1, 3), end=date(2022, 1, 5))
        self.assertAlmostEqual(metrics["max_drawdown"], -0.10)
        self.assertAlmostEqual(metrics["worst_position_loss_nav"], -0.03)


if __name__ == "__main__":
    unittest.main()
