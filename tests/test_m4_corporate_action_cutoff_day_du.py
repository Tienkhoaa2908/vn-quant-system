from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.adapter_mo_phong import chay_backtest_oos_lien_tuc
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import (
    BanGhiPointInTime,
    DongXepHang,
    xac_thuc_co_so_gia_va_su_kien,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import _m3_events
from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong, thanh_gia
from ho_tro_m4 import cau_hinh

VN = timezone(timedelta(hours=7))
D_SIGNAL_1 = date(2026, 1, 31)
D_EXEC_1 = date(2026, 2, 1)
D_EFFECTIVE = date(2026, 2, 15)
D_SIGNAL_2 = date(2026, 2, 28)
D_EXEC_2 = date(2026, 3, 1)


def event(*, published: datetime, key: str = "AAA-split") -> BanGhiPointInTime:
    payload = {
        "ma": "AAA", "loai_su_kien": "chia_tach",
        "ngay_hieu_luc": D_EFFECTIVE.isoformat(), "ngay_thanh_toan": None,
        "ty_le": "2", "gia_tri_tien_mat": None,
        "nguon": "fixture_ca", "phien_ban": "v1",
    }
    return BanGhiPointInTime(
        "corporate_action", key, D_EFFECTIVE, "fixture_ca", "v1", published, payload,
    )


def config_m3():
    return cau_hinh_mo_phong(
        Decimal("100000"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        1, 252, Decimal("0"), "muc_tieu_bang_0", True,
        "khong_dieu_chinh", "dong", "dong",
    )


def price(day: date, value: str):
    return thanh_gia("AAA", day, Decimal(value), Decimal(value), 100000, True, True)


class TestCorporateActionCutoffM4(unittest.TestCase):
    def test_su_kien_giua_hai_ky_tai_can_bang_duoc_ap_dung(self):
        record = event(published=datetime(2026, 2, 10, 10, tzinfo=VN))
        events = _m3_events(
            [record], "gia_khong_dieu_chinh", oos_start=D_SIGNAL_1, oos_end=D_EXEC_2,
        )
        rankings = [
            DongXepHang("f1", "m1", D_SIGNAL_1, "AAA", 0.9, 1, True, 1.0, 1, 0.1),
            DongXepHang("f2", "m2", D_SIGNAL_2, "AAA", 0.9, 1, True, 1.0, 1, 0.1),
        ]
        prices = [
            price(D_SIGNAL_1, "10"), price(D_EXEC_1, "10"),
            price(D_EFFECTIVE, "5"), price(D_SIGNAL_2, "5"), price(D_EXEC_2, "5"),
        ]
        result = chay_backtest_oos_lien_tuc(
            rankings=rankings, du_lieu_gia=prices, cau_hinh_mo_phong=config_m3(),
            cac_su_kien=events, ngay_tai_can_bang=[D_SIGNAL_1, D_SIGNAL_2],
            cac_ma_lien_quan=["AAA"], oos_start=D_SIGNAL_1, oos_end=D_EXEC_2,
        )
        self.assertTrue(any(row["ngay"] == D_EFFECTIVE for row in result.su_kien_da_ap_dung))

    def test_cong_bo_sau_ngay_hieu_luc_bi_tu_choi(self):
        record = event(published=datetime(2026, 2, 16, 9, tzinfo=VN))
        with self.assertRaisesRegex(ValueError, "sau cutoff"):
            _m3_events([record], "gia_khong_dieu_chinh", oos_start=D_SIGNAL_1, oos_end=D_EXEC_2)

    def test_cong_bo_sau_khi_backtest_da_di_qua_hieu_luc_bi_tu_choi(self):
        record = event(published=datetime(2026, 2, 20, 9, tzinfo=VN))
        with self.assertRaisesRegex(ValueError, "hoi to"):
            _m3_events([record], "gia_khong_dieu_chinh", oos_start=D_SIGNAL_1, oos_end=D_EXEC_2)

    def test_gia_dieu_chinh_kem_su_kien_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "khong duoc kem"):
            xac_thuc_co_so_gia_va_su_kien(cau_hinh(), so_su_kien=1)

    def test_su_kien_trung_bi_tu_choi(self):
        published = datetime(2026, 2, 10, 10, tzinfo=VN)
        with self.assertRaisesRegex(ValueError, "Trung su kien"):
            _m3_events(
                [event(published=published, key="k1"), event(published=published, key="k2")],
                "gia_khong_dieu_chinh", oos_start=D_SIGNAL_1, oos_end=D_EXEC_2,
            )


if __name__ == "__main__":
    unittest.main()
