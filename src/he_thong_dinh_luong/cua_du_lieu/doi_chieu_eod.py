"""Doi chieu HOSE EOD va co so gia, khong sua raw value."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .hop_dong import CoSoGia, LoiHopDong, ThanhEod


@dataclass(frozen=True, slots=True)
class SaiLechEod:
    symbol: str
    trading_date: str
    code: str
    candidate_value: str | None
    reference_value: str | None


def _lap_chi_muc(rows: Iterable[ThanhEod], nhan: str) -> dict[tuple[str, object], ThanhEod]:
    result: dict[tuple[str, object], ThanhEod] = {}
    for row in rows:
        row.kiem_tra()
        key = (row.symbol, row.trading_date)
        if key in result:
            raise LoiHopDong(f"DUPLICATE_EOD:{nhan}:{row.symbol}:{row.trading_date}")
        result[key] = row
    return result


def _co_the_lech_scale(a: Decimal, b: Decimal) -> bool:
    return a == b * Decimal("1000") or b == a * Decimal("1000")


def doi_chieu_eod(
    candidate_rows: Iterable[ThanhEod],
    reference_rows: Iterable[ThanhEod],
) -> tuple[SaiLechEod, ...]:
    candidate = _lap_chi_muc(candidate_rows, "candidate")
    reference = _lap_chi_muc(reference_rows, "reference")
    mismatches: list[SaiLechEod] = []
    for key in sorted(set(candidate) | set(reference)):
        symbol, trading_date = key
        left = candidate.get(key)
        right = reference.get(key)
        if left is None:
            mismatches.append(SaiLechEod(symbol, trading_date.isoformat(), "MISSING_CANDIDATE", None, "present"))
            continue
        if right is None:
            mismatches.append(SaiLechEod(symbol, trading_date.isoformat(), "MISSING_REFERENCE", "present", None))
            continue
        if left.open_price != right.open_price:
            code = "PRICE_SCALE_MISMATCH" if _co_the_lech_scale(left.open_price, right.open_price) else "OPEN_MISMATCH"
            mismatches.append(SaiLechEod(symbol, trading_date.isoformat(), code, str(left.open_price), str(right.open_price)))
        if left.close_price != right.close_price:
            code = "PRICE_SCALE_MISMATCH" if _co_the_lech_scale(left.close_price, right.close_price) else "CLOSE_MISMATCH"
            mismatches.append(SaiLechEod(symbol, trading_date.isoformat(), code, str(left.close_price), str(right.close_price)))
        if left.volume != right.volume:
            mismatches.append(SaiLechEod(symbol, trading_date.isoformat(), "VOLUME_MISMATCH", str(left.volume), str(right.volume)))
        if left.price_basis != right.price_basis:
            mismatches.append(SaiLechEod(symbol, trading_date.isoformat(), "PRICE_BASIS_MISMATCH", left.price_basis.value, right.price_basis.value))
    return tuple(mismatches)


def danh_gia_cua_eod(
    mismatches: Iterable[SaiLechEod],
    *,
    candidate_basis: CoSoGia,
    reference_basis: CoSoGia,
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if tuple(mismatches):
        blockers.append("HOSE_EOD_CROSSCHECK_INCOMPLETE")
    if candidate_basis == CoSoGia.UNKNOWN or reference_basis == CoSoGia.UNKNOWN:
        blockers.append("PRICE_BASIS_UNCONFIRMED")
    elif candidate_basis != reference_basis:
        blockers.append("PRICE_BASIS_CONFLICT")
    return len(blockers) == 0, tuple(sorted(set(blockers)))
