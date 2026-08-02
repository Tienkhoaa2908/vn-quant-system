"""ASCII-safe workstation runner and complete ZIP bundler for V31."""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import all_history_protocol_v31 as core

BUNDLE_MANIFEST_FILE = "analysis_bundle_manifest_v31.json"
FAILURE_FILE = "run_failure_v31.json"


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
    text = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        allow_nan=False,
    )
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _write_csv_union(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str] | None = None,
) -> None:
    if not rows and not fields:
        return
    if fields is not None:
        fieldnames = list(fields)
    else:
        fieldnames: list[str] = []
        for row in rows:
            for field in row:
                if field not in fieldnames:
                    fieldnames.append(field)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


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
        "schema_version": "all_history_protocol_v31_analysis_bundle",
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
        "research_eligible": False,
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
            if path.is_file():
                archive.write(
                    path,
                    arcname=(
                        Path(destination.name) / path.relative_to(destination)
                    ).as_posix(),
                )
    temporary_path.replace(bundle_path)
    return bundle_path, _sha256(bundle_path)


def _run_arguments(args: object) -> dict[str, object]:
    return {
        "input_zip": args.input_zip,
        "output_dir": args.output_dir,
        "evaluation_months": args.evaluation_months,
        "minimum_train_months": args.minimum_train_months,
        "inner_validation_months": args.inner_validation_months,
        "pooled_block_months": args.pooled_block_months,
        "pooled_test_slot": args.pooled_test_slot,
        "pooled_validation_slot": args.pooled_validation_slot,
        "bootstrap_repetitions": args.bootstrap_repetitions,
        "bootstrap_block_months": args.bootstrap_block_months,
        "effective_trials": args.effective_trials,
        "seed": args.seed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        core._write_csv = _write_csv_union
        report = core.run_all_history_protocol_v31(**_run_arguments(args))
        bundle_path, bundle_sha = _create_analysis_bundle(
            output_dir,
            status=str(report.get("status") or "SUCCESS"),
            summary={
                "report_file": core.REPORT_FILE,
                "coverage_file": core.COVERAGE_JSON_FILE,
                "primary_protocol": report["primary_protocol"]["name"],
                "primary_fold_count": report["primary_protocol"]["fold_count"],
                "pooled_test_month_count": report["pooled_seven_month_protocol"][
                    "locked_test_month_count"
                ],
                "recommendation": report["recommendation"],
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
        "status": report["status"],
        "output_dir": str(output_dir),
        "artifact_zip": str(bundle_path),
        "artifact_zip_sha256": bundle_sha,
        "coverage_file": str(output_dir / core.COVERAGE_JSON_FILE),
        "primary_fold_count": report["primary_protocol"]["fold_count"],
        "primary_first_test_date": report["primary_protocol"]["first_test_date"],
        "primary_last_test_date": report["primary_protocol"]["last_test_date"],
        "pooled_test_month_count": report["pooled_seven_month_protocol"][
            "locked_test_month_count"
        ],
        "pooled_single_fit": True,
        "portfolio_pnl_after_costs_computed": False,
        "recommendation": report["recommendation"],
        "live_capital_approved": False,
    })
    return 0


__all__ = [
    "BUNDLE_MANIFEST_FILE",
    "FAILURE_FILE",
    "_write_csv_union",
    "_create_analysis_bundle",
    "_emit_json",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
