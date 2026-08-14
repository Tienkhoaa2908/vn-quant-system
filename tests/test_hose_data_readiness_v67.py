from __future__ import annotations

from contextlib import closing
import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import hose_data_readiness_v67 as census


class TestHoseDataReadinessV67(unittest.TestCase):
    def test_classify_requires_symbol_venue_and_effective_time(self) -> None:
        item = census.classify_columns(["symbol", "exchange", "effective_from", "effective_to"])
        self.assertTrue(item["shape_candidate"])
        static = census.classify_columns(["symbol", "exchange"])
        self.assertFalse(static["shape_candidate"])
        listing = census.classify_columns(["symbol", "exchange", "listing_date"])
        self.assertFalse(listing["shape_candidate"])

    def test_store_census_reports_coverage_price_basis_and_redacts_secret(self) -> None:
        # On Windows sqlite3 can retain read-only statement handles until process
        # teardown even after the function has returned.  Cleanup failure is not
        # part of the census contract, so temp cleanup is best-effort here.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = Path(tmp) / "market.sqlite3"
            with closing(sqlite3.connect(store)) as db:
                db.execute("CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER, source TEXT, source_version TEXT, price_basis TEXT)")
                db.executemany(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?)",
                    [
                        ("INDEX", "VNINDEX", "2015-01-05", 1000.0, 1001.0, 0, "dnse", "v1", "raw"),
                        ("STOCK", "AAA", "2015-01-05", 10.0, 10.5, 1000, "dnse", "v1", "raw"),
                        ("STOCK", "AAA", "2026-08-13", 20.0, 20.5, 2000, "dnse", "v2", "raw"),
                    ],
                )
                db.execute("CREATE TABLE metadata(key TEXT, value TEXT)")
                db.executemany("INSERT INTO metadata VALUES(?,?)", [("dataset", "market"), ("api_key", "secret-value")])
                db.commit()
            report = census.inspect_store(store)
            self.assertEqual(report["bars_first_day"], "2015-01-05")
            self.assertEqual(report["bars_last_day"], "2026-08-13")
            self.assertEqual(report["metadata"]["api_key"], "[REDACTED]")
            self.assertEqual(report["bars_price_basis_distribution"][0]["price_basis"], "raw")

    def test_local_scan_finds_candidate_header_without_reading_market_store(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            path = root / "hose_membership_history.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["symbol", "exchange", "effective_from", "effective_to"])
                writer.writeheader()
                writer.writerow({"symbol": "AAA", "exchange": "HOSE", "effective_from": "2020-01-01", "effective_to": ""})
            result = census.discover_local_candidates([root])
            self.assertEqual(result["strict_shape_candidate_count"], 1)
            self.assertTrue(result["strict_shape_candidates"][0]["shape_candidate"])


if __name__ == "__main__":
    unittest.main()
