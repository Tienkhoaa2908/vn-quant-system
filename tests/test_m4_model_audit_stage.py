from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning

from he_thong_dinh_luong.nghien_cuu_moc_4.logistic import du_doan_test, huan_luyen_logistic
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import FoldWalkForward, MauMoHinh
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import _model_audit_rows, _processed_rows
from ho_tro_m4 import cau_hinh

UTC = timezone.utc
NOW = datetime(2026, 1, 30, 14, tzinfo=UTC)
SIGNAL = datetime(2026, 1, 30, 15, tzinfo=UTC)


def _sample(day: date, symbol: str, x: float, label: int) -> MauMoHinh:
    return MauMoHinh(day, symbol, (x, x * x), label, day, 0.1 if label else -0.1)


class _FakePipeline:
    def __init__(self, C: float, *, warn: bool = False) -> None:
        self.C = C
        self.warn = warn
        self.named_steps = {
            "standard_scaler": SimpleNamespace(
                mean_=np.array([0.0, 0.0]), scale_=np.array([1.0, 1.0]),
                transform=lambda X: np.asarray(X, dtype=float),
            ),
            "logistic_regression": SimpleNamespace(
                coef_=np.array([[1.0, 2.0]]), intercept_=np.array([0.0]),
                n_iter_=np.array([7]),
            ),
        }

    def fit(self, X, y):
        if self.warn:
            warnings.warn("candidate khong hoi tu", ConvergenceWarning)
        return self

    def predict_proba(self, X):
        return np.asarray([[0.4, 0.6] for _ in X])


class TestModelAuditStage(unittest.TestCase):
    def setUp(self) -> None:
        d1, d2, d3, d4 = (date(2025, month, 28) for month in range(1, 5))
        self.train = [
            _sample(d1, "A", 0.0, 0), _sample(d1, "B", 1.0, 1),
            _sample(d2, "C", 2.0, 1), _sample(d2, "D", -1.0, 0),
        ]
        self.validation = [
            _sample(d3, "E", 10.0, 0), _sample(d3, "F", 12.0, 1),
        ]
        self.test = [_sample(d4, "G", 3.0, 1), _sample(d4, "H", 4.0, 0)]
        self.config = cau_hinh(feature_order=["x", "x2"], feature_bat_buoc=["x", "x2"])
        self.fold = FoldWalkForward(
            "fold_001", (d1, d2), (d3,), (d4,), d2, d3, d3, (), (),
        )

    def _train(self, **kwargs):
        return huan_luyen_logistic(
            fold=self.fold.fold, train=self.train, validation=self.validation,
            refit=self.train + self.validation, cau_hinh=self.config,
            thoi_diem_huan_luyen=NOW, thoi_diem_tao_tin_hieu=SIGNAL,
            cutoff_feature=NOW, cutoff_nhan=NOW, **kwargs,
        )

    def test_scaler_selection_khac_scaler_refit(self) -> None:
        result = self._train()
        self.assertNotEqual(
            result.metadata["validation_selection"]["scaler_mean"],
            result.metadata["final_refit"]["scaler_mean"],
        )

    def test_validation_processed_khop_scaler_selection(self) -> None:
        result = self._train()
        rows = _processed_rows(self.fold, {
            "train": self.train, "validation": self.validation,
            "refit_train_validation": self.train + self.validation, "test": self.test,
        }, result, ("x", "x2"))
        row = next(item for item in rows if item["vai_tro_du_lieu"] == "validation")
        expected = result.selection_pipeline.named_steps["standard_scaler"].transform(
            [self.validation[0].feature]
        )[0]
        self.assertEqual(row["stage"], "validation_selection")
        self.assertEqual(row["model_id"], result.selection_model_id)
        self.assertAlmostEqual(row["x"], expected[0])
        self.assertAlmostEqual(row["x2"], expected[1])

    def test_test_processed_khop_scaler_final_refit(self) -> None:
        result = self._train()
        rows = _processed_rows(self.fold, {
            "train": self.train, "validation": self.validation,
            "refit_train_validation": self.train + self.validation, "test": self.test,
        }, result, ("x", "x2"))
        row = next(item for item in rows if item["vai_tro_du_lieu"] == "test")
        expected = result.pipeline.named_steps["standard_scaler"].transform(
            [self.test[0].feature]
        )[0]
        self.assertEqual(row["stage"], "final_refit")
        self.assertEqual(row["model_id"], result.refit_model_id)
        self.assertAlmostEqual(row["x"], expected[0])
        self.assertAlmostEqual(row["x2"], expected[1])

    def test_model_id_va_stage_khong_nhap_nhang(self) -> None:
        result = self._train()
        self.assertNotEqual(result.selection_model_id, result.refit_model_id)
        self.assertTrue(all(x.model_id == result.selection_model_id for x in result.validation_predictions))
        self.assertTrue(all(x.model_id == result.refit_model_id for x in du_doan_test(result, self.test)))
        rows = _model_audit_rows(fold=self.fold, training=result)
        self.assertEqual({x["stage"] for x in rows}, {"validation_selection", "final_refit"})

    def test_n_iter_va_convergence_duoc_cong_bo(self) -> None:
        result = self._train()
        rows = _model_audit_rows(fold=self.fold, training=result)
        for row in rows:
            self.assertNotEqual(row["n_iter"], "[]")
            self.assertTrue(row["converged"])
            self.assertEqual(row["convergence_warning"], "[]")

    def test_candidate_warning_duoc_truy_vet(self) -> None:
        def factory(**kwargs):
            return _FakePipeline(kwargs["C"], warn=kwargs["C"] == 0.1)
        result = self._train(pipeline_factory=factory)
        rows = _model_audit_rows(fold=self.fold, training=result)
        self.assertTrue(all("0.1" in row["candidate_errors"] for row in rows))
        self.assertIn("ConvergenceWarning", rows[0]["candidate_errors"])


if __name__ == "__main__":
    unittest.main()
