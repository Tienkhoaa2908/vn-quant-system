"""ASCII-safe workstation runner and artifact bundler for V34."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import future_paper_holdout_freeze_v34 as core

BUNDLE_MANIFEST_FILE = "analysis_bundle_manifest_v34.json"
FAILURE_FILE = "run_failure_v34.json"


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
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            allow_nan=False,
        )
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
        "schema_version": "future_paper_holdout_freeze_v34_analysis_bundle",
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
        "paper_trading_allowed": status == "SUCCESS",
        "historical_promotion_allowed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "exact_cash_ledger_pnl_computed": False,
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
        result = core.freeze_policy(
            v33_artifact_zip=args.v33_artifact_zip,
            output_dir=output_dir,
            freeze_timestamp=core._parse_timestamp(
                args.freeze_timestamp,
                name="freeze_timestamp",
            ),
            exclude_signal_through=core._parse_date(
                args.exclude_signal_through,
                name="exclude_signal_through",
            ),
            expected_v33_sha256=args.expected_v33_sha256,
        )
        bundle, bundle_sha = _bundle(
            output_dir,
            status="SUCCESS",
            summary={
                "report_file": core.REPORT_FILE,
                "policy_file": core.POLICY_FILE,
                "policy_id": result["policy_id"],
                "frozen_at": result["frozen_at"],
                "minimum_future_observations": (
                    result["minimum_future_observations"]
                ),
                "recommendation": result["recommendation"],
            },
        )
    except Exception as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "paper_trading_allowed": False,
            "historical_promotion_allowed": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
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
            "policy_id": result["policy_id"],
            "frozen_at": result["frozen_at"],
            "known_pre_freeze_signals_excluded_through": result[
                "known_pre_freeze_signals_excluded_through"
            ],
            "minimum_future_observations": result[
                "minimum_future_observations"
            ],
            "recommendation": result["recommendation"],
            "paper_trading_allowed": True,
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
