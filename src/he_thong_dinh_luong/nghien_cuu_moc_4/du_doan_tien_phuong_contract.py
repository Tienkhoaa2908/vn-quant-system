"""Forward prediction và LightGBM champion-challenger trên sản phẩm Mốc 4.

Module chỉ đọc ZIP sản phẩm Mốc 4 đã công bố. LightGBM được import lười để CI
không phải mang dependency thường trực; workstation chạy bằng ``uv run --with``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping
from zipfile import ZipFile

SCHEMA_VERSION = "forward_prediction_lgbm_v1"
REQUIRED_INPUT_FILES = {"manifest.json", "cau_hinh.json", "feature_raw.csv", "nhan.csv", "chi_so_mo_hinh.json"}
STOCK_RANK_FEATURES = (
    "khoang_cach_ma20", "khoang_cach_ma60", "khoang_cach_ma120", "khoang_cach_ma250",
    "ty_le_dinh_52_tuan", "loi_nhuan_20", "loi_nhuan_60", "loi_nhuan_120",
    "loi_nhuan_250", "dong_luong_12_1", "suc_manh_tuong_doi_120", "bien_dong_20",
    "bien_dong_60", "bien_dong_giam_60", "gtgd_tb_20", "gtgd_tb_60",
    "gtgd_hien_tai_tren_tb60", "so_phien_volume_0_60",
)
REGIME_FEATURES = (
    "gia_tren_ma250", "vnindex_tren_ma250", "vnindex_momentum_60",
    "vnindex_bien_dong_20", "vnindex_bien_dong_60",
)
DERIVED_FEATURES = ("momentum_tren_bien_dong", "suc_manh_tren_bien_dong", "do_nhat_quan_momentum")
GRID = (
    {"learning_rate": 0.03, "max_depth": 3, "num_leaves": 7, "min_child_samples": 40, "reg_lambda": 10.0, "feature_fraction": 0.8},
    {"learning_rate": 0.03, "max_depth": 4, "num_leaves": 15, "min_child_samples": 60, "reg_lambda": 10.0, "feature_fraction": 0.8},
    {"learning_rate": 0.05, "max_depth": 3, "num_leaves": 7, "min_child_samples": 80, "reg_lambda": 1.0, "feature_fraction": 0.8},
    {"learning_rate": 0.05, "max_depth": 4, "num_leaves": 15, "min_child_samples": 80, "reg_lambda": 10.0, "feature_fraction": 0.7},
)

@dataclass(frozen=True)
class Row:
    ngay: date
    ma: str
    features: Mapping[str, float]
    relative_return: float | None = None
    label_end: date | None = None

@dataclass(frozen=True)
class Metrics:
    mean_rank_ic: float
    precision_at_k: float
    top_k_relative_return: float
    mean_set_turnover: float
    day_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "mean_rank_ic": self.mean_rank_ic,
            "precision_at_k": self.precision_at_k,
            "top_k_relative_return": self.top_k_relative_return,
            "mean_set_turnover": self.mean_set_turnover,
            "day_count": self.day_count,
        }

def _hash_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()

def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_zip_names(names: Iterable[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"INPUT_ZIP_UNSAFE_PATH:{name}")

def _load_verified_input(path: Path) -> tuple[dict[str, bytes], dict[str, object], str]:
    zip_path = Path(path)
    if not zip_path.is_file():
        raise ValueError("INPUT_ZIP_MISSING")
    source_sha = _hash_file(zip_path)
    with ZipFile(zip_path) as archive:
        names = archive.namelist()
        _safe_zip_names(names)
        missing = sorted(REQUIRED_INPUT_FILES - set(names))
        if missing:
            raise ValueError(f"INPUT_ZIP_REQUIRED_FILES_MISSING:{missing}")
        blobs = {name: archive.read(name) for name in REQUIRED_INPUT_FILES}
    manifest = json.loads(blobs["manifest.json"])
    if not isinstance(manifest, dict):
        raise ValueError("INPUT_MANIFEST_INVALID")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("INPUT_MANIFEST_FILES_INVALID")
    for name in sorted(REQUIRED_INPUT_FILES - {"manifest.json"}):
        record = files.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"INPUT_MANIFEST_RECORD_MISSING:{name}")
        observed = blobs[name]
        if record.get("sha256") != _hash_bytes(observed):
            raise ValueError(f"INPUT_FILE_SHA_MISMATCH:{name}")
        if record.get("size") != len(observed):
            raise ValueError(f"INPUT_FILE_SIZE_MISMATCH:{name}")
    return blobs, manifest, source_sha

def _parse_bool(value: object, field: str) -> bool:
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"BOOLEAN_INVALID:{field}:{value}")

def _parse_float(value: object, field: str, *, allow_empty: bool = False) -> float | None:
    text = str(value).strip()
    if not text and allow_empty:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"FLOAT_INVALID:{field}:{value}") from exc
    if not isfinite(result):
        raise ValueError(f"FLOAT_NONFINITE:{field}")
    return result

def _parse_date(value: object, field: str, *, allow_empty: bool = False) -> date | None:
    text = str(value).strip()
    if not text and allow_empty:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"DATE_INVALID:{field}:{value}") from exc

def _csv_rows(payload: bytes, name: str) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"CSV_NOT_UTF8:{name}") from exc
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError(f"CSV_HEADER_MISSING:{name}")
    return [dict(row) for row in reader]

def _feature_order(config_blob: bytes) -> tuple[str, ...]:
    config = json.loads(config_blob)
    if not isinstance(config, dict):
        raise ValueError("CONFIG_INVALID")
    raw = config.get("moc_4", config)
    if not isinstance(raw, dict):
        raise ValueError("CONFIG_M4_INVALID")
    order = raw.get("feature_order")
    if not isinstance(order, list) or not order:
        raise ValueError("CONFIG_FEATURE_ORDER_INVALID")
    normalized = tuple(str(item) for item in order)
    missing = sorted((set(STOCK_RANK_FEATURES) | set(REGIME_FEATURES)) - set(normalized))
    if missing:
        raise ValueError(f"CONFIG_FEATURES_MISSING:{missing}")
    return normalized

def _load_rows(blobs: Mapping[str, bytes]) -> tuple[list[Row], list[Row], date]:
    order = _feature_order(blobs["cau_hinh.json"])
    labels: dict[tuple[date, str], tuple[float | None, date | None]] = {}
    for raw in _csv_rows(blobs["nhan.csv"], "nhan.csv"):
        day = _parse_date(raw.get("ngay"), "nhan.ngay")
        assert day is not None
        symbol = str(raw.get("ma", "")).strip().upper()
        if not symbol:
            raise ValueError("LABEL_SYMBOL_EMPTY")
        key = (day, symbol)
        if key in labels:
            raise ValueError(f"LABEL_DUPLICATE:{day}:{symbol}")
        relative = _parse_float(raw.get("loi_nhuan_tuong_doi", ""), "nhan.loi_nhuan_tuong_doi", allow_empty=True)
        label_end = _parse_date(raw.get("ngay_ket_thuc_nhan", ""), "nhan.ngay_ket_thuc_nhan", allow_empty=True)
        labels[key] = (relative, label_end)
    history: list[Row] = []
    candidates: list[tuple[date, Row]] = []
    seen: set[tuple[date, str]] = set()
    for raw in _csv_rows(blobs["feature_raw.csv"], "feature_raw.csv"):
        day = _parse_date(raw.get("ngay"), "feature.ngay")
        assert day is not None
        symbol = str(raw.get("ma", "")).strip().upper()
        if not symbol:
            raise ValueError("FEATURE_SYMBOL_EMPTY")
        key = (day, symbol)
        if key in seen:
            raise ValueError(f"FEATURE_DUPLICATE:{day}:{symbol}")
        seen.add(key)
        hop_le = _parse_bool(raw.get("hop_le"), "feature.hop_le")
        eligible = _parse_bool(raw.get("eligible"), "feature.eligible")
        values: dict[str, float] = {}
        complete = True
        for name in order:
            raw_value = raw.get(name, "")
            if name in {"gia_tren_ma250", "vnindex_tren_ma250"}:
                value = None if str(raw_value).strip() == "" else (1.0 if _parse_bool(raw_value, f"feature.{name}") else 0.0)
            else:
                value = _parse_float(raw_value, f"feature.{name}", allow_empty=True)
            if value is None:
                complete = False
                break
            values[name] = value
        if not hop_le or not complete:
            continue
        relative, label_end = labels.get(key, (None, None))
        row = Row(day, symbol, values, relative, label_end)
        candidates.append((day, row))
        if eligible and relative is not None and label_end is not None:
            history.append(row)
    if not candidates:
        raise ValueError("NO_COMPLETE_FEATURE_ROWS")
    latest_day = max(day for day, _ in candidates)
    forward = [row for day, row in candidates if day == latest_day]
    if not forward:
        raise ValueError("NO_FORWARD_ROWS")
    if not history:
        raise ValueError("NO_LABELED_HISTORY")
    return sorted(history, key=lambda item: (item.ngay, item.ma)), sorted(forward, key=lambda item: item.ma), latest_day
