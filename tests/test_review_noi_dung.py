from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.cua_du_lieu.review_noi_dung import (
    _canonical_text,
    _extract_vn100_rows,
    tai_manifest_review,
    thuc_hien_review_noi_dung_theo_lo,
)


class FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class FakeReader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [FakePage(text) for text in pages]
        self.is_encrypted = False


def row_text(start: int, end: int) -> str:
    return "\n".join(
        f"{index} X{index:03d} Cong ty {index} {1000000 + index:,} 50% 100%"
        for index in range(start, end + 1)
    )


class TestReviewNoiDung(unittest.TestCase):
    def test_canonical_text_bo_dau_va_d_chu(self) -> None:
        self.assertEqual(
            _canonical_text("CÔNG BỐ Định kỳ VN100"),
            "CONG BO DINH KY VN100",
        )

    def test_extract_rows_day_du_100(self) -> None:
        pages = ["", row_text(1, 50), row_text(51, 100)]
        rows, errors = _extract_vn100_rows(pages, [1, 2], 100)
        self.assertEqual(len(rows), 100)
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["row_number"], 1)
        self.assertEqual(rows[-1]["row_number"], 100)

    def test_manifest_chan_page_indexes_khong_on_dinh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps({
                "schema_version": "content_review_batch_v1",
                "run_id": "x",
                "documents": [{
                    "source_document_id": "d",
                    "document_type": "PERIODIC_FULL_LIST",
                    "expected_sha256": "0" * 64,
                    "expected_byte_size": 1,
                    "required_marker_groups": [["VN100"]],
                    "vn100_page_indexes": [2, 1],
                    "expected_member_count": 100,
                }],
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                tai_manifest_review(path)

    def test_batch_ready_va_zip_khong_co_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "run"
            evidence = run_root / "evidence"
            evidence.mkdir(parents=True)
            output = root / "review"
            source_id = "periodic"
            raw_dir = run_root / "documents" / source_id / "raw" / source_id
            raw_dir.mkdir(parents=True)
            raw = raw_dir / "original.bin"
            raw.write_bytes(b"%PDF-fake")
            raw_hash = sha256(raw.read_bytes()).hexdigest()
            registry = [{
                "source_document_id": source_id,
                "sha256": raw_hash,
                "byte_size": raw.stat().st_size,
                "content_reviewed": False,
                "canonical_eligible": False,
            }]
            (evidence / "source_document_registry_candidate.json").write_text(
                json.dumps(registry), encoding="utf-8"
            )
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "content_review_batch_v1",
                "run_id": "review-1",
                "documents": [{
                    "source_document_id": source_id,
                    "document_type": "PERIODIC_FULL_LIST",
                    "expected_sha256": raw_hash,
                    "expected_byte_size": raw.stat().st_size,
                    "expected_page_count": 3,
                    "required": True,
                    "required_marker_groups": [["VN100"], ["KY 1 2026"]],
                    "vn100_page_indexes": [1, 2],
                    "expected_member_count": 100,
                    "period_label": "KY_1_2026",
                }],
            }), encoding="utf-8")

            pages = [
                "CONG BO DANH MUC VN100 KY 1/2026",
                row_text(1, 50),
                row_text(51, 100),
            ]
            result = thuc_hien_review_noi_dung_theo_lo(
                run_root,
                manifest,
                output,
                reader_factory=lambda _: FakeReader(pages),
                review_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            self.assertEqual(result["batch_status"], "READY_FOR_MANUAL_REVIEW")
            summary = json.loads(
                (output / "evidence/batch_summary.json").read_text(encoding="utf-8")
            )
            self.assertFalse(summary["content_reviewed"])
            candidates = json.loads(
                (output / "evidence/vn100_membership_candidates.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(candidates[0]["observed_member_count"], 100)
            with ZipFile(output / "content_review_metadata_evidence.zip") as archive:
                names = archive.namelist()
                self.assertFalse(
                    any("original.bin" in name or "/raw/" in name for name in names)
                )

    def test_hash_mismatch_khong_mo_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "run"
            evidence = run_root / "evidence"
            evidence.mkdir(parents=True)
            source_id = "d"
            raw_dir = run_root / "documents" / source_id / "raw" / source_id
            raw_dir.mkdir(parents=True)
            raw = raw_dir / "original.bin"
            raw.write_bytes(b"x")
            registry = [{
                "source_document_id": source_id,
                "sha256": "0" * 64,
                "byte_size": 1,
                "content_reviewed": False,
                "canonical_eligible": False,
            }]
            (evidence / "source_document_registry_candidate.json").write_text(
                json.dumps(registry), encoding="utf-8"
            )
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "content_review_batch_v1",
                "run_id": "x",
                "documents": [{
                    "source_document_id": source_id,
                    "document_type": "RULEBOOK",
                    "expected_sha256": "0" * 64,
                    "expected_byte_size": 1,
                    "required": True,
                    "required_marker_groups": [["RULEBOOK"]],
                }],
            }), encoding="utf-8")
            called = False

            def reader_factory(_: Path) -> FakeReader:
                nonlocal called
                called = True
                return FakeReader(["RULEBOOK"])

            result = thuc_hien_review_noi_dung_theo_lo(
                run_root,
                manifest,
                root / "out",
                reader_factory=reader_factory,
            )
            self.assertFalse(called)
            self.assertEqual(result["batch_status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
