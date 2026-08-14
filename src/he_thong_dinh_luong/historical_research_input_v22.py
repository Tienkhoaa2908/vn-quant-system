"""Rebuild the complete monthly Model Lab input from the DNSE historical store.

The existing daily EOD path only replaces the latest month in a previous input
ZIP.  This module intentionally rebuilds ``feature_raw.csv`` and ``nhan.csv``
from scratch so historical coverage can extend back to the local SQLite store.

The current DNSE price basis and candidate universe are not point-in-time
research contracts.  Outputs therefore remain technical-validation-only and
must not be represented as research-grade or live-capital evidence.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Iterable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .dnse_historical_store_v20 import (
    DnseHistoricalStore,
    PRICE_BASIS,
    SCHEMA_VERSION as STORE_SCHEMA_VERSION,
)
from .extended_history_reference_v18 import inspect_input_history
from .nghien_cuu_moc_4.dac_trung import (
    FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1,
    phien_cuoi_thang,
    tao_feature_cuoi_thang,
)
from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    REQUIRED_INPUT_FILES,
    _load_verified_input,
)
from .nghien_cuu_moc_4.mo_hinh import (
    ThanhBenchmarkDongCua,
    ThanhGiaMoDongKhoiLuong,
)
from .nghien_cuu_moc_4.nhan import tao_nhan

SCHEMA_VERSION = "historical_research_input_v22"
OUTPUT_ZIP = "daily_prediction_input.zip"
REPORT_FILE = "historical_research_input_v22.json"
SIBLING_MANIFEST = "manifest.json"

FEATURE_PREFIX = (
    "ngay",
    "ma",
    "hop_le",
    "ly_do",
    "eligible",
    "ly_do_eligibility",
    "gtgd_tb_20_eligibility",
    "T1",
    "open_t1_hop_le",
)
LABEL_FIELDS = (
    "ngay",
    "ma",
    "T_H",
    "ngay_ket_thuc_nhan",
    "loi_nhuan_co_phieu",
    "loi_nhuan_benchmark",
    "loi_nhuan_tuong_doi",
    "nhan",
    "ly_do_nhan_rong",
)
WARNINGS = (
    "PRICE_BASIS_CHUA_XAC_NHAN",
    "CORPORATE_ACTIONS_CHUA_DAY_DU",
    "CANDIDATE_UNION_IS_NOT_POINT_IN_TIME",
    "SURVIVORSHIP_BIAS_NOT_RESOLVED",
    "TECHNICAL_VALIDATION_ONLY",
    "T_PLUS_ONE_IS_EXECUTION_ONLY_NOT_MODEL_VALIDATION",
)


def _sha_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _csv_bytes(
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(fields),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8-sig")


def _format(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".15g")
    return str(value)


def _safe_zip_names(names: Iterable[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"HISTORICAL_INPUT_TEMPLATE_UNSAFE_PATH:{name}")


def _read_template(path: Path) -> tuple[dict[str, bytes], dict[str, object]]:
    source = Path(path)
    _load_verified_input(source)
    with ZipFile(source) as archive:
        names = archive.namelist()
        _safe_zip_names(names)
        blobs = {name: archive.read(name) for name in REQUIRED_INPUT_FILES}
    manifest = json.loads(blobs["manifest.json"])
    config = json.loads(blobs["cau_hinh.json"])
    if not isinstance(manifest, dict) or not isinstance(config, dict):
        raise ValueError("HISTORICAL_INPUT_TEMPLATE_INVALID")
    return blobs, config


def _config_section(config: Mapping[str, object]) -> Mapping[str, object]:
    raw = config.get("moc_4", config)
    if not isinstance(raw, Mapping):
        raise ValueError("HISTORICAL_INPUT_CONFIG_M4_INVALID")
    return raw


def _updated_config(
    raw_config: Mapping[str, object],
    *,
    symbol_count: int,
) -> bytes:
    config = json.loads(json.dumps(raw_config))
    section = config.get("moc_4", config)
    if not isinstance(section, dict):
        raise ValueError("HISTORICAL_INPUT_CONFIG_M4_INVALID")
    order = tuple(str(value) for value in section.get("feature_order", ()))
    if order != FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1:
        raise ValueError(
            "HISTORICAL_INPUT_REQUIRES_REDUCED_CANONICAL_FEATURE_ORDER"
        )
    updates = {
        "muc_dich_lan_chay": "kiem_tra_ky_thuat",
        "price_contract": "reduced_open_close_volume_v1",
        "universe_contract": "technical_candidate_union_v1",
        "stock_price_basis": PRICE_BASIS,
        "stock_price_basis_confirmed": False,
        "corporate_actions_day_du": False,
        "candidate_union_name": f"dnse_static_seed_{symbol_count}_v22",
        "candidate_union_expected_count": symbol_count,
        "candidate_union_is_point_in_time": False,
        "benchmark_price_basis_confirmed": False,
    }
    for key, value in updates.items():
        if key in section:
            section[key] = value
    return _json_bytes(config)


def _load_store_rows(
    store_path: Path,
    *,
    start: date | None,
    end: date | None,
) -> tuple[
    tuple[ThanhGiaMoDongKhoiLuong, ...],
    tuple[ThanhBenchmarkDongCua, ...],
    dict[str, object],
]:
    store = DnseHistoricalStore(store_path)
    status = store.status()
    if int(status.get("conflict_count", 0)) != 0:
        raise ValueError("HISTORICAL_INPUT_STORE_HAS_CONFLICTS")
    raw_stocks = store.rows("STOCK", start, end)
    raw_index = store.rows("INDEX", start, end)
    if not raw_stocks:
        raise ValueError("HISTORICAL_INPUT_STOCK_ROWS_EMPTY")
    if not raw_index:
        raise ValueError("HISTORICAL_INPUT_VNINDEX_ROWS_EMPTY")
    index_symbols = {str(row["symbol"]) for row in raw_index}
    if index_symbols != {"VNINDEX"}:
        raise ValueError(f"HISTORICAL_INPUT_INDEX_IDENTITY_INVALID:{index_symbols}")

    stocks = tuple(
        ThanhGiaMoDongKhoiLuong(
            ma=str(row["symbol"]),
            ngay=date.fromisoformat(str(row["day"])),
            gia_mo_cua=float(row["open"]),
            gia_dong_cua=float(row["close"]),
            khoi_luong=int(row["volume"]),
            nguon=str(row["source"]),
            phien_ban=str(row["source_version"]),
            co_so_gia=str(row["price_basis"]),
            raw_sha256=str(row["normalized_sha256"]),
        )
        for row in raw_stocks
    )
    benchmark = tuple(
        ThanhBenchmarkDongCua(
            ma="VNINDEX",
            ngay=date.fromisoformat(str(row["day"])),
            gia_dong_cua=float(row["close"]),
            nguon=str(row["source"]),
            phien_ban=str(row["source_version"]),
            co_so_gia=str(row["price_basis"]),
        )
        for row in raw_index
    )
    calendar = tuple(row.ngay for row in benchmark)
    if calendar != tuple(sorted(set(calendar))):
        raise ValueError("HISTORICAL_INPUT_BENCHMARK_CALENDAR_INVALID")
    return stocks, benchmark, status


def _feature_and_label_payloads(
    *,
    stocks: Sequence[ThanhGiaMoDongKhoiLuong],
    benchmark: Sequence[ThanhBenchmarkDongCua],
    config: Mapping[str, object],
) -> tuple[bytes, bytes, dict[str, object]]:
    section = _config_section(config)
    order = tuple(str(value) for value in section.get("feature_order", ()))
    required = tuple(str(value) for value in section.get("feature_bat_buoc", ()))
    if order != FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1 or required != order:
        raise ValueError("HISTORICAL_INPUT_FEATURE_CONTRACT_INVALID")
    label_horizon = int(section.get("label_horizon", 20))
    if label_horizon != 20:
        raise ValueError("HISTORICAL_INPUT_LABEL_HORIZON_MUST_BE_20")
    liquidity_threshold = float(section.get("nguong_gtgd_tb_toi_thieu", 0.0))

    calendar = tuple(row.ngay for row in benchmark)
    signal_dates = phien_cuoi_thang(calendar)
    features = tao_feature_cuoi_thang(
        stocks,
        benchmark,
        lich_benchmark=calendar,
        feature_order=order,
        feature_bat_buoc=required,
    )
    labels = tao_nhan(
        stocks,
        benchmark,
        cac_ngay_tin_hieu=signal_dates,
        label_horizon=label_horizon,
        lich_benchmark=calendar,
    )

    calendar_index = {day: index for index, day in enumerate(calendar)}
    stock_days = {(row.ma, row.ngay) for row in stocks}
    feature_rows: list[dict[str, object]] = []
    complete_count = 0
    eligible_count = 0
    for feature in sorted(features, key=lambda row: (row.ngay, row.ma)):
        idx = calendar_index[feature.ngay]
        t1 = calendar[idx + 1] if idx + 1 < len(calendar) else None
        open_t1_ok = t1 is not None and (feature.ma, t1) in stock_days
        reasons = list(feature.ly_do)
        ma250 = feature.gia_tri.get("gia_tren_ma250")
        liquidity = feature.gia_tri.get("gtgd_tb_20")
        if ma250 is not True:
            reasons.append("khong_dat_ma250")
        if liquidity is None or isinstance(liquidity, bool):
            reasons.append("thieu_gtgd_tb_20")
        elif float(liquidity) < liquidity_threshold:
            reasons.append("khong_dat_thanh_khoan")
        if not open_t1_ok:
            reasons.append("thieu_open_t1")
        eligible = bool(
            feature.hop_le
            and ma250 is True
            and liquidity is not None
            and not isinstance(liquidity, bool)
            and float(liquidity) >= liquidity_threshold
            and open_t1_ok
        )
        complete_count += int(feature.hop_le)
        eligible_count += int(eligible)
        row: dict[str, object] = {
            "ngay": feature.ngay.isoformat(),
            "ma": feature.ma,
            "hop_le": str(feature.hop_le).lower(),
            "ly_do": "|".join(sorted(set(feature.ly_do))),
            "eligible": str(eligible).lower(),
            "ly_do_eligibility": "|".join(sorted(set(reasons))) if not eligible else "",
            "gtgd_tb_20_eligibility": _format(liquidity),
            "T1": _format(t1),
            "open_t1_hop_le": str(open_t1_ok).lower(),
        }
        for name in order:
            row[name] = _format(feature.gia_tri.get(name))
        feature_rows.append(row)

    label_rows = [
        {
            "ngay": item.ngay.isoformat(),
            "ma": item.ma,
            "T_H": _format(item.T_H),
            "ngay_ket_thuc_nhan": _format(item.ngay_ket_thuc_nhan),
            "loi_nhuan_co_phieu": _format(item.loi_nhuan_co_phieu),
            "loi_nhuan_benchmark": _format(item.loi_nhuan_benchmark),
            "loi_nhuan_tuong_doi": _format(item.loi_nhuan_tuong_doi),
            "nhan": _format(item.nhan),
            "ly_do_nhan_rong": _format(item.ly_do_nhan_rong),
        }
        for item in sorted(labels, key=lambda row: (row.ngay, row.ma))
    ]
    labeled_count = sum(
        1 for item in labels
        if item.ngay_ket_thuc_nhan is not None
        and item.loi_nhuan_tuong_doi is not None
    )
    summary = {
        "calendar_first_day": calendar[0].isoformat(),
        "calendar_last_day": calendar[-1].isoformat(),
        "calendar_session_count": len(calendar),
        "monthly_signal_date_count": len(signal_dates),
        "first_monthly_signal_date": signal_dates[0].isoformat(),
        "last_monthly_signal_date": signal_dates[-1].isoformat(),
        "feature_row_count": len(feature_rows),
        "complete_feature_row_count": complete_count,
        "eligible_feature_row_count": eligible_count,
        "label_row_count": len(label_rows),
        "labeled_row_count": labeled_count,
    }
    return (
        _csv_bytes(feature_rows, FEATURE_PREFIX + order),
        _csv_bytes(label_rows, LABEL_FIELDS),
        summary,
    )


def build_historical_research_input(
    *,
    store_path: Path,
    template_input_zip: Path,
    output_dir: Path,
    start: date | None = None,
    end: date | None = None,
    evaluation_months: int = 72,
    minimum_train_months: int = 60,
    minimum_outer_test_periods: int = 48,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"HISTORICAL_INPUT_OUTPUT_EXISTS:{destination}")
    store_source = Path(store_path).resolve()
    template_source = Path(template_input_zip).resolve()
    if not store_source.is_file():
        raise FileNotFoundError(f"HISTORICAL_INPUT_STORE_MISSING:{store_source}")
    if not template_source.is_file():
        raise FileNotFoundError(
            f"HISTORICAL_INPUT_TEMPLATE_MISSING:{template_source}"
        )

    _, template_config = _read_template(template_source)
    stocks, benchmark, store_status = _load_store_rows(
        store_source,
        start=start,
        end=end,
    )
    symbols = tuple(sorted({row.ma for row in stocks}))
    config_blob = _updated_config(template_config, symbol_count=len(symbols))
    config = json.loads(config_blob)
    feature_blob, label_blob, data_summary = _feature_and_label_payloads(
        stocks=stocks,
        benchmark=benchmark,
        config=config,
    )
    metrics_blob = _json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "INPUT_ONLY_NOT_EVALUATED",
            "model_quality_evaluated": False,
            "technical_validation_only": True,
            "research_eligible": False,
            "warnings": list(WARNINGS),
        }
    )
    product_blobs = {
        "cau_hinh.json": config_blob,
        "feature_raw.csv": feature_blob,
        "nhan.csv": label_blob,
        "chi_so_mo_hinh.json": metrics_blob,
    }
    input_manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "files": {
            name: {"sha256": _sha_bytes(payload), "size": len(payload)}
            for name, payload in sorted(product_blobs.items())
        },
        "source_store_schema_version": STORE_SCHEMA_VERSION,
        "source_store_path": str(store_source),
        "source_store_sha256": _sha_file(store_source),
        "template_input_zip": str(template_source),
        "template_input_zip_sha256": _sha_file(template_source),
        "price_basis": PRICE_BASIS,
        "candidate_union_name": f"dnse_static_seed_{len(symbols)}_v22",
        "candidate_union_is_point_in_time": False,
        "technical_validation_only": True,
        "research_eligible": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
        "warnings": list(WARNINGS),
        "data_summary": data_summary,
    }
    product_blobs["manifest.json"] = _json_bytes(input_manifest)

    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        staging_zip = staging / OUTPUT_ZIP
        with ZipFile(staging_zip, "w", compression=ZIP_DEFLATED) as archive:
            for name in sorted(product_blobs):
                archive.writestr(name, product_blobs[name])
        _load_verified_input(staging_zip)
        preflight = inspect_input_history(
            staging_zip,
            evaluation_months=evaluation_months,
            minimum_train_months=minimum_train_months,
            minimum_outer_test_periods=minimum_outer_test_periods,
        )
        final_zip = destination / OUTPUT_ZIP
        preflight["input_zip"] = str(final_zip)
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "output_dir": str(destination),
            "output_zip": str(final_zip),
            "output_zip_sha256": _sha_file(staging_zip),
            "store_path": str(store_source),
            "store_sha256": _sha_file(store_source),
            "template_input_zip": str(template_source),
            "template_input_zip_sha256": _sha_file(template_source),
            "stock_symbol_count": len(symbols),
            "stock_row_count": len(stocks),
            "benchmark_row_count": len(benchmark),
            "store_status": store_status,
            "data_summary": data_summary,
            "extended_history_preflight": preflight,
            "technical_validation_only": True,
            "research_eligible": False,
            "automatic_live_orders_allowed": False,
            "live_capital_approved": False,
            "warnings": list(WARNINGS),
        }
        (staging / REPORT_FILE).write_bytes(_json_bytes(report))
        sibling_manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "session_date": data_summary["last_monthly_signal_date"],
            "daily_prediction_input": {
                "path": str(final_zip),
                "sha256": report["output_zip_sha256"],
                "size": staging_zip.stat().st_size,
            },
            "report_file": REPORT_FILE,
            "technical_validation_only": True,
            "research_eligible": False,
        }
        (staging / SIBLING_MANIFEST).write_bytes(_json_bytes(sibling_manifest))
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.historical_research_input_v22"
    )
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--template-input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--evaluation-months", type=int, default=72)
    parser.add_argument("--minimum-train-months", type=int, default=60)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=48)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_historical_research_input(
            store_path=args.store,
            template_input_zip=args.template_input_zip,
            output_dir=args.output_dir,
            start=args.start,
            end=args.end,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "OUTPUT_ZIP",
    "REPORT_FILE",
    "build_historical_research_input",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
