from __future__ import annotations

from datetime import date, timedelta
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import phien_cuoi_thang, tao_feature_cuoi_thang
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import ThanhOHLCV
from ho_tro_m4 import bars, weekdays


class TestCalendarAlignmentDayDuM4(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calendar = weekdays(date(2024, 1, 2), 340)
        cls.stock = bars("AAA", cls.calendar, base=100, step=0.2)
        cls.benchmark = bars("VNINDEX", cls.calendar, base=1000, step=0.3)
        cls.T = phien_cuoi_thang(cls.calendar)[-1]
        cls.index = cls.calendar.index(cls.T)

    def row(self, stock, benchmark=None, required=("khoang_cach_ma250",)):
        return next(
            x for x in tao_feature_cuoi_thang(
                stock,
                self.benchmark if benchmark is None else benchmark,
                lich_benchmark=self.calendar,
                feature_bat_buoc=required,
            )
            if x.ngay == self.T and x.ma == "AAA"
        )

    def without(self, rows, missing_day):
        return [x for x in rows if x.ngay != missing_day]

    def test_thieu_bar_giua_cua_so_ma250(self):
        missing = self.calendar[self.index - 100]
        row = self.row(self.without(self.stock, missing), required=("khoang_cach_ma250",))
        self.assertFalse(row.hop_le)
        self.assertIsNone(row.gia_tri["khoang_cach_ma250"])
        self.assertIn("thieu_bar_co_phieu_ma250", row.ly_do)

    def test_thieu_endpoint_momentum_20_60_120_250(self):
        for horizon in (20, 60, 120, 250):
            with self.subTest(horizon=horizon):
                endpoint = self.calendar[self.index - horizon]
                name = f"loi_nhuan_{horizon}"
                row = self.row(self.without(self.stock, endpoint), required=(name,))
                self.assertFalse(row.hop_le)
                self.assertIsNone(row.gia_tri[name])
                self.assertIn(f"thieu_bar_co_phieu_{name}", row.ly_do)

    def test_thieu_bar_trong_volatility_20_60(self):
        for horizon in (20, 60):
            with self.subTest(horizon=horizon):
                missing = self.calendar[self.index - max(2, horizon // 2)]
                name = f"bien_dong_{horizon}"
                row = self.row(self.without(self.stock, missing), required=(name,))
                self.assertFalse(row.hop_le)
                self.assertIsNone(row.gia_tri[name])
                self.assertIn(f"thieu_bar_co_phieu_{name}", row.ly_do)

    def test_thieu_bar_trong_liquidity_20_60(self):
        for horizon in (20, 60):
            with self.subTest(horizon=horizon):
                missing = self.calendar[self.index - max(2, horizon // 2)]
                name = f"gtgd_tb_{horizon}"
                row = self.row(self.without(self.stock, missing), required=(name,))
                self.assertFalse(row.hop_le)
                self.assertIsNone(row.gia_tri[name])
                self.assertIn(f"thieu_bar_co_phieu_{name}", row.ly_do)

    def test_stock_thieu_nhung_benchmark_co(self):
        row = self.row(self.without(self.stock, self.T), required=("bien_do_cao_thap_chuan_hoa",))
        self.assertFalse(row.hop_le)
        self.assertIn("thieu_bar_t", row.ly_do)
        self.assertIn(self.T, {x.ngay for x in self.benchmark})

    def test_lich_co_phien_nhung_benchmark_bar_thieu(self):
        missing = self.calendar[self.index - 10]
        benchmark = self.without(self.benchmark, missing)
        row = self.row(self.stock, benchmark=benchmark, required=("vnindex_bien_dong_20",))
        self.assertFalse(row.hop_le)
        self.assertIsNone(row.gia_tri["vnindex_bien_dong_20"])
        self.assertIn("thieu_bar_benchmark_vnindex_bien_dong_20", row.ly_do)

    def test_them_bar_cu_khong_bu_duoc_bar_thieu(self):
        missing = self.calendar[self.index - 80]
        stock = self.without(self.stock, missing)
        old_day = self.calendar[0] - timedelta(days=10)
        old = ThanhOHLCV("AAA", old_day, 89.0, 90.0, 88.0, 89.5, 999)
        row = self.row([old, *stock], required=("khoang_cach_ma250",))
        self.assertFalse(row.hop_le)
        self.assertIsNone(row.gia_tri["khoang_cach_ma250"])

    def test_khong_nen_thoi_gian_khi_thieu_endpoint(self):
        endpoint = self.calendar[self.index - 20]
        stock = self.without(self.stock, endpoint)
        old_day = self.calendar[0] - timedelta(days=1)
        stock.append(ThanhOHLCV("AAA", old_day, 99.0, 100.0, 98.0, 99.5, 1000))
        row = self.row(stock, required=("loi_nhuan_20",))
        self.assertFalse(row.hop_le)
        self.assertIsNone(row.gia_tri["loi_nhuan_20"])
        self.assertIn("thieu_bar_co_phieu_loi_nhuan_20", row.ly_do)


if __name__ == "__main__":
    unittest.main()
