from __future__ import annotations

import csv
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from he_thong_dinh_luong import v39_apply_local_operations_evidence as apply_ops


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    fields = [
        "symbol", "quantity", "market_value_vnd",
    ]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _snapshot(*, trading_token_used: bool = False) -> bytes:
    analysis = _csv_bytes([
        {"symbol": "MBB", "quantity": 3, "market_value_vnd": 68250},
    ])
    summary = json.dumps({
        "status": "PASS_SETTLED_CASH",
        "source": "dnse_openapi_read_only",
        "read_only": True,
        "trading_token_used": trading_token_used,
        "masked_account": "******6280",
        "as_of": "2026-07-31T17:04:59+07:00",
        "position_count": 1,
        "stock_market_value_vnd": 68250,
        "total_cash_vnd": 126582,
        "withdrawable_cash_vnd": 126581,
        "safe_planner_cash_vnd": 126581,
        "net_liquidation_value_vnd": 194832,
        "available_cash_vnd": 195000,
    }, sort_keys=True).encode()
    nested_manifest = json.dumps({
        "status": "SUCCESS",
        "read_only": True,
        "credentials_recorded": False,
        "trading_token_used": trading_token_used,
        "masked_account": "******6280",
        "as_of": "2026-07-31T17:04:59+07:00",
        "files": {
            "portfolio_analysis.csv": {"sha256": _sha(analysis), "size": len(analysis)},
            "portfolio_summary.json": {"sha256": _sha(summary), "size": len(summary)},
        },
    }, sort_keys=True).encode()
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("portfolio_analysis.csv", analysis)
        archive.writestr("portfolio_summary.json", summary)
        archive.writestr("manifest.json", nested_manifest)
    return output.getvalue()


class V39ApplyLocalOperationsEvidenceTests(unittest.TestCase):
    def _fixture(self, root: Path, *, trading_token_used: bool = False) -> tuple[Path, Path]:
        workspace = root / "workspace"
        source = workspace / apply_ops.SOURCE_DIR
        source.mkdir(parents=True)
        (workspace / apply_ops.WORKSTATION_FILE).write_text(json.dumps({
            "account_sync_verified": False,
            "account_sync_evidence_document_id": "",
            "account_sync_evidence_filename": "",
            "account_sync_evidence_sha256": "",
            "position_reconciliation_verified": False,
            "position_reconciliation_evidence_document_id": "",
            "position_reconciliation_evidence_filename": "",
            "position_reconciliation_evidence_sha256": "",
        }), encoding="utf-8")

        collected = root / "collected"
        evidence_path = collected / apply_ops.OPS_RELATIVE_ZIP
        evidence_path.parent.mkdir(parents=True)
        evidence = _snapshot(trading_token_used=trading_token_used)
        evidence_path.write_bytes(evidence)
        (collected / apply_ops.COLLECTION_MANIFEST).write_text(json.dumps({
            "status": "EVIDENCE_COLLECTED",
            "copied_files": [{
                "collected_path": apply_ops.OPS_RELATIVE_ZIP.as_posix(),
                "sha256": _sha(evidence),
                "size_bytes": len(evidence),
            }],
        }), encoding="utf-8")
        return workspace, collected

    def test_valid_read_only_snapshot_applies_account_sync_only(self):
        with TemporaryDirectory() as temporary:
            workspace, collected = self._fixture(Path(temporary))
            report = apply_ops.apply_local_operations_evidence(
                workspace_dir=workspace,
                collected_dir=collected,
            )
            controls = json.loads((workspace / apply_ops.WORKSTATION_FILE).read_text(encoding="utf-8"))
            self.assertTrue(controls["account_sync_verified"])
            self.assertFalse(controls["position_reconciliation_verified"])
            evidence = workspace / apply_ops.SOURCE_DIR / apply_ops.EVIDENCE_FILENAME
            self.assertTrue(evidence.is_file())
            self.assertEqual(controls["account_sync_evidence_sha256"], _sha(evidence.read_bytes()))
            self.assertEqual(report["status"], "ACCOUNT_SYNC_APPLIED")
            self.assertFalse(report["live_capital_approved"])

    def test_trading_token_snapshot_fails_closed_without_mutation(self):
        with TemporaryDirectory() as temporary:
            workspace, collected = self._fixture(Path(temporary), trading_token_used=True)
            before = (workspace / apply_ops.WORKSTATION_FILE).read_bytes()
            with self.assertRaisesRegex(ValueError, "CONTROL_FAILED"):
                apply_ops.apply_local_operations_evidence(
                    workspace_dir=workspace,
                    collected_dir=collected,
                )
            self.assertEqual((workspace / apply_ops.WORKSTATION_FILE).read_bytes(), before)
            self.assertFalse((workspace / apply_ops.SOURCE_DIR / apply_ops.EVIDENCE_FILENAME).exists())

    def test_collection_hash_mismatch_fails_closed(self):
        with TemporaryDirectory() as temporary:
            workspace, collected = self._fixture(Path(temporary))
            manifest_path = collected / apply_ops.COLLECTION_MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["copied_files"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
                apply_ops.apply_local_operations_evidence(
                    workspace_dir=workspace,
                    collected_dir=collected,
                )


if __name__ == "__main__":
    unittest.main()
