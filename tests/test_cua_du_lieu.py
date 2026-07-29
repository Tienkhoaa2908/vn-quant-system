from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.cua_du_lieu import (
    CapNguon,
    CoSoGia,
    DauVaoResearchPreflight,
    HanhDongDoanhNghiep,
    KhoangAlias,
    KyReview,
    LoaiHanhDongDoanhNghiep,
    LoiHopDong,
    TaiLieuNguon,
    ThanhEod,
    TrangThaiQuyen,
    TrangThaiThanhVien,
    cong_bo_candidate,
    danh_gia_cua_eod,
    danh_gia_research_preflight,
    doi_chieu_eod,
    kiem_toan_cong_bo_doc_lap,
    kiem_tra_alias,
    tao_chung_nhan_coverage,
    tao_chung_nhan_hanh_dong,
    tao_cong_bo_pit_candidate,
    tao_goi_bang_chung_tu_file,
    truy_van_thanh_vien,
)

UTC = timezone.utc


class TestCuaDuLieu(unittest.TestCase):
    def _fixture_source(self, source_id: str) -> TaiLieuNguon:
        return TaiLieuNguon(
            source_document_id=source_id,
            publisher="fixture",
            source_tier=CapNguon.TIER_1_OFFICIAL,
            document_type="FULL_LIST",
            observed_url="fixture://vn100",
            acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
            rights_status=TrangThaiQuyen.PERMITTED,
            sha256="0" * 64,
            byte_size=10,
            content_reviewed=True,
            chain_verified=True,
            canonical_eligible=False,
            is_fixture=True,
        )

    def _cycles(self) -> tuple[KyReview, KyReview]:
        return (
            KyReview(
                cycle_id="c1",
                index_name="VN100",
                publication_at=datetime(2025, 1, 20, 12, tzinfo=UTC),
                effective_from=date(2025, 2, 3),
                effective_to=date(2025, 8, 4),
                expected_member_count=2,
                members=("i1", "i2"),
                source_document_ids=("s1",),
                rulebook_version="4.0",
                is_fixture=True,
            ),
            KyReview(
                cycle_id="c2",
                index_name="VN100",
                publication_at=datetime(2025, 7, 16, 12, tzinfo=UTC),
                effective_from=date(2025, 8, 4),
                effective_to=date(2026, 2, 2),
                expected_member_count=2,
                members=("i2", "i3"),
                source_document_ids=("s2",),
                rulebook_version="4.0",
                is_fixture=True,
            ),
        )

    def test_fixture_khong_duoc_canonical(self) -> None:
        source = self._fixture_source("s1")
        object.__setattr__(source, "canonical_eligible", True)
        with self.assertRaises(LoiHopDong):
            source.kiem_tra()

    def test_alias_overlap_bi_chan(self) -> None:
        aliases = (
            KhoangAlias(
                "i1",
                "AAA",
                date(2025, 1, 1),
                date(2025, 6, 1),
                ("s",),
            ),
            KhoangAlias(
                "i2",
                "AAA",
                date(2025, 5, 1),
                date(2025, 7, 1),
                ("s",),
            ),
        )
        with self.assertRaisesRegex(LoiHopDong, "IDENTITY_AMBIGUITY"):
            kiem_tra_alias(aliases)

    def test_query_half_open_cutoff_va_ba_trang_thai(self) -> None:
        sources = {
            "s1": self._fixture_source("s1"),
            "s2": self._fixture_source("s2"),
        }
        publication = tao_cong_bo_pit_candidate(self._cycles(), sources)
        cutoff = datetime(2025, 2, 4, tzinfo=UTC)
        self.assertEqual(
            truy_van_thanh_vien(
                publication,
                "i1",
                date(2025, 2, 3),
                cutoff,
                require_canonical=False,
            ),
            TrangThaiThanhVien.MEMBER,
        )
        self.assertEqual(
            truy_van_thanh_vien(
                publication,
                "i9",
                date(2025, 2, 3),
                cutoff,
                require_canonical=False,
            ),
            TrangThaiThanhVien.NOT_MEMBER_PROVEN,
        )
        self.assertEqual(
            truy_van_thanh_vien(
                publication,
                "i1",
                date(2025, 8, 4),
                cutoff,
                require_canonical=False,
            ),
            TrangThaiThanhVien.UNKNOWN,
        )
        self.assertEqual(
            truy_van_thanh_vien(
                publication,
                "i1",
                date(2025, 2, 3),
                datetime(2025, 1, 19, tzinfo=UTC),
                require_canonical=False,
            ),
            TrangThaiThanhVien.UNKNOWN,
        )

    def test_count_mismatch_fail_closed(self) -> None:
        bad = KyReview(
            cycle_id="bad",
            index_name="VN100",
            publication_at=datetime(2025, 1, 1, tzinfo=UTC),
            effective_from=date(2025, 1, 2),
            effective_to=date(2025, 2, 1),
            expected_member_count=2,
            members=("i1",),
            source_document_ids=("s",),
            rulebook_version="4.0",
            is_fixture=True,
        )
        with self.assertRaisesRegex(LoiHopDong, "observed_member_count"):
            bad.kiem_tra()

    def test_fixture_coverage_khong_research(self) -> None:
        sources = {
            "s1": self._fixture_source("s1"),
            "s2": self._fixture_source("s2"),
        }
        publication = tao_cong_bo_pit_candidate(self._cycles(), sources)
        certificate = tao_chung_nhan_coverage(publication)
        self.assertTrue(certificate.complete)
        self.assertFalse(certificate.research_eligible)

    def test_eod_exact_mismatch_va_basis(self) -> None:
        row = ThanhEod(
            "AAA",
            date(2025, 1, 2),
            Decimal("10"),
            Decimal("11"),
            Decimal("100"),
            "s",
            CoSoGia.UNADJUSTED,
            True,
        )
        self.assertEqual(doi_chieu_eod((row,), (row,)), ())
        ref = ThanhEod(
            "AAA",
            date(2025, 1, 2),
            Decimal("10000"),
            Decimal("11000"),
            Decimal("101"),
            "r",
            CoSoGia.UNKNOWN,
            True,
        )
        mismatches = doi_chieu_eod((row,), (ref,))
        self.assertIn("PRICE_SCALE_MISMATCH", {x.code for x in mismatches})
        ready, blockers = danh_gia_cua_eod(
            mismatches,
            candidate_basis=CoSoGia.UNADJUSTED,
            reference_basis=CoSoGia.UNKNOWN,
        )
        self.assertFalse(ready)
        self.assertIn("PRICE_BASIS_UNCONFIRMED", blockers)

    def test_corporate_action_validation_va_fixture_gate(self) -> None:
        action = HanhDongDoanhNghiep(
            action_id="a1",
            instrument_id="i1",
            action_type=LoaiHanhDongDoanhNghiep.CASH_DIVIDEND,
            publication_at=datetime(2025, 1, 1, tzinfo=UTC),
            effective_date=date(2025, 1, 10),
            record_date=date(2025, 1, 10),
            payment_date=date(2025, 1, 20),
            cash_value=Decimal("1000"),
            source_document_id="s",
            is_fixture=True,
        )
        certificate = tao_chung_nhan_hanh_dong(
            (action,),
            range_start=date(2025, 1, 1),
            range_end=date(2025, 2, 1),
            inventory_complete=True,
            price_basis=CoSoGia.UNADJUSTED,
            source_chain_verified=True,
        )
        self.assertFalse(certificate.research_eligible)

    def test_research_preflight_giu_bon_blocker(self) -> None:
        result = danh_gia_research_preflight(
            DauVaoResearchPreflight(
                universe_contract="technical_candidate_union_v1",
                universe_coverage=None,
                eod_crosscheck_ready=False,
                corporate_action_certificate=None,
                price_basis_confirmed=False,
            )
        )
        self.assertFalse(result.passed)
        self.assertIn(
            "VN100_POINT_IN_TIME_HISTORY_INCOMPLETE",
            result.blockers,
        )
        self.assertIn("HOSE_EOD_CROSSCHECK_INCOMPLETE", result.blockers)
        self.assertIn(
            "CORPORATE_ACTION_INVENTORY_INCOMPLETE",
            result.blockers,
        )
        self.assertIn("PRICE_BASIS_UNCONFIRMED", result.blockers)

    def test_acquisition_kit_giu_exact_byte_va_zip_khong_co_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            source.write_bytes(b"exact-source-byte\x00\x01")
            output = root / "run"
            result = tao_goi_bang_chung_tu_file(
                source,
                output,
                source_document_id="doc1",
                publisher="HOSE",
                document_type="RULEBOOK",
                observed_url="https://example.invalid/doc.pdf",
                rights_status=TrangThaiQuyen.RESTRICTED,
                source_tier=CapNguon.TIER_1_OFFICIAL,
                locator="page 1",
                acquisition_time=datetime(2026, 1, 1, tzinfo=UTC),
            )
            self.assertEqual(
                (output / "raw/doc1/original.bin").read_bytes(),
                source.read_bytes(),
            )
            self.assertTrue(result["hash_match"])
            with ZipFile(output / "metadata_evidence.zip") as archive:
                self.assertFalse(
                    any(
                        "original.bin" in name or name.startswith("raw/")
                        for name in archive.namelist()
                    )
                )

    def test_publication_auditor_phat_hien_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            published = cong_bo_candidate(
                root,
                "run1",
                {"coverage.json": {"complete": False}},
                git_commit="a" * 40,
            )
            self.assertTrue(kiem_toan_cong_bo_doc_lap(published).passed)
            (published / "coverage.json").write_text("{}\n", encoding="utf-8")
            audit = kiem_toan_cong_bo_doc_lap(published)
            self.assertFalse(audit.passed)
            self.assertTrue(
                any("HASH_MISMATCH" in error for error in audit.errors)
            )


if __name__ == "__main__":
    unittest.main()
