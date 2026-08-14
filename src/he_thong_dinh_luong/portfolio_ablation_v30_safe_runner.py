"""Robust workstation entrypoint for V30.

This wrapper keeps console output ASCII-safe on Windows code pages and always
packages every generated analysis file into one ZIP archive.  If execution
fails after partial output has been written, the partial directory, traceback
and failure manifest are packaged as well.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import portfolio_ablation_v30 as core
from .portfolio_ablation_v30_runner import run_v30_compatible

BUNDLE_MANIFEST_FILE = "analysis_bundle_manifest_v30.json"
FAILURE_FILE = "run_failure_v30.json"


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
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


def _emit_json(value: object) -> None:
    """Print only ASCII bytes so CP1252/CP850 consoles cannot fail."""
    text = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        allow_nan=False,
    )
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _analysis_files(output_dir: Path) -> list[Path]:
    destination = Path(output_dir).resolve()
    return sorted(
        path
        for path in destination.rglob("*")
        if path.is_file() and path.name != BUNDLE_MANIFEST_FILE
    )


def _create_analysis_bundle(
    output_dir: Path,
    *,
    status: str,
    summary: Mapping[str, object] | None = None,
) -> tuple[Path, str]:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = _analysis_files(destination)
    manifest = {
        "schema_version": "portfolio_ablation_v30_analysis_bundle",
        "status": str(status),
        "output_dir": str(destination),
        "file_count_excluding_manifest": len(files),
        "files": [
            {
                "path": path.relative_to(destination).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ],
        "summary": dict(summary or {}),
        "live_capital_approved": False,
        "actionable": False,
    }
    manifest_path = destination / BUNDLE_MANIFEST_FILE
    _write_json(manifest_path, manifest)

    bundle_path = destination.parent / f"{destination.name}.zip"
    temporary_path = bundle_path.with_suffix(".zip.tmp")
    if temporary_path.exists():
        temporary_path.unlink()
    with zipfile.ZipFile(
        temporary_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(destination.rglob("*")):
            if not path.is_file():
                continue
            archive.write(
                path,
                arcname=(Path(destination.name) / path.relative_to(destination)).as_posix(),
            )
    temporary_path.replace(bundle_path)
    return bundle_path, _sha256(bundle_path)


def _run_arguments(args: argparse.Namespace) -> dict[str, object]:
    return {
        "v29_artifact_zip": args.v29_artifact_zip,
        "model_output": args.model_output,
        "output_dir": args.output_dir,
        "expected_v29_sha256": args.expected_v29_sha256,
        "expected_input_sha256": args.expected_input_sha256,
        "breadths": args.breadths,
        "replacement_caps": args.replacement_caps,
        "validation_months": args.validation_months,
        "test_months": args.test_months,
        "minimum_outer_test_periods": args.minimum_outer_test_periods,
        "bootstrap_repetitions": args.bootstrap_repetitions,
        "bootstrap_block_months": args.bootstrap_block_months,
        "seed": args.seed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        result = run_v30_compatible(**_run_arguments(args))
        bundle_path, bundle_sha = _create_analysis_bundle(
            output_dir,
            status=str(result.get("status") or "SUCCESS"),
            summary={
                "recommendation": result.get("recommendation"),
                "passing_breadths": result.get("passing_breadths", []),
                "performance_status_file": "performance_status_v30.csv",
                "report_file": core.REPORT_FILE,
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
            "actionable": False,
        }
        _write_json(output_dir / FAILURE_FILE, failure)
        bundle_path: Path | None = None
        bundle_sha: str | None = None
        bundle_error: str | None = None
        try:
            bundle_path, bundle_sha = _create_analysis_bundle(
                output_dir,
                status="FAILED",
                summary={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "failure_file": FAILURE_FILE,
                },
            )
        except Exception as bundle_exc:
            bundle_error = f"{type(bundle_exc).__name__}:{bundle_exc}"
        _emit_json({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "output_dir": str(output_dir),
            "artifact_zip": str(bundle_path) if bundle_path else None,
            "artifact_zip_sha256": bundle_sha,
            "bundle_error": bundle_error,
            "failure_file": str(output_dir / FAILURE_FILE),
            "live_capital_approved": False,
        })
        return 2

    _emit_json({
        "status": result.get("status"),
        "output_dir": str(output_dir),
        "artifact_zip": str(bundle_path),
        "artifact_zip_sha256": bundle_sha,
        "passing_breadths": result.get("passing_breadths", []),
        "recommendation": result.get("recommendation"),
        "performance_status_file": str(output_dir / "performance_status_v30.csv"),
        "availability_file": str(output_dir / "breadth_availability_v30.csv"),
        "availability_cash_slot_compatibility_applied": True,
        "live_capital_approved": False,
    })
    return 0


__all__ = [
    "BUNDLE_MANIFEST_FILE",
    "FAILURE_FILE",
    "_create_analysis_bundle",
    "_emit_json",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
