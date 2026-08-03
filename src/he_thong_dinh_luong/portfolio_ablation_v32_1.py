"""Full-horizon breadth compatibility layer for V32.

The canonical V22 eligibility filter can leave fewer symbols than some requested
Top-K breadths in isolated months. V32.1 preserves the complete chronological
57-month horizon: it evaluates only breadths feasible in every eligible month
and records larger breadths as INFEASIBLE_FULL_HORIZON. It never shrinks K and
never drops sparse months to manufacture a result.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import portfolio_ablation_v30 as v30
from . import portfolio_ablation_v32 as core

UPGRADE_SCHEMA_VERSION = "portfolio_ablation_v32_1"
FEASIBILITY_FILE = "breadth_feasibility_v32.csv"
_ORIGINAL_RUN_V32 = core.run_v32


def _breadth_feasibility(
    prediction_rows: Sequence[Mapping[str, object]],
    requested_breadths: Sequence[int],
) -> tuple[tuple[int, ...], tuple[int, ...], list[dict[str, object]]]:
    """Classify requested Top-K values without changing K or dropping months."""
    requested = v30._normalize_breadths(requested_breadths)
    counts: dict[str, int] = defaultdict(int)
    seen: set[tuple[str, str]] = set()
    for row in prediction_rows:
        if str(row.get("model") or "") != core.FROZEN_MODEL:
            continue
        day = str(row.get("test_date") or "")
        symbol = str(row.get("symbol") or "").upper()
        if not day or not symbol:
            raise ValueError("V32_1_PREDICTION_KEY_MISSING")
        key = (day, symbol)
        if key in seen:
            raise ValueError(f"V32_1_DUPLICATE_ELIGIBLE_KEY:{day}:{symbol}")
        seen.add(key)
        counts[day] += 1
    if not counts:
        raise ValueError("V32_1_NO_ELIGIBLE_MONTH_COUNTS")

    rows: list[dict[str, object]] = []
    feasible: list[int] = []
    infeasible: list[int] = []
    ordered_days = sorted(counts)
    for breadth in requested:
        insufficient = [
            (day, counts[day]) for day in ordered_days if counts[day] < breadth
        ]
        is_feasible = not insufficient
        if is_feasible:
            feasible.append(breadth)
        else:
            infeasible.append(breadth)
        rows.append(
            {
                "breadth": breadth,
                "status": (
                    "FULL_HORIZON_FEASIBLE"
                    if is_feasible
                    else "INFEASIBLE_FULL_HORIZON"
                ),
                "full_horizon_month_count": len(ordered_days),
                "minimum_eligible_symbol_count": min(counts.values()),
                "maximum_eligible_symbol_count": max(counts.values()),
                "insufficient_month_count": len(insufficient),
                "first_insufficient_month": (
                    insufficient[0][0] if insufficient else ""
                ),
                "first_insufficient_symbol_count": (
                    insufficient[0][1] if insufficient else ""
                ),
                "insufficient_months": "|".join(
                    f"{day}:{count}" for day, count in insufficient
                ),
                "months_dropped": 0,
                "breadth_shrunk_dynamically": False,
                "evaluation_allowed": is_feasible,
            }
        )
    if 10 not in feasible:
        raise ValueError(
            "V32_1_TOP10_NOT_FEASIBLE_FULL_HORIZON:"
            + json.dumps(rows, ensure_ascii=True, sort_keys=True)
        )
    return tuple(feasible), tuple(infeasible), rows


def _preflight(
    *,
    v31_artifact_zip: Path,
    v22_input_zip: Path,
    expected_v31_sha256: str | None,
    expected_input_sha256: str | None,
    requested_breadths: Sequence[int],
) -> tuple[tuple[int, ...], tuple[int, ...], list[dict[str, object]]]:
    _, predictions, _, _, _ = core._load_v31_artifact(
        v31_artifact_zip,
        expected_sha256=expected_v31_sha256,
        expected_input_sha256=expected_input_sha256,
    )
    eligible_keys, regime_by_day, _ = core._load_v22_policy_contract(
        v22_input_zip,
        expected_sha256=expected_input_sha256,
    )
    eligible_predictions, _ = core._eligible_primary_predictions(
        predictions,
        eligible_keys=eligible_keys,
        regime_by_day=regime_by_day,
    )
    return _breadth_feasibility(eligible_predictions, requested_breadths)


def run_v32_1(**kwargs: object) -> dict[str, object]:
    requested = v30._normalize_breadths(
        tuple(int(value) for value in kwargs.get("breadths", core.DEFAULT_BREADTHS))
    )
    feasible, infeasible, feasibility_rows = _preflight(
        v31_artifact_zip=Path(str(kwargs["v31_artifact_zip"])),
        v22_input_zip=Path(str(kwargs["v22_input_zip"])),
        expected_v31_sha256=(
            str(kwargs["expected_v31_sha256"])
            if kwargs.get("expected_v31_sha256")
            else None
        ),
        expected_input_sha256=(
            str(kwargs["expected_input_sha256"])
            if kwargs.get("expected_input_sha256")
            else None
        ),
        requested_breadths=requested,
    )

    adjusted = dict(kwargs)
    adjusted["breadths"] = feasible
    report = _ORIGINAL_RUN_V32(**adjusted)
    output_dir = Path(str(report["output_dir"])).resolve()

    core._write_csv(
        output_dir / FEASIBILITY_FILE,
        feasibility_rows,
        fields=(
            "breadth",
            "status",
            "full_horizon_month_count",
            "minimum_eligible_symbol_count",
            "maximum_eligible_symbol_count",
            "insufficient_month_count",
            "first_insufficient_month",
            "first_insufficient_symbol_count",
            "insufficient_months",
            "months_dropped",
            "breadth_shrunk_dynamically",
            "evaluation_allowed",
        ),
    )

    report.update(
        {
            "base_schema_version": core.SCHEMA_VERSION,
            "upgrade_schema_version": UPGRADE_SCHEMA_VERSION,
            "requested_breadths": list(requested),
            "evaluated_full_horizon_breadths": list(feasible),
            "infeasible_full_horizon_breadths": list(infeasible),
            "all_requested_breadths_evaluated": not infeasible,
            "breadth_feasibility_file": FEASIBILITY_FILE,
            "breadth_feasibility_rows": feasibility_rows,
            "breadth_feasibility_policy": (
                "SKIP_INFEASIBLE_FULL_HORIZON;DO_NOT_SHRINK_K;DO_NOT_DROP_MONTHS"
            ),
            "full_horizon_preserved": True,
            "months_dropped_for_breadth_feasibility": 0,
            "dynamic_breadth_used": False,
        }
    )
    core._write_json(output_dir / core.REPORT_FILE, report)
    return report


__all__ = [
    "UPGRADE_SCHEMA_VERSION",
    "FEASIBILITY_FILE",
    "_breadth_feasibility",
    "run_v32_1",
]
