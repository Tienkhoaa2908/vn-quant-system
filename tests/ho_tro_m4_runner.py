from __future__ import annotations

import csv
from datetime import date, timedelta
import json
import math
from pathlib import Path

from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import FEATURE_ORDER_MAC_DINH


def weekdays(start: date, count: int) -> list[date]:
    result: list[date] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def tao_fixture_runner(root: Path, *, count: int = 520) -> dict[str, Path]:
    dates = weekdays(date(2024, 1, 2), count)
    calendar = root / "lich_benchmark.csv"
    write_csv(calendar, ["ngay"], [{"ngay": day.isoformat()} for day in dates])
    fields = [
        "ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat",
        "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia",
    ]
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    stock_rows: list[dict[str, object]] = []
    for index_symbol, symbol in enumerate(symbols):
        phase = index_symbol * 1.3
        for index, day in enumerate(dates):
            close = (
                100 + index_symbol * 15 + 0.025 * index
                + 5.0 * math.sin(index / 8.0 + phase)
                + 2.0 * math.sin(index / 27.0 + phase / 2)
            )
            stock_rows.append({
                "ma": symbol, "ngay": day.isoformat(),
                "gia_mo_cua": f"{close - 0.2:.8f}",
                "gia_cao_nhat": f"{close + 1.0:.8f}",
                "gia_thap_nhat": f"{close - 1.0:.8f}",
                "gia_dong_cua": f"{close:.8f}",
                "khoi_luong": 100000 + index_symbol * 10000 + index % 17 * 100,
                "nguon": "fixture_stock", "phien_ban": "v1", "co_so_gia": "gia_dieu_chinh",
            })
    stock = root / "ohlcv.csv"
    write_csv(stock, fields, stock_rows)
    benchmark_rows: list[dict[str, object]] = []
    for index, day in enumerate(dates):
        close = 1000 + 0.2 * index + 2.0 * math.sin(index / 20.0)
        benchmark_rows.append({
            "ma": "VNINDEX", "ngay": day.isoformat(),
            "gia_mo_cua": f"{close - 0.3:.8f}", "gia_cao_nhat": f"{close + 1.0:.8f}",
            "gia_thap_nhat": f"{close - 1.0:.8f}", "gia_dong_cua": f"{close:.8f}",
            "khoi_luong": 1000000 + index, "nguon": "fixture_benchmark",
            "phien_ban": "v1", "co_so_gia": "gia_dieu_chinh",
        })
    benchmark = root / "benchmark.csv"
    write_csv(benchmark, fields, benchmark_rows)
    universe = root / "universe.csv"
    write_csv(
        universe,
        ["ngay_hieu_luc", "ma", "thuoc_universe", "nguon", "phien_ban", "thoi_diem_cong_bo"],
        [{
            "ngay_hieu_luc": dates[0].isoformat(), "ma": symbol, "thuoc_universe": "true",
            "nguon": "fixture_universe", "phien_ban": "v1",
            "thoi_diem_cong_bo": "2023-12-29T10:00:00+07:00",
        } for symbol in symbols],
    )
    pit = root / "corporate_actions_metadata.csv"
    write_csv(
        pit,
        ["loai_du_lieu", "khoa_ban_ghi", "ngay_hieu_luc", "nguon", "phien_ban", "thoi_diem_cong_bo", "du_lieu_json"],
        [{
            "loai_du_lieu": "benchmark_metadata", "khoa_ban_ghi": "VNINDEX",
            "ngay_hieu_luc": dates[0].isoformat(), "nguon": "fixture_metadata",
            "phien_ban": "v1", "thoi_diem_cong_bo": "2023-12-29T10:00:00+07:00",
            "du_lieu_json": json.dumps({"ma": "VNINDEX"}, separators=(",", ":")),
        }],
    )
    config = root / "cau_hinh.json"
    config.write_text(json.dumps({
        "moc_4": {
            "muc_dich_lan_chay": "kiem_tra_ky_thuat",
            "tan_suat_mau_mo_hinh": "cuoi_thang",
            "benchmark": "VNINDEX", "co_so_gia": "gia_dieu_chinh",
            "co_so_gia_da_xac_nhan": False, "corporate_actions_day_du": False,
            "label_horizon": 20, "purge_phien": 20, "embargo_phien": 0,
            "so_thang_train_toi_thieu": 3, "so_thang_validation": 1,
            "so_thang_test": 1, "top_k": 2,
            "cua_so_thanh_khoan": 20,
            "nguong_gtgd_tb_toi_thieu": 0.0,
            "ty_le_coverage_toi_thieu": 0.0,
            "so_ma_eligible_toi_thieu": 0,
            "feature_order": list(FEATURE_ORDER_MAC_DINH),
            "feature_bat_buoc": list(FEATURE_ORDER_MAC_DINH),
            "C_grid": [0.1, 1.0, 10.0], "solver": "lbfgs", "max_iter": 1000,
            "class_weight": None, "seed": 20260725, "thu_muc_dau_ra": ".",
        },
        "mo_phong": {
            "von_ban_dau": "1000000000", "phi_mua_bps": "15", "phi_ban_bps": "15",
            "thue_ban_bps": "100", "truot_gia_bps": "10", "kich_thuoc_lo": 1,
            "so_phien_moi_nam": 252, "lai_suat_phi_rui_ro": "0",
            "che_do_ma_khong_xuat_hien": "muc_tieu_bang_0",
            "cho_phep_ban_le_khi_dong_vi_the": True, "co_so_gia": "dieu_chinh",
            "don_vi_gia": "dong", "don_vi_tien": "dong",
        },
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return {
        "cau_hinh": config, "ohlcv": stock, "benchmark": benchmark,
        "lich_benchmark": calendar, "universe": universe, "corporate_actions": pit,
    }
