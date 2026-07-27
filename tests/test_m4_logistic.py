from __future__ import annotations
import unittest
import warnings
from datetime import date, datetime, timezone
from types import SimpleNamespace

import numpy as np
from sklearn.exceptions import ConvergenceWarning

from he_thong_dinh_luong.nghien_cuu_moc_4.logistic import du_doan_test, huan_luyen_logistic
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import MauMoHinh
from ho_tro_m4 import cau_hinh

UTC = timezone.utc
NOW = datetime(2026, 1, 30, 14, tzinfo=UTC)
SIGNAL = datetime(2026, 1, 30, 15, tzinfo=UTC)


def sample(day, symbol, x, y):
    return MauMoHinh(day, symbol, (float(x), float(x*x)), y, day, 0.1 if y else -0.1)


class FakePipeline:
    def __init__(self, C, *, warn=False, probabilities=(0.4, 0.6)):
        self.C = C; self.warn = warn; self.probabilities = probabilities
        self.named_steps = {
            "standard_scaler": SimpleNamespace(mean_=np.array([0.0, 0.0]), scale_=np.array([1.0, 1.0])),
            "logistic_regression": SimpleNamespace(coef_=np.array([[1.0, 2.0]]), intercept_=np.array([0.0]), n_iter_=np.array([1])),
        }
    def fit(self, X, y):
        if self.warn:
            warnings.warn("khong hoi tu", ConvergenceWarning)
        return self
    def predict_proba(self, X):
        probs = [self.probabilities[i % len(self.probabilities)] for i in range(len(X))]
        return np.array([[1-p, p] for p in probs])


class TestLogisticM4(unittest.TestCase):
    def setUp(self):
        d1, d2, d3 = date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)
        self.train = [sample(d1, "A", 0, 0), sample(d1, "B", 1, 1), sample(d2, "C", 2, 1), sample(d2, "D", -1, 0)]
        self.validation = [sample(d3, "E", 0.5, 0), sample(d3, "F", 1.5, 1)]
        self.refit = self.train + self.validation
        self.config = cau_hinh(feature_order=["x", "x2"], feature_bat_buoc=["x", "x2"])

    def run_model(self, **kwargs):
        return huan_luyen_logistic(
            fold="fold_001", train=self.train, validation=self.validation, refit=self.refit,
            cau_hinh=self.config, thoi_diem_huan_luyen=NOW, thoi_diem_tao_tin_hieu=SIGNAL,
            cutoff_feature=NOW, cutoff_nhan=NOW, **kwargs,
        )

    def test_pipeline_chay_va_luu_metadata(self):
        result = self.run_model()
        self.assertTrue(result.thanh_cong)
        self.assertIn(result.C, self.config.C_grid)
        self.assertEqual(result.metadata["solver"], "lbfgs")
        self.assertIn("scaler_mean", result.metadata)

    def test_validation_predictions_duoc_ghi_ro(self):
        result = self.run_model()
        self.assertTrue(all(x.vai_tro_du_lieu == "validation" for x in result.validation_predictions))

    def test_du_doan_test_chi_sau_refit_thanh_cong(self):
        result = self.run_model()
        predictions = du_doan_test(result, self.validation)
        self.assertEqual(len(predictions), len(self.validation))
        self.assertTrue(all(x.vai_tro_du_lieu == "test" for x in predictions))

    def test_train_mot_lop_fold_fail(self):
        train = [sample(date(2025,1,31), "A", 0, 1), sample(date(2025,1,31), "B", 1, 1)]
        result = huan_luyen_logistic(
            fold="f", train=train, validation=self.validation, refit=train+self.validation,
            cau_hinh=self.config, thoi_diem_huan_luyen=NOW, thoi_diem_tao_tin_hieu=SIGNAL,
            cutoff_feature=NOW, cutoff_nhan=NOW,
        )
        self.assertFalse(result.thanh_cong)
        self.assertEqual(result.ly_do_that_bai, "train_mot_lop")
        self.assertEqual(du_doan_test(result, self.validation), ())

    def test_refit_mot_lop_fold_fail(self):
        one = [sample(date(2025,1,31), "A", 0, 1), sample(date(2025,1,31), "B", 1, 1)]
        result = huan_luyen_logistic(
            fold="f", train=self.train, validation=self.validation, refit=one,
            cau_hinh=self.config, thoi_diem_huan_luyen=NOW, thoi_diem_tao_tin_hieu=SIGNAL,
            cutoff_feature=NOW, cutoff_nhan=NOW,
        )
        self.assertFalse(result.thanh_cong)
        self.assertEqual(result.ly_do_that_bai, "refit_mot_lop")

    def test_validation_mot_lop_log_loss_van_tinh_auc_null(self):
        val = [sample(date(2025,3,31), "E", 0.5, 1), sample(date(2025,3,31), "F", 1.5, 1)]
        result = huan_luyen_logistic(
            fold="f", train=self.train, validation=val, refit=self.train+val,
            cau_hinh=self.config, thoi_diem_huan_luyen=NOW, thoi_diem_tao_tin_hieu=SIGNAL,
            cutoff_feature=NOW, cutoff_nhan=NOW,
        )
        self.assertTrue(result.thanh_cong)
        self.assertIsNotNone(result.validation_log_loss)
        self.assertIsNone(result.validation_auc)

    def test_convergence_candidate_bi_loai(self):
        def factory(**kwargs):
            return FakePipeline(kwargs["C"], warn=kwargs["C"] == 0.1)
        result = self.run_model(pipeline_factory=factory)
        self.assertTrue(result.thanh_cong)
        self.assertIn("0.1", result.metadata["candidate_errors"])

    def test_tat_ca_candidate_warning_fold_fail(self):
        def factory(**kwargs):
            return FakePipeline(kwargs["C"], warn=True)
        result = self.run_model(pipeline_factory=factory)
        self.assertFalse(result.thanh_cong)
        self.assertEqual(result.ly_do_that_bai, "tat_ca_candidate_khong_hop_le")

    def test_refit_convergence_warning_fold_fail(self):
        calls = {"count": 0}
        def factory(**kwargs):
            calls["count"] += 1
            return FakePipeline(kwargs["C"], warn=calls["count"] == 4)
        result = self.run_model(pipeline_factory=factory)
        self.assertFalse(result.thanh_cong)
        self.assertEqual(result.ly_do_that_bai, "refit_khong_hoi_tu")
        self.assertEqual(du_doan_test(result, self.validation), ())

    def test_tie_chon_c_nho_hon(self):
        def factory(**kwargs):
            return FakePipeline(kwargs["C"], probabilities=(0.5, 0.5))
        result = self.run_model(pipeline_factory=factory)
        self.assertTrue(result.thanh_cong)
        self.assertEqual(result.C, 0.1)

    def test_model_clock_train_sau_signal_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "Model clock"):
            huan_luyen_logistic(
                fold="f", train=self.train, validation=self.validation, refit=self.refit,
                cau_hinh=self.config, thoi_diem_huan_luyen=SIGNAL, thoi_diem_tao_tin_hieu=NOW,
                cutoff_feature=NOW, cutoff_nhan=NOW,
            )

    def test_label_cutoff_sau_train_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "Model clock"):
            huan_luyen_logistic(
                fold="f", train=self.train, validation=self.validation, refit=self.refit,
                cau_hinh=self.config, thoi_diem_huan_luyen=NOW, thoi_diem_tao_tin_hieu=SIGNAL,
                cutoff_feature=NOW, cutoff_nhan=SIGNAL,
            )

    def test_scaler_fit_refit_khong_dung_test(self):
        result1 = self.run_model()
        test_outlier = [sample(date(2025,4,30), "Z", 1_000_000, 1)]
        result2 = self.run_model()
        _ = du_doan_test(result2, test_outlier)
        self.assertEqual(result1.metadata["scaler_mean"], result2.metadata["scaler_mean"])
