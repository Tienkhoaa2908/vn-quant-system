"""Tong hop coverage theo ngay, ma va ly do."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class DongLoai:
    ngay: date
    ma: str
    ly_do: str


def bao_cao_do_phu(cac_dong: Iterable[DongLoai]) -> dict[str, object]:
    rows = sorted(cac_dong, key=lambda r: (r.ngay, r.ma, r.ly_do))
    duplicate_keys = [(r.ngay, r.ma, r.ly_do) for r in rows]
    if len(duplicate_keys) != len(set(duplicate_keys)):
        raise ValueError("Trung dong coverage.")
    by_day = Counter(r.ngay.isoformat() for r in rows)
    by_symbol = Counter(r.ma for r in rows)
    by_reason = Counter(r.ly_do for r in rows)
    return {
        "tong_dong_loai": len(rows),
        "theo_ngay": dict(sorted(by_day.items())),
        "theo_ma": dict(sorted(by_symbol.items())),
        "theo_ly_do": dict(sorted(by_reason.items())),
        "chi_tiet": [
            {"ngay": r.ngay.isoformat(), "ma": r.ma, "ly_do": r.ly_do}
            for r in rows
        ],
    }
