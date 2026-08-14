"""Model Lab v14: continuous outer-test portfolio accounting.

V13 introduced nested chronological model/policy selection. V14 corrects the
outer-test execution accounting so holdings persist across adjacent outer
blocks. A model or replacement-cap switch therefore pays the actual turnover
from the portfolio selected in the preceding outer test period.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v13 as v13

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v14"
_BASE_NESTED = v13.nested_outer_test_evaluation
_BASE_RUN = v13.run_model_lab


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _dynamic_outer_periods(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    decisions: Mapping[str, Mapping[str, object]],
    top_k: int,
    cost: v13.DnseCashCostConfig,
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
        rows = sorted(
            by_model_day.get((model, day), ()),
            key=lambda row: (
                int(float(row.get("rank", 10**9) or 10**9)),
                str(row.get("symbol") or ""),
            ),
        )
        ranked = [str(row.get("symbol") or "") for row in rows]
        ranked = [symbol for symbol in ranked if symbol]
        if len(ranked) < top_k:
            raise ValueError(
                f"MODEL_LAB_V14_OUTER_INSUFFICIENT_SYMBOLS:{model}:{day}"
            )
        row_by_symbol = {
            str(row.get("symbol") or ""): row
            for row in rows
            if str(row.get("symbol") or "")
        }
        rank_by_symbol = {
            symbol: position for position, symbol in enumerate(ranked, start=1)
        }
        previous_available = [
            symbol for symbol in previous if symbol in row_by_symbol
        ]
        forced_exits = [
            symbol for symbol in previous if symbol not in row_by_symbol
        ]
        desired = ranked[:top_k]
        if index == 0:
            selected = desired
        else:
            minimum_retain = max(
                0,
                min(len(previous_available), top_k - cap),
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
                if len(selected) >= top_k:
                    break
            selected = selected[:top_k]

        overlap = len(set(previous) & set(selected)) if previous else 0
        turnover = 1.0 if index == 0 else 1.0 - overlap / top_k
        total_replacements = top_k if index == 0 else max(0, top_k - overlap)
        voluntary = (
            0
            if index == 0
            else max(0, total_replacements - len(forced_exits))
        )
        selected_rows = [row_by_symbol[symbol] for symbol in selected]
        gross_return = fmean(
            v13._float(row, "stock_return") for row in selected_rows
        )
        benchmark_return = v13._float(selected_rows[0], "benchmark_return")
        base_cost = (
            (cost.combined_buy_fee_bps + cost.slippage_bps) / 10_000.0
            if index == 0
            else turnover
            * (
                cost.combined_buy_fee_bps
                + cost.combined_sell_fee_bps
                + cost.sell_tax_bps
                + 2.0 * cost.slippage_bps
            )
            / 10_000.0
        )
        stress_cost = (
            (cost.combined_buy_fee_bps + cost.stress_slippage_bps) / 10_000.0
            if index == 0
            else turnover
            * (
                cost.combined_buy_fee_bps
                + cost.combined_sell_fee_bps
                + cost.sell_tax_bps
                + 2.0 * cost.stress_slippage_bps
            )
            / 10_000.0
        )
        base_net = gross_return - base_cost
        stress_net = gross_return - stress_cost
        base_nav *= 1.0 + base_net
        stress_nav *= 1.0 + stress_net
        benchmark_nav *= 1.0 + benchmark_return
        common = {
            "model": model,
            "strategy": "nested_model_and_turnover_cap_continuous",
            "outer_fold": decision["outer_fold"],
            "signal_date": day,
            "label_end": str(selected_rows[0].get("label_end") or ""),
            "selected_model": model,
            "selected_replacement_cap": cap,
            "top_k": top_k,
            "selected_symbols": "|".join(selected),
            "forced_exit_count": len(forced_exits),
            "voluntary_replacement_count": voluntary,
            "voluntary_replacement_cap_respected": str(
                voluntary <= cap
            ).lower(),
            "gross_return": gross_return,
            "benchmark_return": benchmark_return,
            "gross_excess_return": gross_return - benchmark_return,
            "turnover": turnover,
            "selection_uses_outer_test_labels": "false",
            "holdings_carried_across_outer_blocks": "true",
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


def nested_outer_test_evaluation(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    replacement_caps: Sequence[int] = v13.DEFAULT_REPLACEMENT_CAPS,
    candidate_models: Sequence[str] | None = None,
    validation_months: int = 6,
    test_months: int = 3,
    minimum_outer_test_periods: int = 12,
    cost: v13.DnseCashCostConfig | None = None,
) -> dict[str, object]:
    config = cost or v13.DnseCashCostConfig()
    base_result = _BASE_NESTED(
        prediction_rows,
        top_k=top_k,
        replacement_caps=replacement_caps,
        candidate_models=candidate_models,
        validation_months=validation_months,
        test_months=test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        cost=config,
    )
    selections = [dict(row) for row in base_result["selection_rows"]]
    dates = sorted({
        str(row.get("test_date") or "")
        for row in prediction_rows
        if str(row.get("test_date") or "")
    })
    decisions: dict[str, dict[str, object]] = {}
    for selection in selections:
        start = str(selection["test_start"])
        end = str(selection["test_end"])
        for day in dates:
            if start <= day <= end:
                decisions[day] = {
                    "outer_fold": selection["outer_fold"],
                    "selected_model": selection["selected_model"],
                    "selected_replacement_cap": selection[
                        "selected_replacement_cap"
                    ],
                }
    outer_rows, stress_rows = _dynamic_outer_periods(
        prediction_rows,
        decisions=decisions,
        top_k=top_k,
        cost=config,
    )
    base_metrics = v13.v12.v11.capped_policy_metrics(outer_rows)
    stress_metrics = v13.v12.v11.capped_policy_metrics(stress_rows)

    ic_values: list[float] = []
    for day, decision in sorted(decisions.items()):
        count, day_ic, _ = v13._rank_ic_for_model_dates(
            prediction_rows,
            model=str(decision["selected_model"]),
            dates=(day,),
        )
        if count:
            ic_values.append(day_ic)
    mean_ic = fmean(ic_values) if ic_values else 0.0
    positive_ic = (
        sum(value > 0.0 for value in ic_values) / len(ic_values)
        if ic_values else 0.0
    )
    gate = {
        "minimum_outer_test_periods": (
            int(base_metrics["period_count"]) >= minimum_outer_test_periods
        ),
        "mean_rank_ic_at_least_003": mean_ic >= 0.03,
        "positive_rank_ic_ratio_at_least_055": positive_ic >= 0.55,
        "base_average_net_excess_positive": (
            float(base_metrics["average_net_excess_return"]) > 0.0
        ),
        "base_positive_net_excess_ratio_at_least_half": (
            float(base_metrics["positive_net_excess_ratio"]) >= 0.50
        ),
        "base_relative_total_return_positive": (
            float(base_metrics["relative_total_return"]) > 0.0
        ),
        "base_turnover_at_most_half": (
            float(base_metrics["mean_turnover"]) <= 0.50
        ),
        "stress_relative_total_return_positive": (
            float(stress_metrics["relative_total_return"]) > 0.0
        ),
        "selection_uses_no_outer_test_labels": all(
            row["selection_uses_outer_test_labels"] == "false"
            for row in selections
        ),
        "continuous_holdings_across_outer_blocks": True,
    }
    passed = all(gate.values())
    status = (
        "HISTORICALLY_VALIDATED"
        if passed
        else "HISTORICAL_REFERENCE_CANDIDATE"
        if mean_ic > 0.0
        and float(base_metrics["relative_total_return"]) > 0.0
        else "REJECTED"
    )
    summary = dict(base_result["summary"])
    summary.update({
        "status": status,
        "outer_test_period_count": int(base_metrics["period_count"]),
        "rank_ic_period_count": len(ic_values),
        "mean_rank_ic": mean_ic,
        "positive_rank_ic_ratio": positive_ic,
        "base_metrics": base_metrics,
        "stress_metrics": stress_metrics,
        "gate": gate,
        "gate_passed": passed,
        "continuous_holdings_across_outer_blocks": True,
        "model_switch_turnover_charged": True,
        "cap_switch_turnover_charged": True,
    })
    return {
        "summary": summary,
        "selection_rows": selections,
        "outer_rows": outer_rows,
        "stress_outer_rows": stress_rows,
    }


def _publish_v14_contract(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    validation = dict(summary.get("nested_historical_validation_v13") or {})
    gate = dict(validation.get("gate") or {})
    contract = {
        "continuous_holdings_across_outer_blocks": bool(
            validation.get("continuous_holdings_across_outer_blocks", False)
        ),
        "model_switch_turnover_charged": bool(
            validation.get("model_switch_turnover_charged", False)
        ),
        "cap_switch_turnover_charged": bool(
            validation.get("cap_switch_turnover_charged", False)
        ),
        "initial_outer_portfolio_entry_cost_charged": True,
        "selection_uses_outer_test_labels": False,
        "historical_gate_passed": bool(validation.get("gate_passed", False)),
        "continuous_execution_gate": bool(
            gate.get("continuous_holdings_across_outer_blocks", False)
        ),
        "actionable": False,
    }
    _write_csv(
        output / "nested_outer_execution_contract_v14.csv",
        [contract],
        tuple(contract),
    )
    summary["base_upgrade_schema_version"] = v13.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["nested_outer_execution_contract_v14"] = contract
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output / "model_lab_report.txt").open("a", encoding="utf-8") as stream:
        stream.write("\nMODEL LAB UPGRADE V14\n")
        stream.write(
            "Outer-test holdings persist across blocks; model/cap switches "
            "pay actual transition turnover and the first outer portfolio "
            "pays entry cost.\n"
        )
    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "continuous_outer_execution_accounting": True,
        "historical_reference_status": summary.get(
            "historical_reference_status", "REJECTED"
        ),
        "historical_reference_gate_passed": bool(
            summary.get("historical_reference_gate_passed", False)
        ),
        "live_capital_approved": False,
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    original_nested = v13.nested_outer_test_evaluation
    v13.nested_outer_test_evaluation = nested_outer_test_evaluation
    try:
        result = _BASE_RUN(**kwargs)
    finally:
        v13.nested_outer_test_evaluation = original_nested
    contract = _publish_v14_contract(Path(str(kwargs["output_dir"])))
    return {**result, **contract}


def _parser():
    return v13._parser()


def main(argv: Sequence[str] | None = None) -> int:
    original_run = v13.run_model_lab
    v13.run_model_lab = run_model_lab
    try:
        return v13.main(argv)
    finally:
        v13.run_model_lab = original_run


__all__ = [
    "SCHEMA_VERSION",
    "nested_outer_test_evaluation",
    "run_model_lab",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
