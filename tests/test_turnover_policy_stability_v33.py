from __future__ import annotations

import unittest

from src.he_thong_dinh_luong import turnover_policy_stability_v33 as v33


class TurnoverPolicyStabilityV33Tests(unittest.TestCase):
    def test_cap_grid_requires_pre_registered_cap_three(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "V33_PRE_REGISTERED_CAP_3_REQUIRED"
        ):
            v33._normalize_caps((0, 1, 2))

    def test_cap_grid_is_sorted_and_unique(self) -> None:
        self.assertEqual(v33._normalize_caps((3, 1, 3, 2)), (1, 2, 3))

    def test_cap_three_can_freeze_only_for_future_holdout(self) -> None:
        summary = [
            {
                "fixed_replacement_cap": 3,
                "base_relative_total_return": 0.20,
                "stress_relative_total_return": 0.18,
                "base_leave_best_period_out_relative_total_return": 0.05,
                "base_mean_turnover": 0.30,
            }
        ]
        paired = [
            {
                "fixed_replacement_cap": 3,
                "bootstrap_probability_delta_positive": 0.90,
                "leave_best_3_mean_net_excess_delta": 0.001,
            }
        ]
        decisions, recommendation = v33._decision_rows(summary, paired)
        self.assertTrue(decisions[0]["future_holdout_freeze_candidate"])
        self.assertFalse(decisions[0]["historical_promotion_allowed"])
        self.assertEqual(
            recommendation,
            "FREEZE_C3_FIXED_CAP_3_FOR_FUTURE_PAPER_HOLDOUT_ONLY",
        )

    def test_posthoc_non_three_cap_cannot_be_freeze_candidate(self) -> None:
        summary = [
            {
                "fixed_replacement_cap": 6,
                "base_relative_total_return": 0.30,
                "stress_relative_total_return": 0.25,
                "base_leave_best_period_out_relative_total_return": 0.10,
                "base_mean_turnover": 0.40,
            }
        ]
        paired = [
            {
                "fixed_replacement_cap": 6,
                "bootstrap_probability_delta_positive": 0.95,
                "leave_best_3_mean_net_excess_delta": 0.002,
            }
        ]
        decisions, recommendation = v33._decision_rows(summary, paired)
        self.assertTrue(decisions[0]["sensitivity_gate_passed"])
        self.assertFalse(decisions[0]["future_holdout_freeze_candidate"])
        self.assertEqual(
            recommendation,
            "KEEP_C3_NESTED_REFERENCE_AND_REDESIGN_TURNOVER_POLICY",
        )


if __name__ == "__main__":
    unittest.main()
