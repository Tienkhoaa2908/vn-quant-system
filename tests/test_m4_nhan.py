from __future__ import annotations
import unittest
from datetime import date

from he_thong_dinh_luong.nghien_cuu_moc_4.nhan import tao_nhan
from ho_tro_m4 import bars, weekdays


class TestNhanM4(unittest.TestCase):
    def setUp(self):
        self.dates = weekdays(date(2026, 1, 2), 30)
        self.stock = bars("AAA", self.dates, base=100, step=1)
        self.benchmark = bars("VNINDEX", self.dates, base=1000, step=1)
        self.T = self.dates[0]

    def test_t_h_theo_lich_benchmark(self):
        row = tao_nhan(self.stock, self.benchmark, cac_ngay_tin_hieu=[self.T], label_horizon=20)[0]
        self.assertEqual(row.T_H, self.dates[20])
        self.assertEqual(row.ngay_ket_thuc_nhan, self.dates[20])

    def test_return_va_label_tinh_tay(self):
        row = tao_nhan(self.stock, self.benchmark, cac_ngay_tin_hieu=[self.T], label_horizon=20)[0]
        expected_s = self.stock[20].gia_dong_cua/self.stock[0].gia_dong_cua-1
        expected_b = self.benchmark[20].gia_dong_cua/self.benchmark[0].gia_dong_cua-1
        self.assertAlmostEqual(row.loi_nhuan_co_phieu, expected_s)
        self.assertAlmostEqual(row.loi_nhuan_benchmark, expected_b)
        self.assertEqual(row.nhan, int(expected_s-expected_b > 0))

    def test_khong_dung_bar_thu_h_con_ton_tai_cua_ma(self):
        missing = {self.dates[20]}
        stock = bars("AAA", self.dates + weekdays(self.dates[-1], 3)[1:], base=100, step=1, missing=missing)
        row = tao_nhan(stock, self.benchmark, cac_ngay_tin_hieu=[self.T], label_horizon=20)[0]
        self.assertIsNone(row.nhan)
        self.assertEqual(row.T_H, self.dates[20])

    def test_thieu_benchmark_dung_endpoint_nhan_rong(self):
        benchmark = [x for x in self.benchmark if x.ngay != self.dates[20]]
        row = tao_nhan(self.stock, benchmark, cac_ngay_tin_hieu=[self.T], label_horizon=20, lich_benchmark=self.dates)[0]
        self.assertIsNone(row.nhan)
        self.assertEqual(row.ly_do_nhan_rong, "thieu_bar_benchmark_t_hoac_t_h")

    def test_khong_du_horizon_nhan_rong(self):
        row = tao_nhan(self.stock, self.benchmark, cac_ngay_tin_hieu=[self.dates[15]], label_horizon=20)[0]
        self.assertIsNone(row.T_H)
        self.assertEqual(row.ly_do_nhan_rong, "khong_du_horizon")

    def test_t_khong_thuoc_lich_benchmark(self):
        row = tao_nhan(self.stock, self.benchmark, cac_ngay_tin_hieu=[date(2026, 1, 3)], label_horizon=20)[0]
        self.assertEqual(row.ly_do_nhan_rong, "T_khong_thuoc_lich_benchmark")

    def test_duplicate_bar_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "khoa trung"):
            tao_nhan(self.stock + [self.stock[0]], self.benchmark, cac_ngay_tin_hieu=[self.T])
