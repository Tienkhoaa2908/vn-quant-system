"""Baseline momentum don gian, khong hoc tham so tu test."""
from __future__ import annotations

from .mo_hinh import DongFeature


def diem_momentum(feature: DongFeature) -> float | None:
    value = feature.gia_tri.get("dong_luong_12_1")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
