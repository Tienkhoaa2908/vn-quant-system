"""Hop dong eligibility M4: AND fail closed, PIT va open dung T+1."""
from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

from .mo_hinh import DongFeature, ThanhOHLCV, TrangThaiUniverse
from .phong_ve import xac_thuc_so_huu_han

LY_DO_KHONG_THANH_KHOAN = "khong_dat_thanh_khoan"
LY_DO_THIEU_OPEN_T1 = "thieu_open_t1"


def phien_t1_chinh_thuc(lich_benchmark: Sequence[date], ngay_t: date) -> date | None:
    calendar = tuple(lich_benchmark)
    try:
        index = calendar.index(ngay_t)
    except ValueError as exc:
        raise ValueError(f"Ngay tin hieu {ngay_t} khong nam trong lich benchmark.") from exc
    return calendar[index + 1] if index + 1 < len(calendar) else None


def dat_thanh_khoan_pit(
    feature: DongFeature | None,
    *,
    cua_so: int,
    nguong_gtgd_tb_toi_thieu: float,
) -> tuple[bool, float | None]:
    """Dung mean(close*volume) tren dung cua so benchmark ket thuc tai T, don vi VND/phien."""
    if cua_so != 20:
        raise ValueError("MVP chi co feature gtgd_tb_20 cho hop dong thanh khoan.")
    if feature is None:
        return False, None
    raw = feature.gia_tri.get("gtgd_tb_20")
    if raw is None or isinstance(raw, bool):
        return False, None
    value = xac_thuc_so_huu_han(raw, "gtgd_tb_20")
    return value >= nguong_gtgd_tb_toi_thieu, value


def danh_gia_eligibility(
    *,
    state: TrangThaiUniverse,
    feature: DongFeature | None,
    benchmark_metadata_ok: bool,
    open_t1: ThanhOHLCV | None,
    cua_so_thanh_khoan: int,
    nguong_gtgd_tb_toi_thieu: float,
    loi_gia: bool = False,
    loi_volume: bool = False,
) -> tuple[bool, tuple[str, ...], float | None]:
    reasons: set[str] = set()
    if not state.thuoc_universe:
        reasons.add(state.ly_do or "khong_thuoc_universe")
    if feature is None:
        reasons.add("thieu_feature")
    elif not feature.hop_le:
        reasons.update(feature.ly_do)
    liquid, liquidity_value = dat_thanh_khoan_pit(
        feature,
        cua_so=cua_so_thanh_khoan,
        nguong_gtgd_tb_toi_thieu=nguong_gtgd_tb_toi_thieu,
    )
    if not liquid:
        reasons.add(LY_DO_KHONG_THANH_KHOAN)
    if not benchmark_metadata_ok:
        reasons.add("thieu_benchmark_metadata_pit")
    if open_t1 is None:
        reasons.add(LY_DO_THIEU_OPEN_T1)
    if loi_gia:
        reasons.add("loi_gia")
    if loi_volume:
        reasons.add("loi_volume")
    return not reasons, tuple(sorted(reasons)), liquidity_value
