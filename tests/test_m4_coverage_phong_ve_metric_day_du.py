from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.chi_so import metric_model_test, metric_ranking_test
from he_thong_dinh_luong.nghien_cuu_moc_4.cong_bo import TEN_SAN_PHAM, cong_bo_san_pham
from he_thong_dinh_luong.nghien_cuu_moc_4.do_phu import DongLoai, bao_cao_do_phu
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import (
    DongFeature, DongNhan, DongXepHang, DuDoan, ThanhOHLCV,
)

D1 = date(2026, 1, 30)
D2 = date(2026, 2, 27)


class TestCoverageSchemaDayDuM4(unittest.TestCase):
    def test_schema_coverage_day_du(self):
        report = bao_cao_do_phu(
            [DongLoai(D1, "BBB", "thieu_bar_co_phieu_ma250")],
            loi_fold=[{"fold": "f1", "ly_do": "train_mot_lop"}],
            cac_ngay_yeu_cau=[D1, D2], cac_ngay_thuc_te=[D1],
            cac_ma_universe=["AAA", "BBB"],
            phien_co_du_lieu_theo_ma={"AAA": [D1, D2], "BBB": [D1]},
            coverage_theo_ngay={D1: (1, 2), D2: (1, 2)},
            ma_that_bai_hoan_toan=["CCC"], ma_thieu_warm_up=["BBB"],
            ma_co_gap=["BBB"], ma_loi_gia=["DDD"], ma_loi_volume=["EEE"],
            ma_thieu_corporate_actions=["AAA"], ngay_it_hon_top_k=[D1],
            nguon_ohlcv="stock-source", phien_ban_ohlcv="v1",
            nguon_universe="universe-source", phien_ban_universe="v2",
            nguon_benchmark="benchmark-source", phien_ban_benchmark="v3",
            co_so_gia="gia_khong_dieu_chinh",
        )
        required = {
            "ngay_yeu_cau_tu", "ngay_yeu_cau_den", "ngay_thuc_te_tu", "ngay_thuc_te_den",
            "tong_ma_universe", "tong_ma_co_du_lieu", "ma_that_bai_hoan_toan",
            "ma_thieu_warm_up", "ma_co_gap", "ma_loi_gia", "ma_loi_volume",
            "ma_thieu_corporate_actions", "coverage_theo_ngay", "coverage_theo_ma",
            "so_ngay_it_hon_top_k", "ly_do_loai", "loi_fold", "nguon", "co_so_gia",
        }
        self.assertTrue(required.issubset(report))
        self.assertEqual(report["coverage_theo_ngay"][0], {
            "ngay": D1.isoformat(), "tu_so": 1, "mau_so": 2, "ty_le": 0.5,
        })
        per_symbol = {x["ma"]: x for x in report["coverage_theo_ma"]}
        self.assertEqual(per_symbol["BBB"]["so_phien_co"], 1)
        self.assertEqual(per_symbol["BBB"]["so_phien_yeu_cau"], 2)
        self.assertEqual(report["nguon"]["benchmark"]["phien_ban"], "v3")
        self.assertEqual(report["loi_fold"], [{"fold": "f1", "ly_do": "train_mot_lop"}])


class TestPhongVeFiniteM4(unittest.TestCase):
    def test_ohlcv_nan_inf_bi_tu_choi(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "huu han"):
                ThanhOHLCV("AAA", D1, value, 11.0, 9.0, 10.0, 100)

    def test_feature_nan_inf_bi_tu_choi(self):
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "huu han"):
                DongFeature(D1, "AAA", {"x": value}, False)

    def test_probability_nan_inf_ngoai_bien_bi_tu_choi(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                DuDoan("f1", "m1", "test", D1, "AAA", value)

    def test_relative_return_nan_inf_bi_tu_choi(self):
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "huu han"):
                DongNhan(D1, "AAA", D2, D2, 0.1, 0.0, value, 1, None)

    def test_product_json_csv_nan_inf_bi_tu_choi(self):
        products = {name: ("{}\n" if name.endswith(".json") else "a,b\n") for name in TEN_SAN_PHAM}
        metadata = {
            "git_commit": "c" * 40, "ma_lan_chay": "x", "thoi_diem_utc": "2026-07-26T00:00:00Z",
            "python_version": "3.12", "uv_version": "uv", "scikit_learn_version": "1.9.0",
            "nguon_ohlcv": "x", "phien_ban_ohlcv": "1", "nguon_universe": "x",
            "phien_ban_universe": "1", "nguon_benchmark": "x", "phien_ban_benchmark": "1",
            "co_so_gia": "gia_dieu_chinh", "muc_dich_lan_chay": "kiem_tra_ky_thuat",
            "cau_hinh_feature": {"x": 1}, "cau_hinh_label": {"x": 1},
            "cau_hinh_fold": {"x": 1}, "cau_hinh_model": {"x": 1},
            "cau_hinh_ranking": {"x": 1}, "canh_bao": [], "gioi_han": ["fixture"],
        }
        for name, payload in (("bao_cao.json", '{"x":NaN}\n'), ("du_doan.csv", "x\nInf\n")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                broken = dict(products); broken[name] = payload
                with self.assertRaisesRegex(ValueError, "NaN|Inf"):
                    cong_bo_san_pham(Path(tmp) / "run", broken, metadata=metadata, dau_vao={"x": b"1"})


class TestMetricPhongVeM4(unittest.TestCase):
    def prediction(self, *, fold="f1", model="m1", role="test", day=D1, symbol="AAA", p=0.5):
        return DuDoan(fold, model, role, day, symbol, p, 1, 0.1)

    def rank(self, *, fold="f1", model="m1", day=D1, symbol="AAA", role="test"):
        return DongXepHang(fold, model, day, symbol, 0.5, 1, True, 0.5, 1, 0.1, role)

    def test_metric_model_chi_nhan_test(self):
        with self.assertRaisesRegex(ValueError, "chi nhan prediction test"):
            metric_model_test([self.prediction(role="validation")])

    def test_metric_model_tu_choi_duplicate_va_model_fold_khong_nhat_quan(self):
        row = self.prediction()
        with self.assertRaisesRegex(ValueError, "Trung khoa"):
            metric_model_test([row, row])
        with self.assertRaisesRegex(ValueError, "mot model_id"):
            metric_model_test([row, self.prediction(model="m2", symbol="BBB")])

    def test_metric_ranking_chi_nhan_test(self):
        row = self.rank()
        object.__setattr__(row, "vai_tro_du_lieu", "validation")
        with self.assertRaisesRegex(ValueError, "du lieu test"):
            metric_ranking_test([row])

    def test_metric_ranking_tu_choi_duplicate_va_model_fold_khong_nhat_quan(self):
        row = self.rank()
        with self.assertRaisesRegex(ValueError, "Trung khoa"):
            metric_ranking_test([row, row])
        with self.assertRaisesRegex(ValueError, "mot model_id"):
            metric_ranking_test([row, self.rank(model="m2", symbol="BBB")])


if __name__ == "__main__":
    unittest.main()
