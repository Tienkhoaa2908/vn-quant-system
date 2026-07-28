"""Facade VN100: giu bo dieu phoi/kiem toan cu va them hop dong rut gon."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import uuid
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import _tai_du_lieu_vn100_co_so as _co_so
from ._tai_du_lieu_vn100_co_so import *  # noqa: F401,F403
from ._tai_du_lieu_vn100_co_so import (
    _doc_raw,
    _ngay,
    _sha256,
    _so,
    _tim_raw,
)
from .du_lieu_thi_truong.quy_trinh import lam_sach_loi

CO_SO_GIA_CHUA_XAC_NHAN = "CHUA_XAC_NHAN"
CAC_CANH_BAO_HOP_DONG_RUT_GON = (
    "HIGH_LOW_SEMANTICS_CHUA_XAC_NHAN",
    "PRICE_BASIS_CHUA_XAC_NHAN",
    "CORPORATE_ACTIONS_CHUA_DAY_DU",
    "CHI_DUNG_CHO_KIEM_TRA_KY_THUAT",
)
COT_HOP_DONG_RUT_GON = (
    "ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong",
    "nguon", "phien_ban", "co_so_gia", "raw_sha256",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: Mapping[str, Any]) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"


def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    memory = StringIO(newline="")
    writer = csv.DictWriter(
        memory, fieldnames=COT_HOP_DONG_RUT_GON, lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in COT_HOP_DONG_RUT_GON})
    return memory.getvalue().encode("utf-8")


def _dinh_dang_so(value: float) -> str:
    if value == 0:
        return "0"
    if value.is_integer():
        return str(int(value))
    return format(value, ".15g")


def _cong_bo_bat_bien(destination: Path, files: Mapping[str, bytes]) -> None:
    if destination.exists():
        raise FileExistsError(f"Khong duoc ghi de thu muc san pham: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    staging.mkdir()
    try:
        for name, data in sorted(files.items()):
            with (staging / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(staging, destination)
    finally:
        if staging.exists():
            for path in staging.iterdir():
                path.unlink(missing_ok=True)
            staging.rmdir()


def _ly_do_loai(
    symbol: str,
    raw: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    actual_hash: str,
    expected_hash: str | None,
) -> list[str]:
    reasons: list[str] = []
    if not expected_hash:
        reasons.append("AUDIT_RAW_SHA256_MISSING")
    elif expected_hash != actual_hash:
        reasons.append("RAW_SHA256_MISMATCH")
    if str(raw.get("ma", "")).strip().upper() != symbol:
        reasons.append("RAW_IDENTITY_MISMATCH")
    if not str(raw.get("nguon", "")).strip():
        reasons.append("SOURCE_MISSING")
    if not str(raw.get("phien_ban", "")).strip():
        reasons.append("VERSION_MISSING")
    columns = {str(value) for value in raw.get("cac_cot", [])}
    if not {"time", "open", "close", "volume"}.issubset(columns):
        reasons.append("REQUIRED_COLUMNS_MISSING")
    days = [_ngay(row.get("time")) for row in rows]
    if not rows:
        reasons.append("NO_ROWS")
    if any(not day for day in days):
        reasons.append("INVALID_DATE")
    if len(days) != len(set(days)):
        reasons.append("DUPLICATE_DATE")
    if days != sorted(days) or any(left >= right for left, right in zip(days, days[1:])):
        reasons.append("DATE_NOT_STRICTLY_INCREASING")
    for row in rows:
        open_value = _so(row.get("open"))
        close_value = _so(row.get("close"))
        volume_value = _so(row.get("volume"))
        if open_value is None:
            reasons.append("OPEN_NON_FINITE")
        elif open_value <= 0:
            reasons.append("OPEN_NON_POSITIVE")
        if close_value is None:
            reasons.append("CLOSE_NON_FINITE")
        elif close_value <= 0:
            reasons.append("CLOSE_NON_POSITIVE")
        if volume_value is None:
            reasons.append("VOLUME_NON_FINITE")
        elif volume_value < 0:
            reasons.append("VOLUME_NEGATIVE")
    return sorted(set(reasons))


def chuyen_doi_hop_dong_rut_gon_vn100(
    *,
    danh_sach_ma: Path,
    thu_muc_tho: Path,
    tien_to_lan_chay: str,
    bao_cao_kiem_toan: Path,
    thu_muc_san_pham: Path,
    ma_lan_chay: str,
) -> dict[str, Any]:
    """Tao publication open/close/volume tu raw da co, khong goi mang."""
    symbols = tuple(sorted(doc_danh_sach_ma(danh_sach_ma)))
    audit = json.loads(bao_cao_kiem_toan.read_text(encoding="utf-8"))
    states = audit.get("trang_thai_tung_ma", {}) if isinstance(audit, Mapping) else {}
    if not isinstance(states, Mapping):
        raise ValueError("bao cao kiem toan thieu trang_thai_tung_ma")
    selected, candidates = _tim_raw(thu_muc_tho, tien_to_lan_chay)
    reduced: list[dict[str, str]] = []
    coverage: dict[str, Any] = {}
    excluded: dict[str, Any] = {}
    raw_manifest: list[dict[str, Any]] = []

    for symbol in symbols:
        path = selected.get(symbol)
        if path is None:
            reasons = ["RAW_NOT_FOUND"]
            excluded[symbol] = {"ma": symbol, "ly_do": reasons}
            coverage[symbol] = {
                "ma": symbol, "trang_thai": "BI_LOAI", "so_dong": 0,
                "ngay_dau": None, "ngay_cuoi": None, "ly_do": reasons,
            }
            continue
        actual_hash = _sha256(path)
        audit_item = states.get(symbol, {})
        expected_hash = None
        if isinstance(audit_item, Mapping):
            expected_hash = str(
                audit_item.get("ma_sha256_da_kiem_tra_lai")
                or audit_item.get("ma_sha256") or ""
            ) or None
        try:
            raw = _doc_raw(path)
            rows = [row for row in raw["du_lieu"] if isinstance(row, Mapping)]
            reasons = _ly_do_loai(
                symbol, raw, rows,
                actual_hash=actual_hash, expected_hash=expected_hash,
            )
        except Exception as exc:
            raw, rows = {}, []
            reasons = ["RAW_UNREADABLE", lam_sach_loi(exc)]
        relative_path = path.relative_to(thu_muc_tho).as_posix()
        raw_manifest.append({
            "ma": symbol,
            "duong_dan_tuong_doi": relative_path,
            "raw_sha256": actual_hash,
            "raw_sha256_kiem_toan": expected_hash,
            "trang_thai": "BI_LOAI" if reasons else "DAT",
            "so_ung_vien_raw": len(candidates.get(symbol, [])),
        })
        if reasons:
            excluded[symbol] = {
                "ma": symbol, "ly_do": reasons,
                "duong_dan_tuong_doi": relative_path,
                "raw_sha256": actual_hash,
            }
            coverage[symbol] = {
                "ma": symbol, "trang_thai": "BI_LOAI", "so_dong": len(rows),
                "ngay_dau": None, "ngay_cuoi": None, "ly_do": reasons,
                "raw_sha256": actual_hash,
            }
            continue
        source = str(raw["nguon"]).strip()
        version = str(raw["phien_ban"]).strip()
        days = [_ngay(row.get("time")) for row in rows]
        for day, row in zip(days, rows):
            open_value = _so(row.get("open"))
            close_value = _so(row.get("close"))
            volume_value = _so(row.get("volume"))
            assert open_value is not None and close_value is not None
            assert volume_value is not None
            reduced.append({
                "ma": symbol,
                "ngay": day,
                "gia_mo_cua": _dinh_dang_so(open_value),
                "gia_dong_cua": _dinh_dang_so(close_value),
                "khoi_luong": _dinh_dang_so(volume_value),
                "nguon": source,
                "phien_ban": version,
                "co_so_gia": CO_SO_GIA_CHUA_XAC_NHAN,
                "raw_sha256": actual_hash,
            })
        coverage[symbol] = {
            "ma": symbol, "trang_thai": "DAT", "so_dong": len(rows),
            "ngay_dau": days[0], "ngay_cuoi": days[-1],
            "raw_sha256": actual_hash, "nguon": source, "phien_ban": version,
        }

    reduced.sort(key=lambda row: (row["ma"], row["ngay"]))
    coverage_report = {
        "schema_version": "1.0",
        "ma_lan_chay": ma_lan_chay,
        "hop_dong": "GIA_MO_CUA_DONG_CUA_KHOI_LUONG_KY_THUAT_MOC_4",
        "tong_ma": len(symbols),
        "so_ma_dat": sum(item["trang_thai"] == "DAT" for item in coverage.values()),
        "so_ma_bi_loai": sum(item["trang_thai"] == "BI_LOAI" for item in coverage.values()),
        "tong_so_dong": len(reduced),
        "canh_bao_bat_buoc": list(CAC_CANH_BAO_HOP_DONG_RUT_GON),
        "trang_thai_tung_ma": dict(sorted(coverage.items())),
    }
    excluded_report = {
        "schema_version": "1.0", "ma_lan_chay": ma_lan_chay,
        "so_ma_bi_loai": len(excluded),
        "ma_bi_loai": dict(sorted(excluded.items())),
    }
    csv_data = _csv_bytes(reduced)
    coverage_data = _json_bytes(coverage_report)
    excluded_data = _json_bytes(excluded_report)
    product_hashes = {
        "du_lieu_gia_mo_dong_khoi_luong.csv": _sha256_bytes(csv_data),
        "bao_cao_do_phu_hop_dong_rut_gon.json": _sha256_bytes(coverage_data),
        "bao_cao_ma_bi_loai.json": _sha256_bytes(excluded_data),
    }
    manifest = {
        "schema_version": "1.0", "ma_lan_chay": ma_lan_chay,
        "hop_dong": {
            "ten": "GIA_MO_CUA_DONG_CUA_KHOI_LUONG_KY_THUAT_MOC_4",
            "cot": list(COT_HOP_DONG_RUT_GON),
            "co_so_gia": CO_SO_GIA_CHUA_XAC_NHAN,
            "high_low_trong_san_pham": False,
            "chi_dung_kiem_tra_ky_thuat": True,
        },
        "dau_vao": {
            "danh_sach_ma_sha256": _sha256(danh_sach_ma),
            "bao_cao_kiem_toan_sha256": _sha256(bao_cao_kiem_toan),
            "tien_to_lan_chay": tien_to_lan_chay,
        },
        "raw": sorted(raw_manifest, key=lambda item: item["ma"]),
        "san_pham_sha256": product_hashes,
        "canh_bao_bat_buoc": list(CAC_CANH_BAO_HOP_DONG_RUT_GON),
        "sha256_txt_khong_tu_bam_chinh_no": True,
    }
    manifest_data = _json_bytes(manifest)
    all_hashes = dict(product_hashes)
    all_hashes["manifest.json"] = _sha256_bytes(manifest_data)
    sha_data = "".join(
        f"{digest}  {name}\n" for name, digest in sorted(all_hashes.items())
    ).encode("utf-8")
    _cong_bo_bat_bien(thu_muc_san_pham, {
        "du_lieu_gia_mo_dong_khoi_luong.csv": csv_data,
        "bao_cao_do_phu_hop_dong_rut_gon.json": coverage_data,
        "bao_cao_ma_bi_loai.json": excluded_data,
        "manifest.json": manifest_data,
        "sha256.txt": sha_data,
    })
    return {
        "ma_lan_chay": ma_lan_chay,
        "thu_muc_san_pham": str(thu_muc_san_pham),
        "so_raw": len(selected),
        "so_ma_dat": coverage_report["so_ma_dat"],
        "so_ma_bi_loai": coverage_report["so_ma_bi_loai"],
        "tong_so_dong": len(reduced),
        "san_pham_sha256": {
            **all_hashes, "sha256.txt": _sha256_bytes(sha_data),
        },
        "manifest_sha256": all_hashes["manifest.json"],
        "trang_thai_tung_ma": coverage_report["trang_thai_tung_ma"],
    }


def _parser_rut_gon() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tao hop dong open/close/volume VN100 hoan toan ngoai tuyen."
    )
    parser.add_argument("--tao-hop-dong-rut-gon", action="store_true", required=True)
    parser.add_argument("--danh-sach-ma", type=Path, required=True)
    parser.add_argument("--thu-muc-tho", type=Path, required=True)
    parser.add_argument("--tien-to-lan-chay", required=True)
    parser.add_argument("--bao-cao-kiem-toan", type=Path, required=True)
    parser.add_argument("--thu-muc-san-pham", type=Path, required=True)
    parser.add_argument("--ma-lan-chay", required=True)
    return parser


def chay() -> int:
    if "--tao-hop-dong-rut-gon" not in sys.argv[1:]:
        return _co_so.chay()
    args = _parser_rut_gon().parse_args()
    result = chuyen_doi_hop_dong_rut_gon_vn100(
        danh_sach_ma=args.danh_sach_ma,
        thu_muc_tho=args.thu_muc_tho,
        tien_to_lan_chay=args.tien_to_lan_chay,
        bao_cao_kiem_toan=args.bao_cao_kiem_toan,
        thu_muc_san_pham=args.thu_muc_san_pham,
        ma_lan_chay=args.ma_lan_chay,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["so_ma_bi_loai"] else 0


if __name__ == "__main__":
    raise SystemExit(chay())
