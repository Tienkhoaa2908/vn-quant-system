"""ASCII-safe runner and artifact bundler for V35 readiness audit."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import exact_cash_ledger_readiness_v35 as core

MANIFEST_FILE = "analysis_bundle_manifest_v35.json"
FAILURE_FILE = "run_failure_v35.json"


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


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
    sys.stdout.flush()


def _bundle(output_dir: Path, *, status: str, summary: Mapping[str, object]) -> tuple[Path, str]:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in destination.rglob("*")
        if path.is_file() and path.name != MANIFEST_FILE
    )
    manifest = {
        "schema_version": "exact_cash_ledger_readiness_v35_analysis_bundle",
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
        "exact_cash_ledger_pnl_computed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "actionable": False,
    }
    _write_json(destination / MANIFEST_FILE, manifest)
    bundle = destination.parent / f"{destination.name}.zip"
    temporary = bundle.with_suffix(".zip.tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
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
        report = core.run_v35(
            v34_artifact_zip=args.v34_artifact_zip,
            sqlite_store=args.sqlite_store,
            output_dir=output_dir,
            expected_v34_sha256=args.expected_v34_sha256,
            expected_sqlite_sha256=args.expected_sqlite_sha256,
            sector_master=args.sector_master,
            corporate_actions=args.corporate_actions,
            price_basis_confirmed=args.price_basis_confirmed,
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
        _write_json(output_dir / FAILURE_FILE, failure)
        try:
            bundle, digest = _bundle(
                output_dir,
                status="FAILED",
                summary={
                    "failure_file": FAILURE_FILE,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            bundle_error = None
        except Exception as bundle_exc:
            bundle, digest = None, None
            bundle_error = f"{type(bundle_exc).__name__}:{bundle_exc}"
        _emit(
            {
                "status": "FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "output_dir": str(output_dir),
                "artifact_zip": str(bundle) if bundle else None,
                "artifact_zip_sha256": digest,
                "bundle_error": bundle_error,
                "live_capital_approved": False,
            }
        )
        return 2

    _emit(
        {
            "status": "SUCCESS",
            "audit_outcome": report["audit_outcome"],
            "recommendation": report["recommendation"],
            "blockers": report["blockers"],
            "output_dir": str(output_dir),
            "artifact_zip": str(bundle),
            "artifact_zip_sha256": digest,
            "exact_cash_ledger_pnl_computed": False,
            "live_capital_approved": False,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
