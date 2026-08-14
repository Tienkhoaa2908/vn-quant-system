from __future__ import annotations

import unittest

from he_thong_dinh_luong import c3_adaptive_weight_v71 as base
from he_thong_dinh_luong import c3_adaptive_weight_v71_reportfix as fix


class TestV71ReportingFix(unittest.TestCase):
    def _row(self, candidate: str, cost: str, start: str, end: str, strategy_return: float, benchmark_return: float):
        return {
            "variant_id": "GAP18_CLEAN",
            "allocator": "EQUAL",
            "candidate_id": candidate,
            "cost_scenario": cost,
            "strategy_id": "TEST",
            "period_start_day": start,
            "period_end_day": end,
            "strategy_return": strategy_return,
            "benchmark_return": benchmark_return,
            "source": "TEST",
        }

    def test_rebuild_preserves_cost_scenario_and_shadow_contains_adaptive(self):
        frozen = base.CHAMPION_MODEL
        adaptive = "C3_IC_EWMA_HL24"
        monthly = []
        for cost in ("GROSS", "BASE_DNSE", "STRESS", "SEVERE"):
            monthly += [
                self._row(frozen, cost, "2026-03-02", "2026-04-01", -0.02, 0.01),
                self._row(frozen, cost, "2026-04-01", "2026-05-04", -0.10, 0.09),
                self._row(adaptive, cost, "2026-03-02", "2026-04-01", -0.01, 0.01),
                self._row(adaptive, cost, "2026-04-01", "2026-05-04", -0.05, 0.09),
            ]
        annual = fix.rebuild_annual_from_monthly(monthly)
        self.assertTrue(annual)
        self.assertTrue(all(row["cost_scenario"] for row in annual))
        base_rows = [row for row in annual if row["cost_scenario"] == "BASE_DNSE"]
        self.assertEqual({row["candidate_id"] for row in base_rows}, {frozen, adaptive})
        shadow = base._shadow_2026(annual, monthly)
        by_candidate = {row["candidate_id"]: row for row in shadow}
        self.assertIn(frozen, by_candidate)
        self.assertIn(adaptive, by_candidate)
        self.assertFalse(by_candidate[adaptive]["used_for_selection"])
        self.assertAlmostEqual(by_candidate[adaptive]["april_2026_candidate_minus_frozen"], 0.05, places=12)


if __name__ == "__main__":
    unittest.main()
