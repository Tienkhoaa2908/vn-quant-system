from __future__ import annotations
import unittest
from datetime import date, datetime, timedelta, timezone

from he_thong_dinh_luong.nghien_cuu_moc_4.do_phu import DongLoai, bao_cao_do_phu
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import BanGhiUniverse
from he_thong_dinh_luong.nghien_cuu_moc_4.universe import xac_dinh_universe

UTC = timezone.utc
T = date(2026, 1, 30)
SIGNAL = datetime(2026, 1, 30, 15, 0, tzinfo=UTC)


def record(symbol="AAA", member=True, effective=date(2025, 1, 1), published=datetime(2026, 1, 30, 14, 0, tzinfo=UTC)):
    return BanGhiUniverse(effective, symbol, member, "fixture", "1", published)


class TestUniverseM4(unittest.TestCase):
    def test_cong_bo_truoc_tin_hieu_cung_ngay_duoc_dung(self):
        row = xac_dinh_universe([record()], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)[0]
        self.assertTrue(row.thuoc_universe)

    def test_cong_bo_sau_tin_hieu_cung_ngay_bi_loai(self):
        rows = [record(published=SIGNAL + timedelta(minutes=1))]
        result = xac_dinh_universe(rows, ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, cac_ma=["AAA"])[0]
        self.assertFalse(result.thuoc_universe)
        self.assertEqual(result.ly_do, "thieu_snapshot")

    def test_timestamp_record_thieu_mui_gio_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "mui gio"):
            record(published=datetime(2026, 1, 30, 14, 0))

    def test_timestamp_signal_thieu_mui_gio_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "mui gio"):
            xac_dinh_universe([record()], ngay=T, thoi_diem_tao_tin_hieu=datetime(2026, 1, 30, 15, 0))

    def test_ngay_hieu_luc_tuong_lai_bi_loai(self):
        result = xac_dinh_universe([record(effective=date(2026, 2, 1))], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, cac_ma=["AAA"])[0]
        self.assertEqual(result.ly_do, "thieu_snapshot")

    def test_ma_vao_va_roi_universe(self):
        rows = [
            record(member=True, effective=date(2025, 1, 1), published=datetime(2024, 12, 1, tzinfo=UTC)),
            record(member=False, effective=date(2026, 1, 1), published=datetime(2025, 12, 20, tzinfo=UTC)),
        ]
        result = xac_dinh_universe(rows, ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)[0]
        self.assertFalse(result.thuoc_universe)
        self.assertEqual(result.ly_do, "khong_thuoc_universe")

    def test_huy_niem_yet_van_ton_tai_trong_lich_su(self):
        rows = [
            record("OLD", True, date(2020, 1, 1), datetime(2019, 12, 1, tzinfo=UTC)),
            record("OLD", False, date(2025, 1, 1), datetime(2024, 12, 1, tzinfo=UTC)),
        ]
        before = xac_dinh_universe(rows, ngay=date(2024, 1, 31), thoi_diem_tao_tin_hieu=datetime(2024, 1, 31, 15, tzinfo=UTC))[0]
        after = xac_dinh_universe(rows, ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)[0]
        self.assertTrue(before.thuoc_universe)
        self.assertFalse(after.thuoc_universe)

    def test_thieu_snapshot_fail_closed(self):
        result = xac_dinh_universe([], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, cac_ma=["AAA"])[0]
        self.assertFalse(result.thuoc_universe)
        self.assertEqual(result.ly_do, "thieu_snapshot")

    def test_duplicate_record_bi_tu_choi(self):
        r = record()
        with self.assertRaisesRegex(ValueError, "Trung ban ghi"):
            xac_dinh_universe([r, r], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)

    def test_them_record_sau_signal_khong_doi_ket_qua(self):
        base = [record()]
        future = record(member=False, effective=date(2025, 1, 1), published=SIGNAL + timedelta(hours=1))
        left = xac_dinh_universe(base, ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)[0]
        right = xac_dinh_universe(base + [future], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)[0]
        self.assertEqual(left.thuoc_universe, right.thuoc_universe)

    def test_cung_instant_offset_khac_nhau(self):
        plus7 = timezone(timedelta(hours=7))
        published = datetime(2026, 1, 30, 21, 0, tzinfo=plus7)
        result = xac_dinh_universe([record(published=published)], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL)[0]
        self.assertTrue(result.thuoc_universe)


class TestCoverageM4(unittest.TestCase):
    def test_tong_hop_theo_ngay_ma_ly_do(self):
        report = bao_cao_do_phu([
            DongLoai(T, "AAA", "thieu_snapshot"),
            DongLoai(T, "BBB", "thieu_warm_up"),
        ])
        self.assertEqual(report["theo_ngay"][T.isoformat()], 2)
        self.assertEqual(report["theo_ma"]["AAA"], 1)
        self.assertEqual(report["theo_ly_do"]["thieu_warm_up"], 1)

    def test_coverage_duplicate_bi_tu_choi(self):
        row = DongLoai(T, "AAA", "thieu_snapshot")
        with self.assertRaisesRegex(ValueError, "Trung dong"):
            bao_cao_do_phu([row, row])
