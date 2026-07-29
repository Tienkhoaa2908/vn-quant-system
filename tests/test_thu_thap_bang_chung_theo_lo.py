from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.cua_du_lieu import (
    LoiHopDong,
    tao_goi_bang_chung_theo_lo,
)

UTC = timezone.utc


class TestThuThapBangChungTheoLo(unittest.TestCase):
    def _row(
        self,
        source_document_id: str,
        filename: str,
        *,
        required: bool = True,
        expected_sha256: str | None = None,
        rights_status: str = "RESTRICTED",
    ) -> dict[str, object]:
        return {
            "source_document_id": source_document_id,
            "filename": filename,
            "publisher": "HOSE",
            "document_type": "FULL_LIST",
            "observed_url": f"https://example.invalid/{filename}",
            "rights_status": rights_status,
            "source_tier": "TIER_2_OFFICIAL_SURROGATE",
            "locator": "page 1",
            "required": required,
            "expected_sha256": expected_sha256,
        }

    def _write_manifest(
        self,
        path: Path,
        documents: list[dict[str, object]],
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "data_evidence_batch_v1",
                    "run_id": "batch-test",
                    "documents": documents,
                }
            ),
            encoding="utf-8",
        )

    def test_batch_complete_khi_chi_thieu_file_tuy_chon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "downloads"
            downloads.mkdir()
            (downloads / "a.pdf").write_bytes(b"alpha")
            (downloads / "b.pdf").write_bytes(b"beta")
            manifest = root / "manifest.json"
            self._write_manifest(
                manifest,
                [
                    self._row("doc-a", "a.pdf"),
                    self._row("doc-b", "b.pdf"),
                    self._row("doc-c", "c.pdf", required=False),
                ],
            )
            output = root / "output"
            result = tao_goi_bang_chung_theo_lo(
                manifest,
                downloads,
                output,
                acquisition_time=datetime(2026, 1, 1, tzinfo=UTC),
            )
            self.assertEqual(result["batch_status"], "COMPLETE")
            self.assertEqual(result["acquired_count"], 2)
            self.assertEqual(result["missing_count"], 1)
            self.assertEqual(
                (output / "documents/doc-a/raw/doc-a/original.bin").read_bytes(),
                b"alpha",
            )
            with ZipFile(output / "batch_metadata_evidence.zip") as archive:
                self.assertFalse(
                    any(
                        "original.bin" in name or "/raw/" in name
                        for name in archive.namelist()
                    )
                )

    def test_batch_partial_khi_thieu_file_bat_buoc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "downloads"
            downloads.mkdir()
            (downloads / "a.pdf").write_bytes(b"alpha")
            manifest = root / "manifest.json"
            self._write_manifest(
                manifest,
                [self._row("doc-a", "a.pdf"), self._row("doc-b", "b.pdf")],
            )
            result = tao_goi_bang_chung_theo_lo(
                manifest,
                downloads,
                root / "output",
                acquisition_time=datetime(2026, 1, 1, tzinfo=UTC),
            )
            self.assertEqual(result["batch_status"], "PARTIAL")
            self.assertEqual(result["required_failure_count"], 1)

    def test_hash_mismatch_khong_copy_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "downloads"
            downloads.mkdir()
            (downloads / "a.pdf").write_bytes(b"alpha")
            manifest = root / "manifest.json"
            self._write_manifest(
                manifest,
                [self._row("doc-a", "a.pdf", expected_sha256="0" * 64)],
            )
            output = root / "output"
            result = tao_goi_bang_chung_theo_lo(
                manifest,
                downloads,
                output,
                acquisition_time=datetime(2026, 1, 1, tzinfo=UTC),
            )
            self.assertEqual(result["batch_status"], "FAILED")
            self.assertFalse((output / "documents/doc-a").exists())
            rows = json.loads(
                (output / "evidence/acquisition_results.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(rows[0]["status"], "HASH_MISMATCH")
            self.assertEqual(rows[0]["observed_sha256"], sha256(b"alpha").hexdigest())

    def test_manifest_chan_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "downloads"
            downloads.mkdir()
            manifest = root / "manifest.json"
            self._write_manifest(manifest, [self._row("doc-a", "../a.pdf")])
            with self.assertRaises(LoiHopDong):
                tao_goi_bang_chung_theo_lo(
                    manifest,
                    downloads,
                    root / "output",
                    acquisition_time=datetime(2026, 1, 1, tzinfo=UTC),
                )


if __name__ == "__main__":
    unittest.main()
