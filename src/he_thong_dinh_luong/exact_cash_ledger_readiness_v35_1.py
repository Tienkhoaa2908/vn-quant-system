"""V35.1: data-assured exact-ledger readiness gate; never computes P&L."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import exact_cash_ledger_readiness_v35 as base

SCHEMA_VERSION = "exact_cash_ledger_readiness_v35_1"
REPORT_FILE = "exact_cash_ledger_readiness_v35_1.json"
GATES_FILE = "readiness_gates_v35_1.csv"
SCHEMA_FILE = "sqlite_schema_v35_1.csv"
BLOCKERS_FILE = "readiness_blockers_v35_1.csv"
ASSURANCE_SCHEMA = "exact_ledger_data_assurance_v1"


def audit_data_assurance(path: Path | None, *, sqlite_audit: Mapping[str, object], sector_master: Mapping[str, object], corporate_actions: Mapping[str, object]) -> dict[str, object]:
    flags = {"price_basis_confirmed": False, "point_in_time_sector_master_complete": False, "corporate_actions_complete": False}
    if path is None:
        return {"provided": False, "valid": False, **flags, "blocker": "EXACT_LEDGER_DATA_ASSURANCE_REPORT_MISSING"}
    source = Path(path).resolve()
    if not source.is_file():
        return {"provided": True, "valid": False, **flags, "blocker": "EXACT_LEDGER_DATA_ASSURANCE_REPORT_NOT_FOUND"}
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"provided": True, "valid": False, **flags, "blocker": "EXACT_LEDGER_DATA_ASSURANCE_REPORT_INVALID"}
    if not isinstance(value, Mapping):
        return {"provided": True, "valid": False, **flags, "blocker": "EXACT_LEDGER_DATA_ASSURANCE_REPORT_NOT_OBJECT"}
    first = str(value.get("coverage_first_day") or "")
    last = str(value.get("coverage_last_day") or "")
    coverage_ok = bool(first and last) and first <= str(sqlite_audit["first_day"]) and last >= str(sqlite_audit["last_day"])
    hashes = {
        "sqlite_sha256_match": str(value.get("sqlite_sha256") or "") == str(sqlite_audit["sha256"]),
        "sector_master_sha256_match": bool(sector_master.get("valid")) and str(value.get("sector_master_sha256") or "") == str(sector_master.get("sha256") or ""),
        "corporate_actions_sha256_match": bool(corporate_actions.get("valid")) and str(value.get("corporate_actions_sha256") or "") == str(corporate_actions.get("sha256") or ""),
    }
    flags = {
        "price_basis_confirmed": value.get("price_basis_confirmed") is True,
        "point_in_time_sector_master_complete": value.get("point_in_time_sector_master_complete") is True,
        "corporate_actions_complete": value.get("corporate_actions_complete") is True,
    }
    valid = bool(value.get("schema_version") == ASSURANCE_SCHEMA and coverage_ok and all(hashes.values()) and all(flags.values()))
    return {"provided": True, "path": str(source), "sha256": base._sha256(source), "schema_version": value.get("schema_version"), "coverage_first_day": first, "coverage_last_day": last, "coverage_contains_sqlite": coverage_ok, **hashes, **flags, "valid": valid, "blocker": "" if valid else "EXACT_LEDGER_DATA_ASSURANCE_NOT_VERIFIED"}


def run_v35_1(*, v34_artifact_zip: Path, sqlite_store: Path, output_dir: Path, expected_v34_sha256: str = "", expected_sqlite_sha256: str = "", sector_master: Path | None = None, corporate_actions: Path | None = None, data_assurance_report: Path | None = None, initial_capital_vnd: int = 1_000_000_000) -> dict[str, object]:
    out = Path(output_dir).resolve()
    if out.exists():
        raise FileExistsError(f"V35_1_OUTPUT_EXISTS:{out}")
    if initial_capital_vnd <= 0:
        raise ValueError("V35_1_INITIAL_CAPITAL_INVALID")
    frozen = base._verified_v34(v34_artifact_zip, expected_v34_sha256)
    store = base.audit_sqlite(sqlite_store, expected_sqlite_sha256)
    sector = base.audit_sector_master(sector_master)
    actions = base.audit_corporate_actions(corporate_actions)
    assurance = audit_data_assurance(data_assurance_report, sqlite_audit=store, sector_master=sector, corporate_actions=actions)
    assured = bool(assurance["valid"])
    gates = [
        ("V34_POLICY_VERIFIED", True, ""),
        ("SQLITE_UNIQUE_DAY_SYMBOL", store["duplicate_key_count"] == 0, "SQLITE_DUPLICATE_DAY_SYMBOL"),
        ("SQLITE_OHLCV_VALID", store["invalid_ohlcv_row_count"] == 0, "SQLITE_INVALID_OHLCV"),
        ("SQLITE_CONFLICTS_ZERO", store["conflict_row_count"] in (None, 0), "SQLITE_CONFLICTS_PRESENT"),
        ("T1_OPEN_COVERAGE_COMPLETE", store["t1_open_coverage_ratio"] == 1.0, "T1_OPEN_COVERAGE_INCOMPLETE"),
        ("SECTOR_MASTER_SCHEMA_VALID", bool(sector["valid"]), str(sector["blocker"])),
        ("CORPORATE_ACTION_SCHEMA_VALID", bool(actions["valid"]), str(actions["blocker"])),
        ("DATA_ASSURANCE_VERIFIED", assured, str(assurance["blocker"])),
        ("PRICE_BASIS_CONFIRMED", assured and bool(assurance["price_basis_confirmed"]), "PRICE_BASIS_UNCONFIRMED"),
        ("SECTOR_MASTER_COMPLETE", assured and bool(assurance["point_in_time_sector_master_complete"]), "POINT_IN_TIME_SECTOR_MASTER_COMPLETENESS_UNCONFIRMED"),
        ("CORPORATE_ACTIONS_COMPLETE", assured and bool(assurance["corporate_actions_complete"]), "CORPORATE_ACTION_COMPLETENESS_UNCONFIRMED"),
        ("INVERSE_VOLATILITY_ALLOCATOR_AVAILABLE", True, ""),
        ("SINGLE_NAME_CAP_15_AVAILABLE", True, ""),
        ("LOT_SIZE_100_LEDGER_REQUIRED", True, ""),
        ("SECTOR_CAP_25_DATA_READY", assured and bool(sector["valid"]), "POINT_IN_TIME_SECTOR_MASTER_NOT_READY_FOR_SECTOR_CAP"),
    ]
    gate_rows = [{"gate": n, "passed": bool(p), "blocker": "" if p else b} for n, p, b in gates]
    blockers = sorted({str(r["blocker"]) for r in gate_rows if r["blocker"]})
    ready = not blockers
    report = {
        "schema_version": SCHEMA_VERSION, "base_schema_version": base.SCHEMA_VERSION,
        "status": "SUCCESS", "audit_outcome": "READY" if ready else "BLOCKED",
        "recommendation": "READY_TO_IMPLEMENT_EXACT_CASH_LEDGER_SHADOW_BACKTEST" if ready else "BLOCKED_COMPLETE_DATA_CONTRACTS_BEFORE_EXACT_LEDGER",
        "policy_id": base.EXPECTED_POLICY_ID,
        "frozen_policy": {"model": base.EXPECTED_MODEL, "breadth": base.EXPECTED_BREADTH, "fixed_voluntary_replacement_cap": base.EXPECTED_CAP, "source_v34_artifact_sha256": frozen["artifact_sha256"], "source_v34_policy_sha256": frozen["policy_sha256"]},
        "initial_capital_vnd_for_future_shadow_ledger": int(initial_capital_vnd),
        "sqlite": {k: v for k, v in store.items() if k not in {"schema_rows", "tables"}},
        "sector_master": sector, "corporate_actions": actions, "data_assurance": assurance,
        "gates": gate_rows, "blockers": blockers, "exact_cash_ledger_pnl_computed": False,
        "historical_promotion_allowed": False, "research_eligible": False, "live_capital_approved": False,
        "automatic_live_orders_allowed": False, "actionable": False,
    }
    out.mkdir(parents=True)
    base._write_json(out / REPORT_FILE, report)
    base._write_csv(out / GATES_FILE, gate_rows, ("gate", "passed", "blocker"))
    base._write_csv(out / SCHEMA_FILE, store["schema_rows"], ("table", "column_index", "column", "declared_type", "not_null", "primary_key"))
    base._write_csv(out / BLOCKERS_FILE, [{"blocker": b} for b in blockers], ("blocker",))
    return report


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v34-artifact-zip", type=Path, required=True)
    p.add_argument("--sqlite-store", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--expected-v34-sha256", default="")
    p.add_argument("--expected-sqlite-sha256", default="")
    p.add_argument("--sector-master", type=Path)
    p.add_argument("--corporate-actions", type=Path)
    p.add_argument("--data-assurance-report", type=Path)
    p.add_argument("--initial-capital-vnd", type=int, default=1_000_000_000)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    report = run_v35_1(v34_artifact_zip=a.v34_artifact_zip, sqlite_store=a.sqlite_store, output_dir=a.output_dir, expected_v34_sha256=a.expected_v34_sha256, expected_sqlite_sha256=a.expected_sqlite_sha256, sector_master=a.sector_master, corporate_actions=a.corporate_actions, data_assurance_report=a.data_assurance_report, initial_capital_vnd=a.initial_capital_vnd)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
