"""V39 safe runner with compact interval expansion before final validation."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import traceback
from typing import Sequence

from . import trade_reference_bulk_import_v39 as bulk
from . import trade_reference_pack_v39 as core
from . import trade_reference_pack_v39_safe_runner as safe


def main(argv: Sequence[str] | None = None) -> int:
    args = safe._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    workspace = Path(args.workspace_dir).resolve()
    seed_output = output_dir.parent / f".{output_dir.name}-seed"
    try:
        if seed_output.exists():
            raise FileExistsError(f"V39_BULK_SEED_OUTPUT_EXISTS:{seed_output}")
        core.run_v39(
            v36_artifact_zip=args.v36_artifact_zip,
            v38_artifact_zip=args.v38_artifact_zip,
            workspace_dir=workspace,
            output_dir=seed_output,
            expected_v36_sha256=args.expected_v36_sha256,
            expected_v38_sha256=args.expected_v38_sha256,
        )
        shutil.rmtree(seed_output)
        audit = bulk.apply_bulk_import(workspace)
        report = core.run_v39(
            v36_artifact_zip=args.v36_artifact_zip,
            v38_artifact_zip=args.v38_artifact_zip,
            workspace_dir=workspace,
            output_dir=output_dir,
            expected_v36_sha256=args.expected_v36_sha256,
            expected_v38_sha256=args.expected_v38_sha256,
        )
        report["bulk_import"] = audit
        core.write_json(output_dir / core.REPORT_FILE, report)
        safe._write_json(output_dir / bulk.AUDIT_FILE, audit)
        bundle, digest = safe._bundle(
            output_dir,
            "SUCCESS",
            {
                "decision": report["decision"],
                "reference_pack_ready": report["reference_pack_ready"],
                "gap_count": report["gap_count"],
                "next_action": report["next_action"],
                "bulk_expanded_rows": audit["expanded_rows"],
            },
        )
    except Exception as exc:
        if seed_output.exists():
            shutil.rmtree(seed_output, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        safe._write_json(output_dir / safe.FAILURE_FILE, failure)
        bundle, digest = safe._bundle(output_dir, "FAILED", failure)
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "artifact_zip": str(bundle),
            "artifact_zip_sha256": digest,
            "live_capital_approved": False,
        }, ensure_ascii=True, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "SUCCESS",
        "decision": report["decision"],
        "reference_pack_ready": report["reference_pack_ready"],
        "gap_count": report["gap_count"],
        "metrics": report["metrics"],
        "bulk_import": audit,
        "workspace_dir": report["workspace_dir"],
        "next_action": report["next_action"],
        "artifact_zip": str(bundle),
        "artifact_zip_sha256": digest,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
