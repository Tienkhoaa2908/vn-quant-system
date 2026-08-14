"""Vietnam-time, causal-execution and evidence-contract-safe entry point for V77.

Vietnam has no daylight-saving transition in the project period, so this driver
uses an explicit UTC+07:00 timezone instead of depending on host tzdata. Generic
PIT membership evidence can close the HOSE gate only when its venue scope explicitly
says HOSE. Existing paper definitions and monthly signals are revalidated before an
idempotent rerun is accepted.

V77 workstation capture is an after-EOD workflow. A signal captured on Vietnam
calendar day D may therefore execute no earlier than the first market session on or
after D+1, even when the local market store is stale and still ends at D-1. This
prevents a later data sync from retroactively filling at an open that occurred before
the target was actually captured.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

from . import paper_oos_data_lineage_v77 as core
from .mo_phong import engine as sim_engine

VN_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
PIT_MEMBERSHIP_CONTRACTS = {
    "pit_membership_interval_v2",
    "pit_hose_membership_v1",
    "hose_membership_interval_v1",
}
EXECUTION_FLOOR_CONTRACT = "FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1"


def _explicit_hose_scope(record: Mapping[str, object], contract: str) -> bool:
    if contract in {"pit_hose_membership_v1", "hose_membership_interval_v1"}:
        return True
    raw = record.get("venue_scope") or record.get("exchange") or record.get("market") or ""
    return str(raw).strip().upper() == "HOSE"


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
        path_name = path.name.lower()
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
            hose_scope = _explicit_hose_scope(record, contract)

            if contract in PIT_MEMBERSHIP_CONTRACTS:
                matched.append("pit_hose_membership")
                if nonfixture and research and complete and not gaps and not conflicts and covers and hose_scope:
                    passes["pit_hose_membership"] = True

            if contract == "pit_sector_master_v1":
                matched.append("pit_sector_master")
                if nonfixture and research and complete and not gaps and not conflicts and covers:
                    passes["pit_sector_master"] = True

            is_corporate_path = "corporate" in path_name or "hanh_dong" in path_name
            if (
                is_corporate_path
                and "inventory_complete" in record
                and "research_eligible" in record
                and "is_fixture" in record
            ):
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
                    "explicit_hose_scope": hose_scope if "pit_hose_membership" in matched else None,
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


def _execution_floor_by_signal_day(state_dir: Path, model_id: str) -> dict[date, date]:
    rows = core._all_model_signals(Path(state_dir), model_id)
    captures: dict[date, set[str]] = {}
    for row in rows:
        signal_day = date.fromisoformat(str(row["paper_signal_day"]))
        captured_text = str(row.get("captured_at") or "")
        try:
            captured = datetime.fromisoformat(captured_text)
        except ValueError as exc:
            raise ValueError(f"V77_CAPTURE_TIMESTAMP_INVALID:{model_id}:{signal_day}") from exc
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError(f"V77_CAPTURE_TIMESTAMP_NAIVE:{model_id}:{signal_day}")
        captures.setdefault(signal_day, set()).add(captured.astimezone(timezone.utc).isoformat())
    floors: dict[date, date] = {}
    for signal_day, timestamps in captures.items():
        if len(timestamps) != 1:
            raise ValueError(f"V77_SIGNAL_CAPTURE_TIMESTAMP_CONFLICT:{model_id}:{signal_day}")
        captured = datetime.fromisoformat(next(iter(timestamps)))
        floor = captured.astimezone(VN_TZ).date() + timedelta(days=1)
        if floor <= signal_day:
            raise ValueError(f"V77_EXECUTION_FLOOR_NOT_AFTER_SIGNAL:{model_id}:{signal_day}:{floor}")
        floors[signal_day] = floor
    return floors


def _floor_aware_next_session(original, floors: Mapping[date, date]):
    def next_session(cac_ngay, chi_so, ngay):
        floor = floors.get(ngay)
        if floor is None:
            return original(cac_ngay, chi_so, ngay)
        start = chi_so[ngay] + 1
        for candidate in cac_ngay[start:]:
            if candidate >= floor:
                return candidate
        return None

    return next_session


def _guarded_replay(original):
    def replay(state_dir: Path, store: Path, model_id: str, output_dir: Path):
        floors = _execution_floor_by_signal_day(Path(state_dir), model_id)
        if not floors:
            return original(state_dir, store, model_id, output_dir)
        original_next = sim_engine._ngay_ke_tiep
        sim_engine._ngay_ke_tiep = _floor_aware_next_session(original_next, floors)
        try:
            result = original(state_dir, store, model_id, output_dir)
        finally:
            sim_engine._ngay_ke_tiep = original_next

        safe = model_id.lower().replace("/", "_")
        orders_path = Path(output_dir) / f"v77_{safe}_orders.csv"
        nav_path = Path(output_dir) / f"v77_{safe}_nav.csv"
        orders = core._read_csv(orders_path)
        latest_market = date.fromisoformat(str(result.get("latest_market_day")))
        retroactive = 0
        for row in orders:
            signal_text = str(row.get("signal_date") or "")
            if not signal_text:
                continue
            signal_day = date.fromisoformat(signal_text)
            floor = floors.get(signal_day)
            if floor is None:
                continue
            row["causal_execution_floor_date"] = floor.isoformat()
            execution_text = str(row.get("execution_date") or "").strip()
            if execution_text:
                execution_day = date.fromisoformat(execution_text)
                if execution_day < floor:
                    retroactive += 1
            elif latest_market < floor:
                row["status"] = "PENDING_NEXT_SESSION"
                row["reason"] = "CAUSAL_EXECUTION_FLOOR_NOT_REACHED"
        if retroactive:
            raise RuntimeError(f"V77_RETROACTIVE_FILL_DETECTED:{model_id}:{retroactive}")
        if orders:
            core._write_csv(orders_path, orders)
            result["pending_order_count"] = sum(
                str(row.get("status") or "") == "PENDING_NEXT_SESSION" for row in orders
            )

        earliest_floor = min(floors.values())
        nav_rows = core._read_csv(nav_path)
        result["fresh_oos_session_count"] = sum(
            date.fromisoformat(str(row["ngay"])) >= earliest_floor
            for row in nav_rows
            if row.get("ngay")
        )
        result["execution_floor_contract"] = EXECUTION_FLOOR_CONTRACT
        result["execution_floor_by_signal_day"] = {
            signal.isoformat(): floor.isoformat() for signal, floor in sorted(floors.items())
        }
        result["earliest_execution_floor_date"] = earliest_floor.isoformat()
        result["retroactive_fill_count"] = 0
        return result

    return replay


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
    original_replay = core._replay_model

    def vietnam_boundary(capture_day, _host_wall_day, confirmed):
        return original_boundary(capture_day, vn_wall_day, confirmed)

    core._analysis_end_for_capture = vietnam_boundary
    core._scan_evidence = _scan_evidence_once
    core._record_model_signal = _guarded_signal_recorder(original_recorder)
    core._replay_model = _guarded_replay(original_replay)
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
        core._replay_model = original_replay
    report["wall_date_contract"] = "ASIA_HO_CHI_MINH_UTC_PLUS_07"
    report["capture_wall_date_vn"] = vn_wall_day.isoformat()
    report["pit_membership_contracts_recognized"] = sorted(PIT_MEMBERSHIP_CONTRACTS)
    report["generic_membership_requires_explicit_hose_scope"] = True
    report["existing_freeze_definition_verified"] = True
    report["existing_source_signal_recompute_verified"] = True
    report["causal_execution_floor_verified"] = all(
        int(payload.get("retroactive_fill_count") or 0) == 0
        and payload.get("execution_floor_contract") == EXECUTION_FLOOR_CONTRACT
        for payload in report["paper_results"].values()
    )
    report["paper_execution_limitations"] = {
        "execution_floor_contract": EXECUTION_FLOOR_CONTRACT,
        "retroactive_fill_allowed": False,
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
        "causal_execution_floor_verified": report["causal_execution_floor_verified"],
        "promotion_authorized": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
