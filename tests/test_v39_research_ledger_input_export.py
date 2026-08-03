from __future__ import annotations

import csv
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from he_thong_dinh_luong import v39_research_ledger_input_export as exporter


class V39ResearchLedgerInputExportTests(unittest.TestCase):
    def test_export_is_self_contained_and_research_only(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "selected_symbols_v39.txt").write_text("AAA\n", encoding="utf-8")
            with (workspace / "corporate_action_window_evidence_v39.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=("signal_date", "holding_start", "holding_end", "symbol"),
                )
                writer.writeheader()
                writer.writerow({
                    "signal_date": "2024-01-31",
                    "holding_start": "2024-02-01",
                    "holding_end": "2024-03-01",
                    "symbol": "AAA",
                })

            store = root / "market.sqlite3"
            db = sqlite3.connect(store)
            try:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT, source_version TEXT, price_basis TEXT)"
                )
                rows = []
                for index in range(260):
                    day = f"2023-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}"
                    rows.append(("INDEX", "VNINDEX", day, 1000 + index, 1001 + index, 999 + index, 1000 + index, 1, "test", "1", "CHUA_XAC_NHAN"))
                rows.append(("STOCK", "AAA", "2024-02-01", 10, 11, 9, 10.5, 1000, "test", "1", "CHUA_XAC_NHAN"))
                db.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
                db.commit()
            finally:
                db.close()

            output = root / "output"
            report = exporter.export_research_ledger_input(
                workspace_dir=workspace,
                sqlite_store=store,
                output_dir=output,
            )
            self.assertEqual(report["status"], "RESEARCH_INPUT_EXPORTED")
            self.assertTrue(report["research_only"])
            self.assertFalse(report["exact_cash_ledger_approved"])
            self.assertTrue((output / exporter.OHLCV_FILE).is_file())
            self.assertTrue((output / exporter.MANIFEST_FILE).is_file())

    def test_duplicate_selection_is_rejected(self):
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "selected_symbols_v39.txt").write_text("AAA\n", encoding="utf-8")
            with (workspace / "corporate_action_window_evidence_v39.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=("signal_date", "holding_start", "holding_end", "symbol"))
                writer.writeheader()
                row = {"signal_date": "2024-01-31", "holding_start": "2024-02-01", "holding_end": "2024-03-01", "symbol": "AAA"}
                writer.writerow(row)
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "DUPLICATE"):
                exporter._selection_rows(workspace)


if __name__ == "__main__":
    unittest.main()
