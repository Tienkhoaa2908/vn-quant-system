from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.anytime_pipeline import resolve_mode
from he_thong_dinh_luong.eod_hang_ngay import VN_TZ
from he_thong_dinh_luong.portfolio_weighting import (
    dynamic_capital_budget,
    optimized_weights,
    reference_scores,
)


class AnytimeModeTests(unittest.TestCase):
    def test_auto_snapshot_before_18_and_final_after_18(self) -> None:
        morning = datetime(2026, 7, 31, 10, 30, tzinfo=VN_TZ)
        evening = datetime(2026, 7, 31, 18, 30, tzinfo=VN_TZ)
        self.assertEqual(resolve_mode("auto", now=morning), "snapshot")
        self.assertEqual(resolve_mode("auto", now=evening), "final")
        self.assertEqual(resolve_mode("snapshot", now=evening), "snapshot")

    def test_past_target_resolves_final(self) -> None:
        morning = datetime(2026, 7, 31, 10, 30, tzinfo=VN_TZ)
        self.assertEqual(
            resolve_mode("auto", now=morning, target_date=date(2026, 7, 30)),
            "final",
        )


class WeightingTests(unittest.TestCase):
    def test_weights_are_not_equal_and_respect_eligibility_and_cap(self) -> None:
        weights, selected = optimized_weights(
            symbols=["AAA", "BBB", "CCC", "DDD"],
            scores=[0.95, 0.80, 0.70, 0.99],
            confidence=[0.9, 0.8, 0.7, 1.0],
            volatility_60=[0.01, 0.02, 0.04, 0.01],
            eligible=[True, True, True, False],
            budget_pct=30,
            top_k=3,
            max_symbol_weight_pct=15,
        )
        self.assertEqual(selected, ["AAA", "BBB", "CCC"])
        self.assertNotIn("DDD", weights)
        self.assertAlmostEqual(sum(weights.values()), 30.0, places=7)
        self.assertTrue(all(value <= 15.0 + 1e-9 for value in weights.values()))
        self.assertGreater(weights["AAA"], weights["CCC"])
        self.assertGreater(len({round(value, 6) for value in weights.values()}), 1)

    def test_dynamic_budget_reduces_weak_provisional_risk(self) -> None:
        final = dynamic_capital_budget(
            regime="RISK_ON",
            validation_rank_ic=0.05,
            validation_top_return=0.02,
            breadth_above_ma250=0.8,
            provisional=False,
        )
        provisional = dynamic_capital_budget(
            regime="RISK_ON",
            validation_rank_ic=-0.05,
            validation_top_return=-0.02,
            breadth_above_ma250=0.3,
            provisional=True,
        )
        self.assertGreater(final, provisional)
        self.assertGreaterEqual(provisional, 10)

    def test_reference_score_rewards_consistent_strength(self) -> None:
        strong = {
            "dong_luong_12_1": 0.5,
            "suc_manh_tuong_doi_120": 0.3,
            "bien_dong_60": 0.01,
            "khoang_cach_ma60": 0.2,
            "khoang_cach_ma120": 0.2,
            "khoang_cach_ma250": 0.2,
            "loi_nhuan_20": 0.1,
            "loi_nhuan_60": 0.2,
            "loi_nhuan_120": 0.3,
            "loi_nhuan_250": 0.4,
        }
        weak = {
            "dong_luong_12_1": -0.2,
            "suc_manh_tuong_doi_120": -0.2,
            "bien_dong_60": 0.05,
            "khoang_cach_ma60": -0.1,
            "khoang_cach_ma120": -0.1,
            "khoang_cach_ma250": -0.1,
            "loi_nhuan_20": -0.1,
            "loi_nhuan_60": -0.1,
            "loi_nhuan_120": -0.1,
            "loi_nhuan_250": -0.1,
        }
        scores, components, confidence = reference_scores([strong, weak])
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(len(components), 2)
        self.assertTrue(all(0 <= value <= 1 for value in confidence))


if __name__ == "__main__":
    unittest.main()
