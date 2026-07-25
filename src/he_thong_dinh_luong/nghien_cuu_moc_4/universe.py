"""Universe point-in-time, fail closed va khong survivorship bias."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

from .mo_hinh import BanGhiUniverse, TrangThaiUniverse, xac_thuc_timestamp


def xac_dinh_universe(
    ban_ghi: Iterable[BanGhiUniverse],
    *,
    ngay: date,
    thoi_diem_tao_tin_hieu: datetime,
    cac_ma: Iterable[str] | None = None,
) -> list[TrangThaiUniverse]:
    signal_time = xac_thuc_timestamp(thoi_diem_tao_tin_hieu, "thoi_diem_tao_tin_hieu")
    records = list(ban_ghi)
    keys = [r.khoa() for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Trung ban ghi universe theo ma/ngay_hieu_luc/thoi_diem_cong_bo.")
    by_symbol: dict[str, list[BanGhiUniverse]] = defaultdict(list)
    for record in records:
        by_symbol[record.ma].append(record)
    symbols = sorted(set(cac_ma) if cac_ma is not None else by_symbol)
    result: list[TrangThaiUniverse] = []
    for symbol in symbols:
        candidates = [
            r for r in by_symbol.get(symbol, ())
            if r.ngay_hieu_luc <= ngay and r.thoi_diem_cong_bo <= signal_time
        ]
        if not candidates:
            result.append(TrangThaiUniverse(ngay, symbol, False, "thieu_snapshot", None))
            continue
        latest_effective = max(r.ngay_hieu_luc for r in candidates)
        candidates = [r for r in candidates if r.ngay_hieu_luc == latest_effective]
        latest_publication = max(r.thoi_diem_cong_bo for r in candidates)
        candidates = [r for r in candidates if r.thoi_diem_cong_bo == latest_publication]
        if len(candidates) != 1:
            raise ValueError(f"Universe {symbol} khong xac dinh sau tie-break.")
        chosen = candidates[0]
        result.append(TrangThaiUniverse(
            ngay=ngay,
            ma=symbol,
            thuoc_universe=chosen.thuoc_universe,
            ly_do=None if chosen.thuoc_universe else "khong_thuoc_universe",
            ban_ghi=chosen,
        ))
    return result


def cac_ma_hop_le(*args: object, **kwargs: object) -> tuple[str, ...]:
    return tuple(row.ma for row in xac_dinh_universe(*args, **kwargs) if row.thuoc_universe)
