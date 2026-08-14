from __future__ import annotations

import unittest
from datetime import date

from he_thong_dinh_luong import c3_short_horizon_v60 as v60
from he_thong_dinh_luong.weekly_micro_capital_v43 import SignalSnapshot


class V60CausalRulesTests(unittest.TestCase):
    def snapshots(self):
        return [
            SignalSnapshot(
                day=date(2026, 5, 29),
                ranking=("AAA", "BBB", "CCC"),
                weights={"low_volatility": 1/3, "relative_strength_120": 1/3, "high_52_week": 1/3},
                volatility={"AAA": .1, "BBB": .1, "CCC": .1},
                risk_on=True,
            ),
            SignalSnapshot(
                day=date(2026, 6, 30),
                ranking=("DDD", "EEE", "FFF"),
                weights={"low_volatility": 1/3, "relative_strength_120": 1/3, "high_52_week": 1/3},
                volatility={"DDD": .1, "EEE": .1, "FFF": .1},
                risk_on=True,
            ),
        ]

    def test_same_month_canonical_is_not_used_before_month_completion(self):
        snapshots = self.snapshots()
        days = [row.day for row in snapshots]
        selected = v60._canonical_snapshot_for_day(
            snapshots, days, date(2026, 6, 26)
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.day, date(2026, 5, 29))

    def test_previous_month_becomes_canonical_in_next_month(self):
        snapshots = self.snapshots()
        days = [row.day for row in snapshots]
        selected = v60._canonical_snapshot_for_day(
            snapshots, days, date(2026, 7, 3)
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.day, date(2026, 6, 30))

    def test_new_preview_leader_is_distinguished_from_canonical(self):
        canonical = SignalSnapshot(
            day=date(2026, 6, 30),
            ranking=tuple(["OLD"] + [f"C{i}" for i in range(2, 25)]),
            weights={"low_volatility": 1/3, "relative_strength_120": 1/3, "high_52_week": 1/3},
            volatility={},
            risk_on=True,
        )
        preview = [
            v60.PreviewRow("NEW", 1, .9, .1),
            v60.PreviewRow("OLD", 2, .8, .1),
        ] + [
            v60.PreviewRow(f"X{i}", i, .5, .1) for i in range(3, 12)
        ]
        cohorts = v60._cohort_members(preview, canonical)
        self.assertIn("NEW", cohorts["NEW_PREVIEW_TOP10"])
        self.assertIn("NEW", cohorts["NEW_PREVIEW_TOP5"])
        self.assertIn("OLD", cohorts["CANONICAL_TOP10_RETAINED"])

    def test_august_2026_default_is_excluded(self):
        self.assertEqual(v60.ANALYSIS_END_DEFAULT, date(2026, 7, 31))


if __name__ == "__main__":
    unittest.main()
