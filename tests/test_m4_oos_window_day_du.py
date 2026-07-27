from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.adapter_mo_phong import (
    chay_backtest_oos_lien_tuc,
    metric_backtest_oos,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import DongXepHang
from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong, thanh_gia

SIGNAL = date(2026, 1, 30)
EXEC = date(2026, 2, 2)
END = date(2026, 2, 6)


def cfg():
    return cau_hinh_mo_phong(
        Decimal("100000"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        1, 252, Decimal("0"), "muc_tieu_bang_0", True,
        "khong_dieu_chinh", "dong", "dong",
    )


def rank():
    return DongXepHang("f1", "f1_logistic_refit", SIGNAL, "AAA", 0.9, 1, True, 1.0, 1, 0.1)


def bar(day: date, price: int):
    return thanh_gia("AAA", day, Decimal(price), Decimal(price), 1000, True, True)


def core_prices():
    return [
        bar(SIGNAL, 10), bar(EXEC, 11), bar(date(2026, 2, 3), 12),
        bar(date(2026, 2, 4), 13), bar(date(2026, 2, 5), 14), bar(END, 15),
    ]


def run(prices):
    result = chay_backtest_oos_lien_tuc(
        rankings=[rank()], du_lieu_gia=prices, cau_hinh_mo_phong=cfg(),
        ngay_tai_can_bang=[SIGNAL], cac_ma_lien_quan=["AAA"],
        oos_start=SIGNAL, oos_end=END,
    )
    metrics = metric_backtest_oos(
        result, oos_start=SIGNAL, metric_start=EXEC, oos_end=END,
    )
    return result, metrics


class TestOOSWindowDayDuM4(unittest.TestCase):
    def test_them_500_phien_truoc_oos_khong_doi_metric(self):
        prior = [bar(SIGNAL - timedelta(days=500 - i), 5 + i % 3) for i in range(500)]
        base_result, base_metrics = run(core_prices())
        extra_result, extra_metrics = run([*prior, *core_prices()])
        self.assertEqual(base_metrics, extra_metrics)
        self.assertEqual(base_result.nav, extra_result.nav)

    def test_them_du_lieu_sau_oos_end_khong_doi_metric(self):
        future = [bar(END + timedelta(days=i), 100 + i) for i in range(1, 20)]
        base_result, base_metrics = run(core_prices())
        extra_result, extra_metrics = run([*core_prices(), *future])
        self.assertEqual(base_metrics, extra_metrics)
        self.assertEqual(base_result.nav, extra_result.nav)

    def test_cung_prediction_target_cho_cung_nav_va_metric(self):
        first_result, first_metrics = run(core_prices())
        second_result, second_metrics = run(list(core_prices()))
        self.assertEqual(first_result.nav, second_result.nav)
        self.assertEqual(first_metrics, second_metrics)

    def test_phien_warm_up_khong_thanh_phien_danh_gia(self):
        prior = [bar(SIGNAL - timedelta(days=10), 1)]
        result, metrics = run([*prior, *core_prices()])
        self.assertEqual(result.nav[0].ngay, SIGNAL)
        self.assertEqual(metrics["ngay_bat_dau_metric"], EXEC.isoformat())
        self.assertEqual(metrics["so_phien"], 5)
        self.assertNotEqual(metrics["ngay_bat_dau_metric"], prior[0].ngay.isoformat())


if __name__ == "__main__":
    unittest.main()
