"""Workstation runner for V30 with sparse-universe cash-slot compatibility.

The frozen V29 prediction archive contains a small number of historical months
with fewer symbols than the requested breadths 15, 20 and 30.  The legacy V11
portfolio helper intentionally fails when ``available_symbols < top_k``.  That
strict behaviour is useful for the original fixed-Top-K contract but should not
abort the whole V30 breadth diagnostic.

This runner reuses the audited V27 cash-slot implementation: every requested
portfolio slot keeps weight ``1 / top_k``; unavailable slots remain in cash.
Any breadth that used a cash slot fails the explicit
``fixed_breadth_fully_feasible`` gate.  The compatibility layer therefore keeps
all evidence visible without relaxing the V30 decision gate.

The runner also publishes a human-readable profit/loss description with the
exact OOS date range and number of evaluated months.  All results remain
post-selection diagnostics, non-actionable and ineligible for live capital.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import date
import json
from pathlib import Path
from statistics import fmean
from typing import Iterator, Mapping, Sequence

from . import component_breadth_ablation_v27_runner as v27_compat
from . import portfolio_ablation_v30 as core


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not Path(path).is_file():
        return []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _number(value: object, *, name: str) -> float:
    return core._finite(value, name=name)


@contextmanager
def _sparse_universe_compatibility() -> Iterator[None]:
    original_periods = core.v15.v13.v12.corrected_turnover_capped_periods
    original_dynamic = core.v15.v14._dynamic_outer_periods
    core.v15.v13.v12.corrected_turnover_capped_periods = (
        v27_compat._availability_capped_periods
    )
    core.v15.v14._dynamic_outer_periods = (
        v27_compat._availability_capped_dynamic_outer_periods
    )
    try:
        yield
    finally:
        core.v15.v13.v12.corrected_turnover_capped_periods = original_periods
        core.v15.v14._dynamic_outer_periods = original_dynamic


def _availability_summary(
    outer_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_breadth_day: dict[tuple[int, str], Mapping[str, object]] = {}
    for row in outer_rows:
        if str(row.get("model") or "") != core.CHALLENGER_MODEL:
            continue
        breadth = int(float(row.get("breadth", 0) or 0))
        day = str(row.get("signal_date") or "")
        if breadth <= 0 or not day:
            continue
        by_breadth_day[(breadth, day)] = row

    output: list[dict[str, object]] = []
    breadths = sorted({breadth for breadth, _ in by_breadth_day})
    for breadth in breadths:
        rows = [
            row
            for (row_breadth, _), row in sorted(by_breadth_day.items())
            if row_breadth == breadth
        ]
        capped = [
            row for row in rows if _truthy(row.get("availability_cap_applied"))
        ]
        output.append({
            "breadth": breadth,
            "outer_period_count_observed": len(rows),
            "availability_capped_outer_period_count": len(capped),
            "availability_capped_outer_period_ratio": (
                len(capped) / len(rows) if rows else 1.0
            ),
            "minimum_available_symbol_count": min(
                (int(float(row.get("available_symbol_count", 0) or 0)) for row in rows),
                default=0,
            ),
            "minimum_realized_selected_count": min(
                (int(float(row.get("realized_selected_count", 0) or 0)) for row in rows),
                default=0,
            ),
            "minimum_invested_fraction": min(
                (float(row.get("invested_fraction", 0.0) or 0.0) for row in rows),
                default=0.0,
            ),
            "fixed_breadth_fully_feasible": bool(rows) and not capped,
        })
    return output


def _month_span(first_day: str, last_day: str) -> int:
    first = date.fromisoformat(first_day)
    last = date.fromisoformat(last_day)
    return (last.year - first.year) * 12 + last.month - first.month + 1


def _performance_rows(
    portfolio_rows: Sequence[Mapping[str, object]],
    outer_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    periods: dict[tuple[int, str], list[Mapping[str, object]]] = {}
    for row in outer_rows:
        key = (
            int(float(row.get("breadth", 0) or 0)),
            str(row.get("model") or ""),
        )
        if key[0] > 0 and key[1]:
            periods.setdefault(key, []).append(row)

    output: list[dict[str, object]] = []
    for summary in portfolio_rows:
        breadth = int(float(summary.get("breadth", 0) or 0))
        model = str(summary.get("model") or "")
        model_periods = sorted(
            periods.get((breadth, model), []),
            key=lambda row: str(row.get("signal_date") or ""),
        )
        if not model_periods:
            continue
        first_day = str(model_periods[0].get("signal_date") or "")
        last_day = str(model_periods[-1].get("signal_date") or "")
        observed = len(model_periods)
        calendar_months = _month_span(first_day, last_day)
        net_total = _number(
            summary.get("base_net_total_return"),
            name="base_net_total_return",
        )
        benchmark_total = _number(
            summary.get("base_benchmark_total_return"),
            name="base_benchmark_total_return",
        )
        relative_total = _number(
            summary.get("base_relative_total_return"),
            name="base_relative_total_return",
        )
        stress_net_total = _number(
            summary.get("stress_net_total_return"),
            name="stress_net_total_return",
        )
        stress_relative_total = _number(
            summary.get("stress_relative_total_return"),
            name="stress_relative_total_return",
        )
        average_monthly_net = fmean(
            _number(row.get("net_return"), name="net_return")
            for row in model_periods
        )
        average_monthly_excess = fmean(
            _number(row.get("net_excess_return"), name="net_excess_return")
            for row in model_periods
        )
        if net_total > 1e-12:
            profit_loss_status = "PROFIT"
            verb = "Lãi"
        elif net_total < -1e-12:
            profit_loss_status = "LOSS"
            verb = "Lỗ"
        else:
            profit_loss_status = "FLAT"
            verb = "Hòa vốn"
        description = (
            f"{verb} {abs(net_total):.2%} sau chi phí cơ sở trong "
            f"{observed} tháng OOS ({first_day} đến {last_day}); "
            f"VNINDEX {benchmark_total:.2%}; tỷ suất tương đối "
            f"{relative_total:+.2%}; stress {stress_net_total:+.2%}."
        )
        output.append({
            "model": model,
            "breadth": breadth,
            "first_outer_test_date": first_day,
            "last_outer_test_date": last_day,
            "observed_outer_months": observed,
            "calendar_month_span": calendar_months,
            "approximate_years": observed / 12.0,
            "profit_loss_status": profit_loss_status,
            "base_net_total_return": net_total,
            "base_benchmark_total_return": benchmark_total,
            "base_relative_total_return": relative_total,
            "base_average_monthly_net_return": average_monthly_net,
            "base_average_monthly_net_excess_return": average_monthly_excess,
            "stress_net_total_return": stress_net_total,
            "stress_relative_total_return": stress_relative_total,
            "performance_description_vi": description,
            "independent_holdout": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "actionable": False,
        })
    return sorted(output, key=lambda row: (int(row["breadth"]), str(row["model"])))


def _recompute_recommendation(
    decisions: Sequence[Mapping[str, object]],
    configured_breadths: Sequence[int],
) -> tuple[str, list[int], list[tuple[int, int]]]:
    passing = sorted(
        int(float(row.get("breadth", 0) or 0))
        for row in decisions
        if _truthy(row.get("v30_portfolio_gate_passed"))
    )
    passing_set = set(passing)
    configured = sorted(set(int(value) for value in configured_breadths))
    adjacent = [
        (left, right)
        for left, right in zip(configured, configured[1:])
        if left in passing_set and right in passing_set
    ]
    if adjacent:
        recommendation = "FREEZE_V29_LOGIT_POLICY_FOR_FUTURE_HOLDOUT"
    elif passing:
        recommendation = "KEEP_SINGLE_V30_POLICY_AS_PAPER_DIAGNOSTIC_ONLY"
    else:
        recommendation = "KEEP_V29_MODEL_REDESIGN_PORTFOLIO_POLICY"
    return recommendation, passing, adjacent


def _postprocess(
    output_dir: Path,
    result: Mapping[str, object],
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    report_path = destination / core.REPORT_FILE
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))

    outer_rows = _read_csv(destination / "outer_test_periods_v30.csv")
    portfolio_rows = _read_csv(destination / "portfolio_comparison_v30.csv")
    decision_rows = _read_csv(destination / "decision_gates_v30.csv")
    availability_rows = _availability_summary(outer_rows)
    availability_by_breadth = {
        int(row["breadth"]): row for row in availability_rows
    }

    for row in portfolio_rows:
        breadth = int(float(row.get("breadth", 0) or 0))
        summary = availability_by_breadth.get(breadth, {})
        for key, value in summary.items():
            if key != "breadth":
                row[key] = value
    core._write_csv(destination / "portfolio_comparison_v30.csv", portfolio_rows)
    core._write_csv(destination / "breadth_availability_v30.csv", availability_rows)

    for row in decision_rows:
        breadth = int(float(row.get("breadth", 0) or 0))
        summary = availability_by_breadth.get(breadth, {})
        feasible = bool(summary.get("fixed_breadth_fully_feasible", False))
        failed = [
            item
            for item in str(row.get("failed_v30_gates") or "").split("|")
            if item
        ]
        if not feasible and "fixed_breadth_fully_feasible" not in failed:
            failed.append("fixed_breadth_fully_feasible")
        row.update({
            "fixed_breadth_fully_feasible": feasible,
            "availability_capped_outer_period_count": summary.get(
                "availability_capped_outer_period_count", 0
            ),
            "outer_period_count_observed": summary.get(
                "outer_period_count_observed", 0
            ),
            "minimum_available_symbol_count": summary.get(
                "minimum_available_symbol_count", 0
            ),
            "minimum_invested_fraction": summary.get(
                "minimum_invested_fraction", 0.0
            ),
            "v30_portfolio_gate_passed": (
                _truthy(row.get("v30_portfolio_gate_passed")) and feasible
            ),
            "failed_v30_gates": "|".join(failed),
        })
    core._write_csv(destination / "decision_gates_v30.csv", decision_rows)

    performance_rows = _performance_rows(portfolio_rows, outer_rows)
    core._write_csv(destination / "performance_status_v30.csv", performance_rows)

    typed_decisions = list(report.get("decision_rows", []))
    for row in typed_decisions:
        breadth = int(row.get("breadth", 0) or 0)
        summary = availability_by_breadth.get(breadth, {})
        feasible = bool(summary.get("fixed_breadth_fully_feasible", False))
        failed = [
            item
            for item in str(row.get("failed_v30_gates") or "").split("|")
            if item
        ]
        if not feasible and "fixed_breadth_fully_feasible" not in failed:
            failed.append("fixed_breadth_fully_feasible")
        row.update({
            "fixed_breadth_fully_feasible": feasible,
            "availability_capped_outer_period_count": int(
                summary.get("availability_capped_outer_period_count", 0)
            ),
            "outer_period_count_observed": int(
                summary.get("outer_period_count_observed", 0)
            ),
            "minimum_available_symbol_count": int(
                summary.get("minimum_available_symbol_count", 0)
            ),
            "minimum_invested_fraction": float(
                summary.get("minimum_invested_fraction", 0.0)
            ),
            "v30_portfolio_gate_passed": bool(
                row.get("v30_portfolio_gate_passed")
            ) and feasible,
            "failed_v30_gates": "|".join(failed),
        })

    recommendation, passing, adjacent = _recompute_recommendation(
        typed_decisions,
        report.get("breadths", []),
    )
    report["decision_rows"] = typed_decisions
    report["availability_cash_slot_compatibility_applied"] = True
    report["breadth_execution_contract"] = (
        "REQUESTED_TOP_K_WITH_UNAVAILABLE_SLOTS_HELD_AS_CASH"
    )
    report["breadth_availability_summary"] = availability_rows
    report["fixed_breadth_gate_relaxed"] = False
    report["research_gate_relaxed"] = False
    report["performance_status_rows"] = performance_rows
    report["performance_status_contract"] = (
        "ALWAYS_REPORT_PROFIT_OR_LOSS_WITH_OOS_MONTH_COUNT_AND_DATE_RANGE"
    )
    report["passing_breadths"] = passing
    report["adjacent_passing_breadth_pairs"] = [list(pair) for pair in adjacent]
    report["recommendation"] = recommendation
    report["policy_freeze_is_for_future_holdout_only"] = (
        recommendation == "FREEZE_V29_LOGIT_POLICY_FOR_FUTURE_HOLDOUT"
    )
    report["live_capital_approved"] = False
    report["automatic_live_orders_allowed"] = False
    report["actionable"] = False

    portfolio_results = dict(report.get("portfolio_results") or {})
    for breadth, summary in availability_by_breadth.items():
        detail = dict(portfolio_results.get(str(breadth)) or {})
        detail["availability_summary"] = summary
        portfolio_results[str(breadth)] = detail
    report["portfolio_results"] = portfolio_results

    core._write_json(report_path, report)
    return {**report, "output_dir": str(destination)}


def run_v30_compatible(**kwargs: object) -> dict[str, object]:
    output_dir = Path(str(kwargs["output_dir"]))
    with _sparse_universe_compatibility():
        result = core.run_v30(**kwargs)
    return _postprocess(output_dir, result)


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    try:
        result = run_v30_compatible(
            v29_artifact_zip=args.v29_artifact_zip,
            model_output=args.model_output,
            output_dir=args.output_dir,
            expected_v29_sha256=args.expected_v29_sha256,
            expected_input_sha256=args.expected_input_sha256,
            breadths=args.breadths,
            replacement_caps=args.replacement_caps,
            validation_months=args.validation_months,
            test_months=args.test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_months=args.bootstrap_block_months,
            seed=args.seed,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result["status"],
        "output_dir": result["output_dir"],
        "passing_breadths": result["passing_breadths"],
        "recommendation": result["recommendation"],
        "performance_status": [
            row["performance_description_vi"]
            for row in result.get("performance_status_rows", [])
        ],
        "availability_cash_slot_compatibility_applied": True,
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "run_v30_compatible",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
