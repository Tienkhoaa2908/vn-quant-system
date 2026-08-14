from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from src.he_thong_dinh_luong import exact_cash_ledger_readiness_v35 as v35


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _v34_zip(path: Path) -> str:
    policy = {
        "policy_id": v35.EXPECTED_POLICY_ID,
        "policy": {
            "model": v35.EXPECTED_MODEL,
            "breadth": v35.EXPECTED_BREADTH,
            "fixed_voluntary_replacement_cap": v35.EXPECTED_CAP,
        },
        "permissions": {"live_capital_approved": False},
    }
    policy_payload = _json_bytes(policy)
    report_payload = _json_bytes({"status": "SUCCESS"})
    observation_payload = b"policy_id,signal_timestamp\n"
    files = {
        "frozen_policy_v34.json": policy_payload,
        "future_paper_holdout_freeze_v34.json": report_payload,
        "future_holdout_observations_v34.csv": observation_payload,
    }
    manifest = {
        "status": "SUCCESS",
        "files": [
            {
                "path": name,
                "size_bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
            for name, payload in sorted(files.items())
        ],
    }
    root = "future-paper-holdout-freeze-v34-1-test"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{root}/analysis_bundle_manifest_v34.json", _json_bytes(manifest))
        for name, payload in files.items():
            archive.writestr(f"{root}/{name}", payload)
    return v35._sha256(path)


def _sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE bars(
            day TEXT NOT NULL,
            symbol TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL
        );
        CREATE TABLE conflicts(id INTEGER);
        """
    )
    connection.executemany(
        "INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
        [
            ("2026-01-30", "AAA", 10, 11, 9, 10.5, 1000),
            ("2026-02-27", "AAA", 10.5, 12, 10, 11.5, 1200),
            ("2026-01-30", "BBB", 20, 21, 19, 20.5, 1000),
            ("2026-02-27", "BBB", 20.5, 22, 20, 21.5, 1200),
        ],
    )
    connection.commit()
    connection.close()


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class ExactCashLedgerReadinessV35Tests(unittest.TestCase):
    def test_missing_external_contracts_are_successful_blocked_audit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifact = root / "v34.zip"
            artifact_sha = _v34_zip(artifact)
            store = root / "market.sqlite3"
            _sqlite(store)
            report = v35.run_v35(
                v34_artifact_zip=artifact,
                sqlite_store=store,
                output_dir=root / "out",
                expected_v34_sha256=artifact_sha,
            )
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["audit_outcome"], "BLOCKED")
            self.assertIn("PRICE_BASIS_UNCONFIRMED", report["blockers"])
            self.assertIn("POINT_IN_TIME_SECTOR_MASTER_MISSING", report["blockers"])
            self.assertIn("CORPORATE_ACTION_INVENTORY_MISSING", report["blockers"])
            self.assertFalse(report["exact_cash_ledger_pnl_computed"])
            self.assertFalse(report["live_capital_approved"])

    def test_complete_contracts_can_be_ready_without_computing_pnl(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifact = root / "v34.zip"
            _v34_zip(artifact)
            store = root / "market.sqlite3"
            _sqlite(store)
            sector = root / "sector.csv"
            _write_csv(
                sector,
                ["symbol", "sector", "effective_from", "effective_to"],
                [
                    {"symbol": "AAA", "sector": "BANK", "effective_from": "2020-01-01", "effective_to": ""},
                    {"symbol": "BBB", "sector": "INDUSTRIAL", "effective_from": "2020-01-01", "effective_to": ""},
                ],
            )
            actions = root / "actions.csv"
            _write_csv(
                actions,
                ["symbol", "event_date", "event_type", "adjustment_factor", "cash_amount_vnd"],
                [
                    {"symbol": "AAA", "event_date": "2026-02-01", "event_type": "SPLIT", "adjustment_factor": "1.0", "cash_amount_vnd": ""},
                ],
            )
            report = v35.run_v35(
                v34_artifact_zip=artifact,
                sqlite_store=store,
                output_dir=root / "out",
                sector_master=sector,
                corporate_actions=actions,
                price_basis_confirmed=True,
            )
            self.assertEqual(report["audit_outcome"], "READY")
            self.assertEqual(report["blockers"], [])
            self.assertFalse(report["exact_cash_ledger_pnl_computed"])
            self.assertFalse(report["live_capital_approved"])

    def test_duplicate_day_symbol_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = root / "market.sqlite3"
            _sqlite(store)
            connection = sqlite3.connect(store)
            connection.execute(
                "INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
                ("2026-01-30", "AAA", 10, 11, 9, 10.5, 1000),
            )
            connection.commit()
            connection.close()
            audit = v35.audit_sqlite(store)
            self.assertEqual(audit["duplicate_key_count"], 1)


if __name__ == "__main__":
    unittest.main()
