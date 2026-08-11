"""Local-data parity guard for V58 causal tail research.

The causal rewrite must be behaviorally identical to V57 when the overlay is
disabled. This guard uses the frozen research input and local OHLCV, so it runs
on the workstation before the expensive V58 studies.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence
import argparse
import json

from . import tail_noadd_v57 as v57
from . import tail_noadd_v58 as v58
from . import weekly_micro_capital_v43 as base

DEFAULT_ANALYSIS_END = date(2026, 7, 31)


def _assert_close(name: str, left: float | None, right: float | None, tol: float) -> None:
    if left is None or right is None:
        if left != right:
            raise AssertionError(f"V58_BASELINE_PARITY_FAILED:{name}:{left}!={right}")
        return
    if abs(float(left) - float(right)) > tol:
        raise AssertionError(
            f"V58_BASELINE_PARITY_FAILED:{name}:{left}!={right}:tol={tol}"
        )


def run_guard(
    *,
    input_zip: Path,
    store_path: Path,
    contributions: Sequence[int] = base.CONTRIBUTIONS,
    price_multiplier: float = base.PRICE_MULTIPLIER,
    analysis_end: date = DEFAULT_ANALYSIS_END,
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

    checks = 0
    for contribution in sorted(set(int(value) for value in contributions)):
        for scenario in base.SCENARIOS:
            old_summary, _, _ = v57.simulate(
                spec=v57.NoAddSpec("BASELINE"),
                contribution=contribution,
                scenario=scenario,
                snapshots=snapshots,
                prices=prices,
                weekly_days=weekly_days,
                analysis_end=effective_end,
            )
            new_summary, _, _ = v58.simulate(
                spec=v58.NoAddSpec("BASELINE"),
                contribution=contribution,
                scenario=scenario,
                snapshots=snapshots,
                prices=prices,
                weekly_days=weekly_days,
                analysis_end=effective_end,
            )
            prefix = f"{contribution}:{scenario}"
            _assert_close(
                f"{prefix}:final_value_vnd",
                old_summary.get("final_value_vnd"),
                new_summary.get("final_value_vnd"),
                0.01,
            )
            _assert_close(
                f"{prefix}:xirr",
                old_summary.get("xirr"),
                new_summary.get("xirr"),
                1e-12,
            )
            _assert_close(
                f"{prefix}:max_drawdown",
                old_summary.get("max_drawdown"),
                new_summary.get("max_drawdown"),
                1e-12,
            )
            checks += 1

    return {
        "status": "PASS",
        "guard": "V58_BASELINE_PARITY",
        "checked_cells": checks,
        "effective_analysis_end": effective_end.isoformat(),
        "v57_tail_results_admissible": False,
        "v58_baseline_matches_v57": True,
        "live_model_change_authorized": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--contribution", type=int, action="append", dest="contributions")
    parser.add_argument("--price-multiplier", type=float, default=base.PRICE_MULTIPLIER)
    parser.add_argument(
        "--analysis-end",
        type=date.fromisoformat,
        default=DEFAULT_ANALYSIS_END,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_guard(
            input_zip=args.input_zip,
            store_path=args.store,
            contributions=args.contributions or base.CONTRIBUTIONS,
            price_multiplier=args.price_multiplier,
            analysis_end=args.analysis_end,
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
    print("V58_BASELINE_PARITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
