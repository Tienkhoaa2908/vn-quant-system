"""Inventory va validator cho hanh dong doanh nghiep."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .hop_dong import CoSoGia, HanhDongDoanhNghiep, LoiHopDong


@dataclass(frozen=True, slots=True)
class ChungNhanHanhDongDoanhNghiep:
    range_start: date
    range_end: date
    inventory_complete: bool
    conflicts: tuple[str, ...]
    source_document_ids: tuple[str, ...]
    research_eligible: bool
    is_fixture: bool

    def kiem_tra(self) -> None:
        if self.range_end <= self.range_start:
            raise LoiHopDong("corporate action coverage range khong hop le")
        if self.research_eligible:
            if self.is_fixture or not self.inventory_complete or self.conflicts:
                raise LoiHopDong("corporate action certificate khong du research")


def kiem_tra_hanh_dong(records: Iterable[HanhDongDoanhNghiep]) -> tuple[str, ...]:
    rows = sorted(records, key=lambda x: (x.instrument_id, x.effective_date, x.action_type.value, x.action_id))
    seen_id: set[str] = set()
    conflicts: list[str] = []
    by_natural_key: dict[tuple[object, ...], HanhDongDoanhNghiep] = {}
    for row in rows:
        row.kiem_tra()
        if row.action_id in seen_id:
            raise LoiHopDong(f"DUPLICATE_ACTION_ID:{row.action_id}")
        seen_id.add(row.action_id)
        key = (row.instrument_id, row.effective_date, row.action_type)
        previous = by_natural_key.get(key)
        if previous is not None and previous != row:
            conflicts.append(f"ACTION_CONFLICT:{row.instrument_id}:{row.effective_date}:{row.action_type.value}")
        by_natural_key[key] = row
    return tuple(sorted(set(conflicts)))


def tao_chung_nhan_hanh_dong(
    records: Iterable[HanhDongDoanhNghiep],
    *,
    range_start: date,
    range_end: date,
    inventory_complete: bool,
    price_basis: CoSoGia,
    source_chain_verified: bool,
) -> ChungNhanHanhDongDoanhNghiep:
    rows = tuple(records)
    conflicts = list(kiem_tra_hanh_dong(rows))
    if price_basis == CoSoGia.ADJUSTED and rows:
        conflicts.append("ADJUSTED_PRICE_WITH_CORPORATE_ACTIONS")
    is_fixture = any(row.is_fixture for row in rows)
    research_eligible = (
        inventory_complete
        and source_chain_verified
        and price_basis != CoSoGia.UNKNOWN
        and not conflicts
        and not is_fixture
    )
    certificate = ChungNhanHanhDongDoanhNghiep(
        range_start=range_start,
        range_end=range_end,
        inventory_complete=inventory_complete,
        conflicts=tuple(sorted(set(conflicts))),
        source_document_ids=tuple(sorted({row.source_document_id for row in rows})),
        research_eligible=research_eligible,
        is_fixture=is_fixture,
    )
    certificate.kiem_tra()
    return certificate
