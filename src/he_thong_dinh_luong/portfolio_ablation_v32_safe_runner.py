"""ASCII-safe workstation runner and artifact bundler for V32."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Mapping, Sequence
import zipfile

from . import portfolio_ablation_v32 as core

BUNDLE_MANIFEST_FILE = "analysis_bundle_manifest_v32.json"
FAILURE_FILE = "run_failure_v32.json"


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


def _emit_json(value: object) -> None:
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


def _create_bundle(
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
        "schema_version": "portfolio_ablation_v32_analysis_bundle",
        "status": status,
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
        "summary": dict(summary),
        "portfolio_return_proxy_after_modeled_costs_computed": (
            status == "SUCCESS"
        ),
        "exact_cash_ledger_pnl_computed": False,
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
                        Path(destination.name)
                        / path.relative_to(destination)
                    ).as_posix(),
                )
    temporary_path.replace(bundle_path)
    return bundle_path, _sha256(bundle_path)


def _run_kwargs(args: object) -> dict[str, object]:
    return {
        "v31_artifact_zip": args.v31_artifact_zip,
        "v22_input_zip": args.v22_input_zip,
        "output_dir": args.output_dir,
        "expected_v31_sha256": args.expected_v31_sha256,
        "expected_input_sha256": args.expected_input_sha256,
        "breadths": args.breadths,
        "replacement_caps": args.replacement_caps,
        "validation_months": args.validation_months,
        "test_months": args.test_months,
        "minimum_outer_test_periods": args.minimum_outer_test_periods,
        "bootstrap_repetitions": args.bootstrap_repetitions,
        "bootstrap_block_months": args.bootstrap_block_months,
        "seed": args.seed,
        "broker_buy_fee_bps": args.broker_buy_fee_bps,
        "broker_sell_fee_bps": args.broker_sell_fee_bps,
        "exchange_buy_fee_bps": args.exchange_buy_fee_bps,
        "exchange_sell_fee_bps": args.exchange_sell_fee_bps,
        "sell_tax_bps": args.sell_tax_bps,
        "transfer_fee_vnd_per_share": args.transfer_fee_vnd_per_share,
        "transfer_reference_price_vnd": args.transfer_reference_price_vnd,
        "slippage_bps": args.slippage_bps,
        "stress_slippage_bps": args.stress_slippage_bps,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    try:
        report = core.run_v32(**_run_kwargs(args))
        bundle_path, bundle_sha = _create_bundle(
            output_dir,
            status="SUCCESS",
            summary={
                "report_file": core.REPORT_FILE,
                "recommendation": report["recommendation"],
                "diagnostic_passing_policies": report[
                    "diagnostic_passing_policies"
                ],
                "historical_promotion_passing_policies": report[
                    "historical_promotion_passing_policies"
                ],
                "candidate_models": report["candidate_models"],
                "breadths": report["breadths"],
            },
        )
    except Exception as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "portfolio_return_proxy_after_modeled_costs_computed": False,
            "exact_cash_ledger_pnl_computed": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "actionable": False,
        }
        _write_json(output_dir / FAILURE_FILE, failure)
        bundle_path: Path | None = None
        bundle_sha: str | None = None
        bundle_error: str | None = None
        try:
            bundle_path, bundle_sha = _create_bundle(
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
        _emit_json(
            {
                "status": "FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "output_dir": str(output_dir),
                "artifact_zip": str(bundle_path) if bundle_path else None,
                "artifact_zip_sha256": bundle_sha,
                "bundle_error": bundle_error,
                "failure_file": str(output_dir / FAILURE_FILE),
                "live_capital_approved": False,
            }
        )
        return 2

    _emit_json(
        {
            "status": "SUCCESS",
            "output_dir": str(output_dir),
            "artifact_zip": str(bundle_path),
            "artifact_zip_sha256": bundle_sha,
            "report_file": str(output_dir / core.REPORT_FILE),
            "diagnostic_passing_policies": report[
                "diagnostic_passing_policies"
            ],
            "historical_promotion_passing_policies": report[
                "historical_promotion_passing_policies"
            ],
            "recommendation": report["recommendation"],
            "portfolio_pnl_after_costs_computed": True,
            "exact_cash_ledger_pnl_computed": False,
            "live_capital_approved": False,
        }
    )
    return 0


__all__ = [
    "BUNDLE_MANIFEST_FILE",
    "FAILURE_FILE",
    "_create_bundle",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
