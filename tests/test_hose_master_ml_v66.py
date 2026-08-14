from __future__ import annotations

from datetime import date, timedelta
import sqlite3
import unittest

from he_thong_dinh_luong import hose_master_panel_v66 as panel
from he_thong_dinh_luong import hose_walkforward_ml_v66 as ml


class V66HoseMasterMLTests(unittest.TestCase):
    def test_bar_level_exchange_is_preferred(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("""
                CREATE TABLE bars(
                    symbol TEXT, day TEXT, open REAL, high REAL, low REAL,
                    close REAL, volume INTEGER, asset_type TEXT, exchange TEXT
                )
            """)
            source = panel.resolve_venue_source(db)
        self.assertEqual(source.mode, "BAR_LEVEL")
        self.assertEqual(source.table, "bars")
        self.assertEqual(source.venue_col, "exchange")

    def test_interval_membership_is_point_in_time(self):
        source = panel.VenueSource("INTERVAL", "membership", "symbol", "exchange", "effective_from", "effective_to")
        intervals = {"ABC": [(date(2018, 1, 1), date(2020, 12, 31), False), (date(2021, 1, 1), None, True)]}
        self.assertFalse(panel._is_hose_at("ABC", date(2020, 6, 1), source, intervals, None))
        self.assertTrue(panel._is_hose_at("ABC", date(2021, 6, 1), source, intervals, None))

    def test_static_exchange_is_identified_as_non_pit(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, asset_type TEXT)")
            db.execute("CREATE TABLE securities(symbol TEXT, exchange TEXT)")
            source = panel.resolve_venue_source(db)
        self.assertEqual(source.mode, "STATIC")

    def test_cross_sectional_rank_is_monotonic(self):
        ranks = panel._pct_rank([1.0, 2.0, 3.0])
        self.assertLess(ranks[0], ranks[1]); self.assertLess(ranks[1], ranks[2])
        lowvol = panel._pct_rank([0.1, 0.2, 0.3], reverse=True)
        self.assertGreater(lowvol[0], lowvol[2])

    def test_task_rows_use_correct_operational_eligibility(self):
        base = {"signal_day": date(2020, 1, 3), "symbol": "AAA", "label_end_20": date(2020, 2, 3), "eligible_long": True, "liquid_universe": True, "target_opportunity_10": 1, "target_damage_10": 0}
        second = dict(base, symbol="BBB", eligible_long=False)
        self.assertEqual(len(ml.task_rows([base, second], "OPPORTUNITY")), 1)
        self.assertEqual(len(ml.task_rows([base, second], "DAMAGE")), 2)

    def test_walkforward_purges_overlapping_labels(self):
        rows = []
        for year in range(2016, 2024):
            day = date(year, 1, 8)
            for week in range(20):
                signal = day + timedelta(days=7 * week)
                for symbol_index in range(12):
                    rows.append({"signal_day": signal, "label_end_20": signal + timedelta(days=28), "symbol": f"S{symbol_index:02d}"})
        folds = ml._folds(rows)
        self.assertTrue(folds)
        for fold in folds:
            test_start = min(row["signal_day"] for row in fold["test"])
            for row in list(fold["train"]) + list(fold["validation"]):
                self.assertLess(row["label_end_20"], test_start)

    def test_feature_contract_is_broad_and_v22_free(self):
        self.assertGreaterEqual(len(panel.FEATURE_FIELDS), 40)
        self.assertIn("relative_120", panel.FEATURE_FIELDS)
        self.assertIn("drawdown_250", panel.FEATURE_FIELDS)
        self.assertIn("volume_ratio_5_20", panel.FEATURE_FIELDS)
        self.assertIn("index_distance_ma250", panel.FEATURE_FIELDS)


if __name__ == "__main__":
    unittest.main()
