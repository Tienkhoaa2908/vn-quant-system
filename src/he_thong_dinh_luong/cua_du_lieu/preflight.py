"""Research preflight tong hop cho bon data gate."""

from __future__ import annotations

from dataclasses import dataclass

from .hanh_dong_doanh_nghiep import ChungNhanHanhDongDoanhNghiep
from .hop_dong import ChungNhanCoverage, KetQuaResearchGate


@dataclass(frozen=True, slots=True)
class DauVaoResearchPreflight:
    universe_contract: str
    universe_coverage: ChungNhanCoverage | None
    eod_crosscheck_ready: bool
    corporate_action_certificate: ChungNhanHanhDongDoanhNghiep | None
    price_basis_confirmed: bool


def danh_gia_research_preflight(inputs: DauVaoResearchPreflight) -> KetQuaResearchGate:
    blockers: list[str] = []
    warnings: list[str] = []
    if inputs.universe_contract != "pit_membership_interval_v2":
        blockers.append("VN100_CONTRACT_INVALID_FOR_RESEARCH")
        if inputs.universe_contract == "technical_candidate_union_v1":
            warnings.append("TECHNICAL_UNION_NOT_PIT")
    coverage = inputs.universe_coverage
    if coverage is None or not coverage.research_eligible:
        blockers.append("VN100_POINT_IN_TIME_HISTORY_INCOMPLETE")
    if coverage is not None and coverage.is_fixture:
        blockers.append("FIXTURE_EVIDENCE_NOT_RESEARCH_ELIGIBLE")
    if not inputs.eod_crosscheck_ready:
        blockers.append("HOSE_EOD_CROSSCHECK_INCOMPLETE")
    ca = inputs.corporate_action_certificate
    if ca is None or not ca.research_eligible:
        blockers.append("CORPORATE_ACTION_INVENTORY_INCOMPLETE")
    if ca is not None and ca.is_fixture:
        blockers.append("FIXTURE_CORPORATE_ACTIONS_NOT_RESEARCH_ELIGIBLE")
    if not inputs.price_basis_confirmed:
        blockers.append("PRICE_BASIS_UNCONFIRMED")
    result = KetQuaResearchGate(
        passed=len(blockers) == 0,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )
    result.kiem_tra()
    return result
