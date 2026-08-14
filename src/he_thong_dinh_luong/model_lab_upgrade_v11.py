"""Model Lab v11: turnover-capped ensemble reference candidate.

The v10 workstation artifact showed that the fixed positive tree blend restored
broad predictive value and approximately matched the benchmark, but monthly
turnover remained too high.  V11 adds one deliberately simple, stateful
portfolio policy for research diagnostics:

* rank with the unchanged v10 ensemble score;
* retain at least seven of ten prior holdings when they remain available;
* make at most three voluntary replacements per rebalance;
* never use the current period's realised return for selection;
* keep the policy non-actionable because the replacement cap was selected after
  reviewing the 2026-07-30 OOS artifact.

The underlying model scores, leaderboard and forward watchlist remain unchanged.
"""
from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v9 as v9
from . import model_lab_upgrade_v10 as v10
from .model_lab_core import ENSEMBLE_MODEL

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v11"
TURNOVER_CAP_POLICY_FREEZE_DATE = "2026-08-01"
MINIMUM_FUTURE_TURNOVER_CAP_FOLDS = 12
MAX_VOLUNTARY_REPLACEMENTS = 3


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fields),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _float(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value in (None, ""):
        return default
    return float(value)


def turnover_capped_periods(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    max_voluntary_replacements: int = MAX_VOLUNTARY_REPLACEMENTS,
    buy_fee_bps: float,
    sell_fee_bps: float,
    sell_tax_bps: float,
    slippage_bps: float,
) -> list[dict[str, object]]:
    """Replay a deterministic turnover-capped Top-K policy.

    Selection only uses current ensemble ranks and the previous selected set.
    A holding that disappears from the current eligible universe is a forced
    exit and does not consume the voluntary replacement budget.
    """
    if top_k <= 0:
        raise ValueError("MODEL_LAB_V11_TOP_K_MUST_BE_POSITIVE")
    if not 0 <= max_voluntary_replacements <= top_k:
        raise ValueError("MODEL_LAB_V11_REPLACEMENT_CAP_OUT_OF_RANGE")

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
    entry_cost = (buy_fee_bps + slippage_bps) / 10_000.0
    replacement_cost = (
        buy_fee_bps
        + sell_fee_bps
        + sell_tax_bps
        + 2.0 * slippage_bps
    ) / 10_000.0

    for index, day in enumerate(sorted(by_day)):
        rows = sorted(
            by_day[day],
            key=lambda row: (
                int(float(row.get("rank", 10**9) or 10**9)),
                str(row.get("symbol") or ""),
            ),
        )
        ranked = [str(row.get("symbol") or "") for row in rows]
        ranked = [symbol for symbol in ranked if symbol]
        if len(ranked) < top_k:
            raise ValueError("MODEL_LAB_V11_INSUFFICIENT_ELIGIBLE_SYMBOLS")
        row_by_symbol = {
            str(row.get("symbol") or ""): row
            for row in rows
            if str(row.get("symbol") or "")
        }
        rank_by_symbol = {
            symbol: position
            for position, symbol in enumerate(ranked, start=1)
        }

        forced_exits = [symbol for symbol in previous if symbol not in row_by_symbol]
        previous_available = [
            symbol for symbol in previous if symbol in row_by_symbol
        ]
        desired = ranked[:top_k]
        if index == 0:
            selected = desired
            voluntary_replacements = top_k
        else:
            minimum_retain = max(
                0,
                min(
                    len(previous_available),
                    top_k - max_voluntary_replacements,
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
                if len(selected) >= top_k:
                    break
            selected = selected[:top_k]
            voluntary_replacements = len(
                [
                    symbol for symbol in selected
                    if symbol not in previous_available
                ]
            )

        overlap = len(set(previous) & set(selected)) if previous else 0
        turnover = 1.0 if index == 0 else 1.0 - overlap / top_k
        estimated_cost_rate = (
            entry_cost if index == 0 else turnover * replacement_cost
        )
        selected_rows = [row_by_symbol[symbol] for symbol in selected]
        gross_return = fmean(
            _float(row, "stock_return") for row in selected_rows
        )
        benchmark_return = _float(selected_rows[0], "benchmark_return")
        net_return = gross_return - estimated_cost_rate
        net_excess = net_return - benchmark_return
        nav *= 1.0 + net_return
        benchmark_nav *= 1.0 + benchmark_return

        output.append({
            "model": ENSEMBLE_MODEL,
            "strategy": "posthoc_turnover_capped_top_k_candidate",
            "signal_date": day,
            "label_end": str(selected_rows[0].get("label_end") or ""),
            "top_k": top_k,
            "max_voluntary_replacements": max_voluntary_replacements,
            "minimum_retained_when_available": (
                top_k - max_voluntary_replacements
            ),
            "selected_symbols": "|".join(selected),
            "forced_exit_count": len(forced_exits),
            "voluntary_replacement_count": voluntary_replacements,
            "gross_return": gross_return,
            "benchmark_return": benchmark_return,
            "gross_excess_return": gross_return - benchmark_return,
            "turnover": turnover,
            "estimated_cost_rate": estimated_cost_rate,
            "net_return": net_return,
            "net_excess_return": net_excess,
            "net_nav": nav,
            "benchmark_nav": benchmark_nav,
            "relative_nav": nav / benchmark_nav,
            "selection_uses_realized_returns": "false",
            "policy_provenance": (
                "SELECTED_AFTER_REVIEWING_2026_07_30_OOS"
            ),
            "future_holdout_required": "true",
            "policy_freeze_date": TURNOVER_CAP_POLICY_FREEZE_DATE,
            "actionable": "false",
        })
        previous = selected
    return output


def _compound(rows: Sequence[Mapping[str, object]], key: str) -> float:
    return math.prod(1.0 + _float(row, key) for row in rows) - 1.0


def _max_drawdown(rows: Sequence[Mapping[str, object]]) -> float:
    nav = 1.0
    peak = 1.0
    drawdown = 0.0
    for row in rows:
        nav *= 1.0 + _float(row, "net_return")
        peak = max(peak, nav)
        drawdown = min(drawdown, nav / peak - 1.0)
    return drawdown


def capped_policy_metrics(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, float | int]:
    if not rows:
        return {
            "period_count": 0,
            "gross_total_return": 0.0,
            "net_total_return": 0.0,
            "benchmark_total_return": 0.0,
            "relative_total_return": 0.0,
            "top_k_relative_return": 0.0,
            "average_net_excess_return": 0.0,
            "positive_net_excess_ratio": 0.0,
            "mean_turnover": 1.0,
            "max_drawdown": 0.0,
            "first_half_average_net_excess": 0.0,
            "second_half_average_net_excess": 0.0,
            "leave_best_period_out_relative_total_return": 0.0,
            "best_positive_excess_contribution_share": 1.0,
        }
    period_count = len(rows)
    gross_total = _compound(rows, "gross_return")
    net_total = _compound(rows, "net_return")
    benchmark_total = _compound(rows, "benchmark_return")
    relative_total = (
        (1.0 + net_total) / (1.0 + benchmark_total) - 1.0
    )
    net_excess = [_float(row, "net_excess_return") for row in rows]
    gross_excess = [_float(row, "gross_excess_return") for row in rows]
    split = max(1, period_count // 2)
    first = net_excess[:split]
    second = net_excess[split:]
    best_index = max(range(period_count), key=lambda index: net_excess[index])
    leave_best = [row for index, row in enumerate(rows) if index != best_index]
    leave_best_net = _compound(leave_best, "net_return")
    leave_best_benchmark = _compound(leave_best, "benchmark_return")
    leave_best_relative = (
        (1.0 + leave_best_net) / (1.0 + leave_best_benchmark) - 1.0
        if leave_best else 0.0
    )
    positive_sum = sum(value for value in net_excess if value > 0.0)
    best_positive = max([value for value in net_excess if value > 0.0] or [0.0])
    return {
        "period_count": period_count,
        "gross_total_return": gross_total,
        "net_total_return": net_total,
        "benchmark_total_return": benchmark_total,
        "relative_total_return": relative_total,
        "top_k_relative_return": fmean(gross_excess),
        "average_net_excess_return": fmean(net_excess),
        "positive_net_excess_ratio": (
            sum(value > 0.0 for value in net_excess) / period_count
        ),
        "mean_turnover": fmean(_float(row, "turnover") for row in rows),
        "max_drawdown": _max_drawdown(rows),
        "first_half_average_net_excess": fmean(first),
        "second_half_average_net_excess": (
            fmean(second) if second else 0.0
        ),
        "leave_best_period_out_relative_total_return": leave_best_relative,
        "best_positive_excess_contribution_share": (
            best_positive / positive_sum if positive_sum > 0.0 else 1.0
        ),
    }


def _future_rank_ic(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    freeze_date: str,
) -> tuple[int, float, float]:
    by_day: dict[str, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if str(row.get("model") or "") != ENSEMBLE_MODEL:
            continue
        day = str(row.get("test_date") or "")
        if day > freeze_date:
            by_day.setdefault(day, []).append(row)
    values: list[float] = []
    for rows in by_day.values():
        ordered_score = sorted(rows, key=lambda row: _float(row, "score"))
        ordered_return = sorted(rows, key=lambda row: _float(row, "relative_return"))
        score_rank = {
            str(row.get("symbol") or ""): index
            for index, row in enumerate(ordered_score)
        }
        return_rank = {
            str(row.get("symbol") or ""): index
            for index, row in enumerate(ordered_return)
        }
        symbols = sorted(set(score_rank) & set(return_rank))
        if len(symbols) < 3:
            continue
        x = [float(score_rank[symbol]) for symbol in symbols]
        y = [float(return_rank[symbol]) for symbol in symbols]
        x_mean = fmean(x)
        y_mean = fmean(y)
        numerator = sum(
            (left - x_mean) * (right - y_mean)
            for left, right in zip(x, y)
        )
        denominator = math.sqrt(
            sum((value - x_mean) ** 2 for value in x)
            * sum((value - y_mean) ** 2 for value in y)
        )
        if denominator > 0.0:
            values.append(numerator / denominator)
    return (
        len(values),
        fmean(values) if values else 0.0,
        sum(value > 0.0 for value in values) / len(values)
        if values else 0.0,
    )


def publish_v11_turnover_cap(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    predictions = _read_csv(output / "oos_predictions.csv")
    leaderboard = _read_csv(output / "model_leaderboard.csv")
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    contract = dict(summary.get("backtest_contract") or {})
    costs = dict(contract.get("costs") or {})
    top_k = int(float(costs.get("top_k", contract.get("top_k", 10)) or 10))

    periods = turnover_capped_periods(
        predictions,
        top_k=top_k,
        max_voluntary_replacements=MAX_VOLUNTARY_REPLACEMENTS,
        buy_fee_bps=float(costs.get("buy_fee_bps", 15.0) or 15.0),
        sell_fee_bps=float(costs.get("sell_fee_bps", 15.0) or 15.0),
        sell_tax_bps=float(costs.get("sell_tax_bps", 10.0) or 10.0),
        slippage_bps=float(costs.get("slippage_bps", 10.0) or 10.0),
    )
    _write_csv(
        output / "turnover_capped_reference_periods.csv",
        periods,
        tuple(periods[0]) if periods else (
            "model",
            "strategy",
            "signal_date",
        ),
    )
    metrics = capped_policy_metrics(periods)
    ensemble_row = next(
        (
            dict(row) for row in leaderboard
            if str(row.get("model") or "") == ENSEMBLE_MODEL
        ),
        {},
    )
    ensemble_row.update({
        "top_k_relative_return": metrics["top_k_relative_return"],
        "average_net_excess_return": metrics[
            "average_net_excess_return"
        ],
        "positive_net_excess_ratio": metrics[
            "positive_net_excess_ratio"
        ],
        "relative_total_return": metrics["relative_total_return"],
    })
    weight_contract = dict(
        summary.get("final_ensemble_weights_contract_v10") or {}
    )
    positive_components = int(
        weight_contract.get("positive_component_count", 0) or 0
    )
    strict_gate = v9.strict_reference_gate(
        ensemble_row,
        mean_turnover=float(metrics["mean_turnover"]),
        positive_component_count=positive_components,
    ) if ensemble_row else {}
    strict_gate.update({
        "no_negative_ensemble_weights": bool(
            weight_contract.get("no_negative_weights", False)
        ),
        "first_half_net_excess_positive": (
            float(metrics["first_half_average_net_excess"]) > 0.0
        ),
        "second_half_net_excess_positive": (
            float(metrics["second_half_average_net_excess"]) > 0.0
        ),
        "leave_best_period_out_relative_positive": (
            float(
                metrics["leave_best_period_out_relative_total_return"]
            ) > 0.0
        ),
        "best_positive_period_share_at_most_half": (
            float(metrics["best_positive_excess_contribution_share"])
            <= 0.50
        ),
    })
    historical_pass = bool(strict_gate) and all(strict_gate.values())

    diagnostic = {
        "model": ENSEMBLE_MODEL,
        "strategy": "posthoc_turnover_capped_top_k_candidate",
        "top_k": top_k,
        "max_voluntary_replacements": MAX_VOLUNTARY_REPLACEMENTS,
        "minimum_retained_when_available": (
            top_k - MAX_VOLUNTARY_REPLACEMENTS
        ),
        **metrics,
        "mean_rank_ic": ensemble_row.get("mean_rank_ic", ""),
        "positive_rank_ic_ratio": ensemble_row.get(
            "positive_rank_ic_ratio", ""
        ),
        "positive_component_count": positive_components,
        "no_negative_ensemble_weights": str(
            bool(weight_contract.get("no_negative_weights", False))
        ).lower(),
        "strict_historical_reference_gate_passed": str(
            historical_pass
        ).lower(),
        "selection_uses_realized_returns": "false",
        "policy_provenance": (
            "SELECTED_AFTER_REVIEWING_2026_07_30_OOS"
        ),
        "policy_freeze_date": TURNOVER_CAP_POLICY_FREEZE_DATE,
        "future_holdout_required": "true",
        "actionable": "false",
    }
    _write_csv(
        output / "turnover_capped_reference_diagnostic.csv",
        [diagnostic],
        tuple(diagnostic),
    )

    future_periods = [
        row for row in periods
        if str(row.get("signal_date") or "")
        > TURNOVER_CAP_POLICY_FREEZE_DATE
    ]
    future_metrics = capped_policy_metrics(future_periods)
    future_fold_count, future_mean_ic, future_positive_ic = _future_rank_ic(
        predictions,
        freeze_date=TURNOVER_CAP_POLICY_FREEZE_DATE,
    )
    future_gate = {
        "enough_future_folds": (
            future_fold_count >= MINIMUM_FUTURE_TURNOVER_CAP_FOLDS
        ),
        "mean_rank_ic_at_least_003": future_mean_ic >= 0.03,
        "positive_rank_ic_ratio_at_least_055": (
            future_positive_ic >= 0.55
        ),
        "net_total_return_positive": (
            float(future_metrics["net_total_return"]) > 0.0
        ),
        "relative_total_return_positive": (
            float(future_metrics["relative_total_return"]) > 0.0
        ),
        "average_net_excess_positive": (
            float(future_metrics["average_net_excess_return"]) > 0.0
        ),
        "positive_net_excess_ratio_at_least_half": (
            float(future_metrics["positive_net_excess_ratio"]) >= 0.50
        ),
        "turnover_controlled": (
            float(future_metrics["mean_turnover"]) <= 0.60
        ),
    }
    future_support = all(future_gate.values())
    future_row = {
        "model": ENSEMBLE_MODEL,
        "policy_freeze_date": TURNOVER_CAP_POLICY_FREEZE_DATE,
        "minimum_future_folds": MINIMUM_FUTURE_TURNOVER_CAP_FOLDS,
        "future_fold_count": future_fold_count,
        "mean_rank_ic": future_mean_ic,
        "positive_rank_ic_ratio": future_positive_ic,
        **future_metrics,
        "status": (
            "FUTURE_HOLDOUT_SUPPORTS_TURNOVER_CAPPED_REFERENCE"
            if future_support
            else "INSUFFICIENT_OR_FAILED_FUTURE_HOLDOUT"
        ),
        "actionable": "false",
    }
    _write_csv(
        output / "predictive_v11_future_holdout.csv",
        [future_row],
        tuple(future_row),
    )

    original_champion = str(
        summary.get("research_champion") or "NO_MODEL_APPROVED"
    )
    summary["base_upgrade_schema_version"] = v10.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["predictive_upgrade_v11"] = {
        "portfolio_policy": "TURNOVER_CAPPED_TOP_K_MAX_3_REPLACEMENTS",
        "max_voluntary_replacements": MAX_VOLUNTARY_REPLACEMENTS,
        "minimum_retained_when_available": (
            top_k - MAX_VOLUNTARY_REPLACEMENTS
        ),
        "historical_metrics": metrics,
        "strict_historical_reference_gate": strict_gate,
        "strict_historical_reference_gate_passed": historical_pass,
        "future_holdout_gate": future_gate,
        "future_holdout_support": future_support,
        "policy_provenance": (
            "SELECTED_AFTER_REVIEWING_2026_07_30_OOS"
        ),
        "policy_freeze_date": TURNOVER_CAP_POLICY_FREEZE_DATE,
        "minimum_future_folds": MINIMUM_FUTURE_TURNOVER_CAP_FOLDS,
        "selection_uses_realized_returns": False,
        "requires_actual_prior_portfolio_for_forward_use": True,
        "research_gate_relaxed": False,
        "actionable": False,
        "files": [
            "turnover_capped_reference_diagnostic.csv",
            "turnover_capped_reference_periods.csv",
            "predictive_v11_future_holdout.csv",
        ],
    }
    summary["v11_historical_champion_before_provenance_block"] = (
        original_champion
    )
    summary["research_champion"] = "NO_MODEL_APPROVED"
    summary["champion_reason"] = (
        "V11_POSTHOC_POLICY_REQUIRES_FUTURE_HOLDOUT"
        if historical_pass
        else "V11_HISTORICAL_REFERENCE_GATE_NOT_MET"
    )
    summary["forward_watchlist_published"] = False
    summary["research_eligible"] = False
    summary["live_capital_approved"] = False
    summary["deployment_status"] = "NO_MODEL_APPROVED"
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    forward_path = output / "forward_model_scores.csv"
    forward_rows = _read_csv(forward_path)
    for row in forward_rows:
        row["research_champion"] = "NO_MODEL_APPROVED"
        row["reference_model"] = "NO_MODEL_APPROVED"
        row["selected_top_k"] = "false"
        row["research_approved"] = "false"
        row["live_capital_approved"] = "false"
    if forward_rows:
        _write_csv(forward_path, forward_rows, tuple(forward_rows[0]))

    with (output / "model_lab_report.txt").open(
        "a",
        encoding="utf-8",
    ) as stream:
        stream.write("\nMODEL LAB UPGRADE V11\n")
        stream.write(
            "Portfolio policy: unchanged v10 ensemble rank with at most "
            "three voluntary replacements per monthly rebalance.\n"
        )
        stream.write(
            f"Historical reference gate: {str(historical_pass).lower()}; "
            f"future holdout support: {str(future_support).lower()}; "
            "post-hoc policy, actionable=false.\n"
        )

    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "historical_turnover_capped_reference_gate_passed": historical_pass,
        "future_turnover_capped_holdout_support": future_support,
        "research_champion": "NO_MODEL_APPROVED",
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    result = v10.run_model_lab(**kwargs)
    diagnostics = publish_v11_turnover_cap(
        Path(str(kwargs["output_dir"]))
    )
    return {**result, **diagnostics}


def _parser():
    return v10._parser()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_model_lab(
        input_zip=args.input_zip,
        output_dir=args.output_dir,
        models=tuple(
            item.strip()
            for item in args.models.split(",")
            if item.strip()
        ),
        evaluation_months=args.evaluation_months,
        minimum_train_months=args.minimum_train_months,
        inner_validation_months=args.inner_validation_months,
        top_k=args.top_k,
        turnover_buffer=args.turnover_buffer,
        seed=args.seed,
        strict_dependencies=args.strict_dependencies,
        buy_fee_bps=args.buy_fee_bps,
        sell_fee_bps=args.sell_fee_bps,
        sell_tax_bps=args.sell_tax_bps,
        slippage_bps=args.slippage_bps,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "TURNOVER_CAP_POLICY_FREEZE_DATE",
    "MINIMUM_FUTURE_TURNOVER_CAP_FOLDS",
    "MAX_VOLUNTARY_REPLACEMENTS",
    "turnover_capped_periods",
    "capped_policy_metrics",
    "publish_v11_turnover_cap",
    "run_model_lab",
    "main",
]
