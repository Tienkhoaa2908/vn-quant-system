"""Chon C tren validation va refit Logistic Regression theo hop dong fail closed."""
from __future__ import annotations

from datetime import datetime
from math import isclose
import warnings
from typing import Callable, Sequence

import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import log_loss, roc_auc_score

from .mo_hinh import CauHinhMoc4, DuDoan, KetQuaHuanLuyen, MauMoHinh, xac_thuc_timestamp
from .tien_xu_ly import tao_pipeline

PipelineFactory = Callable[..., object]


def _xy(samples: Sequence[MauMoHinh]) -> tuple[list[tuple[float, ...]], list[int]]:
    return [x.feature for x in samples], [x.nhan for x in samples]


def _fit_khong_warning(pipeline: object, X: object, y: object) -> tuple[bool, str | None]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        pipeline.fit(X, y)
    convergence = [w for w in caught if issubclass(w.category, ConvergenceWarning)]
    if convergence:
        return False, str(convergence[0].message)
    return True, None


def huan_luyen_logistic(
    *,
    fold: str,
    train: Sequence[MauMoHinh],
    validation: Sequence[MauMoHinh],
    refit: Sequence[MauMoHinh],
    cau_hinh: CauHinhMoc4,
    thoi_diem_huan_luyen: datetime,
    thoi_diem_tao_tin_hieu: datetime,
    cutoff_feature: datetime,
    cutoff_nhan: datetime,
    pipeline_factory: PipelineFactory = tao_pipeline,
) -> KetQuaHuanLuyen:
    trained_at = xac_thuc_timestamp(thoi_diem_huan_luyen, "thoi_diem_huan_luyen")
    signal_at = xac_thuc_timestamp(thoi_diem_tao_tin_hieu, "thoi_diem_tao_tin_hieu")
    feature_cutoff = xac_thuc_timestamp(cutoff_feature, "cutoff_feature")
    label_cutoff = xac_thuc_timestamp(cutoff_nhan, "cutoff_nhan")
    if trained_at > signal_at or feature_cutoff > signal_at or label_cutoff > trained_at:
        raise ValueError("Model clock vi pham cutoff.")
    model_id = f"{fold}_logistic"
    metadata = {
        "fold": fold, "model_id": model_id, "thoi_diem_huan_luyen": trained_at.isoformat(),
        "thoi_diem_tao_tin_hieu": signal_at.isoformat(), "cutoff_feature": feature_cutoff.isoformat(),
        "cutoff_nhan": label_cutoff.isoformat(), "scikit_learn": sklearn.__version__,
        "feature_order": list(cau_hinh.feature_order), "solver": cau_hinh.solver,
        "max_iter": cau_hinh.max_iter, "class_weight": cau_hinh.class_weight,
        "seed": cau_hinh.seed,
    }
    if len({x.nhan for x in train}) < 2:
        return KetQuaHuanLuyen(fold, model_id, None, None, (), None, None, False, "train_mot_lop", metadata)
    if not validation:
        return KetQuaHuanLuyen(fold, model_id, None, None, (), None, None, False, "validation_rong", metadata)
    X_train, y_train = _xy(train)
    X_val, y_val = _xy(validation)
    candidates: list[tuple[float, float, object, tuple[DuDoan, ...], float | None]] = []
    candidate_errors: dict[str, str] = {}
    for C in sorted(cau_hinh.C_grid):
        pipeline = pipeline_factory(C=C, solver=cau_hinh.solver, max_iter=cau_hinh.max_iter, class_weight=None, seed=cau_hinh.seed)
        ok, warning_text = _fit_khong_warning(pipeline, X_train, y_train)
        if not ok:
            candidate_errors[str(C)] = f"ConvergenceWarning: {warning_text}"
            continue
        probabilities = [float(x) for x in pipeline.predict_proba(X_val)[:, 1]]
        loss = float(log_loss(y_val, probabilities, labels=[0, 1]))
        auc = float(roc_auc_score(y_val, probabilities)) if len(set(y_val)) == 2 else None
        predictions = tuple(DuDoan(
            fold=fold, model_id=model_id, vai_tro_du_lieu="validation", ngay=s.ngay, ma=s.ma,
            xac_suat_nhan_1=p, nhan=s.nhan, loi_nhuan_tuong_doi=s.loi_nhuan_tuong_doi,
        ) for s, p in zip(validation, probabilities, strict=True))
        candidates.append((loss, C, pipeline, predictions, auc))
    metadata["candidate_errors"] = candidate_errors
    if not candidates:
        return KetQuaHuanLuyen(fold, model_id, None, None, (), None, None, False, "tat_ca_candidate_khong_hop_le", metadata)
    candidates.sort(key=lambda x: (x[0], x[1]))
    best_loss = candidates[0][0]
    tied = [x for x in candidates if isclose(x[0], best_loss, abs_tol=1e-12, rel_tol=0.0)]
    _, selected_c, _, validation_predictions, validation_auc = min(tied, key=lambda x: x[1])
    if len({x.nhan for x in refit}) < 2:
        return KetQuaHuanLuyen(fold, model_id, selected_c, None, validation_predictions, best_loss, validation_auc, False, "refit_mot_lop", metadata)
    final_pipeline = pipeline_factory(C=selected_c, solver=cau_hinh.solver, max_iter=cau_hinh.max_iter, class_weight=None, seed=cau_hinh.seed)
    X_refit, y_refit = _xy(refit)
    ok, warning_text = _fit_khong_warning(final_pipeline, X_refit, y_refit)
    if not ok:
        metadata["refit_warning"] = warning_text
        return KetQuaHuanLuyen(fold, model_id, selected_c, None, validation_predictions, best_loss, validation_auc, False, "refit_khong_hoi_tu", metadata)
    scaler = final_pipeline.named_steps["standard_scaler"]
    model = final_pipeline.named_steps["logistic_regression"]
    metadata.update({
        "C": selected_c,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficients": model.coef_[0].tolist(),
        "intercept": model.intercept_.tolist(),
        "n_iter": model.n_iter_.tolist(),
        "converged": True,
    })
    return KetQuaHuanLuyen(fold, model_id, selected_c, final_pipeline, validation_predictions, best_loss, validation_auc, True, None, metadata)


def du_doan_test(result: KetQuaHuanLuyen, samples: Sequence[MauMoHinh]) -> tuple[DuDoan, ...]:
    if not result.thanh_cong or result.pipeline is None:
        return ()
    probabilities = result.pipeline.predict_proba([x.feature for x in samples])[:, 1]
    return tuple(DuDoan(
        fold=result.fold, model_id=result.model_id, vai_tro_du_lieu="test", ngay=s.ngay, ma=s.ma,
        xac_suat_nhan_1=float(p), nhan=s.nhan, loi_nhuan_tuong_doi=s.loi_nhuan_tuong_doi,
    ) for s, p in zip(samples, probabilities, strict=True))
