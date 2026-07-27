from __future__ import annotations
import unittest
from datetime import date

from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import DuDoan, MauMoHinh
from he_thong_dinh_luong.nghien_cuu_moc_4.walk_forward import loc_mau_theo_fold, tao_folds, xac_thuc_prediction_test
from ho_tro_m4 import cau_hinh, weekdays


class TestWalkForwardM4(unittest.TestCase):
    def setUp(self):
        self.calendar = weekdays(date(2023, 1, 2), 900)
        self.config = cau_hinh(so_thang_train_toi_thieu=3, so_thang_validation=1, embargo_phien=2)
        self.folds = tao_folds(self.calendar, self.config)

    def test_co_fold(self):
        self.assertTrue(self.folds)

    def test_moi_test_dung_mot_thang(self):
        self.assertTrue(all(len(f.test_dates) == 1 for f in self.folds))

    def test_test_khong_chong_lan(self):
        dates = [f.test_dates[0] for f in self.folds]
        self.assertEqual(len(dates), len(set(dates)))

    def test_expanding_train(self):
        sizes = [len(f.train_dates) for f in self.folds]
        self.assertEqual(sizes, sorted(sizes))

    def test_purge_du_horizon(self):
        self.assertTrue(all(len(f.purge_dates) >= 20 for f in self.folds))

    def test_embargo_duoc_ap_dung(self):
        self.assertTrue(all(len(f.embargo_dates) == 2 for f in self.folds))

    def test_monthly_samples_only(self):
        for fold in self.folds:
            for day in fold.train_dates + fold.validation_dates + fold.test_dates:
                later_same_month = [x for x in self.calendar if x.year == day.year and x.month == day.month and x > day]
                self.assertFalse(later_same_month)

    def test_cutoff_nhan_train_validation_refit(self):
        fold = self.folds[0]
        d_train = fold.train_dates[-1]
        d_val = fold.validation_dates[0]
        d_test = fold.test_dates[0]
        samples = [
            MauMoHinh(d_train, "AAA", (1.0,), 1, fold.cutoff_train, 0.1),
            MauMoHinh(d_train, "BAD", (1.0,), 1, d_test, 0.1),
            MauMoHinh(d_val, "BBB", (1.0,), 0, fold.cutoff_validation, -0.1),
            MauMoHinh(d_test, "CCC", (1.0,), 1, d_test, 0.1),
        ]
        selected = loc_mau_theo_fold(samples, fold)
        self.assertEqual([x.ma for x in selected["train"]], ["AAA"])
        self.assertEqual([x.ma for x in selected["validation"]], ["BBB"])
        self.assertEqual([x.ma for x in selected["test"]], ["CCC"])

    def test_prediction_test_duplicate_bi_tu_choi(self):
        day = self.folds[0].test_dates[0]
        row = DuDoan("f1", "m1", "test", day, "AAA", 0.5)
        with self.assertRaisesRegex(ValueError, "Trung khoa"):
            xac_thuc_prediction_test([row, row])

    def test_prediction_test_fold_overlap_bi_tu_choi(self):
        day = self.folds[0].test_dates[0]
        rows = [
            DuDoan("f1", "m1", "test", day, "AAA", 0.5),
            DuDoan("f2", "m2", "test", day, "BBB", 0.4),
        ]
        with self.assertRaisesRegex(ValueError, "chong lan"):
            xac_thuc_prediction_test(rows)
