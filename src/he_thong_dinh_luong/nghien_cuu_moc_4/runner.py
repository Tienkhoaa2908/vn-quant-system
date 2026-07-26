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

from .adapter_mo_phong import chay_backtest_oos_lien_tuc, chuyen_ty_trong_test
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


@dataclass(frozen=True)
class _DocOHLCV:
    rows: tuple[ThanhOHLCV, ...]
    nguon: str
    phien_ban: str
    ma_loi_gia: tuple[str, ...]
    ma_loi_volume: tuple[str, ...]


@dataclass(frozen=True)
class _DocPIT:
    records: tuple[BanGhiPointInTime, ...]
    event_rows: tuple[Mapping[str, object], ...]
    nguon: str
    phien_ban: str


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    if not path.is_file():
        raise ValueError(f"Tep dau vao khong ton tai: {path}.")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV khong co header: {path}.")
        rows = [dict(row) for row in reader]
        return rows, tuple(reader.fieldnames)


def _parse_date(value: object, name: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} khong duoc rong.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} khong dung YYYY-MM-DD.") from exc


def _parse_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} khong duoc rong.")
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} khong phai ISO-8601.") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} phai co mui gio.")
    return result


def _parse_bool(value: object, name: str) -> bool:
    if value is True or value == "true" or value == "True" or value == "1":
        return True
    if value is False or value == "false" or value == "False" or value == "0":
        return False
    raise ValueError(f"{name} phai la boolean ro rang.")


def _parse_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} khong phai so hop le.")
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} khong phai so hop le.") from exc
    if not isfinite(result):
        raise ValueError(f"{name} phai huu han; NaN/Inf bi tu choi.")
    return result


def _parse_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} khong phai int hop le.")
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        raise ValueError(f"{name} phai la int.")
    return int(text)


def _unique(values: Iterable[str], name: str) -> str:
    found = sorted({value for value in values if value})
    if len(found) != 1:
        raise ValueError(f"{name} phai co dung mot gia tri; nhan duoc {found}.")
    return found[0]


def _doc_ohlcv(path: Path, *, benchmark: bool = False) -> _DocOHLCV:
    raw_rows, fields = _read_csv(path)
    required = {
        "ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat",
        "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"OHLCV thieu cot: {', '.join(missing)}.")
    rows: list[ThanhOHLCV] = []
    price_errors: set[str] = set()
    volume_errors: set[str] = set()
    seen: set[tuple[str, date]] = set()
    sources: list[str] = []
    versions: list[str] = []
    for number, raw in enumerate(raw_rows, 2):
        symbol = str(raw.get("ma", "")).strip().upper()
        if not symbol:
            raise ValueError(f"Ma rong tai dong {number} cua {path.name}.")
        day = _parse_date(raw.get("ngay"), f"ngay dong {number}")
        key = (symbol, day)
        if key in seen:
            raise ValueError(f"OHLCV trung ma/ngay: {symbol}, {day}.")
        seen.add(key)
        source = str(raw.get("nguon", "")).strip()
        version = str(raw.get("phien_ban", "")).strip()
        basis = str(raw.get("co_so_gia", "")).strip()
        if not source or not version or not basis:
            raise ValueError(f"OHLCV thieu nguon/phien_ban/co_so_gia tai dong {number}.")
        sources.append(source)
        versions.append(version)
        try:
            open_price = _parse_float(raw.get("gia_mo_cua"), "gia_mo_cua")
            high = _parse_float(raw.get("gia_cao_nhat"), "gia_cao_nhat")
            low = _parse_float(raw.get("gia_thap_nhat"), "gia_thap_nhat")
            close = _parse_float(raw.get("gia_dong_cua"), "gia_dong_cua")
            if min(open_price, high, low, close) <= 0:
                raise ValueError("Gia phai duong.")
        except ValueError as exc:
            price_errors.add(symbol)
            raise ValueError(f"OHLCV loi gia tai {symbol}, {day}: {exc}") from exc
        try:
            volume = _parse_int(raw.get("khoi_luong"), "khoi_luong")
            if volume < 0:
                raise ValueError("khoi_luong khong duoc am.")
        except ValueError as exc:
            volume_errors.add(symbol)
            raise ValueError(f"OHLCV loi volume tai {symbol}, {day}: {exc}") from exc
        rows.append(ThanhOHLCV(
            ma=symbol, ngay=day, gia_mo_cua=open_price, gia_cao_nhat=high,
            gia_thap_nhat=low, gia_dong_cua=close, khoi_luong=volume,
            nguon=source, phien_ban=version, co_so_gia=basis,
        ))
    if benchmark and not rows:
        raise ValueError("Benchmark khong co bar hop le.")
    return _DocOHLCV(
        tuple(sorted(rows, key=lambda row: (row.ma, row.ngay))),
        _unique(sources, "nguon OHLCV"), _unique(versions, "phien_ban OHLCV"),
        tuple(sorted(price_errors)), tuple(sorted(volume_errors)),
    )


def _doc_calendar(path: Path) -> tuple[date, ...]:
    rows, fields = _read_csv(path)
    if "ngay" not in fields:
        raise ValueError("Lich benchmark thieu cot ngay.")
    days = tuple(_parse_date(row.get("ngay"), "lich_benchmark.ngay") for row in rows)
    if not days:
        raise ValueError("Lich benchmark rong.")
    if len(days) != len(set(days)):
        raise ValueError("Lich benchmark trung ngay.")
    if tuple(sorted(days)) != days:
        raise ValueError("Lich benchmark phai sap xep tang dan.")
    return days


def _doc_universe(path: Path) -> tuple[tuple[BanGhiUniverse, ...], str, str]:
    rows, fields = _read_csv(path)
    required = {"ngay_hieu_luc", "ma", "thuoc_universe", "nguon", "phien_ban", "thoi_diem_cong_bo"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"Universe thieu cot: {', '.join(missing)}.")
    result: list[BanGhiUniverse] = []
    for number, row in enumerate(rows, 2):
        result.append(BanGhiUniverse(
            ngay_hieu_luc=_parse_date(row.get("ngay_hieu_luc"), f"universe.ngay_hieu_luc dong {number}"),
            ma=str(row.get("ma", "")).strip().upper(),
            thuoc_universe=_parse_bool(row.get("thuoc_universe"), "thuoc_universe"),
            nguon=str(row.get("nguon", "")).strip(),
            phien_ban=str(row.get("phien_ban", "")).strip(),
            thoi_diem_cong_bo=_parse_datetime(row.get("thoi_diem_cong_bo"), "thoi_diem_cong_bo"),
        ))
    if not result:
        raise ValueError("Universe rong.")
    return tuple(result), _unique((x.nguon for x in result), "nguon universe"), _unique((x.phien_ban for x in result), "phien_ban universe")


def _doc_pit(path: Path) -> _DocPIT:
    rows, fields = _read_csv(path)
    if not rows:
        return _DocPIT((), (), "khong_co_su_kien", "0")
    required = {"loai_du_lieu", "khoa_ban_ghi", "ngay_hieu_luc", "nguon", "phien_ban", "thoi_diem_cong_bo"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"Metadata PIT thieu cot: {', '.join(missing)}.")
    records: list[BanGhiPointInTime] = []
    events: list[Mapping[str, object]] = []
    for number, row in enumerate(rows, 2):
        data_text = str(row.get("du_lieu_json", "") or "{}").strip()
        try:
            data = json.loads(data_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"du_lieu_json sai tai dong {number}.") from exc
        if not isinstance(data, dict):
            raise ValueError("du_lieu_json phai la object.")
        xac_thuc_cau_truc_huu_han(data, f"metadata_pit[{number}]")
        record = BanGhiPointInTime(
            loai_du_lieu=str(row.get("loai_du_lieu", "")).strip(),
            khoa_ban_ghi=str(row.get("khoa_ban_ghi", "")).strip(),
            ngay_hieu_luc=_parse_date(row.get("ngay_hieu_luc"), "metadata_pit.ngay_hieu_luc"),
            nguon=str(row.get("nguon", "")).strip(),
            phien_ban=str(row.get("phien_ban", "")).strip(),
            thoi_diem_cong_bo=_parse_datetime(row.get("thoi_diem_cong_bo"), "metadata_pit.thoi_diem_cong_bo"),
            du_lieu=data,
        )
        records.append(record)
        if record.loai_du_lieu == "corporate_action":
            events.append(data)
    return _DocPIT(
        tuple(records), tuple(events),
        _unique((x.nguon for x in records), "nguon metadata PIT"),
        _unique((x.phien_ban for x in records), "phien_ban metadata PIT"),
    )


def _signal_time(day: date) -> datetime:
    return datetime.combine(day, GIO_TAO_TIN_HIEU, tzinfo=MUI_GIO_VIET_NAM)


def _json_ready(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, float):
        xac_thuc_so_huu_han(value, "json")
    return value


def _json_text(value: object) -> str:
    return json.dumps(_json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def _csv_text(fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        normalized = {}
        for name in fieldnames:
            value = row.get(name)
            if isinstance(value, bool):
                normalized[name] = "true" if value else "false"
            elif isinstance(value, (date, datetime)):
                normalized[name] = value.isoformat()
            elif value is None:
                normalized[name] = ""
            elif isinstance(value, float):
                xac_thuc_so_huu_han(value, f"csv.{name}")
                normalized[name] = format(value, ".17g")
            else:
                normalized[name] = value
        writer.writerow(normalized)
    return stream.getvalue()


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


def _m3_price_rows(rows: Sequence[ThanhOHLCV]) -> list[object]:
    from he_thong_dinh_luong.mo_phong.mo_hinh import thanh_gia
    return [thanh_gia(
        ma=row.ma, ngay=row.ngay, gia_mo_cua=Decimal(str(row.gia_mo_cua)),
        gia_dong_cua=Decimal(str(row.gia_dong_cua)), khoi_luong=row.khoi_luong,
        thuoc_tap_co_phieu=True, dat_thanh_khoan=True,
    ) for row in sorted(rows, key=lambda x: (x.ngay, x.ma))]


def _m3_config(data: Mapping[str, object], basis: str) -> object:
    from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong
    mapping = dict(data)
    mapping["co_so_gia"] = "dieu_chinh" if basis == "gia_dieu_chinh" else "khong_dieu_chinh"
    if mapping.get("che_do_ma_khong_xuat_hien") != "muc_tieu_bang_0":
        raise ValueError("Backtest Moc 4 bat buoc che_do_ma_khong_xuat_hien=muc_tieu_bang_0.")
    return cau_hinh_mo_phong.tu_mapping(mapping)


def _m3_events(records: Sequence[BanGhiPointInTime], basis: str, signal_dates: Sequence[date]) -> list[object]:
    if not records:
        return []
    accepted: list[Mapping[str, object]] = []
    signal_times = [_signal_time(day) for day in signal_dates]
    for record in records:
        if record.loai_du_lieu != "corporate_action":
            continue
        usable = any(record.thoi_diem_cong_bo <= instant and instant.date() <= record.ngay_hieu_luc for instant in signal_times)
        if usable:
            accepted.append(record.du_lieu)
    if not accepted:
        return []
    from he_thong_dinh_luong.mo_phong.mo_hinh import chuan_hoa_su_kien
    return chuan_hoa_su_kien(accepted, co_so_gia="dieu_chinh" if basis == "gia_dieu_chinh" else "khong_dieu_chinh")


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
    pipeline = getattr(training, "pipeline", None)
    if pipeline is None:
        return []
    scaler = pipeline.named_steps["standard_scaler"]
    result: list[dict[str, object]] = []
    for role in ("train", "validation", "refit_train_validation", "test"):
        samples = list(selected[role])
        if not samples:
            continue
        transformed = scaler.transform([sample.feature for sample in samples])
        for sample, values in zip(samples, transformed, strict=True):
            row: dict[str, object] = {
                "fold": fold.fold, "model_id": training.model_id, "vai_tro_du_lieu": role,
                "ngay": sample.ngay.isoformat(), "ma": sample.ma,
            }
            row.update({name: float(value) for name, value in zip(feature_order, values, strict=True)})
            result.append(row)
    return result


def _product_rows_targets(strategy: str, targets: Sequence[object]) -> list[dict[str, object]]:
    return [{
        "chien_luoc": strategy,
        "ngay_tin_hieu": target.ngay_tin_hieu,
        "ma": target.ma,
        "ty_trong_muc_tieu": float(target.ty_trong),
    } for target in targets]


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
    benchmark_doc = _doc_ohlcv(paths["benchmark"], benchmark=True)
    calendar = _doc_calendar(paths["lich_benchmark"])
    universe_records, universe_source, universe_version = _doc_universe(paths["universe"])
    pit_doc = _doc_pit(paths["corporate_actions"])
    benchmark_source = benchmark_doc.nguon
    benchmark_version = benchmark_doc.phien_ban
    if any(row.co_so_gia != config.co_so_gia for row in [*stock_doc.rows, *benchmark_doc.rows]):
        raise ValueError("Co so gia OHLCV/benchmark khong khop cau hinh.")

    sample_dates = phien_cuoi_thang(calendar)
    symbols = tuple(sorted({record.ma for record in universe_records} | {row.ma for row in stock_doc.rows}))
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
    universe_rows: list[object] = []
    exclusion_rows: list[DongLoai] = []
    eligible: set[tuple[date, str]] = set()
    coverage_by_day: dict[date, tuple[int, int]] = {}
    less_top_k: list[date] = []
    for day in sample_dates:
        signal_time = _signal_time(day)
        states = xac_dinh_universe(
            universe_records, ngay=day, thoi_diem_tao_tin_hieu=signal_time, cac_ma=symbols,
        )
        universe_rows.extend(states)
        benchmark_metadata = chon_ban_ghi_pit(
            pit_doc.records, ngay=day, thoi_diem_tao_tin_hieu=signal_time,
            loai_du_lieu="benchmark_metadata",
        )
        metadata_ok = bool(benchmark_metadata) or not pit_doc.records
        denominator = sum(state.thuoc_universe for state in states)
        numerator = 0
        for state in states:
            key = (day, state.ma)
            reasons: set[str] = set()
            if not state.thuoc_universe:
                reasons.add(state.ly_do or "khong_thuoc_universe")
            feature = feature_map.get(key)
            if feature is None:
                reasons.add("thieu_feature")
            elif not feature.hop_le:
                reasons.update(feature.ly_do)
            if not metadata_ok:
                reasons.add("thieu_benchmark_metadata_pit")
            label = label_map.get(key)
            if label is None or label.nhan is None:
                reasons.add(label.ly_do_nhan_rong if label is not None else "thieu_nhan")
            if state.thuoc_universe and feature is not None and feature.hop_le and metadata_ok:
                eligible.add(key)
                numerator += 1
            for reason in sorted(reasons):
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
        model_rows.append({
            "fold": fold.fold, "model_id": result.model_id, "thanh_cong": result.thanh_cong,
            "C": result.C, "validation_log_loss": result.validation_log_loss,
            "validation_auc": result.validation_auc, "ly_do_that_bai": result.ly_do_that_bai,
            "thoi_diem_huan_luyen": result.metadata.get("thoi_diem_huan_luyen"),
            "thoi_diem_tao_tin_hieu": result.metadata.get("thoi_diem_tao_tin_hieu"),
            "cutoff_feature": result.metadata.get("cutoff_feature"),
            "cutoff_nhan": result.metadata.get("cutoff_nhan"),
        })
        logistic_validation.extend(result.validation_predictions)
        if not result.thanh_cong:
            fold_errors.append({"fold": fold.fold, "ly_do": result.ly_do_that_bai or "fold_that_bai"})
            continue
        test_predictions = list(du_doan_test(result, selected["test"]))
        logistic_test.extend(test_predictions)
        baseline_test.extend(du_doan_baseline_test(
            fold=fold.fold, samples=selected["test"], momentum_theo_khoa=momentum_map,
        ))
        successful_test_dates.extend(fold.test_dates)
        successful_fold_count += 1
        processed_rows.extend(_processed_rows(fold, selected, result, config.feature_order))
        coefficients = list(result.metadata.get("coefficients", []))
        for name, coefficient in zip(config.feature_order, coefficients, strict=True):
            coefficient_rows.append({
                "fold": fold.fold, "model_id": result.model_id, "feature": name,
                "he_so": float(coefficient), "intercept": "",
            })
        intercept = list(result.metadata.get("intercept", []))
        if intercept:
            coefficient_rows.append({
                "fold": fold.fold, "model_id": result.model_id, "feature": "__intercept__",
                "he_so": "", "intercept": float(intercept[0]),
            })

    xac_thuc_prediction_test(logistic_test)
    xac_thuc_prediction_test(baseline_test)
    logistic_rankings, logistic_cash = xep_hang_test(logistic_test, top_k=config.top_k)
    baseline_rankings, baseline_cash = xep_hang_baseline_test(baseline_test, top_k=config.top_k)
    successful_test_dates = sorted(set(successful_test_dates))
    m3_config = _m3_config(m3_raw, config.co_so_gia)
    warnings = list(xac_thuc_co_so_gia_va_su_kien(config, so_su_kien=len(pit_doc.event_rows)))
    events = _m3_events(pit_doc.records, config.co_so_gia, successful_test_dates)
    price_rows = _m3_price_rows(stock_doc.rows)
    logistic_backtest = chay_backtest_oos_lien_tuc(
        rankings=logistic_rankings, du_lieu_gia=price_rows, cau_hinh_mo_phong=m3_config,
        cac_su_kien=events, ngay_tai_can_bang=successful_test_dates,
        cac_ma_lien_quan=symbols, ten_chien_luoc="m4_logistic_oos",
    )
    baseline_backtest = chay_backtest_oos_lien_tuc(
        rankings=baseline_rankings, du_lieu_gia=price_rows, cau_hinh_mo_phong=m3_config,
        cac_su_kien=events, ngay_tai_can_bang=successful_test_dates,
        cac_ma_lien_quan=symbols, ten_chien_luoc="m4_momentum_oos",
    )
    logistic_model_metrics = metric_model_test(logistic_test)
    baseline_model_metrics = metric_baseline_test(baseline_test)
    logistic_ranking_metrics = metric_ranking_test(logistic_rankings)
    baseline_ranking_metrics = metric_ranking_test(baseline_rankings)
    logistic_backtest_metrics = _backtest_metrics(logistic_backtest)
    baseline_backtest_metrics = _backtest_metrics(baseline_backtest)

    sessions_by_symbol: dict[str, set[date]] = {symbol: set() for symbol in symbols}
    for row in stock_doc.rows:
        sessions_by_symbol.setdefault(row.ma, set()).add(row.ngay)
    calendar_set = set(calendar)
    gap_symbols = [symbol for symbol in symbols if not calendar_set.issubset(sessions_by_symbol.get(symbol, set()))]
    warmup_symbols = sorted({row.ma for row in features if any("ma250" in reason or "thieu_warm_up" in reason for reason in row.ly_do)})
    failed_symbols = [symbol for symbol in symbols if not sessions_by_symbol.get(symbol)]
    missing_ca = symbols if config.co_so_gia == "gia_khong_dieu_chinh" and not config.corporate_actions_day_du else ()
    coverage = bao_cao_do_phu(
        exclusion_rows, loi_fold=fold_errors, cac_ngay_yeu_cau=calendar,
        cac_ngay_thuc_te=[row.ngay for row in stock_doc.rows], cac_ma_universe=symbols,
        phien_co_du_lieu_theo_ma=sessions_by_symbol, coverage_theo_ngay=coverage_by_day,
        ma_that_bai_hoan_toan=failed_symbols, ma_thieu_warm_up=warmup_symbols,
        ma_co_gap=gap_symbols, ma_loi_gia=stock_doc.ma_loi_gia,
        ma_loi_volume=stock_doc.ma_loi_volume, ma_thieu_corporate_actions=missing_ca,
        ngay_it_hon_top_k=less_top_k, nguon_ohlcv=stock_doc.nguon,
        phien_ban_ohlcv=stock_doc.phien_ban, nguon_universe=universe_source,
        phien_ban_universe=universe_version, nguon_benchmark=benchmark_source,
        phien_ban_benchmark=benchmark_version, co_so_gia=config.co_so_gia,
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
        item: dict[str, object] = {"ngay": row.ngay, "ma": row.ma, "hop_le": row.hop_le, "ly_do": "|".join(row.ly_do)}
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
        "chien_luoc": "logistic" if row.model_id.endswith("_logistic") else "momentum_baseline",
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
        "KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC",
        "KHONG_LIGHTGBM_KHONG_SSI_KHONG_MOC_5",
    ]
    report = {
        "ma_lan_chay": ma_lan_chay, "so_fold": len(folds),
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
        "feature_raw.csv": _csv_text(("ngay", "ma", "hop_le", "ly_do", *config.feature_order), feature_product_rows),
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
            ("fold", "model_id", "thanh_cong", "C", "validation_log_loss", "validation_auc", "ly_do_that_bai", "thoi_diem_huan_luyen", "thoi_diem_tao_tin_hieu", "cutoff_feature", "cutoff_nhan"),
            model_rows,
        ),
        "he_so_logistic.csv": _csv_text(("fold", "model_id", "feature", "he_so", "intercept"), coefficient_rows),
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
        "nguon_ohlcv": stock_doc.nguon, "phien_ban_ohlcv": stock_doc.phien_ban,
        "nguon_universe": universe_source, "phien_ban_universe": universe_version,
        "nguon_benchmark": benchmark_source, "phien_ban_benchmark": benchmark_version,
        "co_so_gia": config.co_so_gia, "muc_dich_lan_chay": config.muc_dich_lan_chay,
        "cau_hinh_feature": {"feature_order": list(config.feature_order), "feature_bat_buoc": list(config.feature_bat_buoc), "tan_suat": "cuoi_thang", "lich": "benchmark_chinh_thuc"},
        "cau_hinh_label": {"horizon": config.label_horizon, "lich": "benchmark_chinh_thuc"},
        "cau_hinh_fold": {"expanding": True, "purge_phien": config.purge_phien, "embargo_phien": config.embargo_phien, "so_thang_validation": config.so_thang_validation, "so_thang_test": config.so_thang_test},
        "cau_hinh_model": {"standard_scaler": True, "penalty": "l2", "solver": config.solver, "max_iter": config.max_iter, "C_grid": list(config.C_grid), "seed": config.seed},
        "cau_hinh_ranking": {"top_k": config.top_k, "tie_break": "ma_tang_dan", "ty_trong": "1/top_k", "phan_thieu": "tien_mat"},
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
