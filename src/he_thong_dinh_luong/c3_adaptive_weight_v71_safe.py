"""Resource/provenance-safe entrypoint for V71.

Historical component values are anchored to the exact V67 training rows when
available.  Raw-store factor reconstruction remains an audit.  This prevents a
candidate from being compared with a numerically drifted reconstruction of the
frozen C3 baseline.  Unlabelled latest rows use direct causal raw-store factors.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from . import c3_adaptive_weight_v71 as base
from . import deep_portfolio_backtest_v70 as v70
from . import weekly_micro_capital_v43 as c3


def build_variant_candidates(*, variant_id: str, variant_dir: Path, market: v70.Market) -> dict[str, object]:
    grouped = base._group_rankings(base._read_gz(variant_dir / "v67_c3_monthly_rankings.csv.gz"))
    training = base._load_training(variant_dir / "v67_c3_training_rows.csv.gz")
    training_key = {(row.signal_day, row.symbol): row for row in training}
    ic_months = base._monthly_ics(training)
    recorded_weights = base._load_recorded_weights(variant_dir / "v67_c3_weight_history.csv")
    candidate_snaps = {candidate.candidate_id: [] for candidate in base.CANDIDATES}
    ranking_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    predictive_rows: list[dict[str, object]] = []
    overlap_rows: list[dict[str, object]] = []
    max_raw_factor_error = max_weight_error = max_score_error = 0.0
    rank_mismatch = raw_audit_count = 0

    for signal_day in sorted(grouped):
        baseline_rows = grouped[signal_day]
        symbols = [str(row["symbol"]).strip().upper() for row in baseline_rows]
        risk_on = base._bool(baseline_rows[0].get("risk_on"))
        components_by_symbol: dict[str, dict[str, float]] = {}
        component_source: dict[str, str] = {}
        for symbol in symbols:
            frozen = training_key.get((signal_day, symbol))
            raw = base.factor_components(market, symbol, signal_day)
            if frozen is not None:
                components = {name: float(frozen.components[name]) for name in base.COMPONENTS}
                component_source[symbol] = "V67_FROZEN_TRAINING_ROW"
                if raw is not None:
                    raw_audit_count += 1
                    for name in base.COMPONENTS:
                        max_raw_factor_error = max(max_raw_factor_error, abs(float(raw[name]) - components[name]))
            else:
                if raw is None:
                    raise ValueError(f"V71_LATEST_FACTOR_STATE_MISSING:{variant_id}:{signal_day}:{symbol}")
                components = {name: float(raw[name]) for name in base.COMPONENTS}
                component_source[symbol] = "DIRECT_RAW_STORE_CAUSAL_LATEST"
            components_by_symbol[symbol] = components

        candidate_top10: dict[str, tuple[str, ...]] = {}
        for candidate in base.CANDIDATES:
            weights, used = base.adaptive_weights(ic_months, signal_day=signal_day, candidate=candidate)
            if candidate.candidate_id == base.CHAMPION_MODEL:
                recorded = recorded_weights.get(signal_day)
                if recorded is None:
                    raise ValueError(f"V71_BASELINE_WEIGHT_MISSING:{signal_day}")
                for name in base.COMPONENTS:
                    max_weight_error = max(max_weight_error, abs(float(weights[name]) - float(recorded[name])))
            states = [{"symbol": symbol, **components_by_symbol[symbol]} for symbol in symbols]
            pct = {
                name: c3.average_percentile([float(row[name]) for row in states])
                for name in base.COMPONENTS
            }
            for index, row in enumerate(states):
                row["score"] = sum(float(weights[name]) * pct[name][index] for name in base.COMPONENTS)
            states.sort(key=lambda row: (-float(row["score"]), str(row["symbol"])))
            order = tuple(str(row["symbol"]) for row in states)
            candidate_top10[candidate.candidate_id] = order[:10]
            candidate_snaps[candidate.candidate_id].append(v70.Snap(signal_day, order[:10], risk_on))
            if candidate.candidate_id == base.CHAMPION_MODEL:
                if order != tuple(symbols):
                    rank_mismatch += 1
                frozen_scores = {str(row["symbol"]).strip().upper(): float(row["score"]) for row in baseline_rows}
                for row in states:
                    max_score_error = max(max_score_error, abs(float(row["score"]) - frozen_scores[str(row["symbol"])]))
            phase = "PRE2026_PRIMARY" if signal_day <= base.PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW"
            labels = [
                training_key[(signal_day, symbol)].relative_return
                for symbol in order[:10]
                if (signal_day, symbol) in training_key
            ]
            predictive_rows.append({
                "variant_id": variant_id,
                "candidate_id": candidate.candidate_id,
                "signal_day": signal_day.isoformat(),
                "phase": phase,
                "label_count": len(labels),
                "mean_top10_close_close20_excess": base.fmean(labels) if labels else None,
                "positive_label_rate": sum(value > 0 for value in labels) / len(labels) if labels else None,
                "used_for_candidate_selection": signal_day <= base.PRIMARY_SELECTION_END,
            })
            weight_rows.append({
                "variant_id": variant_id,
                "candidate_id": candidate.candidate_id,
                "mode": candidate.mode,
                "parameter": candidate.parameter,
                "signal_day": signal_day.isoformat(),
                "completed_ic_month_count_used": used,
                "weight_low_volatility": weights["low_volatility"],
                "weight_relative_strength_120": weights["relative_strength_120"],
                "weight_high_52_week": weights["high_52_week"],
                "uses_only_label_end_before_signal": True,
                "year_2026_used_for_selection": False,
            })
            baseline_rank = {symbol: index for index, symbol in enumerate(symbols, 1)}
            for rank, row in enumerate(states, 1):
                symbol = str(row["symbol"])
                frozen = training_key.get((signal_day, symbol))
                ranking_rows.append({
                    "variant_id": variant_id,
                    "candidate_id": candidate.candidate_id,
                    "signal_day": signal_day.isoformat(),
                    "symbol": symbol,
                    "rank": rank,
                    "baseline_rank": baseline_rank.get(symbol),
                    "score": row["score"],
                    "low_volatility": row["low_volatility"],
                    "relative_strength_120": row["relative_strength_120"],
                    "high_52_week": row["high_52_week"],
                    "component_source": component_source[symbol],
                    "risk_on": risk_on,
                    "relative_return_close_t_to_close_t20": frozen.relative_return if frozen else None,
                    "phase": phase,
                })
        frozen_top10 = set(candidate_top10[base.CHAMPION_MODEL])
        for candidate in base.CANDIDATES[1:]:
            current = set(candidate_top10[candidate.candidate_id])
            overlap_rows.append({
                "variant_id": variant_id,
                "candidate_id": candidate.candidate_id,
                "signal_day": signal_day.isoformat(),
                "top10_jaccard_vs_frozen_c3": len(current & frozen_top10) / len(current | frozen_top10),
                "exact_top10_match": current == frozen_top10,
                "changed_name_count": 10 - len(current & frozen_top10),
                "phase": "PRE2026_PRIMARY" if signal_day <= base.PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW",
            })

    if max_weight_error > 1e-10:
        raise ValueError(f"V71_FROZEN_WEIGHT_RECONSTRUCTION_DRIFT:{max_weight_error}")
    if max_score_error > 1e-10:
        raise ValueError(f"V71_FROZEN_SCORE_RECONSTRUCTION_DRIFT:{max_score_error}")
    if rank_mismatch:
        raise ValueError(f"V71_FROZEN_RANK_RECONSTRUCTION_DRIFT:{rank_mismatch}")
    ic_rows = [{
        "variant_id": variant_id,
        "signal_day": row.signal_day.isoformat(),
        "label_end": row.label_end.isoformat(),
        **{f"ic_{name}": row.values[name] for name in base.COMPONENTS},
    } for row in ic_months]
    return {
        "candidate_snaps": candidate_snaps,
        "ranking_rows": ranking_rows,
        "weight_rows": weight_rows,
        "predictive_rows": predictive_rows,
        "overlap_rows": overlap_rows,
        "ic_rows": ic_rows,
        "audit": {
            "historical_scoring_source": "V67_FROZEN_TRAINING_COMPONENTS_WHEN_AVAILABLE",
            "latest_unlabelled_scoring_source": "DIRECT_RAW_STORE_CAUSAL",
            "raw_factor_crosscheck_count": raw_audit_count,
            "max_raw_factor_crosscheck_error": max_raw_factor_error,
            "max_frozen_weight_reconstruction_error": max_weight_error,
            "max_frozen_score_reconstruction_error": max_score_error,
            "frozen_rank_mismatch_count": rank_mismatch,
        },
    }


def analyze(**kwargs):
    original = base.build_variant_candidates
    base.build_variant_candidates = build_variant_candidates
    try:
        report = base.analyze(**kwargs)
    finally:
        base.build_variant_candidates = original
    report["historical_component_provenance"] = "V67_FROZEN_TRAINING_ROWS"
    report["raw_factor_reconstruction_role"] = "AUDIT_ONLY_WHEN_FROZEN_COMPONENT_EXISTS"
    output_dir = Path(kwargs["output_dir"])
    (output_dir / "v71_report.json").write_text(
        base.json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    parser = base.argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signflip-samples", type=int, default=base.SIGNFLIP_SAMPLES)
    parser.add_argument("--bootstrap-samples", type=int, default=base.BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    report = analyze(
        v68_output=args.v68_output,
        v70_output=args.v70_output,
        store=args.store,
        output_dir=args.output_dir,
        signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(base.json.dumps({
        "schema_version": report["schema_version"],
        "status": report["status"],
        "champion_model": report["champion_model"],
        "diagnostic_watchlist_count": report["diagnostic_watchlist_count"],
        "year_2026_used_for_candidate_selection": report["year_2026_used_for_candidate_selection"],
        "promotion_authorized": report["promotion_authorized"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
