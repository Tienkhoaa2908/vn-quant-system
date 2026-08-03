from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from he_thong_dinh_luong import trade_reference_pack_v39 as v39


class TradeReferencePackV39Tests(unittest.TestCase):
    def _source(self, workspace: Path, name: str, payload: bytes = b"official") -> str:
        source_dir = workspace / v39.SOURCE_DIR
        source_dir.mkdir(parents=True, exist_ok=True)
        path = source_dir / name
        path.write_bytes(payload)
        return v39.sha256_file(path)

    def _required(self):
        sector = [{"signal_date": "2024-01-31", "execution_day": "2024-02-01", "symbol": "AAA"}]
        windows = [{"signal_date": "2024-01-31", "holding_start": "2024-02-01", "holding_end": "2024-03-01", "symbol": "AAA"}]
        prices = [{"execution_day": "2024-02-01"}]
        ops = {"checklist": {key: key not in {"account_sync_verified", "position_reconciliation_verified"} for key in v39.OPS_KEYS}}
        return sector, windows, prices, ops

    def test_first_run_seeds_persistent_workspace(self):
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            sector, windows, prices, ops = self._required()
            created = v39._seed_workspace(workspace, sector, windows, prices, ops)
            self.assertEqual(len(created), 6)
            self.assertTrue((workspace / v39.SECTOR_WORK_FILE).is_file())
            self.assertTrue((workspace / v39.SOURCE_DIR).is_dir())
            with (workspace / v39.SECTOR_WORK_FILE).open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["symbol"], "AAA")
            self.assertEqual(v39._seed_workspace(workspace, sector, windows, prices, ops), [])

    def test_unverified_workspace_is_blocked(self):
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            sector, windows, prices, ops = self._required()
            v39._seed_workspace(workspace, sector, windows, prices, ops)
            result = v39._validate_workspace(workspace, sector, windows, prices)
            self.assertFalse(result["ready"])
            self.assertGreater(len(result["gaps"]), 0)

    def test_complete_workspace_compiles_exact_inputs(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            output = root / "output"
            output.mkdir()
            sector, windows, prices, ops_candidate = self._required()
            v39._seed_workspace(workspace, sector, windows, prices, ops_candidate)
            source_sha = self._source(workspace, "official.html")
            evidence = {
                "source_document_id": "official-doc",
                "source_filename": "official.html",
                "source_url": "https://official.example/doc",
                "source_sha256": source_sha,
            }
            v39.write_csv(
                workspace / v39.SECTOR_WORK_FILE,
                [{
                    **sector[0], "sector": "Industrials",
                    "effective_from": "2020-01-01", "effective_to": "2030-01-01",
                    **evidence, "verified": True,
                }],
                (
                    "signal_date", "execution_day", "symbol", "sector",
                    "effective_from", "effective_to", "source_document_id",
                    "source_filename", "source_url", "source_sha256", "verified",
                ),
            )
            v39.write_csv(
                workspace / v39.WINDOW_WORK_FILE,
                [{**windows[0], "event_count": 0, **evidence, "source_checked": True, "verified_complete": True}],
                (
                    "signal_date", "holding_start", "holding_end", "symbol",
                    "event_count", "source_document_id", "source_filename",
                    "source_url", "source_sha256", "source_checked", "verified_complete",
                ),
            )
            v39.write_csv(
                workspace / v39.EVENT_WORK_FILE,
                [],
                (
                    "source_event_id", "symbol", "event_date", "event_type",
                    "adjustment_factor", "cash_amount_vnd", "source_document_id",
                    "source_filename", "source_url", "source_sha256", "verified",
                ),
            )
            v39.write_csv(
                workspace / v39.PRICE_WORK_FILE,
                [{**prices[0], "crosscheck_symbol_count": 1, **evidence, "official_source_url": evidence["source_url"], "verified": True}],
                (
                    "execution_day", "crosscheck_symbol_count", "source_document_id",
                    "source_filename", "official_source_url", "source_sha256", "verified",
                ),
            )
            v39.write_json(
                workspace / v39.CONTRACT_WORK_FILE,
                {
                    "schema_version": "execution_contract_evidence_v39",
                    "price_basis_mode": v39.PRICE_BASIS_MODE,
                    "price_unit_vnd_multiplier": 1000,
                    "cash_dividend_tax_bps": 0,
                    **evidence,
                    "reviewer": "tester",
                    "reviewed_at": "2026-08-03T12:00:00+07:00",
                    "verified": True,
                },
            )
            ops = {key: True for key in v39.OPS_KEYS}
            ops.update({
                "account_sync_evidence_document_id": "official-doc",
                "account_sync_evidence_filename": "official.html",
                "account_sync_evidence_sha256": source_sha,
                "position_reconciliation_evidence_document_id": "official-doc",
                "position_reconciliation_evidence_filename": "official.html",
                "position_reconciliation_evidence_sha256": source_sha,
            })
            v39.write_json(workspace / v39.OPS_WORK_FILE, ops)
            validation = v39._validate_workspace(workspace, sector, windows, prices)
            self.assertTrue(validation["ready"], validation["gaps"])
            compiled = v39._compile(
                output,
                validation,
                {"sha256": "a" * 64, "report": {"source": {"sqlite_sha256": "b" * 64}, "data_integrity": {"invalid_ohlcv_export_sha256": "c" * 64}}},
                {"sha256": "d" * 64},
            )
            self.assertTrue(Path(compiled["sector_path"]).is_file())
            self.assertTrue(Path(compiled["actions_path"]).is_file())
            assurance = json.loads(Path(compiled["assurance_path"]).read_text(encoding="utf-8"))
            self.assertEqual(assurance["schema_version"], v39.ASSURANCE_SCHEMA)
            self.assertEqual(assurance["decision_surface"]["corporate_action_event_count"], 0)

    def test_event_count_mismatch_fails_closed(self):
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            sector, windows, prices, ops = self._required()
            v39._seed_workspace(workspace, sector, windows, prices, ops)
            source_sha = self._source(workspace, "official.html")
            rows = list(csv.DictReader((workspace / v39.WINDOW_WORK_FILE).open("r", encoding="utf-8-sig", newline="")))
            rows[0].update({
                "event_count": "1", "source_document_id": "doc",
                "source_filename": "official.html", "source_url": "https://official.example",
                "source_sha256": source_sha, "source_checked": "true", "verified_complete": "true",
            })
            v39.write_csv(
                workspace / v39.WINDOW_WORK_FILE, rows,
                (
                    "signal_date", "holding_start", "holding_end", "symbol",
                    "event_count", "source_document_id", "source_filename", "source_url",
                    "source_sha256", "source_checked", "verified_complete",
                ),
            )
            result = v39._validate_workspace(workspace, sector, windows, prices)
            self.assertTrue(any("EVENT_COUNT_MISMATCH" in row["reason"] for row in result["gaps"]))


if __name__ == "__main__":
    unittest.main()
