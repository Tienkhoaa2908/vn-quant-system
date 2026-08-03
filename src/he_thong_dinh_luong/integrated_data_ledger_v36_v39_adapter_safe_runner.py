"""Safe artifact runner for the V36/V39 adapter."""
from __future__ import annotations

import json
from pathlib import Path
import traceback
from typing import Sequence

from . import integrated_data_ledger_v36_safe_runner as bundler
from . import integrated_data_ledger_v36_v39_adapter as core


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    values = vars(args)
    v39_output = values.pop("v39_output_dir")
    values.pop("benchmark_ohlcv", None)
    try:
        report = core.run_v36_with_v39(v39_output_dir=v39_output, **values)
        bundle, digest = bundler._bundle(
            output_dir,
            status="SUCCESS",
            summary={
                "report_file": bundler.REPORT_FILE,
                "decision": report["decision"],
                "recommendation": report["recommendation"],
                "blockers": report["blockers"],
                "ledger_status": report["ledger_status"],
                "exact_cash_ledger_pnl_computed": report["exact_cash_ledger_pnl_computed"],
                "exact_vnindex_comparison_computed": report.get("exact_vnindex_comparison_computed", False),
                "decision_surface_assurance_v39": True,
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
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        bundler._write_json(output_dir / bundler.FAILURE_FILE, failure)
        bundle, digest = bundler._bundle(
            output_dir,
            status="FAILED",
            summary=failure,
        )
        bundler._emit({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "artifact_zip": str(bundle),
            "artifact_zip_sha256": digest,
            "live_capital_approved": False,
        })
        return 2
    bundler._emit({
        "status": "SUCCESS",
        "decision": report["decision"],
        "recommendation": report["recommendation"],
        "blockers": report["blockers"],
        "ledger_status": report["ledger_status"],
        "ledger_summaries": report["ledger_summaries"],
        "exact_cash_ledger_pnl_computed": report["exact_cash_ledger_pnl_computed"],
        "exact_vnindex_comparison_computed": report.get("exact_vnindex_comparison_computed", False),
        "artifact_zip": str(bundle),
        "artifact_zip_sha256": digest,
        "live_capital_approved": False,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
