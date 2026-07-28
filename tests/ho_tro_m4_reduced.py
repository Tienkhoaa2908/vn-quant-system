from __future__ import annotations

import csv
from datetime import date, timedelta
import hashlib
from io import StringIO
import json
import math
from pathlib import Path

from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1
from he_thong_dinh_luong.nghien_cuu_moc_4.runner_io import COT_REDUCED


def weekdays(start: date, count: int) -> list[date]:
    result: list[date] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def csv_bytes(fields: tuple[str, ...] | list[str], rows: list[dict[str, object]]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def tao_publication_rut_gon(
    root: Path,
    *,
    symbols: tuple[str, ...] = ("AAA", "BBB", "CCC"),
    count: int = 1050,
    fractional_volume: bool = False,
) -> tuple[Path, list[date]]:
    root.mkdir(parents=True)
    dates = weekdays(date(2021, 1, 4), count)
    rows: list[dict[str, object]] = []
    for symbol_index, symbol in enumerate(symbols):
        raw_hash = hashlib.sha256(f"raw:{symbol}".encode()).hexdigest()
        for index, day in enumerate(dates):
            close = (
                100.0 + 8.0 * symbol_index + 0.018 * index
                + 4.0 * math.sin(index / 9.0 + symbol_index * 1.7)
                + 1.5 * math.sin(index / 31.0 + symbol_index)
            )
            rows.append({
                "ma": symbol,
                "ngay": day.isoformat(),
                "gia_mo_cua": f"{close - 0.15:.8f}",
                "gia_dong_cua": f"{close:.8f}",
                "khoi_luong": "1000.5" if fractional_volume and index == 0 and symbol_index == 0 else str(100000 + 1000 * symbol_index + index % 23),
                "nguon": "fixture_reduced",
                "phien_ban": "v1",
                "co_so_gia": "CHUA_XAC_NHAN",
                "raw_sha256": raw_hash,
            })
    price = csv_bytes(COT_REDUCED, rows)
    coverage = json_bytes({
        "tong_ma": len(symbols),
        "so_ma_dat": len(symbols),
        "tong_so_dong": len(rows),
    })
    excluded = json_bytes({"so_ma_bi_loai": 0, "ma_bi_loai": []})
    payloads = {
        "du_lieu_gia_mo_dong_khoi_luong.csv": price,
        "bao_cao_do_phu_hop_dong_rut_gon.json": coverage,
        "bao_cao_ma_bi_loai.json": excluded,
    }
    manifest = {
        "hop_dong": {
            "cot": list(COT_REDUCED),
            "co_so_gia": "CHUA_XAC_NHAN",
            "high_low_trong_san_pham": False,
            "chi_dung_kiem_tra_ky_thuat": True,
        },
        "raw": [{"ma": symbol, "sha256": hashlib.sha256(f"raw:{symbol}".encode()).hexdigest()} for symbol in symbols],
        "san_pham_sha256": {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
    }
    payloads["manifest.json"] = json_bytes(manifest)
    for name, payload in payloads.items():
        write(root / name, payload)
    sha_text = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in sorted(payloads.items())
    ).encode("utf-8")
    write(root / "sha256.txt", sha_text)
    return root, dates


def tao_dau_vao_runner(root: Path, *, symbols: tuple[str, ...] = ("AAA", "BBB", "CCC"), count: int = 1050) -> dict[str, Path]:
    publication, dates = tao_publication_rut_gon(root / "publication", symbols=symbols, count=count)
    calendar = root / "lich_benchmark.csv"
    write(calendar, csv_bytes(("ngay",), [{"ngay": day.isoformat()} for day in dates]))
    benchmark = root / "benchmark.csv"
    benchmark_rows = []
    for index, day in enumerate(dates):
        close = 1000 + 0.12 * index + 2.2 * math.sin(index / 18.0)
        benchmark_rows.append({
            "ma": "VNINDEX", "ngay": day.isoformat(), "gia_dong_cua": f"{close:.8f}",
            "nguon": "fixture_benchmark", "phien_ban": "v1", "co_so_gia": "benchmark_basis_fixture",
        })
    write(benchmark, csv_bytes(("ma", "ngay", "gia_dong_cua", "nguon", "phien_ban", "co_so_gia"), benchmark_rows))
    pit = root / "pit.csv"
    write(pit, csv_bytes(
        ("loai_du_lieu", "khoa_ban_ghi", "ngay_hieu_luc", "nguon", "phien_ban", "thoi_diem_cong_bo", "du_lieu_json"),
        [{
            "loai_du_lieu": "benchmark_metadata", "khoa_ban_ghi": "VNINDEX",
            "ngay_hieu_luc": dates[0].isoformat(), "nguon": "fixture_metadata",
            "phien_ban": "v1", "thoi_diem_cong_bo": "2020-12-31T10:00:00+07:00",
            "du_lieu_json": json.dumps({"ma": "VNINDEX"}, separators=(",", ":")),
        }],
    ))
    config = root / "cau_hinh.json"
    config.write_text(json.dumps({
        "moc_4": {
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
            "candidate_union_name": "technical_candidate_union_fixture",
            "candidate_union_expected_count": len(symbols),
            "candidate_union_is_point_in_time": False,
            "corporate_actions_day_du": False,
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
            "feature_order": list(FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1),
            "feature_bat_buoc": list(FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1),
            "C_grid": [0.1, 1.0, 10.0],
            "solver": "lbfgs", "max_iter": 1000, "class_weight": None,
            "seed": 20260725, "thu_muc_dau_ra": ".",
        },
        "mo_phong": {
            "von_ban_dau": "1000000000", "phi_mua_bps": "15", "phi_ban_bps": "15",
            "thue_ban_bps": "100", "truot_gia_bps": "10", "kich_thuoc_lo": 1,
            "so_phien_moi_nam": 250, "lai_suat_phi_rui_ro": "0",
            "che_do_ma_khong_xuat_hien": "muc_tieu_bang_0",
            "cho_phep_ban_le_khi_dong_vi_the": False,
            "co_so_gia": "dieu_chinh", "don_vi_gia": "dong", "don_vi_tien": "dong",
        },
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return {
        "cau_hinh": config, "publication": publication, "benchmark": benchmark,
        "lich_benchmark": calendar, "corporate_actions": pit,
    }
