from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from he_thong_dinh_luong.cua_du_lieu.hop_dong import LoiHopDong
from he_thong_dinh_luong.cua_du_lieu.kiem_toan_doc_lap import (
    _extract_independent_rows,
    chay_audit_doc_lap,
)


class FakePage:
    def __init__(self, text: str, lines: list[list[str]]) -> None:
        self._text = text
        self._lines = lines

    def extract_text(self, **kwargs):
        return self._text

    def extract_words(self, **kwargs):
        words = []
        for line_index, line in enumerate(self._lines):
            for word_index, token in enumerate(line):
                words.append(
                    {
                        "text": token,
                        "top": float(line_index * 10),
                        "x0": float(word_index * 20),
                    }
                )
        return words


class FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_review_zip(path: Path, candidate: dict) -> str:
    evidence = {
        "batch_summary.json": {
            "batch_status": "READY_FOR_MANUAL_REVIEW",
            "content_reviewed": False,
            "chain_verified": False,
            "canonical_eligible": False,
            "research_eligible": False,
        },
        "document_review_results.json": [],
        "manifest_copy.json": {},
        "page_text_fingerprints.json": [],
        "vn100_membership_candidates.json": [candidate],
    }
    hashes = {}
    blobs = {}
    for name, value in evidence.items():
        blob = (json.dumps(value, sort_keys=True) + "\n").encode()
        blobs[name] = blob
        hashes[name] = sha256(blob).hexdigest()
    blobs["evidence_hashes.json"] = (
        json.dumps(hashes, sort_keys=True) + "\n"
    ).encode()
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, blob in blobs.items():
            archive.writestr(f"evidence/{name}", blob)
    return sha256(path.read_bytes()).hexdigest()


def write_manifest(
    path: Path,
    review_sha: str,
    source_id: str,
    raw_sha: str,
    document_type: str = "PERIODIC_FULL_LIST",
    expected_count: int = 2,
) -> None:
    document = {
        "source_document_id": source_id,
        "document_type": document_type,
        "required": True,
        "expected_sha256": raw_sha,
        "expected_byte_size": 8,
        "expected_page_count": 1,
        "required_marker_groups": [["VN100"]],
    }
    if document_type == "PERIODIC_FULL_LIST":
        document.update(
            {
                "vn100_page_indexes": [0],
                "expected_member_count": expected_count,
            }
        )
    payload = {
        "schema_version": "independent_audit_batch_v1",
        "run_id": "test",
        "expected_review_zip_sha256": review_sha,
        "documents": [document],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestKiemToanDocLap(unittest.TestCase):
    def test_parser_toa_do_ho_tro_ten_xuong_dong(self):
        page = FakePage(
            "VN100",
            [
                ["1", "AAA", "Cong", "ty"],
                ["Co", "phan", "A", "1,000", "45%", "100%"],
                ["2", "BBB", "Cong", "ty", "B", "2.000", "50%", "100%"],
                ["3", "CCC", "Cong", "ty", "C", "3000", "55%", "100%"],
            ],
        )
        rows, errors, diagnostics = _extract_independent_rows([page], [0], 3)
        self.assertEqual([], errors)
        self.assertEqual(3, len(rows))
        self.assertEqual("Cong ty Co phan A", rows[0]["company_name"])
        self.assertEqual(1000, rows[0]["shares_for_index"])
        self.assertEqual(3, diagnostics[0]["parsed_row_count"])

    def test_end_to_end_match_va_zip_khong_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "run-02"
            source_id = "rc-test"
            raw_path = (
                run_root
                / "documents"
                / source_id
                / "raw"
                / source_id
                / "original.bin"
            )
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(b"fake-pdf")
            raw_sha = sha256(b"fake-pdf").hexdigest()
            candidate = {
                "source_document_id": source_id,
                "rows": [
                    {
                        "row_number": 1,
                        "raw_symbol": "AAA",
                        "company_name": "Cong ty A",
                        "shares_for_index": 1000,
                        "free_float_pct": "45",
                        "capitalization_cap_pct": "100",
                        "source_locator": "pdf_page_index=0;page_number=1",
                    },
                    {
                        "row_number": 2,
                        "raw_symbol": "BBB",
                        "company_name": "Cong ty B",
                        "shares_for_index": 2000,
                        "free_float_pct": "50",
                        "capitalization_cap_pct": "100",
                        "source_locator": "pdf_page_index=0;page_number=1",
                    },
                ],
                "observed_member_count": 2,
                "content_reviewed": False,
                "chain_verified": False,
                "canonical_candidate": False,
                "research_eligible": False,
            }
            review_zip = root / "review.zip"
            review_sha = make_review_zip(review_zip, candidate)
            manifest = root / "manifest.json"
            write_manifest(manifest, review_sha, source_id, raw_sha)
            fake_pdf = FakePdf(
                [
                    FakePage(
                        "VN100",
                        [
                            ["1", "AAA", "Cong", "ty", "A", "1,000", "45%", "100%"],
                            ["2", "BBB", "Cong", "ty", "B", "2,000", "50%", "100%"],
                        ],
                    )
                ]
            )
            output = root / "audit"
            result = chay_audit_doc_lap(
                run_root,
                review_zip,
                manifest,
                output,
                pdf_factory=lambda path: fake_pdf,
            )
            self.assertEqual("INDEPENDENT_AUDIT_PASSED", result["batch_status"])
            self.assertEqual(0, result["discrepancy_count"])
            with ZipFile(output / "independent_audit_metadata_evidence.zip") as archive:
                names = archive.namelist()
                self.assertFalse(any("original.bin" in name for name in names))
                self.assertFalse(any(name.endswith(".pdf") for name in names))

    def test_field_mismatch_bi_phat_hien(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "run-02"
            source_id = "rc-test"
            raw_path = (
                run_root
                / "documents"
                / source_id
                / "raw"
                / source_id
                / "original.bin"
            )
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(b"fake-pdf")
            raw_sha = sha256(b"fake-pdf").hexdigest()
            candidate = {
                "source_document_id": source_id,
                "rows": [
                    {
                        "row_number": 1,
                        "raw_symbol": "AAA",
                        "company_name": "Cong ty A",
                        "shares_for_index": 9999,
                        "free_float_pct": "45",
                        "capitalization_cap_pct": "100",
                        "source_locator": "pdf_page_index=0;page_number=1",
                    }
                ],
                "observed_member_count": 1,
                "content_reviewed": False,
                "chain_verified": False,
                "canonical_candidate": False,
                "research_eligible": False,
            }
            review_zip = root / "review.zip"
            review_sha = make_review_zip(review_zip, candidate)
            manifest = root / "manifest.json"
            write_manifest(manifest, review_sha, source_id, raw_sha, expected_count=1)
            fake_pdf = FakePdf(
                [
                    FakePage(
                        "VN100",
                        [["1", "AAA", "Cong", "ty", "A", "1,000", "45%", "100%"]],
                    )
                ]
            )
            result = chay_audit_doc_lap(
                run_root,
                review_zip,
                manifest,
                root / "out",
                pdf_factory=lambda path: fake_pdf,
            )
            self.assertEqual("INDEPENDENT_AUDIT_FAILED", result["batch_status"])
            self.assertEqual(1, result["discrepancy_count"])

    def test_raw_hash_sai_chan_truoc_khi_mo_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "run-02"
            source_id = "rc-test"
            raw_path = (
                run_root
                / "documents"
                / source_id
                / "raw"
                / source_id
                / "original.bin"
            )
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(b"tampered")
            candidate = {
                "source_document_id": source_id,
                "rows": [],
                "observed_member_count": 0,
                "content_reviewed": False,
                "chain_verified": False,
                "canonical_candidate": False,
                "research_eligible": False,
            }
            review_zip = root / "review.zip"
            review_sha = make_review_zip(review_zip, candidate)
            manifest = root / "manifest.json"
            write_manifest(
                manifest,
                review_sha,
                source_id,
                "0" * 64,
                document_type="RULEBOOK",
            )
            calls = []
            result = chay_audit_doc_lap(
                run_root,
                review_zip,
                manifest,
                root / "out",
                pdf_factory=lambda path: calls.append(path),
            )
            self.assertEqual([], calls)
            self.assertEqual("INDEPENDENT_AUDIT_FAILED", result["batch_status"])

    def test_review_zip_hash_sai_bi_chan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = {
                "source_document_id": "x",
                "rows": [],
                "observed_member_count": 0,
                "content_reviewed": False,
                "chain_verified": False,
                "canonical_candidate": False,
                "research_eligible": False,
            }
            review_zip = root / "review.zip"
            make_review_zip(review_zip, candidate)
            manifest = root / "manifest.json"
            write_manifest(
                manifest,
                "0" * 64,
                "x",
                "0" * 64,
                document_type="RULEBOOK",
            )
            with self.assertRaisesRegex(
                LoiHopDong, "REVIEW_EVIDENCE_ZIP_SHA_MISMATCH"
            ):
                chay_audit_doc_lap(root, review_zip, manifest, root / "out")


if __name__ == "__main__":
    unittest.main()
