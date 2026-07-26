from __future__ import annotations
import unittest
from datetime import date
from statistics import fmean

from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import FEATURE_ORDER_MAC_DINH, phien_cuoi_thang, tao_feature_cuoi_thang
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import ThanhOHLCV
from ho_tro_m4 import bars, weekdays


class TestFeatureM4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates = weekdays(date(2024, 1, 2), 320)
        cls.stock = bars("AAA", cls.dates, base=100, step=0.25)
        cls.benchmark = bars("VNINDEX", cls.dates, base=1000, step=0.5)

    def test_phien_cuoi_thang(self):
        samples = phien_cuoi_thang(self.dates)
        self.assertTrue(samples)
        for day in samples[:-1]:
            self.assertNotEqual((day.year, day.month), (samples[samples.index(day)+1].year, samples[samples.index(day)+1].month))

    def test_khong_sinh_mau_ngay_thuong(self):
        output = tao_feature_cuoi_thang(self.stock, self.benchmark)
        self.assertEqual({x.ngay for x in output}, set(phien_cuoi_thang(self.dates)))

    def test_warm_up_ma250(self):
        output = tao_feature_cuoi_thang(self.stock, self.benchmark)
        invalid = [x for x in output if self.dates.index(x.ngay) < 250]
        valid = [x for x in output if self.dates.index(x.ngay) >= 250]
        self.assertTrue(all(not x.hop_le for x in invalid))
        self.assertTrue(valid and all(x.hop_le for x in valid))

    def test_feature_tinh_tay_ma20(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        history = [x.gia_dong_cua for x in self.stock if x.ngay <= row.ngay]
        expected = history[-1] / fmean(history[-20:]) - 1
        self.assertAlmostEqual(row.gia_tri["khoang_cach_ma20"], expected)

    def test_return_20_tinh_tay(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        history = [x.gia_dong_cua for x in self.stock if x.ngay <= row.ngay]
        self.assertAlmostEqual(row.gia_tri["loi_nhuan_20"], history[-1] / history[-21] - 1)

    def test_momentum_12_1_tinh_tay(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        history = [x.gia_dong_cua for x in self.stock if x.ngay <= row.ngay]
        self.assertAlmostEqual(row.gia_tri["dong_luong_12_1"], history[-21] / history[-251] - 1)

    def test_relative_strength_120(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        s = [x.gia_dong_cua for x in self.stock if x.ngay <= row.ngay]
        b = [x.gia_dong_cua for x in self.benchmark if x.ngay <= row.ngay]
        expected = (s[-1]/s[-121]-1) - (b[-1]/b[-121]-1)
        self.assertAlmostEqual(row.gia_tri["suc_manh_tuong_doi_120"], expected)

    def test_high_low_range_tai_t(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        bar = next(x for x in self.stock if x.ngay == row.ngay)
        self.assertAlmostEqual(row.gia_tri["bien_do_cao_thap_chuan_hoa"], (bar.gia_cao_nhat-bar.gia_thap_nhat)/bar.gia_dong_cua)

    def test_liquidity_va_volume_zero(self):
        changed = list(self.stock)
        for i in range(1, 4):
            old = changed[-i]
            changed[-i] = ThanhOHLCV(old.ma, old.ngay, old.gia_mo_cua, old.gia_cao_nhat, old.gia_thap_nhat, old.gia_dong_cua, 0)
        row = [x for x in tao_feature_cuoi_thang(changed, self.benchmark) if x.hop_le][-1]
        self.assertEqual(row.gia_tri["so_phien_volume_0_60"], 3)
        self.assertGreaterEqual(row.gia_tri["gtgd_tb_60"], 0)

    def test_vnindex_regime_co_du(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        for name in ("vnindex_tren_ma250", "vnindex_momentum_60", "vnindex_bien_dong_20", "vnindex_bien_dong_60"):
            self.assertIn(name, row.gia_tri)

    def test_metamorphic_them_du_lieu_sau_t_khong_doi_feature_t(self):
        original = tao_feature_cuoi_thang(self.stock, self.benchmark)
        target = [x for x in original if x.hop_le][-2]
        future_dates = weekdays(self.dates[-1], 20)[1:]
        extended_stock = self.stock + bars("AAA", future_dates, base=5000, step=100)
        extended_benchmark = self.benchmark + bars("VNINDEX", future_dates, base=9000, step=100)
        extended = tao_feature_cuoi_thang(extended_stock, extended_benchmark)
        same = next(x for x in extended if x.ngay == target.ngay and x.ma == target.ma)
        self.assertEqual(dict(target.gia_tri), dict(same.gia_tri))

    def test_thieu_bar_t_fail_closed(self):
        sample = phien_cuoi_thang(self.dates)[-1]
        stock = [x for x in self.stock if x.ngay != sample]
        row = next(x for x in tao_feature_cuoi_thang(stock, self.benchmark) if x.ngay == sample)
        self.assertFalse(row.hop_le)
        self.assertIn("thieu_bar_t", row.ly_do)

    def test_duplicate_ohlcv_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "trung"):
            tao_feature_cuoi_thang(self.stock + [self.stock[0]], self.benchmark)

    def test_feature_order_day_du(self):
        row = [x for x in tao_feature_cuoi_thang(self.stock, self.benchmark) if x.hop_le][-1]
        self.assertEqual(set(row.gia_tri), set(FEATURE_ORDER_MAC_DINH))
