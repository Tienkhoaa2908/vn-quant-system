from __future__ import annotations

import unittest

from he_thong_dinh_luong import c3_multisignal_gates_v64 as v64


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
        "new_to_canonical_top10": False,
    }
    base.update(updates)
    return base


class V64GateContractTests(unittest.TestCase):
    def test_vpi_like_rank_blind_spot_can_be_caught_by_price_relative_gate(self):
        row = feature(preview_rank=10, distance_ma20=-0.03, relative_5=-0.06, drawdown_20=-0.07)
        self.assertFalse(v64.gate_matches("P01_RANK_OUT20", row))
        self.assertTrue(v64.gate_matches("P05_MA20_REL5", row))
        self.assertTrue(v64.gate_matches("P13_MULTI_2OF4", row))

    def test_rank_collapse_gate_remains_available(self):
        self.assertTrue(v64.gate_matches("P01_RANK_OUT20", feature(preview_rank=25)))

    def test_two_week_confirmation_requires_prior_composite(self):
        current = feature(distance_ma20=-0.02, relative_5=-0.04)
        prior_bad = feature(distance_ma20=-0.01, relative_5=-0.05)
        prior_good = feature()
        self.assertTrue(v64.gate_matches("P15_CONFIRM_2W", current, prior_bad))
        self.assertFalse(v64.gate_matches("P15_CONFIRM_2W", current, prior_good))

    def test_new_top5_trend_gate_excludes_canonical_top10(self):
        row = feature(canonical_rank=21, preview_rank=2, new_to_canonical_top10=True, distance_ma20=0.04, distance_ma50=0.06)
        self.assertTrue(v64.gate_matches("O02_TOP5_TREND", row))
        self.assertFalse(v64.gate_matches("O02_TOP5_TREND", feature(preview_rank=2)))

    def test_velocity_gate_requires_prior_6_to_20(self):
        row = feature(canonical_rank=21, preview_rank=3, prior_preview_rank=12, rank_delta=-9, new_to_canonical_top10=True, volume_ratio_5_20=1.2)
        self.assertTrue(v64.gate_matches("O08_VELOCITY_20_TO5", row))

    def test_top5_raw_is_not_mistaken_for_filtered_gate(self):
        row = feature(canonical_rank=15, preview_rank=5, new_to_canonical_top10=True, distance_ma20=-0.05, distance_ma50=-0.08)
        self.assertTrue(v64.gate_matches("O01_TOP5_RAW", row))
        self.assertFalse(v64.gate_matches("O02_TOP5_TREND", row))

    def test_gate_matrix_has_broad_fixed_coverage(self):
        self.assertGreaterEqual(len(v64.PROTECTION_GATES), 15)
        self.assertGreaterEqual(len(v64.OPPORTUNITY_GATES), 15)
        self.assertEqual(len(v64.ALL_GATES), len({g.gate_id for g in v64.ALL_GATES}))

    def test_august_is_not_selection_default(self):
        self.assertEqual(v64.SELECTION_END_DEFAULT.isoformat(), "2026-07-31")
        self.assertEqual(v64.ANALYSIS_END_DEFAULT.isoformat(), "2026-08-13")
        self.assertFalse(v64.LIVE_MODEL_CHANGE_AUTHORIZED)
        self.assertFalse(v64.TURNOVER_IS_VETO)


if __name__ == "__main__":
    unittest.main()
