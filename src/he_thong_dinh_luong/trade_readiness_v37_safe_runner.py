"""Safe runner and artifact bundler for trade-readiness V37."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import trade_readiness_v37 as core

MANIFEST_FILE = "analysis_bundle_manifest_v37.json"
FAILURE_FILE = "run_failure_v37.json"


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
        "schema_version": "trade_readiness_v37_analysis_bundle",
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
                archive.write(path, arcname=(Path(destination.name) / path.relative_to(destination)).as_posix())
    temporary.replace(bundle)
    return bundle, _sha256(bundle)


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        report = core.run_v37(
            v36_artifact_zip=args.v36_artifact_zip,
            output_dir=output_dir,
            expected_v36_sha256=args.expected_v36_sha256,
            paper_observations=args.paper_observations,
            operational_checklist=args.operational_checklist,
        )
        bundle, digest = _bundle(
            output_dir,
            "SUCCESS",
            {
                "capital_stage": report["capital_stage"],
                "readiness_score_percent": report["readiness_score_percent"],
                "next_action": report["next_action"],
                "manual_micro_live_review_eligible": report["manual_micro_live_review_eligible"],
            },
        )
    except Exception as exc:
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
        "capital_stage": report["capital_stage"],
        "readiness_score_percent": report["readiness_score_percent"],
        "next_action": report["next_action"],
        "blockers": report["blockers"],
        "paper_observations": report["paper_holdout"]["completed_observation_count"],
        "artifact_zip": str(bundle),
        "artifact_zip_sha256": digest,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
