from __future__ import annotations

import csv
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import integrated_data_ledger_v36_auto as auto


class IntegratedDataLedgerV36AutoTests(unittest.TestCase):
    def test_derive_vnindex_from_canonical_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            connection = sqlite3.connect(store)
            try:
                connection.execute(
                    """
                    CREATE TABLE bars (
                        day TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL
                    )
                    """
                )
                connection.executemany(
                    "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        ("2024-01-02", "AAA", 10, 11, 9, 10.5, 100),
                        ("2024-01-02", "VNINDEX", 1100, 1110, 1090, 1105, 0),
                        ("2024-02-01", "VNINDEX", 1120, 1130, 1110, 1125, 0),
                    ],
                )
                connection.commit()
            finally:
                connection.close()
            destination = root / "vnindex.csv"
            result = auto.derive_vnindex_from_sqlite(store, destination)
            self.assertEqual(result["row_count"], 2)
            with destination.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(
                [row["day"] for row in rows],
                ["2024-01-02", "2024-02-01"],
            )
            self.assertEqual({row["symbol"] for row in rows}, {"VNINDEX"})

    def test_auto_assurance_only_approves_mechanical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "assurance.json"
            value = auto.build_auto_assurance_candidate(
                existing_path=None,
                destination=destination,
                quarantine={
                    "approved": True,
                    "invalid_row_count": 679,
                    "execution_critical_count": 0,
                    "range_only": True,
                    "reason_counts": {
                        "HIGH_BELOW_OPEN_OR_CLOSE": 563,
                        "LOW_ABOVE_OPEN_OR_CLOSE": 116,
                    },
                    "invalid_ohlcv_export_sha256": "a" * 64,
                    "sqlite_audit": {
                        "first_day": "2015-06-29",
                        "last_day": "2026-07-31",
                        "sha256": "b" * 64,
                    },
                },
                benchmark={
                    "sha256": "c" * 64,
                },
                sector_master=None,
                corporate_actions=None,
            )
            self.assertTrue(value["invalid_ohlcv_quarantine_approved"])
            self.assertTrue(value["vnindex_next_open_complete"])
            self.assertFalse(value["price_basis_confirmed"])
            self.assertFalse(value["point_in_time_sector_master_complete"])
            self.assertFalse(value["corporate_actions_complete"])
            on_disk = json.loads(
                destination.read_text(encoding="utf-8")
            )
            self.assertEqual(
                on_disk["reviewer"],
                "V36_DETERMINISTIC_RULE_ENGINE",
            )

    def test_existing_authoritative_flags_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "existing.json"
            existing.write_text(
                json.dumps(
                    {
                        "price_basis_confirmed": True,
                        "point_in_time_sector_master_complete": True,
                        "corporate_actions_complete": True,
                        "cash_dividend_tax_bps": 5.0,
                    }
                ),
                encoding="utf-8",
            )
            value = auto.build_auto_assurance_candidate(
                existing_path=existing,
                destination=root / "out.json",
                quarantine={
                    "approved": True,
                    "invalid_row_count": 0,
                    "execution_critical_count": 0,
                    "range_only": True,
                    "reason_counts": {},
                    "invalid_ohlcv_export_sha256": "d" * 64,
                    "sqlite_audit": {
                        "first_day": "2015-06-29",
                        "last_day": "2026-07-31",
                        "sha256": "e" * 64,
                    },
                },
                benchmark={"sha256": "f" * 64},
                sector_master=None,
                corporate_actions=None,
            )
            self.assertTrue(value["price_basis_confirmed"])
            self.assertTrue(value["point_in_time_sector_master_complete"])
            self.assertTrue(value["corporate_actions_complete"])
            self.assertEqual(value["cash_dividend_tax_bps"], 5.0)


if __name__ == "__main__":
    unittest.main()
