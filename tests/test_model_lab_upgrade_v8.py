from __future__ import annotations

from datetime import date, timedelta
import unittest

from he_thong_dinh_luong.model_lab_upgrade_v9 import (
    _tail_relevance,
    _top_tail_target,
    select_score_orientation,
    strict_reference_gate,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row


def _rows(days: int = 2, symbols: int = 10) -> list[Row]:
    output: list[Row] = []
    start = date(2026, 1, 30)
    for day_index in range(days):
        day = start + timedelta(days=31 * day_index)
        for index in range(symbols):
            output.append(
                Row(
                    ngay=day,
                    ma=f"S{index:02d}",
                    features={},
                    relative_return=float(index),
                    label_end=day + timedelta(days=20),
                )
            )
    return output


class ModelLabUpgradeV9Tests(unittest.TestCase):
    def test_top_tail_target_emphasizes_only_upper_cross_section(self):
        rows = _rows(days=1, symbols=10)
        target = [float(value) for value in _top_tail_target(rows)]
        self.assertEqual(sum(value > 0.0 for value in target), 2)
        self.assertAlmostEqual(target[-1], 1.0)
        self.assertGreater(target[-1], target[-2])
        self.assertTrue(all(value == 0.0 for value in target[:-2]))

    def test_tail_relevance_has_extra_resolution_near_top(self):
        relevance = _tail_relevance(_rows(days=1, symbols=10))
        self.assertEqual(relevance[-1], 4)
        self.assertEqual(relevance[-2], 3)
        self.assertGreater(relevance[-3], relevance[0])

    def test_orientation_inverts_validation_scores_when_tail_is_reversed(self):
        rows = _rows(days=2, symbols=10)
        reversed_scores = []
        for _day in range(2):
            reversed_scores.extend(float(10 - index) for index in range(10))
        self.assertEqual(
            select_score_orientation(rows, reversed_scores),
            -1.0,
        )

    def test_strict_reference_gate_rejects_ic_without_investable_alpha(self):
        row = {
            "oos_folds": 24,
            "mean_rank_ic": 0.049,
            "positive_rank_ic_ratio": 0.583,
            "top_k_relative_return": 0.0029,
            "average_net_excess_return": -0.0021,
            "positive_net_excess_ratio": 0.417,
            "relative_total_return": -0.085,
            "degenerate_fold_ratio": 0.0,
        }
        gate = strict_reference_gate(
            row,
            mean_turnover=0.848,
            positive_component_count=1,
        )
        self.assertTrue(gate["mean_rank_ic_at_least_003"])
        self.assertFalse(gate["average_net_excess_positive"])
        self.assertFalse(gate["relative_total_return_positive"])
        self.assertFalse(gate["turnover_controlled"])
        self.assertFalse(gate["two_independent_positive_components"])
        self.assertFalse(all(gate.values()))

    def test_strict_reference_gate_accepts_complete_reference_evidence(self):
        row = {
            "oos_folds": 24,
            "mean_rank_ic": 0.04,
            "positive_rank_ic_ratio": 0.58,
            "top_k_relative_return": 0.004,
            "average_net_excess_return": 0.002,
            "positive_net_excess_ratio": 0.54,
            "relative_total_return": 0.03,
            "degenerate_fold_ratio": 0.0,
        }
        gate = strict_reference_gate(
            row,
            mean_turnover=0.45,
            positive_component_count=2,
        )
        self.assertTrue(all(gate.values()))

    def test_zero_degenerate_ratio_is_not_replaced_by_default(self):
        row = {
            "oos_folds": 24,
            "mean_rank_ic": 0.04,
            "positive_rank_ic_ratio": 0.58,
            "top_k_relative_return": 0.004,
            "average_net_excess_return": 0.002,
            "positive_net_excess_ratio": 0.54,
            "relative_total_return": 0.03,
            "degenerate_fold_ratio": "0.0",
        }
        gate = strict_reference_gate(
            row,
            mean_turnover=0.45,
            positive_component_count=2,
        )
        self.assertTrue(gate["no_degenerate_folds"])


if __name__ == "__main__":
    unittest.main()
