from __future__ import annotations
import unittest
from datetime import date

from he_thong_dinh_luong.nghien_cuu_moc_4.chi_so import calibration_equal_width, decile_spread, metric_model_test, metric_ranking_test, spearman_rank_ic
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import DongXepHang, DuDoan
from he_thong_dinh_luong.nghien_cuu_moc_4.xep_hang import xep_hang_test

D1 = date(2026, 1, 30)
D2 = date(2026, 2, 27)


def pred(day, symbol, p, label=None, ret=None, fold="f1"):
    return DuDoan(fold, fold+"_m", "test", day, symbol, p, label, ret)


class TestRankingMetricM4(unittest.TestCase):
    def test_probability_giam_tie_break_ma_tang(self):
        rankings, _ = xep_hang_test([pred(D1,"BBB",0.8), pred(D1,"AAA",0.8), pred(D1,"CCC",0.2)], top_k=2)
        self.assertEqual([x.ma for x in rankings], ["AAA","BBB","CCC"])

    def test_top_k_va_tien_mat(self):
        rankings, cash = xep_hang_test([pred(D1,"AAA",0.8), pred(D1,"BBB",0.7)], top_k=3)
        self.assertTrue(all(x.ty_trong_muc_tieu == 1/3 for x in rankings))
        self.assertAlmostEqual(cash[D1], 1/3)

    def test_validation_prediction_khong_duoc_ranking_cuoi(self):
        row = DuDoan("f","m","validation",D1,"AAA",0.5)
        with self.assertRaisesRegex(ValueError, "chi nhan prediction test"):
            xep_hang_test([row], top_k=1)

    def test_metric_model_chi_test(self):
        with self.assertRaisesRegex(ValueError, "chi nhan prediction test"):
            metric_model_test([DuDoan("f","m","validation",D1,"AAA",0.5,1,0.1)])

    def test_metric_model_tinh_tay(self):
        report = metric_model_test([pred(D1,"A",0.8,1,0.1), pred(D1,"B",0.2,0,-0.1)])
        self.assertAlmostEqual(report["brier"], 0.04)
        self.assertAlmostEqual(report["auc"], 1.0)

    def test_auc_null_mot_lop(self):
        report = metric_model_test([pred(D1,"A",0.8,1,0.1), pred(D1,"B",0.6,1,0.2)])
        self.assertIsNone(report["auc"])
        self.assertIsNotNone(report["log_loss"])

    def test_calibration_10_bin_equal_width_bo_bin_rong(self):
        bins = calibration_equal_width([pred(D1,"A",0.0,0,-.1), pred(D1,"B",1.0,1,.1)])
        self.assertEqual([x["bin"] for x in bins], [0,9])

    def test_precision_hit_average_return_tinh_tay(self):
        rankings, _ = xep_hang_test([
            pred(D1,"A",.9,1,.2), pred(D1,"B",.8,0,-.1), pred(D1,"C",.1,1,.3)
        ], top_k=2)
        report = metric_ranking_test(rankings)["theo_ngay"][0]
        self.assertAlmostEqual(report["precision_at_k"], .5)
        self.assertEqual(report["hit_rate_top_k"], 1.0)
        self.assertAlmostEqual(report["loi_nhuan_tuong_doi_trung_binh_top_k"], .05)

    def test_average_return_top_k_null_neu_thieu_nhan(self):
        rankings, _ = xep_hang_test([pred(D1,"A",.9,1,.2), pred(D1,"B",.8,None,None)], top_k=2)
        report = metric_ranking_test(rankings)["theo_ngay"][0]
        self.assertIsNone(report["loi_nhuan_tuong_doi_trung_binh_top_k"])
        self.assertIsNone(report["precision_at_k"])

    def test_set_turnover(self):
        rankings, _ = xep_hang_test([
            pred(D1,"A",.9,1,.1), pred(D1,"B",.8,0,-.1),
            pred(D2,"B",.9,1,.2,fold="f2"), pred(D2,"C",.8,0,-.2,fold="f2"),
        ], top_k=2)
        daily = metric_ranking_test(rankings)["theo_ngay"]
        self.assertIsNone(daily[0]["set_turnover"])
        self.assertAlmostEqual(daily[1]["set_turnover"], .5)

    def test_spearman_average_rank_ties(self):
        value = spearman_rank_ic([1,1,2],[1,1,2])
        self.assertAlmostEqual(value, 1.0)

    def test_spearman_null_duoi_ba_hoac_zero_variance(self):
        self.assertIsNone(spearman_rank_ic([1,2],[1,2]))
        self.assertIsNone(spearman_rank_ic([1,1,1],[1,2,3]))

    def test_decile_spread_toi_thieu_10(self):
        rows = [DongXepHang("f","m",D1,f"S{i:02d}",1-i/20,i+1,False,0,None,float(10-i)) for i in range(10)]
        self.assertEqual(decile_spread(rows), 9.0)
        self.assertIsNone(decile_spread(rows[:9]))

    def test_decile_chia_khong_deu(self):
        rows = [DongXepHang("f","m",D1,f"S{i:02d}",1-i/30,i+1,False,0,None,float(13-i)) for i in range(13)]
        self.assertIsNotNone(decile_spread(rows))

    def test_aggregate_truc_tiep_theo_ngay_khong_mean_fold(self):
        predictions = [
            pred(D1,"A",.9,1,.2), pred(D1,"B",.8,1,.1),
            pred(D2,"C",.9,0,-.2,fold="f2"), pred(D2,"D",.8,0,-.1,fold="f2"),
        ]
        rankings, _ = xep_hang_test(predictions, top_k=2)
        overall = metric_ranking_test(rankings)["tong_the"]
        self.assertAlmostEqual(overall["precision_at_k"], .5)
