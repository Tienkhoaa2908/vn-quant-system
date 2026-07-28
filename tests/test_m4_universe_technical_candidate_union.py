from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import ThanhGiaMoDongKhoiLuong
from he_thong_dinh_luong.nghien_cuu_moc_4.universe import xac_dinh_technical_candidate_union


def bar(symbol: str, day: date) -> ThanhGiaMoDongKhoiLuong:
    return ThanhGiaMoDongKhoiLuong(
        symbol, day, 10.0, 10.5, 1000, "fixture", "v1", "CHUA_XAC_NHAN", "a" * 64,
    )


class TestTechnicalCandidateUnionM4(unittest.TestCase):
    def test_chi_thuoc_universe_khi_co_bar_dung_t(self) -> None:
        d1 = date(2026, 1, 30)
        d2 = date(2026, 2, 2)
        states = xac_dinh_technical_candidate_union(
            [bar("AAA", d1), bar("BBB", d2)], ngay=d2, cac_ma=("AAA", "BBB"),
        )
        by_symbol = {row.ma: row for row in states}
        self.assertFalse(by_symbol["AAA"].thuoc_universe)
        self.assertEqual(by_symbol["AAA"].ly_do, "thieu_bar_t")
        self.assertTrue(by_symbol["BBB"].thuoc_universe)

    def test_khong_carry_bar_cu_sang_ngay_sau(self) -> None:
        d1 = date(2026, 1, 30)
        d2 = date(2026, 2, 2)
        state = xac_dinh_technical_candidate_union([bar("AAA", d1)], ngay=d2, cac_ma=("AAA",))[0]
        self.assertFalse(state.thuoc_universe)

    def test_ket_qua_on_dinh_theo_ma(self) -> None:
        day = date(2026, 1, 30)
        states = xac_dinh_technical_candidate_union(
            [bar("BBB", day), bar("AAA", day)], ngay=day, cac_ma=("BBB", "AAA"),
        )
        self.assertEqual([row.ma for row in states], ["AAA", "BBB"])


if __name__ == "__main__":
    unittest.main()
