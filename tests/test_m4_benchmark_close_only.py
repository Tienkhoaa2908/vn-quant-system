from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.baseline import du_doan_baseline_test, metric_baseline_test, xep_hang_baseline_test
from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import phien_cuoi_thang, tao_feature_cuoi_thang
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import BENCHMARK_CONTRACT, ThanhBenchmarkDongCua, ThanhOHLCV
from he_thong_dinh_luong.nghien_cuu_moc_4.nhan import tao_nhan
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from he_thong_dinh_luong.nghien_cuu_moc_4.runner_core import _samples
from he_thong_dinh_luong.nghien_cuu_moc_4.runner_io import _doc_benchmark_dong_cua, _xac_thuc_benchmark_identity
from ho_tro_m4 import bars, weekdays
from ho_tro_m4_runner import tao_fixture_runner, write_csv

GIT_SHA = "e" * 40
FIXED_TIME = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
BENCHMARK_FIELDS = ["ma", "ngay", "gia_dong_cua", "nguon", "phien_ban", "co_so_gia"]


def benchmark_close_rows(dates: list[date], *, base: float = 1000.0) -> list[ThanhBenchmarkDongCua]:
    return [ThanhBenchmarkDongCua("VNINDEX", day, base + 0.2 * index, "fixture_benchmark", "v1", "gia_dieu_chinh") for index, day in enumerate(dates)]


def benchmark_ohlcv_rows(dates: list[date], *, high_pad: float, low_pad: float, open_offset: float, volume_offset: int) -> list[ThanhOHLCV]:
    result: list[ThanhOHLCV] = []
    for index, day in enumerate(dates):
        close = 1000.0 + 0.2 * index
        result.append(ThanhOHLCV("VNINDEX", day, close + open_offset, max(close + high_pad, close + open_offset), min(close - low_pad, close + open_offset), close, 1_000_000 + volume_offset + index, "legacy_fixture", "v1", "gia_dieu_chinh"))
    return result


class TestKieuVaParserBenchmarkCloseOnly(unittest.TestCase):
    def test_stock_van_tu_choi_high_nho_hon_close(self):
        with self.assertRaises(ValueError):
            ThanhOHLCV("AAA", date(2026, 1, 2), 10.0, 10.5, 9.0, 11.0, 100)

    def test_stock_van_tu_choi_low_lon_hon_close(self):
        with self.assertRaises(ValueError):
            ThanhOHLCV("AAA", date(2026, 1, 2), 10.0, 12.0, 11.0, 10.5, 100)

    def test_benchmark_chap_nhan_ba_close_anomaly(self):
        for day, close in ((date(2021, 2, 17), 1155.78), (date(2021, 12, 10), 1463.54), (date(2023, 5, 15), 1065.71)):
            with self.subTest(day=day):
                self.assertEqual(ThanhBenchmarkDongCua("VNINDEX", day, close, "kbs", "4.0.4", "gia_khong_dieu_chinh").gia_dong_cua, close)

    def test_parser_chap_nhan_ba_ngay_anomaly_close_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "benchmark.csv"
            write_csv(path, BENCHMARK_FIELDS, [
                {"ma": "VNINDEX", "ngay": "2021-02-17", "gia_dong_cua": 1155.78, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "gia_khong_dieu_chinh"},
                {"ma": "VNINDEX", "ngay": "2021-12-10", "gia_dong_cua": 1463.54, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "gia_khong_dieu_chinh"},
                {"ma": "VNINDEX", "ngay": "2023-05-15", "gia_dong_cua": 1065.71, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "gia_khong_dieu_chinh"},
            ])
            parsed = _doc_benchmark_dong_cua(path, expected_symbol="VNINDEX")
            self.assertEqual([row.gia_dong_cua for row in parsed.rows], [1155.78, 1463.54, 1065.71])

    def test_close_nan_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), float("nan"), "kbs", "4.0.4", "x")

    def test_close_inf_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), float("inf"), "kbs", "4.0.4", "x")

    def test_close_khong_duong_bi_tu_choi(self):
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), value, "kbs", "4.0.4", "x")

    def test_duplicate_ngay_bi_tu_choi(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "benchmark.csv"
            row = {"ma": "VNINDEX", "ngay": "2023-05-15", "gia_dong_cua": 1065.71, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "x"}
            write_csv(path, BENCHMARK_FIELDS, [row, dict(row)])
            with self.assertRaisesRegex(ValueError, "trung ma/ngay"):
                _doc_benchmark_dong_cua(path, expected_symbol="VNINDEX")

    def test_sai_identity_benchmark_bi_tu_choi(self):
        rows = [ThanhBenchmarkDongCua("HNXINDEX", date(2026, 1, 2), 100.0, "x", "1", "x")]
        with self.assertRaisesRegex(ValueError, "VNINDEX"):
            _xac_thuc_benchmark_identity(rows, "VNINDEX")

    def test_thieu_metadata_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), 100.0, "", "1", "x")

    def test_extra_ohlcv_volume_column_bi_tu_choi(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "benchmark.csv"
            fields = [*BENCHMARK_FIELDS, "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat", "khoi_luong"]
            write_csv(path, fields, [{"ma": "VNINDEX", "ngay": "2023-05-15", "gia_dong_cua": 1065.71, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "x", "gia_mo_cua": 1074.82, "gia_cao_nhat": 1076.32, "gia_thap_nhat": 1067.15, "khoi_luong": 791524900}])
            with self.assertRaisesRegex(ValueError, "cot ngoai hop dong"):
                _doc_benchmark_dong_cua(path, expected_symbol="VNINDEX")


class TestCongThucBenchmarkChiDungClose(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dates = weekdays(date(2023, 1, 2), 340)
        cls.stock = [*bars("AAA", cls.dates, base=80.0, step=0.17), *bars("BBB", cls.dates, base=120.0, step=0.09)]
        cls.close_only = benchmark_close_rows(cls.dates)
        cls.legacy_a = benchmark_ohlcv_rows(cls.dates, high_pad=1.0, low_pad=1.0, open_offset=-0.2, volume_offset=0)
        cls.legacy_b = benchmark_ohlcv_rows(cls.dates, high_pad=8.0, low_pad=6.0, open_offset=3.0, volume_offset=9_000_000)
        cls.signal_dates = phien_cuoi_thang(cls.dates)

    def test_feature_close_only_giong_implementation_ohlcv_hop_le(self):
        self.assertEqual(tao_feature_cuoi_thang(self.stock, self.close_only, lich_benchmark=self.dates, feature_bat_buoc=("vnindex_momentum_60",)), tao_feature_cuoi_thang(self.stock, self.legacy_a, lich_benchmark=self.dates, feature_bat_buoc=("vnindex_momentum_60",)))

    def test_label_close_only_giong_implementation_ohlcv_hop_le(self):
        self.assertEqual(tao_nhan(self.stock, self.close_only, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates), tao_nhan(self.stock, self.legacy_a, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates))

    def test_metamorphic_ohlv_benchmark_khong_doi_feature_label_prediction_ranking_metric(self):
        features_a = tao_feature_cuoi_thang(self.stock, self.legacy_a, lich_benchmark=self.dates, feature_bat_buoc=("dong_luong_12_1",))
        features_b = tao_feature_cuoi_thang(self.stock, self.legacy_b, lich_benchmark=self.dates, feature_bat_buoc=("dong_luong_12_1",))
        labels_a = tao_nhan(self.stock, self.legacy_a, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates)
        labels_b = tao_nhan(self.stock, self.legacy_b, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates)
        self.assertEqual(features_a, features_b)
        self.assertEqual(labels_a, labels_b)
        eligible = {(row.ngay, row.ma) for row in features_a if row.hop_le}
        samples_a, momentum_a = _samples(features_a, labels_a, eligible, ("dong_luong_12_1",))
        samples_b, momentum_b = _samples(features_b, labels_b, eligible, ("dong_luong_12_1",))
        self.assertEqual(samples_a, samples_b)
        predictions_a = du_doan_baseline_test(fold="fold_close", samples=samples_a, momentum_theo_khoa=momentum_a)
        predictions_b = du_doan_baseline_test(fold="fold_close", samples=samples_b, momentum_theo_khoa=momentum_b)
        self.assertEqual(predictions_a, predictions_b)
        self.assertEqual(xep_hang_baseline_test(predictions_a, top_k=1), xep_hang_baseline_test(predictions_b, top_k=1))
        self.assertEqual(metric_baseline_test(predictions_a), metric_baseline_test(predictions_b))

    def test_thay_high_low_co_phieu_van_doi_bien_do(self):
        target = self.signal_dates[-1]
        stock_wide = [replace(row, gia_cao_nhat=row.gia_dong_cua + 5.0, gia_thap_nhat=row.gia_dong_cua - 5.0) if row.ma == "AAA" and row.ngay == target else row for row in self.stock]
        normal = tao_feature_cuoi_thang(self.stock, self.close_only, lich_benchmark=self.dates, feature_bat_buoc=("bien_do_cao_thap_chuan_hoa",))
        wide = tao_feature_cuoi_thang(stock_wide, self.close_only, lich_benchmark=self.dates, feature_bat_buoc=("bien_do_cao_thap_chuan_hoa",))
        normal_map = {(row.ngay, row.ma): row for row in normal}
        wide_map = {(row.ngay, row.ma): row for row in wide}
        self.assertNotEqual(normal_map[(target, "AAA")].gia_tri["bien_do_cao_thap_chuan_hoa"], wide_map[(target, "AAA")].gia_tri["bien_do_cao_thap_chuan_hoa"])


class TestRunnerBenchmarkCloseOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        fixture = cls.root / "fixture"
        fixture.mkdir()
        cls.paths = tao_fixture_runner(fixture)
        cls.result = chay_nghien_cuu_moc_4(duong_dan_cau_hinh=cls.paths["cau_hinh"], duong_dan_ohlcv=cls.paths["ohlcv"], duong_dan_benchmark=cls.paths["benchmark"], duong_dan_lich_benchmark=cls.paths["lich_benchmark"], duong_dan_universe=cls.paths["universe"], duong_dan_corporate_actions=cls.paths["corporate_actions"], thu_muc_dau_ra=cls.root / "out", ma_lan_chay="close-only", git_commit=GIT_SHA, thoi_diem_utc=FIXED_TIME)

        research_fixture = cls.root / "fixture-research"
        research_fixture.mkdir()
        cls.research_paths = tao_fixture_runner(research_fixture)
        research_config = json.loads(cls.research_paths["cau_hinh"].read_text(encoding="utf-8"))
        research_config["moc_4"]["muc_dich_lan_chay"] = "nghien_cuu"
        research_config["moc_4"]["co_so_gia_da_xac_nhan"] = True
        cls.research_paths["cau_hinh"].write_text(
            json.dumps(research_config, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        cls.research_result = chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=cls.research_paths["cau_hinh"],
            duong_dan_ohlcv=cls.research_paths["ohlcv"],
            duong_dan_benchmark=cls.research_paths["benchmark"],
            duong_dan_lich_benchmark=cls.research_paths["lich_benchmark"],
            duong_dan_universe=cls.research_paths["universe"],
            duong_dan_corporate_actions=cls.research_paths["corporate_actions"],
            thu_muc_dau_ra=cls.root / "out-research",
            ma_lan_chay="close-only-research",
            git_commit=GIT_SHA,
            thoi_diem_utc=FIXED_TIME,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_manifest_report_technical_co_policy_dong_va_hai_warning(self):
        report = json.loads((self.result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
        for payload in (report, manifest["metadata"]):
            self.assertEqual(payload["benchmark_contract"], BENCHMARK_CONTRACT)
            policy = payload["benchmark_policy"]
            self.assertTrue(policy["features_va_labels_chi_dung_close"])
            self.assertFalse(policy["open_high_low_volume_duoc_dung"])
            self.assertFalse(policy["correction_overlay_duoc_phep"])
            self.assertTrue(policy["raw_source_bat_buoc_giu_bat_bien"])
            self.assertFalse(policy["exact_official_ohlc_hien_co"])
            self.assertTrue(policy["chi_kiem_tra_ky_thuat"])
            self.assertIn("BENCHMARK_CLOSE_ONLY", payload["canh_bao"])
            self.assertIn("BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN", payload["canh_bao"])
            self.assertIn("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA", payload["canh_bao"])
            self.assertIn("KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC", payload["gioi_han"])

    def test_manifest_report_research_khong_mang_gioi_han_technical(self):
        report = json.loads((self.research_result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.research_result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
        for payload in (report, manifest["metadata"]):
            self.assertFalse(payload["benchmark_policy"]["chi_kiem_tra_ky_thuat"])
            self.assertNotIn("KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC", payload["gioi_han"])
            self.assertNotIn("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA", payload["canh_bao"])
            self.assertIn("BENCHMARK_CLOSE_ONLY", payload["canh_bao"])
            self.assertIn("BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN", payload["canh_bao"])

    def test_report_manifest_khong_chua_assertion_mo_ho_hoac_trang_thai_dieu_phoi(self):
        forbidden_limits = {
            "TIER_A_TIER_B_CHUA_CHAY",
            "NGUON_DU_LIEU_THAT_CHUA_DUOC_PHE_DUYET",
        }
        forbidden_policy_keys = {
            "correction_overlay",
            "raw_source_giu_bat_bien",
            "exact_official_ohlc_da_co",
        }
        for result in (self.result, self.research_result):
            report = json.loads((result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
            manifest = json.loads((result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
            for payload in (report, manifest["metadata"]):
                self.assertTrue(forbidden_limits.isdisjoint(payload["gioi_han"]))
                self.assertTrue(forbidden_policy_keys.isdisjoint(payload["benchmark_policy"]))
                self.assertFalse(payload["benchmark_policy"]["correction_overlay_duoc_phep"])
                self.assertTrue(payload["benchmark_policy"]["raw_source_bat_buoc_giu_bat_bien"])
                self.assertFalse(payload["benchmark_policy"]["exact_official_ohlc_hien_co"])

    def test_runner_end_to_end_nhan_benchmark_close_only(self):
        with self.paths["benchmark"].open(newline="", encoding="utf-8") as handle:
            self.assertEqual(next(csv.reader(handle)), BENCHMARK_FIELDS)
        self.assertGreater(self.result.so_fold, 0)
        self.assertGreater(self.result.so_fold_thanh_cong, 0)

    def test_runner_tu_choi_full_ohlcv_o_vi_tri_benchmark_canonical(self):
        fixture_root = self.root / "full-ohlcv"
        fixture_root.mkdir()
        paths = tao_fixture_runner(fixture_root)
        full = fixture_root / "benchmark_full.csv"
        fields = ["ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat", "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia"]
        write_csv(full, fields, [{"ma": "VNINDEX", "ngay": "2024-01-02", "gia_mo_cua": 999.0, "gia_cao_nhat": 1001.0, "gia_thap_nhat": 998.0, "gia_dong_cua": 1000.0, "khoi_luong": 1_000_000, "nguon": "legacy", "phien_ban": "1", "co_so_gia": "gia_dieu_chinh"}])
        with self.assertRaisesRegex(ValueError, "sai schema"):
            chay_nghien_cuu_moc_4(duong_dan_cau_hinh=paths["cau_hinh"], duong_dan_ohlcv=paths["ohlcv"], duong_dan_benchmark=full, duong_dan_lich_benchmark=paths["lich_benchmark"], duong_dan_universe=paths["universe"], duong_dan_corporate_actions=paths["corporate_actions"], thu_muc_dau_ra=self.root / "reject", ma_lan_chay="reject-full", git_commit=GIT_SHA, thoi_diem_utc=FIXED_TIME)


if __name__ == "__main__":
    unittest.main()
