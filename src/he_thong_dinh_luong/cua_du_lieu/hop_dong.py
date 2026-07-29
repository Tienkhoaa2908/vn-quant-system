"""Hop dong fail-closed cho cac cua du lieu nghien cuu."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
import re
from typing import Any


class LoiHopDong(ValueError):
    """Du lieu vi pham hop dong bat bien."""


class CapNguon(StrEnum):
    TIER_1_OFFICIAL = "TIER_1_OFFICIAL"
    TIER_2_OFFICIAL_SURROGATE = "TIER_2_OFFICIAL_SURROGATE"
    TIER_3_SECONDARY = "TIER_3_SECONDARY"
    REJECTED = "REJECTED"


class TrangThaiQuyen(StrEnum):
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"
    DO_NOT_STORE = "DO_NOT_STORE"


class TrangThaiThanhVien(StrEnum):
    MEMBER = "MEMBER"
    NOT_MEMBER_PROVEN = "NOT_MEMBER_PROVEN"
    UNKNOWN = "UNKNOWN"


class CoSoGia(StrEnum):
    ADJUSTED = "ADJUSTED"
    UNADJUSTED = "UNADJUSTED"
    UNKNOWN = "UNKNOWN"


class LoaiHanhDongDoanhNghiep(StrEnum):
    SPLIT = "SPLIT"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    MERGER = "MERGER"
    DELIST = "DELIST"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    TRANSFER = "TRANSFER"
    OTHER_OFFICIAL_ACTION = "OTHER_OFFICIAL_ACTION"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def bat_buoc_timestamp_co_mui_gio(gia_tri: datetime, ten: str) -> None:
    if gia_tri.tzinfo is None or gia_tri.utcoffset() is None:
        raise LoiHopDong(f"{ten} phai co mui gio")


def bat_buoc_sha256(gia_tri: str, ten: str = "sha256") -> None:
    if not _SHA256_RE.fullmatch(gia_tri):
        raise LoiHopDong(f"{ten} khong phai SHA-256 chu thuong hop le")


def bat_buoc_so_duong(gia_tri: Decimal, ten: str) -> None:
    if not gia_tri.is_finite() or gia_tri <= 0:
        raise LoiHopDong(f"{ten} phai huu han va duong")


@dataclass(frozen=True, slots=True)
class TaiLieuNguon:
    source_document_id: str
    publisher: str
    source_tier: CapNguon
    document_type: str
    observed_url: str
    acquired_at: datetime
    rights_status: TrangThaiQuyen
    sha256: str | None = None
    byte_size: int | None = None
    content_reviewed: bool = False
    chain_verified: bool = False
    canonical_eligible: bool = False
    is_fixture: bool = False

    def kiem_tra(self) -> None:
        if not self.source_document_id.strip():
            raise LoiHopDong("source_document_id rong")
        if not self.publisher.strip() or not self.document_type.strip():
            raise LoiHopDong("publisher/document_type rong")
        if not self.observed_url.strip():
            raise LoiHopDong("observed_url rong")
        bat_buoc_timestamp_co_mui_gio(self.acquired_at, "acquired_at")
        if (self.sha256 is None) != (self.byte_size is None):
            raise LoiHopDong("sha256 va byte_size phai cung co hoac cung rong")
        if self.sha256 is not None:
            bat_buoc_sha256(self.sha256)
            if self.byte_size is None or self.byte_size < 0:
                raise LoiHopDong("byte_size khong hop le")
        if self.canonical_eligible:
            if self.is_fixture:
                raise LoiHopDong("fixture khong duoc canonical_eligible")
            if self.sha256 is None or not self.chain_verified or not self.content_reviewed:
                raise LoiHopDong("canonical_eligible thieu byte/chain/content review")
            if self.rights_status in {TrangThaiQuyen.UNKNOWN, TrangThaiQuyen.DO_NOT_STORE}:
                raise LoiHopDong("canonical_eligible co rights status khong hop le")


@dataclass(frozen=True, slots=True)
class DongTrichXuatTho:
    source_document_id: str
    row_number: int
    raw_symbol: str
    raw_index_name: str
    raw_effective_date: date
    source_locator: str

    def kiem_tra(self) -> None:
        if not self.source_document_id.strip() or self.row_number <= 0:
            raise LoiHopDong("dong trich xuat thieu khoa")
        if not self.raw_symbol.strip() or not self.raw_index_name.strip():
            raise LoiHopDong("raw symbol/index rong")
        if not self.source_locator.strip():
            raise LoiHopDong("source_locator rong")


@dataclass(frozen=True, slots=True)
class KhoangAlias:
    instrument_id: str
    symbol: str
    valid_from: date
    valid_to: date
    source_document_ids: tuple[str, ...]
    is_fixture: bool = False

    def kiem_tra(self) -> None:
        if not self.instrument_id.strip() or not self.symbol.strip():
            raise LoiHopDong("instrument_id/symbol rong")
        if self.valid_to <= self.valid_from:
            raise LoiHopDong("alias interval phai half-open va co end")
        if not self.source_document_ids:
            raise LoiHopDong("alias interval thieu provenance")


@dataclass(frozen=True, slots=True)
class KyReview:
    cycle_id: str
    index_name: str
    publication_at: datetime
    effective_from: date
    effective_to: date
    expected_member_count: int
    members: tuple[str, ...]
    source_document_ids: tuple[str, ...]
    rulebook_version: str
    complete_snapshot: bool = True
    is_fixture: bool = False

    def kiem_tra(self) -> None:
        if not self.cycle_id.strip() or not self.index_name.strip():
            raise LoiHopDong("cycle_id/index_name rong")
        bat_buoc_timestamp_co_mui_gio(self.publication_at, "publication_at")
        if self.effective_to <= self.effective_from:
            raise LoiHopDong("review cycle phai co interval half-open dong")
        if self.expected_member_count <= 0:
            raise LoiHopDong("expected_member_count phai duong")
        if not self.rulebook_version.strip() or not self.source_document_ids:
            raise LoiHopDong("review cycle thieu rulebook/provenance")
        if len(set(self.members)) != len(self.members):
            raise LoiHopDong("review cycle trung instrument_id")
        if tuple(sorted(self.members)) != self.members:
            raise LoiHopDong("members phai sap xep on dinh")
        if self.complete_snapshot and len(self.members) != self.expected_member_count:
            raise LoiHopDong("observed_member_count khong khop contract")


@dataclass(frozen=True, slots=True)
class KhoangThanhVien:
    instrument_id: str
    cycle_id: str
    effective_from: date
    effective_to: date
    publication_at: datetime
    source_document_ids: tuple[str, ...]
    canonical_candidate: bool
    is_fixture: bool

    def kiem_tra(self) -> None:
        if self.effective_to <= self.effective_from:
            raise LoiHopDong("membership interval phai co end")
        bat_buoc_timestamp_co_mui_gio(self.publication_at, "publication_at")
        if self.canonical_candidate and self.is_fixture:
            raise LoiHopDong("fixture interval khong duoc canonical candidate")


@dataclass(frozen=True, slots=True)
class ChungNhanCoverage:
    contract_version: str
    range_start: date
    range_end: date
    complete: bool
    gaps: tuple[str, ...]
    conflicts: tuple[str, ...]
    research_eligible: bool
    source_document_ids: tuple[str, ...]
    is_fixture: bool

    def kiem_tra(self) -> None:
        if self.range_end <= self.range_start:
            raise LoiHopDong("coverage range khong hop le")
        if self.contract_version != "pit_membership_interval_v2":
            raise LoiHopDong("coverage sai contract")
        if self.research_eligible:
            if self.is_fixture:
                raise LoiHopDong("fixture coverage khong duoc research eligible")
            if not self.complete or self.gaps or self.conflicts:
                raise LoiHopDong("research eligible coverage khong complete")


@dataclass(frozen=True, slots=True)
class ThanhEod:
    symbol: str
    trading_date: date
    open_price: Decimal
    close_price: Decimal
    volume: Decimal
    source_document_id: str
    price_basis: CoSoGia
    is_fixture: bool = False

    def kiem_tra(self) -> None:
        if not self.symbol.strip() or not self.source_document_id.strip():
            raise LoiHopDong("EOD thieu symbol/provenance")
        bat_buoc_so_duong(self.open_price, "open_price")
        bat_buoc_so_duong(self.close_price, "close_price")
        if not self.volume.is_finite() or self.volume < 0:
            raise LoiHopDong("volume phai huu han va khong am")


@dataclass(frozen=True, slots=True)
class HanhDongDoanhNghiep:
    action_id: str
    instrument_id: str
    action_type: LoaiHanhDongDoanhNghiep
    publication_at: datetime
    effective_date: date
    source_document_id: str
    record_date: date | None = None
    payment_date: date | None = None
    ratio: Decimal | None = None
    cash_value: Decimal | None = None
    target_instrument_id: str | None = None
    is_fixture: bool = False

    def kiem_tra(self) -> None:
        if not self.action_id.strip() or not self.instrument_id.strip():
            raise LoiHopDong("corporate action thieu khoa")
        if not self.source_document_id.strip():
            raise LoiHopDong("corporate action thieu provenance")
        bat_buoc_timestamp_co_mui_gio(self.publication_at, "publication_at")
        if self.payment_date is not None and self.payment_date < self.effective_date:
            raise LoiHopDong("payment_date truoc effective_date")
        if self.ratio is not None:
            bat_buoc_so_duong(self.ratio, "ratio")
        if self.cash_value is not None:
            bat_buoc_so_duong(self.cash_value, "cash_value")
        if self.action_type in {
            LoaiHanhDongDoanhNghiep.SPLIT,
            LoaiHanhDongDoanhNghiep.STOCK_DIVIDEND,
            LoaiHanhDongDoanhNghiep.RIGHTS_ISSUE,
        } and self.ratio is None:
            raise LoiHopDong("action type bat buoc ratio")
        if self.action_type == LoaiHanhDongDoanhNghiep.CASH_DIVIDEND:
            if self.cash_value is None or self.payment_date is None or self.record_date is None:
                raise LoiHopDong("cash dividend thieu record/payment/value")
        if self.action_type in {
            LoaiHanhDongDoanhNghiep.MERGER,
            LoaiHanhDongDoanhNghiep.SYMBOL_CHANGE,
            LoaiHanhDongDoanhNghiep.TRANSFER,
        } and not self.target_instrument_id:
            raise LoiHopDong("identity action thieu target_instrument_id")


@dataclass(frozen=True, slots=True)
class KetQuaResearchGate:
    passed: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def kiem_tra(self) -> None:
        if self.passed != (len(self.blockers) == 0):
            raise LoiHopDong("passed khong khop blockers")


def thanh_primitive(gia_tri: Any) -> Any:
    if is_dataclass(gia_tri):
        return {k: thanh_primitive(v) for k, v in asdict(gia_tri).items()}
    if isinstance(gia_tri, Enum):
        return gia_tri.value
    if isinstance(gia_tri, datetime):
        bat_buoc_timestamp_co_mui_gio(gia_tri, "datetime")
        return gia_tri.isoformat()
    if isinstance(gia_tri, date):
        return gia_tri.isoformat()
    if isinstance(gia_tri, Decimal):
        if not gia_tri.is_finite():
            raise LoiHopDong("Decimal khong huu han")
        return format(gia_tri, "f")
    if isinstance(gia_tri, dict):
        return {str(k): thanh_primitive(v) for k, v in gia_tri.items()}
    if isinstance(gia_tri, (tuple, list)):
        return [thanh_primitive(v) for v in gia_tri]
    return gia_tri
