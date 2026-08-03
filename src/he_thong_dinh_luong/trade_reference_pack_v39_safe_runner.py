"""Safe runner and artifact bundler for V39.

The same official entrypoint seeds the workspace, expands optional compact
interval imports, validates the exact 510/510/52 surface and bundles the final
result. No approval flag is invented by the expansion step.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import traceback
from typing import Mapping, Sequence
import zipfile

from . import trade_reference_bulk_import_v39 as bulk
from . import trade_reference_pack_v39 as core

MANIFEST_FILE = "analysis_bundle_manifest_v39.json"
FAILURE_FILE = "run_failure_v39.json"


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _bundle(output_dir: Path, status: str, summary: Mapping[str, object]) -> tuple[Path, str]:
    root = Path(output_dir).resolve()
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != MANIFEST_FILE)
    manifest = {
        "schema_version": "trade_reference_pack_v39_analysis_bundle",
        "status": status,
        "file_count_excluding_manifest": len(files),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ],
        "summary": dict(summary),
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(root / MANIFEST_FILE, manifest)
    destination = root.parent / f"{root.name}.zip"
    temporary = destination.with_suffix(".zip.tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=(Path(root.name) / path.relative_to(root)).as_posix())
    temporary.replace(destination)
    return destination, _sha256(destination)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V39 authoritative decision-surface reference pack")
    parser.add_argument("--v36-artifact-zip", required=True, type=Path)
    parser.add_argument("--v38-artifact-zip", required=True, type=Path)
    parser.add_argument("--workspace-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-v36-sha256", default="")
    parser.add_argument("--expected-v38-sha256", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
        _write_json(output_dir / bulk.AUDIT_FILE, audit)
        bundle, digest = _bundle(
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
        _write_json(output_dir / FAILURE_FILE, failure)
        bundle, digest = _bundle(output_dir, "FAILED", failure)
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
