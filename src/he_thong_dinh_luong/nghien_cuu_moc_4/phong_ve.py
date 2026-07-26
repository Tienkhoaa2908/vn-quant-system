"""Phong ve du lieu huu han va chuyen doi on dinh cho Moc 4."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from math import isfinite
from typing import Mapping, Sequence


def xac_thuc_so_huu_han(value: object, ten: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError(f"{ten} phai la so thuc; khong ep kieu ngam.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{ten} phai huu han; NaN/Inf bi tu choi.")
    return result


def xac_thuc_cau_truc_huu_han(value: object, ten: str = "root") -> None:
    if value is None or isinstance(value, (str, bool, int, date, datetime)):
        return
    if isinstance(value, (float, Decimal)):
        xac_thuc_so_huu_han(value, ten)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            xac_thuc_cau_truc_huu_han(item, f"{ten}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            xac_thuc_cau_truc_huu_han(item, f"{ten}[{index}]")
        return
