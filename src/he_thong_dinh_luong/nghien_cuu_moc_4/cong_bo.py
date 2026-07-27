"""Cong bo san pham bat bien bang staging, fsync, atomic rename va SHA-256."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
from math import isfinite
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable, Mapping

TEN_SAN_PHAM = (
    "cau_hinh.json", "bao_cao_do_phu.json", "universe_theo_ngay.csv", "feature_raw.csv",
    "feature_sau_tien_xu_ly.csv", "nhan.csv", "folds.csv", "mo_hinh.csv",
    "he_so_logistic.csv", "du_doan.csv", "xep_hang.csv", "ty_trong_muc_tieu.csv",
    "chi_so_mo_hinh.json", "chi_so_ranking.json", "chi_so_backtest.json", "bao_cao.json",
)

METADATA_BAT_BUOC = {
    "git_commit", "ma_lan_chay", "thoi_diem_utc", "python_version", "uv_version",
    "scikit_learn_version", "nguon_ohlcv", "phien_ban_ohlcv", "nguon_universe",
    "phien_ban_universe", "nguon_benchmark", "phien_ban_benchmark", "co_so_gia",
    "muc_dich_lan_chay", "cau_hinh_feature", "cau_hinh_label", "cau_hinh_fold",
    "cau_hinh_model", "cau_hinh_ranking", "canh_bao", "gioi_han",
}


def _bytes(value: str | bytes) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, bytes):
        return value
    raise TypeError("San pham chi duoc la str hoac bytes.")


def _fsync_dir(path: Path) -> bool:
    """Fsync directory tren POSIX; bao unsupported tren Windows.

    File fsync va atomic replace van duoc thuc hien tren moi nen tang. Python
    tren Windows khong ho tro mo directory bang ``os.open(..., O_RDONLY)``;
    ham vi vay tra ``False`` thay vi gia lap directory fsync thanh cong.
    """
    if os.name == "nt":
        return False

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def _validate_finite(value: object, path: str = "root") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} chua NaN/Inf.")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _validate_finite(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_finite(item, f"{path}[{index}]")
        return
    # Decimal/date/datetime and other deterministic domain values are serialized as strings upstream.


def _validate_json_bytes(payload: bytes, name: str) -> None:
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"{name} chua {value}.")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} khong phai JSON UTF-8 hop le.") from exc
    _validate_finite(decoded, name)


def _validate_csv_bytes(payload: bytes, name: str) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name} khong phai UTF-8.") from exc
    forbidden = {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
    for row_number, row in enumerate(csv.reader(StringIO(text)), 1):
        for column_number, value in enumerate(row, 1):
            if value.strip().lower() in forbidden:
                raise ValueError(f"{name} chua NaN/Inf tai dong {row_number}, cot {column_number}.")


def _validate_product_payload(name: str, payload: bytes) -> None:
    if name.endswith(".json"):
        _validate_json_bytes(payload, name)
    elif name.endswith(".csv"):
        _validate_csv_bytes(payload, name)


def _validate_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    missing = sorted(METADATA_BAT_BUOC - set(metadata))
    if missing:
        raise ValueError(f"Metadata manifest thieu: {', '.join(missing)}.")
    extra_empty = [
        key for key in METADATA_BAT_BUOC
        if metadata.get(key) is None or metadata.get(key) == "" or metadata.get(key) == {}
    ]
    if extra_empty:
        raise ValueError(f"Metadata manifest rong: {', '.join(sorted(extra_empty))}.")
    commit = metadata["git_commit"]
    if not isinstance(commit, str) or len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit.lower()):
        raise ValueError("git_commit phai la SHA 40 ky tu hexa.")
    try:
        timestamp = datetime.fromisoformat(str(metadata["thoi_diem_utc"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("thoi_diem_utc khong hop le.") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("thoi_diem_utc phai co offset UTC.")
    for key in ("cau_hinh_feature", "cau_hinh_label", "cau_hinh_fold", "cau_hinh_model", "cau_hinh_ranking"):
        if not isinstance(metadata[key], Mapping) or not metadata[key]:
            raise ValueError(f"{key} phai la mapping khong rong.")
    if not isinstance(metadata["canh_bao"], (list, tuple)):
        raise ValueError("canh_bao phai la list/tuple.")
    if not isinstance(metadata["gioi_han"], (list, tuple)) or not metadata["gioi_han"]:
        raise ValueError("gioi_han phai la list/tuple khong rong.")
    normalized = dict(metadata)
    _validate_finite(normalized, "metadata")
    return normalized


def _input_bytes(value: Path | str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"Dau vao khong ton tai hoac khong phai tep: {path}.")
    return path.read_bytes()


def cong_bo_san_pham(
    thu_muc_dich: Path,
    san_pham: Mapping[str, str | bytes],
    *,
    metadata: Mapping[str, object],
    dau_vao: Mapping[str, Path | str | bytes],
) -> Path:
    destination = Path(thu_muc_dich)
    if destination.exists():
        raise FileExistsError("Khong ghi de thu muc san pham.")
    missing = sorted(set(TEN_SAN_PHAM) - set(san_pham))
    extra = sorted(set(san_pham) - set(TEN_SAN_PHAM))
    if missing or extra:
        raise ValueError(f"Tap san pham sai hop dong; thieu={missing}, thua={extra}.")
    if not dau_vao:
        raise ValueError("Manifest bat buoc co it nhat mot dau vao de tinh SHA-256.")
    normalized_metadata = _validate_metadata(metadata)
    input_hashes: dict[str, dict[str, object]] = {}
    for name in sorted(dau_vao):
        if not name:
            raise ValueError("Ten dau vao manifest khong duoc rong.")
        payload = _input_bytes(dau_vao[name])
        input_hashes[name] = {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        hashes: dict[str, dict[str, object]] = {}
        for name in TEN_SAN_PHAM:
            payload = _bytes(san_pham[name])
            _validate_product_payload(name, payload)
            path = staging / name
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            hashes[name] = {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
        manifest = {
            "trang_thai": "thanh_cong",
            "metadata": dict(sorted(normalized_metadata.items())),
            "inputs": input_hashes,
            "files": hashes,
        }
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        ).encode("utf-8")
        with (staging / "manifest.json").open("xb") as handle:
            handle.write(manifest_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_dir(staging)
        os.replace(staging, destination)
        _fsync_dir(destination.parent)
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


COT_FEATURE_SAU_TIEN_XU_LY = ("fold", "stage", "model_id", "vai_tro_du_lieu", "ngay", "ma")
COT_DU_DOAN = ("fold", "model_id", "vai_tro_du_lieu", "ngay", "ma", "xac_suat_nhan_1")


def _csv_on_dinh(rows: list[dict[str, object]], fieldnames: tuple[str, ...]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return stream.getvalue()


def tao_csv_feature_sau_tien_xu_ly(rows: Iterable[Mapping[str, object]], feature_order: tuple[str, ...]) -> str:
    fieldnames = COT_FEATURE_SAU_TIEN_XU_LY + feature_order
    normalized: list[dict[str, object]] = []
    keys: set[tuple[object, ...]] = set()
    for raw in rows:
        row = dict(raw)
        role = row.get("vai_tro_du_lieu")
        stage = row.get("stage")
        if role not in {"train", "validation", "refit_train_validation", "test"}:
            raise ValueError("vai_tro_du_lieu feature khong hop le.")
        if stage not in {"validation_selection", "final_refit"}:
            raise ValueError("stage feature khong hop le.")
        if stage == "validation_selection" and role not in {"train", "validation"}:
            raise ValueError("validation_selection chi duoc cong bo train/validation.")
        if stage == "final_refit" and role not in {"refit_train_validation", "test"}:
            raise ValueError("final_refit chi duoc cong bo refit/test.")
        if tuple(row) != fieldnames:
            raise ValueError("Cot feature_sau_tien_xu_ly khong dung thu tu/hop dong.")
        for name in feature_order:
            value = row[name]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(float(value)):
                raise ValueError("feature_sau_tien_xu_ly chua gia tri khong huu han.")
        key = tuple(row[name] for name in COT_FEATURE_SAU_TIEN_XU_LY)
        if key in keys:
            raise ValueError("Trung khoa feature_sau_tien_xu_ly.")
        keys.add(key)
        normalized.append(row)
    normalized.sort(key=lambda x: (str(x["fold"]), str(x["stage"]), str(x["model_id"]), str(x["vai_tro_du_lieu"]), str(x["ngay"]), str(x["ma"])))
    return _csv_on_dinh(normalized, fieldnames)


def tao_csv_du_doan(predictions: Iterable[object]) -> str:
    rows: list[dict[str, object]] = []
    keys: set[tuple[object, ...]] = set()
    for item in predictions:
        role = getattr(item, "vai_tro_du_lieu")
        if role not in {"validation", "test"}:
            raise ValueError("du_doan.csv chi chap nhan validation hoac test.")
        probability = float(getattr(item, "xac_suat_nhan_1"))
        if not isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("du_doan.csv chua probability khong hop le.")
        row = {
            "fold": getattr(item, "fold"), "model_id": getattr(item, "model_id"),
            "vai_tro_du_lieu": role, "ngay": getattr(item, "ngay").isoformat(),
            "ma": getattr(item, "ma"), "xac_suat_nhan_1": format(probability, ".17g"),
        }
        key = tuple(row[name] for name in COT_DU_DOAN[:-1])
        if key in keys:
            raise ValueError("Trung khoa du_doan.csv.")
        keys.add(key)
        rows.append(row)
    rows.sort(key=lambda x: (str(x["fold"]), str(x["model_id"]), str(x["vai_tro_du_lieu"]), str(x["ngay"]), str(x["ma"])))
    return _csv_on_dinh(rows, COT_DU_DOAN)
