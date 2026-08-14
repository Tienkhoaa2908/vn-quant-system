from __future__ import annotations

import unittest

from he_thong_dinh_luong import frozen_component_candidate_v28 as v28


class FrozenComponentCandidateV28Tests(unittest.TestCase):
    def test_candidate_gate_requires_exact_frozen_model_and_breadth(self) -> None:
        row = {
            "breadth": "10",
            "model": v28.FROZEN_MODEL,
            "v27_decision_gate_passed": "true",
            "fixed_breadth_fully_feasible": "true",
            "availability_capped_outer_period_count": "0",
        }
        selected = v28._candidate_gate_row([row])
        self.assertEqual(selected["model"], v28.FROZEN_MODEL)

        rejected = dict(row)
        rejected["availability_capped_outer_period_count"] = "1"
        with self.assertRaisesRegex(
            ValueError,
            "V28_FROZEN_BREADTH_USED_CASH_SLOT_HOTFIX",
        ):
            v28._candidate_gate_row([rejected])

    def test_prediction_rebuild_requires_same_score_and_rank(self) -> None:
        source = [{
            "model": v28.FROZEN_MODEL,
            "test_date": "2026-01-30",
            "symbol": "AAA",
            "score": "0.75",
            "rank": "1",
            "label_end": "2026-02-27",
            "stock_return": "0.10",
            "benchmark_return": "0.02",
            "relative_return": "0.08",
        }]
        rebuilt = [dict(source[0])]
        result = v28.compare_prediction_rows(source, rebuilt)
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["row_count"], 1)

        rebuilt[0]["rank"] = "2"
        with self.assertRaisesRegex(
            ValueError,
            "V28_PREDICTION_RANK_MISMATCH",
        ):
            v28.compare_prediction_rows(source, rebuilt)

    def test_forward_eligibility_ignores_only_missing_t1(self) -> None:
        self.assertTrue(v28._forward_reason_is_eligible("thieu_open_t1"))
        self.assertTrue(v28._forward_reason_is_eligible(""))
        self.assertFalse(
            v28._forward_reason_is_eligible(
                "khong_dat_ma250|thieu_open_t1"
            )
        )

    def test_public_contract_never_approves_live_capital(self) -> None:
        self.assertEqual(v28.FROZEN_BREADTH, 10)
        self.assertEqual(
            v28.FROZEN_MODEL,
            "C3_STABLE_3_PAST_IC_SHRUNK",
        )
        self.assertGreaterEqual(
            v28.MINIMUM_FUTURE_HOLDOUT_MONTHS,
            12,
        )


if __name__ == "__main__":
    unittest.main()
