"""Tao nhan T+H tren lich benchmark, khong tu tim phien thay the."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from .mo_hinh import DongNhan, ThanhCoGiaDongCua, ThanhOHLCV


def tao_nhan(
    du_lieu_co_phieu: Iterable[ThanhOHLCV],
    du_lieu_benchmark: Iterable[ThanhCoGiaDongCua],
    *,
    cac_ngay_tin_hieu: Iterable[date],
    label_horizon: int = 20,
    lich_benchmark: Iterable[date] | None = None,
) -> list[DongNhan]:
    if not isinstance(label_horizon, int) or isinstance(label_horizon, bool) or label_horizon <= 0:
        raise ValueError("label_horizon phai la int duong.")
    stock = list(du_lieu_co_phieu)
    benchmark = list(du_lieu_benchmark)
    stock_keys = [(x.ma, x.ngay) for x in stock]
    benchmark_keys = [(x.ma, x.ngay) for x in benchmark]
    if len(stock_keys) != len(set(stock_keys)) or len(benchmark_keys) != len(set(benchmark_keys)):
        raise ValueError("Du lieu nhan co khoa trung.")
    raw_calendar = list(lich_benchmark) if lich_benchmark is not None else [x.ngay for x in benchmark]
    calendar = sorted(raw_calendar)
    if len(calendar) != len(set(calendar)):
        raise ValueError("Lich benchmark trung ngay.")
    index = {d: i for i, d in enumerate(calendar)}
    benchmark_map = {x.ngay: x for x in benchmark}
    stock_map = {(x.ma, x.ngay): x for x in stock}
    symbols = sorted({x.ma for x in stock})
    result: list[DongNhan] = []
    for T in sorted(set(cac_ngay_tin_hieu)):
        if T not in index:
            for symbol in symbols:
                result.append(DongNhan(T, symbol, None, None, None, None, None, None, "T_khong_thuoc_lich_benchmark"))
            continue
        target_index = index[T] + label_horizon
        if target_index >= len(calendar):
            for symbol in symbols:
                result.append(DongNhan(T, symbol, None, None, None, None, None, None, "khong_du_horizon"))
            continue
        T_H = calendar[target_index]
        b0, b1 = benchmark_map.get(T), benchmark_map.get(T_H)
        for symbol in symbols:
            s0, s1 = stock_map.get((symbol, T)), stock_map.get((symbol, T_H))
            if s0 is None or s1 is None:
                result.append(DongNhan(T, symbol, T_H, T_H, None, None, None, None, "thieu_bar_co_phieu_t_hoac_t_h"))
                continue
            if b0 is None or b1 is None:
                result.append(DongNhan(T, symbol, T_H, T_H, None, None, None, None, "thieu_bar_benchmark_t_hoac_t_h"))
                continue
            stock_return = s1.gia_dong_cua / s0.gia_dong_cua - 1.0
            benchmark_return = b1.gia_dong_cua / b0.gia_dong_cua - 1.0
            relative = stock_return - benchmark_return
            result.append(DongNhan(T, symbol, T_H, T_H, stock_return, benchmark_return, relative, int(relative > 0.0), None))
    return result
