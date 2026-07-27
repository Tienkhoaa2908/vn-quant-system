"""Runner dau-cuoi Moc 4, chi doc tep cuc bo va cong bo san pham bat bien."""
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
    BENCHMARK_CONTRACT,
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



@dataclass(frozen=True)
class KetQuaNghienCuuMoc4:
    thu_muc_san_pham: Path
    so_fold: int
    so_fold_thanh_cong: int
    so_du_doan_test_logistic: int
    so_du_doan_test_baseline: int
    so_lenh_logistic: int
    so_lenh_baseline: int
    nav_cuoi_logistic: object
    nav_cuoi_baseline: object
    canh_bao: tuple[str, ...]


from .runner_io import (
    _DocBenchmarkDongCua, _DocOHLCV, _DocPIT, _read_csv, _parse_date, _parse_datetime, _parse_bool, _parse_float, _parse_int, _unique, _doc_ohlcv, _doc_benchmark_dong_cua, _xac_thuc_benchmark_identity, _doc_calendar, _doc_universe, _doc_pit, _signal_time, _json_ready, _json_text, _csv_text,
)
from .runner_core import (
    _samples, _m3_price_rows, _m3_config, _m3_events, _uv_version, _backtest_metrics, _processed_rows, _model_audit_rows, _oos_window, _benchmark_metadata_ok, _phien_yeu_cau_coverage_pit, _ma_co_gap_pit, _research_fail_closed, _product_rows_targets,
)

def chay_nghien_cuu_moc_4(
    *,
    duong_dan_cau_hinh: Path,
    duong_dan_ohlcv: Path,
    duong_dan_benchmark: Path,
    duong_dan_lich_benchmark: Path,
    duong_dan_universe: Path,
    duong_dan_corporate_actions: Path,
    thu_muc_dau_ra: Path,
    ma_lan_chay: str,
    git_commit: str,
    thoi_diem_utc: datetime | None = None,
) -> KetQuaNghienCuuMoc4:
    """Chay toan bo pipeline M4 tu tep cuc bo; khong co bat ky loi goi mang nao."""
    paths = {
        "cau_hinh": Path(duong_dan_cau_hinh),
        "ohlcv": Path(duong_dan_ohlcv),
        "benchmark": Path(duong_dan_benchmark),
        "lich_benchmark": Path(duong_dan_lich_benchmark),
        "universe": Path(duong_dan_universe),
        "corporate_actions": Path(duong_dan_corporate_actions),
    }
    if not ma_lan_chay or "/" in ma_lan_chay or "\\" in ma_lan_chay or ma_lan_chay in {".", ".."}:
        raise ValueError("ma_lan_chay khong hop le.")
    if len(git_commit) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in git_commit):
        raise ValueError("git_commit phai la SHA 40 ky tu hexa.")
    config_raw = json.loads(paths["cau_hinh"].read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Cau hinh chua {x}.")))
    if not isinstance(config_raw, dict):
        raise ValueError("Cau hinh goc phai la object.")
    m4_raw = config_raw.get("moc_4", config_raw)
    m3_raw = config_raw.get("mo_phong")
    if not isinstance(m4_raw, dict) or not isinstance(m3_raw, dict):
        raise ValueError("Cau hinh runner can hai object moc_4 va mo_phong.")
    m4_mapping = dict(m4_raw)
    m4_mapping["thu_muc_dau_ra"] = str(m4_mapping.get("thu_muc_dau_ra", "."))
    config = CauHinhMoc4.tu_mapping(m4_mapping)
    stock_doc = _doc_ohlcv(paths["ohlcv"])
    benchmark_doc = _doc_benchmark_dong_cua(
        paths["benchmark"], expected_symbol=config.benchmark,
    )
    calendar = _doc_calendar(paths["lich_benchmark"])
    universe_records, universe_source, universe_version = _doc_universe(paths["universe"])
    pit_doc = _doc_pit(paths["corporate_actions"])
    benchmark_source = benchmark_doc.nguon
    benchmark_version = benchmark_doc.phien_ban
    if (
        any(row.co_so_gia != config.co_so_gia for row in stock_doc.rows)
        or benchmark_doc.co_so_gia != config.co_so_gia
    ):
        raise ValueError("Co so gia OHLCV/benchmark khong khop cau hinh.")

    sample_dates = phien_cuoi_thang(calendar)
    symbols = tuple(sorted({record.ma for record in universe_records} | {row.ma for row in stock_doc.rows}
                           | set(stock_doc.ma_loi_gia) | set(stock_doc.ma_loi_volume)))
    features = tao_feature_cuoi_thang(
        stock_doc.rows, benchmark_doc.rows, lich_benchmark=calendar,
        feature_bat_buoc=config.feature_bat_buoc,
    )
    labels = tao_nhan(
        stock_doc.rows, benchmark_doc.rows, cac_ngay_tin_hieu=sample_dates,
        label_horizon=config.label_horizon, lich_benchmark=calendar,
    )
    feature_map = {(row.ngay, row.ma): row for row in features}
    label_map = {(row.ngay, row.ma): row for row in labels}
    stock_bar_map = {(row.ngay, row.ma): row for row in stock_doc.rows}
    universe_rows: list[object] = []
    exclusion_rows: list[DongLoai] = []
    eligible: set[tuple[date, str]] = set()
    eligibility_details: dict[tuple[date, str], dict[str, object]] = {}
    coverage_by_day: dict[date, tuple[int, int]] = {}
    less_top_k: list[date] = []
    benchmark_metadata_missing: list[date] = []
    for day in sample_dates:
        signal_time = _signal_time(day)
        states = xac_dinh_universe(
            universe_records, ngay=day, thoi_diem_tao_tin_hieu=signal_time, cac_ma=symbols,
        )
        universe_rows.extend(states)
        metadata_ok = _benchmark_metadata_ok(
            pit_doc.records, day=day, signal_time=signal_time, expected_symbol=config.benchmark,
        )
        if not metadata_ok:
            benchmark_metadata_missing.append(day)
        t1 = phien_t1_chinh_thuc(calendar, day)
        denominator = sum(state.thuoc_universe for state in states)
        numerator = 0
        for state in states:
            key = (day, state.ma)
            feature = feature_map.get(key)
            open_t1 = stock_bar_map.get((t1, state.ma)) if t1 is not None else None
            is_eligible, reasons, liquidity_value = danh_gia_eligibility(
                state=state, feature=feature, benchmark_metadata_ok=metadata_ok,
                open_t1=open_t1, cua_so_thanh_khoan=config.cua_so_thanh_khoan,
                nguong_gtgd_tb_toi_thieu=config.nguong_gtgd_tb_toi_thieu,
                loi_gia=(state.ma, day) in stock_doc.khoa_loi_gia,
                loi_volume=(state.ma, day) in stock_doc.khoa_loi_volume,
            )
            label = label_map.get(key)
            all_reasons = set(reasons)
            if label is None or label.nhan is None:
                all_reasons.add(label.ly_do_nhan_rong if label is not None else "thieu_nhan")
            if is_eligible:
                eligible.add(key)
                numerator += 1
            eligibility_details[key] = {
                "eligible": is_eligible, "ly_do": tuple(sorted(reasons)),
                "gtgd_tb_20": liquidity_value, "T1": t1,
                "open_t1_hop_le": open_t1 is not None,
            }
            for reason in sorted(all_reasons):
                exclusion_rows.append(DongLoai(day, state.ma, reason))
        coverage_by_day[day] = (numerator, denominator)
        if numerator < config.top_k:
            less_top_k.append(day)

    model_samples, momentum_map = _samples(features, labels, eligible, config.feature_order)
    folds = tao_folds(calendar, config)
    logistic_validation: list[DuDoan] = []
    logistic_test: list[DuDoan] = []
    baseline_test: list[DuDoan] = []
    processed_rows: list[dict[str, object]] = []
    model_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    fold_errors: list[dict[str, str]] = []
    successful_test_dates: list[date] = []
    successful_fold_count = 0
    for fold in folds:
        fold_rows.append({
            "fold": fold.fold,
            "train_tu": fold.train_dates[0] if fold.train_dates else None,
            "train_den": fold.train_dates[-1] if fold.train_dates else None,
            "validation_tu": fold.validation_dates[0] if fold.validation_dates else None,
            "validation_den": fold.validation_dates[-1] if fold.validation_dates else None,
            "test_tu": fold.test_dates[0] if fold.test_dates else None,
            "test_den": fold.test_dates[-1] if fold.test_dates else None,
            "cutoff_train": fold.cutoff_train,
            "cutoff_validation": fold.cutoff_validation,
            "cutoff_refit": fold.cutoff_refit,
            "so_phien_purge": len(fold.purge_dates),
            "so_phien_embargo": len(fold.embargo_dates),
        })
        selected = loc_mau_theo_fold(model_samples, fold)
        signal_at = _signal_time(fold.test_dates[0])
        trained_at = signal_at - timedelta(minutes=1)
        feature_cutoff = signal_at
        label_cutoff = datetime.combine(fold.cutoff_refit, time(23, 59), tzinfo=UTC)
        result = huan_luyen_logistic(
            fold=fold.fold, train=selected["train"], validation=selected["validation"],
            refit=selected["refit_train_validation"], cau_hinh=config,
            thoi_diem_huan_luyen=trained_at, thoi_diem_tao_tin_hieu=signal_at,
            cutoff_feature=feature_cutoff, cutoff_nhan=label_cutoff,
        )
        logistic_validation.extend(result.validation_predictions)
        processed_rows.extend(_processed_rows(fold, selected, result, config.feature_order))

        fold_failure_reason: str | None = None
        if not result.thanh_cong:
            fold_failure_reason = result.ly_do_that_bai or "fold_that_bai"
        elif not selected["test"]:
            fold_failure_reason = "test_rong"
        else:
            test_predictions = list(du_doan_test(result, selected["test"]))
            if not test_predictions:
                fold_failure_reason = "khong_co_prediction_test"

        model_rows.extend(_model_audit_rows(
            fold=fold, training=result, fold_failure_reason=fold_failure_reason,
        ))
        for stage_key, stage_name, model_id in (
            ("validation_selection", "validation_selection", result.selection_model_id),
            ("final_refit", "final_refit", result.refit_model_id),
        ):
            audit = result.metadata.get(stage_key)
            if not isinstance(audit, Mapping) or not model_id:
                continue
            coefficients = list(audit.get("coefficients", []))
            for name, coefficient in zip(config.feature_order, coefficients, strict=True):
                coefficient_rows.append({
                    "fold": fold.fold, "stage": stage_name, "model_id": model_id,
                    "feature": name, "he_so": float(coefficient), "intercept": "",
                })
            intercept = list(audit.get("intercept", []))
            if intercept:
                coefficient_rows.append({
                    "fold": fold.fold, "stage": stage_name, "model_id": model_id,
                    "feature": "__intercept__", "he_so": "", "intercept": float(intercept[0]),
                })

        if fold_failure_reason is not None:
            fold_errors.append({"fold": fold.fold, "ly_do": fold_failure_reason})
            continue

        logistic_test.extend(test_predictions)
        baseline_test.extend(du_doan_baseline_test(
            fold=fold.fold, samples=selected["test"], momentum_theo_khoa=momentum_map,
        ))
        successful_test_dates.extend(fold.test_dates)
        successful_fold_count += 1

    xac_thuc_prediction_test(logistic_test)
    xac_thuc_prediction_test(baseline_test)
    logistic_rankings, logistic_cash = xep_hang_test(logistic_test, top_k=config.top_k)
    baseline_rankings, baseline_cash = xep_hang_baseline_test(baseline_test, top_k=config.top_k)
    successful_test_dates = sorted(set(successful_test_dates))

    sessions_by_symbol: dict[str, set[date]] = {symbol: set() for symbol in symbols}
    for row in stock_doc.rows:
        sessions_by_symbol.setdefault(row.ma, set()).add(row.ngay)
    observed_start_by_symbol: dict[str, date] = {}
    for symbol, days in sessions_by_symbol.items():
        if days:
            observed_start_by_symbol[symbol] = min(days)
    for symbol, day in (*stock_doc.khoa_loi_gia, *stock_doc.khoa_loi_volume):
        current = observed_start_by_symbol.get(symbol)
        if current is None or day < current:
            observed_start_by_symbol[symbol] = day
    required_by_symbol = _phien_yeu_cau_coverage_pit(
        calendar=calendar, sample_dates=sample_dates, universe_records=universe_records,
        symbols=symbols, sessions_by_symbol=sessions_by_symbol,
        ngay_bat_dau_theo_ma=observed_start_by_symbol,
    )
    gap_symbols = _ma_co_gap_pit(required_by_symbol, sessions_by_symbol)
    warmup_symbols = sorted({
        row.ma for row in features
        if any("ma250" in reason or "thieu_warm_up" in reason for reason in row.ly_do)
    })
    failed_symbols = [symbol for symbol in symbols if not sessions_by_symbol.get(symbol)]
    missing_ca = (
        symbols if config.co_so_gia == "gia_khong_dieu_chinh"
        and not config.corporate_actions_day_du else ()
    )
    coverage = bao_cao_do_phu(
        exclusion_rows, loi_fold=fold_errors, cac_ngay_yeu_cau=calendar,
        cac_ngay_thuc_te=[row.ngay for row in stock_doc.rows], cac_ma_universe=symbols,
        phien_co_du_lieu_theo_ma=sessions_by_symbol,
        phien_yeu_cau_theo_ma=required_by_symbol,
        coverage_theo_ngay=coverage_by_day,
        ma_that_bai_hoan_toan=failed_symbols, ma_thieu_warm_up=warmup_symbols,
        ma_co_gap=gap_symbols, ma_loi_gia=stock_doc.ma_loi_gia,
        ma_loi_volume=stock_doc.ma_loi_volume, ma_thieu_corporate_actions=missing_ca,
        ngay_it_hon_top_k=less_top_k, nguon_ohlcv=stock_doc.nguon,
        phien_ban_ohlcv=stock_doc.phien_ban, nguon_universe=universe_source,
        phien_ban_universe=universe_version, nguon_benchmark=benchmark_source,
        phien_ban_benchmark=benchmark_version, co_so_gia=config.co_so_gia,
    )

    m3_config = _m3_config(m3_raw, config.co_so_gia)
    warnings = list(xac_thuc_co_so_gia_va_su_kien(
        config, so_su_kien=len(pit_doc.event_rows),
    ))
    if stock_doc.ma_loi_gia:
        warnings.append("DU_LIEU_LOI_GIA_DA_LOAI_CO_KIEM_SOAT")
    if stock_doc.ma_loi_volume:
        warnings.append("DU_LIEU_LOI_VOLUME_DA_LOAI_CO_KIEM_SOAT")
    _research_fail_closed(
        config=config, warnings=warnings,
        benchmark_metadata_missing=benchmark_metadata_missing,
        successful_fold_count=successful_fold_count,
        test_predictions=logistic_test, rebalance_dates=successful_test_dates,
        coverage_by_day=coverage_by_day,
    )
    if config.muc_dich_lan_chay == "nghien_cuu" and not baseline_test:
        raise ValueError("Nghien_cuu fail closed: KHONG_CO_PREDICTION_BASELINE_TEST.")
    if config.muc_dich_lan_chay == "kiem_tra_ky_thuat" and not baseline_test:
        warnings.append("TECHNICAL_KHONG_CO_PREDICTION_BASELINE_TEST")

    oos_start, metric_start, oos_end = _oos_window(
        calendar, successful_test_dates, horizon=config.label_horizon,
    )
    events = _m3_events(
        pit_doc.records, config.co_so_gia, oos_start=oos_start, oos_end=oos_end,
    )
    price_rows = _m3_price_rows(stock_doc.rows, eligible=eligible)
    logistic_backtest = chay_backtest_oos_lien_tuc(
        rankings=logistic_rankings, du_lieu_gia=price_rows, cau_hinh_mo_phong=m3_config,
        cac_su_kien=events, ngay_tai_can_bang=successful_test_dates,
        cac_ma_lien_quan=symbols, ten_chien_luoc="m4_logistic_oos",
        oos_start=oos_start, oos_end=oos_end,
    )
    baseline_backtest = chay_backtest_oos_lien_tuc(
        rankings=baseline_rankings, du_lieu_gia=price_rows, cau_hinh_mo_phong=m3_config,
        cac_su_kien=events, ngay_tai_can_bang=successful_test_dates,
        cac_ma_lien_quan=symbols, ten_chien_luoc="m4_momentum_oos",
        oos_start=oos_start, oos_end=oos_end,
    )
    logistic_model_metrics = metric_model_test(logistic_test)
    baseline_model_metrics = metric_baseline_test(baseline_test)
    logistic_ranking_metrics = metric_ranking_test(logistic_rankings)
    baseline_ranking_metrics = metric_ranking_test(baseline_rankings)
    logistic_backtest_metrics = metric_backtest_oos(
        logistic_backtest, oos_start=oos_start, metric_start=metric_start, oos_end=oos_end,
    )
    baseline_backtest_metrics = metric_backtest_oos(
        baseline_backtest, oos_start=oos_start, metric_start=metric_start, oos_end=oos_end,
    )

    all_predictions = [*logistic_validation, *logistic_test, *baseline_test]
    all_rankings = [*logistic_rankings, *baseline_rankings]
    logistic_targets = chuyen_ty_trong_test(
        logistic_rankings, ngay_tai_can_bang=successful_test_dates,
        cac_ma_lien_quan=symbols, ten_chien_luoc="m4_logistic_oos",
    )
    baseline_targets = chuyen_ty_trong_test(
        baseline_rankings, ngay_tai_can_bang=successful_test_dates,
        cac_ma_lien_quan=symbols, ten_chien_luoc="m4_momentum_oos",
    )

    universe_product_rows = []
    for state in sorted(universe_rows, key=lambda x: (x.ngay, x.ma)):
        record = state.ban_ghi
        universe_product_rows.append({
            "ngay": state.ngay, "ma": state.ma, "thuoc_universe": state.thuoc_universe,
            "ly_do": state.ly_do, "ngay_hieu_luc": record.ngay_hieu_luc if record else None,
            "nguon": record.nguon if record else None, "phien_ban": record.phien_ban if record else None,
            "thoi_diem_cong_bo": record.thoi_diem_cong_bo if record else None,
        })
    feature_product_rows = []
    for row in sorted(features, key=lambda x: (x.ngay, x.ma)):
        detail = eligibility_details.get((row.ngay, row.ma), {})
        item: dict[str, object] = {
            "ngay": row.ngay, "ma": row.ma, "hop_le": row.hop_le,
            "ly_do": "|".join(row.ly_do),
            "eligible": detail.get("eligible", False),
            "ly_do_eligibility": "|".join(detail.get("ly_do", ())),
            "gtgd_tb_20_eligibility": detail.get("gtgd_tb_20"),
            "T1": detail.get("T1"),
            "open_t1_hop_le": detail.get("open_t1_hop_le", False),
        }
        item.update({name: row.gia_tri.get(name) for name in config.feature_order})
        feature_product_rows.append(item)
    label_product_rows = [{
        "ngay": row.ngay, "ma": row.ma, "T_H": row.T_H,
        "ngay_ket_thuc_nhan": row.ngay_ket_thuc_nhan,
        "loi_nhuan_co_phieu": row.loi_nhuan_co_phieu,
        "loi_nhuan_benchmark": row.loi_nhuan_benchmark,
        "loi_nhuan_tuong_doi": row.loi_nhuan_tuong_doi,
        "nhan": row.nhan, "ly_do_nhan_rong": row.ly_do_nhan_rong,
    } for row in sorted(labels, key=lambda x: (x.ngay, x.ma))]
    ranking_rows = [{
        "chien_luoc": "logistic" if "_logistic_" in row.model_id else "momentum_baseline",
        "fold": row.fold, "model_id": row.model_id, "ngay": row.ngay, "ma": row.ma,
        "diem": row.xac_suat_nhan_1, "thu_hang": row.thu_hang,
        "duoc_chon": row.duoc_chon, "ty_trong_muc_tieu": row.ty_trong_muc_tieu,
        "nhan": row.nhan, "loi_nhuan_tuong_doi": row.loi_nhuan_tuong_doi,
    } for row in sorted(all_rankings, key=lambda x: (x.model_id, x.ngay, x.thu_hang, x.ma))]
    target_rows = [
        *_product_rows_targets("logistic", logistic_targets),
        *_product_rows_targets("momentum_baseline", baseline_targets),
    ]

    model_metrics = {"logistic": logistic_model_metrics, "momentum_baseline": baseline_model_metrics}
    ranking_metrics = {"logistic": logistic_ranking_metrics, "momentum_baseline": baseline_ranking_metrics}
    backtest_metrics = {"logistic": logistic_backtest_metrics, "momentum_baseline": baseline_backtest_metrics}
    limitations = [
        "TIER_A_TIER_B_CHUA_CHAY",
        "NGUON_DU_LIEU_THAT_CHUA_DUOC_PHE_DUYET",
        "BENCHMARK_EXACT_OFFICIAL_OHLC_CHUA_CO",
        "BENCHMARK_RAW_SOURCE_GIU_BAT_BIEN",
        "KHONG_CORRECTION_OVERLAY",
        "KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC",
        "KHONG_LIGHTGBM_KHONG_SSI_KHONG_MOC_5",
    ]
    report = {
        "ma_lan_chay": ma_lan_chay,
        "benchmark_contract": BENCHMARK_CONTRACT,
        "benchmark_policy": {
            "features_va_labels_chi_dung_close": True,
            "open_high_low_volume_duoc_dung": False,
            "correction_overlay": False,
            "raw_source_giu_bat_bien": True,
            "exact_official_ohlc_da_co": False,
            "chi_kiem_tra_ky_thuat": True,
        },
        "so_fold": len(folds),
        "oos_start": oos_start, "ngay_bat_dau_metric": metric_start, "oos_end": oos_end,
        "so_fold_thanh_cong": successful_fold_count,
        "so_du_doan_test_logistic": len(logistic_test),
        "so_du_doan_test_baseline": len(baseline_test),
        "so_ngay_tai_can_bang": len(successful_test_dates),
        "cash_logistic": {day.isoformat(): value for day, value in logistic_cash.items()},
        "cash_baseline": {day.isoformat(): value for day, value in baseline_cash.items()},
        "backtest_logistic": {
            "ngay_tin_hieu": [item.ngay_tin_hieu.isoformat() for item in logistic_backtest.lenh],
            "ngay_thuc_thi": [item.ngay_thuc_thi.isoformat() if item.ngay_thuc_thi else None for item in logistic_backtest.lenh],
            "ngay_khop": [item.ngay_khop.isoformat() for item in logistic_backtest.khop_lenh],
            "nav_cuoi": str(logistic_backtest.nav[-1].nav if logistic_backtest.nav else m3_config.von_ban_dau),
            "so_lan_tai_can_bang": logistic_backtest.so_lan_tai_can_bang,
        },
        "backtest_baseline": {
            "ngay_tin_hieu": [item.ngay_tin_hieu.isoformat() for item in baseline_backtest.lenh],
            "ngay_thuc_thi": [item.ngay_thuc_thi.isoformat() if item.ngay_thuc_thi else None for item in baseline_backtest.lenh],
            "ngay_khop": [item.ngay_khop.isoformat() for item in baseline_backtest.khop_lenh],
            "nav_cuoi": str(baseline_backtest.nav[-1].nav if baseline_backtest.nav else m3_config.von_ban_dau),
            "so_lan_tai_can_bang": baseline_backtest.so_lan_tai_can_bang,
        },
        "canh_bao": warnings, "gioi_han": limitations,
    }
    products: dict[str, str | bytes] = {
        "cau_hinh.json": _json_text({"moc_4": config.thanh_mapping(), "mo_phong": m3_raw}),
        "bao_cao_do_phu.json": _json_text(coverage),
        "universe_theo_ngay.csv": _csv_text(
            ("ngay", "ma", "thuoc_universe", "ly_do", "ngay_hieu_luc", "nguon", "phien_ban", "thoi_diem_cong_bo"),
            universe_product_rows,
        ),
        "feature_raw.csv": _csv_text(
            ("ngay", "ma", "hop_le", "ly_do", "eligible", "ly_do_eligibility",
             "gtgd_tb_20_eligibility", "T1", "open_t1_hop_le", *config.feature_order),
            feature_product_rows,
        ),
        "feature_sau_tien_xu_ly.csv": tao_csv_feature_sau_tien_xu_ly(processed_rows, config.feature_order),
        "nhan.csv": _csv_text(
            ("ngay", "ma", "T_H", "ngay_ket_thuc_nhan", "loi_nhuan_co_phieu", "loi_nhuan_benchmark", "loi_nhuan_tuong_doi", "nhan", "ly_do_nhan_rong"),
            label_product_rows,
        ),
        "folds.csv": _csv_text(
            ("fold", "train_tu", "train_den", "validation_tu", "validation_den", "test_tu", "test_den", "cutoff_train", "cutoff_validation", "cutoff_refit", "so_phien_purge", "so_phien_embargo"),
            fold_rows,
        ),
        "mo_hinh.csv": _csv_text(
            (
                "fold", "stage", "selection_model_id", "refit_model_id", "model_id",
                "thanh_cong", "C", "scaler_mean", "scaler_scale", "coefficients",
                "intercept", "n_iter", "converged", "convergence_warning",
                "candidate_errors", "feature_order", "train_cutoff",
                "validation_cutoff", "test_cutoff", "scikit_learn_version",
                "validation_log_loss", "validation_auc", "ly_do_that_bai",
                "thoi_diem_huan_luyen", "thoi_diem_tao_tin_hieu",
                "cutoff_feature", "cutoff_nhan",
            ),
            model_rows,
        ),
        "he_so_logistic.csv": _csv_text(
            ("fold", "stage", "model_id", "feature", "he_so", "intercept"),
            coefficient_rows,
        ),
        "du_doan.csv": tao_csv_du_doan(all_predictions),
        "xep_hang.csv": _csv_text(
            ("chien_luoc", "fold", "model_id", "ngay", "ma", "diem", "thu_hang", "duoc_chon", "ty_trong_muc_tieu", "nhan", "loi_nhuan_tuong_doi"),
            ranking_rows,
        ),
        "ty_trong_muc_tieu.csv": _csv_text(("chien_luoc", "ngay_tin_hieu", "ma", "ty_trong_muc_tieu"), target_rows),
        "chi_so_mo_hinh.json": _json_text(model_metrics),
        "chi_so_ranking.json": _json_text(ranking_metrics),
        "chi_so_backtest.json": _json_text(backtest_metrics),
        "bao_cao.json": _json_text(report),
    }
    if set(products) != set(TEN_SAN_PHAM):
        raise AssertionError("Runner khong dung 16 san pham truoc manifest.")
    timestamp = thoi_diem_utc or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise ValueError("thoi_diem_utc runner phai timezone-aware UTC.")
    metadata = {
        "git_commit": git_commit.lower(), "ma_lan_chay": ma_lan_chay,
        "thoi_diem_utc": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "python_version": platform.python_version(), "uv_version": _uv_version(),
        "scikit_learn_version": sklearn.__version__,
        "benchmark_contract": BENCHMARK_CONTRACT,
        "benchmark_policy": {
            "features_va_labels_chi_dung_close": True,
            "open_high_low_volume_duoc_dung": False,
            "correction_overlay": False,
            "raw_source_giu_bat_bien": True,
            "exact_official_ohlc_da_co": False,
            "chi_kiem_tra_ky_thuat": True,
        },
        "nguon_ohlcv": stock_doc.nguon, "phien_ban_ohlcv": stock_doc.phien_ban,
        "nguon_universe": universe_source, "phien_ban_universe": universe_version,
        "nguon_benchmark": benchmark_source, "phien_ban_benchmark": benchmark_version,
        "co_so_gia": config.co_so_gia, "muc_dich_lan_chay": config.muc_dich_lan_chay,
        "cau_hinh_feature": {
            "feature_order": list(config.feature_order),
            "feature_bat_buoc": list(config.feature_bat_buoc),
            "tan_suat": "cuoi_thang", "lich": "benchmark_chinh_thuc",
            "benchmark": "chi_dung_gia_dong_cua",
            "thanh_khoan": {
                "cong_thuc": "mean(close*volume) tren 20 phien benchmark ket thuc tai T",
                "cua_so_phien": config.cua_so_thanh_khoan,
                "nguong_toi_thieu": config.nguong_gtgd_tb_toi_thieu,
                "don_vi": "VND/phien", "cutoff": "close T",
            },
            "open_t1": "open dung phien benchmark T+1; khong tim phien xa hon",
        },
        "cau_hinh_label": {
            "horizon": config.label_horizon, "lich": "benchmark_chinh_thuc",
            "benchmark": "chi_dung_gia_dong_cua",
        },
        "cau_hinh_fold": {
            "expanding": True, "purge_phien": config.purge_phien,
            "embargo_phien": config.embargo_phien,
            "so_thang_validation": config.so_thang_validation,
            "so_thang_test": config.so_thang_test,
            "oos_start": oos_start.isoformat(),
            "ngay_bat_dau_metric": metric_start.isoformat(),
            "oos_end": oos_end.isoformat(),
        },
        "cau_hinh_model": {"standard_scaler": True, "penalty": "l2", "solver": config.solver, "max_iter": config.max_iter, "C_grid": list(config.C_grid), "seed": config.seed},
        "cau_hinh_ranking": {
            "top_k": config.top_k, "tie_break": "ma_tang_dan",
            "ty_trong": "1/top_k", "phan_thieu": "tien_mat",
            "ty_le_coverage_toi_thieu": config.ty_le_coverage_toi_thieu,
            "so_ma_eligible_toi_thieu": config.so_ma_eligible_toi_thieu,
        },
        "canh_bao": warnings, "gioi_han": limitations,
    }
    destination = Path(thu_muc_dau_ra) / ma_lan_chay
    published = cong_bo_san_pham(destination, products, metadata=metadata, dau_vao=paths)
    logistic_nav = logistic_backtest.nav[-1].nav if logistic_backtest.nav else m3_config.von_ban_dau
    baseline_nav = baseline_backtest.nav[-1].nav if baseline_backtest.nav else m3_config.von_ban_dau
    return KetQuaNghienCuuMoc4(
        thu_muc_san_pham=published, so_fold=len(folds),
        so_fold_thanh_cong=successful_fold_count,
        so_du_doan_test_logistic=len(logistic_test),
        so_du_doan_test_baseline=len(baseline_test),
        so_lenh_logistic=len(logistic_backtest.lenh), so_lenh_baseline=len(baseline_backtest.lenh),
        nav_cuoi_logistic=logistic_nav, nav_cuoi_baseline=baseline_nav,
        canh_bao=tuple(warnings),
    )
