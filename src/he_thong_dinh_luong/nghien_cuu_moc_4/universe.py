"""Universe point-in-time va candidate union ky thuat, deu fail closed."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

from .mo_hinh import (
    BanGhiPointInTime,
    BanGhiUniverse,
    ThanhGiaCoPhieu,
    TrangThaiUniverse,
    xac_thuc_timestamp,
)


def xac_dinh_universe(
    ban_ghi: Iterable[BanGhiUniverse],
    *,
    ngay: date,
    thoi_diem_tao_tin_hieu: datetime,
    cac_ma: Iterable[str] | None = None,
) -> list[TrangThaiUniverse]:
    """Chon membership PIT moi nhat cho strict_ohlcv."""
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


def xac_dinh_technical_candidate_union(
    du_lieu_gia: Iterable[ThanhGiaCoPhieu],
    *,
    ngay: date,
    cac_ma: Iterable[str],
) -> list[TrangThaiUniverse]:
    """Danh gia candidate union tai dung T; khong carry membership hoac bar gan nhat.

    Candidate union chi la ho so thu thap. Tai tung ngay, mot ma chi duoc coi la
    thuoc universe ky thuat khi co bar dung ngay T. Warm-up, MA250, feature,
    thanh khoan va open T+1 duoc danh gia rieng trong eligibility.
    """
    symbols = tuple(sorted(set(cac_ma)))
    if not symbols:
        raise ValueError("technical_candidate_union_v1 khong duoc rong.")
    bar_keys = {(row.ma, row.ngay) for row in du_lieu_gia}
    result: list[TrangThaiUniverse] = []
    for symbol in symbols:
        has_bar_t = (symbol, ngay) in bar_keys
        result.append(TrangThaiUniverse(
            ngay=ngay,
            ma=symbol,
            thuoc_universe=has_bar_t,
            ly_do=None if has_bar_t else "thieu_bar_t",
            ban_ghi=None,
        ))
    return result


def cac_ma_hop_le(*args: object, **kwargs: object) -> tuple[str, ...]:
    return tuple(row.ma for row in xac_dinh_universe(*args, **kwargs) if row.thuoc_universe)


def chon_ban_ghi_pit(
    ban_ghi: Iterable[BanGhiPointInTime],
    *,
    ngay: date,
    thoi_diem_tao_tin_hieu: datetime,
    loai_du_lieu: str,
) -> list[BanGhiPointInTime]:
    """Chon snapshot PIT moi nhat theo tung khoa, fail closed va timezone-aware."""
    signal_time = xac_thuc_timestamp(thoi_diem_tao_tin_hieu, "thoi_diem_tao_tin_hieu")
    if loai_du_lieu not in {"benchmark_metadata", "corporate_action", "su_kien_point_in_time"}:
        raise ValueError("loai_du_lieu PIT khong hop le.")
    records = [r for r in ban_ghi if r.loai_du_lieu == loai_du_lieu]
    keys = [r.khoa() for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Trung ban ghi {loai_du_lieu} point-in-time.")
    by_key: dict[str, list[BanGhiPointInTime]] = defaultdict(list)
    for record in records:
        if record.ngay_hieu_luc <= ngay and record.thoi_diem_cong_bo <= signal_time:
            by_key[record.khoa_ban_ghi].append(record)
    selected: list[BanGhiPointInTime] = []
    for key in sorted(by_key):
        candidates = by_key[key]
        latest_effective = max(x.ngay_hieu_luc for x in candidates)
        candidates = [x for x in candidates if x.ngay_hieu_luc == latest_effective]
        latest_publication = max(x.thoi_diem_cong_bo for x in candidates)
        candidates = [x for x in candidates if x.thoi_diem_cong_bo == latest_publication]
        if len(candidates) != 1:
            raise ValueError(f"{loai_du_lieu} {key} khong xac dinh sau tie-break.")
        selected.append(candidates[0])
    return selected
