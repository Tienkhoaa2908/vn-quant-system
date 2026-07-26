from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.eligibility import (
    LY_DO_KHONG_THANH_KHOAN,
    LY_DO_THIEU_OPEN_T1,
    danh_gia_eligibility,
    phien_t1_chinh_thuc,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import (
    BanGhiUniverse,
    DongFeature,
    ThanhOHLCV,
    TrangThaiUniverse,
)
from ho_tro_m4 import SIGNAL_TIME

T = date(2026, 1, 30)
T1 = date(2026, 2, 2)
T2 = date(2026, 2, 3)


def state(member: bool = True) -> TrangThaiUniverse:
    record = BanGhiUniverse(date(2025, 1, 1), "AAA", member, "fixture", "1", SIGNAL_TIME)
    return TrangThaiUniverse(T, "AAA", member, None if member else "khong_thuoc_universe", record)


def feature(liquidity: float | None = 1_000_000.0) -> DongFeature:
    return DongFeature(T, "AAA", {"gtgd_tb_20": liquidity}, True, ())


def bar(day: date) -> ThanhOHLCV:
    return ThanhOHLCV("AAA", day, 10.0, 11.0, 9.0, 10.0, 1000)


class TestEligibilityDayDuM4(unittest.TestCase):
    def evaluate(self, **overrides: object):
        data = {
            "state": state(), "feature": feature(), "benchmark_metadata_ok": True,
            "open_t1": bar(T1), "cua_so_thanh_khoan": 20,
            "nguong_gtgd_tb_toi_thieu": 500_000.0,
        }
        data.update(overrides)
        return danh_gia_eligibility(**data)

    def test_membership_dat_nhung_thanh_khoan_khong_dat(self):
        ok, reasons, _ = self.evaluate(feature=feature(100.0))
        self.assertFalse(ok)
        self.assertIn(LY_DO_KHONG_THANH_KHOAN, reasons)

    def test_thanh_khoan_none_fail_closed(self):
        ok, reasons, value = self.evaluate(feature=feature(None))
        self.assertFalse(ok)
        self.assertIsNone(value)
        self.assertIn(LY_DO_KHONG_THANH_KHOAN, reasons)

    def test_co_close_t_nhung_thieu_open_t1(self):
        ok, reasons, _ = self.evaluate(open_t1=None)
        self.assertFalse(ok)
        self.assertIn(LY_DO_THIEU_OPEN_T1, reasons)

    def test_co_open_t2_khong_duoc_bu_cho_t1(self):
        prices = {T2: bar(T2)}
        exact_t1 = prices.get(phien_t1_chinh_thuc((T, T1, T2), T))
        ok, reasons, _ = self.evaluate(open_t1=exact_t1)
        self.assertFalse(ok)
        self.assertIn(LY_DO_THIEU_OPEN_T1, reasons)

    def test_them_du_lieu_sau_t_khong_doi_eligibility_tai_t(self):
        future_error_keys = {("AAA", T2)}
        before = self.evaluate(loi_gia=("AAA", T) in future_error_keys)
        future_error_keys.add(("AAA", date(2026, 2, 4)))
        after = self.evaluate(loi_gia=("AAA", T) in future_error_keys)
        self.assertEqual(before, after)
        self.assertTrue(before[0])


if __name__ == "__main__":
    unittest.main()
