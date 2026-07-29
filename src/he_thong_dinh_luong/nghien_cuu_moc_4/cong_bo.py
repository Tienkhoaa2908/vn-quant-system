"""Cong bo san pham bat bien bang staging, fsync, atomic rename va SHA-256."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import json
from math import isfinite
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable, Mapping, Sequence

TEN_SAN_PHAM = (
    "cau_hinh.json", "bao_cao_do_phu.json", "universe_theo_ngay.csv", "feature_raw.csv",
    "feature_sau_tien_xu_ly.csv", "nhan.csv", "folds.csv", "mo_hinh.csv",
    "he_so_logistic.csv", "du_doan.csv", "xep_hang.csv", "ty_trong_muc_tieu.csv",
    "chi_so_mo_hinh.json", "chi_so_ranking.json", "chi_so_backtest.json", "bao_cao.json",
)
TEN_SAN_PHAM_V2 = TEN_SAN_PHAM + (
    "lenh.csv", "khop_lenh.csv", "so_cai.csv", "vi_the.csv", "nav.csv",
    "su_kien_da_ap_dung.csv",
)

METADATA_BAT_BUOC = {
    "git_commit", "ma_lan_chay", "thoi_diem_utc", "python_version", "uv_version",
    "scikit_learn_version", "nguon_ohlcv", "phien_ban_ohlcv", "nguon_universe",
    "phien_ban_universe", "nguon_benchmark", "phien_ban_benchmark", "co_so_gia",
    "muc_dich_lan_chay", "cau_hinh_feature", "cau_hinh_label", "cau_hinh_fold",
    "cau_hinh_model", "cau_hinh_ranking", "canh_bao", "gioi_han",
}
METADATA_BAT_BUOC_V2 = {
    "git_commit", "ma_lan_chay", "thoi_diem_utc", "python_version", "uv_version",
    "scikit_learn_version", "muc_dich_lan_chay", "price_contract", "universe_contract",
    "candidate_union_name", "candidate_union_expected_count",
    "candidate_union_observed_count", "candidate_union_is_point_in_time",
    "publication_expected_row_count", "publication_observed_row_count",
    "publication_expected_symbol_count", "publication_observed_symbol_count",
    "stock_price_basis", "stock_price_basis_confirmed", "benchmark_contract",
    "benchmark_unit", "benchmark_price_basis", "benchmark_price_basis_confirmed",
    "stock_benchmark_price_basis_equality_required", "corporate_actions_applied",
    "corporate_actions_inventory_complete", "high_low_present_in_stock_input",
    "high_low_used", "high_low_synthesized", "replacement_feature_for_high_low",
    "research_gate", "research_gate_reasons", "technical_validation_only",
    "nguon_ohlcv", "phien_ban_ohlcv", "nguon_universe", "phien_ban_universe",
    "nguon_benchmark", "phien_ban_benchmark", "cau_hinh_feature",
    "cau_hinh_label", "cau_hinh_fold", "cau_hinh_model", "cau_hinh_ranking",
    "canh_bao", "gioi_han",
}


def _bytes(value: str | bytes) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, bytes):
        return value
    raise TypeError("San pham chi duoc la str hoac bytes.")


def _fsync_dir(path: Path) -> bool:
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


def _validate_metadata(metadata: Mapping[str, object], required: set[str]) -> dict[str, object]:
    missing = sorted(required - set(metadata))
    if missing:
        raise ValueError(f"Metadata manifest thieu: {', '.join(missing)}.")
    extra_empty = [
        key for key in required
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


def _cong_bo(
    thu_muc_dich: Path,
    san_pham: Mapping[str, str | bytes],
    *,
    metadata: Mapping[str, object],
    dau_vao: Mapping[str, Path | str | bytes],
    ten_san_pham: Sequence[str],
    metadata_bat_buoc: set[str],
    manifest_versions: Mapping[str, str] | None = None,
) -> Path:
    destination = Path(thu_muc_dich)
    if destination.exists():
        raise FileExistsError("Khong ghi de thu muc san pham.")
    missing = sorted(set(ten_san_pham) - set(san_pham))
    extra = sorted(set(san_pham) - set(ten_san_pham))
    if missing or extra:
        raise ValueError(f"Tap san pham sai hop dong; thieu={missing}, thua={extra}.")
    if not dau_vao:
        raise ValueError("Manifest bat buoc co it nhat mot dau vao de tinh SHA-256.")
    normalized_metadata = _validate_metadata(metadata, metadata_bat_buoc)
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
        for name in ten_san_pham:
            payload = _bytes(san_pham[name])
            _validate_product_payload(name, payload)
            path = staging / name
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            hashes[name] = {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
        manifest: dict[str, object] = {
            "trang_thai": "thanh_cong",
            "metadata": dict(sorted(normalized_metadata.items())),
            "inputs": input_hashes,
            "files": hashes,
        }
        if manifest_versions:
            manifest.update(manifest_versions)
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


def cong_bo_san_pham(
    thu_muc_dich: Path,
    san_pham: Mapping[str, str | bytes],
    *,
    metadata: Mapping[str, object],
    dau_vao: Mapping[str, Path | str | bytes],
) -> Path:
    """Cong bo v1 khong thay doi hop dong strict hien hanh."""
    return _cong_bo(
        thu_muc_dich, san_pham, metadata=metadata, dau_vao=dau_vao,
        ten_san_pham=TEN_SAN_PHAM, metadata_bat_buoc=METADATA_BAT_BUOC,
    )


def cong_bo_san_pham_v2(
    thu_muc_dich: Path,
    san_pham: Mapping[str, str | bytes],
    *,
    metadata: Mapping[str, object],
    dau_vao: Mapping[str, Path | str | bytes],
) -> Path:
    return _cong_bo(
        thu_muc_dich, san_pham, metadata=metadata, dau_vao=dau_vao,
        ten_san_pham=TEN_SAN_PHAM_V2, metadata_bat_buoc=METADATA_BAT_BUOC_V2,
        manifest_versions={
            "manifest_schema_version": "m4_manifest_v2",
            "product_contract_version": "m4_products_v2",
            "model_contract_version": "m4_logistic_reduced_open_close_volume_v1",
            "audit_contract_version": "m4_product_audit_v1",
        },
    )


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


def _value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return "" if value is None else str(value)


def tao_san_pham_backtest_v2(logistic: object, baseline: object) -> dict[str, str]:
    """Cong bo chi tiet hai chuoi OOS; khong tai tinh hoac chay lai engine."""
    strategies = (("logistic", logistic), ("momentum_baseline", baseline))

    def combine(attr: str, fields: tuple[str, ...]) -> str:
        rows: list[dict[str, object]] = []
        for strategy, result in strategies:
            for item in getattr(result, attr):
                row = {"chien_luoc": strategy}
                row.update({name: _value(getattr(item, name)) for name in fields})
                rows.append(row)
        rows.sort(key=lambda row: tuple(str(row[name]) for name in ("chien_luoc", *fields)))
        return _csv_on_dinh(rows, ("chien_luoc", *fields))

    lenh_fields = (
        "ma_lenh", "ngay_tin_hieu", "ngay_thuc_thi", "ma", "chieu", "so_luong",
        "loai_lenh", "trang_thai", "ly_do_tu_choi_hoac_het_han",
        "so_luong_yeu_cau", "so_luong_bi_giam", "ly_do_giam",
    )
    khop_fields = (
        "ma_lenh", "ma", "ngay_khop", "chieu", "so_luong", "gia_mo_cua",
        "gia_khop", "gia_tri_giao_dich", "phi", "thue", "chi_phi_truot_gia",
        "so_luong_yeu_cau", "so_luong_bi_giam", "ly_do_giam",
    )
    ledger_fields = (
        "ngay", "tien_mat_dau_ngay", "dong_tien_su_kien", "tien_mua", "tien_ban",
        "phi", "thue", "tien_mat_cuoi_ngay", "gia_tri_vi_the", "nav",
        "lai_lo_da_thuc_hien", "lai_lo_da_thuc_hien_luy_ke", "lai_lo_chua_thuc_hien",
        "co_tuc_tien_mat", "co_tuc_tien_mat_luy_ke", "chi_phi_truot_gia",
        "phi_mua", "phi_ban", "thue_ban", "phi_mua_luy_ke", "phi_ban_luy_ke",
        "thue_ban_luy_ke", "chenh_lech_doi_soat",
    )
    position_fields = (
        "ngay", "ma", "so_luong", "gia_von", "gia_dong_cua",
        "gia_tri_thi_truong", "lai_lo_chua_thuc_hien",
    )
    nav_fields = ("ngay", "nav", "loi_nhuan_phien", "tien_mat", "ty_trong_tien_mat")

    event_rows: list[dict[str, object]] = []
    event_keys: set[str] = set()
    for strategy, result in strategies:
        for raw in getattr(result, "su_kien_da_ap_dung"):
            text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
            key = f"{strategy}|{text}"
            if key in event_keys:
                raise ValueError("Trung su_kien_da_ap_dung trong san pham v2.")
            event_keys.add(key)
            event_rows.append({"chien_luoc": strategy, "su_kien_json": text})
    event_rows.sort(key=lambda row: (str(row["chien_luoc"]), str(row["su_kien_json"])))

    return {
        "lenh.csv": combine("lenh", lenh_fields),
        "khop_lenh.csv": combine("khop_lenh", khop_fields),
        "so_cai.csv": combine("so_cai", ledger_fields),
        "vi_the.csv": combine("vi_the_hang_ngay", position_fields),
        "nav.csv": combine("nav", nav_fields),
        "su_kien_da_ap_dung.csv": _csv_on_dinh(event_rows, ("chien_luoc", "su_kien_json")),
    }
