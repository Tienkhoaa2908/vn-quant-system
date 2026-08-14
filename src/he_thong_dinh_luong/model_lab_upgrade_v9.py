"""Model Lab v9: zero-preserving strict-gate hotfix around v8.

V8 introduced the tail-aware objective and strict reference gate.  Its first CI
run exposed one fail-closed parsing defect: an explicit zero degenerate-fold
ratio was replaced by the fallback value through ``value or 1.0``.  This wrapper
preserves zero, keeps the complete v8 predictive policy unchanged, and records
the compatibility hotfix in the published summary.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v8 as v8

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v9"


def _number(
    row: Mapping[str, object],
    key: str,
    default: float,
) -> float:
    raw = row.get(key, default)
    if raw is None or raw == "":
        return float(default)
    return float(raw)


def strict_reference_gate(
    leaderboard_row: Mapping[str, object],
    *,
    mean_turnover: float,
    positive_component_count: int,
) -> dict[str, bool]:
    """V8 reference gate with explicit zeros preserved."""
    return {
        "enough_oos_folds": int(
            _number(leaderboard_row, "oos_folds", 0.0)
        ) >= 24,
        "mean_rank_ic_at_least_003": _number(
            leaderboard_row, "mean_rank_ic", 0.0
        ) >= 0.03,
        "positive_rank_ic_ratio_at_least_055": _number(
            leaderboard_row, "positive_rank_ic_ratio", 0.0
        ) >= 0.55,
        "top_k_relative_return_positive": _number(
            leaderboard_row, "top_k_relative_return", 0.0
        ) > 0.0,
        "average_net_excess_positive": _number(
            leaderboard_row, "average_net_excess_return", 0.0
        ) > 0.0,
        "positive_net_excess_ratio_at_least_half": _number(
            leaderboard_row, "positive_net_excess_ratio", 0.0
        ) >= 0.50,
        "relative_total_return_positive": _number(
            leaderboard_row, "relative_total_return", 0.0
        ) > 0.0,
        "turnover_controlled": float(mean_turnover) <= 0.60,
        "no_degenerate_folds": _number(
            leaderboard_row, "degenerate_fold_ratio", 1.0
        ) == 0.0,
        "two_independent_positive_components": (
            int(positive_component_count) >= 2
        ),
    }


def _publish_hotfix_metadata(output_dir: Path) -> None:
    output = Path(output_dir)
    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    summary["base_upgrade_schema_version"] = v8.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["predictive_upgrade_v9"] = {
        "strict_gate_zero_preserved": True,
        "predictive_policy_changed": False,
        "research_gate_relaxed": False,
        "actionable": False,
    }
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    quality_runner._rebuild_manifest_and_zip(output, summary)


def run_model_lab(**kwargs: object) -> dict[str, object]:
    original_gate = v8.strict_reference_gate
    v8.strict_reference_gate = strict_reference_gate
    try:
        result = v8.run_model_lab(**kwargs)
    finally:
        v8.strict_reference_gate = original_gate
    _publish_hotfix_metadata(Path(str(kwargs["output_dir"])))
    return {**result, "upgrade_schema_version": SCHEMA_VERSION}


def _parser():
    return v8._parser()


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


_top_tail_target = v8._top_tail_target
_tail_relevance = v8._tail_relevance
_tail_validation_key = v8._tail_validation_key
select_score_orientation = v8.select_score_orientation

__all__ = [
    "SCHEMA_VERSION",
    "_number",
    "_top_tail_target",
    "_tail_relevance",
    "_tail_validation_key",
    "select_score_orientation",
    "strict_reference_gate",
    "run_model_lab",
    "main",
]
