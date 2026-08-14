"""Integrated V38 trade-evidence accelerator.

This module composes bundle verification, decision-surface extraction and
operational dry-runs. It never grants research or live-capital permission.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .trade_evidence_accelerator_v38_io import (
    load_verified_bundle as _load_verified_bundle,
    read_csv_bytes as _read_csv_bytes,
    write_csv as _write_csv,
    write_json as _write_json,
)
from .trade_evidence_accelerator_v38_surface import build_decision_surface
from .trade_evidence_accelerator_v38_ops import (
    OPS_KEYS, OperationalGuard, authoritative_source_registry, run_operational_dry_run,
)

SCHEMA_VERSION = "vn_quant_trade_evidence_accelerator_v38"
REPORT_FILE = "trade_evidence_accelerator_v38.json"
SECTOR_KEYS_FILE = "required_sector_keys_v38.csv"
ACTION_WINDOWS_FILE = "required_corporate_action_windows_v38.csv"
PRICE_DATES_FILE = "required_price_basis_dates_v38.csv"
OPS_FILE = "operational_dry_run_v38.json"
OPS_CHECKLIST_FILE = "operational_checklist_v37_candidate.json"
SOURCE_REGISTRY_FILE = "authoritative_source_registry_v38.json"
ASSURANCE_TEMPLATE_FILE = "decision_surface_assurance_v38_template.json"
EXPECTED_POLICY_ID = "c3-top10-cap3-c32fe6ec8c2fd4ce"

def run_v38(
    *,
    v36_artifact_zip: Path,
    v37_artifact_zip: Path,
    output_dir: Path,
    expected_v36_sha256: str = "",
    expected_v37_sha256: str = "",
) -> dict[str, object]:
    out = Path(output_dir).resolve()
    if out.exists():
        raise FileExistsError(f"V38_OUTPUT_EXISTS:{out}")
    out.mkdir(parents=True)

    v36 = _load_verified_bundle(
        v36_artifact_zip,
        manifest_name="analysis_bundle_manifest_v36.json",
        report_name="integrated_data_ledger_v36.json",
        expected_sha256=expected_v36_sha256,
    )
    v37 = _load_verified_bundle(
        v37_artifact_zip,
        manifest_name="analysis_bundle_manifest_v37.json",
        report_name="trade_readiness_v37.json",
        expected_sha256=expected_v37_sha256,
    )
    v36_report = dict(v36["report"])
    v37_report = dict(v37["report"])
    if str(v36_report.get("policy_id") or "") != EXPECTED_POLICY_ID:
        raise ValueError("V38_POLICY_ID_MISMATCH")
    if str(v37_report.get("policy_id") or "") != EXPECTED_POLICY_ID:
        raise ValueError("V38_V37_POLICY_ID_MISMATCH")

    members = dict(v36["members"])
    for required in ("selection_lineage_audit_v36.csv", "benchmark_execution_coverage_v36.csv"):
        if required not in members:
            raise ValueError(f"V38_V36_DECISION_SURFACE_MEMBER_MISSING:{required}")
    selection_rows = _read_csv_bytes(members["selection_lineage_audit_v36.csv"])
    benchmark_rows = _read_csv_bytes(members["benchmark_execution_coverage_v36.csv"])
    surface = build_decision_surface(selection_rows, benchmark_rows)
    ops = run_operational_dry_run()
    sources = authoritative_source_registry()

    _write_csv(
        out / SECTOR_KEYS_FILE,
        surface["sector_keys"],
        (
            "signal_date", "execution_day", "symbol", "sector", "effective_from",
            "effective_to", "source_url", "source_document_date", "verified",
        ),
    )
    _write_csv(
        out / ACTION_WINDOWS_FILE,
        surface["action_windows"],
        (
            "signal_date", "holding_start", "holding_end", "symbol",
            "source_checked", "event_count", "source_url", "verified_complete",
        ),
    )
    _write_csv(
        out / PRICE_DATES_FILE,
        surface["price_dates"],
        (
            "execution_day", "price_basis_mode", "price_unit_vnd_multiplier",
            "official_source_url", "crosscheck_symbol_count", "verified",
        ),
    )
    _write_json(out / OPS_FILE, ops)
    _write_json(out / OPS_CHECKLIST_FILE, ops["checklist"])
    _write_json(out / SOURCE_REGISTRY_FILE, sources)

    assurance_template = {
        "schema_version": "decision_surface_assurance_v38",
        "policy_id": EXPECTED_POLICY_ID,
        "coverage": {
            "period_count": surface["period_count"],
            "position_time_key_count": surface["position_time_key_count"],
            "holding_window_count": surface["holding_window_count"],
            "unique_symbol_count": surface["unique_symbol_count"],
            "execution_date_count": surface["execution_date_count"],
            "first_execution_day": surface["first_execution_day"],
            "last_execution_day": surface["last_execution_day"],
        },
        "files": {
            "sector_master_decision_surface_sha256": "REPLACE_WITH_SHA256",
            "corporate_actions_decision_surface_sha256": "REPLACE_WITH_SHA256",
            "price_basis_evidence_sha256": "REPLACE_WITH_SHA256",
        },
        "confirmations": {
            "sector_keys_complete": False,
            "corporate_action_windows_complete": False,
            "price_basis_confirmed": False,
            "price_unit_vnd_multiplier": 1000,
            "reviewer": "",
            "reviewed_at": "",
        },
        "live_capital_approved": False,
    }
    _write_json(out / ASSURANCE_TEMPLATE_FILE, assurance_template)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "objective": "SHRINK_AND_PARALLELIZE_REMAINING_TRADE_EVIDENCE",
        "policy_id": EXPECTED_POLICY_ID,
        "source_v36": {
            "path": v36["path"],
            "sha256": v36["sha256"],
            "manifest_entry_count": v36["manifest_entry_count"],
        },
        "source_v37": {
            "path": v37["path"],
            "sha256": v37["sha256"],
            "manifest_entry_count": v37["manifest_entry_count"],
            "capital_stage": v37_report.get("capital_stage"),
            "readiness_score_percent": v37_report.get("readiness_score_percent"),
        },
        "decision_surface": {
            key: surface[key]
            for key in (
                "period_count", "position_time_key_count", "holding_window_count",
                "unique_symbol_count", "execution_date_count", "first_execution_day",
                "last_execution_day", "unique_symbols",
            )
        },
        "operational_dry_run": {
            "passed_count": ops["passed_count"],
            "total_count": ops["total_count"],
            "remaining_workstation_controls": ops["remaining_workstation_controls"],
        },
        "parallel_workstreams": [
            {
                "workstream": "REFERENCE_DATA_DECISION_SURFACE",
                "status": "READY_FOR_ACQUISITION",
                "scope": (
                    f"{surface['position_time_key_count']} sector keys; "
                    f"{surface['holding_window_count']} corporate-action windows; "
                    f"{surface['execution_date_count']} price-basis dates"
                ),
            },
            {
                "workstream": "OPERATIONS_DRY_RUN",
                "status": f"{ops['passed_count']}/{ops['total_count']}",
                "remaining": ops["remaining_workstation_controls"],
            },
            {
                "workstream": "EXACT_LEDGER",
                "status": "BLOCKED_UNTIL_DECISION_SURFACE_ASSURANCE",
            },
            {
                "workstream": "FUTURE_HOLDOUT",
                "status": (
                    f"{int((v37_report.get('paper_holdout') or {}).get('completed_observation_count') or 0)}/12"
                ),
            },
        ],
        "next_action": "COMPLETE_DECISION_SURFACE_DATA_AND_TWO_WORKSTATION_CONTROLS_THEN_RERUN_INTEGRATED_GATE",
        "research_eligible": False,
        "manual_micro_live_review_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(out / REPORT_FILE, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trade-evidence accelerator V38")
    parser.add_argument("--v36-artifact-zip", type=Path, required=True)
    parser.add_argument("--v37-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v36-sha256", default="")
    parser.add_argument("--expected-v37-sha256", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_v38(
        v36_artifact_zip=args.v36_artifact_zip,
        v37_artifact_zip=args.v37_artifact_zip,
        output_dir=args.output_dir,
        expected_v36_sha256=args.expected_v36_sha256,
        expected_v37_sha256=args.expected_v37_sha256,
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
