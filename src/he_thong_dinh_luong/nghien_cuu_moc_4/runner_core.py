"""Xu ly fold, OOS, coverage va san pham trung gian cho runner Moc 4."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import StringIO
import json
from math import isfinite
from pathlib import Path
import platform
import subprocess
from typing import Iterable, Mapping, Sequence

import sklearn

from .adapter_mo_phong import chay_backtest_oos_lien_tuc, chuyen_ty_trong_test, metric_backtest_oos
from .baseline import du_doan_baseline_test, metric_baseline_test, xep_hang_baseline_test
from .chi_so import metric_model_test, metric_ranking_test
from .cong_bo import (
    TEN_SAN_PHAM,
    cong_bo_san_pham,
    tao_csv_du_doan,
    tao_csv_feature_sau_tien_xu_ly,
)
from .dac_trung import FEATURE_ORDER_MAC_DINH, phien_cuoi_thang, tao_feature_cuoi_thang
from .do_phu import DongLoai, bao_cao_do_phu
from .eligibility import danh_gia_eligibility, phien_t1_chinh_thuc
from .logistic import du_doan_test, huan_luyen_logistic
from .mo_hinh import (
    BanGhiPointInTime,
    BanGhiUniverse,
    CauHinhMoc4,
    DongFeature,
    DongNhan,
    DongXepHang,
    DuDoan,
    FoldWalkForward,
    MauMoHinh,
    ThanhOHLCV,
    xac_thuc_co_so_gia_va_su_kien,
)
from .nhan import tao_nhan
from .phong_ve import xac_thuc_cau_truc_huu_han, xac_thuc_so_huu_han
from .universe import chon_ban_ghi_pit, xac_dinh_universe
from .walk_forward import loc_mau_theo_fold, tao_folds, xac_thuc_prediction_test
from .xep_hang import xep_hang_test

UTC = timezone.utc
MUI_GIO_VIET_NAM = timezone(timedelta(hours=7))
GIO_TAO_TIN_HIEU = time(15, 0)



from .runner_io import (
    _DocOHLCV, _DocPIT, _read_csv, _parse_date, _parse_datetime, _parse_bool, _parse_float, _parse_int, _unique, _doc_ohlcv, _xac_thuc_benchmark_identity, _doc_calendar, _doc_universe, _doc_pit, _signal_time, _json_ready, _json_text, _csv_text,
)

def _samples(
    features: Sequence[DongFeature],
    labels: Sequence[DongNhan],
    eligible: set[tuple[date, str]],
    feature_order: Sequence[str],
) -> tuple[list[MauMoHinh], dict[tuple[date, str], float]]:
    label_map = {(row.ngay, row.ma): row for row in labels}
    result: list[MauMoHinh] = []
    momentum: dict[tuple[date, str], float] = {}
    for row in features:
        key = (row.ngay, row.ma)
        value = row.gia_tri.get("dong_luong_12_1")
        if value is not None and not isinstance(value, bool):
            momentum[key] = xac_thuc_so_huu_han(value, "dong_luong_12_1")
        label = label_map.get(key)
        if key not in eligible or not row.hop_le or label is None or label.nhan is None:
            continue
        if label.ngay_ket_thuc_nhan is None or label.loi_nhuan_tuong_doi is None:
            continue
        vector: list[float] = []
        for name in feature_order:
            raw = row.gia_tri.get(name)
            if isinstance(raw, bool):
                vector.append(float(raw))
            elif raw is not None:
                vector.append(xac_thuc_so_huu_han(raw, f"feature.{name}"))
            else:
                raise ValueError(f"Feature bat buoc {name} bi rong trong dong hop_le.")
        result.append(MauMoHinh(
            ngay=row.ngay, ma=row.ma, feature=tuple(vector), nhan=label.nhan,
            ngay_ket_thuc_nhan=label.ngay_ket_thuc_nhan,
            loi_nhuan_tuong_doi=label.loi_nhuan_tuong_doi,
        ))
    return sorted(result, key=lambda x: (x.ngay, x.ma)), momentum


def _m3_price_rows(
    rows: Sequence[ThanhOHLCV],
    *,
    eligible: set[tuple[date, str]] | None = None,
) -> list[object]:
    from he_thong_dinh_luong.mo_phong.mo_hinh import thanh_gia
    eligibility = eligible or set()
    return [thanh_gia(
        ma=row.ma, ngay=row.ngay, gia_mo_cua=Decimal(str(row.gia_mo_cua)),
        gia_dong_cua=Decimal(str(row.gia_dong_cua)), khoi_luong=row.khoi_luong,
        thuoc_tap_co_phieu=(row.ngay, row.ma) in eligibility,
        dat_thanh_khoan=(row.ngay, row.ma) in eligibility,
    ) for row in sorted(rows, key=lambda x: (x.ngay, x.ma))]


def _m3_config(data: Mapping[str, object], basis: str) -> object:
    from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong
    mapping = dict(data)
    mapping["co_so_gia"] = "dieu_chinh" if basis == "gia_dieu_chinh" else "khong_dieu_chinh"
    if mapping.get("che_do_ma_khong_xuat_hien") != "muc_tieu_bang_0":
        raise ValueError("Backtest Moc 4 bat buoc che_do_ma_khong_xuat_hien=muc_tieu_bang_0.")
    return cau_hinh_mo_phong.tu_mapping(mapping)


def _m3_events(
    records: Sequence[BanGhiPointInTime],
    basis: str,
    *,
    oos_start: date,
    oos_end: date,
) -> list[object]:
    """Chon CA theo publication/effective window, khong phu thuoc ngay tai can bang."""
    accepted: list[Mapping[str, object]] = []
    seen_business_keys: set[tuple[object, ...]] = set()
    for record in records:
        if record.loai_du_lieu != "corporate_action":
            continue
        if not (oos_start <= record.ngay_hieu_luc <= oos_end):
            continue
        # Engine ap dung su kien tu dau ngay hieu luc, nen cutoff fail-closed la 00:00 local.
        cutoff = datetime.combine(record.ngay_hieu_luc, time.min, tzinfo=MUI_GIO_VIET_NAM)
        if record.thoi_diem_cong_bo > cutoff:
            raise ValueError(
                f"Corporate action {record.khoa_ban_ghi} cong bo sau cutoff ngay hieu luc; "
                "khong duoc ap dung hoi to."
            )
        payload = dict(record.du_lieu)
        for optional_key in ("ngay_thanh_toan", "ty_le", "gia_tri_tien_mat"):
            if payload.get(optional_key) is None:
                payload[optional_key] = ""
        payload_effective = _parse_date(payload.get("ngay_hieu_luc"), "corporate_action.ngay_hieu_luc")
        if payload_effective != record.ngay_hieu_luc:
            raise ValueError("Corporate action metadata va payload khong khop ngay_hieu_luc.")
        business_key = (
            payload.get("ma"), payload.get("loai_su_kien"), payload.get("ngay_hieu_luc"),
            payload.get("ngay_thanh_toan"), payload.get("ty_le"),
            payload.get("gia_tri_tien_mat"), payload.get("nguon"), payload.get("phien_ban"),
        )
        if business_key in seen_business_keys:
            raise ValueError("Trung su kien doanh nghiep.")
        seen_business_keys.add(business_key)
        accepted.append(payload)
    if not accepted:
        return []
    from he_thong_dinh_luong.mo_phong.mo_hinh import chuan_hoa_su_kien
    return chuan_hoa_su_kien(
        accepted, co_so_gia="dieu_chinh" if basis == "gia_dieu_chinh" else "khong_dieu_chinh"
    )


def _uv_version() -> str:
    try:
        completed = subprocess.run(["uv", "--version"], check=True, capture_output=True, text=True, timeout=10)
        value = completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        value = "khong_xac_dinh"
    return value or "khong_xac_dinh"


def _backtest_metrics(result: object) -> dict[str, object]:
    from he_thong_dinh_luong.mo_phong import tinh_chi_so
    return tinh_chi_so(result)


def _processed_rows(
    fold: FoldWalkForward,
    selected: Mapping[str, Sequence[MauMoHinh]],
    training: object,
    feature_order: tuple[str, ...],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    stages = (
        ("validation_selection", getattr(training, "selection_model_id", None),
         getattr(training, "selection_pipeline", None), ("train", "validation")),
        ("final_refit", getattr(training, "refit_model_id", None),
         getattr(training, "pipeline", None), ("refit_train_validation", "test")),
    )
    for stage, model_id, pipeline, roles in stages:
        if pipeline is None or model_id is None:
            continue
        scaler = pipeline.named_steps["standard_scaler"]
        for role in roles:
            samples = list(selected[role])
            if not samples:
                continue
            transformed = scaler.transform([sample.feature for sample in samples])
            for sample, values in zip(samples, transformed, strict=True):
                row: dict[str, object] = {
                    "fold": fold.fold, "stage": stage, "model_id": model_id,
                    "vai_tro_du_lieu": role, "ngay": sample.ngay.isoformat(), "ma": sample.ma,
                }
                row.update({name: float(value) for name, value in zip(feature_order, values, strict=True)})
                result.append(row)
    return result


def _model_audit_rows(
    *,
    fold: FoldWalkForward,
    training: object,
    fold_failure_reason: str | None = None,
) -> list[dict[str, object]]:
    metadata = dict(getattr(training, "metadata", {}))
    candidate_errors = metadata.get("candidate_errors", {})
    common = {
        "fold": fold.fold,
        "selection_model_id": getattr(training, "selection_model_id", None),
        "refit_model_id": getattr(training, "refit_model_id", None),
        "candidate_errors": json.dumps(candidate_errors, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "feature_order": json.dumps(metadata.get("feature_order", []), ensure_ascii=False, separators=(",", ":")),
        "train_cutoff": fold.cutoff_train,
        "validation_cutoff": fold.cutoff_validation,
        "test_cutoff": fold.test_dates[-1] if fold.test_dates else None,
        "scikit_learn_version": metadata.get("scikit_learn"),
        "validation_log_loss": getattr(training, "validation_log_loss", None),
        "validation_auc": getattr(training, "validation_auc", None),
        "thoi_diem_huan_luyen": metadata.get("thoi_diem_huan_luyen"),
        "thoi_diem_tao_tin_hieu": metadata.get("thoi_diem_tao_tin_hieu"),
        "cutoff_feature": metadata.get("cutoff_feature"),
        "cutoff_nhan": metadata.get("cutoff_nhan"),
    }
    rows: list[dict[str, object]] = []
    for stage, key, model_id in (
        ("validation_selection", "validation_selection", getattr(training, "selection_model_id", None)),
        ("final_refit", "final_refit", getattr(training, "refit_model_id", None)),
    ):
        audit = metadata.get(key)
        if not isinstance(audit, Mapping):
            if stage == "final_refit" and getattr(training, "selection_pipeline", None) is None:
                continue
            audit = {}
        reason = getattr(training, "ly_do_that_bai", None)
        stage_success = bool(audit.get("converged"))
        if stage == "final_refit" and fold_failure_reason:
            stage_success = False
            reason = fold_failure_reason
        row = dict(common)
        row.update({
            "stage": stage,
            "model_id": model_id or getattr(training, "model_id", None),
            "thanh_cong": stage_success,
            "C": audit.get("C", getattr(training, "C", None)),
            "scaler_mean": json.dumps(audit.get("scaler_mean", []), separators=(",", ":")),
            "scaler_scale": json.dumps(audit.get("scaler_scale", []), separators=(",", ":")),
            "coefficients": json.dumps(audit.get("coefficients", []), separators=(",", ":")),
            "intercept": json.dumps(audit.get("intercept", []), separators=(",", ":")),
            "n_iter": json.dumps(audit.get("n_iter", []), separators=(",", ":")),
            "converged": audit.get("converged", False),
            "convergence_warning": json.dumps(audit.get("convergence_warning", []), ensure_ascii=False, separators=(",", ":")),
            "ly_do_that_bai": reason,
        })
        rows.append(row)
    if not rows:
        row = dict(common)
        row.update({
            "stage": "validation_selection", "model_id": getattr(training, "model_id", None),
            "thanh_cong": False, "C": getattr(training, "C", None),
            "scaler_mean": "[]", "scaler_scale": "[]", "coefficients": "[]",
            "intercept": "[]", "n_iter": "[]", "converged": False,
            "convergence_warning": "[]",
            "ly_do_that_bai": fold_failure_reason or getattr(training, "ly_do_that_bai", None),
        })
        rows.append(row)
    return rows


def _oos_window(
    calendar: Sequence[date],
    test_dates: Sequence[date],
    *,
    horizon: int,
) -> tuple[date, date, date]:
    if not test_dates:
        if len(calendar) < 2:
            raise ValueError("Khong du lich benchmark de tao cua so technical fallback.")
        return calendar[-2], calendar[-1], calendar[-1]
    index = {day: i for i, day in enumerate(calendar)}
    oos_start = min(test_dates)
    first_index = index[oos_start]
    if first_index + 1 >= len(calendar):
        raise ValueError("Tin hieu OOS dau tien khong co phien T+1.")
    metric_start = calendar[first_index + 1]
    last_index = index[max(test_dates)]
    oos_end = calendar[min(last_index + horizon, len(calendar) - 1)]
    if oos_end < metric_start:
        raise ValueError("Cua so OOS khong du de tinh metric.")
    return oos_start, metric_start, oos_end


def _benchmark_metadata_ok(
    records: Sequence[BanGhiPointInTime],
    *,
    day: date,
    signal_time: datetime,
    expected_symbol: str,
) -> bool:
    selected = chon_ban_ghi_pit(
        records, ngay=day, thoi_diem_tao_tin_hieu=signal_time,
        loai_du_lieu="benchmark_metadata",
    )
    return bool(selected) and all(
        record.khoa_ban_ghi == expected_symbol and record.du_lieu.get("ma") == expected_symbol
        for record in selected
    )


def _phien_yeu_cau_coverage_pit(
    *,
    calendar: Sequence[date],
    sample_dates: Sequence[date],
    universe_records: Sequence[BanGhiUniverse],
    symbols: Sequence[str],
    sessions_by_symbol: Mapping[str, set[date]],
    ngay_bat_dau_theo_ma: Mapping[str, date] | None = None,
) -> dict[str, set[date]]:
    """Mau so theo ma: research range ∩ data/listing start ∩ membership PIT ∩ phien can kiem tra."""
    first_observed = {
        symbol: min(days) for symbol, days in sessions_by_symbol.items() if days
    }
    for symbol, day in (ngay_bat_dau_theo_ma or {}).items():
        current = first_observed.get(symbol)
        if current is None or day < current:
            first_observed[symbol] = day

    required: dict[str, set[date]] = {symbol: set() for symbol in symbols}
    first_membership: dict[str, date] = {}
    for day in calendar:
        states = xac_dinh_universe(
            universe_records, ngay=day, thoi_diem_tao_tin_hieu=_signal_time(day), cac_ma=symbols,
        )
        for state in states:
            if not state.thuoc_universe:
                continue
            first_membership.setdefault(state.ma, day)
            # Co bar/loi quan sat thi dung moc bat dau du lieu; neu khong co bat ky
            # quan sat nao, membership dau tien la fallback de ma that bai co mau so > 0.
            start = first_observed.get(state.ma, first_membership[state.ma])
            if day >= start:
                required[state.ma].add(day)
    for day in sample_dates:
        states = xac_dinh_universe(
            universe_records, ngay=day, thoi_diem_tao_tin_hieu=_signal_time(day), cac_ma=symbols,
        )
        t1 = phien_t1_chinh_thuc(calendar, day)
        for state in states:
            if not state.thuoc_universe or t1 is None:
                continue
            start = first_observed.get(state.ma, first_membership.get(state.ma, day))
            if t1 >= start:
                required[state.ma].add(t1)
    return required


def _ma_co_gap_pit(
    required_by_symbol: Mapping[str, set[date]],
    sessions_by_symbol: Mapping[str, set[date]],
) -> list[str]:
    return sorted(
        symbol for symbol, required in required_by_symbol.items()
        if required - sessions_by_symbol.get(symbol, set())
    )


def _research_fail_closed(
    *,
    config: CauHinhMoc4,
    warnings: list[str],
    benchmark_metadata_missing: Sequence[date],
    successful_fold_count: int,
    test_predictions: Sequence[DuDoan],
    rebalance_dates: Sequence[date],
    coverage_by_day: Mapping[date, tuple[int, int]],
) -> None:
    failures: list[str] = []
    if benchmark_metadata_missing:
        failures.append("THIEU_BENCHMARK_METADATA_PIT")
    if successful_fold_count <= 0:
        failures.append("KHONG_CO_FOLD_TEST_HOP_LE")
    if not test_predictions:
        failures.append("KHONG_CO_PREDICTION_TEST_OOS")
    if not rebalance_dates:
        failures.append("KHONG_CO_NGAY_TAI_CAN_BANG")
    total_numerator = sum(value[0] for value in coverage_by_day.values())
    total_denominator = sum(value[1] for value in coverage_by_day.values())
    coverage_ratio = total_numerator / total_denominator if total_denominator else 0.0
    if coverage_ratio < config.ty_le_coverage_toi_thieu:
        failures.append("COVERAGE_DUOI_NGUONG_TOI_THIEU")
    if rebalance_dates and any(
        coverage_by_day.get(day, (0, 0))[0] < config.so_ma_eligible_toi_thieu
        for day in rebalance_dates
    ):
        failures.append("UNIVERSE_ELIGIBLE_DUOI_NGUONG_TOI_THIEU")
    if config.muc_dich_lan_chay == "nghien_cuu" and failures:
        raise ValueError("Nghien_cuu fail closed: " + ", ".join(failures) + ".")
    warnings.extend(f"TECHNICAL_{item}" for item in failures)


def _product_rows_targets(strategy: str, targets: Sequence[object]) -> list[dict[str, object]]:
    return [{
        "chien_luoc": strategy,
        "ngay_tin_hieu": target.ngay_tin_hieu,
        "ma": target.ma,
        "ty_trong_muc_tieu": float(target.ty_trong),
    } for target in targets]
