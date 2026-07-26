from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.do_phu import bao_cao_do_phu
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import BanGhiUniverse
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import (
    _doc_ohlcv,
    _ma_co_gap_pit,
    _phien_yeu_cau_coverage_pit,
)
from ho_tro_m4_runner import write_csv


def _record(day: date, symbol: str, member: bool) -> BanGhiUniverse:
    return BanGhiUniverse(
        ngay_hieu_luc=day,
        ma=symbol,
        thuoc_universe=member,
        nguon="fixture",
        phien_ban="v1",
        thoi_diem_cong_bo=datetime(2023, 12, 1, tzinfo=timezone.utc),
    )


class TestCoveragePointInTime(unittest.TestCase):
    def setUp(self) -> None:
        self.calendar = tuple(date(2024, 1, day) for day in range(2, 11))

    def _required(self, records, sessions):
        return _phien_yeu_cau_coverage_pit(
            calendar=self.calendar,
            sample_dates=(self.calendar[3],),
            universe_records=records,
            symbols=("AAA",),
            sessions_by_symbol={"AAA": set(sessions)},
        )["AAA"]

    def test_ma_moi_niem_yet_khong_bi_tinh_thieu_truoc_ngay_bat_dau(self) -> None:
        sessions = set(self.calendar[4:])
        required = self._required([_record(self.calendar[0], "AAA", True)], sessions)
        self.assertTrue(required)
        self.assertGreaterEqual(min(required), self.calendar[4])

    def test_ma_vao_universe_giua_lich_su(self) -> None:
        sessions = set(self.calendar)
        required = self._required([
            _record(self.calendar[0], "AAA", False),
            _record(self.calendar[4], "AAA", True),
        ], sessions)
        self.assertEqual(required, set(self.calendar[4:]))

    def test_ma_roi_universe_khong_bi_tinh_thieu_sau_ngay_roi(self) -> None:
        sessions = set(self.calendar)
        required = self._required([
            _record(self.calendar[0], "AAA", True),
            _record(self.calendar[6], "AAA", False),
        ], sessions)
        self.assertEqual(required, set(self.calendar[:6]))

    def test_khoang_trong_truoc_membership_khong_phai_gap(self) -> None:
        sessions = set(self.calendar[4:])
        required = self._required([
            _record(self.calendar[0], "AAA", False),
            _record(self.calendar[4], "AAA", True),
        ], sessions)
        self.assertEqual(_ma_co_gap_pit({"AAA": required}, {"AAA": sessions}), [])

    def test_khoang_trong_trong_membership_la_gap(self) -> None:
        sessions = set(self.calendar)
        sessions.remove(self.calendar[5])
        required = self._required([_record(self.calendar[0], "AAA", True)], sessions)
        # Day 5 remains required because listing/data start precedes it and membership is active.
        self.assertIn(self.calendar[5], required)
        self.assertEqual(_ma_co_gap_pit({"AAA": required}, {"AAA": sessions}), ["AAA"])

    def test_loi_gia_duoc_loai_co_kiem_soat_va_ghi_ma(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "ohlcv.csv"
            write_csv(path, [
                "ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat",
                "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia",
            ], [{
                "ma": "AAA", "ngay": "2024-01-02", "gia_mo_cua": "NaN",
                "gia_cao_nhat": "11", "gia_thap_nhat": "9", "gia_dong_cua": "10",
                "khoi_luong": "100", "nguon": "fixture", "phien_ban": "v1",
                "co_so_gia": "gia_dieu_chinh",
            }])
            result = _doc_ohlcv(path)
        self.assertEqual(result.rows, ())
        self.assertEqual(result.ma_loi_gia, ("AAA",))
        self.assertEqual(result.khoa_loi_gia, (("AAA", date(2024, 1, 2)),))

    def test_loi_volume_duoc_loai_co_kiem_soat_va_ghi_ma(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "ohlcv.csv"
            write_csv(path, [
                "ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat",
                "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia",
            ], [{
                "ma": "AAA", "ngay": "2024-01-02", "gia_mo_cua": "10",
                "gia_cao_nhat": "11", "gia_thap_nhat": "9", "gia_dong_cua": "10",
                "khoi_luong": "Inf", "nguon": "fixture", "phien_ban": "v1",
                "co_so_gia": "gia_dieu_chinh",
            }])
            result = _doc_ohlcv(path)
        self.assertEqual(result.rows, ())
        self.assertEqual(result.ma_loi_volume, ("AAA",))
        self.assertEqual(result.khoa_loi_volume, (("AAA", date(2024, 1, 2)),))

    def test_ma_that_bai_hoan_toan_van_co_mau_so_theo_membership(self) -> None:
        required = _phien_yeu_cau_coverage_pit(
            calendar=self.calendar, sample_dates=(self.calendar[3],),
            universe_records=[_record(self.calendar[2], "AAA", True)],
            symbols=("AAA",), sessions_by_symbol={"AAA": set()},
        )["AAA"]
        self.assertEqual(required, set(self.calendar[2:]))

    def test_ngay_loi_truoc_bar_hop_le_duoc_tinh_trong_mau_so(self) -> None:
        sessions = {self.calendar[4], self.calendar[5]}
        required = _phien_yeu_cau_coverage_pit(
            calendar=self.calendar, sample_dates=(),
            universe_records=[_record(self.calendar[0], "AAA", True)],
            symbols=("AAA",), sessions_by_symbol={"AAA": sessions},
            ngay_bat_dau_theo_ma={"AAA": self.calendar[2]},
        )["AAA"]
        self.assertIn(self.calendar[2], required)
        self.assertEqual(_ma_co_gap_pit({"AAA": required}, {"AAA": sessions}), ["AAA"])

    def test_mau_so_coverage_theo_ma_dung_tap_phien_yeu_cau(self) -> None:
        required = {"AAA": {self.calendar[3], self.calendar[4]}}
        available = {"AAA": {self.calendar[0], self.calendar[3]}}
        report = bao_cao_do_phu(
            (), cac_ngay_yeu_cau=self.calendar, cac_ma_universe=("AAA",),
            phien_co_du_lieu_theo_ma=available, phien_yeu_cau_theo_ma=required,
        )
        row = report["coverage_theo_ma"][0]
        self.assertEqual(row["so_phien_yeu_cau"], 2)
        self.assertEqual(row["so_phien_co"], 1)
        self.assertEqual(row["ty_le"], 0.5)


if __name__ == "__main__":
    unittest.main()
