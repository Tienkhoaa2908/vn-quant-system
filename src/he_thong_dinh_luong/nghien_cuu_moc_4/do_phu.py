"""Tong hop coverage day du theo ngay, ma, ly do, nguon va fold."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class DongLoai:
    ngay: date
    ma: str
    ly_do: str


def _ty_le(tu_so: int, mau_so: int) -> float | None:
    return tu_so / mau_so if mau_so > 0 else None


def bao_cao_do_phu(
    cac_dong: Iterable[DongLoai],
    *,
    loi_fold: Iterable[dict[str, str]] = (),
    cac_ngay_yeu_cau: Iterable[date] = (),
    cac_ngay_thuc_te: Iterable[date] = (),
    cac_ma_universe: Iterable[str] = (),
    phien_co_du_lieu_theo_ma: Mapping[str, Iterable[date]] | None = None,
    coverage_theo_ngay: Mapping[date, tuple[int, int]] | None = None,
    ma_that_bai_hoan_toan: Iterable[str] = (),
    ma_thieu_warm_up: Iterable[str] = (),
    ma_co_gap: Iterable[str] = (),
    ma_loi_gia: Iterable[str] = (),
    ma_loi_volume: Iterable[str] = (),
    ma_thieu_corporate_actions: Iterable[str] = (),
    ngay_it_hon_top_k: Iterable[date] = (),
    nguon_ohlcv: str | None = None,
    phien_ban_ohlcv: str | None = None,
    nguon_universe: str | None = None,
    phien_ban_universe: str | None = None,
    nguon_benchmark: str | None = None,
    phien_ban_benchmark: str | None = None,
    co_so_gia: str | None = None,
) -> dict[str, object]:
    rows = sorted(cac_dong, key=lambda r: (r.ngay, r.ma, r.ly_do))
    duplicate_keys = [(r.ngay, r.ma, r.ly_do) for r in rows]
    if len(duplicate_keys) != len(set(duplicate_keys)):
        raise ValueError("Trung dong coverage.")
    fold_errors = sorted((dict(x) for x in loi_fold), key=lambda x: (x.get("fold", ""), x.get("ly_do", "")))
    for item in fold_errors:
        if not item.get("fold") or not item.get("ly_do"):
            raise ValueError("Loi fold phai co fold va ly_do.")

    requested = tuple(sorted(set(cac_ngay_yeu_cau)))
    actual = tuple(sorted(set(cac_ngay_thuc_te)))
    universe = tuple(sorted(set(cac_ma_universe)))
    sessions_by_symbol = {
        symbol: set(days) for symbol, days in (phien_co_du_lieu_theo_ma or {}).items()
    }
    symbols_with_data = tuple(sorted(symbol for symbol in universe if sessions_by_symbol.get(symbol)))

    day_coverage_rows: list[dict[str, object]] = []
    if coverage_theo_ngay is not None:
        for day in sorted(coverage_theo_ngay):
            numerator, denominator = coverage_theo_ngay[day]
            if numerator < 0 or denominator < 0 or numerator > denominator:
                raise ValueError("Coverage theo ngay co tu so/mau so khong hop le.")
            day_coverage_rows.append({
                "ngay": day.isoformat(),
                "tu_so": numerator,
                "mau_so": denominator,
                "ty_le": _ty_le(numerator, denominator),
            })
    elif requested and universe:
        for day in requested:
            numerator = sum(day in sessions_by_symbol.get(symbol, set()) for symbol in universe)
            day_coverage_rows.append({
                "ngay": day.isoformat(), "tu_so": numerator, "mau_so": len(universe),
                "ty_le": _ty_le(numerator, len(universe)),
            })

    symbol_coverage_rows: list[dict[str, object]] = []
    for symbol in universe:
        requested_count = len(requested)
        available = len(set(requested) & sessions_by_symbol.get(symbol, set()))
        symbol_coverage_rows.append({
            "ma": symbol,
            "so_phien_co": available,
            "so_phien_yeu_cau": requested_count,
            "ty_le": _ty_le(available, requested_count),
        })

    by_day = Counter(r.ngay.isoformat() for r in rows)
    by_symbol = Counter(r.ma for r in rows)
    by_reason = Counter(r.ly_do for r in rows)
    return {
        "ngay_yeu_cau_tu": requested[0].isoformat() if requested else None,
        "ngay_yeu_cau_den": requested[-1].isoformat() if requested else None,
        "ngay_thuc_te_tu": actual[0].isoformat() if actual else None,
        "ngay_thuc_te_den": actual[-1].isoformat() if actual else None,
        "tong_ma_universe": len(universe),
        "tong_ma_co_du_lieu": len(symbols_with_data),
        "ma_that_bai_hoan_toan": sorted(set(ma_that_bai_hoan_toan)),
        "ma_thieu_warm_up": sorted(set(ma_thieu_warm_up)),
        "ma_co_gap": sorted(set(ma_co_gap)),
        "ma_loi_gia": sorted(set(ma_loi_gia)),
        "ma_loi_volume": sorted(set(ma_loi_volume)),
        "ma_thieu_corporate_actions": sorted(set(ma_thieu_corporate_actions)),
        "coverage_theo_ngay": day_coverage_rows,
        "coverage_theo_ma": symbol_coverage_rows,
        "so_ngay_it_hon_top_k": len(set(ngay_it_hon_top_k)),
        "ngay_it_hon_top_k": [x.isoformat() for x in sorted(set(ngay_it_hon_top_k))],
        "ly_do_loai": dict(sorted(by_reason.items())),
        "loi_fold": fold_errors,
        "nguon": {
            "ohlcv": {"nguon": nguon_ohlcv, "phien_ban": phien_ban_ohlcv},
            "universe": {"nguon": nguon_universe, "phien_ban": phien_ban_universe},
            "benchmark": {"nguon": nguon_benchmark, "phien_ban": phien_ban_benchmark},
        },
        "co_so_gia": co_so_gia,
        # Cac khoa cu duoc giu de khong pha hop dong kiem thu/nguoi dung hien tai.
        "tong_dong_loai": len(rows),
        "theo_ngay": dict(sorted(by_day.items())),
        "theo_ma": dict(sorted(by_symbol.items())),
        "theo_ly_do": dict(sorted(by_reason.items())),
        "chi_tiet": [
            {"ngay": r.ngay.isoformat(), "ma": r.ma, "ly_do": r.ly_do}
            for r in rows
        ],
    }
