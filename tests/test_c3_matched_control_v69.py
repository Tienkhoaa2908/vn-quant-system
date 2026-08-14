from __future__ import annotations

import unittest

from he_thong_dinh_luong import c3_matched_control_v69 as v69


class FakeOutcomeStore:
    def __init__(self, mapping):
        self.mapping = mapping

    def outcome(self, symbol, signal_day, horizon=10):
        return self.mapping.get((symbol, signal_day.isoformat()))


def state(day, symbol, canonical_rank, preview_rank):
    return {
        "phase": "HISTORICAL_SELECTION",
        "evaluation_day": day,
        "canonical_day": "2025-01-31",
        "symbol": symbol,
        "canonical_rank": str(canonical_rank),
        "preview_rank": str(preview_rank),
        "prior_preview_rank": "6",
        "rank_delta": "-3",
        "score_delta": "0.05",
        "eligible_now": "True",
        "distance_ma20": "0.05",
        "distance_ma50": "0.04",
        "return_5": "0.03",
        "return_10": "0.04",
        "return_20": "0.08",
        "relative_5": "0.03",
        "relative_10": "0.04",
        "relative_20": "0.06",
        "drawdown_20": "0",
        "drawdown_60": "0",
        "volume_ratio_5_20": "1.2",
        "realized_vol_ratio_20_60": "1.0",
        "breakout_20_gap": "0.01",
        "breakdown_20_low_gap": "0.10",
    }


class TestC3MatchedControlV69(unittest.TestCase):
    def test_signflip_pvalue_never_zero(self):
        weekly = {f"2025-{month:02d}-07": 0.02 for month in range(1, 13)}
        result = v69._signflip_and_bootstrap(
            weekly, signflip_samples=1000, bootstrap_samples=1000, seed=1
        )
        self.assertGreater(result["signflip_two_sided_p"], 0.0)
        self.assertLessEqual(result["signflip_two_sided_p"], 1.0)
        self.assertGreater(result["observed_block_mean"], 0.0)

    def test_leader_uses_same_week_raw_top5_comparator(self):
        day = "2025-02-07"
        states = [state(day, "AAA", 99, 2), state(day, "BBB", 99, 4)]
        outcomes = FakeOutcomeStore({
            ("AAA", day): {"forward_return": 0.10, "forward_excess_return": 0.10, "mae_10": -0.02, "mfe_10": 0.12},
            ("BBB", day): {"forward_return": -0.10, "forward_excess_return": -0.10, "mae_10": -0.12, "mfe_10": 0.01},
        })
        events = [{
            "phase": "HISTORICAL_SELECTION", "evaluation_day": day,
            "cohort_id": "L15_PERSIST_REL", "kind": "LEADER", "horizon": "10",
            "symbol": "AAA", "forward_return": "0.10", "forward_excess_return": "0.10",
            "mae_10": "-0.02", "mfe_10": "0.12",
        }]
        rows, _ = v69._leader_audit(
            events, states, outcomes, variant_id="TEST",
            signflip_samples=1000, bootstrap_samples=1000, seed=2,
        )
        row = next(item for item in rows if item["cohort_id"] == "L15_PERSIST_REL")
        self.assertEqual(row["comparator"], "SAME_WEEK_RAW_EMERGING_TOP5")
        self.assertAlmostEqual(row["matched_week_delta_mean"], 0.10, places=12)

    def test_risk_uses_unsignalled_same_week_canonical_control(self):
        day = "2025-04-04"
        states = [state(day, "AAA", 1, 13), state(day, "BBB", 2, 3)]
        outcomes = FakeOutcomeStore({
            ("AAA", day): {"forward_return": -0.10, "forward_excess_return": -0.11, "mae_10": -0.15, "mfe_10": 0.01},
            ("BBB", day): {"forward_return": 0.02, "forward_excess_return": 0.01, "mae_10": -0.03, "mfe_10": 0.06},
        })
        events = [{
            "phase": "HISTORICAL_SELECTION", "evaluation_day": day,
            "cohort_id": "R03_RANK_DROP8", "kind": "RISK", "horizon": "10",
            "symbol": "AAA", "forward_return": "-0.10", "forward_excess_return": "-0.11",
            "mae_10": "-0.15", "mfe_10": "0.01",
        }]
        rows, _ = v69._risk_audit(
            events, states, outcomes, variant_id="TEST",
            signflip_samples=1000, bootstrap_samples=1000, seed=3,
        )
        row = next(item for item in rows if item["cohort_id"] == "R03_RANK_DROP8")
        self.assertEqual(row["comparator"], "SAME_WEEK_UNSIGNALLED_CANONICAL_TOP10")
        self.assertAlmostEqual(row["matched_control_minus_signal_return_mean"], 0.12, places=12)
        self.assertAlmostEqual(row["matched_signal_minus_control_damage_mean"], 0.12, places=12)

    def test_top10_cohorts_use_top10_comparator(self):
        for cohort_id in ("L10_BREAKOUT20", "L11_RELATIVE_LEADER", "L14_MULTI_4OF6"):
            self.assertEqual(v69._scope_for_leader(cohort_id), 10)
        self.assertEqual(v69._scope_for_leader("L15_PERSIST_REL"), 5)


if __name__ == "__main__":
    unittest.main()
