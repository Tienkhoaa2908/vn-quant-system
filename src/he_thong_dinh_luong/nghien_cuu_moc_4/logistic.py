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


def _fit_khong_warning(pipeline: object, X: object, y: object) -> tuple[bool, tuple[str, ...]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        pipeline.fit(X, y)
    convergence = tuple(str(w.message) for w in caught if issubclass(w.category, ConvergenceWarning))
    return not convergence, convergence


def _audit_pipeline(pipeline: object, *, stage: str, model_id: str, C: float) -> dict[str, object]:
    scaler = pipeline.named_steps["standard_scaler"]
    model = pipeline.named_steps["logistic_regression"]
    return {
        "stage": stage,
        "model_id": model_id,
        "C": C,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficients": model.coef_[0].tolist(),
        "intercept": model.intercept_.tolist(),
        "n_iter": model.n_iter_.tolist(),
        "converged": True,
        "convergence_warning": [],
    }


def _failure(
    *, fold: str, model_id: str, selection_model_id: str, refit_model_id: str,
    C: float | None, validation_predictions: tuple[DuDoan, ...],
    validation_log_loss: float | None, validation_auc: float | None,
    reason: str, metadata: dict[str, object], selection_pipeline: object | None = None,
) -> KetQuaHuanLuyen:
    return KetQuaHuanLuyen(
        fold, model_id, C, None, validation_predictions, validation_log_loss,
        validation_auc, False, reason, metadata,
        selection_model_id=selection_model_id, refit_model_id=refit_model_id,
        selection_pipeline=selection_pipeline,
    )


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

    selection_model_id = f"{fold}_logistic_selection"
    refit_model_id = f"{fold}_logistic_refit"
    metadata: dict[str, object] = {
        "fold": fold,
        "selection_model_id": selection_model_id,
        "refit_model_id": refit_model_id,
        "thoi_diem_huan_luyen": trained_at.isoformat(),
        "thoi_diem_tao_tin_hieu": signal_at.isoformat(),
        "cutoff_feature": feature_cutoff.isoformat(),
        "cutoff_nhan": label_cutoff.isoformat(),
        "cutoff_train": label_cutoff.isoformat(),
        "cutoff_validation": label_cutoff.isoformat(),
        "cutoff_test": signal_at.isoformat(),
        "scikit_learn": sklearn.__version__,
        "feature_order": list(cau_hinh.feature_order),
        "solver": cau_hinh.solver,
        "max_iter": cau_hinh.max_iter,
        "class_weight": cau_hinh.class_weight,
        "seed": cau_hinh.seed,
        "candidate_errors": {},
    }
    if len({x.nhan for x in train}) < 2:
        return _failure(
            fold=fold, model_id=selection_model_id, selection_model_id=selection_model_id,
            refit_model_id=refit_model_id, C=None, validation_predictions=(),
            validation_log_loss=None, validation_auc=None, reason="train_mot_lop", metadata=metadata,
        )
    if not validation:
        return _failure(
            fold=fold, model_id=selection_model_id, selection_model_id=selection_model_id,
            refit_model_id=refit_model_id, C=None, validation_predictions=(),
            validation_log_loss=None, validation_auc=None, reason="validation_rong", metadata=metadata,
        )

    X_train, y_train = _xy(train)
    X_val, y_val = _xy(validation)
    candidates: list[tuple[float, float, object, tuple[DuDoan, ...], float | None]] = []
    candidate_errors: dict[str, str] = {}
    for C in sorted(cau_hinh.C_grid):
        pipeline = pipeline_factory(
            C=C, solver=cau_hinh.solver, max_iter=cau_hinh.max_iter,
            class_weight=None, seed=cau_hinh.seed,
        )
        ok, warning_texts = _fit_khong_warning(pipeline, X_train, y_train)
        if not ok:
            candidate_errors[str(C)] = "ConvergenceWarning: " + " | ".join(warning_texts)
            continue
        probabilities = [float(x) for x in pipeline.predict_proba(X_val)[:, 1]]
        loss = float(log_loss(y_val, probabilities, labels=[0, 1]))
        auc = float(roc_auc_score(y_val, probabilities)) if len(set(y_val)) == 2 else None
        predictions = tuple(DuDoan(
            fold=fold, model_id=selection_model_id, vai_tro_du_lieu="validation",
            ngay=s.ngay, ma=s.ma, xac_suat_nhan_1=p, nhan=s.nhan,
            loi_nhuan_tuong_doi=s.loi_nhuan_tuong_doi,
        ) for s, p in zip(validation, probabilities, strict=True))
        candidates.append((loss, C, pipeline, predictions, auc))
    metadata["candidate_errors"] = candidate_errors
    if not candidates:
        return _failure(
            fold=fold, model_id=selection_model_id, selection_model_id=selection_model_id,
            refit_model_id=refit_model_id, C=None, validation_predictions=(),
            validation_log_loss=None, validation_auc=None,
            reason="tat_ca_candidate_khong_hop_le", metadata=metadata,
        )

    candidates.sort(key=lambda x: (x[0], x[1]))
    best_loss = candidates[0][0]
    tied = [x for x in candidates if isclose(x[0], best_loss, abs_tol=1e-12, rel_tol=0.0)]
    _, selected_c, selection_pipeline, validation_predictions, validation_auc = min(tied, key=lambda x: x[1])
    selection_audit = _audit_pipeline(
        selection_pipeline, stage="validation_selection", model_id=selection_model_id, C=selected_c,
    )
    metadata["validation_selection"] = selection_audit

    if len({x.nhan for x in refit}) < 2:
        return _failure(
            fold=fold, model_id=refit_model_id, selection_model_id=selection_model_id,
            refit_model_id=refit_model_id, C=selected_c,
            validation_predictions=validation_predictions, validation_log_loss=best_loss,
            validation_auc=validation_auc, reason="refit_mot_lop", metadata=metadata,
            selection_pipeline=selection_pipeline,
        )

    final_pipeline = pipeline_factory(
        C=selected_c, solver=cau_hinh.solver, max_iter=cau_hinh.max_iter,
        class_weight=None, seed=cau_hinh.seed,
    )
    X_refit, y_refit = _xy(refit)
    ok, warning_texts = _fit_khong_warning(final_pipeline, X_refit, y_refit)
    if not ok:
        metadata["final_refit"] = {
            "stage": "final_refit", "model_id": refit_model_id, "C": selected_c,
            "converged": False, "convergence_warning": list(warning_texts),
        }
        metadata["refit_warning"] = " | ".join(warning_texts)
        return _failure(
            fold=fold, model_id=refit_model_id, selection_model_id=selection_model_id,
            refit_model_id=refit_model_id, C=selected_c,
            validation_predictions=validation_predictions, validation_log_loss=best_loss,
            validation_auc=validation_auc, reason="refit_khong_hoi_tu", metadata=metadata,
            selection_pipeline=selection_pipeline,
        )

    final_audit = _audit_pipeline(
        final_pipeline, stage="final_refit", model_id=refit_model_id, C=selected_c,
    )
    metadata["final_refit"] = final_audit
    # Khoa cu duoc giu de khong pha nguoi dung hien tai; day la scaler/model final_refit.
    metadata.update({
        "C": selected_c,
        "scaler_mean": final_audit["scaler_mean"],
        "scaler_scale": final_audit["scaler_scale"],
        "coefficients": final_audit["coefficients"],
        "intercept": final_audit["intercept"],
        "n_iter": final_audit["n_iter"],
        "converged": True,
    })
    return KetQuaHuanLuyen(
        fold, refit_model_id, selected_c, final_pipeline, validation_predictions,
        best_loss, validation_auc, True, None, metadata,
        selection_model_id=selection_model_id, refit_model_id=refit_model_id,
        selection_pipeline=selection_pipeline,
    )


def du_doan_test(result: KetQuaHuanLuyen, samples: Sequence[MauMoHinh]) -> tuple[DuDoan, ...]:
    if not result.thanh_cong or result.pipeline is None or not samples:
        return ()
    probabilities = result.pipeline.predict_proba([x.feature for x in samples])[:, 1]
    model_id = result.refit_model_id or result.model_id
    return tuple(DuDoan(
        fold=result.fold, model_id=model_id, vai_tro_du_lieu="test", ngay=s.ngay, ma=s.ma,
        xac_suat_nhan_1=float(p), nhan=s.nhan, loi_nhuan_tuong_doi=s.loi_nhuan_tuong_doi,
    ) for s, p in zip(samples, probabilities, strict=True))
