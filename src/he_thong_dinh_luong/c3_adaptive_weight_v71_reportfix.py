"""Reporting-safe V71 entrypoint.

V71 deep-backtest calculations are produced by the provenance-safe entrypoint.
This wrapper rebuilds annual rows from the already-complete monthly rows so
adaptive candidates retain cost-scenario metadata.  The original workstation
artifact exposed the defect because adaptive annual rows had blank
``cost_scenario`` and therefore disappeared from ``v71_2026_shadow.csv``.

No ranking, weighting, trade, return, or candidate-selection calculation is
changed here.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from . import c3_adaptive_weight_v71 as base
from . import c3_adaptive_weight_v71_safe as safe


def _compound(values: Sequence[float]) -> float:
    wealth = 1.0
    for value in values:
        wealth *= 1.0 + float(value)
    return wealth - 1.0


def rebuild_annual_from_monthly(monthly_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in monthly_rows:
        end = str(row.get("period_end_day") or "")
        if len(end) < 4:
            continue
        try:
            year = int(end[:4])
        except ValueError:
            continue
        key = (
            str(row.get("variant_id") or ""),
            str(row.get("allocator") or ""),
            str(row.get("candidate_id") or ""),
            str(row.get("cost_scenario") or ""),
            year,
        )
        grouped[key].append(row)

    output: list[dict[str, object]] = []
    for (variant, allocator, candidate, cost_scenario, year), rows in sorted(grouped.items()):
        if not cost_scenario:
            raise ValueError(f"V71_ANNUAL_REBUILD_COST_SCENARIO_MISSING:{variant}:{allocator}:{candidate}:{year}")
        rows = sorted(rows, key=lambda row: str(row.get("period_end_day") or ""))
        strategy_return = _compound([float(row["strategy_return"]) for row in rows])
        benchmark_return = _compound([float(row["benchmark_return"]) for row in rows])
        first = rows[0]
        output.append({
            "variant_id": variant,
            "strategy_id": str(first.get("strategy_id") or ""),
            "allocator": allocator,
            "cost_scenario": cost_scenario,
            "candidate_id": candidate,
            "year": year,
            "strategy_return": strategy_return,
            "benchmark_return": benchmark_return,
            "alpha_arithmetic": strategy_return - benchmark_return,
            "source": str(first.get("source") or ""),
        })
    return output


def analyze(**kwargs):
    report = safe.analyze(**kwargs)
    output_dir = Path(kwargs["output_dir"])
    monthly_rows = base._read_csv(output_dir / "v71_monthly_returns.csv")
    annual_rows = rebuild_annual_from_monthly(monthly_rows)
    shadow = base._shadow_2026(annual_rows, monthly_rows)

    base._write_csv(output_dir / "v71_annual_returns.csv", annual_rows)
    base._write_csv(output_dir / "v71_2026_shadow.csv", shadow)

    adaptive_ids = {item.candidate_id for item in base.CANDIDATES[1:]}
    shadow_ids = {str(row.get("candidate_id") or "") for row in shadow}
    if not adaptive_ids.issubset(shadow_ids):
        missing = sorted(adaptive_ids - shadow_ids)
        raise ValueError("V71_ADAPTIVE_2026_SHADOW_MISSING:" + "|".join(missing))

    report["annual_reporting_rebuilt_from_monthly"] = True
    report["annual_cost_scenario_preserved"] = True
    report["adaptive_2026_shadow_included"] = True
    report["v71_2026_shadow_row_count"] = len(shadow)
    (output_dir / "v71_report.json").write_text(
        base.json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    parser = base.argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signflip-samples", type=int, default=base.SIGNFLIP_SAMPLES)
    parser.add_argument("--bootstrap-samples", type=int, default=base.BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    report = analyze(
        v68_output=args.v68_output,
        v70_output=args.v70_output,
        store=args.store,
        output_dir=args.output_dir,
        signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(base.json.dumps({
        "schema_version": report["schema_version"],
        "status": report["status"],
        "champion_model": report["champion_model"],
        "diagnostic_watchlist_count": report["diagnostic_watchlist_count"],
        "adaptive_2026_shadow_included": report["adaptive_2026_shadow_included"],
        "promotion_authorized": report["promotion_authorized"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
