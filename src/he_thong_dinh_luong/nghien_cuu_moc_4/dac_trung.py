"""Tinh feature MVP tai cuoi thang tren lich benchmark chinh thuc, khong nen thoi gian."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt
from statistics import fmean
from typing import Iterable, Sequence, TypeVar

from .mo_hinh import DongFeature, ThanhCoGiaDongCua, ThanhGiaCoPhieu
from .phong_ve import xac_thuc_so_huu_han

FEATURE_ORDER_STRICT_OHLCV_V1 = (
    "khoang_cach_ma20", "khoang_cach_ma60", "khoang_cach_ma120", "khoang_cach_ma250",
    "gia_tren_ma250", "ty_le_dinh_52_tuan", "loi_nhuan_20", "loi_nhuan_60",
    "loi_nhuan_120", "loi_nhuan_250", "dong_luong_12_1", "suc_manh_tuong_doi_120",
    "bien_dong_20", "bien_dong_60", "bien_dong_giam_60",
    "bien_do_cao_thap_chuan_hoa", "gtgd_tb_20", "gtgd_tb_60",
    "gtgd_hien_tai_tren_tb60", "so_phien_volume_0_60", "vnindex_tren_ma250",
    "vnindex_momentum_60", "vnindex_bien_dong_20", "vnindex_bien_dong_60",
)
FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1 = tuple(
    name for name in FEATURE_ORDER_STRICT_OHLCV_V1
    if name != "bien_do_cao_thap_chuan_hoa"
)
FEATURE_ORDER_MAC_DINH = FEATURE_ORDER_STRICT_OHLCV_V1

_BAR_DONG_CUA = TypeVar("_BAR_DONG_CUA", bound=ThanhCoGiaDongCua)


def _lich_chinh_thuc(lich_benchmark: Iterable[date]) -> tuple[date, ...]:
    raw = list(lich_benchmark)
    if not raw:
        return ()
    if any(not isinstance(x, date) for x in raw):
        raise TypeError("Lich benchmark chi duoc chua date.")
    if len(raw) != len(set(raw)):
        raise ValueError("Lich benchmark trung ngay.")
    return tuple(sorted(raw))


def phien_cuoi_thang(lich_benchmark: Iterable[date]) -> tuple[date, ...]:
    sessions = _lich_chinh_thuc(lich_benchmark)
    latest: dict[tuple[int, int], date] = {}
    for session in sessions:
        latest[(session.year, session.month)] = session
    return tuple(latest[key] for key in sorted(latest))


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("Can it nhat hai quan sat de tinh sample std.")
    for index, value in enumerate(values):
        xac_thuc_so_huu_han(value, f"sample_std[{index}]")
    mean = fmean(values)
    return sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))


def _returns(closes: Sequence[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _validate_bars(rows: Sequence[ThanhCoGiaDongCua]) -> None:
    keys = [(r.ma, r.ngay) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("OHLCV trung ma/ngay.")


def _window(calendar: Sequence[date], index: int, length: int) -> tuple[date, ...] | None:
    start = index - length + 1
    return tuple(calendar[start:index + 1]) if start >= 0 else None


def _endpoint(calendar: Sequence[date], index: int, offset: int) -> date | None:
    target = index - offset
    return calendar[target] if target >= 0 else None


def _bars_exact(mapping: dict[date, _BAR_DONG_CUA], dates: Sequence[date]) -> list[_BAR_DONG_CUA] | None:
    rows = [mapping.get(day) for day in dates]
    return None if any(row is None for row in rows) else [row for row in rows if row is not None]


def _feature_calendar_aligned(
    *,
    symbol: str,
    T: date,
    calendar: Sequence[date],
    stock_map: dict[date, ThanhGiaCoPhieu],
    benchmark_map: dict[date, ThanhCoGiaDongCua],
    feature_order: Sequence[str],
) -> tuple[dict[str, float | bool | int | None], tuple[str, ...]]:
    index = {day: i for i, day in enumerate(calendar)}[T]
    values: dict[str, float | bool | int | None] = {name: None for name in feature_order}
    reasons: set[str] = set()
    if stock_map.get(T) is None:
        reasons.add("thieu_bar_t")
    if benchmark_map.get(T) is None:
        reasons.add("thieu_bar_benchmark_t")

    def missing(feature: str, side: str) -> None:
        if feature != "bien_do_cao_thap_chuan_hoa" or feature in values:
            reasons.add(f"thieu_bar_{side}_{feature}")

    for n in (20, 60, 120, 250):
        ma_dates = _window(calendar, index, n)
        ma_rows = _bars_exact(stock_map, ma_dates) if ma_dates is not None else None
        if ma_rows is None:
            missing(f"ma{n}", "co_phieu")
        else:
            closes = [float(x.gia_dong_cua) for x in ma_rows]
            values[f"khoang_cach_ma{n}"] = closes[-1] / fmean(closes) - 1.0
            if n == 250:
                values["gia_tren_ma250"] = closes[-1] >= fmean(closes)
                values["ty_le_dinh_52_tuan"] = closes[-1] / max(closes)

        start = _endpoint(calendar, index, n)
        start_row = stock_map.get(start) if start is not None else None
        end_row = stock_map.get(T)
        if start_row is None or end_row is None:
            missing(f"loi_nhuan_{n}", "co_phieu")
        else:
            values[f"loi_nhuan_{n}"] = end_row.gia_dong_cua / start_row.gia_dong_cua - 1.0

    t20, t250 = _endpoint(calendar, index, 20), _endpoint(calendar, index, 250)
    row20, row250 = stock_map.get(t20) if t20 else None, stock_map.get(t250) if t250 else None
    if row20 is None or row250 is None:
        missing("dong_luong_12_1", "co_phieu")
    else:
        values["dong_luong_12_1"] = row20.gia_dong_cua / row250.gia_dong_cua - 1.0

    t120 = _endpoint(calendar, index, 120)
    s0, s1 = stock_map.get(t120) if t120 else None, stock_map.get(T)
    b0, b1 = benchmark_map.get(t120) if t120 else None, benchmark_map.get(T)
    if s0 is None or s1 is None:
        missing("suc_manh_tuong_doi_120", "co_phieu")
    if b0 is None or b1 is None:
        missing("suc_manh_tuong_doi_120", "benchmark")
    if s0 is not None and s1 is not None and b0 is not None and b1 is not None:
        values["suc_manh_tuong_doi_120"] = (
            s1.gia_dong_cua / s0.gia_dong_cua - 1.0
            - (b1.gia_dong_cua / b0.gia_dong_cua - 1.0)
        )

    for n in (20, 60):
        vol_dates = _window(calendar, index, n + 1)
        stock_rows = _bars_exact(stock_map, vol_dates) if vol_dates is not None else None
        benchmark_rows = _bars_exact(benchmark_map, vol_dates) if vol_dates is not None else None
        if stock_rows is None:
            missing(f"bien_dong_{n}", "co_phieu")
        else:
            returns = _returns([float(x.gia_dong_cua) for x in stock_rows])
            values[f"bien_dong_{n}"] = _sample_std(returns)
            if n == 60:
                values["bien_dong_giam_60"] = _sample_std([min(x, 0.0) for x in returns])
        if benchmark_rows is None:
            missing(f"vnindex_bien_dong_{n}", "benchmark")
        else:
            values[f"vnindex_bien_dong_{n}"] = _sample_std(
                _returns([float(x.gia_dong_cua) for x in benchmark_rows])
            )

    if "bien_do_cao_thap_chuan_hoa" in values:
        current = stock_map.get(T)
        if current is None:
            missing("bien_do_cao_thap_chuan_hoa", "co_phieu")
        elif not hasattr(current, "gia_cao_nhat") or not hasattr(current, "gia_thap_nhat"):
            raise ValueError("strict_ohlcv bat buoc high/low; khong duoc suy dung.")
        else:
            values["bien_do_cao_thap_chuan_hoa"] = (
                float(getattr(current, "gia_cao_nhat"))
                - float(getattr(current, "gia_thap_nhat"))
            ) / current.gia_dong_cua

    for n in (20, 60):
        liq_dates = _window(calendar, index, n)
        liq_rows = _bars_exact(stock_map, liq_dates) if liq_dates is not None else None
        if liq_rows is None:
            missing(f"gtgd_tb_{n}", "co_phieu")
        else:
            traded = [float(x.gia_dong_cua) * x.khoi_luong for x in liq_rows]
            values[f"gtgd_tb_{n}"] = fmean(traded)
            if n == 60:
                average = float(values["gtgd_tb_60"])
                values["gtgd_hien_tai_tren_tb60"] = traded[-1] / average if average > 0.0 else 0.0
                values["so_phien_volume_0_60"] = sum(1 for x in liq_rows if x.khoi_luong == 0)

    benchmark_ma_dates = _window(calendar, index, 250)
    benchmark_ma_rows = _bars_exact(benchmark_map, benchmark_ma_dates) if benchmark_ma_dates is not None else None
    if benchmark_ma_rows is None:
        missing("vnindex_tren_ma250", "benchmark")
    else:
        bcloses = [float(x.gia_dong_cua) for x in benchmark_ma_rows]
        values["vnindex_tren_ma250"] = bcloses[-1] >= fmean(bcloses)
    t60 = _endpoint(calendar, index, 60)
    b60, bT = benchmark_map.get(t60) if t60 else None, benchmark_map.get(T)
    if b60 is None or bT is None:
        missing("vnindex_momentum_60", "benchmark")
    else:
        values["vnindex_momentum_60"] = bT.gia_dong_cua / b60.gia_dong_cua - 1.0

    for name, value in values.items():
        if value is not None and not isinstance(value, (bool, int)):
            xac_thuc_so_huu_han(value, f"feature.{symbol}.{T}.{name}")
    return values, tuple(sorted(reasons))


def tao_feature_cuoi_thang(
    du_lieu_co_phieu: Iterable[ThanhGiaCoPhieu],
    du_lieu_benchmark: Iterable[ThanhCoGiaDongCua],
    *,
    lich_benchmark: Iterable[date] | None = None,
    feature_order: Sequence[str] = FEATURE_ORDER_MAC_DINH,
    feature_bat_buoc: Sequence[str] = FEATURE_ORDER_MAC_DINH,
) -> list[DongFeature]:
    canonical_order = tuple(feature_order)
    if canonical_order not in {
        FEATURE_ORDER_STRICT_OHLCV_V1,
        FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1,
    }:
        raise ValueError("feature_order khong thuoc hai hop dong canonical.")
    if not set(feature_bat_buoc).issubset(canonical_order):
        raise ValueError("feature_bat_buoc phai la tap con cua feature_order.")
    stock_rows = list(du_lieu_co_phieu)
    benchmark_rows = list(du_lieu_benchmark)
    _validate_bars(stock_rows)
    _validate_bars(benchmark_rows)
    if not benchmark_rows and lich_benchmark is None:
        return []
    benchmark_symbols = {x.ma for x in benchmark_rows}
    if len(benchmark_symbols) > 1:
        raise ValueError("Benchmark chi duoc co mot ma.")
    official_calendar = _lich_chinh_thuc(
        lich_benchmark if lich_benchmark is not None else (x.ngay for x in benchmark_rows)
    )
    sample_dates = phien_cuoi_thang(official_calendar)
    by_symbol: dict[str, dict[date, ThanhGiaCoPhieu]] = defaultdict(dict)
    for row in stock_rows:
        by_symbol[row.ma][row.ngay] = row
    benchmark_map = {x.ngay: x for x in benchmark_rows}
    result: list[DongFeature] = []
    for T in sample_dates:
        for symbol in sorted(by_symbol):
            values, reasons = _feature_calendar_aligned(
                symbol=symbol,
                T=T,
                calendar=official_calendar,
                stock_map=by_symbol[symbol],
                benchmark_map=benchmark_map,
                feature_order=canonical_order,
            )
            missing_required = tuple(
                name for name in feature_bat_buoc
                if name not in values or values[name] is None
            )
            final_reasons = tuple(sorted(set(reasons) | ({"thieu_feature_bat_buoc"} if missing_required else set())))
            result.append(DongFeature(T, symbol, values, not missing_required, final_reasons))
    return result
