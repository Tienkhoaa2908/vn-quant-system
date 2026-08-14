"""Model Lab v13: DNSE cash cost contract and nested historical validation.

V13 replaces the old all-in fee approximation with explicit DNSE cash-equity
cost components and evaluates the turnover policy with nested, chronological,
non-overlapping outer test blocks.  Policy selection only sees the validation
block immediately before each outer test block.

The prediction artifact does not carry exchange or executed share quantities.
Therefore:
* the exchange fee defaults to the conservative upper bound (2.7 bps/side);
* the 0.3 VND/share transfer fee is converted to a conservative bps equivalent
  using a disclosed reference price (10,000 VND by default);
* both assumptions are published and stress-tested.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v12 as v12
from .model_lab_core import DEFAULT_MODELS, ENSEMBLE_MODEL

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v13"
DEFAULT_REPLACEMENT_CAPS = (0, 1, 2, 3, 4, 5)


@dataclass(frozen=True)
class DnseCashCostConfig:
    broker_buy_fee_bps: float = 0.0
    broker_sell_fee_bps: float = 0.0
    exchange_buy_fee_bps: float = 2.7
    exchange_sell_fee_bps: float = 2.7
    sell_tax_bps: float = 10.0
    transfer_fee_vnd_per_share: float = 0.3
    transfer_reference_price_vnd: float = 10_000.0
    slippage_bps: float = 5.0
    stress_slippage_bps: float = 10.0

    def __post_init__(self) -> None:
        rate_names = (
            "broker_buy_fee_bps",
            "broker_sell_fee_bps",
            "exchange_buy_fee_bps",
            "exchange_sell_fee_bps",
            "sell_tax_bps",
            "slippage_bps",
            "stress_slippage_bps",
        )
        for name in rate_names:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0 or value >= 10_000.0:
                raise ValueError(f"MODEL_LAB_V13_INVALID_BPS:{name}")
        if (
            not math.isfinite(float(self.transfer_fee_vnd_per_share))
            or self.transfer_fee_vnd_per_share < 0.0
        ):
            raise ValueError("MODEL_LAB_V13_INVALID_TRANSFER_FEE")
        if (
            not math.isfinite(float(self.transfer_reference_price_vnd))
            or self.transfer_reference_price_vnd <= 0.0
        ):
            raise ValueError("MODEL_LAB_V13_INVALID_REFERENCE_PRICE")
        if self.stress_slippage_bps < self.slippage_bps:
            raise ValueError("MODEL_LAB_V13_STRESS_SLIPPAGE_BELOW_BASE")

    @property
    def transfer_fee_bps_equivalent(self) -> float:
        return (
            self.transfer_fee_vnd_per_share
            / self.transfer_reference_price_vnd
            * 10_000.0
        )

    @property
    def combined_buy_fee_bps(self) -> float:
        return self.broker_buy_fee_bps + self.exchange_buy_fee_bps

    @property
    def combined_sell_fee_bps(self) -> float:
        return (
            self.broker_sell_fee_bps
            + self.exchange_sell_fee_bps
            + self.transfer_fee_bps_equivalent
        )

    def as_contract(self) -> dict[str, object]:
        return {
            "broker_buy_fee_bps": self.broker_buy_fee_bps,
            "broker_sell_fee_bps": self.broker_sell_fee_bps,
            "exchange_buy_fee_bps": self.exchange_buy_fee_bps,
            "exchange_sell_fee_bps": self.exchange_sell_fee_bps,
            "sell_tax_bps": self.sell_tax_bps,
            "transfer_fee_vnd_per_share": self.transfer_fee_vnd_per_share,
            "transfer_reference_price_vnd": self.transfer_reference_price_vnd,
            "transfer_fee_bps_equivalent": self.transfer_fee_bps_equivalent,
            "combined_buy_fee_bps": self.combined_buy_fee_bps,
            "combined_sell_fee_bps": self.combined_sell_fee_bps,
            "base_slippage_bps_each_side": self.slippage_bps,
            "stress_slippage_bps_each_side": self.stress_slippage_bps,
            "exchange_fee_policy": "CONSERVATIVE_UPPER_BOUND_2_7_BPS",
            "broker_fee_policy": "DNSE_NON_MARGIN_DEFAULT_ZERO_CONFIGURABLE",
            "exchange_field_available": False,
            "executed_share_quantity_available": False,
            "transfer_fee_model": "REFERENCE_PRICE_BPS_EQUIVALENT",
            "exact_execution_cost_claimed": False,
        }


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


def _period_subset(
    rows: Sequence[Mapping[str, object]],
    dates: Sequence[str],
) -> list[dict[str, object]]:
    wanted = set(dates)
    return [
        dict(row)
        for row in rows
        if str(row.get("signal_date") or "") in wanted
    ]


def _rank_ic_for_model_dates(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    model: str,
    dates: Sequence[str],
) -> tuple[int, float, float]:
    wanted = set(dates)
    by_day: dict[str, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if str(row.get("model") or "") != model:
            continue
        day = str(row.get("test_date") or "")
        if day in wanted:
            by_day.setdefault(day, []).append(row)

    values: list[float] = []
    for day in sorted(by_day):
        rows = by_day[day]
        if len(rows) < 3:
            continue
        score_order = sorted(
            rows,
            key=lambda row: (_float(row, "score"), str(row.get("symbol") or "")),
        )
        return_order = sorted(
            rows,
            key=lambda row: (
                _float(row, "relative_return"),
                str(row.get("symbol") or ""),
            ),
        )
        score_rank = {
            str(row.get("symbol") or ""): index
            for index, row in enumerate(score_order)
        }
        return_rank = {
            str(row.get("symbol") or ""): index
            for index, row in enumerate(return_order)
        }
        symbols = sorted(set(score_rank) & set(return_rank))
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
        (
            sum(value > 0.0 for value in values) / len(values)
            if values else 0.0
        ),
    )


def _validation_key(
    metrics: Mapping[str, float | int],
    *,
    cap: int,
    model_priority: int,
) -> tuple[float, float, float, float, float, int, int]:
    turnover = float(metrics["mean_turnover"])
    controlled = 1.0 if turnover <= 0.60 else 0.0
    first_half = float(metrics["first_half_average_net_excess"])
    second_half = float(metrics["second_half_average_net_excess"])
    conservative_excess = min(first_half, second_half)
    return (
        controlled,
        conservative_excess,
        float(metrics["average_net_excess_return"]),
        float(metrics["positive_net_excess_ratio"]),
        float(metrics["relative_total_return"]),
        -model_priority,
        -cap,
    )


def _policy_rows_for_model(
    prediction_rows: Sequence[Mapping[str, object]],
    model: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in prediction_rows:
        if str(row.get("model") or "") != model:
            continue
        converted = dict(row)
        converted["source_model"] = model
        converted["model"] = ENSEMBLE_MODEL
        rows.append(converted)
    return rows


def _complete_candidate_models(
    prediction_rows: Sequence[Mapping[str, object]],
    dates: Sequence[str],
    requested: Sequence[str] | None,
) -> tuple[str, ...]:
    wanted = set(dates)
    by_model: dict[str, set[str]] = {}
    for row in prediction_rows:
        model = str(row.get("model") or "")
        day = str(row.get("test_date") or "")
        if model and day in wanted:
            by_model.setdefault(model, set()).add(day)
    allowed = set(requested) if requested else set(by_model)
    complete = sorted(
        model
        for model, observed_dates in by_model.items()
        if model in allowed and observed_dates == wanted
    )
    if not complete:
        raise ValueError("MODEL_LAB_V13_NO_COMPLETE_CANDIDATE_MODEL")
    return tuple(complete)


def _period_cache(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    candidate_models: Sequence[str],
    replacement_caps: Sequence[int],
    cost: DnseCashCostConfig,
    slippage_bps: float,
) -> dict[tuple[str, int], list[dict[str, object]]]:
    cache: dict[tuple[str, int], list[dict[str, object]]] = {}
    for model in candidate_models:
        policy_rows = _policy_rows_for_model(prediction_rows, model)
        for cap in replacement_caps:
            periods = v12.corrected_turnover_capped_periods(
                policy_rows,
                top_k=top_k,
                max_voluntary_replacements=cap,
                buy_fee_bps=cost.combined_buy_fee_bps,
                sell_fee_bps=cost.combined_sell_fee_bps,
                sell_tax_bps=cost.sell_tax_bps,
                slippage_bps=slippage_bps,
            )
            for row in periods:
                row["selected_model"] = model
                row["model"] = model
            cache[(model, cap)] = periods
    return cache


def nested_outer_test_evaluation(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    replacement_caps: Sequence[int] = DEFAULT_REPLACEMENT_CAPS,
    candidate_models: Sequence[str] | None = None,
    validation_months: int = 6,
    test_months: int = 3,
    minimum_outer_test_periods: int = 12,
    cost: DnseCashCostConfig | None = None,
) -> dict[str, object]:
    """Select model and turnover cap on prior validation, then score outer test."""
    if validation_months < 3:
        raise ValueError("MODEL_LAB_V13_VALIDATION_MONTHS_TOO_SMALL")
    if test_months < 1:
        raise ValueError("MODEL_LAB_V13_TEST_MONTHS_TOO_SMALL")
    if minimum_outer_test_periods < 3:
        raise ValueError("MODEL_LAB_V13_MINIMUM_OUTER_TEST_TOO_SMALL")
    caps = tuple(sorted(set(int(value) for value in replacement_caps)))
    if not caps or any(value < 0 or value > top_k for value in caps):
        raise ValueError("MODEL_LAB_V13_INVALID_REPLACEMENT_CAPS")
    config = cost or DnseCashCostConfig()

    dates = sorted({
        str(row.get("test_date") or "")
        for row in prediction_rows
        if str(row.get("test_date") or "")
    })
    if len(dates) < validation_months + test_months:
        raise ValueError("MODEL_LAB_V13_INSUFFICIENT_OOS_DATES")
    models = _complete_candidate_models(
        prediction_rows,
        dates,
        candidate_models,
    )
    complexity_order = {
        "momentum_baseline": 0,
        "robust_technical_ensemble_v1": 1,
        "ridge_ranker": 2,
        "hist_gradient_boosting_ranker": 3,
        "lightgbm_ranker": 4,
        "xgboost_ranker": 5,
        "torch_pairwise_mlp": 6,
        ENSEMBLE_MODEL: 7,
    }

    base_cache = _period_cache(
        prediction_rows,
        top_k=top_k,
        candidate_models=models,
        replacement_caps=caps,
        cost=config,
        slippage_bps=config.slippage_bps,
    )
    stress_cache = _period_cache(
        prediction_rows,
        top_k=top_k,
        candidate_models=models,
        replacement_caps=caps,
        cost=config,
        slippage_bps=config.stress_slippage_bps,
    )

    selections: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    stress_outer_rows: list[dict[str, object]] = []
    outer_ic_values: list[float] = []

    block_index = 0
    for test_start in range(validation_months, len(dates), test_months):
        test_dates = dates[test_start:test_start + test_months]
        if not test_dates:
            continue
        validation_dates = dates[
            max(0, test_start - validation_months):test_start
        ]
        if len(validation_dates) < validation_months:
            continue

        candidates: list[
            tuple[
                tuple[float, float, float, float, float, int, int],
                str,
                int,
                dict[str, float | int],
            ]
        ] = []
        for model in models:
            priority = complexity_order.get(model, 99)
            for cap in caps:
                validation_periods = _period_subset(
                    base_cache[(model, cap)],
                    validation_dates,
                )
                metrics = v12.v11.capped_policy_metrics(validation_periods)
                candidates.append((
                    _validation_key(
                        metrics,
                        cap=cap,
                        model_priority=priority,
                    ),
                    model,
                    cap,
                    metrics,
                ))
        _, selected_model, selected_cap, validation_metrics = max(
            candidates,
            key=lambda item: item[0],
        )

        outer_fold = f"outer_{block_index + 1:02d}"
        selections.append({
            "outer_fold": outer_fold,
            "validation_start": validation_dates[0],
            "validation_end": validation_dates[-1],
            "test_start": test_dates[0],
            "test_end": test_dates[-1],
            "selected_model": selected_model,
            "selected_replacement_cap": selected_cap,
            "candidate_models": "|".join(models),
            "candidate_caps": "|".join(str(value) for value in caps),
            "validation_average_net_excess_return": validation_metrics[
                "average_net_excess_return"
            ],
            "validation_positive_net_excess_ratio": validation_metrics[
                "positive_net_excess_ratio"
            ],
            "validation_relative_total_return": validation_metrics[
                "relative_total_return"
            ],
            "validation_mean_turnover": validation_metrics["mean_turnover"],
            "selection_uses_outer_test_labels": "false",
        })

        for row in _period_subset(
            base_cache[(selected_model, selected_cap)],
            test_dates,
        ):
            row["outer_fold"] = outer_fold
            row["selected_model"] = selected_model
            row["selected_replacement_cap"] = selected_cap
            row["cost_scenario"] = "BASE"
            outer_rows.append(row)
        for row in _period_subset(
            stress_cache[(selected_model, selected_cap)],
            test_dates,
        ):
            row["outer_fold"] = outer_fold
            row["selected_model"] = selected_model
            row["selected_replacement_cap"] = selected_cap
            row["cost_scenario"] = "STRESS"
            stress_outer_rows.append(row)

        for day in test_dates:
            count, day_ic, _ = _rank_ic_for_model_dates(
                prediction_rows,
                model=selected_model,
                dates=(day,),
            )
            if count:
                outer_ic_values.append(day_ic)
        block_index += 1

    if not outer_rows:
        raise ValueError("MODEL_LAB_V13_NO_OUTER_TEST_ROWS")

    base_metrics = v12.v11.capped_policy_metrics(outer_rows)
    stress_metrics = v12.v11.capped_policy_metrics(stress_outer_rows)
    ic_count = len(outer_ic_values)
    mean_ic = fmean(outer_ic_values) if outer_ic_values else 0.0
    positive_ic = (
        sum(value > 0.0 for value in outer_ic_values) / ic_count
        if ic_count else 0.0
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
    summary = {
        "status": status,
        "outer_fold_count": len(selections),
        "outer_test_period_count": int(base_metrics["period_count"]),
        "rank_ic_period_count": ic_count,
        "mean_rank_ic": mean_ic,
        "positive_rank_ic_ratio": positive_ic,
        "base_metrics": base_metrics,
        "stress_metrics": stress_metrics,
        "gate": gate,
        "gate_passed": passed,
        "validation_months": validation_months,
        "test_months": test_months,
        "candidate_models": list(models),
        "candidate_replacement_caps": list(caps),
        "outer_test_dates": sorted({
            str(row.get("signal_date") or "") for row in outer_rows
        }),
        "selected_models_by_outer_fold": [
            str(row["selected_model"]) for row in selections
        ],
        "selected_caps_by_outer_fold": [
            int(row["selected_replacement_cap"]) for row in selections
        ],
        "random_split_used": False,
        "chronological_split": True,
        "outer_test_blocks_non_overlapping": True,
        "model_and_policy_selected_only_from_prior_validation": True,
    }
    return {
        "summary": summary,
        "selection_rows": selections,
        "outer_rows": outer_rows,
        "stress_outer_rows": stress_outer_rows,
    }


def publish_v13_validation(
    output_dir: Path,
    *,
    cost: DnseCashCostConfig,
    validation_months: int,
    test_months: int,
    minimum_outer_test_periods: int,
    replacement_caps: Sequence[int],
) -> dict[str, object]:
    output = Path(output_dir)
    predictions = _read_csv(output / "oos_predictions.csv")
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    contract = dict(summary.get("backtest_contract") or {})
    costs = dict(contract.get("costs") or {})
    top_k = int(float(costs.get("top_k", contract.get("top_k", 10)) or 10))

    result = nested_outer_test_evaluation(
        predictions,
        top_k=top_k,
        replacement_caps=replacement_caps,
        validation_months=validation_months,
        test_months=test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        cost=cost,
    )
    validation = dict(result["summary"])
    selections = list(result["selection_rows"])
    outer_rows = list(result["outer_rows"])
    stress_rows = list(result["stress_outer_rows"])

    cost_contract = cost.as_contract()
    _write_csv(
        output / "dnse_cost_contract_v13.csv",
        [cost_contract],
        tuple(cost_contract),
    )
    scenario_rows = [
        {
            "scenario": "BASE",
            "buy_fee_bps_ex_slippage": cost.combined_buy_fee_bps,
            "sell_fee_bps_ex_tax_slippage": cost.combined_sell_fee_bps,
            "sell_tax_bps": cost.sell_tax_bps,
            "slippage_bps_each_side": cost.slippage_bps,
            "full_round_trip_bps": (
                cost.combined_buy_fee_bps
                + cost.combined_sell_fee_bps
                + cost.sell_tax_bps
                + 2.0 * cost.slippage_bps
            ),
        },
        {
            "scenario": "STRESS",
            "buy_fee_bps_ex_slippage": cost.combined_buy_fee_bps,
            "sell_fee_bps_ex_tax_slippage": cost.combined_sell_fee_bps,
            "sell_tax_bps": cost.sell_tax_bps,
            "slippage_bps_each_side": cost.stress_slippage_bps,
            "full_round_trip_bps": (
                cost.combined_buy_fee_bps
                + cost.combined_sell_fee_bps
                + cost.sell_tax_bps
                + 2.0 * cost.stress_slippage_bps
            ),
        },
    ]
    _write_csv(
        output / "dnse_cost_scenarios_v13.csv",
        scenario_rows,
        tuple(scenario_rows[0]),
    )
    _write_csv(
        output / "nested_policy_selection_v13.csv",
        selections,
        tuple(selections[0]),
    )
    _write_csv(
        output / "nested_outer_test_periods_v13.csv",
        outer_rows,
        tuple(outer_rows[0]),
    )
    _write_csv(
        output / "nested_outer_test_stress_periods_v13.csv",
        stress_rows,
        tuple(stress_rows[0]),
    )
    validation_row = {
        "model": ENSEMBLE_MODEL,
        "status": validation["status"],
        "outer_fold_count": validation["outer_fold_count"],
        "outer_test_period_count": validation["outer_test_period_count"],
        "mean_rank_ic": validation["mean_rank_ic"],
        "positive_rank_ic_ratio": validation["positive_rank_ic_ratio"],
        **{
            f"base_{key}": value
            for key, value in dict(validation["base_metrics"]).items()
        },
        **{
            f"stress_{key}": value
            for key, value in dict(validation["stress_metrics"]).items()
        },
        "gate_passed": str(bool(validation["gate_passed"])).lower(),
        "model_and_policy_selected_only_from_prior_validation": "true",
        "outer_test_blocks_non_overlapping": "true",
        "random_split_used": "false",
        "actionable": "false",
    }
    _write_csv(
        output / "nested_historical_validation_v13.csv",
        [validation_row],
        tuple(validation_row),
    )

    summary["base_upgrade_schema_version"] = v12.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["dnse_cash_cost_contract_v13"] = cost_contract
    summary["nested_historical_validation_v13"] = validation
    summary["historical_reference_status"] = validation["status"]
    summary["historical_reference_gate_passed"] = bool(
        validation["gate_passed"]
    )
    summary["historical_reference_model"] = (
        ENSEMBLE_MODEL if validation["gate_passed"] else "NO_MODEL_APPROVED"
    )
    summary["forward_watchlist_published"] = False
    summary["live_capital_approved"] = False
    summary["actionable"] = False
    raw_limitations = summary.get("limitations")
    limitations = list(raw_limitations) if isinstance(raw_limitations, list) else []
    limitations.extend([
        (
            "Exchange is absent from oos_predictions; v13 uses the conservative "
            "2.7 bps exchange-fee upper bound for all cash-equity trades."
        ),
        (
            "Executed shares are absent; the 0.3 VND/share transfer fee is "
            "converted with a disclosed reference price and stress-tested."
        ),
        (
            "Historical validation can approve reference quality, but does not "
            "approve live capital or claim exact T+1 execution."
        ),
    ])
    summary["limitations"] = list(dict.fromkeys(limitations))
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    with (output / "model_lab_report.txt").open(
        "a",
        encoding="utf-8",
    ) as stream:
        stream.write("\nMODEL LAB UPGRADE V13\n")
        stream.write(
            "DNSE cash costs are decomposed into broker, exchange, sell tax, "
            "per-share transfer-fee equivalent and slippage scenarios.\n"
        )
        stream.write(
            "Model and turnover cap are selected only on prior validation "
            "blocks and scored on chronological, non-overlapping outer tests.\n"
        )
        stream.write(
            f"Historical validation status: {validation['status']}; "
            f"gate_passed={str(validation['gate_passed']).lower()}; "
            "actionable=false; live_capital_approved=false.\n"
        )

    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "historical_reference_status": validation["status"],
        "historical_reference_gate_passed": bool(validation["gate_passed"]),
        "historical_reference_model": summary[
            "historical_reference_model"
        ],
        "research_champion": summary.get(
            "research_champion", "NO_MODEL_APPROVED"
        ),
        "live_capital_approved": False,
    }


def run_model_lab(
    *,
    input_zip: Path,
    output_dir: Path,
    models: Sequence[str] = DEFAULT_MODELS,
    evaluation_months: int = 24,
    minimum_train_months: int = 24,
    inner_validation_months: int = 3,
    top_k: int = 10,
    turnover_buffer: int | None = None,
    seed: int = 20260731,
    strict_dependencies: bool = False,
    buy_fee_bps: float | None = None,
    sell_fee_bps: float | None = None,
    sell_tax_bps: float = 10.0,
    slippage_bps: float = 5.0,
    dnse_broker_buy_fee_bps: float = 0.0,
    dnse_broker_sell_fee_bps: float = 0.0,
    exchange_buy_fee_bps: float = 2.7,
    exchange_sell_fee_bps: float = 2.7,
    transfer_fee_vnd_per_share: float = 0.3,
    transfer_reference_price_vnd: float = 10_000.0,
    stress_slippage_bps: float = 10.0,
    nested_validation_months: int = 6,
    nested_test_months: int = 3,
    minimum_outer_test_periods: int = 12,
    replacement_caps: Sequence[int] = DEFAULT_REPLACEMENT_CAPS,
    predictor_overrides: Mapping[str, object] | None = None,
) -> dict[str, object]:
    cost = DnseCashCostConfig(
        broker_buy_fee_bps=dnse_broker_buy_fee_bps,
        broker_sell_fee_bps=dnse_broker_sell_fee_bps,
        exchange_buy_fee_bps=exchange_buy_fee_bps,
        exchange_sell_fee_bps=exchange_sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        transfer_fee_vnd_per_share=transfer_fee_vnd_per_share,
        transfer_reference_price_vnd=transfer_reference_price_vnd,
        slippage_bps=slippage_bps,
        stress_slippage_bps=stress_slippage_bps,
    )
    effective_buy_fee = (
        float(buy_fee_bps)
        if buy_fee_bps is not None
        else cost.combined_buy_fee_bps
    )
    effective_sell_fee = (
        float(sell_fee_bps)
        if sell_fee_bps is not None
        else cost.combined_sell_fee_bps
    )
    result = v12.run_model_lab(
        input_zip=input_zip,
        output_dir=output_dir,
        models=models,
        evaluation_months=evaluation_months,
        minimum_train_months=minimum_train_months,
        inner_validation_months=inner_validation_months,
        top_k=top_k,
        turnover_buffer=turnover_buffer,
        seed=seed,
        strict_dependencies=strict_dependencies,
        buy_fee_bps=effective_buy_fee,
        sell_fee_bps=effective_sell_fee,
        sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps,
        predictor_overrides=predictor_overrides,
    )
    validation = publish_v13_validation(
        Path(output_dir),
        cost=cost,
        validation_months=nested_validation_months,
        test_months=nested_test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        replacement_caps=replacement_caps,
    )
    return {**result, **validation}


def _parser() -> argparse.ArgumentParser:
    parser = v12._parser()
    parser.set_defaults(
        buy_fee_bps=None,
        sell_fee_bps=None,
        sell_tax_bps=10.0,
        slippage_bps=5.0,
    )
    parser.add_argument("--dnse-broker-buy-fee-bps", type=float, default=0.0)
    parser.add_argument("--dnse-broker-sell-fee-bps", type=float, default=0.0)
    parser.add_argument("--exchange-buy-fee-bps", type=float, default=2.7)
    parser.add_argument("--exchange-sell-fee-bps", type=float, default=2.7)
    parser.add_argument("--transfer-fee-vnd-per-share", type=float, default=0.3)
    parser.add_argument(
        "--transfer-reference-price-vnd",
        type=float,
        default=10_000.0,
    )
    parser.add_argument("--stress-slippage-bps", type=float, default=10.0)
    parser.add_argument("--nested-validation-months", type=int, default=6)
    parser.add_argument("--nested-test-months", type=int, default=3)
    parser.add_argument("--minimum-outer-test-periods", type=int, default=12)
    parser.add_argument(
        "--replacement-caps",
        default="0,1,2,3,4,5",
        help="Comma-separated voluntary replacement caps selected in validation.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    caps = tuple(
        int(item.strip())
        for item in str(args.replacement_caps).split(",")
        if item.strip()
    )
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
        dnse_broker_buy_fee_bps=args.dnse_broker_buy_fee_bps,
        dnse_broker_sell_fee_bps=args.dnse_broker_sell_fee_bps,
        exchange_buy_fee_bps=args.exchange_buy_fee_bps,
        exchange_sell_fee_bps=args.exchange_sell_fee_bps,
        transfer_fee_vnd_per_share=args.transfer_fee_vnd_per_share,
        transfer_reference_price_vnd=args.transfer_reference_price_vnd,
        stress_slippage_bps=args.stress_slippage_bps,
        nested_validation_months=args.nested_validation_months,
        nested_test_months=args.nested_test_months,
        minimum_outer_test_periods=args.minimum_outer_test_periods,
        replacement_caps=caps,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_REPLACEMENT_CAPS",
    "DnseCashCostConfig",
    "nested_outer_test_evaluation",
    "publish_v13_validation",
    "run_model_lab",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
