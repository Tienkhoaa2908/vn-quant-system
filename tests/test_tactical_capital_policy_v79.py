from __future__ import annotations

import unittest
from datetime import date

from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong import tactical_capital_policy_v79 as v79
from he_thong_dinh_luong import weekly_overlay_backtest_v72 as v72


class TestTacticalCapitalPolicyV79(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "symbol": "AAA",
            "canonical_rank": 1,
            "preview_rank": 18,
            "prior_preview_rank": 17,
            "preview_score": 0.1,
            "eligible_now": True,
            "relative_5": -0.03,
            "drawdown_20": -0.05,
            "drawdown_60": -0.06,
            "volume_ratio_5_20": 1.2,
        }
        row.update(overrides)
        return row

    def test_policy_matrix_unique_and_complete(self):
        ids = [policy.policy_id for policy in v79.POLICIES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "NO_OVERLAY")
        for expected in {
            "DRAG_PERSIST_TRIM25_CASH",
            "DRAG_PERSIST_TRIM50_CASH",
            "SEVERE_DRAG_EXIT100_CASH",
            "L15_SWAP25_WORST",
            "L15_CASH_ADD25_SLOT",
            "DRAG_L15_ROTATE25",
            "DRAG_L15_ROTATE50",
            "COMBINED50_CASHFALLBACK25",
        }:
            self.assertIn(expected, ids)
        families = {policy.family for policy in v79.POLICIES}
        self.assertTrue({"BASELINE", "V72_ANCHOR", "INCUMBENT_CUT", "EMERGING_ADD", "ROTATION", "COMBINED"} <= families)

    def test_v72_anchor_ids_are_real(self):
        v72_ids = {policy.policy_id for policy in v72.POLICIES}
        for policy in v79.POLICIES:
            if policy.anchor_v72_id:
                self.assertIn(policy.anchor_v72_id, v72_ids)

    def test_period_drag_uses_next_session_open(self):
        cal = [date(2025, 1, 31), date(2025, 2, 3), date(2025, 2, 4), date(2025, 2, 7)]
        market = v70.Market(
            cal,
            {date(2025, 1, 31): 990.0, date(2025, 2, 3): 1000.0, date(2025, 2, 4): 1010.0, date(2025, 2, 7): 1020.0},
            {date(2025, 1, 31): 995.0, date(2025, 2, 3): 1005.0, date(2025, 2, 4): 1015.0, date(2025, 2, 7): 1020.0},
            {("AAA", date(2025, 2, 3)): 100.0},
            {("AAA", date(2025, 2, 7)): 90.0},
            {},
        )
        signal = v72.WeeklySignal(date(2025, 2, 7), date(2025, 1, 31), {})
        drag = v79.period_drag_metrics(market, "AAA", signal)
        self.assertIsNotNone(drag)
        assert drag is not None
        self.assertEqual(drag["period_entry_day"], "2025-02-03")
        self.assertAlmostEqual(float(drag["period_return"]), -0.10)
        self.assertAlmostEqual(float(drag["period_benchmark_return"]), 0.02)
        self.assertAlmostEqual(float(drag["period_relative_return"]), -0.12)
        self.assertTrue(drag["dragging_current_period"])

    def test_drag_persist_requires_real_prior_week(self):
        policy = v79._POLICY_BY_ID["DRAG_PERSIST_TRIM50_CASH"]
        drag = {"dragging_current_period": True}
        self.assertTrue(v79._risk_match(policy, self._row(), drag))
        self.assertFalse(v79._risk_match(policy, self._row(prior_preview_rank=None), drag))
        self.assertFalse(v79._risk_match(policy, self._row(preview_rank=14), drag))
        self.assertFalse(v79._risk_match(policy, self._row(relative_5=-0.01), drag))
        self.assertFalse(v79._risk_match(policy, self._row(), {"dragging_current_period": False}))

    def test_severe_exit_needs_persistent_drag_plus_severe_condition(self):
        policy = v79._POLICY_BY_ID["SEVERE_DRAG_EXIT100_CASH"]
        drag = {"dragging_current_period": True}
        self.assertFalse(v79._risk_match(policy, self._row(), drag))
        self.assertTrue(v79._risk_match(policy, self._row(eligible_now=False), drag))
        self.assertTrue(v79._risk_match(policy, self._row(eligible_now="false"), drag))
        self.assertTrue(v79._risk_match(policy, self._row(drawdown_20=-0.081), drag))
        self.assertTrue(v79._risk_match(policy, self._row(drawdown_60=-0.121), drag))

    def test_exact_l15_is_reused_without_fake_persistence(self):
        good = self._row(canonical_rank=15, preview_rank=3, prior_preview_rank=8,
                         relative_5=0.025, volume_ratio_5_20=1.2)
        self.assertTrue(v79._l15(good))
        self.assertFalse(v79._l15({**good, "prior_preview_rank": None}))
        self.assertFalse(v79._l15({**good, "relative_5": 0.019}))
        self.assertFalse(v79._l15({**good, "volume_ratio_5_20": 0.99}))

    def test_2026_is_not_selection_window(self):
        self.assertEqual(v79.PRIMARY_SELECTION_END, date(2025, 12, 31))

    def test_cash_admission_is_bounded(self):
        policy = v79._POLICY_BY_ID["L15_CASH_ADD25_SLOT"]
        self.assertEqual(policy.leader_mode, "CASH_ADD")
        self.assertAlmostEqual(v79.BASE_SLOT_WEIGHT * policy.cash_slot_fraction, 0.025)

    def test_combined_policy_has_rotation_and_fallbacks(self):
        policy = v79._POLICY_BY_ID["COMBINED50_CASHFALLBACK25"]
        self.assertEqual(policy.risk_rule, "DRAG_PERSIST")
        self.assertEqual(policy.leader_mode, "PAIR_RISK")
        self.assertAlmostEqual(policy.risk_fraction, 0.50)
        self.assertTrue(policy.fallback_trim_to_cash)
        self.assertTrue(policy.fallback_cash_add)


if __name__ == "__main__":
    unittest.main()
