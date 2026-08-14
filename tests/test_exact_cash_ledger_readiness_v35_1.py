from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.he_thong_dinh_luong import exact_cash_ledger_readiness_v35_1 as v351


class ExactCashLedgerReadinessV351Tests(unittest.TestCase):
    def test_missing_assurance_is_blocked(self) -> None:
        result = v351.audit_data_assurance(
            None,
            sqlite_audit={"sha256": "s", "first_day": "2015-01-01", "last_day": "2026-01-01"},
            sector_master={"valid": True, "sha256": "a"},
            corporate_actions={"valid": True, "sha256": "b"},
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["blocker"], "EXACT_LEDGER_DATA_ASSURANCE_REPORT_MISSING")

    def test_assurance_requires_matching_hashes_and_full_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "assurance.json"
            path.write_text(
                json.dumps({
                    "schema_version": v351.ASSURANCE_SCHEMA,
                    "coverage_first_day": "2015-01-01",
                    "coverage_last_day": "2026-12-31",
                    "sqlite_sha256": "sqlite",
                    "sector_master_sha256": "sector",
                    "corporate_actions_sha256": "actions",
                    "price_basis_confirmed": True,
                    "point_in_time_sector_master_complete": True,
                    "corporate_actions_complete": True,
                }),
                encoding="utf-8",
            )
            result = v351.audit_data_assurance(
                path,
                sqlite_audit={"sha256": "sqlite", "first_day": "2015-06-29", "last_day": "2026-07-31"},
                sector_master={"valid": True, "sha256": "sector"},
                corporate_actions={"valid": True, "sha256": "actions"},
            )
            self.assertTrue(result["valid"])
            self.assertTrue(result["coverage_contains_sqlite"])

    def test_assurance_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "assurance.json"
            path.write_text(
                json.dumps({
                    "schema_version": v351.ASSURANCE_SCHEMA,
                    "coverage_first_day": "2015-01-01",
                    "coverage_last_day": "2026-12-31",
                    "sqlite_sha256": "wrong",
                    "sector_master_sha256": "sector",
                    "corporate_actions_sha256": "actions",
                    "price_basis_confirmed": True,
                    "point_in_time_sector_master_complete": True,
                    "corporate_actions_complete": True,
                }),
                encoding="utf-8",
            )
            result = v351.audit_data_assurance(
                path,
                sqlite_audit={"sha256": "sqlite", "first_day": "2015-06-29", "last_day": "2026-07-31"},
                sector_master={"valid": True, "sha256": "sector"},
                corporate_actions={"valid": True, "sha256": "actions"},
            )
            self.assertFalse(result["valid"])
            self.assertFalse(result["sqlite_sha256_match"])


if __name__ == "__main__":
    unittest.main()
