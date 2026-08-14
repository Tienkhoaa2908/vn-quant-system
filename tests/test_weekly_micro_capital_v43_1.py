from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong import weekly_micro_capital_v43 as base
from he_thong_dinh_luong import weekly_micro_capital_v43_1 as subject


class WeeklyMicroCapitalV431Tests(unittest.TestCase):
    def test_regular_policy_can_redeploy_all_available_cash(self) -> None:
        self.assertEqual(
            subject.deployable_cash(
                policy_id="P1_TOP10_UNDERWEIGHT_BUFFER20",
                cash=1_000_000.0,
                contribution=250_000,
                risk_on=False,
            ),
            1_000_000.0,
        )

    def test_risk_half_policy_throttles_only_risk_off(self) -> None:
        policy_id = "P6_TOP10_UNDERWEIGHT_BUFFER20_RISK_HALF"
        self.assertEqual(
            subject.deployable_cash(
                policy_id=policy_id,
                cash=1_000_000.0,
                contribution=250_000,
                risk_on=False,
            ),
            125_000.0,
        )
        self.assertEqual(
            subject.deployable_cash(
                policy_id=policy_id,
                cash=1_000_000.0,
                contribution=250_000,
                risk_on=True,
            ),
            1_000_000.0,
        )

    def test_dynamic_cap_converges_to_frozen_symbol_cap(self) -> None:
        self.assertEqual(
            subject.effective_symbol_cap(
                base_cap=0.15,
                target_count=10,
                established_target_positions=0,
                symbol_already_held=False,
            ),
            1.0,
        )
        self.assertEqual(
            subject.effective_symbol_cap(
                base_cap=0.15,
                target_count=10,
                established_target_positions=1,
                symbol_already_held=False,
            ),
            0.5,
        )
        self.assertAlmostEqual(
            subject.effective_symbol_cap(
                base_cap=0.15,
                target_count=10,
                established_target_positions=9,
                symbol_already_held=False,
            ),
            0.15,
        )

    def test_large_target_gap_can_use_more_than_new_contribution(self) -> None:
        day = date(2020, 1, 2)
        prices = base.PriceStore(
            opens={("AAA", day): 10_000.0},
            closes={("AAA", day): 10_000.0},
            history_days={"AAA": [day]},
            history_closes={"AAA": [10_000.0]},
            index_open={day: 1_000.0},
            index_close={day: 1_000.0},
            calendar=[day],
        )
        budget, gap, _ = subject.candidate_budget(
            symbol="AAA",
            target_symbols=("AAA",),
            target_weights={"AAA": 0.15},
            holdings={},
            prices=prices,
            day=day,
            account_value=10_000_000.0,
            deployable=5_000_000.0,
            contribution=250_000,
            target_count=10,
            base_symbol_cap=0.15,
            slippage_bps=20.0,
        )
        self.assertEqual(gap, 1_500_000.0)
        self.assertGreater(budget, 250_000.0)

    def test_immediate_exit_sale_proceeds_are_reused(self) -> None:
        policy_id = "TEST_V43_1_FULL_CASH"
        original = subject.POLICIES.get(policy_id)
        subject.POLICIES[policy_id] = {
            "target_count": 1,
            "exit_rank": 1,
            "exit_months": 1,
            "buy_rule": "UNDERWEIGHT",
            "risk_off_fraction": 1.0,
            "risk_on_release_multiple": 1.0,
            "symbol_cap": 1.0,
            "cash_redeployment_mode": "TEST",
        }
        try:
            first_signal = date(2020, 1, 1)
            first_week = date(2020, 1, 2)
            second_signal = date(2020, 1, 8)
            second_week = date(2020, 1, 9)
            prices = base.PriceStore(
                opens={
                    ("AAA", first_week): 10.0,
                    ("AAA", second_week): 10.0,
                    ("BBB", second_week): 10.0,
                },
                closes={
                    ("AAA", first_week): 10.0,
                    ("AAA", second_week): 10.0,
                    ("BBB", second_week): 10.0,
                },
                history_days={
                    "AAA": [first_week, second_week],
                    "BBB": [second_week],
                },
                history_closes={
                    "AAA": [10.0, 10.0],
                    "BBB": [10.0],
                },
                index_open={first_week: 100.0, second_week: 100.0},
                index_close={first_week: 100.0, second_week: 100.0},
                calendar=[first_week, second_week],
            )
            snapshots = [
                base.SignalSnapshot(
                    first_signal,
                    ("AAA",),
                    {},
                    {"AAA": 1.0},
                    True,
                ),
                base.SignalSnapshot(
                    second_signal,
                    ("BBB",),
                    {},
                    {"BBB": 1.0},
                    True,
                ),
            ]
            summary, _, trades = subject._simulate(
                policy_id=policy_id,
                contribution=1_000,
                scenario="BASE",
                snapshots=snapshots,
                prices=prices,
                weekly_days=[first_week, second_week],
            )
            buys = [row for row in trades if row["side"] == "BUY"]
            self.assertEqual(len(buys), 2)
            self.assertGreater(
                abs(float(buys[1]["cash_effect_vnd"])),
                1_000.0,
            )
            self.assertLess(float(summary["ending_cash_ratio"]), 0.01)
        finally:
            if original is None:
                subject.POLICIES.pop(policy_id, None)
            else:
                subject.POLICIES[policy_id] = original


if __name__ == "__main__":
    unittest.main()
