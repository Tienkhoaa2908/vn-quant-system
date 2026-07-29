from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from ho_tro_m4_reduced import tao_dau_vao_runner


class TestMetadataCoSoGiaTachBietM4(unittest.TestCase):
    def test_reduced_runner_tach_stock_va_benchmark_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = tao_dau_vao_runner(root)
            result = chay_nghien_cuu_moc_4(
                duong_dan_cau_hinh=paths["cau_hinh"],
                thu_muc_publication_gia_rut_gon=paths["publication"],
                duong_dan_benchmark=paths["benchmark"],
                duong_dan_lich_benchmark=paths["lich_benchmark"],
                duong_dan_corporate_actions=paths["corporate_actions"],
                thu_muc_dau_ra=root / "out",
                ma_lan_chay="fixture_reduced",
                git_commit="a" * 40,
                thoi_diem_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
            )
            product = result.thu_muc_san_pham
            self.assertEqual(len(list(product.iterdir())), 23)
            config = json.loads((product / "cau_hinh.json").read_text())
            self.assertEqual(config["mo_phong"]["co_so_gia"], "CHUA_XAC_NHAN")
            manifest = json.loads((product / "manifest.json").read_text())
            metadata = manifest["metadata"]
            self.assertEqual(metadata["stock_price_basis"], "CHUA_XAC_NHAN")
            self.assertFalse(metadata["stock_price_basis_confirmed"])
            self.assertEqual(metadata["benchmark_price_basis"], "benchmark_basis_fixture")
            self.assertFalse(metadata["benchmark_price_basis_confirmed"])
            self.assertFalse(metadata["stock_benchmark_price_basis_equality_required"])
            self.assertEqual(metadata["research_gate"], "FAIL")
            self.assertIn("PRICE_BASIS_UNCONFIRMED", metadata["research_gate_reasons"])
            self.assertFalse(metadata["corporate_actions_applied"])
            self.assertEqual(manifest["manifest_schema_version"], "m4_manifest_v2")
            self.assertNotIn("bien_do_cao_thap_chuan_hoa", (product / "feature_raw.csv").read_text().splitlines()[0])


if __name__ == "__main__":
    unittest.main()
