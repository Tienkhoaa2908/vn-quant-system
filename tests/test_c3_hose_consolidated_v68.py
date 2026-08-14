from __future__ import annotations

from datetime import date, timedelta
import hashlib
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68


def weekdays(start: date, count: int) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestC3HoseConsolidatedV68(unittest.TestCase):
    def test_variant_contract_keeps_broad_and_excludes_gap_symbols(self) -> None:
        variants = v68._variant_contract(
            all_symbols=["AAA", "BBB", "CCC"],
            basis={
                "gap_events": [{"symbol": "AAA"}],
                "mixed_basis_seam_candidates": [{"symbol": "BBB"}],
            },
            lineage={"symbol_lineage_rows": []},
        )
        by_id = {str(row["variant_id"]): row for row in variants}
        self.assertEqual(by_id["BROAD_PROVISIONAL"]["symbols"], ["AAA", "BBB", "CCC"])
        self.assertEqual(by_id["SEAM_CLEAN"]["symbols"], ["AAA", "CCC"])
        self.assertEqual(by_id["GAP18_CLEAN"]["symbols"], ["BBB", "CCC"])
        self.assertFalse(by_id["BROAD_PROVISIONAL"]["promotion_eligible"])

    def test_consolidated_run_executes_c3_without_authorizing_promotion(self) -> None:
        days = weekdays(date(2018, 1, 2), 900)
        symbols = [f"S{i:02d}" for i in range(16)]
        gap_symbol = symbols[0]
        # On Windows this test also proves every SQLite handle in the consolidated
        # call graph is closed: TemporaryDirectory cleanup fails immediately if a
        # source or diagnostic variant DB remains open.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            output = root / "out"
            db = sqlite3.connect(store)
            try:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, "
                    "volume INTEGER, source TEXT, source_version TEXT, price_basis TEXT, fetched_at TEXT)"
                )
                for i, day in enumerate(days):
                    idx_close = 900.0 + 0.18 * i + 2.0 * math.sin(i / 21.0)
                    db.execute(
                        "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                        ("INDEX", "VNINDEX", day.isoformat(), idx_close * 0.999, idx_close, 0, "synthetic", "1", "CHUA_XAC_NHAN", "batch-a"),
                    )
                    for j, symbol in enumerate(symbols):
                        base = 30.0 + j * 2.5 + (0.02 + j * 0.0008) * i + 0.8 * math.sin(i / (10.0 + j * 0.2))
                        open_price = base * 0.999
                        close_price = base
                        fetched_at = "batch-a"
                        if symbol == gap_symbol and i == 600:
                            open_price = base * 0.50
                            close_price = base * 0.51
                            fetched_at = "batch-b"
                        db.execute(
                            "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("STOCK", symbol, day.isoformat(), open_price, close_price, 400_000 + j * 10_000, "synthetic", "1", "CHUA_XAC_NHAN", fetched_at),
                        )
                db.commit()
            finally:
                db.close()

            before = sha256(store)
            report = v68.run_consolidated(
                store=store,
                output_dir=output,
                search_roots=[],
                allow_network=False,
                bootstrap_samples=100,
            )
            after = sha256(store)

            self.assertEqual(before, after)
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["champion_model"], "C3_STABLE_3_PAST_IC_SHRUNK")
            self.assertFalse(report["champion_replaced"])
            self.assertFalse(report["challenger_ml_run"])
            self.assertTrue(report["data_gates"]["diagnostic_c3_allowed"])
            self.assertFalse(report["data_gates"]["promotion_authorized"])
            self.assertFalse(report["data_gates"]["canonical_research_claim_authorized"])
            summaries = {str(row["variant_id"]): row for row in report["variant_summaries"]}
            self.assertEqual(summaries["BROAD_PROVISIONAL"]["status"], "SUCCESS")
            self.assertLess(int(summaries["GAP18_CLEAN"]["symbol_count"]), int(summaries["BROAD_PROVISIONAL"]["symbol_count"]))
            self.assertTrue((output / "v68_consolidated_report.json").is_file())
            self.assertTrue((output / "v68_cohort_robustness.csv").is_file())
            self.assertTrue((output / "variants" / "BROAD_PROVISIONAL" / "v67_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
