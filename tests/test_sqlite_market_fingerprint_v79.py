from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong.sqlite_market_fingerprint_v79 import fingerprint_bars


class TestSqliteMarketFingerprintV79(unittest.TestCase):
    def test_wal_checkpoint_can_change_physical_file_without_logical_bars_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = Path(temp_dir) / "market.sqlite3"
            writer = sqlite3.connect(store)
            try:
                mode = writer.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                self.assertEqual(str(mode).lower(), "wal")
                writer.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER)"
                )
                writer.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?)",
                    ("INDEX", "VNINDEX", "2026-08-13", 1.0, 1.0, 0),
                )
                writer.commit()
                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                writer.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?)",
                    ("INDEX", "VNINDEX", "2026-08-14", 2.0, 2.0, 0),
                )
                writer.commit()

                physical_before = hashlib.sha256(store.read_bytes()).hexdigest()
                logical_before = fingerprint_bars(store)
                self.assertEqual(logical_before["bars_row_count"], 2)
                self.assertEqual(logical_before["bars_last_day"], "2026-08-14")

                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                physical_after = hashlib.sha256(store.read_bytes()).hexdigest()
                logical_after = fingerprint_bars(store)

                self.assertNotEqual(physical_before, physical_after)
                self.assertEqual(logical_before, logical_after)
            finally:
                writer.close()

    def test_actual_bar_mutation_changes_logical_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = Path(temp_dir) / "market.sqlite3"
            with closing(sqlite3.connect(store)) as db:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, volume INTEGER)"
                )
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?)",
                    ("STOCK", "AAA", "2026-08-13", 10.0, 11.0, 1000),
                )
                db.commit()
            before = fingerprint_bars(store)
            with closing(sqlite3.connect(store)) as db:
                db.execute("UPDATE bars SET close=12.0 WHERE symbol='AAA'")
                db.commit()
            after = fingerprint_bars(store)
            self.assertNotEqual(before["bars_sha256"], after["bars_sha256"])


if __name__ == "__main__":
    unittest.main()
