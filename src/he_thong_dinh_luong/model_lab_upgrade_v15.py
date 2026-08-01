"""Model Lab v15: model-wise nested outer validation.

V14 correctly carried holdings across outer blocks, but evaluated a meta-strategy
that was allowed to switch model families every three months. That is not the
usual nested-ML comparison contract: each algorithm should tune only its own
portfolio hyperparameters on inner validation, then be scored independently on
outer test data. V15 therefore:

* evaluates every model family independently;
* selects only the voluntary-replacement cap on prior validation data;
* carries each model's holdings continuously across all outer blocks;
* charges entry, cap-switch and normal turnover costs under DNSE base/stress
  scenarios;
* compares aggregate outer-test evidence only after every model has finished.

The protocol revision is disclosed because it was introduced after reviewing the
rejected v14 meta-selector. Historical reference status never approves live
capital or marks output actionable.
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
from . import model_lab_upgrade_v14 as v14

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v15"
PROTOCOL_PROVENANCE = "REVISED_AFTER_V14_META_SELECTOR_REJECTION"
_BASE_RUN = v14.run_model_lab


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


def _outer_block_positive_ratio(
    rows: Sequence[Mapping[str, object]],
) -> float:
    by_fold: dict[str, list[float]] = {}
    for row in rows:
        fold = str(row.get("outer_fold") or "")
        by_fold.setdefault(fold, []).append(
            float(row.get("net_excess_return", 0.0) or 0.0)
        )
    if not by_fold:
        return 0.0
    positive = sum(fmean(values) > 0.0 for values in by_fold.values())
    return positive / len(by_fold)


def _model_gate(
    *,
    mean_ic: float,
    positive_ic_ratio: float,
    base_metrics: Mapping[str, object],
    stress_metrics: Mapping[str, object],
    outer_block_positive_ratio: float,
    minimum_outer_test_periods: int,
) -> dict[str, bool]:
    return {
        "minimum_outer_test_periods": int(
            base_metrics.get("period_count", 0) or 0
        ) >= minimum_outer_test_periods,
        "mean_rank_ic_at_least_003": mean_ic >= 0.03,
        "positive_rank_ic_ratio_at_least_055": positive_ic_ratio >= 0.55,
        "base_average_net_excess_positive": float(
            base_metrics.get("average_net_excess_return", 0.0) or 0.0
        ) > 0.0,
        "base_positive_net_excess_ratio_at_least_half": float(
            base_metrics.get("positive_net_excess_ratio", 0.0) or 0.0
        ) >= 0.50,
        "base_relative_total_return_positive": float(
            base_metrics.get("relative_total_return", 0.0) or 0.0
        ) > 0.0,
        "base_turnover_at_most_half": float(
            base_metrics.get("mean_turnover", 1.0) or 1.0
        ) <= 0.50,
        "stress_relative_total_return_positive": float(
            stress_metrics.get("relative_total_return", 0.0) or 0.0
        ) > 0.0,
        "leave_best_period_out_relative_positive": float(
            base_metrics.get(
                "leave_best_period_out_relative_total_return", 0.0
            ) or 0.0
        ) > 0.0,
        "best_positive_excess_contribution_at_most_half": float(
            base_metrics.get(
                "best_positive_excess_contribution_share", 1.0
            ) or 1.0
        ) <= 0.50,
        "positive_outer_block_ratio_at_least_half": (
            outer_block_positive_ratio >= 0.50
        ),
        "cap_selected_only_from_prior_validation": True,
        "model_fixed_across_outer_blocks": True,
        "continuous_holdings_across_outer_blocks": True,
        "outer_test_blocks_non_overlapping": True,
        "random_split_not_used": True,
    }


def _summary_row(
    *,
    model: str,
    status: str,
    outer_fold_count: int,
    mean_ic: float,
    positive_ic_ratio: float,
    base_metrics: Mapping[str, object],
    stress_metrics: Mapping[str, object],
    block_positive_ratio: float,
    gate: Mapping[str, bool],
) -> dict[str, object]:
    result: dict[str, object] = {
        "model": model,
        "status": status,
        "outer_fold_count": outer_fold_count,
        "outer_test_period_count": int(
            base_metrics.get("period_count", 0) or 0
        ),
        "mean_rank_ic": mean_ic,
        "positive_rank_ic_ratio": positive_ic_ratio,
        "outer_block_positive_net_excess_ratio": block_positive_ratio,
    }
    for prefix, metrics in (
        ("base", base_metrics),
        ("stress", stress_metrics),
    ):
        for key, value in metrics.items():
            result[f"{prefix}_{key}"] = value
    result["gate_passed"] = all(gate.values())
    result["failed_gate_count"] = sum(not value for value in gate.values())
    result["failed_gates"] = "|".join(
        key for key, value in gate.items() if not value
    )
    result["model_fixed_across_outer_blocks"] = True
    result["cap_selected_only_from_prior_validation"] = True
    result["actionable"] = False
    return result


def model_wise_nested_evaluation(
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
    """Tune cap per model on inner validation and score independent outer tests."""
    if validation_months < 3:
        raise ValueError("MODEL_LAB_V15_VALIDATION_MONTHS_TOO_SMALL")
    if test_months < 1:
        raise ValueError("MODEL_LAB_V15_TEST_MONTHS_TOO_SMALL")
    if minimum_outer_test_periods < 3:
        raise ValueError("MODEL_LAB_V15_MINIMUM_OUTER_TEST_TOO_SMALL")
    caps = tuple(sorted(set(int(value) for value in replacement_caps)))
    if not caps or any(value < 0 or value > top_k for value in caps):
        raise ValueError("MODEL_LAB_V15_INVALID_REPLACEMENT_CAPS")
    config = cost or v13.DnseCashCostConfig()
    dates = sorted({
        str(row.get("test_date") or "")
        for row in prediction_rows
        if str(row.get("test_date") or "")
    })
    if len(dates) < validation_months + test_months:
        raise ValueError("MODEL_LAB_V15_INSUFFICIENT_OOS_DATES")
    models = v13._complete_candidate_models(
        prediction_rows,
        dates,
        candidate_models,
    )
    base_cache = v13._period_cache(
        prediction_rows,
        top_k=top_k,
        candidate_models=models,
        replacement_caps=caps,
        cost=config,
        slippage_bps=config.slippage_bps,
    )

    summary_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    outer_rows_all: list[dict[str, object]] = []
    stress_rows_all: list[dict[str, object]] = []
    gate_by_model: dict[str, dict[str, bool]] = {}
    model_details: dict[str, dict[str, object]] = {}

    for model in models:
        decisions: dict[str, dict[str, object]] = {}
        model_selections: list[dict[str, object]] = []
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
                    int,
                    dict[str, float | int],
                ]
            ] = []
            for cap in caps:
                validation_periods = v13._period_subset(
                    base_cache[(model, cap)],
                    validation_dates,
                )
                metrics = v13.v12.v11.capped_policy_metrics(
                    validation_periods
                )
                candidates.append((
                    v13._validation_key(
                        metrics,
                        cap=cap,
                        model_priority=0,
                    ),
                    cap,
                    metrics,
                ))
            _, selected_cap, validation_metrics = max(
                candidates,
                key=lambda item: item[0],
            )
            outer_fold = f"outer_{block_index + 1:02d}"
            selection = {
                "model": model,
                "outer_fold": outer_fold,
                "validation_start": validation_dates[0],
                "validation_end": validation_dates[-1],
                "test_start": test_dates[0],
                "test_end": test_dates[-1],
                "selected_replacement_cap": selected_cap,
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
                "validation_mean_turnover": validation_metrics[
                    "mean_turnover"
                ],
                "selection_uses_outer_test_labels": "false",
                "model_fixed_across_outer_blocks": "true",
                "actionable": "false",
            }
            selection_rows.append(selection)
            model_selections.append(selection)
            for day in test_dates:
                decisions[day] = {
                    "outer_fold": outer_fold,
                    "selected_model": model,
                    "selected_replacement_cap": selected_cap,
                }
            block_index += 1

        base_rows, stress_rows = v14._dynamic_outer_periods(
            prediction_rows,
            decisions=decisions,
            top_k=top_k,
            cost=config,
        )
        for row in base_rows:
            row["evaluation_protocol"] = "MODEL_WISE_NESTED_V15"
        for row in stress_rows:
            row["evaluation_protocol"] = "MODEL_WISE_NESTED_V15"
        outer_rows_all.extend(base_rows)
        stress_rows_all.extend(stress_rows)

        base_metrics = v13.v12.v11.capped_policy_metrics(base_rows)
        stress_metrics = v13.v12.v11.capped_policy_metrics(stress_rows)
        outer_dates = [str(row.get("signal_date") or "") for row in base_rows]
        ic_count, mean_ic, positive_ic_ratio = v13._rank_ic_for_model_dates(
            prediction_rows,
            model=model,
            dates=outer_dates,
        )
        block_positive_ratio = _outer_block_positive_ratio(base_rows)
        gate = _model_gate(
            mean_ic=mean_ic,
            positive_ic_ratio=positive_ic_ratio,
            base_metrics=base_metrics,
            stress_metrics=stress_metrics,
            outer_block_positive_ratio=block_positive_ratio,
            minimum_outer_test_periods=minimum_outer_test_periods,
        )
        passed = all(gate.values())
        status = (
            "HISTORICALLY_VALIDATED_REFERENCE"
            if passed
            else "HISTORICAL_REFERENCE_CANDIDATE"
            if mean_ic > 0.0
            and float(base_metrics["relative_total_return"]) > 0.0
            else "REJECTED"
        )
        summary_rows.append(_summary_row(
            model=model,
            status=status,
            outer_fold_count=len(model_selections),
            mean_ic=mean_ic,
            positive_ic_ratio=positive_ic_ratio,
            base_metrics=base_metrics,
            stress_metrics=stress_metrics,
            block_positive_ratio=block_positive_ratio,
            gate=gate,
        ))
        gate_by_model[model] = gate
        model_details[model] = {
            "status": status,
            "outer_fold_count": len(model_selections),
            "outer_test_period_count": int(base_metrics["period_count"]),
            "rank_ic_period_count": ic_count,
            "mean_rank_ic": mean_ic,
            "positive_rank_ic_ratio": positive_ic_ratio,
            "outer_block_positive_net_excess_ratio": block_positive_ratio,
            "selected_caps_by_outer_fold": [
                int(row["selected_replacement_cap"])
                for row in model_selections
            ],
            "base_metrics": base_metrics,
            "stress_metrics": stress_metrics,
            "gate": gate,
            "gate_passed": passed,
        }

    passed_rows = [row for row in summary_rows if bool(row["gate_passed"])]
    if passed_rows:
        champion_row = max(
            passed_rows,
            key=lambda row: (
                min(
                    float(row["base_relative_total_return"]),
                    float(row["stress_relative_total_return"]),
                ),
                float(row["base_leave_best_period_out_relative_total_return"]),
                float(row["mean_rank_ic"]),
                float(row["base_average_net_excess_return"]),
                -float(row["base_mean_turnover"]),
                str(row["model"]),
            ),
        )
        champion = str(champion_row["model"])
        overall_status = "HISTORICALLY_VALIDATED_REFERENCE"
    else:
        candidates = [
            row for row in summary_rows
            if str(row["status"]) == "HISTORICAL_REFERENCE_CANDIDATE"
        ]
        champion = "NO_MODEL_APPROVED"
        overall_status = (
            "HISTORICAL_REFERENCE_CANDIDATE"
            if candidates else "REJECTED"
        )

    summary_rows.sort(
        key=lambda row: (
            bool(row["gate_passed"]),
            float(row["stress_relative_total_return"]),
            float(row["base_relative_total_return"]),
            float(row["mean_rank_ic"]),
        ),
        reverse=True,
    )
    return {
        "status": overall_status,
        "historical_reference_model": champion,
        "historical_reference_gate_passed": champion != "NO_MODEL_APPROVED",
        "model_comparison_count": len(models),
        "candidate_models": list(models),
        "candidate_replacement_caps": list(caps),
        "validation_months": validation_months,
        "test_months": test_months,
        "minimum_outer_test_periods": minimum_outer_test_periods,
        "model_fixed_across_outer_blocks": True,
        "cap_selected_only_from_prior_validation": True,
        "continuous_holdings_across_outer_blocks": True,
        "outer_test_blocks_non_overlapping": True,
        "random_split_used": False,
        "winner_selected_after_all_outer_tests": True,
        "protocol_provenance": PROTOCOL_PROVENANCE,
        "actionable": False,
        "model_details": model_details,
        "gate_by_model": gate_by_model,
        "summary_rows": summary_rows,
        "selection_rows": selection_rows,
        "outer_rows": outer_rows_all,
        "stress_rows": stress_rows_all,
    }


def publish_v15_validation(
    output_dir: Path,
    *,
    cost: v13.DnseCashCostConfig,
    validation_months: int,
    test_months: int,
    minimum_outer_test_periods: int,
    replacement_caps: Sequence[int],
) -> dict[str, object]:
    output = Path(output_dir)
    predictions = v13._read_csv(output / "oos_predictions.csv")
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    contract = dict(summary.get("backtest_contract") or {})
    costs = dict(contract.get("costs") or {})
    top_k = int(float(costs.get("top_k", contract.get("top_k", 10)) or 10))
    result = model_wise_nested_evaluation(
        predictions,
        top_k=top_k,
        replacement_caps=replacement_caps,
        validation_months=validation_months,
        test_months=test_months,
        minimum_outer_test_periods=minimum_outer_test_periods,
        cost=cost,
    )

    summary_rows = list(result["summary_rows"])
    selection_rows = list(result["selection_rows"])
    outer_rows = list(result["outer_rows"])
    stress_rows = list(result["stress_rows"])
    if summary_rows:
        _write_csv(
            output / "nested_model_historical_validation_v15.csv",
            summary_rows,
            tuple(summary_rows[0]),
        )
    if selection_rows:
        _write_csv(
            output / "nested_model_policy_selection_v15.csv",
            selection_rows,
            tuple(selection_rows[0]),
        )
    if outer_rows:
        _write_csv(
            output / "nested_model_outer_test_periods_v15.csv",
            outer_rows,
            tuple(outer_rows[0]),
        )
    if stress_rows:
        _write_csv(
            output / "nested_model_outer_test_stress_periods_v15.csv",
            stress_rows,
            tuple(stress_rows[0]),
        )

    validation_contract = {
        "evaluation_unit": "MODEL_FAMILY",
        "model_switching_inside_outer_portfolio": False,
        "inner_selected_parameter": "MAX_VOLUNTARY_REPLACEMENTS",
        "cap_selected_only_from_prior_validation": True,
        "continuous_holdings_across_outer_blocks": True,
        "outer_test_blocks_non_overlapping": True,
        "winner_selected_after_all_outer_tests": True,
        "protocol_provenance": PROTOCOL_PROVENANCE,
        "future_holdout_required_for_historical_reference": False,
        "live_capital_approved": False,
        "actionable": False,
    }
    _write_csv(
        output / "nested_model_validation_contract_v15.csv",
        [validation_contract],
        tuple(validation_contract),
    )

    champion = str(result["historical_reference_model"])
    historical_pass = bool(result["historical_reference_gate_passed"])
    old_v14 = dict(summary.get("nested_historical_validation_v13") or {})
    summary["base_upgrade_schema_version"] = v14.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["v14_meta_selector_result"] = {
        "status": old_v14.get("status", "REJECTED"),
        "gate_passed": bool(old_v14.get("gate_passed", False)),
        "retained_for_diagnostic_only": True,
    }
    summary["nested_model_validation_v15"] = {
        key: value
        for key, value in result.items()
        if key not in {
            "summary_rows",
            "selection_rows",
            "outer_rows",
            "stress_rows",
        }
    }
    summary["nested_model_validation_contract_v15"] = validation_contract
    summary["historical_reference_gate_passed"] = historical_pass
    summary["historical_reference_model"] = champion
    summary["historical_reference_status"] = str(result["status"])
    summary["research_champion"] = champion
    summary["research_eligible"] = historical_pass
    summary["champion_reason"] = (
        "V15_MODEL_WISE_NESTED_OUTER_GATE_PASSED"
        if historical_pass
        else "V15_NO_MODEL_PASSED_MODEL_WISE_NESTED_GATE"
    )
    summary["evidence_grade"] = (
        "GREEN_HISTORICAL_REFERENCE"
        if historical_pass
        else "YELLOW_HISTORICAL_CANDIDATE"
        if str(result["status"]) == "HISTORICAL_REFERENCE_CANDIDATE"
        else "RED_NO_PREDICTIVE_VALUE"
    )
    summary["deployment_status"] = (
        "PAPER_REFERENCE_ONLY"
        if historical_pass else "NO_MODEL_APPROVED"
    )
    summary["forward_watchlist_published"] = False
    summary["live_capital_approved"] = False
    summary["actionable"] = False
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with (output / "model_lab_report.txt").open("a", encoding="utf-8") as stream:
        stream.write("\nMODEL LAB UPGRADE V15\n")
        stream.write(
            "Each model family is evaluated independently. Inner validation "
            "selects only the turnover cap; the model is fixed across all "
            "outer blocks and holdings remain continuous.\n"
        )
        stream.write(
            f"Historical model-wise status: {result['status']}; reference "
            f"model: {champion}; gate_passed={str(historical_pass).lower()}; "
            "actionable=false; live_capital_approved=false.\n"
        )
        stream.write(
            "Protocol provenance: revised after v14 meta-selector rejection; "
            "v14 remains a diagnostic and does not override v15.\n"
        )
    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "historical_reference_status": str(result["status"]),
        "historical_reference_model": champion,
        "historical_reference_gate_passed": historical_pass,
        "research_champion": champion,
        "forward_watchlist_published": False,
        "live_capital_approved": False,
        "actionable": False,
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    result = _BASE_RUN(**kwargs)
    cost = v13.DnseCashCostConfig(
        broker_buy_fee_bps=float(kwargs.get("dnse_broker_buy_fee_bps", 0.0)),
        broker_sell_fee_bps=float(kwargs.get("dnse_broker_sell_fee_bps", 0.0)),
        exchange_buy_fee_bps=float(kwargs.get("exchange_buy_fee_bps", 2.7)),
        exchange_sell_fee_bps=float(kwargs.get("exchange_sell_fee_bps", 2.7)),
        sell_tax_bps=float(kwargs.get("sell_tax_bps", 10.0)),
        transfer_fee_vnd_per_share=float(
            kwargs.get("transfer_fee_vnd_per_share", 0.3)
        ),
        transfer_reference_price_vnd=float(
            kwargs.get("transfer_reference_price_vnd", 10_000.0)
        ),
        slippage_bps=float(kwargs.get("slippage_bps", 5.0)),
        stress_slippage_bps=float(
            kwargs.get("stress_slippage_bps", 10.0)
        ),
    )
    validation = publish_v15_validation(
        Path(str(kwargs["output_dir"])),
        cost=cost,
        validation_months=int(kwargs.get("nested_validation_months", 6)),
        test_months=int(kwargs.get("nested_test_months", 3)),
        minimum_outer_test_periods=int(
            kwargs.get("minimum_outer_test_periods", 12)
        ),
        replacement_caps=tuple(
            int(value)
            for value in kwargs.get(
                "replacement_caps", v13.DEFAULT_REPLACEMENT_CAPS
            )
        ),
    )
    return {**result, **validation}


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
    "PROTOCOL_PROVENANCE",
    "model_wise_nested_evaluation",
    "publish_v15_validation",
    "run_model_lab",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
