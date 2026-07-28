"""Kiem toan doc lap san pham M4 v2; khong goi pipeline, model hoac engine."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable, Mapping, Sequence

EXPECTED_PRODUCTS = (
    "cau_hinh.json", "bao_cao_do_phu.json", "universe_theo_ngay.csv", "feature_raw.csv",
    "feature_sau_tien_xu_ly.csv", "nhan.csv", "folds.csv", "mo_hinh.csv",
    "he_so_logistic.csv", "du_doan.csv", "xep_hang.csv", "ty_trong_muc_tieu.csv",
    "chi_so_mo_hinh.json", "chi_so_ranking.json", "chi_so_backtest.json", "bao_cao.json",
    "lenh.csv", "khop_lenh.csv", "so_cai.csv", "vi_the.csv", "nav.csv",
    "su_kien_da_ap_dung.csv",
)
RESEARCH_REASONS = (
    "VN100_POINT_IN_TIME_HISTORY_INCOMPLETE",
    "HOSE_EOD_CROSSCHECK_INCOMPLETE",
    "CORPORATE_ACTION_INVENTORY_INCOMPLETE",
    "PRICE_BASIS_UNCONFIRMED",
)
FORBIDDEN_FEATURE = "bien_do_cao_thap_chuan_hoa"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} phai la JSON object")
    return value


def _csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path.name} khong co header")
        return tuple(reader.fieldnames), [dict(row) for row in reader]


def _decimal(value: object, name: str, *, allow_empty: bool = False) -> Decimal | None:
    text = str(value).strip()
    if allow_empty and not text:
        return None
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{name} khong phai Decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} khong huu han")
    return result


def _check_manifest(root: Path, errors: list[str]) -> dict[str, object]:
    manifest = _json(root / "manifest.json")
    for key, expected in (
        ("manifest_schema_version", "m4_manifest_v2"),
        ("product_contract_version", "m4_products_v2"),
        ("model_contract_version", "m4_logistic_reduced_open_close_volume_v1"),
        ("audit_contract_version", "m4_product_audit_v1"),
    ):
        if manifest.get(key) != expected:
            errors.append(f"MANIFEST_VERSION:{key}")
    files = manifest.get("files")
    if not isinstance(files, Mapping) or set(files) != set(EXPECTED_PRODUCTS):
        errors.append("MANIFEST_PRODUCT_SET")
        return manifest
    actual_names = {path.name for path in root.iterdir() if path.is_file()}
    if actual_names != {*EXPECTED_PRODUCTS, "manifest.json"}:
        errors.append("PRODUCT_DIRECTORY_SET")
    for name in EXPECTED_PRODUCTS:
        item = files.get(name)
        path = root / name
        if not isinstance(item, Mapping) or not path.is_file():
            errors.append(f"PRODUCT_MISSING:{name}")
            continue
        if item.get("sha256") != _sha256(path):
            errors.append(f"PRODUCT_SHA256:{name}")
        if item.get("size") != path.stat().st_size:
            errors.append(f"PRODUCT_SIZE:{name}")
    return manifest


def _check_config_and_metadata(root: Path, manifest: Mapping[str, object], errors: list[str]) -> int:
    config = _json(root / "cau_hinh.json")
    m4 = config.get("moc_4")
    m3 = config.get("mo_phong")
    if not isinstance(m4, Mapping) or not isinstance(m3, Mapping):
        errors.append("CONFIG_SHAPE")
        return 0
    canonical = {
        "muc_dich_lan_chay": "kiem_tra_ky_thuat",
        "tan_suat_mau_mo_hinh": "cuoi_thang",
        "benchmark": "VNINDEX",
        "price_contract": "reduced_open_close_volume_v1",
        "universe_contract": "technical_candidate_union_v1",
        "stock_price_basis": "CHUA_XAC_NHAN",
        "stock_price_basis_confirmed": False,
        "benchmark_contract": "close_only",
        "benchmark_unit": "index_points",
        "benchmark_price_basis_confirmed": False,
        "candidate_union_is_point_in_time": False,
        "label_horizon": 20,
        "purge_phien": 20,
        "embargo_phien": 0,
        "so_thang_train_toi_thieu": 24,
        "so_thang_validation": 6,
        "so_thang_test": 1,
        "top_k": 2,
        "cua_so_thanh_khoan": 20,
        "nguong_gtgd_tb_toi_thieu": 0.0,
        "ty_le_coverage_toi_thieu": 0.0,
        "so_ma_eligible_toi_thieu": 0,
        "solver": "lbfgs",
        "max_iter": 1000,
        "class_weight": None,
        "seed": 20260725,
    }
    for key, expected in canonical.items():
        if m4.get(key) != expected:
            errors.append(f"CONFIG_M4:{key}")
    if m4.get("C_grid") != [0.1, 1.0, 10.0]:
        errors.append("CONFIG_M4:C_grid")
    order = m4.get("feature_order")
    required = m4.get("feature_bat_buoc")
    if not isinstance(order, list) or len(order) != 23 or FORBIDDEN_FEATURE in order:
        errors.append("FEATURE_ORDER_REDUCED")
    if required != order:
        errors.append("FEATURE_REQUIRED_REDUCED")
    if m3.get("co_so_gia") != "CHUA_XAC_NHAN":
        errors.append("M3_PRICE_BASIS")
    m3_canonical = {
        "von_ban_dau": "1000000000", "phi_mua_bps": "15", "phi_ban_bps": "15",
        "thue_ban_bps": "100", "truot_gia_bps": "10", "kich_thuoc_lo": 1,
        "so_phien_moi_nam": 250, "lai_suat_phi_rui_ro": "0",
        "che_do_ma_khong_xuat_hien": "muc_tieu_bang_0",
        "cho_phep_ban_le_khi_dong_vi_the": False,
        "don_vi_gia": "dong", "don_vi_tien": "dong",
    }
    for key, expected in m3_canonical.items():
        if m3.get(key) != expected:
            errors.append(f"CONFIG_M3:{key}")

    metadata = manifest.get("metadata")
    if not isinstance(metadata, Mapping):
        errors.append("MANIFEST_METADATA")
        return 0
    metadata_expected = {
        "price_contract": "reduced_open_close_volume_v1",
        "universe_contract": "technical_candidate_union_v1",
        "candidate_union_is_point_in_time": False,
        "stock_price_basis": "CHUA_XAC_NHAN",
        "stock_price_basis_confirmed": False,
        "benchmark_contract": "close_only",
        "benchmark_unit": "index_points",
        "benchmark_price_basis_confirmed": False,
        "stock_benchmark_price_basis_equality_required": False,
        "corporate_actions_applied": False,
        "corporate_actions_inventory_complete": False,
        "high_low_present_in_stock_input": False,
        "high_low_used": False,
        "high_low_synthesized": False,
        "replacement_feature_for_high_low": False,
        "research_gate": "FAIL",
        "technical_validation_only": True,
    }
    for key, expected in metadata_expected.items():
        if metadata.get(key) != expected:
            errors.append(f"METADATA:{key}")
    if metadata.get("research_gate_reasons") != list(RESEARCH_REASONS):
        errors.append("METADATA:research_gate_reasons")
    expected_count = metadata.get("candidate_union_expected_count")
    observed_count = metadata.get("candidate_union_observed_count")
    publication_expected = metadata.get("publication_expected_symbol_count")
    publication_observed = metadata.get("publication_observed_symbol_count")
    if not isinstance(expected_count, int) or expected_count <= 0:
        errors.append("METADATA:candidate_union_expected_count")
        return 0
    if not (expected_count == observed_count == publication_expected == publication_observed):
        errors.append("METADATA:SYMBOL_COUNTS")
    if metadata.get("publication_expected_row_count") != metadata.get("publication_observed_row_count"):
        errors.append("METADATA:ROW_COUNTS")
    return expected_count


def _check_features(root: Path, errors: list[str]) -> None:
    raw_fields, _ = _csv(root / "feature_raw.csv")
    processed_fields, _ = _csv(root / "feature_sau_tien_xu_ly.csv")
    if FORBIDDEN_FEATURE in raw_fields or FORBIDDEN_FEATURE in processed_fields:
        errors.append("FEATURE_HIGH_LOW_PRESENT")
    raw_features = raw_fields[9:]
    processed_features = processed_fields[6:]
    if len(raw_features) != 23 or raw_features != processed_features:
        errors.append("FEATURE_COLUMNS_REDUCED")


def _check_ranking(root: Path, errors: list[str]) -> None:
    _, rows = _csv(root / "xep_hang.csv")
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault((row["chien_luoc"], row["ngay"]), []).append(row)
    for key, items in groups.items():
        expected = sorted(items, key=lambda row: (-float(row["diem"]), row["ma"]))
        for index, row in enumerate(expected, 1):
            if int(row["thu_hang"]) != index:
                errors.append(f"RANK_ORDER:{key}")
                break
            selected = row["duoc_chon"] == "true"
            if selected != (index <= 2):
                errors.append(f"RANK_TOP_K:{key}")
                break
            expected_weight = Decimal("0.5") if selected else Decimal("0")
            if _decimal(row["ty_trong_muc_tieu"], "ranking.weight") != expected_weight:
                errors.append(f"RANK_WEIGHT:{key}")
                break


def _check_backtest(root: Path, errors: list[str]) -> list[dict[str, object]]:
    _, nav_rows = _csv(root / "nav.csv")
    _, ledger_rows = _csv(root / "so_cai.csv")
    _, order_rows = _csv(root / "lenh.csv")
    _, fill_rows = _csv(root / "khop_lenh.csv")
    _, position_rows = _csv(root / "vi_the.csv")
    _, event_rows = _csv(root / "su_kien_da_ap_dung.csv")
    if event_rows:
        errors.append("CORPORATE_ACTION_APPLIED")
    nav_by_key: dict[tuple[str, str], Decimal] = {}
    nav_dates: dict[str, list[str]] = {}
    for row in nav_rows:
        nav = _decimal(row["nav"], "nav")
        cash = _decimal(row["tien_mat"], "nav.cash")
        assert nav is not None and cash is not None
        if nav <= 0 or cash < 0:
            errors.append("NAV_OR_CASH_NEGATIVE")
        key = (row["chien_luoc"], row["ngay"])
        if key in nav_by_key:
            errors.append("NAV_DUPLICATE")
        nav_by_key[key] = nav
        nav_dates.setdefault(row["chien_luoc"], []).append(row["ngay"])
    for strategy in nav_dates:
        nav_dates[strategy] = sorted(set(nav_dates[strategy]))
    reconciliation: list[dict[str, object]] = []
    for row in ledger_rows:
        key = (row["chien_luoc"], row["ngay"])
        ledger_nav = _decimal(row["nav"], "ledger.nav")
        cash = _decimal(row["tien_mat_cuoi_ngay"], "ledger.cash")
        diff = _decimal(row["chenh_lech_doi_soat"], "ledger.reconciliation")
        assert ledger_nav is not None and cash is not None and diff is not None
        nav = nav_by_key.get(key)
        if nav is None or nav != ledger_nav:
            errors.append("NAV_LEDGER_MISMATCH")
        if cash < 0 or diff != 0:
            errors.append("LEDGER_INVALID")
        reconciliation.append({
            "chien_luoc": key[0], "ngay": key[1], "nav": str(nav or ""),
            "nav_so_cai": str(ledger_nav), "chenh_lech": str((nav - ledger_nav) if nav is not None else ""),
        })
    for row in position_rows:
        quantity = _decimal(row["so_luong"], "position.quantity")
        value = _decimal(row["gia_tri_thi_truong"], "position.value")
        assert quantity is not None and value is not None
        if quantity < 0 or value < 0:
            errors.append("POSITION_NEGATIVE")
    for row in fill_rows:
        quantity = _decimal(row["so_luong"], "fill.quantity")
        price = _decimal(row["gia_khop"], "fill.price")
        assert quantity is not None and price is not None
        if quantity <= 0 or price <= 0:
            errors.append("FILL_INVALID")
    for row in order_rows:
        execution = row["ngay_thuc_thi"]
        if not execution:
            continue
        dates = nav_dates.get(row["chien_luoc"], [])
        try:
            index = dates.index(row["ngay_tin_hieu"])
        except ValueError:
            errors.append("ORDER_SIGNAL_NOT_IN_NAV")
            continue
        if index + 1 >= len(dates) or execution != dates[index + 1]:
            errors.append("ORDER_NOT_EXACT_T1")
    reconciliation.sort(key=lambda row: (str(row["chien_luoc"]), str(row["ngay"])))
    return reconciliation


def _csv_text(rows: Iterable[Mapping[str, object]]) -> bytes:
    fields = ("chien_luoc", "ngay", "nav", "nav_so_cai", "chenh_lech")
    memory = StringIO(newline="")
    writer = csv.DictWriter(memory, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return memory.getvalue().encode("utf-8")


def _publish(destination: Path, report: bytes, reconciliation: bytes) -> Path:
    if destination.exists():
        raise FileExistsError("Khong ghi de thu muc audit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        payloads = {
            "bao_cao_kiem_toan_doc_lap.json": report,
            "doi_soat_nav.csv": reconciliation,
        }
        hashes = "".join(
            f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
            for name, payload in sorted(payloads.items())
        ).encode("utf-8")
        payloads["sha256.txt"] = hashes
        for name, payload in sorted(payloads.items()):
            with (staging / name).open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(staging, destination)
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def kiem_toan_san_pham(
    *,
    thu_muc_san_pham: Path,
    thu_muc_bao_cao: Path,
    ma_kiem_toan: str,
) -> tuple[bool, Path]:
    root = Path(thu_muc_san_pham)
    errors: list[str] = []
    reconciliation: list[dict[str, object]] = []
    try:
        manifest = _check_manifest(root, errors)
        expected_count = _check_config_and_metadata(root, manifest, errors)
        _check_features(root, errors)
        _check_ranking(root, errors)
        reconciliation = _check_backtest(root, errors)
    except Exception as exc:
        errors.append(f"AUDIT_EXCEPTION:{type(exc).__name__}:{exc}")
        expected_count = 0
    unique_errors = sorted(set(errors))
    passed = not unique_errors
    report_obj = {
        "audit_contract_version": "m4_product_audit_v1",
        "ma_kiem_toan": ma_kiem_toan,
        "hop_le": passed,
        "candidate_union_expected_count": expected_count,
        "loi": unique_errors,
        "pipeline_duoc_goi": False,
        "huan_luyen_lai": False,
        "san_pham_bi_sua": False,
    }
    report = (json.dumps(report_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    destination = _publish(Path(thu_muc_bao_cao), report, _csv_text(reconciliation))
    return passed, destination


def tao_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.nghien_cuu_moc_4.kiem_toan_san_pham")
    parser.add_argument("--thu-muc-san-pham", type=Path, required=True)
    parser.add_argument("--thu-muc-bao-cao", type=Path, required=True)
    parser.add_argument("--ma-kiem-toan", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = tao_parser().parse_args(argv)
    passed, destination = kiem_toan_san_pham(
        thu_muc_san_pham=args.thu_muc_san_pham,
        thu_muc_bao_cao=args.thu_muc_bao_cao,
        ma_kiem_toan=args.ma_kiem_toan,
    )
    print(json.dumps({"hop_le": passed, "thu_muc_bao_cao": str(destination)}, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
