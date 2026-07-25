"""Cong bo san pham bat bien bang staging, fsync, atomic rename va SHA-256."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

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
