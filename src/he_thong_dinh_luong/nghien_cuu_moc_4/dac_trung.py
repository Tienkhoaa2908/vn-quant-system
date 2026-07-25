"""Tinh feature MVP khong nhin truoc tai phien benchmark cuoi thang."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt
from statistics import fmean
from typing import Iterable, Sequence

from .mo_hinh import DongFeature, ThanhOHLCV

FEATURE_ORDER_MAC_DINH = (
    "khoang_cach_ma20", "khoang_cach_ma60", "khoang_cach_ma120", "khoang_cach_ma250",
    "gia_tren_ma250", "ty_le_dinh_52_tuan", "loi_nhuan_20", "loi_nhuan_60",
    "loi_nhuan_120", "loi_nhuan_250", "dong_luong_12_1", "suc_manh_tuong_doi_120",
    "bien_dong_20", "bien_dong_60", "bien_dong_giam_60",
    "bien_do_cao_thap_chuan_hoa", "gtgd_tb_20", "gtgd_tb_60",
    "gtgd_hien_tai_tren_tb60", "so_phien_volume_0_60", "vnindex_tren_ma250",
    "vnindex_momentum_60", "vnindex_bien_dong_20", "vnindex_bien_dong_60",
)


def phien_cuoi_thang(lich_benchmark: Iterable[date]) -> tuple[date, ...]:
    sessions = sorted(set(lich_benchmark))
    latest: dict[tuple[int, int], date] = {}
    for session in sessions:
        latest[(session.year, session.month)] = session
    return tuple(latest[key] for key in sorted(latest))


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("Can it nhat hai quan sat de tinh sample std.")
    mean = fmean(values)
    return sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))


def _returns(closes: Sequence[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _validate_bars(rows: Sequence[ThanhOHLCV]) -> None:
    keys = [(r.ma, r.ngay) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("OHLCV trung ma/ngay.")


def _feature_for_series(stock: Sequence[ThanhOHLCV], benchmark: Sequence[ThanhOHLCV]) -> dict[str, float | bool | int]:
    if len(stock) < 251 or len(benchmark) < 251:
        raise ValueError("thieu_warm_up")
    s_close = [float(x.gia_dong_cua) for x in stock]
    b_close = [float(x.gia_dong_cua) for x in benchmark]
    current = stock[-1]
    result: dict[str, float | bool | int] = {}
    for n in (20, 60, 120, 250):
        result[f"khoang_cach_ma{n}"] = s_close[-1] / fmean(s_close[-n:]) - 1.0
        result[f"loi_nhuan_{n}"] = s_close[-1] / s_close[-(n + 1)] - 1.0
    result["gia_tren_ma250"] = s_close[-1] >= fmean(s_close[-250:])
    result["ty_le_dinh_52_tuan"] = s_close[-1] / max(s_close[-250:])
    result["dong_luong_12_1"] = s_close[-21] / s_close[-251] - 1.0
    result["suc_manh_tuong_doi_120"] = result["loi_nhuan_120"] - (b_close[-1] / b_close[-121] - 1.0)
    s_returns = _returns(s_close)
    b_returns = _returns(b_close)
    result["bien_dong_20"] = _sample_std(s_returns[-20:])
    result["bien_dong_60"] = _sample_std(s_returns[-60:])
    result["bien_dong_giam_60"] = _sample_std([min(x, 0.0) for x in s_returns[-60:]])
    result["bien_do_cao_thap_chuan_hoa"] = (current.gia_cao_nhat - current.gia_thap_nhat) / current.gia_dong_cua
    traded = [float(x.gia_dong_cua) * x.khoi_luong for x in stock]
    result["gtgd_tb_20"] = fmean(traded[-20:])
    result["gtgd_tb_60"] = fmean(traded[-60:])
    result["gtgd_hien_tai_tren_tb60"] = traded[-1] / result["gtgd_tb_60"] if result["gtgd_tb_60"] else 0.0
    result["so_phien_volume_0_60"] = sum(1 for x in stock[-60:] if x.khoi_luong == 0)
    result["vnindex_tren_ma250"] = b_close[-1] >= fmean(b_close[-250:])
    result["vnindex_momentum_60"] = b_close[-1] / b_close[-61] - 1.0
    result["vnindex_bien_dong_20"] = _sample_std(b_returns[-20:])
    result["vnindex_bien_dong_60"] = _sample_std(b_returns[-60:])
    return result


def tao_feature_cuoi_thang(
    du_lieu_co_phieu: Iterable[ThanhOHLCV],
    du_lieu_benchmark: Iterable[ThanhOHLCV],
    *,
    feature_bat_buoc: Sequence[str] = FEATURE_ORDER_MAC_DINH,
) -> list[DongFeature]:
    stock_rows = list(du_lieu_co_phieu)
    benchmark_rows = list(du_lieu_benchmark)
    _validate_bars(stock_rows)
    _validate_bars(benchmark_rows)
    if not benchmark_rows:
        return []
    benchmark_symbol = benchmark_rows[0].ma
    if any(x.ma != benchmark_symbol for x in benchmark_rows):
        raise ValueError("Benchmark chi duoc co mot ma.")
    benchmark_rows.sort(key=lambda x: x.ngay)
    sample_dates = phien_cuoi_thang(x.ngay for x in benchmark_rows)
    by_symbol: dict[str, list[ThanhOHLCV]] = defaultdict(list)
    for row in stock_rows:
        by_symbol[row.ma].append(row)
    for rows in by_symbol.values():
        rows.sort(key=lambda x: x.ngay)
    benchmark_by_date = {x.ngay: x for x in benchmark_rows}
    result: list[DongFeature] = []
    for T in sample_dates:
        benchmark_history = [x for x in benchmark_rows if x.ngay <= T]
        for symbol in sorted(by_symbol):
            history = [x for x in by_symbol[symbol] if x.ngay <= T]
            if not history or history[-1].ngay != T or T not in benchmark_by_date:
                result.append(DongFeature(T, symbol, {}, False, ("thieu_bar_t",)))
                continue
            try:
                values = _feature_for_series(history, benchmark_history)
            except ValueError as exc:
                result.append(DongFeature(T, symbol, {}, False, (str(exc),)))
                continue
            missing = tuple(name for name in feature_bat_buoc if name not in values or values[name] is None)
            result.append(DongFeature(T, symbol, values, not missing, ("thieu_feature_bat_buoc",) if missing else ()))
    return result
