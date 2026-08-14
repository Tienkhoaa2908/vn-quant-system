"""Model Lab v10: positive diversified ensemble and weight-contract audit.

The v9 workstation rerun showed that the tail-aware learners improved as
individual models, while the inherited v6 polarity ensemble remained aligned
to broad prior IC and materially damaged the investable Top-K tail.  V10 makes
one deliberately simple research-policy change:

* combine the available HistGB, LightGBM and XGBoost rankers with fixed,
  positive, equal weights;
* never invert a rank through a negative ensemble weight;
* derive component-count evidence from the weights actually used on the latest
  fold, rather than from a separate diagnostic list;
* keep the policy non-actionable because it was selected after reviewing the
  2026-07-30 OOS artifact and therefore requires genuinely future holdout.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v6 as v6
from . import model_lab_upgrade_v8 as v8
from . import model_lab_upgrade_v9 as v9
from .model_lab_core import ENSEMBLE_MODEL

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v10"
ENSEMBLE_POLICY_FREEZE_DATE = "2026-08-01"
MINIMUM_FUTURE_ENSEMBLE_FOLDS = 12
FIXED_POSITIVE_TREE_COMPONENTS = (
    "hist_gradient_boosting_ranker",
    "lightgbm_ranker",
    "xgboost_ranker",
)


def positive_diversified_tree_weights(
    prior_ic: Mapping[str, Sequence[float]],
    available_models: Sequence[str],
    *,
    max_weight: float = 0.55,
    minimum_history: int = 6,
    minimum_consistency: float = 0.50,
) -> dict[str, float]:
    """Return deterministic positive weights without using fold labels.

    ``prior_ic`` and the threshold arguments remain in the signature for
    compatibility with the legacy online-weight hook.  They are intentionally
    ignored: the selected policy is a fixed, post-hoc research candidate whose
    only unbiased evaluation can come from folds after the policy freeze.
    """
    del prior_ic, max_weight, minimum_history, minimum_consistency
    available = {
        str(name)
        for name in available_models
        if str(name) != ENSEMBLE_MODEL
    }
    selected = [
        name for name in FIXED_POSITIVE_TREE_COMPONENTS
        if name in available
    ]
    if not selected:
        fallback_order = (
            "ridge_ranker",
            "robust_technical_ensemble_v1",
            "momentum_baseline",
        )
        selected = [
            name for name in fallback_order
            if name in available
        ][:1]
    if not selected:
        selected = sorted(available)[:1]
    if not selected:
        raise ValueError("MODEL_LAB_ENSEMBLE_NO_BASE_MODELS")
    weight = 1.0 / len(selected)
    return {name: weight for name in selected}


def latest_weight_contract(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Summarize the components actually used on the latest OOS fold."""
    if not rows:
        return {
            "latest_test_date": "",
            "positive_components": [],
            "negative_components": [],
            "nonzero_component_count": 0,
            "positive_component_count": 0,
            "negative_component_count": 0,
            "weights_sum": 0.0,
            "absolute_weights_sum": 0.0,
            "no_negative_weights": False,
        }
    latest = max(str(row.get("test_date") or "") for row in rows)
    latest_rows = [
        row for row in rows
        if str(row.get("test_date") or "") == latest
    ]
    weighted = [
        (str(row.get("base_model") or ""), float(row.get("weight", 0.0) or 0.0))
        for row in latest_rows
        if str(row.get("base_model") or "")
    ]
    positive = sorted(name for name, weight in weighted if weight > 0.0)
    negative = sorted(name for name, weight in weighted if weight < 0.0)
    nonzero = [name for name, weight in weighted if weight != 0.0]
    return {
        "latest_test_date": latest,
        "positive_components": positive,
        "negative_components": negative,
        "nonzero_component_count": len(nonzero),
        "positive_component_count": len(positive),
        "negative_component_count": len(negative),
        "weights_sum": sum(weight for _, weight in weighted),
        "absolute_weights_sum": sum(abs(weight) for _, weight in weighted),
        "no_negative_weights": not negative and bool(positive),
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


def publish_v10_ensemble_contract(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    weights = _read_csv(output / "ensemble_weights_oos.csv")
    leaderboard = _read_csv(output / "model_leaderboard.csv")
    periods = _read_csv(output / "oos_backtest_periods.csv")
    predictions = _read_csv(output / "oos_predictions.csv")
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))

    contract = latest_weight_contract(weights)
    ensemble_row = next(
        (
            row for row in leaderboard
            if str(row.get("model") or "") == ENSEMBLE_MODEL
        ),
        {},
    )
    ensemble_periods = [
        row for row in periods
        if str(row.get("model") or "") == ENSEMBLE_MODEL
    ]
    mean_turnover = (
        fmean(float(row.get("turnover", 0.0) or 0.0) for row in ensemble_periods)
        if ensemble_periods else 1.0
    )
    strict_gate = v9.strict_reference_gate(
        ensemble_row,
        mean_turnover=mean_turnover,
        positive_component_count=int(contract["positive_component_count"]),
    ) if ensemble_row else {}
    strict_gate["no_negative_ensemble_weights"] = bool(
        contract["no_negative_weights"]
    )
    historical_pass = bool(strict_gate) and all(strict_gate.values())

    diagnostics: list[dict[str, object]] = []
    for row in weights:
        weight = float(row.get("weight", 0.0) or 0.0)
        diagnostics.append({
            "fold": row.get("fold", ""),
            "test_date": row.get("test_date", ""),
            "base_model": row.get("base_model", ""),
            "weight": weight,
            "polarity": (
                "POSITIVE" if weight > 0.0
                else ("NEGATIVE" if weight < 0.0 else "ZERO")
            ),
            "prior_fold_count": row.get("prior_fold_count", ""),
            "current_fold_label_used_for_weight": "false",
            "actionable": "false",
        })
    _write_csv(
        output / "ensemble_alignment_diagnostic.csv",
        diagnostics,
        (
            "fold",
            "test_date",
            "base_model",
            "weight",
            "polarity",
            "prior_fold_count",
            "current_fold_label_used_for_weight",
            "actionable",
        ),
    )

    holdout = v6.future_predictive_holdout_rows(
        predictions,
        periods,
        freeze_date=ENSEMBLE_POLICY_FREEZE_DATE,
        minimum_folds=MINIMUM_FUTURE_ENSEMBLE_FOLDS,
    )
    _write_csv(
        output / "predictive_v10_future_holdout.csv",
        holdout,
        (
            "model",
            "policy_freeze_date",
            "minimum_future_folds",
            "future_fold_count",
            "first_future_signal_date",
            "last_future_signal_date",
            "mean_rank_ic",
            "positive_rank_ic_ratio",
            "net_total_return",
            "benchmark_total_return",
            "relative_total_return",
            "mean_turnover",
            "status",
            "actionable",
        ),
    )
    future_support = any(
        str(row.get("model") or "") == ENSEMBLE_MODEL
        and str(row.get("status") or "")
        == "FUTURE_HOLDOUT_SUPPORTS_PREDICTIVE_REFERENCE"
        for row in holdout
    )

    original_champion = str(
        summary.get("research_champion") or "NO_MODEL_APPROVED"
    )
    summary["base_upgrade_schema_version"] = v9.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["ensemble_positive_components"] = list(
        contract["positive_components"]
    )
    summary["final_ensemble_weights_contract_v10"] = contract
    summary["predictive_upgrade_v10"] = {
        "ensemble_policy": "FIXED_POSITIVE_DIVERSIFIED_TREE_BLEND",
        "configured_components": list(FIXED_POSITIVE_TREE_COMPONENTS),
        "actual_latest_weight_contract": contract,
        "negative_polarity_allowed": False,
        "component_count_uses_actual_weights": True,
        "strict_reference_gate": strict_gate,
        "strict_reference_gate_passed": historical_pass,
        "policy_provenance": "SELECTED_AFTER_REVIEWING_2026_07_30_OOS",
        "policy_freeze_date": ENSEMBLE_POLICY_FREEZE_DATE,
        "minimum_future_folds": MINIMUM_FUTURE_ENSEMBLE_FOLDS,
        "future_holdout_support": future_support,
        "research_gate_relaxed": False,
        "actionable": False,
        "files": [
            "ensemble_alignment_diagnostic.csv",
            "predictive_v10_future_holdout.csv",
        ],
    }
    summary["v10_historical_champion_before_provenance_block"] = (
        original_champion
    )
    if not (historical_pass and future_support):
        summary["research_champion"] = "NO_MODEL_APPROVED"
        summary["champion_reason"] = (
            "V10_ENSEMBLE_GATE_OR_FUTURE_HOLDOUT_NOT_MET"
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
        stream.write("\nMODEL LAB UPGRADE V10\n")
        stream.write(
            "Ensemble policy: fixed positive equal-weight blend across "
            "available HistGB, LightGBM and XGBoost rankers.\n"
        )
        stream.write(
            "Negative rank polarity is disabled; component evidence is "
            "derived from the latest weights actually used.\n"
        )
        stream.write(
            f"Strict historical ensemble gate: {str(historical_pass).lower()}; "
            f"future holdout support: {str(future_support).lower()}; "
            "actionable=false.\n"
        )

    quality_runner._rebuild_manifest_and_zip(output, summary)
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "strict_ensemble_reference_gate_passed": historical_pass,
        "future_ensemble_holdout_support": future_support,
        "actual_positive_component_count": int(
            contract["positive_component_count"]
        ),
        "negative_ensemble_weights": int(
            contract["negative_component_count"]
        ),
        "research_champion": summary["research_champion"],
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    original_weights = v6.polarity_online_weights
    v6.polarity_online_weights = positive_diversified_tree_weights
    try:
        result = v9.run_model_lab(**kwargs)
    finally:
        v6.polarity_online_weights = original_weights
    diagnostics = publish_v10_ensemble_contract(
        Path(str(kwargs["output_dir"]))
    )
    return {**result, **diagnostics}


def _parser():
    return v9._parser()


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
    "ENSEMBLE_POLICY_FREEZE_DATE",
    "MINIMUM_FUTURE_ENSEMBLE_FOLDS",
    "FIXED_POSITIVE_TREE_COMPONENTS",
    "positive_diversified_tree_weights",
    "latest_weight_contract",
    "publish_v10_ensemble_contract",
    "run_model_lab",
    "main",
]
