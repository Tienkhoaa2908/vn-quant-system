"""Nen VN100 point-in-time v2: interval, query ba trang thai va coverage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Mapping

from .hop_dong import (
    ChungNhanCoverage,
    KhoangAlias,
    KhoangThanhVien,
    KyReview,
    LoiHopDong,
    TaiLieuNguon,
    TrangThaiThanhVien,
    bat_buoc_timestamp_co_mui_gio,
)


@dataclass(frozen=True, slots=True)
class CongBoPitCandidate:
    cycles: tuple[KyReview, ...]
    intervals: tuple[KhoangThanhVien, ...]
    gaps: tuple[str, ...]
    conflicts: tuple[str, ...]
    source_document_ids: tuple[str, ...]
    is_fixture: bool


def kiem_tra_alias(aliases: Iterable[KhoangAlias]) -> None:
    danh_sach = sorted(aliases, key=lambda x: (x.symbol, x.valid_from, x.valid_to, x.instrument_id))
    for alias in danh_sach:
        alias.kiem_tra()
    for truoc, sau in zip(danh_sach, danh_sach[1:]):
        if truoc.symbol == sau.symbol and truoc.instrument_id != sau.instrument_id:
            if sau.valid_from < truoc.valid_to:
                raise LoiHopDong("IDENTITY_AMBIGUITY: symbol overlap giua instrument")


def _cycle_canonical(cycle: KyReview, sources: Mapping[str, TaiLieuNguon]) -> bool:
    if cycle.is_fixture:
        return False
    for source_id in cycle.source_document_ids:
        source = sources.get(source_id)
        if source is None:
            return False
        source.kiem_tra()
        if not source.canonical_eligible:
            return False
    return True


def tao_cong_bo_pit_candidate(
    cycles: Iterable[KyReview],
    sources: Mapping[str, TaiLieuNguon],
) -> CongBoPitCandidate:
    danh_sach = sorted(cycles, key=lambda x: (x.effective_from, x.effective_to, x.cycle_id))
    if not danh_sach:
        raise LoiHopDong("khong co review cycle")
    for cycle in danh_sach:
        cycle.kiem_tra()

    gaps: list[str] = []
    conflicts: list[str] = []
    for truoc, sau in zip(danh_sach, danh_sach[1:]):
        if sau.effective_from < truoc.effective_to:
            conflicts.append(f"OVERLAP:{truoc.cycle_id}:{sau.cycle_id}")
        elif sau.effective_from > truoc.effective_to:
            gaps.append(f"GAP:{truoc.effective_to.isoformat()}:{sau.effective_from.isoformat()}")

    intervals: list[KhoangThanhVien] = []
    source_ids: set[str] = set()
    for cycle in danh_sach:
        canonical = _cycle_canonical(cycle, sources)
        source_ids.update(cycle.source_document_ids)
        for instrument_id in cycle.members:
            interval = KhoangThanhVien(
                instrument_id=instrument_id,
                cycle_id=cycle.cycle_id,
                effective_from=cycle.effective_from,
                effective_to=cycle.effective_to,
                publication_at=cycle.publication_at,
                source_document_ids=cycle.source_document_ids,
                canonical_candidate=canonical,
                is_fixture=cycle.is_fixture,
            )
            interval.kiem_tra()
            intervals.append(interval)

    intervals.sort(key=lambda x: (x.effective_from, x.effective_to, x.instrument_id, x.cycle_id))
    return CongBoPitCandidate(
        cycles=tuple(danh_sach),
        intervals=tuple(intervals),
        gaps=tuple(gaps),
        conflicts=tuple(conflicts),
        source_document_ids=tuple(sorted(source_ids)),
        is_fixture=any(c.is_fixture for c in danh_sach),
    )


def truy_van_thanh_vien(
    publication: CongBoPitCandidate,
    instrument_id: str,
    ngay_danh_gia: date,
    thoi_diem_tao_tin_hieu: datetime,
    *,
    require_canonical: bool = True,
) -> TrangThaiThanhVien:
    bat_buoc_timestamp_co_mui_gio(thoi_diem_tao_tin_hieu, "thoi_diem_tao_tin_hieu")
    covering = [
        c
        for c in publication.cycles
        if c.effective_from <= ngay_danh_gia < c.effective_to
    ]
    if len(covering) != 1:
        return TrangThaiThanhVien.UNKNOWN
    cycle = covering[0]
    if cycle.publication_at > thoi_diem_tao_tin_hieu:
        return TrangThaiThanhVien.UNKNOWN
    if not cycle.complete_snapshot:
        return TrangThaiThanhVien.UNKNOWN
    if require_canonical:
        interval_canonical = {
            i.instrument_id
            for i in publication.intervals
            if i.cycle_id == cycle.cycle_id and i.canonical_candidate
        }
        if len(interval_canonical) != cycle.expected_member_count:
            return TrangThaiThanhVien.UNKNOWN
    return (
        TrangThaiThanhVien.MEMBER
        if instrument_id in cycle.members
        else TrangThaiThanhVien.NOT_MEMBER_PROVEN
    )


def tao_chung_nhan_coverage(
    publication: CongBoPitCandidate,
    *,
    contract_version: str = "pit_membership_interval_v2",
) -> ChungNhanCoverage:
    start = min(c.effective_from for c in publication.cycles)
    end = max(c.effective_to for c in publication.cycles)
    all_canonical = all(i.canonical_candidate for i in publication.intervals)
    complete = not publication.gaps and not publication.conflicts and all(
        c.complete_snapshot for c in publication.cycles
    )
    research_eligible = complete and all_canonical and not publication.is_fixture
    certificate = ChungNhanCoverage(
        contract_version=contract_version,
        range_start=start,
        range_end=end,
        complete=complete,
        gaps=publication.gaps,
        conflicts=publication.conflicts,
        research_eligible=research_eligible,
        source_document_ids=publication.source_document_ids,
        is_fixture=publication.is_fixture,
    )
    certificate.kiem_tra()
    return certificate
