from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import csv
from io import StringIO
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.adapter_mo_phong import chay_backtest_oos_lien_tuc
from he_thong_dinh_luong.nghien_cuu_moc_4.cong_bo import (
    COT_DU_DOAN,
    COT_FEATURE_SAU_TIEN_XU_LY,
    tao_csv_du_doan,
    tao_csv_feature_sau_tien_xu_ly,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.do_phu import DongLoai, bao_cao_do_phu
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import (
    BanGhiPointInTime,
    DongXepHang,
    DuDoan,
    xac_thuc_co_so_gia_va_su_kien,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.universe import chon_ban_ghi_pit
from ho_tro_m4 import cau_hinh

UTC = timezone.utc
T = date(2026, 1, 30)
SIGNAL = datetime(2026, 1, 30, 15, 0, tzinfo=UTC)


def pit(loai: str, *, key: str = "K", published: datetime | None = None, effective: date = date(2025, 1, 1)) -> BanGhiPointInTime:
    return BanGhiPointInTime(
        loai_du_lieu=loai,
        khoa_ban_ghi=key,
        ngay_hieu_luc=effective,
        nguon="fixture",
        phien_ban="1",
        thoi_diem_cong_bo=published or datetime(2026, 1, 30, 14, 0, tzinfo=UTC),
        du_lieu={"gia_tri": 1},
    )


class TestPitDungChungM4(unittest.TestCase):
    def test_benchmark_metadata_truoc_signal_duoc_dung(self):
        rows = chon_ban_ghi_pit([pit("benchmark_metadata")], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, loai_du_lieu="benchmark_metadata")
        self.assertEqual(len(rows), 1)

    def test_corporate_action_sau_signal_cung_ngay_bi_loai(self):
        record = pit("corporate_action", published=SIGNAL + timedelta(seconds=1))
        rows = chon_ban_ghi_pit([record], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, loai_du_lieu="corporate_action")
        self.assertEqual(rows, [])

    def test_event_point_in_time_chon_ban_moi_nhat_hop_le(self):
        old = pit("su_kien_point_in_time", published=datetime(2026, 1, 30, 13, tzinfo=UTC), effective=date(2024, 1, 1))
        new = pit("su_kien_point_in_time", published=datetime(2026, 1, 30, 14, tzinfo=UTC), effective=date(2025, 1, 1))
        rows = chon_ban_ghi_pit([old, new], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, loai_du_lieu="su_kien_point_in_time")
        self.assertEqual(rows, [new])

    def test_timestamp_pit_thieu_mui_gio_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "mui gio"):
            pit("benchmark_metadata", published=datetime(2026, 1, 30, 14))

    def test_duplicate_pit_bi_tu_choi(self):
        row = pit("corporate_action")
        with self.assertRaisesRegex(ValueError, "Trung ban ghi"):
            chon_ban_ghi_pit([row, row], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, loai_du_lieu="corporate_action")

    def test_loai_pit_ngoai_hop_dong_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "loai_du_lieu"):
            chon_ban_ghi_pit([], ngay=T, thoi_diem_tao_tin_hieu=SIGNAL, loai_du_lieu="khac")

    def test_gia_dieu_chinh_khong_kem_corporate_actions(self):
        with self.assertRaisesRegex(ValueError, "khong duoc kem"):
            xac_thuc_co_so_gia_va_su_kien(cau_hinh(), so_su_kien=1)

    def test_kiem_tra_ky_thuat_khong_co_su_kien_tra_canh_bao(self):
        warnings = xac_thuc_co_so_gia_va_su_kien(cau_hinh(), so_su_kien=0)
        self.assertIn("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA", warnings)


class TestSanPhamTheoFoldM4(unittest.TestCase):
    def test_feature_processed_co_header_bat_buoc(self):
        row = {
            "fold": "f1", "stage": "validation_selection", "model_id": "m1", "vai_tro_du_lieu": "train",
            "ngay": "2026-01-30", "ma": "AAA", "x": 1.5,
        }
        text = tao_csv_feature_sau_tien_xu_ly([row], ("x",))
        header = next(csv.reader(StringIO(text)))
        self.assertEqual(tuple(header[:6]), COT_FEATURE_SAU_TIEN_XU_LY)

    def test_feature_processed_sai_thu_tu_cot_bi_tu_choi(self):
        row = {
            "model_id": "m1", "stage": "validation_selection", "fold": "f1", "vai_tro_du_lieu": "train",
            "ngay": "2026-01-30", "ma": "AAA", "x": 1.5,
        }
        with self.assertRaisesRegex(ValueError, "thu tu"):
            tao_csv_feature_sau_tien_xu_ly([row], ("x",))

    def test_feature_processed_duplicate_bi_tu_choi(self):
        row = {
            "fold": "f1", "stage": "final_refit", "model_id": "m1", "vai_tro_du_lieu": "test",
            "ngay": "2026-01-30", "ma": "AAA", "x": 1.5,
        }
        with self.assertRaisesRegex(ValueError, "Trung khoa"):
            tao_csv_feature_sau_tien_xu_ly([row, row], ("x",))

    def test_du_doan_header_va_vai_tro(self):
        row = DuDoan("f1", "m1", "validation", T, "AAA", 0.25)
        text = tao_csv_du_doan([row])
        header = next(csv.reader(StringIO(text)))
        self.assertEqual(tuple(header), COT_DU_DOAN)
        self.assertIn("validation", text)

    def test_du_doan_duplicate_bi_tu_choi(self):
        row = DuDoan("f1", "m1", "test", T, "AAA", 0.25)
        with self.assertRaisesRegex(ValueError, "Trung khoa"):
            tao_csv_du_doan([row, row])

    def test_coverage_ghi_loi_fold(self):
        report = bao_cao_do_phu(
            [DongLoai(T, "AAA", "thieu_snapshot")],
            loi_fold=[{"fold": "fold_001", "ly_do": "train_mot_lop"}],
        )
        self.assertEqual(report["loi_fold"], [{"fold": "fold_001", "ly_do": "train_mot_lop"}])

    def test_coverage_loi_fold_thieu_khoa_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "fold va ly_do"):
            bao_cao_do_phu([], loi_fold=[{"fold": "f1"}])


try:
    from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong, thanh_gia
    HAVE_M3 = True
except ModuleNotFoundError:
    HAVE_M3 = False


@unittest.skipUnless(HAVE_M3, "Sandbox cuc bo khong co module M3; CI repo se chay test nay.")
class TestTichHopEngineM3That(unittest.TestCase):
    def test_tin_hieu_close_t_khop_open_dung_t1(self):
        d1, d2, d3 = date(2026, 1, 30), date(2026, 2, 2), date(2026, 2, 3)
        prices = [
            thanh_gia("AAA", d1, Decimal("10"), Decimal("10"), 1000, True, True),
            thanh_gia("AAA", d2, Decimal("11"), Decimal("11"), 1000, True, True),
            thanh_gia("AAA", d3, Decimal("12"), Decimal("12"), 1000, True, True),
        ]
        config = cau_hinh_mo_phong(
            Decimal("100000"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
            1, 252, Decimal("0"), "muc_tieu_bang_0", False,
            "khong_dieu_chinh", "dong", "dong",
        )
        rankings = [DongXepHang("f1", "m1", d1, "AAA", 0.9, 1, True, 0.5, 1, 0.1)]
        result = chay_backtest_oos_lien_tuc(
            rankings=rankings, du_lieu_gia=prices, cau_hinh_mo_phong=config,
        )
        self.assertEqual(len(result.khop_lenh), 1)
        self.assertEqual(result.khop_lenh[0].ngay_khop, d2)
        self.assertEqual(result.khop_lenh[0].gia_mo_cua, Decimal("11"))
        self.assertEqual(result.so_lan_tai_can_bang, 1)
