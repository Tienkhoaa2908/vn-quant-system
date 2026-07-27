from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import he_thong_dinh_luong.nghien_cuu_moc_4.runner as runner
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from ho_tro_m4_runner import tao_fixture_runner


class TestFoldTestRongFailClosed(unittest.TestCase):
    def _run(self, temp: str, paths: dict[str, Path], run_id: str):
        return chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=paths["cau_hinh"], duong_dan_ohlcv=paths["ohlcv"],
            duong_dan_benchmark=paths["benchmark"],
            duong_dan_lich_benchmark=paths["lich_benchmark"],
            duong_dan_universe=paths["universe"],
            duong_dan_corporate_actions=paths["corporate_actions"],
            thu_muc_dau_ra=Path(temp) / "out", ma_lan_chay=run_id,
            git_commit="e" * 40,
        )

    def test_selected_test_rong_khong_duoc_tinh_fold_thanh_cong(self) -> None:
        with TemporaryDirectory() as temp:
            paths = tao_fixture_runner(Path(temp))
            original = runner.loc_mau_theo_fold

            def empty_test(samples, fold):
                selected = dict(original(samples, fold))
                selected["test"] = ()
                return selected

            with patch.object(runner, "loc_mau_theo_fold", side_effect=empty_test):
                result = self._run(temp, paths, "test-rong")
            coverage = json.loads((result.thu_muc_san_pham / "bao_cao_do_phu.json").read_text())
            with (result.thu_muc_san_pham / "mo_hinh.csv").open(newline="", encoding="utf-8") as handle:
                models = list(csv.DictReader(handle))
            with (result.thu_muc_san_pham / "xep_hang.csv").open(newline="", encoding="utf-8") as handle:
                rankings = list(csv.DictReader(handle))
        self.assertEqual(result.so_fold_thanh_cong, 0)
        self.assertEqual(result.so_du_doan_test_logistic, 0)
        self.assertEqual(rankings, [])
        self.assertTrue(any(x["ly_do"] == "test_rong" for x in coverage["loi_fold"]))
        self.assertTrue(any(x["ly_do_that_bai"] == "test_rong" for x in models))

    def test_khong_co_prediction_test_khong_duoc_tinh_fold_thanh_cong(self) -> None:
        with TemporaryDirectory() as temp:
            paths = tao_fixture_runner(Path(temp))
            with patch.object(runner, "du_doan_test", return_value=()):
                result = self._run(temp, paths, "prediction-rong")
            coverage = json.loads((result.thu_muc_san_pham / "bao_cao_do_phu.json").read_text())
            with (result.thu_muc_san_pham / "mo_hinh.csv").open(newline="", encoding="utf-8") as handle:
                models = list(csv.DictReader(handle))
        self.assertEqual(result.so_fold_thanh_cong, 0)
        self.assertEqual(result.so_du_doan_test_logistic, 0)
        self.assertTrue(any(x["ly_do"] == "khong_co_prediction_test" for x in coverage["loi_fold"]))
        self.assertTrue(any(x["ly_do_that_bai"] == "khong_co_prediction_test" for x in models))


if __name__ == "__main__":
    unittest.main()
