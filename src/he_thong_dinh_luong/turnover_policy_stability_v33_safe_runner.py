"""ASCII-safe workstation runner and artifact bundler for V33."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import turnover_policy_stability_v33 as core

BUNDLE_MANIFEST_FILE = "analysis_bundle_manifest_v33.json"
FAILURE_FILE = "run_failure_v33.json"


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _emit(value: object) -> None:
    sys.stdout.write(
        json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)
        + "\n"
    )
    sys.stdout.flush()


def _bundle(
    output_dir: Path,
    *,
    status: str,
    summary: Mapping[str, object],
) -> tuple[Path, str]:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path
        for path in destination.rglob("*")
        if path.is_file() and path.name != BUNDLE_MANIFEST_FILE
    )
    manifest = {
        "schema_version": "turnover_policy_stability_v33_analysis_bundle",
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
    _write_json(destination / BUNDLE_MANIFEST_FILE, manifest)
    bundle_path = destination.parent / f"{destination.name}.zip"
    temporary = bundle_path.with_suffix(".zip.tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    arcname=(
                        Path(destination.name)
                        / path.relative_to(destination)
                    ).as_posix(),
                )
    temporary.replace(bundle_path)
    return bundle_path, _sha256(bundle_path)


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        report = core.run_v33(
            v32_artifact_zip=args.v32_artifact_zip,
            output_dir=output_dir,
            expected_v32_sha256=args.expected_v32_sha256,
            caps=args.caps,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            seed=args.seed,
        )
        bundle, bundle_sha = _bundle(
            output_dir,
            status="SUCCESS",
            summary={
                "report_file": core.REPORT_FILE,
                "recommendation": report["recommendation"],
                "pre_registered_cap": core.PRE_REGISTERED_CAP,
                "cap3_summary": report["cap3_summary"],
                "cap3_paired_vs_nested": report["cap3_paired_vs_nested"],
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
        bundle = None
        bundle_sha = None
        bundle_error = None
        try:
            bundle, bundle_sha = _bundle(
                output_dir,
                status="FAILED",
                summary={
                    "failure_file": FAILURE_FILE,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
        except Exception as bundle_exc:
            bundle_error = f"{type(bundle_exc).__name__}:{bundle_exc}"
        _emit(
            {
                "status": "FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "output_dir": str(output_dir),
                "artifact_zip": str(bundle) if bundle else None,
                "artifact_zip_sha256": bundle_sha,
                "bundle_error": bundle_error,
                "live_capital_approved": False,
            }
        )
        return 2

    _emit(
        {
            "status": "SUCCESS",
            "output_dir": str(output_dir),
            "artifact_zip": str(bundle),
            "artifact_zip_sha256": bundle_sha,
            "recommendation": report["recommendation"],
            "cap3_summary": report["cap3_summary"],
            "cap3_paired_vs_nested": report["cap3_paired_vs_nested"],
            "exact_cash_ledger_pnl_computed": False,
            "live_capital_approved": False,
        }
    )
    return 0


__all__ = [
    "BUNDLE_MANIFEST_FILE",
    "FAILURE_FILE",
    "_bundle",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
