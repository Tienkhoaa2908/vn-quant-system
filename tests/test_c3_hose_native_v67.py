from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import c3_hose_native_driver_v67 as v67


def _weekdays(start: date, count: int) -> list[date]:
    result: list[date] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


class TestC3HoseNativeV67(unittest.TestCase):
    def test_champion_is_frozen_c3(self) -> None:
        self.assertEqual(v67.CHAMPION_MODEL, "C3_STABLE_3_PAST_IC_SHRUNK")

    def test_static_exchange_metadata_is_rejected(self) -> None:
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, asset_type TEXT)")
            db.execute("CREATE TABLE symbols(symbol TEXT, exchange TEXT)")
            with self.assertRaisesRegex(ValueError, "V67_STATIC_EXCHANGE_METADATA_NOT_ACCEPTED"):
                v67.resolve_venue_source(db)

    def test_interval_exchange_metadata_is_accepted(self) -> None:
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, asset_type TEXT)")
            db.execute("CREATE TABLE membership(symbol TEXT, exchange TEXT, effective_from TEXT, effective_to TEXT)")
            source = v67.resolve_venue_source(db)
            self.assertEqual(source.mode, "INTERVAL")
            self.assertEqual(source.table, "membership")

    def test_start_only_listing_date_current_exchange_is_rejected(self) -> None:
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, asset_type TEXT)")
            db.execute("CREATE TABLE membership(symbol TEXT, exchange TEXT, listing_date TEXT)")
            db.executemany("INSERT INTO membership VALUES(?,?,?)", [("AAA", "HOSE", "2020-01-01"), ("BBB", "HOSE", "2021-01-01")])
            source = v67.resolve_venue_source(db)
            with self.assertRaisesRegex(ValueError, "V67_START_ONLY_STATIC_LIKE_EXCHANGE_METADATA_NOT_ACCEPTED"):
                v67._strict_membership_intervals(db, source)

    def test_repeated_point_in_time_start_only_history_is_accepted(self) -> None:
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, asset_type TEXT)")
            db.execute("CREATE TABLE venue_history(symbol TEXT, exchange TEXT, day TEXT)")
            db.executemany("INSERT INTO venue_history VALUES(?,?,?)", [("AAA", "HOSE", "2026-01-02"), ("AAA", "HOSE", "2026-01-05")])
            source = v67.resolve_venue_source(db)
            result = v67._strict_membership_intervals(db, source)
            self.assertEqual(len(result["AAA"]), 2)

    def test_partial_analysis_month_is_not_a_canonical_snapshot(self) -> None:
        calendar = [date(2026, 6, 30), date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 3), date(2026, 8, 13)]
        self.assertEqual(v67._monthly_days(calendar, date(2026, 8, 13)), [date(2026, 6, 30), date(2026, 7, 31)])

    def test_canonical_for_august_uses_july_snapshot(self) -> None:
        snapshots = [
            v67.C3Snapshot(date(2026, 6, 30), ("AAA",), {"AAA": 1.0}, {"low_volatility": 1 / 3, "relative_strength_120": 1 / 3, "high_52_week": 1 / 3}, True, 1, 12),
            v67.C3Snapshot(date(2026, 7, 31), ("BBB",), {"BBB": 1.0}, {"low_volatility": 1 / 3, "relative_strength_120": 1 / 3, "high_52_week": 1 / 3}, True, 1, 13),
        ]
        result = v67._canonical_snapshot(snapshots, [item.day for item in snapshots], date(2026, 8, 7))
        self.assertIsNotNone(result)
        self.assertEqual(result.day, date(2026, 7, 31))

    def test_scoring_uses_only_c3_three_components(self) -> None:
        common = dict(
            evaluation_day=date(2026, 7, 31), eligible=True, distance_ma20=0.0, distance_ma50=0.0,
            return_5=0.0, return_10=0.0, return_20=0.0, relative_5=0.0, relative_10=0.0,
            relative_20=0.0, drawdown_20=0.0, drawdown_60=0.0, volume_ratio_5_20=1.0,
            realized_vol_ratio_20_60=1.0, breakout_20_gap=0.0, breakdown_20_low_gap=0.1,
            adv20_vnd=10_000_000_000.0, zero_volume_60=0,
        )
        states = [
            v67.FeatureState(symbol="AAA", low_volatility=3.0, relative_strength_120=3.0, high_52_week=3.0, **common),
            v67.FeatureState(symbol="BBB", low_volatility=2.0, relative_strength_120=2.0, high_52_week=2.0, **common),
            v67.FeatureState(symbol="CCC", low_volatility=1.0, relative_strength_120=1.0, high_52_week=1.0, **common),
        ]
        ranking, _ = v67.score_states(states, {"low_volatility": 1 / 3, "relative_strength_120": 1 / 3, "high_52_week": 1 / 3})
        self.assertEqual(ranking, ("AAA", "BBB", "CCC"))

    def test_c3_training_label_is_close_to_close_t_plus_h(self) -> None:
        days = tuple(date(2026, 1, 1) + timedelta(days=i) for i in range(5))
        stock_open = {("AAA", day): value for day, value in zip(days, [10.0, 50.0, 60.0, 70.0, 80.0])}
        stock_close = {("AAA", day): value for day, value in zip(days, [100.0, 110.0, 121.0, 133.1, 146.41])}
        stock_volume = {("AAA", day): 1000 for day in days}
        index_open = {day: value for day, value in zip(days, [1000.0, 2000.0, 2100.0, 2200.0, 2300.0])}
        index_close = {day: value for day, value in zip(days, [1000.0, 1000.0, 1000.0, 1000.0, 1000.0])}
        source = v67.VenueSource("BAR_LEVEL", "bars", "symbol", "exchange")
        market = v67.Market(days, index_open, index_close, stock_open, stock_close, stock_volume, ("AAA",), source)
        label = v67._c3_training_label(market=market, symbol="AAA", signal_day=days[0], calendar_index={day: i for i, day in enumerate(days)}, horizon=2)
        self.assertIsNotNone(label)
        self.assertAlmostEqual(float(label["relative_return"]), 0.21, places=12)
        self.assertEqual(label["label_end"], days[2])

    def test_forward_outcome_enters_next_session_open(self) -> None:
        days = tuple(date(2026, 1, 1) + timedelta(days=i) for i in range(8))
        stock_open = {("AAA", day): 100.0 + i for i, day in enumerate(days)}
        stock_close = {("AAA", day): 100.0 + i for i, day in enumerate(days)}
        stock_volume = {("AAA", day): 1000 for day in days}
        index_open = {day: 1000.0 + i for i, day in enumerate(days)}
        index_close = dict(index_open)
        source = v67.VenueSource("BAR_LEVEL", "bars", "symbol", "exchange")
        market = v67.Market(days, index_open, index_close, stock_open, stock_close, stock_volume, ("AAA",), source)
        outcome = v67._forward_outcome(market=market, symbol="AAA", signal_day=days[1], calendar_index={day: i for i, day in enumerate(days)}, horizon=2)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["entry_day"], days[2].isoformat())
        self.assertEqual(outcome["exit_day"], days[4].isoformat())

    def test_synthetic_end_to_end_rebuilds_c3_and_excludes_hnx(self) -> None:
        days = _weekdays(date(2017, 1, 2), 760)
        hose_symbols = [f"S{i:02d}" for i in range(12)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            output = root / "out"
            with sqlite3.connect(store) as db:
                db.execute("CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, asset_type TEXT, exchange TEXT)")
                rows: list[tuple[object, ...]] = []
                for i, day in enumerate(days):
                    idx_close = 1000.0 + 0.25 * i + 3.0 * math.sin(i / 19.0)
                    rows.append(("VNINDEX", day.isoformat(), idx_close * 0.999, idx_close, 0, "INDEX", ""))
                    for j, symbol in enumerate(hose_symbols):
                        close = 55.0 + 4.0 * j + (0.035 + 0.002 * j) * i + 1.8 * math.sin(i / (9.0 + j * 0.15) + j * 0.4)
                        rows.append((symbol, day.isoformat(), close * (0.998 + 0.0002 * (j % 3)), close, 220_000 + j * 5_000, "STOCK", "HOSE"))
                    hnx_close = 70.0 + 0.05 * i + 1.0 * math.sin(i / 12.0)
                    rows.append(("HNX1", day.isoformat(), hnx_close * 0.999, hnx_close, 300_000, "STOCK", "HNX"))
                db.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", rows)
                db.commit()
            report = v67.run_study(store=store, output_dir=output, historical_end=days[-80], analysis_end=days[-1], price_multiplier=1000.0)
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["champion_model"], "C3_STABLE_3_PAST_IC_SHRUNK")
            self.assertFalse(report["challenger_models_run"])
            self.assertEqual(report["hose_symbol_count_seen"], len(hose_symbols))
            self.assertGreater(report["monthly_snapshot_count"], 0)
            self.assertGreater(report["c3_training_row_count"], 0)
            self.assertTrue((output / "v67_c3_training_rows.csv.gz").is_file())
            self.assertTrue((output / "v67_c3_weight_history.csv").is_file())
            self.assertTrue((output / "v67_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
