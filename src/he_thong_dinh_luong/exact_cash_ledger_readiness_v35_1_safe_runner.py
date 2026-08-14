"""ASCII-safe runner for V35.1 data-assured readiness."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback
from typing import Sequence

from . import exact_cash_ledger_readiness_v35_1 as core
from . import exact_cash_ledger_readiness_v35_safe_runner as base_safe

MANIFEST_FILE = "analysis_bundle_manifest_v35_1.json"
FAILURE_FILE = "run_failure_v35_1.json"


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
    sys.stdout.flush()


def _bundle(output_dir: Path, *, status: str, summary: dict[str, object]):
    original = base_safe.MANIFEST_FILE
    base_safe.MANIFEST_FILE = MANIFEST_FILE
    try:
        return base_safe._bundle(output_dir, status=status, summary=summary)
    finally:
        base_safe.MANIFEST_FILE = original


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        report = core.run_v35_1(
            v34_artifact_zip=args.v34_artifact_zip,
            sqlite_store=args.sqlite_store,
            output_dir=output_dir,
            expected_v34_sha256=args.expected_v34_sha256,
            expected_sqlite_sha256=args.expected_sqlite_sha256,
            sector_master=args.sector_master,
            corporate_actions=args.corporate_actions,
            data_assurance_report=args.data_assurance_report,
            initial_capital_vnd=args.initial_capital_vnd,
        )
        bundle, digest = _bundle(
            output_dir,
            status="SUCCESS",
            summary={
                "report_file": core.REPORT_FILE,
                "audit_outcome": report["audit_outcome"],
                "recommendation": report["recommendation"],
                "blockers": report["blockers"],
            },
        )
    except Exception as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "exact_cash_ledger_pnl_computed": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "actionable": False,
        }
        base_safe._write_json(output_dir / FAILURE_FILE, failure)
        try:
            bundle, digest = _bundle(
                output_dir,
                status="FAILED",
                summary={"failure_file": FAILURE_FILE, "error_type": type(exc).__name__, "error": str(exc)},
            )
            bundle_error = None
        except Exception as bundle_exc:
            bundle, digest = None, None
            bundle_error = f"{type(bundle_exc).__name__}:{bundle_exc}"
        _emit({
            "status": "FAILED", "error": f"{type(exc).__name__}:{exc}",
            "output_dir": str(output_dir), "artifact_zip": str(bundle) if bundle else None,
            "artifact_zip_sha256": digest, "bundle_error": bundle_error,
            "live_capital_approved": False,
        })
        return 2
    _emit({
        "status": "SUCCESS", "audit_outcome": report["audit_outcome"],
        "recommendation": report["recommendation"], "blockers": report["blockers"],
        "output_dir": str(output_dir), "artifact_zip": str(bundle),
        "artifact_zip_sha256": digest, "exact_cash_ledger_pnl_computed": False,
        "live_capital_approved": False,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
