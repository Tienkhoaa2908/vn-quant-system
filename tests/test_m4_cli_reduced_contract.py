from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.dong_lenh import main
from ho_tro_m4_reduced import tao_dau_vao_runner


class TestCLIReducedContractM4(unittest.TestCase):
    def test_reduced_khong_tu_nhan_dang_ohlcv_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = tao_dau_vao_runner(root, count=20)
            with self.assertRaises(SystemExit) as raised:
                main([
                    "--cau-hinh", str(paths["cau_hinh"]),
                    "--ohlcv", str(paths["publication"] / "du_lieu_gia_mo_dong_khoi_luong.csv"),
                    "--benchmark", str(paths["benchmark"]),
                    "--lich-benchmark", str(paths["lich_benchmark"]),
                    "--universe", str(paths["publication"] / "bao_cao_do_phu_hop_dong_rut_gon.json"),
                    "--corporate-actions", str(paths["corporate_actions"]),
                    "--thu-muc-dau-ra", str(root / "out"),
                    "--ma-lan-chay", "cli_no_autodetect",
                    "--git-commit", "c" * 40,
                ])
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
