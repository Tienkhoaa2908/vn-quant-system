from __future__ import annotations

import unittest

from he_thong_dinh_luong import c3_cohort_matrix_v64 as v64


def feature(**updates):
    base = {
        "canonical_rank": 6,
        "preview_rank": 10,
        "prior_preview_rank": 4,
        "rank_delta": 6,
        "score_delta": -0.02,
        "distance_ma20": 0.02,
        "distance_ma50": 0.03,
        "return_5": 0.01,
        "relative_5": 0.01,
        "relative_10": 0.01,
        "relative_20": 0.02,
        "drawdown_20": -0.02,
        "drawdown_60": -0.04,
        "volume_ratio_5_20": 1.0,
        "realized_vol_ratio_20_60": 1.0,
        "breakout_20_gap": -0.01,
        "breakdown_20_low_gap": 0.05,
        "risk_on": True,
    }
    base.update(updates)
    return base


class V64CohortContractTests(unittest.TestCase):
    def test_vpi_like_rank_blind_spot_can_be_caught_by_price_relative_cohort(self):
        row = feature(preview_rank=10, distance_ma20=-0.03, relative_5=-0.06, drawdown_20=-0.07)
        self.assertFalse(v64.cohort_matches("R01_RANK_OUT20", row))
        self.assertTrue(v64.cohort_matches("R05_MA20_REL5", row))
        self.assertTrue(v64.cohort_matches("R13_MULTI_2OF4", row))

    def test_rank_collapse_cohort_remains_available(self):
        self.assertTrue(v64.cohort_matches("R01_RANK_OUT20", feature(preview_rank=25)))

    def test_two_week_confirmation_requires_prior_composite(self):
        current = feature(distance_ma20=-0.02, relative_5=-0.04)
        prior_bad = feature(distance_ma20=-0.01, relative_5=-0.05)
        prior_good = feature()
        self.assertTrue(v64.cohort_matches("R15_CONFIRM_2W", current, prior_bad))
        self.assertFalse(v64.cohort_matches("R15_CONFIRM_2W", current, prior_good))

    def test_new_top5_trend_cohort_excludes_canonical_top10(self):
        row = feature(canonical_rank=21, preview_rank=2, distance_ma20=0.04, distance_ma50=0.06)
        self.assertTrue(v64.cohort_matches("L02_TOP5_TREND", row))
        self.assertFalse(v64.cohort_matches("L02_TOP5_TREND", feature(preview_rank=2)))

    def test_velocity_cohort_requires_prior_6_to_20(self):
        row = feature(canonical_rank=21, preview_rank=3, prior_preview_rank=12, rank_delta=-9, volume_ratio_5_20=1.2)
        self.assertTrue(v64.cohort_matches("L08_VELOCITY_20_TO5", row))

    def test_top5_raw_is_not_mistaken_for_filtered_cohort(self):
        row = feature(canonical_rank=15, preview_rank=5, distance_ma20=-0.05, distance_ma50=-0.08)
        self.assertTrue(v64.cohort_matches("L01_TOP5_RAW", row))
        self.assertFalse(v64.cohort_matches("L02_TOP5_TREND", row))

    def test_matrix_has_broad_fixed_coverage(self):
        self.assertGreaterEqual(len(v64.RISK_COHORTS), 15)
        self.assertGreaterEqual(len(v64.LEADER_COHORTS), 15)
        self.assertEqual(len(v64.ALL_COHORTS), len({c.cohort_id for c in v64.ALL_COHORTS}))

    def test_august_is_not_selection_default(self):
        self.assertEqual(v64.SELECTION_END_DEFAULT.isoformat(), "2026-07-31")
        self.assertEqual(v64.ANALYSIS_END_DEFAULT.isoformat(), "2026-08-13")
        self.assertFalse(v64.LIVE_MODEL_CHANGE_AUTHORIZED)
        self.assertFalse(v64.TURNOVER_IS_VETO)


if __name__ == "__main__":
    unittest.main()
