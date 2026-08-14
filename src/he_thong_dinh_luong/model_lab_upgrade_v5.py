"""Model Lab v5: honest policy provenance and future-holdout tracking.

The turnover buffer was proposed after reviewing the historical OOS artifact.
This layer corrects that provenance, keeps the policy non-actionable, and tracks
only genuinely future folds after the policy freeze date as holdout evidence.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v4 as v4

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v5"
POLICY_FREEZE_DATE = "2026-07-30"
MINIMUM_FUTURE_HOLDOUT_FOLDS = 12
POLICY_STRATEGY = "posthoc_fixed_top_k_retention_candidate"


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


def _float(row: Mapping[str, object], field: str) -> float:
    return float(row.get(field, 0.0) or 0.0)


def future_holdout_rows(
    buffered_periods: Sequence[Mapping[str, object]],
    baseline_periods: Sequence[Mapping[str, object]],
    *,
    freeze_date: str = POLICY_FREEZE_DATE,
    minimum_folds: int = MINIMUM_FUTURE_HOLDOUT_FOLDS,
) -> list[dict[str, object]]:
    """Compare only folds strictly after the policy was frozen.

    Passing this diagnostic never activates a model. The underlying base model
    must independently pass the unchanged Model Lab research gate.
    """
    if minimum_folds <= 0:
        raise ValueError("MODEL_LAB_HOLDOUT_MINIMUM_NONPOSITIVE")
    baseline_by_key = {
        (
            str(row.get("model") or ""),
            str(row.get("signal_date") or ""),
        ): row
        for row in baseline_periods
    }
    grouped: dict[str, list[tuple[Mapping[str, object], Mapping[str, object]]]] = {}
    for row in buffered_periods:
        model = str(row.get("model") or "")
        signal_date = str(row.get("signal_date") or "")
        if not model or not signal_date or signal_date <= freeze_date:
            continue
        baseline = baseline_by_key.get((model, signal_date))
        if baseline is not None:
            grouped.setdefault(model, []).append((row, baseline))

    models = sorted({
        str(row.get("model") or "")
        for row in buffered_periods
        if str(row.get("model") or "")
    })
    output: list[dict[str, object]] = []
    for model in models:
        pairs = sorted(
            grouped.get(model, []),
            key=lambda pair: str(pair[0].get("signal_date") or ""),
        )
        net_deltas = [
            _float(buffered, "net_return") - _float(baseline, "net_return")
            for buffered, baseline in pairs
        ]
        turnover_reductions = [
            _float(baseline, "turnover") - _float(buffered, "turnover")
            for buffered, baseline in pairs
        ]
        enough = len(pairs) >= minimum_folds
        mean_delta = fmean(net_deltas) if net_deltas else 0.0
        mean_turnover_reduction = (
            fmean(turnover_reductions) if turnover_reductions else 0.0
        )
        positive_delta_ratio = (
            fmean(1.0 if value > 0.0 else 0.0 for value in net_deltas)
            if net_deltas else 0.0
        )
        support = (
            enough
            and mean_delta > 0.0
            and mean_turnover_reduction > 0.0
            and positive_delta_ratio >= 0.50
        )
        status = (
            "FUTURE_HOLDOUT_SUPPORTS_POLICY_CANDIDATE"
            if support
            else (
                "FUTURE_HOLDOUT_DOES_NOT_SUPPORT_POLICY"
                if enough
                else "INSUFFICIENT_FUTURE_HOLDOUT"
            )
        )
        output.append({
            "model": model,
            "policy_freeze_date": freeze_date,
            "minimum_future_folds": minimum_folds,
            "future_fold_count": len(pairs),
            "first_future_signal_date": (
                str(pairs[0][0].get("signal_date") or "") if pairs else ""
            ),
            "last_future_signal_date": (
                str(pairs[-1][0].get("signal_date") or "") if pairs else ""
            ),
            "mean_net_return_delta_vs_top_k": mean_delta,
            "positive_net_delta_ratio": positive_delta_ratio,
            "mean_turnover_reduction_vs_top_k": mean_turnover_reduction,
            "status": status,
            "base_model_research_gate_still_required": "true",
            "actionable": "false",
        })
    return output


def publish_v5_provenance(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    diagnostic_path = output / "turnover_buffer_diagnostic.csv"
    periods_path = output / "turnover_buffer_periods.csv"
    baseline_path = output / "oos_backtest_periods.csv"

    diagnostics = _read_csv(diagnostic_path)
    buffered_periods = _read_csv(periods_path)
    baseline_periods = _read_csv(baseline_path)

    for row in diagnostics:
        row["strategy"] = POLICY_STRATEGY
        row["policy_provenance"] = "SELECTED_AFTER_REVIEWING_PRIOR_OOS"
        row["future_holdout_required"] = "true"
        row["policy_freeze_date"] = POLICY_FREEZE_DATE
        row["actionable"] = "false"
    for row in buffered_periods:
        row["strategy"] = POLICY_STRATEGY
        row["policy_provenance"] = "SELECTED_AFTER_REVIEWING_PRIOR_OOS"
        row["future_holdout_required"] = "true"
        row["policy_freeze_date"] = POLICY_FREEZE_DATE
        row["actionable"] = "false"

    diagnostic_fields = tuple(diagnostics[0]) if diagnostics else (
        "model", "strategy", "policy_provenance", "future_holdout_required",
        "policy_freeze_date", "actionable",
    )
    period_fields = tuple(buffered_periods[0]) if buffered_periods else (
        "model", "strategy", "signal_date", "policy_provenance",
        "future_holdout_required", "policy_freeze_date", "actionable",
    )
    diagnostic_fields = tuple(dict.fromkeys(
        (*diagnostic_fields, "policy_provenance", "future_holdout_required",
         "policy_freeze_date")
    ))
    period_fields = tuple(dict.fromkeys(
        (*period_fields, "policy_provenance", "future_holdout_required",
         "policy_freeze_date")
    ))
    _write_csv(diagnostic_path, diagnostics, diagnostic_fields)
    _write_csv(periods_path, buffered_periods, period_fields)

    holdout = future_holdout_rows(buffered_periods, baseline_periods)
    holdout_fields = (
        "model", "policy_freeze_date", "minimum_future_folds",
        "future_fold_count", "first_future_signal_date",
        "last_future_signal_date", "mean_net_return_delta_vs_top_k",
        "positive_net_delta_ratio", "mean_turnover_reduction_vs_top_k",
        "status", "base_model_research_gate_still_required", "actionable",
    )
    holdout_path = output / "turnover_buffer_future_holdout.csv"
    _write_csv(holdout_path, holdout, holdout_fields)

    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    prior = dict(summary.get("turnover_buffer_diagnostic") or {})
    prior.update({
        "status": "POSTHOC_POLICY_CANDIDATE",
        "strategy": POLICY_STRATEGY,
        "policy_provenance": "SELECTED_AFTER_REVIEWING_PRIOR_OOS",
        "predeclared_not_oos_optimized": False,
        "future_holdout_required": True,
        "policy_freeze_date": POLICY_FREEZE_DATE,
        "minimum_future_holdout_folds": MINIMUM_FUTURE_HOLDOUT_FOLDS,
        "base_model_research_gate_still_required": True,
        "research_gate_unchanged": True,
        "actionable": False,
        "files": [
            "turnover_buffer_diagnostic.csv",
            "turnover_buffer_periods.csv",
            "turnover_buffer_future_holdout.csv",
        ],
    })
    summary["base_upgrade_schema_version"] = v4.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["turnover_buffer_diagnostic"] = prior
    summary["turnover_buffer_future_holdout"] = {
        "status": (
            "NO_GENUINELY_FUTURE_FOLDS"
            if not holdout or max(
                int(row["future_fold_count"]) for row in holdout
            ) == 0
            else "FUTURE_FOLDS_OBSERVED"
        ),
        "policy_freeze_date": POLICY_FREEZE_DATE,
        "minimum_future_folds": MINIMUM_FUTURE_HOLDOUT_FOLDS,
        "base_model_research_gate_still_required": True,
        "actionable": False,
        "file": "turnover_buffer_future_holdout.csv",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output / "model_lab_report.txt").open("a", encoding="utf-8") as stream:
        stream.write("\nMODEL LAB UPGRADE V5\n")
        stream.write(
            "Turnover buffer provenance corrected: policy was selected after "
            "reviewing prior OOS and is not an independent holdout result.\n"
        )
        stream.write(
            f"Future holdout starts strictly after {POLICY_FREEZE_DATE}; "
            f"minimum folds={MINIMUM_FUTURE_HOLDOUT_FOLDS}; "
            "base research gate remains mandatory.\n"
        )
    quality_runner._rebuild_manifest_and_zip(output, summary)
    max_future = max(
        (int(row["future_fold_count"]) for row in holdout),
        default=0,
    )
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "turnover_buffer_status": "POSTHOC_POLICY_CANDIDATE",
        "turnover_buffer_policy_freeze_date": POLICY_FREEZE_DATE,
        "maximum_future_holdout_folds": max_future,
        "future_holdout_status": (
            "NO_GENUINELY_FUTURE_FOLDS"
            if max_future == 0
            else "FUTURE_FOLDS_OBSERVED"
        ),
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    result = v4.run_model_lab(**kwargs)
    provenance = publish_v5_provenance(Path(str(kwargs["output_dir"])))
    return {**result, **provenance}


def _parser():
    return v4._parser()


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
    "POLICY_FREEZE_DATE",
    "MINIMUM_FUTURE_HOLDOUT_FOLDS",
    "POLICY_STRATEGY",
    "future_holdout_rows",
    "publish_v5_provenance",
    "run_model_lab",
    "main",
]
