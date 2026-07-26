from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import FEATURE_ORDER_MAC_DINH
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import CauHinhMoc4, ThanhOHLCV


def cau_hinh_mapping(tmp: str = "/tmp/m4-output", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "muc_dich_lan_chay": "kiem_tra_ky_thuat",
        "tan_suat_mau_mo_hinh": "cuoi_thang",
        "benchmark": "VNINDEX",
        "co_so_gia": "gia_dieu_chinh",
        "co_so_gia_da_xac_nhan": False,
        "corporate_actions_day_du": False,
        "label_horizon": 20,
        "purge_phien": 20,
        "embargo_phien": 0,
        "so_thang_train_toi_thieu": 3,
        "so_thang_validation": 1,
        "so_thang_test": 1,
        "top_k": 3,
        "cua_so_thanh_khoan": 20,
        "nguong_gtgd_tb_toi_thieu": 0.0,
        "ty_le_coverage_toi_thieu": 0.0,
        "so_ma_eligible_toi_thieu": 0,
        "feature_order": list(FEATURE_ORDER_MAC_DINH),
        "feature_bat_buoc": list(FEATURE_ORDER_MAC_DINH),
        "C_grid": [0.1, 1.0, 10.0],
        "solver": "lbfgs",
        "max_iter": 1000,
        "class_weight": None,
        "seed": 20260725,
        "thu_muc_dau_ra": tmp,
    }
    data.update(overrides)
    return data


def cau_hinh(**overrides: object) -> CauHinhMoc4:
    return CauHinhMoc4.tu_mapping(cau_hinh_mapping(**overrides))


def weekdays(start: date, count: int) -> list[date]:
    result: list[date] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def bars(symbol: str, dates: Iterable[date], *, base: float = 100.0, step: float = 0.25, missing: set[date] | None = None) -> list[ThanhOHLCV]:
    missing = missing or set()
    result: list[ThanhOHLCV] = []
    for i, day in enumerate(dates):
        if day in missing:
            continue
        close = base + i * step
        result.append(ThanhOHLCV(
            ma=symbol, ngay=day, gia_mo_cua=close - 0.1, gia_cao_nhat=close + 1.0,
            gia_thap_nhat=close - 1.0, gia_dong_cua=close, khoi_luong=1000 + i,
        ))
    return result

UTC = timezone.utc
SIGNAL_TIME = datetime(2026, 1, 30, 15, 0, tzinfo=UTC)
