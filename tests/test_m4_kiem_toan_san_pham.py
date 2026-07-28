from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.kiem_toan_san_pham import kiem_toan_san_pham
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from ho_tro_m4_reduced import tao_dau_vao_runner


class TestKiemToanSanPhamM4(unittest.TestCase):
    def test_hai_lan_audit_cung_byte_va_phat_hien_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = tao_dau_vao_runner(root)
            product = chay_nghien_cuu_moc_4(
                duong_dan_cau_hinh=paths["cau_hinh"],
                thu_muc_publication_gia_rut_gon=paths["publication"],
                duong_dan_benchmark=paths["benchmark"],
                duong_dan_lich_benchmark=paths["lich_benchmark"],
                duong_dan_corporate_actions=paths["corporate_actions"],
                thu_muc_dau_ra=root / "out",
                ma_lan_chay="fixture_audit",
                git_commit="b" * 40,
                thoi_diem_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
            ).thu_muc_san_pham
            with (product / "so_cai.csv").open(encoding="utf-8", newline="") as handle:
                ledger_rows = list(csv.DictReader(handle))
            bad_ledger = [
                {
                    "chien_luoc": row["chien_luoc"], "ngay": row["ngay"],
                    "cash": row["tien_mat_cuoi_ngay"], "diff": row["chenh_lech_doi_soat"],
                }
                for row in ledger_rows
                if Decimal(row["tien_mat_cuoi_ngay"]) < 0 or Decimal(row["chenh_lech_doi_soat"]) != 0
            ]
            self.assertFalse(bad_ledger, bad_ledger[:5])
            ok1, audit1 = kiem_toan_san_pham(
                thu_muc_san_pham=product, thu_muc_bao_cao=root / "audit1", ma_kiem_toan="audit_fixture",
            )
            ok2, audit2 = kiem_toan_san_pham(
                thu_muc_san_pham=product, thu_muc_bao_cao=root / "audit2", ma_kiem_toan="audit_fixture",
            )
            report1 = json.loads((audit1 / "bao_cao_kiem_toan_doc_lap.json").read_text())
            report2 = json.loads((audit2 / "bao_cao_kiem_toan_doc_lap.json").read_text())
            self.assertTrue(ok1, report1["loi"])
            self.assertTrue(ok2, report2["loi"])
            for name in ("bao_cao_kiem_toan_doc_lap.json", "doi_soat_nav.csv", "sha256.txt"):
                self.assertEqual((audit1 / name).read_bytes(), (audit2 / name).read_bytes())
            self.assertFalse(report1["pipeline_duoc_goi"])
            self.assertFalse(report1["huan_luyen_lai"])
            self.assertFalse(report1["san_pham_bi_sua"])

            with (product / "feature_raw.csv").open("a", encoding="utf-8") as handle:
                handle.write("tamper\n")
            valid, failed = kiem_toan_san_pham(
                thu_muc_san_pham=product, thu_muc_bao_cao=root / "audit_fail", ma_kiem_toan="audit_fixture_fail",
            )
            self.assertFalse(valid)
            failed_report = json.loads((failed / "bao_cao_kiem_toan_doc_lap.json").read_text())
            self.assertTrue(any("PRODUCT_SHA256:feature_raw.csv" in item for item in failed_report["loi"]))


if __name__ == "__main__":
    unittest.main()
