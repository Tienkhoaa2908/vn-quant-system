"""Boundary-safe entry point for V67 C3-native HOSE research.

Two contracts are enforced here:
1) monthly canonical snapshots are created only from completed months;
2) C3 component-IC training keeps the original close(T)->close(T+20) label,
   while tradable research outcomes remain next-session-open based.
"""
from __future__ import annotations

from datetime import date
from statistics import fmean
from typing import Mapping, Sequence

from . import c3_hose_native_v67 as core
from . import weekly_micro_capital_v43 as c3


def _monthly_days(calendar: Sequence[date], end: date) -> list[date]:
    by_month: dict[tuple[int, int], date] = {}
    end_key = (end.year, end.month)
    for day in calendar:
        key = (day.year, day.month)
        if day <= end and key < end_key:
            by_month[key] = day
    return [by_month[key] for key in sorted(by_month)]


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


# Patch core globals before any run. run_study resolves these names at runtime.
core._monthly_days = _monthly_days
core.build_monthly_c3 = _build_monthly_c3

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
run_study = core.run_study


def main(argv=None) -> int:
    core._monthly_days = _monthly_days
    core.build_monthly_c3 = _build_monthly_c3
    return core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
