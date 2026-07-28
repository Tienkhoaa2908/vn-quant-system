"""Dieu phoi tai va kiem toan OHLCV VN100, giu raw bat bien."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol

from .du_lieu_thi_truong.nguon_vnstock import nguon_vnstock
from .du_lieu_thi_truong.quy_trinh import chay_quy_trinh, lam_sach_loi
from .du_lieu_thi_truong.tham_so_vnstock import SO_NEN_MAC_DINH, so_nguyen_duong

TAI_NGUON_THAT_BAI = "TAI_NGUON_THAT_BAI"
TAI_NGUON_THANH_CONG_KIEM_TRA_DAT = "TAI_NGUON_THANH_CONG_KIEM_TRA_DAT"
TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI = (
    "TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI"
)
RAW_NOT_PRESERVED = "RAW_NOT_PRESERVED"

CAC_LOAI_VI_PHAM = (
    "HIGH_LT_OPEN",
    "HIGH_LT_CLOSE",
    "LOW_GT_OPEN",
    "LOW_GT_CLOSE",
    "NON_FINITE",
    "NON_POSITIVE_PRICE",
    "NEGATIVE_VOLUME",
    "DUPLICATE_DATE",
)
THU_TU_VI_PHAM = {ten: i for i, ten in enumerate(CAC_LOAI_VI_PHAM)}
COT_BAT_THUONG = (
    "ma", "ngay", "open", "high", "low", "close", "volume",
    "loai_vi_pham", "truong_vi_pham", "nguon", "phien_ban", "raw_sha256",
)


class NguonCoTheTai(Protocol):
    ten_nguon: str
    phien_ban: str

    def lay_du_lieu(self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str) -> Any:
        """Lay bang du lieu nguon."""


@dataclass(frozen=True)
class CauHinhTaiVN100:
    danh_sach_ma: Path
    ngay_bat_dau: str
    ngay_ket_thuc: str
    ngay_kiem_tra: date
    thu_muc_du_lieu: Path
    ma_lan_chay: str
    so_nen: int = SO_NEN_MAC_DINH
    so_lan_thu_toi_da: int = 3
    yeu_cau_moi_phut: int = 18
    tiep_tuc: bool = True

    def __post_init__(self) -> None:
        if self.ngay_bat_dau > self.ngay_ket_thuc:
            raise ValueError("ngay_bat_dau phai khong sau ngay_ket_thuc")
        if self.ngay_ket_thuc > self.ngay_kiem_tra.isoformat():
            raise ValueError("ngay_ket_thuc khong duoc sau ngay_kiem_tra")
        if min(self.so_nen, self.so_lan_thu_toi_da, self.yeu_cau_moi_phut) <= 0:
            raise ValueError("cac tham so so luong phai duong")
        if not self.ma_lan_chay.strip():
            raise ValueError("ma_lan_chay khong duoc rong")


class NguonGioiHanTocDo:
    """Gioi han moi lan goi nguon, ke ca retry cua pipeline Moc 1."""

    def __init__(
        self,
        nguon: NguonCoTheTai,
        *,
        yeu_cau_moi_phut: int,
        ham_dong_ho: Callable[[], float] = time.monotonic,
        ham_cho: Callable[[float], None] = time.sleep,
    ) -> None:
        if yeu_cau_moi_phut <= 0:
            raise ValueError("yeu_cau_moi_phut phai duong")
        self._nguon = nguon
        self.ten_nguon = nguon.ten_nguon
        self.phien_ban = nguon.phien_ban
        self._khoang_cach = 60.0 / yeu_cau_moi_phut
        self._dong_ho = ham_dong_ho
        self._cho = ham_cho
        self._lan_truoc: float | None = None

    def lay_du_lieu(self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str) -> Any:
        bay_gio = self._dong_ho()
        if self._lan_truoc is not None:
            con_lai = self._khoang_cach - (bay_gio - self._lan_truoc)
            if con_lai > 0:
                self._cho(con_lai)
                bay_gio = self._dong_ho()
        self._lan_truoc = bay_gio
        return self._nguon.lay_du_lieu(ma, ngay_bat_dau, ngay_ket_thuc)


def _sha256(path: Path) -> str:
    ma_bam = hashlib.sha256()
    with path.open("rb") as tep:
        for khoi in iter(lambda: tep.read(1024 * 1024), b""):
            ma_bam.update(khoi)
    return ma_bam.hexdigest()


def _ghi_nguyen_tu(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("xb") as tep:
            tep.write(data)
            tep.flush()
            os.fsync(tep.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _ghi_json(path: Path, data: Mapping[str, Any]) -> None:
    noi_dung = json.dumps(
        data, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    _ghi_nguyen_tu(path, noi_dung)


def _ghi_csv(
    path: Path, rows: Iterable[Mapping[str, Any]], columns: tuple[str, ...]
) -> None:
    bo_nho = StringIO(newline="")
    writer = csv.DictWriter(bo_nho, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in columns})
    _ghi_nguyen_tu(path, bo_nho.getvalue().encode("utf-8"))


def doc_danh_sach_ma(path: Path) -> tuple[str, ...]:
    with path.open(encoding="utf-8-sig", newline="") as tep:
        reader = csv.DictReader(tep)
        if not reader.fieldnames or "ma" not in reader.fieldnames:
            raise ValueError("CSV danh sach ma phai co cot 'ma'")
        symbols = tuple(dict.fromkeys(
            str(row.get("ma", "")).strip().upper()
            for row in reader if str(row.get("ma", "")).strip()
        ))
    if not symbols:
        raise ValueError("CSV danh sach ma khong co ma hop le")
    return symbols


def _doc_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "2.0", "trang_thai_tung_ma": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("checkpoint phai la JSON object")
    data.setdefault("schema_version", "2.0")
    data.setdefault("trang_thai_tung_ma", {})
    if not isinstance(data["trang_thai_tung_ma"], dict):
        raise ValueError("checkpoint.trang_thai_tung_ma phai la object")
    return data


def _checkpoint_dat_va_hash_khop(item: Mapping[str, Any]) -> bool:
    if item.get("trang_thai") not in {
        "thanh_cong", TAI_NGUON_THANH_CONG_KIEM_TRA_DAT
    }:
        return False
    path, expected = item.get("duong_dan_tho"), item.get("ma_sha256")
    return bool(
        path and expected and Path(str(path)).is_file()
        and _sha256(Path(str(path))) == str(expected)
    )


def _ghi_loi(path: Path, item: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as tep:
        tep.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        tep.flush()
        os.fsync(tep.fileno())


def _get(obj: Any, key: str, default: Any = None) -> Any:
    return getattr(obj, key, default)


def _phan_loai_pipeline(
    state: Any, *, source: str, version: str
) -> tuple[str, dict[str, Any]]:
    item = dict(state.thanh_tu_dien())
    raw_path, pipeline_hash = _get(state, "duong_dan_tho"), _get(state, "ma_sha256")
    if not raw_path or not pipeline_hash or not Path(str(raw_path)).is_file():
        item.update({
            "trang_thai": TAI_NGUON_THAT_BAI,
            "trang_thai_tai_nguon": "THAT_BAI",
            "trang_thai_kiem_tra": "KHONG_CHAY",
            "trang_thai_raw": RAW_NOT_PRESERVED,
        })
        return TAI_NGUON_THAT_BAI, item

    raw = Path(str(raw_path))
    actual_hash = _sha256(raw)
    hash_ok = actual_hash == str(pipeline_hash)
    item.update({
        "duong_dan_tho": str(raw),
        "ma_sha256": actual_hash,
        "ma_sha256_pipeline": str(pipeline_hash),
        "ma_sha256_da_kiem_tra_lai": actual_hash,
        "trang_thai_doi_chieu_hash": "KHOP" if hash_ok else "KHONG_KHOP",
        "so_dong_nguon": int(_get(state, "so_dong", 0) or 0),
        "ngay_dau_nguon": _get(state, "ngay_dau"),
        "ngay_cuoi_nguon": _get(state, "ngay_cuoi"),
        "ten_cot_nguon": list(_get(state, "ten_cot_nguon", ()) or ()),
        "kieu_du_lieu_nguon": _get(state, "kieu_du_lieu"),
        "nguon": source,
        "phien_ban_nguon": version,
        "trang_thai_tai_nguon": "THANH_CONG",
    })
    if hash_ok and _get(state, "trang_thai") == "thanh_cong":
        item.update({
            "trang_thai": TAI_NGUON_THANH_CONG_KIEM_TRA_DAT,
            "trang_thai_kiem_tra": "DAT",
            "trang_thai_raw": "PRESERVED_HASH_VERIFIED",
        })
        return TAI_NGUON_THANH_CONG_KIEM_TRA_DAT, item

    item.update({
        "trang_thai": TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI,
        "trang_thai_kiem_tra": "THAT_BAI",
        "trang_thai_raw": (
            "PRESERVED_HASH_VERIFIED" if hash_ok else "PRESERVED_HASH_MISMATCH"
        ),
        "loi_kiem_tra": _get(state, "loi"),
    })
    if not hash_ok:
        item["loi_toan_ven_raw"] = "SHA-256 pipeline khong khop bytes raw hien co"
    return TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI, item


def chay_tai_hang_loat(
    config: CauHinhTaiVN100,
    *,
    ham_tao_nguon: Callable[[int], NguonCoTheTai] = lambda n: nguon_vnstock(
        so_nen=n
    ),
    ham_chay_quy_trinh: Callable[..., Any] = chay_quy_trinh,
    ham_dong_ho: Callable[[], float] = time.monotonic,
    ham_cho: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Tai tung ma; validation-fail van giu provenance raw."""

    symbols = doc_danh_sach_ma(config.danh_sach_ma)
    root = config.thu_muc_du_lieu / "dieu_phoi_vn100" / config.ma_lan_chay
    checkpoint_path, error_path, summary_path = (
        root / "checkpoint.json", root / "loi_tung_ma.jsonl", root / "tong_hop.json"
    )
    checkpoint = _doc_checkpoint(checkpoint_path)
    checkpoint.update({
        "schema_version": "2.0",
        "ma_lan_chay": config.ma_lan_chay,
        "ngay_bat_dau": config.ngay_bat_dau,
        "ngay_ket_thuc": config.ngay_ket_thuc,
        "danh_sach_ma_sha256": _sha256(config.danh_sach_ma),
        "nguon_yeu_cau": "vnstock_kbs",
        "phien_ban_yeu_cau": "4.0.4",
        "cap_nhat_luc": datetime.now(timezone.utc).isoformat(),
    })
    states: dict[str, Any] = checkpoint["trang_thai_tung_ma"]
    source = NguonGioiHanTocDo(
        ham_tao_nguon(config.so_nen),
        yeu_cau_moi_phut=config.yeu_cau_moi_phut,
        ham_dong_ho=ham_dong_ho,
        ham_cho=ham_cho,
    )
    skipped, counts = 0, Counter()

    for symbol in symbols:
        old = states.get(symbol, {})
        if config.tiep_tuc and isinstance(old, Mapping) and _checkpoint_dat_va_hash_khop(old):
            skipped += 1
            continue
        attempt = int(old.get("lan_tai", 0)) + 1 if isinstance(old, Mapping) else 1
        started = datetime.now(timezone.utc).isoformat()
        try:
            result = ham_chay_quy_trinh(
                source, (symbol,), config.ngay_bat_dau, config.ngay_ket_thuc,
                config.thu_muc_du_lieu, config.ngay_kiem_tra,
                so_lan_thu_toi_da=config.so_lan_thu_toi_da,
                ham_cho=ham_cho,
                ma_lan_chay=f"{config.ma_lan_chay}_{symbol}_{attempt:03d}",
                cau_hinh_lan_chay={
                    "loai_lan_chay": "vn100_hang_loat",
                    "ma_lan_chay_cha": config.ma_lan_chay,
                    "so_nen_yeu_cau": config.so_nen,
                    "yeu_cau_moi_phut": config.yeu_cau_moi_phut,
                },
            )
            status, item = _phan_loai_pipeline(
                result.trang_thai_tung_ma[0],
                source=source.ten_nguon,
                version=source.phien_ban,
            )
        except Exception as exc:
            status, item = TAI_NGUON_THAT_BAI, {
                "ma": symbol,
                "trang_thai": TAI_NGUON_THAT_BAI,
                "trang_thai_tai_nguon": "THAT_BAI",
                "trang_thai_kiem_tra": "KHONG_CHAY",
                "trang_thai_raw": RAW_NOT_PRESERVED,
                "loi": lam_sach_loi(exc),
            }
        item.update({
            "ma": symbol,
            "lan_tai": attempt,
            "thoi_diem_bat_dau": started,
            "thoi_diem_ket_thuc": datetime.now(timezone.utc).isoformat(),
        })
        states[symbol] = item
        counts[status] += 1
        if status != TAI_NGUON_THANH_CONG_KIEM_TRA_DAT:
            _ghi_loi(error_path, item)
        checkpoint["cap_nhat_luc"] = datetime.now(timezone.utc).isoformat()
        _ghi_json(checkpoint_path, checkpoint)

    failures = counts[TAI_NGUON_THAT_BAI] + counts[
        TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI
    ]
    summary = {
        "schema_version": "2.0",
        "ma_lan_chay": config.ma_lan_chay,
        "nguon": source.ten_nguon,
        "phien_ban": source.phien_ban,
        "tong_so_ma": len(symbols),
        "tai_nguon_that_bai_trong_lan_nay": counts[TAI_NGUON_THAT_BAI],
        "tai_nguon_thanh_cong_kiem_tra_dat_trong_lan_nay": counts[
            TAI_NGUON_THANH_CONG_KIEM_TRA_DAT
        ],
        "tai_nguon_thanh_cong_kiem_tra_that_bai_trong_lan_nay": counts[
            TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI
        ],
        "tai_thanh_cong_trong_lan_nay": counts[
            TAI_NGUON_THANH_CONG_KIEM_TRA_DAT
        ],
        "that_bai_trong_lan_nay": failures,
        "bo_qua_do_hash_checkpoint_hop_le": skipped,
        "so_ma_checkpoint_thanh_cong": sum(
            _checkpoint_dat_va_hash_khop(x)
            for x in states.values() if isinstance(x, Mapping)
        ),
        "checkpoint": str(checkpoint_path),
        "nhat_ky_loi": str(error_path),
        "ket_thuc_luc": datetime.now(timezone.utc).isoformat(),
    }
    _ghi_json(summary_path, summary)
    return summary


def _ngay(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _so(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _them_loi(
    errors: list[dict[str, Any]], row: Mapping[str, Any], *, symbol: str,
    day: str, kind: str, field: str, source: str, version: str, raw_hash: str,
) -> None:
    errors.append({
        "ma": symbol, "ngay": day,
        "open": row.get("open", ""), "high": row.get("high", ""),
        "low": row.get("low", ""), "close": row.get("close", ""),
        "volume": row.get("volume", ""), "loai_vi_pham": kind,
        "truong_vi_pham": field, "nguon": source, "phien_ban": version,
        "raw_sha256": raw_hash,
    })


def _kiem_tra_raw_rows(
    symbol: str, rows: list[Mapping[str, Any]], *, source: str,
    version: str, raw_hash: str,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    day_counts = Counter(_ngay(row.get("time")) for row in rows)
    for row in rows:
        day = _ngay(row.get("time"))
        values = {key: _so(row.get(key)) for key in (
            "open", "high", "low", "close", "volume"
        )}
        for key, value in values.items():
            if value is None:
                _them_loi(errors, row, symbol=symbol, day=day, kind="NON_FINITE",
                          field=key, source=source, version=version, raw_hash=raw_hash)
        for key in ("open", "high", "low", "close"):
            if values[key] is not None and values[key] <= 0:
                _them_loi(errors, row, symbol=symbol, day=day,
                          kind="NON_POSITIVE_PRICE", field=key, source=source,
                          version=version, raw_hash=raw_hash)
        if values["volume"] is not None and values["volume"] < 0:
            _them_loi(errors, row, symbol=symbol, day=day, kind="NEGATIVE_VOLUME",
                      field="volume", source=source, version=version,
                      raw_hash=raw_hash)
        comparisons = (
            ("HIGH_LT_OPEN", "high|open", "high", "open", lambda a, b: a < b),
            ("HIGH_LT_CLOSE", "high|close", "high", "close", lambda a, b: a < b),
            ("LOW_GT_OPEN", "low|open", "low", "open", lambda a, b: a > b),
            ("LOW_GT_CLOSE", "low|close", "low", "close", lambda a, b: a > b),
        )
        for kind, field, left, right, compare in comparisons:
            a, b = values[left], values[right]
            if a is not None and b is not None and compare(a, b):
                _them_loi(errors, row, symbol=symbol, day=day, kind=kind,
                          field=field, source=source, version=version,
                          raw_hash=raw_hash)
        if day_counts[day] > 1:
            _them_loi(errors, row, symbol=symbol, day=day, kind="DUPLICATE_DATE",
                      field="ngay", source=source, version=version,
                      raw_hash=raw_hash)
    return errors


def _tim_raw(
    raw_root: Path, prefix: str
) -> tuple[dict[str, Path], dict[str, list[str]]]:
    candidates: dict[str, list[tuple[int, str, Path]]] = defaultdict(list)
    for run_dir in sorted(raw_root.glob(f"{prefix}_*")):
        if not run_dir.is_dir():
            continue
        for path in sorted(run_dir.glob("*.json")):
            symbol = path.stem.strip().upper()
            match = re.match(
                rf"^{re.escape(prefix)}_{re.escape(symbol)}_(\d+)$", run_dir.name
            )
            attempt = int(match.group(1)) if match else -1
            candidates[symbol].append((attempt, str(path), path))
    selected, all_paths = {}, {}
    for symbol, items in sorted(candidates.items()):
        items.sort(key=lambda x: (x[0], x[1]))
        selected[symbol] = items[-1][2]
        all_paths[symbol] = [x[1] for x in items]
    return selected, all_paths


def _doc_raw(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("du_lieu"), list):
        raise ValueError(f"Raw khong dung schema: {path}")
    return data


def _loi_ocv_doc_lap(error: Mapping[str, Any]) -> bool:
    kind, field = error["loai_vi_pham"], error.get("truong_vi_pham")
    if kind in {"NEGATIVE_VOLUME", "DUPLICATE_DATE"}:
        return True
    return kind in {"NON_FINITE", "NON_POSITIVE_PRICE"} and field in {
        "open", "close", "volume", "ngay"
    }


def kiem_toan_raw_vn100(
    *,
    danh_sach_ma: Path,
    thu_muc_tho: Path,
    tien_to_lan_chay: str,
    thu_muc_bao_cao: Path,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Quet raw da co; khong khoi tao source va khong goi mang."""

    symbols = doc_danh_sach_ma(danh_sach_ma)
    checkpoint = (
        _doc_checkpoint(checkpoint_path)
        if checkpoint_path and checkpoint_path.exists()
        else {"schema_version": "2.0", "trang_thai_tung_ma": {}}
    )
    old_states = checkpoint.get("trang_thai_tung_ma", {})
    if not isinstance(old_states, Mapping):
        old_states = {}
    selected, candidates = _tim_raw(thu_muc_tho, tien_to_lan_chay)
    metadata: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    unreadable: dict[str, str] = {}

    for symbol in symbols:
        path = selected.get(symbol)
        if path is None:
            metadata[symbol] = {
                "ma": symbol, "trang_thai": TAI_NGUON_THAT_BAI,
                "trang_thai_tai_nguon": "KHONG_THE_XAC_NHAN",
                "trang_thai_kiem_tra": "KHONG_CHAY",
                "trang_thai_raw": RAW_NOT_PRESERVED,
            }
            continue
        raw_hash = _sha256(path)
        try:
            data = _doc_raw(path)
            rows = [x for x in data["du_lieu"] if isinstance(x, Mapping)]
            item_errors = _kiem_tra_raw_rows(
                symbol, rows, source=str(data.get("nguon", "")),
                version=str(data.get("phien_ban", "")), raw_hash=raw_hash,
            )
            errors.extend(item_errors)
            days = sorted(x for x in (_ngay(r.get("time")) for r in rows) if x)
            item = {
                "ma": symbol,
                "trang_thai": (
                    TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI
                    if item_errors else TAI_NGUON_THANH_CONG_KIEM_TRA_DAT
                ),
                "trang_thai_tai_nguon": "THANH_CONG",
                "trang_thai_kiem_tra": "THAT_BAI" if item_errors else "DAT",
                "trang_thai_raw": "PRESERVED_HASH_VERIFIED",
                "duong_dan_tho": str(path), "ma_sha256": raw_hash,
                "ma_sha256_da_kiem_tra_lai": raw_hash,
                "so_dong_nguon": len(rows),
                "ngay_dau_nguon": days[0] if days else None,
                "ngay_cuoi_nguon": days[-1] if days else None,
                "ten_cot_nguon": list(data.get("cac_cot", [])),
                "kieu_du_lieu_nguon": data.get("kieu_du_lieu"),
                "nguon": str(data.get("nguon", "")),
                "phien_ban_nguon": str(data.get("phien_ban", "")),
                "so_loi_kiem_tra": len(item_errors),
                "so_ngay_vi_pham_duy_nhat": len({e["ngay"] for e in item_errors}),
            }
            old = old_states.get(symbol, {})
            expected = old.get("ma_sha256") if isinstance(old, Mapping) else None
            if expected:
                item["ma_sha256_checkpoint_truoc"] = str(expected)
                item["nguon_hash_doi_chieu"] = str(
                    old.get("nguon_hash_doi_chieu", "CHECKPOINT_VAN_HANH")
                )
                item["trang_thai_doi_chieu_hash"] = (
                    "KHOP" if str(expected) == raw_hash else "KHONG_KHOP"
                )
                if str(expected) != raw_hash:
                    item.update({
                        "trang_thai": TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI,
                        "trang_thai_kiem_tra": "THAT_BAI",
                        "trang_thai_raw": "PRESERVED_HASH_MISMATCH",
                        "loi_toan_ven_raw": "SHA-256 checkpoint khong khop raw",
                    })
            else:
                item.update({
                    "ma_sha256_checkpoint_truoc": raw_hash,
                    "nguon_hash_doi_chieu": "TAO_MOI_TU_RAW",
                    "trang_thai_doi_chieu_hash": "KHOP",
                })
            metadata[symbol] = item
        except Exception as exc:
            unreadable[symbol] = lam_sach_loi(exc)
            metadata[symbol] = {
                "ma": symbol, "trang_thai": TAI_NGUON_THAT_BAI,
                "trang_thai_tai_nguon": "KHONG_THE_XAC_NHAN",
                "trang_thai_kiem_tra": "KHONG_CHAY",
                "trang_thai_raw": "RAW_UNREADABLE", "duong_dan_tho": str(path),
                "ma_sha256": raw_hash, "ma_sha256_da_kiem_tra_lai": raw_hash,
                "loi": unreadable[symbol],
            }

    errors.sort(key=lambda e: (
        e["ma"], e["ngay"], THU_TU_VI_PHAM[e["loai_vi_pham"]],
        e["truong_vi_pham"],
    ))
    csv_path = thu_muc_bao_cao / "bao_cao_bat_thuong_ohlc.csv"
    _ghi_csv(csv_path, errors, COT_BAT_THUONG)

    by_kind = Counter(e["loai_vi_pham"] for e in errors)
    by_symbol = Counter(e["ma"] for e in errors)
    bad_days = sorted({e["ngay"] for e in errors if e["ngay"]})
    symbol_days = {(e["ma"], e["ngay"]) for e in errors}
    ocv_bad = {e["ma"] for e in errors if _loi_ocv_doc_lap(e)}
    any_bad = set(by_symbol)
    raw_ok = {s for s, x in metadata.items() if x.get("trang_thai_tai_nguon") == "THANH_CONG"}
    strict_ok = {s for s, x in metadata.items() if x.get("trang_thai") == TAI_NGUON_THANH_CONG_KIEM_TRA_DAT}
    strict_bad = {s for s, x in metadata.items() if x.get("trang_thai") == TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI}
    hash_match = sum(x.get("trang_thai_doi_chieu_hash") == "KHOP" for x in metadata.values())
    hash_mismatch = sum(x.get("trang_thai_doi_chieu_hash") == "KHONG_KHOP" for x in metadata.values())

    summary: dict[str, Any] = {
        "schema_version": "1.0", "tien_to_lan_chay": tien_to_lan_chay,
        "tong_ma": len(symbols),
        "so_raw_file_thuc_te_tim_thay": sum(map(len, candidates.values())),
        "so_ma_co_raw": len(selected),
        "so_ma_raw_con_ma_bam_khop": hash_match,
        "so_ma_raw_ma_bam_khong_khop": hash_mismatch,
        "so_ma_raw_hash_doi_chieu_tu_checkpoint_van_hanh": sum(
            x.get("nguon_hash_doi_chieu") == "CHECKPOINT_VAN_HANH"
            for x in metadata.values()
        ),
        "so_ma_raw_hash_doi_chieu_tao_moi_tu_raw": sum(
            x.get("nguon_hash_doi_chieu") == "TAO_MOI_TU_RAW"
            for x in metadata.values()
        ),
        "so_ma_tai_nguon_thanh_cong": len(raw_ok),
        "so_ma_tai_nguon_that_bai": len(symbols) - len(raw_ok),
        "so_ma_kiem_tra_dat": len(strict_ok),
        "so_ma_kiem_tra_that_bai": len(strict_bad),
        "tong_so_dong_nguon": sum(
            int(x.get("so_dong_nguon", 0) or 0) for x in metadata.values()
        ),
        "tong_so_ngay_vi_pham_duy_nhat": len(symbol_days),
        "so_ngay_lich_vi_pham_duy_nhat": len(bad_days),
        "so_loi_theo_loai": {k: by_kind.get(k, 0) for k in CAC_LOAI_VI_PHAM},
        "so_loi_theo_ma": dict(sorted(by_symbol.items())),
        "ngay_vi_pham_som_nhat": bad_days[0] if bad_days else None,
        "ngay_vi_pham_muon_nhat": bad_days[-1] if bad_days else None,
        "so_ma_chi_loi_high_low_nhung_open_close_volume_hop_le": len(any_bad - ocv_bad),
        "so_ma_co_loi_open_close_volume_doc_lap": len(ocv_bad),
        "so_ma_open_close_volume_hop_le": len(raw_ok - ocv_bad),
        "so_ma_khong_the_dung_hop_dong_rut_gon": len(ocv_bad),
        "raw_not_preserved": sorted(
            s for s, x in metadata.items() if x.get("trang_thai_raw") == RAW_NOT_PRESERVED
        ),
        "raw_khong_doc_duoc": dict(sorted(unreadable.items())),
        "raw_ung_vien_theo_ma": dict(sorted(candidates.items())),
        "trang_thai_tung_ma": dict(sorted(metadata.items())),
        "bao_cao_bat_thuong_ohlc": str(csv_path),
    }
    json_path = thu_muc_bao_cao / "bao_cao_phan_loai_121_ma.json"
    _ghi_json(json_path, summary)
    summary["bao_cao_phan_loai_121_ma"] = str(json_path)

    if checkpoint_path:
        checkpoint["schema_version"] = "2.0"
        states = checkpoint.setdefault("trang_thai_tung_ma", {})
        for symbol, item in metadata.items():
            merged = dict(states.get(symbol, {}))
            merged.update(item)
            states[symbol] = merged
        checkpoint["kiem_toan_raw"] = {
            "tien_to_lan_chay": tien_to_lan_chay,
            "bao_cao_bat_thuong_ohlc": str(csv_path),
            "bao_cao_phan_loai_121_ma": str(json_path),
        }
        _ghi_json(checkpoint_path, checkpoint)
    return summary


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tai hoac kiem toan OHLCV VN100 bang vnstock 4.0.4/KBS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--kiem-toan-raw", action="store_true")
    parser.add_argument("--danh-sach-ma", type=Path, required=True)
    for name in ("ngay-bat-dau", "ngay-ket-thuc", "ngay-kiem-tra", "ma-lan-chay"):
        parser.add_argument("--" + name)
    parser.add_argument("--thu-muc-du-lieu", type=Path)
    parser.add_argument("--so-nen", type=so_nguyen_duong, default=SO_NEN_MAC_DINH)
    parser.add_argument("--so-lan-thu-toi-da", type=so_nguyen_duong, default=3)
    parser.add_argument("--yeu-cau-moi-phut", type=so_nguyen_duong, default=18)
    parser.add_argument("--khong-tiep-tuc", action="store_true")
    parser.add_argument("--thu-muc-tho", type=Path)
    parser.add_argument("--tien-to-lan-chay")
    parser.add_argument("--thu-muc-bao-cao", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    return parser


def _bat_buoc(args: argparse.Namespace, *names: str) -> None:
    missing = [name for name in names if getattr(args, name) in {None, ""}]
    if missing:
        labels = ", ".join("--" + x.replace("_", "-") for x in missing)
        raise SystemExit("Thieu tham so bat buoc: " + labels)


def chay() -> int:
    args = tao_bo_phan_tich().parse_args()
    if args.kiem_toan_raw:
        _bat_buoc(args, "thu_muc_tho", "tien_to_lan_chay", "thu_muc_bao_cao")
        result = kiem_toan_raw_vn100(
            danh_sach_ma=args.danh_sach_ma,
            thu_muc_tho=args.thu_muc_tho,
            tien_to_lan_chay=args.tien_to_lan_chay,
            thu_muc_bao_cao=args.thu_muc_bao_cao,
            checkpoint_path=args.checkpoint,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    _bat_buoc(args, "ngay_bat_dau", "ngay_ket_thuc", "thu_muc_du_lieu")
    config = CauHinhTaiVN100(
        danh_sach_ma=args.danh_sach_ma,
        ngay_bat_dau=date.fromisoformat(args.ngay_bat_dau).isoformat(),
        ngay_ket_thuc=date.fromisoformat(args.ngay_ket_thuc).isoformat(),
        ngay_kiem_tra=(
            date.fromisoformat(args.ngay_kiem_tra) if args.ngay_kiem_tra else date.today()
        ),
        thu_muc_du_lieu=args.thu_muc_du_lieu,
        ma_lan_chay=args.ma_lan_chay or (
            "vn100_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ),
        so_nen=args.so_nen,
        so_lan_thu_toi_da=args.so_lan_thu_toi_da,
        yeu_cau_moi_phut=args.yeu_cau_moi_phut,
        tiep_tuc=not args.khong_tiep_tuc,
    )
    result = chay_tai_hang_loat(config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["that_bai_trong_lan_nay"] else 0


if __name__ == "__main__":
    raise SystemExit(chay())
