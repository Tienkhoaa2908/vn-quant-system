from __future__ import annotations

import inspect
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import (
    FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1,
    FEATURE_ORDER_STRICT_OHLCV_V1,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import CauHinhMoc4
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import _m3_config_reduced
from he_thong_dinh_luong.nghien_cuu_moc_4.runner_io import _doc_publication_rut_gon
from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong
from ho_tro_m4_reduced import tao_dau_vao_runner, tao_publication_rut_gon


class TestHopDongGiaRutGonM4(unittest.TestCase):
    def test_feature_order_loai_duy_nhat_high_low(self) -> None:
        self.assertEqual(len(FEATURE_ORDER_STRICT_OHLCV_V1), 24)
        self.assertEqual(len(FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1), 23)
        self.assertEqual(
            set(FEATURE_ORDER_STRICT_OHLCV_V1) - set(FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1),
            {"bien_do_cao_thap_chuan_hoa"},
        )

    def test_config_reduced_giu_dung_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = tao_dau_vao_runner(Path(tmp), count=20)
            raw = json.loads(paths["cau_hinh"].read_text())["moc_4"]
            raw["thu_muc_dau_ra"] = "."
            config = CauHinhMoc4.tu_mapping(raw)
            self.assertTrue(config.la_reduced)
            self.assertEqual(config.top_k, 2)
            self.assertEqual(config.so_thang_train_toi_thieu, 24)
            self.assertEqual(config.stock_price_basis, "CHUA_XAC_NHAN")
            self.assertIn("PRICE_BASIS_UNCONFIRMED", config.canh_bao_muc_dich())

    def test_config_reduced_tu_choi_drift_top_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = tao_dau_vao_runner(Path(tmp), count=20)
            raw = json.loads(paths["cau_hinh"].read_text())["moc_4"]
            raw["top_k"] = 3
            raw["thu_muc_dau_ra"] = "."
            with self.assertRaisesRegex(ValueError, "canonical"):
                CauHinhMoc4.tu_mapping(raw)

    def test_parser_doc_so_ma_tu_profile_khong_hardcode_121(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publication, _ = tao_publication_rut_gon(Path(tmp) / "p", symbols=("AAA", "BBB"), count=5)
            result = _doc_publication_rut_gon(publication, candidate_union_expected_count=2)
            self.assertEqual(result.publication_observed_symbol_count, 2)
            self.assertEqual(result.publication_observed_row_count, 10)

    def test_volume_thap_phan_fail_closed_khong_lam_tron(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publication, _ = tao_publication_rut_gon(
                Path(tmp) / "p", symbols=("AAA", "BBB"), count=5, fractional_volume=True,
            )
            with self.assertRaisesRegex(ValueError, "so nguyen"):
                _doc_publication_rut_gon(publication, candidate_union_expected_count=2)

    def test_profile_count_lech_publication_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            publication, _ = tao_publication_rut_gon(Path(tmp) / "p", symbols=("AAA", "BBB"), count=5)
            with self.assertRaisesRegex(ValueError, "So ma du kien"):
                _doc_publication_rut_gon(publication, candidate_union_expected_count=3)

    def test_runner_reduced_dung_cau_hinh_m3_typed_khong_simple_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = tao_dau_vao_runner(Path(tmp), count=20)
            raw = json.loads(paths["cau_hinh"].read_text())["mo_phong"]
            result = _m3_config_reduced(raw)
            self.assertIsInstance(result, cau_hinh_mo_phong)
            self.assertEqual(result.co_so_gia, "CHUA_XAC_NHAN")
            self.assertNotIn("SimpleNamespace", inspect.getsource(_m3_config_reduced))


if __name__ == "__main__":
    unittest.main()
