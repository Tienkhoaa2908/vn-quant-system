from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.cong_bo import TEN_SAN_PHAM
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from ho_tro_m4_runner import tao_fixture_runner

FIXED_TIME = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)
GIT_SHA = "d" * 40


class TestRunnerDauCuoiM4(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.paths = tao_fixture_runner(cls.root)
        cls.result_1 = chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=cls.paths["cau_hinh"],
            duong_dan_ohlcv=cls.paths["ohlcv"],
            duong_dan_benchmark=cls.paths["benchmark"],
            duong_dan_lich_benchmark=cls.paths["lich_benchmark"],
            duong_dan_universe=cls.paths["universe"],
            duong_dan_corporate_actions=cls.paths["corporate_actions"],
            thu_muc_dau_ra=cls.root / "out-1", ma_lan_chay="fixture-vang",
            git_commit=GIT_SHA, thoi_diem_utc=FIXED_TIME,
        )
        cls.result_2 = chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=cls.paths["cau_hinh"],
            duong_dan_ohlcv=cls.paths["ohlcv"],
            duong_dan_benchmark=cls.paths["benchmark"],
            duong_dan_lich_benchmark=cls.paths["lich_benchmark"],
            duong_dan_universe=cls.paths["universe"],
            duong_dan_corporate_actions=cls.paths["corporate_actions"],
            thu_muc_dau_ra=cls.root / "out-2", ma_lan_chay="fixture-vang",
            git_commit=GIT_SHA, thoi_diem_utc=FIXED_TIME,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_tao_du_17_tep_va_manifest(self):
        names = {path.name for path in self.result_1.thu_muc_san_pham.iterdir()}
        self.assertEqual(names, {*TEN_SAN_PHAM, "manifest.json"})
        manifest = json.loads((self.result_1.thu_muc_san_pham / "manifest.json").read_text())
        self.assertEqual(manifest["metadata"]["git_commit"], GIT_SHA)
        self.assertEqual(manifest["metadata"]["ma_lan_chay"], "fixture-vang")
        self.assertEqual(set(manifest["inputs"]), {
            "benchmark", "cau_hinh", "corporate_actions", "lich_benchmark", "ohlcv", "universe",
        })
        self.assertEqual(set(manifest["files"]), set(TEN_SAN_PHAM))

    def test_fold_prediction_ranking_khong_rong(self):
        self.assertGreater(self.result_1.so_fold, 0)
        self.assertGreater(self.result_1.so_fold_thanh_cong, 0)
        self.assertGreater(self.result_1.so_du_doan_test_logistic, 0)
        self.assertGreater(self.result_1.so_du_doan_test_baseline, 0)
        with (self.result_1.thu_muc_san_pham / "du_doan.csv").open(newline="", encoding="utf-8") as handle:
            predictions = list(csv.DictReader(handle))
        with (self.result_1.thu_muc_san_pham / "xep_hang.csv").open(newline="", encoding="utf-8") as handle:
            rankings = list(csv.DictReader(handle))
        self.assertTrue(any(row["vai_tro_du_lieu"] == "test" for row in predictions))
        self.assertTrue(any(row["duoc_chon"] == "true" for row in rankings))

    def test_lenh_khop_dung_t1_va_nav_duong(self):
        report = json.loads((self.result_1.thu_muc_san_pham / "bao_cao.json").read_text())
        with self.paths["lich_benchmark"].open(newline="", encoding="utf-8") as handle:
            calendar = [row["ngay"] for row in csv.DictReader(handle)]
        index = {day: i for i, day in enumerate(calendar)}
        for strategy in ("backtest_logistic", "backtest_baseline"):
            audit = report[strategy]
            for signal, execution in zip(audit["ngay_tin_hieu"], audit["ngay_thuc_thi"], strict=True):
                if execution is not None:
                    self.assertEqual(execution, calendar[index[signal] + 1])
            self.assertGreater(float(audit["nav_cuoi"]), 0.0)
            self.assertGreater(audit["so_lan_tai_can_bang"], 0)

    def test_tai_lap_byte_for_byte(self):
        first = self.result_1.thu_muc_san_pham
        second = self.result_2.thu_muc_san_pham
        self.assertEqual(
            {path.name: path.read_bytes() for path in first.iterdir()},
            {path.name: path.read_bytes() for path in second.iterdir()},
        )

    def test_cli_chay_pipeline_tu_tep_cuc_bo(self):
        output = self.root / "out-cli"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        command = [
            sys.executable, "-m", "he_thong_dinh_luong.nghien_cuu_moc_4",
            "--cau-hinh", str(self.paths["cau_hinh"]),
            "--ohlcv", str(self.paths["ohlcv"]),
            "--benchmark", str(self.paths["benchmark"]),
            "--lich-benchmark", str(self.paths["lich_benchmark"]),
            "--universe", str(self.paths["universe"]),
            "--corporate-actions", str(self.paths["corporate_actions"]),
            "--thu-muc-dau-ra", str(output),
            "--ma-lan-chay", "cli-fixture",
            "--git-commit", GIT_SHA,
        ]
        completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["hop_le"])
        self.assertEqual(len(list((output / "cli-fixture").iterdir())), 17)


if __name__ == "__main__":
    unittest.main()
