"""Cong bo san pham bat bien bang staging, fsync, atomic rename va SHA-256."""
from __future__ import annotations

import csv
import hashlib
from io import StringIO
import json
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


def _bytes(value: str | bytes) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else value


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def cong_bo_san_pham(
    thu_muc_dich: Path,
    san_pham: Mapping[str, str | bytes],
    *,
    metadata: Mapping[str, object],
) -> Path:
    destination = Path(thu_muc_dich)
    if destination.exists():
        raise FileExistsError("Khong ghi de thu muc san pham.")
    missing = sorted(set(TEN_SAN_PHAM) - set(san_pham))
    extra = sorted(set(san_pham) - set(TEN_SAN_PHAM))
    if missing or extra:
        raise ValueError(f"Tap san pham sai hop dong; thieu={missing}, thua={extra}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        hashes: dict[str, dict[str, object]] = {}
        for name in TEN_SAN_PHAM:
            payload = _bytes(san_pham[name])
            path = staging / name
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            hashes[name] = {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
        manifest = {
            "trang_thai": "thanh_cong",
            "metadata": dict(sorted(metadata.items())),
            "files": hashes,
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
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


COT_FEATURE_SAU_TIEN_XU_LY = ("fold", "model_id", "vai_tro_du_lieu", "ngay", "ma")
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
        if role not in {"train", "validation", "refit_train_validation", "test"}:
            raise ValueError("vai_tro_du_lieu feature khong hop le.")
        if tuple(row) != fieldnames:
            raise ValueError("Cot feature_sau_tien_xu_ly khong dung thu tu/hop dong.")
        key = tuple(row[name] for name in COT_FEATURE_SAU_TIEN_XU_LY)
        if key in keys:
            raise ValueError("Trung khoa feature_sau_tien_xu_ly.")
        keys.add(key)
        normalized.append(row)
    normalized.sort(key=lambda x: (str(x["fold"]), str(x["model_id"]), str(x["vai_tro_du_lieu"]), str(x["ngay"]), str(x["ma"])))
    return _csv_on_dinh(normalized, fieldnames)


def tao_csv_du_doan(predictions: Iterable[object]) -> str:
    rows: list[dict[str, object]] = []
    keys: set[tuple[object, ...]] = set()
    for item in predictions:
        role = getattr(item, "vai_tro_du_lieu")
        if role not in {"validation", "test"}:
            raise ValueError("du_doan.csv chi chap nhan validation hoac test.")
        row = {
            "fold": getattr(item, "fold"),
            "model_id": getattr(item, "model_id"),
            "vai_tro_du_lieu": role,
            "ngay": getattr(item, "ngay").isoformat(),
            "ma": getattr(item, "ma"),
            "xac_suat_nhan_1": format(float(getattr(item, "xac_suat_nhan_1")), ".17g"),
        }
        key = tuple(row[name] for name in COT_DU_DOAN[:-1])
        if key in keys:
            raise ValueError("Trung khoa du_doan.csv.")
        keys.add(key)
        rows.append(row)
    rows.sort(key=lambda x: (str(x["fold"]), str(x["model_id"]), str(x["vai_tro_du_lieu"]), str(x["ngay"]), str(x["ma"])))
    return _csv_on_dinh(rows, COT_DU_DOAN)
