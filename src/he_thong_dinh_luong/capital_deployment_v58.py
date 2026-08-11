"""V58 research-only target-gap 3/4/5 capital deployment study.

This module extends V57 with the conservative residual-cash variants that add
more underweight names before any above-target spillover. It does not change
workstation/live behavior.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile
import argparse
import json

from . import capital_deployment_v57 as v57
from . import weekly_micro_capital_v43 as base

SCHEMA_VERSION = "capital_deployment_v58"
DEFAULT_ANALYSIS_END = date(2026, 7, 31)
DEFAULT_HOLDOUT_START = date(2022, 1, 1)

DeploymentSpec = v57.DeploymentSpec
_allocate = v57._allocate

VARIANTS: tuple[DeploymentSpec, ...] = (
    DeploymentSpec("BASELINE_ONE_ORDER", 1, False, 0.15),
    DeploymentSpec("TARGET_GAP_3", 3, False, 0.15),
    DeploymentSpec("TARGET_GAP_4", 4, False, 0.15),
    DeploymentSpec("TARGET_GAP_5", 5, False, 0.15),
    DeploymentSpec("STAGED_FULL_3_REFERENCE", 3, True, 0.15),
    DeploymentSpec("STAGED_FULL_5_REFERENCE", 5, True, 0.15),
)


def run_study(
    *,
    input_zip: Path,
    store_path: Path,
    output_dir: Path,
    output_zip: Path,
    contributions: Sequence[int] = base.CONTRIBUTIONS,
    price_multiplier: float = base.PRICE_MULTIPLIER,
    analysis_end: date = DEFAULT_ANALYSIS_END,
    holdout_start: date = DEFAULT_HOLDOUT_START,
) -> dict[str, object]:
    rows, _ = base._load_research_rows(input_zip)
    snapshots, _, _ = base.build_signal_snapshots(rows)
    prices = base._load_prices(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, snapshots[-1].day, prices.calendar[-1])
    weekly_days = base._weekly_days(
        prices.calendar,
        start=snapshots[0].day,
        end=effective_end,
    )
    calibration_end = date.fromordinal(holdout_start.toordinal() - 1)

    summaries: list[dict[str, object]] = []
    ledgers: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []

    for contribution in sorted(set(int(value) for value in contributions)):
        for scenario in base.SCENARIOS:
            for spec in VARIANTS:
                summary, ledger, trade_rows = v57.simulate(
                    spec=spec,
                    contribution=contribution,
                    scenario=scenario,
                    snapshots=snapshots,
                    prices=prices,
                    weekly_days=weekly_days,
                    analysis_end=effective_end,
                )
                summary = dict(summary)
                summary["schema_version"] = SCHEMA_VERSION
                summary["calibration"] = v57._segment(
                    ledger,
                    None,
                    calibration_end,
                )
                summary["holdout"] = v57._segment(
                    ledger,
                    holdout_start,
                    effective_end,
                )
                summary["live_model_change_authorized"] = False
                summaries.append(summary)
                ledgers.extend(
                    {
                        **dict(row),
                        "schema_version": SCHEMA_VERSION,
                    }
                    for row in ledger
                )
                trades.extend(
                    {
                        "variant": spec.variant_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        **dict(row),
                    }
                    for row in trade_rows
                )

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "effective_analysis_end": effective_end.isoformat(),
        "holdout_start": holdout_start.isoformat(),
        "variant_count": len(VARIANTS),
        "simulation_count": len(summaries),
        "target_gap_rule": (
            "TARGET_GAP_4_5_ADD_MORE_UNDERWEIGHT_NAMES_AND_DO_NOT_"
            "REDEPLOY_ABOVE_TARGET_EXCEPT_ONE_SHARE_BOOTSTRAP"
        ),
        "summary_rows": summaries,
        "permissions": {
            "research_only": True,
            "live_model_change_authorized": False,
        },
    }

    flat_rows: list[dict[str, object]] = []
    for row in summaries:
        flat = {
            key: value
            for key, value in row.items()
            if key not in {"calibration", "holdout"}
        }
        flat.update(
            {
                f"calibration_{key}": value
                for key, value in dict(row["calibration"]).items()
            }
        )
        flat.update(
            {
                f"holdout_{key}": value
                for key, value in dict(row["holdout"]).items()
            }
        )
        flat_rows.append(flat)

    files = {
        "capital_deployment_summary_v58.csv": base._csv_bytes(flat_rows),
        "capital_deployment_ledger_v58.csv": base._csv_bytes(ledgers),
        "capital_deployment_trades_v58.csv": base._csv_bytes(trades),
        "capital_deployment_report_v58.json": base._json_bytes(report),
    }
    files["manifest.json"] = base._json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "files": {
                name: {
                    "sha256": base._sha(payload),
                    "size_bytes": len(payload),
                }
                for name, payload in files.items()
            },
        }
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in files.items():
        (output_dir / name).write_bytes(payload)
    with ZipFile(output_zip, "w", ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)

    return {
        "status": "SUCCESS",
        "output_zip": str(output_zip.resolve()),
        "output_zip_sha256": sha256(output_zip.read_bytes()).hexdigest(),
        "simulation_count": len(summaries),
        "live_model_change_authorized": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument(
        "--contribution",
        type=int,
        action="append",
        dest="contributions",
    )
    parser.add_argument(
        "--price-multiplier",
        type=float,
        default=base.PRICE_MULTIPLIER,
    )
    parser.add_argument(
        "--analysis-end",
        type=date.fromisoformat,
        default=DEFAULT_ANALYSIS_END,
    )
    parser.add_argument(
        "--holdout-start",
        type=date.fromisoformat,
        default=DEFAULT_HOLDOUT_START,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_study(
            input_zip=args.input_zip,
            store_path=args.store,
            output_dir=args.output_dir,
            output_zip=args.output_zip,
            contributions=args.contributions or base.CONTRIBUTIONS,
            price_multiplier=args.price_multiplier,
            analysis_end=args.analysis_end,
            holdout_start=args.holdout_start,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
