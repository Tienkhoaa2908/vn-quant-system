"""Boundary-safe entry point for V67 C3-native HOSE research.

Contracts enforced here:
1) monthly canonical snapshots are created only from completed months;
2) C3 component-IC training keeps the original close(T)->close(T+20) label;
3) tradable research outcomes remain next-session-open based;
4) start-only exchange metadata that looks like a static current mapping is rejected.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import c3_hose_native_v67 as core
from . import weekly_micro_capital_v43 as c3

_ORIGINAL_MEMBERSHIP_INTERVALS = core._membership_intervals


def _monthly_days(calendar: Sequence[date], end: date) -> list[date]:
    by_month: dict[tuple[int, int], date] = {}
    end_key = (end.year, end.month)
    for day in calendar:
        key = (day.year, day.month)
        if day <= end and key < end_key:
            by_month[key] = day
    return [by_month[key] for key in sorted(by_month)]


def _strict_membership_intervals(db, source: core.VenueSource):
    result = _ORIGINAL_MEMBERSHIP_INTERVALS(db, source)
    if source.mode == "INTERVAL" and source.start_col and source.end_col is None:
        repeated_history = False
        for items in result.values():
            starts = {start for start, _, _ in items if start is not None}
            if len(starts) >= 2:
                repeated_history = True
                break
        if not repeated_history:
            raise ValueError("V67_START_ONLY_STATIC_LIKE_EXCHANGE_METADATA_NOT_ACCEPTED")
    return result


def _c3_training_label(*, market: core.Market, symbol: str, signal_day: date, calendar_index: Mapping[date, int], horizon: int = 20) -> dict[str, object] | None:
    """Original M4/C3 label: close at T to close at T+H, benchmark-relative."""
    pos = calendar_index.get(signal_day)
    if pos is None:
        return None
    target_pos = pos + horizon
    if target_pos >= len(market.calendar):
        return None
    target_day = market.calendar[target_pos]
    stock_start = market.stock_close.get((symbol, signal_day))
    stock_end = market.stock_close.get((symbol, target_day))
    index_start = market.index_close.get(signal_day)
    index_end = market.index_close.get(target_day)
    if not all(value is not None and value > 0 for value in (stock_start, stock_end, index_start, index_end)):
        return None
    stock_return = float(stock_end) / float(stock_start) - 1.0
    index_return = float(index_end) / float(index_start) - 1.0
    return {
        "label_end": target_day,
        "stock_return": stock_return,
        "benchmark_return": index_return,
        "relative_return": stock_return - index_return,
    }


def _build_monthly_c3(*, market: core.Market, analysis_end: date) -> tuple[list[core.C3Snapshot], list[c3.ResearchRow], list[dict[str, object]], list[dict[str, object]]]:
    calendar_index = {day: idx for idx, day in enumerate(market.calendar)}
    training_rows: list[c3.ResearchRow] = []
    snapshots: list[core.C3Snapshot] = []
    ranking_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    for signal_day in _monthly_days(market.calendar, analysis_end):
        states = [state for symbol in market.symbols if (state := core.feature_state(market=market, symbol=symbol, evaluation_day=signal_day, calendar_index=calendar_index)) is not None]
        current = [state for state in states if state.eligible]
        history = [row for row in training_rows if row.signal_day < signal_day and row.label_end < signal_day]
        history_months = len({row.signal_day for row in history})
        if history_months >= 12 and current:
            weights = c3.shrunk_component_weights(history)
            ranking, scores = core.score_states(current, weights)
            pos = calendar_index[signal_day]
            risk_on = pos >= 249 and market.index_close[signal_day] >= fmean(market.index_close[day] for day in market.calendar[pos - 249:pos + 1])
            snapshot = core.C3Snapshot(signal_day, ranking, scores, dict(weights), risk_on, len(current), history_months)
            snapshots.append(snapshot)
            for rank, symbol in enumerate(ranking, start=1):
                ranking_rows.append({
                    "signal_day": signal_day.isoformat(),
                    "symbol": symbol,
                    "rank": rank,
                    "score": scores[symbol],
                    "risk_on": str(risk_on).lower(),
                    "eligible_count": len(current),
                })
            weight_rows.append({
                "signal_day": signal_day.isoformat(),
                "history_months": history_months,
                "weight_low_volatility": weights["low_volatility"],
                "weight_relative_strength_120": weights["relative_strength_120"],
                "weight_high_52_week": weights["high_52_week"],
                "uses_only_completed_past_labels": "true",
                "c3_training_label": "CLOSE_T_TO_CLOSE_T_PLUS_20",
            })
        for state in current:
            label = _c3_training_label(market=market, symbol=state.symbol, signal_day=signal_day, calendar_index=calendar_index, horizon=20)
            if label is None:
                continue
            training_rows.append(c3.ResearchRow(
                signal_day=signal_day,
                label_end=label["label_end"],
                symbol=state.symbol,
                relative_return=float(label["relative_return"]),
                volatility_60=abs(state.low_volatility),
                risk_on=False,
                components={
                    "low_volatility": state.low_volatility,
                    "relative_strength_120": state.relative_strength_120,
                    "high_52_week": state.high_52_week,
                },
            ))
    return snapshots, training_rows, ranking_rows, weight_rows


def run_study(*, store: Path, output_dir: Path, historical_end: date = core.HISTORICAL_END_DEFAULT, analysis_end: date = core.ANALYSIS_END_DEFAULT, price_multiplier: float = core.PRICE_MULTIPLIER_DEFAULT) -> dict[str, object]:
    market = core.load_market(store, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, market.calendar[-1])
    snapshots, training_rows, rankings, weights = _build_monthly_c3(market=market, analysis_end=effective_end)
    baseline = core.monthly_baseline_metrics(market=market, snapshots=snapshots, historical_end=historical_end)
    states, events, shadow_focus = core.weekly_c3_cohorts(market=market, snapshots=snapshots, historical_end=historical_end, analysis_end=effective_end)
    metrics = core.aggregate_cohort_metrics(events, historical_end)
    output_dir.mkdir(parents=True, exist_ok=True)
    training_dump = [
        {
            "signal_day": row.signal_day.isoformat(),
            "label_end": row.label_end.isoformat(),
            "symbol": row.symbol,
            "relative_return_close_t_to_close_t20": row.relative_return,
            "low_volatility": row.components["low_volatility"],
            "relative_strength_120": row.components["relative_strength_120"],
            "high_52_week": row.components["high_52_week"],
        }
        for row in training_rows
    ]
    core._write_gzip_csv(output_dir / "v67_c3_training_rows.csv.gz", training_dump)
    core._write_csv(output_dir / "v67_c3_weight_history.csv", weights)
    core._write_gzip_csv(output_dir / "v67_c3_monthly_rankings.csv.gz", rankings)
    core._write_csv(output_dir / "v67_c3_monthly_top10_metrics.csv", baseline)
    core._write_gzip_csv(output_dir / "v67_weekly_signal_states.csv.gz", states)
    core._write_gzip_csv(output_dir / "v67_cohort_events.csv.gz", events)
    core._write_csv(output_dir / "v67_cohort_metrics.csv", metrics)
    core._write_csv(output_dir / "v67_shadow_focus_vpi_tlg_baf.csv", shadow_focus)
    report = {
        "schema_version": core.SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": core.CHAMPION_MODEL,
        "champion_replaced": False,
        "challenger_models_run": False,
        "workstation_environment_contract": "vn_quant_local_system/.venv",
        "training_source": "LOCAL_POINT_IN_TIME_HOSE_MARKET_STORE",
        "c3_training_label_contract": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE",
        "tradable_outcome_contract": "NEXT_SESSION_OPEN_TO_FUTURE_OPEN",
        "v22_used_as_training_input": False,
        "static_current_hose_mapping_allowed": False,
        "start_only_static_like_exchange_metadata_allowed": False,
        "completed_month_only": True,
        "venue_source_mode": market.venue_source.mode,
        "venue_source_table": market.venue_source.table,
        "store_first_day": market.calendar[0].isoformat(),
        "store_last_day": market.calendar[-1].isoformat(),
        "analysis_end_effective": effective_end.isoformat(),
        "historical_selection_end": historical_end.isoformat(),
        "august_2026_shadow_only": True,
        "historical_selection_uses_august_2026": False,
        "hose_symbol_count_seen": len(market.symbols),
        "monthly_snapshot_count": len(snapshots),
        "c3_training_row_count": len(training_rows),
        "monthly_ranking_row_count": len(rankings),
        "weekly_signal_state_count": len(states),
        "cohort_event_count": len(events),
        "cohort_hypothesis_count": len(core.cohort_contract.ALL_COHORTS),
        "shadow_focus_row_count": len(shadow_focus),
        "c3_weight_training": "ONLY_LABELS_COMPLETED_BEFORE_EACH_SIGNAL_DAY",
        "research_only": True,
        "live_model_change_authorized": False,
        "automatic_live_orders_allowed": False,
        "limitations": [
            "corporate-action and price-basis lineage must still be audited before live promotion",
            "cohort events are overlapping observations and are not independent samples",
            "August 2026 is shadow-only and cannot be used to tune thresholds",
            "portfolio-level benefit requires a later exposure-normalized simulation",
            "challenger ML is intentionally deferred until this C3-native HOSE baseline is verified",
        ],
    }
    (output_dir / "v67_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


# Patch core globals before any run. Functions resolve these names at runtime.
core._monthly_days = _monthly_days
core._membership_intervals = _strict_membership_intervals
core.build_monthly_c3 = _build_monthly_c3
core.run_study = run_study

CHAMPION_MODEL = core.CHAMPION_MODEL
SCHEMA_VERSION = core.SCHEMA_VERSION
VenueSource = core.VenueSource
Market = core.Market
FeatureState = core.FeatureState
C3Snapshot = core.C3Snapshot
resolve_venue_source = core.resolve_venue_source
score_states = core.score_states
_canonical_snapshot = core._canonical_snapshot
_forward_outcome = core._forward_outcome


def main(argv=None) -> int:
    core._monthly_days = _monthly_days
    core._membership_intervals = _strict_membership_intervals
    core.build_monthly_c3 = _build_monthly_c3
    core.run_study = run_study
    return core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
