from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import market_store_basis_audit_v67 as audit


class TestMarketStoreBasisAuditV67(unittest.TestCase):
    def _make_store(self, root: Path) -> Path:
        store = root / "market.sqlite3"
        with closing(sqlite3.connect(store)) as db:
            db.execute(
                "CREATE TABLE bars("
                "asset_type TEXT,symbol TEXT,day TEXT,open REAL,high REAL,low REAL,close REAL,"
                "volume INTEGER,source TEXT,source_version TEXT,price_basis TEXT,"
                "normalized_sha256 TEXT,fetched_at TEXT)"
            )
            days = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
            for day in days:
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("INDEX","VNINDEX",day,1000,1000,1000,1000,0,"dnse","0.5.0","CHUA_XAC_NHAN","idx","A"),
                )
            values = [
                ("2026-01-02",100.0,100.0,"A"),
                ("2026-01-05",101.0,102.0,"A"),
                ("2026-01-06",51.0,52.0,"B"),
                ("2026-01-07",53.0,54.0,"B"),
            ]
            for day, open_price, close_price, fetched_at in values:
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("STOCK","AAA",day,open_price,open_price,open_price,close_price,1000,
                     "dnse","0.5.0","CHUA_XAC_NHAN","aaa",fetched_at),
                )
            db.execute(
                "CREATE TABLE market_source_revisions_v49("
                "id INTEGER,asset_type TEXT,symbol TEXT,day TEXT,old_json TEXT,new_json TEXT,"
                "detected_at TEXT,policy TEXT)"
            )
            db.execute(
                "INSERT INTO market_source_revisions_v49 VALUES(1,'STOCK','AAA','2026-01-06',?,?,?,?)",
                (json.dumps({"open": 102.0}), json.dumps({"open": 51.0}), "2026-02-01T00:00:00", "replace"),
            )
            db.execute(
                "CREATE TABLE conflicts("
                "id INTEGER,asset_type TEXT,symbol TEXT,day TEXT,existing_json TEXT,incoming_json TEXT,detected_at TEXT)"
            )
            db.execute(
                "CREATE TABLE fetched_ranges("
                "id INTEGER,asset_type TEXT,symbol TEXT,start_day TEXT,end_day TEXT,fetched_at TEXT,"
                "returned_rows INTEGER,source TEXT,source_version TEXT)"
            )
            db.execute(
                "INSERT INTO fetched_ranges VALUES(1,'STOCK','AAA','2026-01-06','2026-01-07','B',2,'dnse','0.5.0')"
            )
            db.execute(
                "CREATE TABLE market_sync_runs_v49("
                "run_id TEXT,started_at TEXT,requested_start TEXT,requested_end TEXT,"
                "expected_final_session TEXT,latest_index_day TEXT,latest_stock_day TEXT,"
                "source_freshness TEXT,details_json TEXT)"
            )
            db.execute(
                "INSERT INTO market_sync_runs_v49 VALUES("
                "'r1','B','2026-01-06','2026-01-07','2026-01-07','2026-01-07','2026-01-07','fresh','{}')"
            )
            db.commit()
        return store

    def test_detects_fetch_boundary_revision_overlap_and_large_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = audit.build_report(self._make_store(Path(tmp)))
            self.assertEqual(report["gap_event_count_by_threshold"]["0.40"], 1)
            self.assertEqual(report["different_fetch_timestamp_gap_count"], 1)
            self.assertEqual(report["revision_overlap_gap_count"], 1)
            self.assertEqual(report["mixed_basis_seam_candidate_count"], 1)
            event = report["gap_events"][0]
            self.assertEqual(event["symbol"], "AAA")
            self.assertEqual(event["day"], "2026-01-06")
            self.assertTrue(event["mixed_basis_seam_candidate"])

    def test_audit_is_read_only_and_never_authorizes_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(Path(tmp))
            with closing(sqlite3.connect(store)) as db:
                before = db.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
            report = audit.build_report(store)
            with closing(sqlite3.connect(store)) as db:
                after = db.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
            self.assertEqual(before, after)
            self.assertFalse(report["store_mutated"])
            self.assertFalse(report["model_training_run"])
            self.assertFalse(report["research_gate"]["c3_training_authorized"])

    def test_context_contains_rows_on_both_sides_of_seam(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = audit.build_report(self._make_store(Path(tmp)))
            rows = [r for r in report["gap_context_rows"] if r["symbol"] == "AAA"]
            self.assertTrue(any(int(r["relative_row"]) < 0 for r in rows))
            self.assertTrue(any(int(r["relative_row"]) == 0 for r in rows))
            self.assertTrue(any(int(r["relative_row"]) > 0 for r in rows))


if __name__ == "__main__":
    unittest.main()
