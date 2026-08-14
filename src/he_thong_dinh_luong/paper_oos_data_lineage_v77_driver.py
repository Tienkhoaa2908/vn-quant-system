"""Vietnam-time and evidence-contract-safe entry point for V77.

Vietnam has no daylight-saving transition in the project period, so this driver
uses an explicit UTC+07:00 timezone instead of depending on host tzdata. It also
recognizes the repository's existing PIT membership coverage contract, refuses
to continue a paper experiment whose frozen definition drifts, and verifies that
an already-captured monthly signal still recomputes identically before treating a
rerun as idempotent.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

from . import paper_oos_data_lineage_v77 as core

VN_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
PIT_MEMBERSHIP_CONTRACTS = {
    "pit_membership_interval_v2",
    "pit_hose_membership_v1",
    "hose_membership_interval_v1",
}


def _scan_evidence_once(
    search_roots: Sequence[Path], *, target_day, store_sha: str
) -> dict[str, object]:
    paths = core._candidate_json_files(search_roots)
    candidates: list[dict[str, object]] = []
    passes = {
        "pit_hose_membership": False,
        "corporate_actions": False,
        "pit_sector_master": False,
        "price_basis_certificate": False,
    }
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for record in core._walk_dicts(payload):
            if not isinstance(record, Mapping):
                continue
            contract = str(record.get("contract_version") or record.get("schema_version") or "")
            matched: list[str] = []
            nonfixture = record.get("is_fixture") is False
            research = record.get("research_eligible") is True
            complete = record.get("complete") is True or record.get("inventory_complete") is True
            gaps = record.get("gaps") or []
            conflicts = record.get("conflicts") or []
            covers = core._date_covers(record, target_day)

            if contract in PIT_MEMBERSHIP_CONTRACTS:
                matched.append("pit_hose_membership")
                if nonfixture and research and complete and not gaps and not conflicts and covers:
                    passes["pit_hose_membership"] = True

            if contract == "pit_sector_master_v1":
                matched.append("pit_sector_master")
                if nonfixture and research and complete and not gaps and not conflicts and covers:
                    passes["pit_sector_master"] = True

            if "inventory_complete" in record and "research_eligible" in record and "is_fixture" in record:
                matched.append("corporate_actions")
                if nonfixture and research and record.get("inventory_complete") is True and not conflicts and covers:
                    passes["corporate_actions"] = True

            if contract == "price_basis_certificate_v1":
                matched.append("price_basis_certificate")
                bound_sha = str(record.get("store_sha256") or "")
                basis = str(record.get("price_basis") or "").upper()
                if (
                    nonfixture
                    and research
                    and record.get("confirmed") is True
                    and bound_sha == store_sha
                    and basis in {"ADJUSTED", "UNADJUSTED"}
                    and not conflicts
                ):
                    passes["price_basis_certificate"] = True

            if matched:
                candidates.append({
                    "path": str(path),
                    "sha256": core._sha_file(path),
                    "contract": contract,
                    "matched_gates": matched,
                    "research_eligible": record.get("research_eligible"),
                    "is_fixture": record.get("is_fixture"),
                    "covers_target_day": covers,
                })
    return {"passes": passes, "candidates": candidates, "files_scanned": len(paths)}


def _validate_existing_freeze(state_dir: Path) -> None:
    path = Path(state_dir) / "freeze_manifest.json"
    if not path.is_file():
        return
    freeze = json.loads(path.read_text(encoding="utf-8-sig"))
    expected = {
        "schema_version": core.FREEZE_SCHEMA,
        "champion_model": core.CHAMPION_MODEL,
        "shadow_model": core.SHADOW_MODEL,
        "primary_variant": core.PRIMARY_VARIANT,
        "primary_allocator": core.PRIMARY_ALLOCATOR,
        "paper_cost_contract": core.PAPER_COST_CONTRACT,
        "future_model_mutation_allowed": False,
        "capital_authorized": False,
    }
    for key, value in expected.items():
        if freeze.get(key) != value:
            raise ValueError(f"V77_EXISTING_FREEZE_DEFINITION_DRIFT:{key}")
    symbols = freeze.get("variant_symbols")
    if not isinstance(symbols, list) or len(symbols) < 10 or len(symbols) != len(set(map(str, symbols))):
        raise ValueError("V77_EXISTING_FREEZE_VARIANT_SYMBOLS_INVALID")


def _guarded_signal_recorder(original):
    def record(**kwargs):
        state_dir = Path(kwargs["state_dir"])
        model_id = str(kwargs["model_id"])
        source_day = kwargs["source_day"].isoformat()
        existing = [
            row
            for path in core._model_signal_files(state_dir, model_id)
            for row in core._read_csv(path)
            if row.get("source_signal_day") == source_day
        ]
        if not existing:
            return original(**kwargs)
        if len(existing) != 10:
            raise ValueError(f"V77_EXISTING_SOURCE_SIGNAL_ROW_COUNT:{model_id}:{source_day}:{len(existing)}")
        old = sorted(existing, key=lambda row: int(row["rank"]))
        new = list(kwargs["ranking"][:10])
        if len(new) != 10:
            raise ValueError(f"V77_RECOMPUTED_TOP10_INCOMPLETE:{model_id}:{source_day}")
        for old_row, new_row in zip(old, new):
            if str(old_row.get("symbol")) != str(new_row.get("symbol")):
                raise ValueError(f"V77_EXISTING_SOURCE_SIGNAL_RECOMPUTE_DRIFT:{model_id}:{source_day}:symbol")
            if int(old_row.get("rank") or 0) != int(new_row.get("rank") or 0):
                raise ValueError(f"V77_EXISTING_SOURCE_SIGNAL_RECOMPUTE_DRIFT:{model_id}:{source_day}:rank")
            if str(old_row.get("risk_on", "")).lower() != str(bool(kwargs["risk_on"])).lower():
                raise ValueError(f"V77_EXISTING_SOURCE_SIGNAL_RECOMPUTE_DRIFT:{model_id}:{source_day}:risk_on")
            if not math.isclose(
                float(old_row.get("model_score") or 0.0),
                float(new_row.get("score") or 0.0),
                rel_tol=1e-10,
                abs_tol=1e-12,
            ):
                raise ValueError(f"V77_EXISTING_SOURCE_SIGNAL_RECOMPUTE_DRIFT:{model_id}:{source_day}:score")
        return None, False

    return record


def run(
    *,
    store: Path,
    state_dir: Path,
    output_dir: Path,
    search_roots: Sequence[Path] = (),
    git_head: str = "UNKNOWN",
    captured_at: datetime | None = None,
    month_close_confirmed: bool = False,
) -> dict[str, object]:
    captured = captured_at or datetime.now(timezone.utc)
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("V77_CAPTURE_TIME_MUST_HAVE_TIMEZONE")
    _validate_existing_freeze(Path(state_dir))
    vn_wall_day = captured.astimezone(VN_TZ).date()
    original_boundary = core._analysis_end_for_capture
    original_scan = core._scan_evidence
    original_recorder = core._record_model_signal

    def vietnam_boundary(capture_day, _host_wall_day, confirmed):
        return original_boundary(capture_day, vn_wall_day, confirmed)

    core._analysis_end_for_capture = vietnam_boundary
    core._scan_evidence = _scan_evidence_once
    core._record_model_signal = _guarded_signal_recorder(original_recorder)
    try:
        report = core.run(
            store=store,
            state_dir=state_dir,
            output_dir=output_dir,
            search_roots=search_roots,
            git_head=git_head,
            captured_at=captured,
            month_close_confirmed=month_close_confirmed,
        )
    finally:
        core._analysis_end_for_capture = original_boundary
        core._scan_evidence = original_scan
        core._record_model_signal = original_recorder
    report["wall_date_contract"] = "ASIA_HO_CHI_MINH_UTC_PLUS_07"
    report["capture_wall_date_vn"] = vn_wall_day.isoformat()
    report["pit_membership_contracts_recognized"] = sorted(PIT_MEMBERSHIP_CONTRACTS)
    report["existing_freeze_definition_verified"] = True
    report["existing_source_signal_recompute_verified"] = True
    report["paper_execution_limitations"] = {
        "settlement_mode": "M3_ENGINE_DEFAULT_IMMEDIATE_CASH_REUSE",
        "t2_no_advance_modeled": False,
        "transfer_fee_vnd_per_share_modeled": False,
        "pit_sector_cap_enforced": False,
        "reason": "V77 is a frozen comparative paper evidence lane, not exact V70 BASE execution.",
    }
    (Path(output_dir) / "v77_report.json").write_text(core._json_text(report), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    try:
        captured = datetime.fromisoformat(args.capture_time) if args.capture_time else None
        report = run(
            store=args.store,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            search_roots=args.search_root,
            git_head=args.git_head,
            captured_at=captured,
            month_close_confirmed=args.month_close_confirmed,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report["status"],
        "capture_market_day": report["capture_market_day"],
        "capture_wall_date_vn": report["capture_wall_date_vn"],
        "source_signal_day": report["source_signal_day"],
        "signals_appended": report["signals_appended"],
        "champion_paper": report["paper_results"][core.CHAMPION_MODEL],
        "shadow_paper": report["paper_results"][core.SHADOW_MODEL],
        "data_gate_blockers": report["data_lineage"]["blockers"],
        "promotion_authorized": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
