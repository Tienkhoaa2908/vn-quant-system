"""ASCII-safe runner and artifact bundler for V38."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import trade_evidence_accelerator_v38 as core

MANIFEST_FILE = "analysis_bundle_manifest_v38.json"
FAILURE_FILE = "run_failure_v38.json"


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _bundle(output_dir: Path, status: str, summary: Mapping[str, object]) -> tuple[Path, str]:
    destination = Path(output_dir).resolve()
    files = sorted(
        path for path in destination.rglob("*")
        if path.is_file() and path.name != MANIFEST_FILE
    )
    manifest = {
        "schema_version": "trade_evidence_accelerator_v38_analysis_bundle",
        "status": status,
        "file_count_excluding_manifest": len(files),
        "files": [
            {
                "path": path.relative_to(destination).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ],
        "summary": dict(summary),
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(destination / MANIFEST_FILE, manifest)
    bundle = destination.parent / f"{destination.name}.zip"
    temporary = bundle.with_suffix(".zip.tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    arcname=(Path(destination.name) / path.relative_to(destination)).as_posix(),
                )
    temporary.replace(bundle)
    return bundle, _sha256(bundle)


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        report = core.run_v38(
            v36_artifact_zip=args.v36_artifact_zip,
            v37_artifact_zip=args.v37_artifact_zip,
            output_dir=output_dir,
            expected_v36_sha256=args.expected_v36_sha256,
            expected_v37_sha256=args.expected_v37_sha256,
        )
        bundle, digest = _bundle(
            output_dir,
            "SUCCESS",
            {
                "policy_id": report["policy_id"],
                "position_time_key_count": report["decision_surface"]["position_time_key_count"],
                "holding_window_count": report["decision_surface"]["holding_window_count"],
                "operational_passed": report["operational_dry_run"]["passed_count"],
                "operational_total": report["operational_dry_run"]["total_count"],
                "next_action": report["next_action"],
            },
        )
    except Exception as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        _write_json(output_dir / FAILURE_FILE, failure)
        bundle, digest = _bundle(output_dir, "FAILED", failure)
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                    "artifact_zip": str(bundle),
                    "artifact_zip_sha256": digest,
                    "live_capital_approved": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": "SUCCESS",
                "objective": report["objective"],
                "position_time_key_count": report["decision_surface"]["position_time_key_count"],
                "holding_window_count": report["decision_surface"]["holding_window_count"],
                "unique_symbol_count": report["decision_surface"]["unique_symbol_count"],
                "execution_date_count": report["decision_surface"]["execution_date_count"],
                "operational_passed": report["operational_dry_run"]["passed_count"],
                "operational_total": report["operational_dry_run"]["total_count"],
                "remaining_workstation_controls": report["operational_dry_run"][
                    "remaining_workstation_controls"
                ],
                "next_action": report["next_action"],
                "artifact_zip": str(bundle),
                "artifact_zip_sha256": digest,
                "live_capital_approved": False,
                "automatic_live_orders_allowed": False,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
