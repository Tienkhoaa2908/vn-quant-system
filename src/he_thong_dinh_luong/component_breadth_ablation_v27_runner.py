"""Workstation entrypoint for V27 with strict V22 compatibility.

V22 serializes ``vnindex_tren_ma250`` as ``true``/``false``.  In addition,
some historical monthly universes contain fewer eligible symbols than a
requested Top-K breadth.  The original V11/V14 portfolio helpers fail the whole
run in that situation.  This runner keeps the requested number of portfolio
slots fixed, invests one ``1 / top_k`` slot in each available selected symbol,
and leaves unavailable slots in cash.

Availability-capped results remain diagnostic.  A breadth with any capped
outer-test period fails the V27 ``fixed_breadth_fully_feasible`` decision gate.
No research-quality, live-capital or automatic-order approval is granted.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
from pathlib import Path
from statistics import fmean
from typing import Iterator, Mapping, Sequence
import json

from . import component_breadth_ablation_v27 as base
from .model_lab_core import ENSEMBLE_MODEL


def _finite_with_v22_boolean(value: object, *, name: str) -> float:
    if name != "vnindex_tren_ma250":
        return base._ORIGINAL_V27_FINITE(value, name=name)  # type: ignore[attr-defined]
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return 1.0
    if text in {"0", "false", "no", "n"}:
        return 0.0
    raise ValueError(f"V27_INVALID_BOOLEAN:{name}:{text}")


def _float(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value in (None, ""):
        return default
    return float(value)


def _ranked_symbols(
    rows: Sequence[Mapping[str, object]],
) -> tuple[list[str], dict[str, Mapping[str, object]]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            int(float(row.get("rank", 10**9) or 10**9)),
            str(row.get("symbol") or ""),
        ),
    )
    ranked: list[str] = []
    row_by_symbol: dict[str, Mapping[str, object]] = {}
    for row in ordered:
        symbol = str(row.get("symbol") or "")
        if not symbol or symbol in row_by_symbol:
            continue
        ranked.append(symbol)
        row_by_symbol[symbol] = row
    return ranked, row_by_symbol


def _select_with_cash_slots(
    ranked: Sequence[str],
    previous: Sequence[str],
    *,
    top_k: int,
    replacement_cap: int,
    initial: bool,
) -> dict[str, object]:
    target_count = min(top_k, len(ranked))
    current = set(ranked)
    previous_available = [symbol for symbol in previous if symbol in current]
    forced_exits = [symbol for symbol in previous if symbol not in current]
    rank_by_symbol = {
        symbol: position for position, symbol in enumerate(ranked, start=1)
    }
    desired = list(ranked[:target_count])

    if initial:
        selected = desired
    else:
        minimum_retain = max(
            0,
            min(
                len(previous_available),
                target_count - replacement_cap,
            ),
        )
        retained = [
            symbol for symbol in desired if symbol in previous_available
        ]
        if len(retained) < minimum_retain:
            for symbol in sorted(
                previous_available,
                key=lambda item: (rank_by_symbol[item], item),
            ):
                if symbol not in retained:
                    retained.append(symbol)
                if len(retained) >= minimum_retain:
                    break
        selected = list(retained)
        for symbol in ranked:
            if symbol not in selected:
                selected.append(symbol)
            if len(selected) >= target_count:
                break
        selected = selected[:target_count]

    previous_set = set(previous)
    selected_set = set(selected)
    entries = [symbol for symbol in selected if symbol not in previous_set]
    exits = [symbol for symbol in previous if symbol not in selected_set]
    voluntary = (
        0
        if initial
        else max(0, len(entries) - len(forced_exits))
    )
    turnover = (
        len(entries) / top_k
        if initial
        else (len(entries) + len(exits)) / (2.0 * top_k)
    )
    return {
        "selected": selected,
        "entries": entries,
        "exits": exits,
        "forced_exits": forced_exits,
        "voluntary_replacements": voluntary,
        "turnover": turnover,
        "available_symbol_count": len(ranked),
        "realized_selected_count": len(selected),
        "cash_slot_count": top_k - len(selected),
        "invested_fraction": len(selected) / top_k,
        "availability_cap_applied": len(selected) < top_k,
        "minimum_retained_when_available": max(
            0,
            target_count - replacement_cap,
        ),
    }


def _transaction_cost_rate(
    *,
    entry_count: int,
    exit_count: int,
    top_k: int,
    buy_fee_bps: float,
    sell_fee_bps: float,
    sell_tax_bps: float,
    slippage_bps: float,
) -> float:
    buy_rate = (buy_fee_bps + slippage_bps) / 10_000.0
    sell_rate = (
        sell_fee_bps + sell_tax_bps + slippage_bps
    ) / 10_000.0
    return (
        entry_count / top_k * buy_rate
        + exit_count / top_k * sell_rate
    )


def _availability_capped_periods(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    max_voluntary_replacements: int = 3,
    buy_fee_bps: float,
    sell_fee_bps: float,
    sell_tax_bps: float,
    slippage_bps: float,
) -> list[dict[str, object]]:
    if top_k <= 0:
        raise ValueError("V27_TOP_K_MUST_BE_POSITIVE")
    if not 0 <= max_voluntary_replacements <= top_k:
        raise ValueError("V27_REPLACEMENT_CAP_OUT_OF_RANGE")

    by_day: dict[str, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if str(row.get("model") or "") != ENSEMBLE_MODEL:
            continue
        day = str(row.get("test_date") or "")
        if day:
            by_day.setdefault(day, []).append(row)

    previous: list[str] = []
    nav = 1.0
    benchmark_nav = 1.0
    output: list[dict[str, object]] = []
    for index, day in enumerate(sorted(by_day)):
        ranked, row_by_symbol = _ranked_symbols(by_day[day])
        if not ranked:
            raise ValueError(f"V27_NO_ELIGIBLE_SYMBOLS:{day}")
        selection = _select_with_cash_slots(
            ranked,
            previous,
            top_k=top_k,
            replacement_cap=max_voluntary_replacements,
            initial=index == 0,
        )
        selected = list(selection["selected"])
        selected_rows = [row_by_symbol[symbol] for symbol in selected]
        gross_return = sum(
            _float(row, "stock_return") for row in selected_rows
        ) / top_k
        benchmark_return = _float(by_day[day][0], "benchmark_return")
        estimated_cost_rate = _transaction_cost_rate(
            entry_count=len(selection["entries"]),
            exit_count=len(selection["exits"]),
            top_k=top_k,
            buy_fee_bps=buy_fee_bps,
            sell_fee_bps=sell_fee_bps,
            sell_tax_bps=sell_tax_bps,
            slippage_bps=slippage_bps,
        )
        net_return = gross_return - estimated_cost_rate
        nav *= 1.0 + net_return
        benchmark_nav *= 1.0 + benchmark_return
        output.append({
            "model": ENSEMBLE_MODEL,
            "strategy": "requested_top_k_with_unavailable_slots_in_cash",
            "signal_date": day,
            "label_end": str(by_day[day][0].get("label_end") or ""),
            "top_k": top_k,
            "requested_top_k": top_k,
            "max_voluntary_replacements": max_voluntary_replacements,
            "minimum_retained_when_available": selection[
                "minimum_retained_when_available"
            ],
            "selected_symbols": "|".join(selected),
            "available_symbol_count": selection["available_symbol_count"],
            "realized_selected_count": selection["realized_selected_count"],
            "cash_slot_count": selection["cash_slot_count"],
            "invested_fraction": selection["invested_fraction"],
            "availability_cap_applied": str(
                selection["availability_cap_applied"]
            ).lower(),
            "forced_exit_count": len(selection["forced_exits"]),
            "voluntary_replacement_count": selection[
                "voluntary_replacements"
            ],
            "voluntary_replacement_cap_respected": str(
                int(selection["voluntary_replacements"])
                <= max_voluntary_replacements
            ).lower(),
            "gross_return": gross_return,
            "benchmark_return": benchmark_return,
            "gross_excess_return": gross_return - benchmark_return,
            "turnover": selection["turnover"],
            "estimated_cost_rate": estimated_cost_rate,
            "net_return": net_return,
            "net_excess_return": net_return - benchmark_return,
            "net_nav": nav,
            "benchmark_nav": benchmark_nav,
            "relative_nav": nav / benchmark_nav,
            "selection_uses_realized_returns": "false",
            "policy_provenance": "V27_AVAILABILITY_CASH_SLOT_HOTFIX",
            "future_holdout_required": "true",
            "actionable": "false",
        })
        previous = selected
    return output


def _availability_capped_dynamic_outer_periods(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    decisions: Mapping[str, Mapping[str, object]],
    top_k: int,
    cost: object,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_model_day: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        model = str(row.get("model") or "")
        day = str(row.get("test_date") or "")
        if model and day in decisions:
            by_model_day.setdefault((model, day), []).append(row)

    previous: list[str] = []
    base_rows: list[dict[str, object]] = []
    stress_rows: list[dict[str, object]] = []
    base_nav = 1.0
    stress_nav = 1.0
    benchmark_nav = 1.0

    for index, day in enumerate(sorted(decisions)):
        decision = decisions[day]
        model = str(decision["selected_model"])
        cap = int(decision["selected_replacement_cap"])
        ranked, row_by_symbol = _ranked_symbols(
            by_model_day.get((model, day), ())
        )
        if not ranked:
            raise ValueError(
                f"V27_OUTER_NO_ELIGIBLE_SYMBOLS:{model}:{day}"
            )
        selection = _select_with_cash_slots(
            ranked,
            previous,
            top_k=top_k,
            replacement_cap=cap,
            initial=index == 0,
        )
        selected = list(selection["selected"])
        selected_rows = [row_by_symbol[symbol] for symbol in selected]
        gross_return = sum(
            _float(row, "stock_return") for row in selected_rows
        ) / top_k
        benchmark_return = _float(
            by_model_day[(model, day)][0],
            "benchmark_return",
        )
        base_cost = _transaction_cost_rate(
            entry_count=len(selection["entries"]),
            exit_count=len(selection["exits"]),
            top_k=top_k,
            buy_fee_bps=float(cost.combined_buy_fee_bps),
            sell_fee_bps=float(cost.combined_sell_fee_bps),
            sell_tax_bps=float(cost.sell_tax_bps),
            slippage_bps=float(cost.slippage_bps),
        )
        stress_cost = _transaction_cost_rate(
            entry_count=len(selection["entries"]),
            exit_count=len(selection["exits"]),
            top_k=top_k,
            buy_fee_bps=float(cost.combined_buy_fee_bps),
            sell_fee_bps=float(cost.combined_sell_fee_bps),
            sell_tax_bps=float(cost.sell_tax_bps),
            slippage_bps=float(cost.stress_slippage_bps),
        )
        base_net = gross_return - base_cost
        stress_net = gross_return - stress_cost
        base_nav *= 1.0 + base_net
        stress_nav *= 1.0 + stress_net
        benchmark_nav *= 1.0 + benchmark_return
        common = {
            "model": model,
            "strategy": "requested_top_k_with_unavailable_slots_in_cash",
            "outer_fold": decision["outer_fold"],
            "signal_date": day,
            "label_end": str(
                by_model_day[(model, day)][0].get("label_end") or ""
            ),
            "selected_model": model,
            "selected_replacement_cap": cap,
            "top_k": top_k,
            "requested_top_k": top_k,
            "selected_symbols": "|".join(selected),
            "available_symbol_count": selection["available_symbol_count"],
            "realized_selected_count": selection["realized_selected_count"],
            "cash_slot_count": selection["cash_slot_count"],
            "invested_fraction": selection["invested_fraction"],
            "availability_cap_applied": str(
                selection["availability_cap_applied"]
            ).lower(),
            "forced_exit_count": len(selection["forced_exits"]),
            "voluntary_replacement_count": selection[
                "voluntary_replacements"
            ],
            "voluntary_replacement_cap_respected": str(
                int(selection["voluntary_replacements"]) <= cap
            ).lower(),
            "gross_return": gross_return,
            "benchmark_return": benchmark_return,
            "gross_excess_return": gross_return - benchmark_return,
            "turnover": selection["turnover"],
            "selection_uses_outer_test_labels": "false",
            "holdings_carried_across_outer_blocks": "true",
            "availability_cash_slot_contract": "true",
            "actionable": "false",
        }
        base_rows.append({
            **common,
            "cost_scenario": "BASE",
            "estimated_cost_rate": base_cost,
            "net_return": base_net,
            "net_excess_return": base_net - benchmark_return,
            "net_nav": base_nav,
            "benchmark_nav": benchmark_nav,
            "relative_nav": base_nav / benchmark_nav,
        })
        stress_rows.append({
            **common,
            "cost_scenario": "STRESS",
            "estimated_cost_rate": stress_cost,
            "net_return": stress_net,
            "net_excess_return": stress_net - benchmark_return,
            "net_nav": stress_nav,
            "benchmark_nav": benchmark_nav,
            "relative_nav": stress_nav / benchmark_nav,
        })
        previous = selected
    return base_rows, stress_rows


@contextmanager
def _compatibility_patches() -> Iterator[None]:
    original_finite = base._finite
    original_periods = base.v15.v13.v12.corrected_turnover_capped_periods
    original_dynamic = base.v15.v14._dynamic_outer_periods
    base._ORIGINAL_V27_FINITE = original_finite  # type: ignore[attr-defined]
    base._finite = _finite_with_v22_boolean
    base.v15.v13.v12.corrected_turnover_capped_periods = (
        _availability_capped_periods
    )
    base.v15.v14._dynamic_outer_periods = (
        _availability_capped_dynamic_outer_periods
    )
    try:
        yield
    finally:
        base._finite = original_finite
        base.v15.v13.v12.corrected_turnover_capped_periods = original_periods
        base.v15.v14._dynamic_outer_periods = original_dynamic
        try:
            delattr(base, "_ORIGINAL_V27_FINITE")
        except AttributeError:
            pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _availability_postprocess(
    output_dir: Path,
    result: Mapping[str, object],
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    report_path = destination / base.REPORT_FILE
    if not report_path.is_file():
        return dict(result)

    outer_rows = _read_csv(destination / "outer_test_periods_v27.csv")
    by_breadth_day: dict[tuple[int, str], dict[str, object]] = {}
    for row in outer_rows:
        breadth = int(float(row.get("breadth") or 0))
        day = str(row.get("signal_date") or "")
        if breadth <= 0 or not day:
            continue
        key = (breadth, day)
        by_breadth_day[key] = {
            "breadth": breadth,
            "signal_date": day,
            "available_symbol_count": int(float(
                row.get("available_symbol_count") or 0
            )),
            "requested_top_k": int(float(
                row.get("requested_top_k") or breadth
            )),
            "realized_selected_count": int(float(
                row.get("realized_selected_count") or 0
            )),
            "cash_slot_count": int(float(
                row.get("cash_slot_count") or 0
            )),
            "invested_fraction": float(
                row.get("invested_fraction") or 0.0
            ),
            "availability_cap_applied": _truthy(
                row.get("availability_cap_applied")
            ),
        }
    availability_rows = [
        by_breadth_day[key] for key in sorted(by_breadth_day)
    ]
    base._write_csv(
        destination / "breadth_availability_v27.csv",
        availability_rows,
    )

    summaries: dict[int, dict[str, object]] = {}
    for breadth in sorted({int(row["breadth"]) for row in availability_rows}):
        rows = [
            row for row in availability_rows
            if int(row["breadth"]) == breadth
        ]
        capped = [
            row for row in rows if bool(row["availability_cap_applied"])
        ]
        summaries[breadth] = {
            "breadth": breadth,
            "outer_period_count_observed": len(rows),
            "availability_capped_outer_period_count": len(capped),
            "availability_capped_outer_period_ratio": (
                len(capped) / len(rows) if rows else 1.0
            ),
            "minimum_available_symbol_count": (
                min(int(row["available_symbol_count"]) for row in rows)
                if rows else 0
            ),
            "minimum_realized_selected_count": (
                min(int(row["realized_selected_count"]) for row in rows)
                if rows else 0
            ),
            "minimum_invested_fraction": (
                min(float(row["invested_fraction"]) for row in rows)
                if rows else 0.0
            ),
            "fixed_breadth_fully_feasible": bool(rows) and not capped,
        }

    portfolio_rows = _read_csv(destination / "portfolio_comparison_v27.csv")
    for row in portfolio_rows:
        breadth = int(float(row.get("breadth") or 0))
        summary = summaries.get(breadth, {})
        for key, value in summary.items():
            if key != "breadth":
                row[key] = value
    if portfolio_rows:
        base._write_csv(
            destination / "portfolio_comparison_v27.csv",
            portfolio_rows,
        )

    decision_rows = _read_csv(destination / "decision_gates_v27.csv")
    for row in decision_rows:
        breadth = int(float(row.get("breadth") or 0))
        summary = summaries.get(breadth, {})
        feasible = bool(summary.get("fixed_breadth_fully_feasible", False))
        previous_pass = _truthy(row.get("v27_decision_gate_passed"))
        failed = [
            item for item in str(
                row.get("failed_v27_decision_gates") or ""
            ).split("|") if item
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
            "v27_decision_gate_passed": previous_pass and feasible,
            "failed_v27_decision_gates": "|".join(failed),
        })
    if decision_rows:
        base._write_csv(
            destination / "decision_gates_v27.csv",
            decision_rows,
        )

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    report["availability_cash_slot_hotfix_applied"] = True
    report["breadth_execution_contract"] = (
        "REQUESTED_TOP_K_WITH_UNAVAILABLE_SLOTS_HELD_AS_CASH"
    )
    report["breadth_availability_summary"] = [
        summaries[key] for key in sorted(summaries)
    ]
    report["fixed_breadth_gate_relaxed"] = False
    report["research_gate_relaxed"] = False

    typed_decisions = list(report.get("decision_gate_rows", []))
    for row in typed_decisions:
        breadth = int(row.get("breadth", 0) or 0)
        summary = summaries.get(breadth, {})
        feasible = bool(summary.get("fixed_breadth_fully_feasible", False))
        failed = [
            item for item in str(
                row.get("failed_v27_decision_gates") or ""
            ).split("|") if item
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
            "v27_decision_gate_passed": bool(
                row.get("v27_decision_gate_passed")
            ) and feasible,
            "failed_v27_decision_gates": "|".join(failed),
        })
    report["decision_gate_rows"] = typed_decisions

    portfolio_results = dict(report.get("portfolio_results") or {})
    for breadth, summary in summaries.items():
        detail = dict(portfolio_results.get(str(breadth)) or {})
        detail["availability_summary"] = summary
        portfolio_results[str(breadth)] = detail
    report["portfolio_results"] = portfolio_results

    any_decision_passed = any(
        bool(row.get("v27_decision_gate_passed"))
        for row in typed_decisions
    )
    signal_rows = list(
        dict(report.get("factor_diagnostics") or {}).get(
            "signal_gate_rows", []
        )
    )
    any_signal_passed = any(
        bool(row.get("signal_gate_passed")) for row in signal_rows
    )
    report["recommendation"] = (
        "RUN_V28_FULL_WALK_FORWARD"
        if any_decision_passed
        else "KEEP_SCORE_OPTIMIZE_PORTFOLIO"
        if any_signal_passed
        else "REDESIGN_TARGET_AND_FEATURES"
    )
    report["requires_confirmation_before_v28"] = True
    report["live_capital_approved"] = False
    report["automatic_live_orders_allowed"] = False
    base._write_json(report_path, report)
    return {**report, "output_dir": str(destination)}


def run_v27_compatible(*args, **kwargs):
    output_dir = Path(args[2] if len(args) >= 3 else kwargs["output_dir"])
    with _compatibility_patches():
        result = base.run_v27(*args, **kwargs)
    return _availability_postprocess(output_dir, result)


def main(argv: Sequence[str] | None = None) -> int:
    args = base._parser().parse_args(argv)
    try:
        result = run_v27_compatible(
            args.input_zip,
            args.model_output,
            args.output_dir,
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            nested_validation_months=args.nested_validation_months,
            nested_test_months=args.nested_test_months,
            minimum_outer_test_periods=args.minimum_outer_test_periods,
            breadths=args.breadths,
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
        "report": str(Path(result["output_dir"]) / base.REPORT_FILE),
        "walk_forward_fold_count": result["walk_forward_fold_count"],
        "recommendation": result["recommendation"],
        "availability_cash_slot_hotfix_applied": True,
        "v22_boolean_compatibility_applied": True,
        "requires_confirmation_before_v28": True,
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "_availability_capped_periods",
    "_availability_capped_dynamic_outer_periods",
    "run_v27_compatible",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
