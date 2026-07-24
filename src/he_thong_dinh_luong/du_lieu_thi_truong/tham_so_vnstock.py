"""Tham số CLI dùng chung cho Vnstock 4.0.4."""

from __future__ import annotations

import argparse

SO_NEN_MAC_DINH = 400


def so_nguyen_duong(gia_tri: str) -> int:
    """Đọc một số nguyên dương từ dòng lệnh."""
    try:
        ket_qua = int(gia_tri)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("so_nen phai la so nguyen duong") from exc
    if ket_qua <= 0:
        raise argparse.ArgumentTypeError("so_nen phai la so nguyen duong")
    return ket_qua
