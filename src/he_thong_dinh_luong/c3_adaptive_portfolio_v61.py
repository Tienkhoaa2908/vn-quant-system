"""V61 adaptive C3 portfolio-policy research.

Research question
-----------------
V60 showed that blindly buying every new weekly Preview Top-5/Top-10 did not
survive costs, while canonical leaders that collapsed outside Preview Top-20
showed materially weaker forward behaviour.  V61 therefore studies portfolio
*policy* rather than replacing C3 stock selection:

* route new capital toward canonical leaders that remain preview-confirmed;
* freeze adds to weakening/broken canonical leaders;
* partial trims after confirmed preview breakdown, with hysteresis;
* rotate trim proceeds only into still-confirmed canonical leaders;
* small tactical sleeves for new preview leaders only when extra confirmation
  (persistence / volume / extension / rank-velocity) is present.

All preview information is observed at a completed weekly close and can affect
trading only at a later session open.  The current August-2026 VPI episode is
outside the default analysis end and is never used for parameter selection.

V60 already consumed the former 2022+ holdout, so V61 does NOT claim a pristine
untouched holdout.  It reports cross-era/year robustness and cost-stress results
and never authorizes a live policy change by itself.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import dataclass
from datetime import date
import io
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import c3_short_horizon_v60 as v60
from . import weekly_micro_capital_v43 as v43

SCHEMA_VERSION = "c3_adaptive_portfolio_v61"
ANALYSIS_END_DEFAULT = date(2026, 7, 31)
SYMBOL_CAP = 0.15


@dataclass(frozen=True)
class Policy:
    policy_id: str
    route_mode: str = "ALL"
    trim_fraction: float = 0.0
    breakdown_hits_required: int = 0
    hysteresis: bool = False
    rotate_trim_cash: bool = False
    minimum_signal_age_sessions: int = 0
    tactical_filter: str = "NONE"
    tactical_fraction: float = 0.0
    tactical_horizon_sessions: int = 10


POLICIES: tuple[Policy, ...] = (
    Policy("BASELINE_P1"),
    Policy("ROUTE_CONFIRMED10", route_mode="CONFIRMED10"),
    Policy("NOADD_BREAKDOWN20", route_mode="NOT_BREAKDOWN20"),
    Policy("TRIM25_BREAK1", route_mode="NOT_BREAKDOWN20", trim_fraction=0.25, breakdown_hits_required=1),
    Policy("TRIM25_BREAK2", route_mode="NOT_BREAKDOWN20", trim_fraction=0.25, breakdown_hits_required=2),
    Policy("TRIM50_BREAK2", route_mode="NOT_BREAKDOWN20", trim_fraction=0.50, breakdown_hits_required=2),
    Policy("HYST_TRIM25_BREAK2", route_mode="NOT_BREAKDOWN20", trim_fraction=0.25, breakdown_hits_required=2, hysteresis=True),
    Policy("ROTATE25_BREAK2", route_mode="CONFIRMED10", trim_fraction=0.25, breakdown_hits_required=2, hysteresis=True, rotate_trim_cash=True),
    Policy("ROTATE50_BREAK2", route_mode="CONFIRMED10", trim_fraction=0.50, breakdown_hits_required=2, hysteresis=True, rotate_trim_cash=True),
    Policy("AGE10_TRIM25_BREAK2", route_mode="NOT_BREAKDOWN20", trim_fraction=0.25, breakdown_hits_required=2, hysteresis=True, minimum_signal_age_sessions=10),
    Policy("AGE15_TRIM25_BREAK2", route_mode="NOT_BREAKDOWN20", trim_fraction=0.25, breakdown_hits_required=2, hysteresis=True, minimum_signal_age_sessions=15),
    Policy("TACT_PERSIST5_F05_H10", tactical_filter="PERSIST_TOP5", tactical_fraction=0.05),
    Policy("TACT_VOLUME5_F05_H10", tactical_filter="VOLUME_TOP5", tactical_fraction=0.05),
    Policy("TACT_VELOCITY5_F05_H10", tactical_filter="VELOCITY_TOP5", tactical_fraction=0.05),
    Policy("TACT_COMBO5_F05_H10", tactical_filter="COMBO_TOP5", tactical_fraction=0.05),
    Policy("TACT_COMBO5_F10_H10", tactical_filter="COMBO_TOP5", tactical_fraction=0.10),
    Policy(
        "ADAPTIVE_ROTATE25_TACT5",
        route_mode="CONFIRMED10",
        trim_fraction=0.25,
        breakdown_hits_required=2,
        hysteresis=True,
        rotate_trim_cash=True,
        tactical_filter="COMBO_TOP5",
        tactical_fraction=0.05,
    ),
)
POLICY_BY_ID = {policy.policy_id: policy for policy in POLICIES}


@dataclass(frozen=True)
class PreviewState:
    observation_day: date
    canonical_day: date
    ranking: tuple[str, ...]
    rank_by_symbol: Mapping[str, int]
    score_by_symbol: Mapping[str, float]
    volume_ratio_5_20: Mapping[str, float]
    return_5: Mapping[str, float]
    distance_ma20: Mapping[str, float]
    prior_rank_by_symbol: Mapping[str, int]


@dataclass
class TacticalLot:
    quantity: int
    entry_day: date
    entry_cost_vnd: float


def _safe_mean(values: Sequence[float]) -> float:
    return fmean(values) if values else 0.0


def _annualized(total_return: float, first_day: date, last_day: date) -> float:
    elapsed = max((last_day - first_day).days, 1)
    if total_return <= -1.0:
        return -1.0
    return (1.0 + total_return) ** (365.25 / elapsed) - 1.0


def _calendar_index(calendar: Sequence[date]) -> dict[date, int]:
    return {day: index for index, day in enumerate(calendar)}


def _latest_preview_before(
    trade_day: date,
    observation_days: Sequence[date],
    states: Mapping[date, PreviewState],
) -> PreviewState | None:
    index = bisect.bisect_left(observation_days, trade_day) - 1
    if index < 0:
        return None
    return states.get(observation_days[index])


def _market_features(
    *,
    symbol: str,
    day: date,
    market: v60.Market,
    calendar_index: Mapping[date, int],
) -> tuple[float, float, float]:
    position = calendar_index.get(day)
    if position is None or position < 20:
        return 0.0, 0.0, 0.0
    calendar = market.calendar
    days20 = calendar[position - 19 : position + 1]
    days5 = calendar[position - 4 : position + 1]
    close = market.stock_close.get((symbol, day))
    close5 = market.stock_close.get((symbol, calendar[position - 5])) if position >= 5 else None
    closes20 = [market.stock_close.get((symbol, item)) for item in days20]
    if close is None or close5 is None or any(value is None for value in closes20):
        return 0.0, 0.0, 0.0
    vols5 = [float(market.stock_volume.get((symbol, item), 0)) for item in days5]
    vols20 = [float(market.stock_volume.get((symbol, item), 0)) for item in days20]
    avg20 = _safe_mean(vols20)
    volume_ratio = _safe_mean(vols5) / avg20 if avg20 > 0 else 0.0
    return5 = float(close) / float(close5) - 1.0
    ma20 = _safe_mean([float(value) for value in closes20 if value is not None])
    distance = float(close) / ma20 - 1.0 if ma20 > 0 else 0.0
    return volume_ratio, return5, distance


def build_preview_states(
    *,
    rows: Sequence[v43.ResearchRow],
    snapshots: Sequence[v43.SignalSnapshot],
    market: v60.Market,
    analysis_end: date,
) -> dict[date, PreviewState]:
    """Build weekly-close preview states once; all simulations reuse them."""
    signal_days = [snapshot.day for snapshot in snapshots]
    universe_by_signal = v60._universe_by_signal(rows)
    calendar_index = _calendar_index(market.calendar)
    observation_days = v60._weekly_signal_days(market.calendar, end=analysis_end)
    states: dict[date, PreviewState] = {}
    prior_ranks: dict[str, int] = {}
    for observation_day in observation_days:
        canonical = v60._canonical_snapshot_for_day(
            snapshots,
            signal_days,
            observation_day,
        )
        if canonical is None:
            continue
        universe = universe_by_signal.get(canonical.day, tuple(canonical.ranking))
        ranking_rows = v60._preview_ranking(
            evaluation_day=observation_day,
            canonical=canonical,
            universe=universe,
            market=market,
            calendar_index=calendar_index,
        )
        if not ranking_rows:
            continue
        ranking = tuple(row.symbol for row in ranking_rows)
        rank_by_symbol = {row.symbol: row.rank for row in ranking_rows}
        score_by_symbol = {row.symbol: row.score for row in ranking_rows}
        volume_ratio: dict[str, float] = {}
        return5: dict[str, float] = {}
        distance20: dict[str, float] = {}
        for symbol in ranking:
            vr, r5, d20 = _market_features(
                symbol=symbol,
                day=observation_day,
                market=market,
                calendar_index=calendar_index,
            )
            volume_ratio[symbol] = vr
            return5[symbol] = r5
            distance20[symbol] = d20
        states[observation_day] = PreviewState(
            observation_day=observation_day,
            canonical_day=canonical.day,
            ranking=ranking,
            rank_by_symbol=rank_by_symbol,
            score_by_symbol=score_by_symbol,
            volume_ratio_5_20=volume_ratio,
            return_5=return5,
            distance_ma20=distance20,
            prior_rank_by_symbol=dict(prior_ranks),
        )
        prior_ranks = rank_by_symbol
    return states


def _preview_rank(state: PreviewState | None, symbol: str) -> int:
    if state is None:
        return 10**9
    return int(state.rank_by_symbol.get(symbol, 10**9))


def _preview_valid_for_snapshot(
    state: PreviewState | None,
    snapshot: v43.SignalSnapshot,
) -> bool:
    return state is not None and state.canonical_day == snapshot.day


def _route_targets(
    *,
    policy: Policy,
    canonical_targets: Sequence[str],
    preview: PreviewState | None,
    snapshot: v43.SignalSnapshot,
) -> list[str]:
    if policy.route_mode == "ALL" or not _preview_valid_for_snapshot(preview, snapshot):
        return list(canonical_targets)
    if policy.route_mode == "CONFIRMED10":
        return [symbol for symbol in canonical_targets if _preview_rank(preview, symbol) <= 10]
    if policy.route_mode == "NOT_BREAKDOWN20":
        return [symbol for symbol in canonical_targets if _preview_rank(preview, symbol) <= 20]
    raise ValueError(f"V61_UNKNOWN_ROUTE_MODE:{policy.route_mode}")


def tactical_candidate(
    *,
    policy: Policy,
    preview: PreviewState | None,
    snapshot: v43.SignalSnapshot,
    held_symbols: set[str],
) -> str | None:
    """Return one filtered new preview leader, or None.

    Thresholds are intentionally pre-declared, not optimized on V60's former
    holdout: persistence, moderate volume acceleration, and anti-extension.
    """
    if policy.tactical_filter == "NONE" or preview is None:
        return None
    if not _preview_valid_for_snapshot(preview, snapshot):
        return None
    canonical_top10 = set(snapshot.ranking[:10])
    new_top5 = [
        symbol for symbol in preview.ranking[:5]
        if symbol not in canonical_top10 and symbol not in held_symbols
    ]
    for symbol in new_top5:
        rank = _preview_rank(preview, symbol)
        previous = int(preview.prior_rank_by_symbol.get(symbol, 10**9))
        volume_ratio = float(preview.volume_ratio_5_20.get(symbol, 0.0))
        return5 = float(preview.return_5.get(symbol, 0.0))
        distance = float(preview.distance_ma20.get(symbol, 0.0))
        persistent = previous <= 5
        not_extended = return5 <= 0.10 and distance <= 0.08
        volume_ok = volume_ratio >= 1.15
        velocity_ok = 6 <= previous <= 20 and 2 <= previous - rank <= 15
        if policy.tactical_filter == "PERSIST_TOP5" and persistent:
            return symbol
        if policy.tactical_filter == "VOLUME_TOP5" and volume_ok and not_extended:
            return symbol
        if policy.tactical_filter == "VELOCITY_TOP5" and velocity_ok and volume_ratio >= 1.0 and not_extended:
            return symbol
        if policy.tactical_filter == "COMBO_TOP5" and persistent and volume_ok and not_extended:
            return symbol
    return None


def _sessions_between(calendar_index: Mapping[date, int], start: date, end: date) -> int:
    left = calendar_index.get(start)
    right = calendar_index.get(end)
    if left is None or right is None:
        return 0
    return max(right - left, 0)


def _update_average_cost(old_qty: int, old_cost: float, add_qty: int, add_total: float) -> float:
    new_qty = old_qty + add_qty
    if new_qty <= 0:
        return 0.0
    old_total = old_qty * old_cost
    return (old_total + add_total) / new_qty


def _execute_sell(
    *,
    symbol: str,
    quantity: int,
    trade_day: date,
    prices: v43.PriceStore,
    slippage_bps: float,
) -> tuple[float, float, float] | None:
    raw_price = prices.opens.get((symbol, trade_day))
    if raw_price is None or quantity <= 0:
        return None
    proceeds = v43._sell_proceeds(float(raw_price), quantity, slippage_bps)
    gross = float(raw_price) * quantity
    return proceeds, gross, gross - proceeds


def _position_cap_quantity(
    *,
    symbol: str,
    current_qty: int,
    budget: float,
    account_value: float,
    trade_day: date,
    prices: v43.PriceStore,
    slippage_bps: float,
) -> int:
    raw_price = prices.opens.get((symbol, trade_day))
    if raw_price is None or account_value <= 0:
        return 0
    affordable = v43.affordable_quantity(budget, float(raw_price), slippage_bps)
    max_value = SYMBOL_CAP * account_value
    current_value = current_qty * float(raw_price)
    cap_gap = max(max_value - current_value, 0.0)
    cap_qty = int(cap_gap // max(float(raw_price), 1e-12))
    return max(min(affordable, cap_qty), 0)


def _custom_simulate(
    *,
    policy: Policy,
    contribution: int,
    scenario: str,
    snapshots: Sequence[v43.SignalSnapshot],
    prices: v43.PriceStore,
    weekly_days: Sequence[date],
    preview_states: Mapping[date, PreviewState],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slippage_bps = float(v43.SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    observation_days = sorted(preview_states)
    calendar_index = _calendar_index(prices.calendar)

    cash = 0.0
    holdings: dict[str, int] = {}
    average_cost: dict[str, float] = {}
    peak_mark: dict[str, float] = {}
    outside_counts: dict[str, int] = {}
    breakdown_hits: dict[str, int] = {}
    trimmed_episode: dict[str, bool] = {}
    recent_trim_week: dict[str, int] = {}
    tactical_lots: dict[str, TacticalLot] = {}
    current_signal_index = -1
    current_snapshot: v43.SignalSnapshot | None = None
    round_robin_pointer = 0

    fund_units = 0.0
    unit_price = 1.0
    peak_unit_price = 1.0
    max_drawdown = 0.0
    contributions_total = 0.0
    fees_total = 0.0
    gross_turnover = 0.0
    buy_count = 0
    sell_count = 0
    trim_count = 0
    tactical_candidate_count = 0
    tactical_buy_count = 0
    tactical_exit_count = 0
    tactical_promotion_count = 0
    whipsaw_recovery_count = 0
    single_name_damage_weeks = 0
    worst_single_name_unrealized_nav = 0.0
    worst_weighted_peak_drawdown_nav = 0.0
    missing_trade_bar_count = 0
    stale_valuation_count = 0
    cashflows: list[tuple[date, float]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []
    weekly_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    for week_number, trade_day in enumerate(weekly_days, start=1):
        snapshot_index = bisect.bisect_left(signal_days, trade_day) - 1
        if snapshot_index < 0:
            continue
        signal_changed = snapshot_index != current_signal_index
        if signal_changed:
            current_signal_index = snapshot_index
            current_snapshot = snapshots[snapshot_index]
        assert current_snapshot is not None
        preview = _latest_preview_before(trade_day, observation_days, preview_states)
        preview_valid = _preview_valid_for_snapshot(preview, current_snapshot)

        value_before, stale_before = v43._account_value(cash, holdings, prices, trade_day, use_open=True)
        stale_valuation_count += stale_before
        if fund_units > 0.0:
            unit_price = value_before / fund_units
        issued_units = contribution / max(unit_price, 1e-12)
        fund_units += issued_units
        cash += contribution
        contributions_total += contribution
        cashflows.append((trade_day, -float(contribution)))
        index_open = prices.index_open.get(trade_day)
        if index_open and index_open > 0.0:
            benchmark_units += contribution / index_open
            benchmark_cashflows.append((trade_day, -float(contribution)))

        # Original P1 monthly buffered exit remains active for every policy.
        monthly_exits: list[str] = []
        if signal_changed:
            rank_by_symbol = {symbol: rank for rank, symbol in enumerate(current_snapshot.ranking, start=1)}
            monthly_exits = v43.compute_exit_symbols(
                holdings,
                rank_by_symbol,
                outside_counts,
                exit_rank=20,
                exit_months=2,
            )
        for symbol in monthly_exits:
            quantity = holdings.get(symbol, 0)
            execution = _execute_sell(
                symbol=symbol,
                quantity=quantity,
                trade_day=trade_day,
                prices=prices,
                slippage_bps=slippage_bps,
            )
            if execution is None:
                missing_trade_bar_count += 1
                continue
            proceeds, gross, cost = execution
            cash += proceeds
            fees_total += cost
            gross_turnover += gross
            holdings[symbol] = 0
            average_cost[symbol] = 0.0
            peak_mark.pop(symbol, None)
            tactical_lots.pop(symbol, None)
            outside_counts[symbol] = 0
            breakdown_hits[symbol] = 0
            trimmed_episode[symbol] = False
            sell_count += 1
            trade_rows.append({
                "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                "trade_day": trade_day.isoformat(), "side": "SELL_P1", "symbol": symbol,
                "quantity": quantity, "gross_reference_vnd": gross, "cash_effect_vnd": proceeds,
                "preview_rank": _preview_rank(preview, symbol) if preview_valid else "",
            })

        canonical_top10 = list(current_snapshot.ranking[:10])
        canonical_set = set(canonical_top10)

        # Tactical positions become core automatically if a new monthly canonical
        # signal later promotes them into Top-10.  No needless round trip.
        for symbol in list(tactical_lots):
            if symbol in canonical_set and holdings.get(symbol, 0) > 0:
                tactical_lots.pop(symbol, None)
                tactical_promotion_count += 1
                trade_rows.append({
                    "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                    "trade_day": trade_day.isoformat(), "side": "TACTICAL_PROMOTED_TO_CORE",
                    "symbol": symbol, "quantity": holdings.get(symbol, 0),
                    "gross_reference_vnd": 0.0, "cash_effect_vnd": 0.0,
                })

        # Fixed-horizon tactical exits, executed only at this later weekly open.
        for symbol, lot in list(tactical_lots.items()):
            if holdings.get(symbol, 0) <= 0:
                tactical_lots.pop(symbol, None)
                continue
            age = _sessions_between(calendar_index, lot.entry_day, trade_day)
            rank = _preview_rank(preview, symbol) if preview_valid else 10**9
            if age < policy.tactical_horizon_sessions and rank <= 20:
                continue
            quantity = min(lot.quantity, holdings.get(symbol, 0))
            execution = _execute_sell(
                symbol=symbol, quantity=quantity, trade_day=trade_day,
                prices=prices, slippage_bps=slippage_bps,
            )
            if execution is None:
                missing_trade_bar_count += 1
                continue
            proceeds, gross, cost = execution
            cash += proceeds
            fees_total += cost
            gross_turnover += gross
            holdings[symbol] -= quantity
            tactical_lots.pop(symbol, None)
            tactical_exit_count += 1
            sell_count += 1
            if holdings[symbol] <= 0:
                average_cost[symbol] = 0.0
                peak_mark.pop(symbol, None)
            trade_rows.append({
                "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                "trade_day": trade_day.isoformat(), "side": "SELL_TACTICAL",
                "symbol": symbol, "quantity": quantity, "gross_reference_vnd": gross,
                "cash_effect_vnd": proceeds, "tactical_age_sessions": age,
                "preview_rank": rank if preview_valid else "",
            })

        # Preview breakdown state and optional one-trim-per-episode action.
        trim_proceeds_this_week = 0.0
        if preview_valid:
            signal_age = _sessions_between(calendar_index, current_snapshot.day, preview.observation_day)
            for symbol in canonical_top10:
                if holdings.get(symbol, 0) <= 0:
                    continue
                rank = _preview_rank(preview, symbol)
                if rank > 20:
                    breakdown_hits[symbol] = breakdown_hits.get(symbol, 0) + 1
                elif rank <= 10:
                    if symbol in recent_trim_week and week_number - recent_trim_week[symbol] <= 2:
                        whipsaw_recovery_count += 1
                        recent_trim_week.pop(symbol, None)
                    breakdown_hits[symbol] = 0
                    trimmed_episode[symbol] = False
                elif not policy.hysteresis:
                    breakdown_hits[symbol] = 0
                    trimmed_episode[symbol] = False

                eligible_trim = (
                    policy.trim_fraction > 0.0
                    and policy.breakdown_hits_required > 0
                    and breakdown_hits.get(symbol, 0) >= policy.breakdown_hits_required
                    and not trimmed_episode.get(symbol, False)
                    and signal_age >= policy.minimum_signal_age_sessions
                )
                if not eligible_trim:
                    continue
                quantity = int(math.floor(holdings[symbol] * policy.trim_fraction))
                # A 1-share holding cannot be partially trimmed.  Do not silently
                # turn a 25% research trim into a 100% forced exit.
                if quantity <= 0 or quantity >= holdings[symbol]:
                    continue
                execution = _execute_sell(
                    symbol=symbol, quantity=quantity, trade_day=trade_day,
                    prices=prices, slippage_bps=slippage_bps,
                )
                if execution is None:
                    missing_trade_bar_count += 1
                    continue
                proceeds, gross, cost = execution
                cash += proceeds
                trim_proceeds_this_week += proceeds
                fees_total += cost
                gross_turnover += gross
                holdings[symbol] -= quantity
                trim_count += 1
                sell_count += 1
                trimmed_episode[symbol] = True
                recent_trim_week[symbol] = week_number
                trade_rows.append({
                    "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                    "trade_day": trade_day.isoformat(), "side": "SELL_PREVIEW_TRIM",
                    "symbol": symbol, "quantity": quantity, "gross_reference_vnd": gross,
                    "cash_effect_vnd": proceeds, "preview_rank": rank,
                    "breakdown_hits": breakdown_hits.get(symbol, 0),
                    "signal_age_sessions": signal_age,
                })

        # Determine one optional tactical candidate using only the prior weekly
        # close.  Candidate evaluation itself never sees today's open/close.
        candidate = tactical_candidate(
            policy=policy,
            preview=preview if preview_valid else None,
            snapshot=current_snapshot,
            held_symbols={symbol for symbol, quantity in holdings.items() if quantity > 0},
        )
        if candidate is not None:
            tactical_candidate_count += 1

        # Tactical budget is a small reserved fraction of this week's new cash.
        tactical_budget = min(cash, contribution * policy.tactical_fraction) if candidate else 0.0
        account_value_open, _ = v43._account_value(cash, holdings, prices, trade_day, use_open=True)
        if candidate and tactical_budget > 0.0:
            quantity = _position_cap_quantity(
                symbol=candidate,
                current_qty=holdings.get(candidate, 0),
                budget=tactical_budget,
                account_value=account_value_open,
                trade_day=trade_day,
                prices=prices,
                slippage_bps=slippage_bps,
            )
            raw_price = prices.opens.get((candidate, trade_day))
            if quantity > 0 and raw_price is not None:
                total_cost = v43._buy_total(float(raw_price), quantity, slippage_bps)
                if total_cost <= cash + 1e-8:
                    old_qty = holdings.get(candidate, 0)
                    average_cost[candidate] = _update_average_cost(
                        old_qty, average_cost.get(candidate, 0.0), quantity, total_cost
                    )
                    holdings[candidate] = old_qty + quantity
                    cash -= total_cost
                    gross = float(raw_price) * quantity
                    fees_total += total_cost - gross
                    gross_turnover += gross
                    tactical_lots[candidate] = TacticalLot(quantity=quantity, entry_day=trade_day, entry_cost_vnd=total_cost)
                    tactical_buy_count += 1
                    buy_count += 1
                    tactical_budget = total_cost
                    trade_rows.append({
                        "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                        "trade_day": trade_day.isoformat(), "side": "BUY_TACTICAL",
                        "symbol": candidate, "quantity": quantity, "gross_reference_vnd": gross,
                        "cash_effect_vnd": -total_cost,
                        "preview_rank": _preview_rank(preview, candidate),
                        "volume_ratio_5_20": preview.volume_ratio_5_20.get(candidate, 0.0) if preview else 0.0,
                        "return_5": preview.return_5.get(candidate, 0.0) if preview else 0.0,
                        "distance_ma20": preview.distance_ma20.get(candidate, 0.0) if preview else 0.0,
                    })
                else:
                    tactical_budget = 0.0
            else:
                tactical_budget = 0.0

        # Core budget: baseline uses at most one contribution.  If tactical did
        # not consume its reserve the cash is released back to core.  Rotation
        # policies may additionally recycle this week's trim proceeds.
        core_cap = float(contribution)
        if policy.rotate_trim_cash:
            core_cap += trim_proceeds_this_week
        core_budget = min(cash, core_cap)
        canonical_targets = list(current_snapshot.ranking[:10])
        target_symbols = _route_targets(
            policy=policy,
            canonical_targets=canonical_targets,
            preview=preview if preview_valid else None,
            snapshot=current_snapshot,
        )
        target_weights_all = v43.capped_inverse_vol_weights(
            current_snapshot.ranking,
            current_snapshot.volatility,
            target_count=10,
            symbol_cap=SYMBOL_CAP,
        )
        target_weights = {symbol: target_weights_all.get(symbol, 0.0) for symbol in target_symbols}
        buy_symbol = None
        buy_quantity = 0
        if target_symbols and core_budget > 0.0:
            account_value_open, _ = v43._account_value(cash, holdings, prices, trade_day, use_open=True)
            buy_symbol, round_robin_pointer = v43._choose_buy_symbol(
                rule="UNDERWEIGHT",
                target_symbols=target_symbols,
                target_weights=target_weights,
                holdings=holdings,
                prices=prices,
                day=trade_day,
                account_value=account_value_open,
                budget=core_budget,
                slippage_bps=slippage_bps,
                round_robin_pointer=round_robin_pointer,
            )
        if buy_symbol is not None:
            raw_price = float(prices.opens[(buy_symbol, trade_day)])
            buy_quantity = v43.affordable_quantity(core_budget, raw_price, slippage_bps)
            total_cost = v43._buy_total(raw_price, buy_quantity, slippage_bps)
            while buy_quantity > 0 and total_cost > cash + 1e-8:
                buy_quantity -= 1
                total_cost = v43._buy_total(raw_price, buy_quantity, slippage_bps)
            if buy_quantity > 0:
                old_qty = holdings.get(buy_symbol, 0)
                average_cost[buy_symbol] = _update_average_cost(
                    old_qty, average_cost.get(buy_symbol, 0.0), buy_quantity, total_cost
                )
                holdings[buy_symbol] = old_qty + buy_quantity
                cash -= total_cost
                gross = raw_price * buy_quantity
                fees_total += total_cost - gross
                gross_turnover += gross
                buy_count += 1
                trade_rows.append({
                    "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                    "trade_day": trade_day.isoformat(), "side": "BUY_CORE",
                    "symbol": buy_symbol, "quantity": buy_quantity,
                    "gross_reference_vnd": gross, "cash_effect_vnd": -total_cost,
                    "preview_rank": _preview_rank(preview, buy_symbol) if preview_valid else "",
                    "route_mode": policy.route_mode,
                })

        end_value, stale_end = v43._account_value(cash, holdings, prices, trade_day, use_open=False)
        stale_valuation_count += stale_end
        unit_price = end_value / fund_units if fund_units > 0 else 1.0
        peak_unit_price = max(peak_unit_price, unit_price)
        drawdown = unit_price / peak_unit_price - 1.0
        max_drawdown = min(max_drawdown, drawdown)

        live_positions = {symbol: quantity for symbol, quantity in holdings.items() if quantity > 0}
        largest_weight = 0.0
        weekly_worst_unrealized = 0.0
        weekly_worst_peak = 0.0
        damage_count = 0
        for symbol, quantity in live_positions.items():
            mark = prices.latest_close(symbol, trade_day)
            if mark is None or end_value <= 0.0:
                continue
            largest_weight = max(largest_weight, quantity * mark / end_value)
            peak_mark[symbol] = max(float(peak_mark.get(symbol, mark)), float(mark))
            cost_basis = average_cost.get(symbol, 0.0)
            if cost_basis > 0.0:
                unrealized_nav = quantity * (float(mark) - cost_basis) / end_value
                weekly_worst_unrealized = min(weekly_worst_unrealized, unrealized_nav)
                if unrealized_nav <= -0.01:
                    damage_count += 1
            peak_damage = quantity * (float(mark) - peak_mark[symbol]) / end_value
            weekly_worst_peak = min(weekly_worst_peak, peak_damage)
        worst_single_name_unrealized_nav = min(worst_single_name_unrealized_nav, weekly_worst_unrealized)
        worst_weighted_peak_drawdown_nav = min(worst_weighted_peak_drawdown_nav, weekly_worst_peak)
        single_name_damage_weeks += damage_count

        weekly_rows.append({
            "policy": policy.policy_id,
            "contribution": contribution,
            "scenario": scenario,
            "week_number": week_number,
            "trade_day": trade_day.isoformat(),
            "signal_day": current_snapshot.day.isoformat(),
            "preview_day": preview.observation_day.isoformat() if preview_valid and preview else "",
            "risk_on": str(current_snapshot.risk_on).lower(),
            "weekly_contribution_vnd": contribution,
            "buy_symbol": buy_symbol or "",
            "buy_quantity": buy_quantity,
            "tactical_candidate": candidate or "",
            "cash_vnd": cash,
            "portfolio_value_vnd": end_value,
            "unit_price": unit_price,
            "drawdown": drawdown,
            "position_count": len(live_positions),
            "largest_symbol_weight": largest_weight,
            "weekly_worst_single_name_unrealized_nav": weekly_worst_unrealized,
            "weekly_worst_weighted_peak_drawdown_nav": weekly_worst_peak,
            "single_name_damage_count_1pct": damage_count,
        })

    if not weekly_rows:
        raise ValueError("V61_NO_WEEKLY_SIMULATION_ROWS")
    first_day = date.fromisoformat(str(weekly_rows[0]["trade_day"]))
    final_day = date.fromisoformat(str(weekly_rows[-1]["trade_day"]))
    final_value = float(weekly_rows[-1]["portfolio_value_vnd"])
    cashflows.append((final_day, final_value))
    index_close = prices.index_close.get(final_day)
    benchmark_final = benchmark_units * index_close if index_close else 0.0
    benchmark_cashflows.append((final_day, benchmark_final))
    portfolio_xirr = v43.xirr(cashflows)
    benchmark_xirr = v43.xirr(benchmark_cashflows)
    total_return = unit_price - 1.0
    annualized_return = _annualized(total_return, first_day, final_day)
    summary = {
        "policy": policy.policy_id,
        "contribution": contribution,
        "scenario": scenario,
        "first_trade_day": first_day.isoformat(),
        "final_day": final_day.isoformat(),
        "week_count": len(weekly_rows),
        "total_contributed_vnd": contributions_total,
        "final_value_vnd": final_value,
        "absolute_profit_vnd": final_value - contributions_total,
        "xirr": portfolio_xirr,
        "benchmark_xirr": benchmark_xirr,
        "xirr_excess": portfolio_xirr - benchmark_xirr if portfolio_xirr is not None and benchmark_xirr is not None else None,
        "unitized_total_return": total_return,
        "annualized_unitized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "calmar": annualized_return / abs(max_drawdown) if max_drawdown < 0 else None,
        "ending_cash_vnd": cash,
        "ending_cash_ratio": cash / final_value if final_value > 0 else 0.0,
        "largest_symbol_weight": max(float(row["largest_symbol_weight"]) for row in weekly_rows),
        "buy_order_count": buy_count,
        "sell_order_count": sell_count,
        "preview_trim_count": trim_count,
        "tactical_candidate_count": tactical_candidate_count,
        "tactical_buy_count": tactical_buy_count,
        "tactical_exit_count": tactical_exit_count,
        "tactical_promotion_count": tactical_promotion_count,
        "whipsaw_recovery_count_2w": whipsaw_recovery_count,
        "worst_single_name_unrealized_nav": worst_single_name_unrealized_nav,
        "worst_weighted_peak_drawdown_nav": worst_weighted_peak_drawdown_nav,
        "single_name_damage_weeks_1pct": single_name_damage_weeks,
        "estimated_total_cost_vnd": fees_total,
        "gross_turnover_vnd": gross_turnover,
        "turnover_to_contributions": gross_turnover / contributions_total if contributions_total > 0 else 0.0,
        "missing_trade_bar_count": missing_trade_bar_count,
        "stale_valuation_count": stale_valuation_count,
        "live_capital_approved": False,
    }
    return summary, weekly_rows, trade_rows


def _yearly_metrics(weekly_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by_key: dict[tuple[str, int, str], list[Mapping[str, object]]] = {}
    for row in weekly_rows:
        day = date.fromisoformat(str(row["trade_day"]))
        key = (str(row["policy"]), int(row["contribution"]), str(row["scenario"]))
        by_key.setdefault(key, []).append(row)
    output: list[dict[str, object]] = []
    for (policy, contribution, scenario), rows in sorted(by_key.items()):
        rows = sorted(rows, key=lambda item: str(item["trade_day"]))
        start_unit = 1.0
        current_year = None
        year_rows: list[Mapping[str, object]] = []
        for row in rows + [None]:
            row_year = date.fromisoformat(str(row["trade_day"])).year if row is not None else None
            if current_year is None and row is not None:
                current_year = row_year
            if row is not None and row_year == current_year:
                year_rows.append(row)
                continue
            if year_rows:
                peak = start_unit
                max_dd = 0.0
                for item in year_rows:
                    unit = float(item["unit_price"])
                    peak = max(peak, unit)
                    max_dd = min(max_dd, unit / peak - 1.0)
                end_unit = float(year_rows[-1]["unit_price"])
                output.append({
                    "policy": policy,
                    "contribution": contribution,
                    "scenario": scenario,
                    "year": current_year,
                    "unitized_return": end_unit / start_unit - 1.0,
                    "max_drawdown": max_dd,
                    "worst_single_name_unrealized_nav": min(float(item["weekly_worst_single_name_unrealized_nav"]) for item in year_rows),
                    "single_name_damage_weeks_1pct": sum(int(item["single_name_damage_count_1pct"]) for item in year_rows),
                })
                start_unit = end_unit
            year_rows = [row] if row is not None else []
            current_year = row_year
    return output


def _baseline_compare(
    summaries: Sequence[Mapping[str, object]],
    yearly: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    baseline = {
        (int(row["contribution"]), str(row["scenario"])): row
        for row in summaries if row["policy"] == "BASELINE_P1"
    }
    yearly_base = {
        (int(row["contribution"]), str(row["scenario"]), int(row["year"])): row
        for row in yearly if row["policy"] == "BASELINE_P1"
    }
    result: list[dict[str, object]] = []
    for policy in POLICIES:
        if policy.policy_id == "BASELINE_P1":
            continue
        cells = [row for row in summaries if row["policy"] == policy.policy_id]
        if not cells:
            continue
        return_diffs: list[float] = []
        dd_diffs: list[float] = []
        tail_diffs: list[float] = []
        cost_diffs: list[float] = []
        return_wins = dd_wins = tail_wins = 0
        severe_diffs: list[float] = []
        for row in cells:
            base = baseline[(int(row["contribution"]), str(row["scenario"]))]
            rdiff = float(row["annualized_unitized_return"]) - float(base["annualized_unitized_return"])
            ddiff = float(row["max_drawdown"]) - float(base["max_drawdown"])
            tdiff = float(row["worst_single_name_unrealized_nav"]) - float(base["worst_single_name_unrealized_nav"])
            cdiff = float(row["estimated_total_cost_vnd"]) - float(base["estimated_total_cost_vnd"])
            return_diffs.append(rdiff)
            dd_diffs.append(ddiff)
            tail_diffs.append(tdiff)
            cost_diffs.append(cdiff)
            return_wins += int(rdiff > 0)
            dd_wins += int(ddiff > 0)
            tail_wins += int(tdiff > 0)
            if str(row["scenario"]) == "SEVERE":
                severe_diffs.append(rdiff)
        year_wins = year_total = 0
        for row in yearly:
            if row["policy"] != policy.policy_id:
                continue
            key = (int(row["contribution"]), str(row["scenario"]), int(row["year"]))
            base = yearly_base.get(key)
            if base is None:
                continue
            year_total += 1
            year_wins += int(float(row["unitized_return"]) > float(base["unitized_return"]))
        robust = bool(
            median(return_diffs) > 0.0
            and return_wins >= 6
            and median(dd_diffs) >= -0.01
            and dd_wins >= 4
            and median(severe_diffs or [-1.0]) >= 0.0
            and year_total > 0
            and year_wins / year_total >= 0.55
        )
        result.append({
            "policy": policy.policy_id,
            "cell_count": len(cells),
            "return_better_cells": return_wins,
            "drawdown_better_cells": dd_wins,
            "single_name_tail_better_cells": tail_wins,
            "median_annualized_return_diff": median(return_diffs),
            "median_max_drawdown_diff": median(dd_diffs),
            "median_single_name_tail_diff": median(tail_diffs),
            "median_cost_diff_vnd": median(cost_diffs),
            "median_severe_return_diff": median(severe_diffs) if severe_diffs else None,
            "year_return_better_count": year_wins,
            "year_comparison_count": year_total,
            "year_return_win_rate": year_wins / year_total if year_total else 0.0,
            "historical_robustness_candidate": robust,
        })
    result.sort(
        key=lambda row: (
            not bool(row["historical_robustness_candidate"]),
            -float(row["median_annualized_return_diff"]),
            -float(row["median_max_drawdown_diff"]),
            str(row["policy"]),
        )
    )
    return result


def _baseline_parity(
    *,
    snapshots: Sequence[v43.SignalSnapshot],
    prices: v43.PriceStore,
    preview_states: Mapping[date, PreviewState],
    contributions: Sequence[int],
) -> dict[str, object]:
    """Custom baseline must equal frozen V43 P1 at V43's own terminal day."""
    end = min(snapshots[-1].day, prices.calendar[-1])
    weekly_days = v43._weekly_days(prices.calendar, start=snapshots[0].day, end=end)
    checks: list[dict[str, object]] = []
    for contribution in contributions:
        for scenario in v43.SCENARIOS:
            reference, _, _ = v43._simulate(
                policy_id="P1_TOP10_UNDERWEIGHT_BUFFER20",
                contribution=int(contribution),
                scenario=scenario,
                snapshots=snapshots,
                prices=prices,
                weekly_days=weekly_days,
            )
            candidate, _, _ = _custom_simulate(
                policy=POLICY_BY_ID["BASELINE_P1"],
                contribution=int(contribution),
                scenario=scenario,
                snapshots=snapshots,
                prices=prices,
                weekly_days=weekly_days,
                preview_states=preview_states,
            )
            final_diff = abs(float(reference["final_value_vnd"]) - float(candidate["final_value_vnd"]))
            xirr_diff = abs(float(reference.get("xirr") or 0.0) - float(candidate.get("xirr") or 0.0))
            dd_diff = abs(float(reference["max_drawdown"]) - float(candidate["max_drawdown"]))
            passed = final_diff <= 1e-6 and xirr_diff <= 1e-12 and dd_diff <= 1e-12
            checks.append({
                "contribution": contribution,
                "scenario": scenario,
                "final_value_diff_vnd": final_diff,
                "xirr_diff": xirr_diff,
                "max_drawdown_diff": dd_diff,
                "passed": passed,
            })
    if not all(row["passed"] for row in checks):
        raise AssertionError("V61_BASELINE_PARITY_FAILED")
    return {"status": "PASS", "comparison_day": end.isoformat(), "checked_cells": len(checks), "checks": checks}


def _csv_bytes(rows: Sequence[Mapping[str, object]]) -> bytes:
    if not rows:
        return b""
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def run_v61(
    *,
    input_zip: Path,
    store_path: Path,
    output_zip: Path,
    analysis_end: date = ANALYSIS_END_DEFAULT,
    contributions: Sequence[int] = v43.CONTRIBUTIONS,
    price_multiplier: float = v43.PRICE_MULTIPLIER,
) -> dict[str, object]:
    rows, source_manifest = v43._load_research_rows(input_zip)
    snapshots, _, _ = v43.build_signal_snapshots(rows)
    prices = v43._load_prices(store_path, price_multiplier=price_multiplier)
    market = v60._load_market(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, prices.calendar[-1], market.calendar[-1])
    preview_states = build_preview_states(rows=rows, snapshots=snapshots, market=market, analysis_end=effective_end)
    parity = _baseline_parity(
        snapshots=snapshots,
        prices=prices,
        preview_states=preview_states,
        contributions=tuple(sorted(set(int(value) for value in contributions))),
    )
    weekly_days = v43._weekly_days(prices.calendar, start=snapshots[0].day, end=effective_end)

    summaries: list[dict[str, object]] = []
    weekly_all: list[dict[str, object]] = []
    trades_all: list[dict[str, object]] = []
    for contribution in sorted(set(int(value) for value in contributions)):
        if contribution <= 0:
            raise ValueError("V61_CONTRIBUTION_MUST_BE_POSITIVE")
        for scenario in v43.SCENARIOS:
            for policy in POLICIES:
                summary, weekly, trades = _custom_simulate(
                    policy=policy,
                    contribution=contribution,
                    scenario=scenario,
                    snapshots=snapshots,
                    prices=prices,
                    weekly_days=weekly_days,
                    preview_states=preview_states,
                )
                summaries.append(summary)
                weekly_all.extend(weekly)
                trades_all.extend(trades)

    yearly = _yearly_metrics(weekly_all)
    comparisons = _baseline_compare(summaries, yearly)
    candidates = [row for row in comparisons if row["historical_robustness_candidate"]]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "analysis_end_requested": analysis_end.isoformat(),
        "analysis_end_effective": effective_end.isoformat(),
        "baseline_parity": parity,
        "simulation_count": len(summaries),
        "policy_count": len(POLICIES),
        "preview_state_count": len(preview_states),
        "historical_robustness_candidates": candidates,
        "decision": {
            "status": "RESEARCH_CANDIDATES_FOUND" if candidates else "NO_ROBUST_POLICY_FOUND",
            "live_model_change_authorized": False,
            "paper_research_requires_manual_review": True,
            "reason": "V60_ALREADY_CONSUMED_FORMER_HOLDOUT_USE_CROSS_ERA_ROBUSTNESS_NOT_PRISTINE_OOS",
        },
        "research_scope": {
            "canonical_selection_model_changed": False,
            "monthly_P1_exit_retained": True,
            "preview_routes_new_money": True,
            "partial_trim_variants": True,
            "hysteresis_variants": True,
            "rotation_variants": True,
            "tactical_filtered_new_entrants": True,
            "august_2026_vpi_used_for_selection": False,
        },
        "permissions": {
            "research_only": True,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        },
        "limitations": {
            "no_pristine_holdout_after_v60": True,
            "odd_lot_order_book_history_available": False,
            "sector_history_constraint_not_modelled_in_v43_archive_harness": True,
            "corporate_actions_complete": False,
            "point_in_time_universe_complete": False,
            "tactical_thresholds_are_predeclared_not_optimized": True,
        },
        "source_manifest": source_manifest,
    }

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        raise FileExistsError(f"V61_OUTPUT_EXISTS:{output_zip}")
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("v61_report.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")
        archive.writestr("v61_policy_summaries.csv", _csv_bytes(summaries))
        archive.writestr("v61_policy_comparison.csv", _csv_bytes(comparisons))
        archive.writestr("v61_yearly_robustness.csv", _csv_bytes(yearly))
        archive.writestr("v61_trades.csv", _csv_bytes(trades_all))
        archive.writestr("v61_weekly_paths.csv", _csv_bytes(weekly_all))
        archive.writestr(
            "v61_policy_contract.json",
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "policies": [policy.__dict__ for policy in POLICIES],
                    "scenarios": v43.SCENARIOS,
                    "costs": {
                        "broker_fee_bps": v43.BROKER_FEE_BPS,
                        "exchange_fee_bps": v43.EXCHANGE_FEE_BPS,
                        "sell_tax_bps": v43.SELL_TAX_BPS,
                        "transfer_fee_per_share": v43.TRANSFER_FEE_PER_SHARE,
                    },
                    "causality": "PREVIOUS_COMPLETED_WEEKLY_CLOSE_TO_LATER_WEEKLY_OPEN",
                    "live_model_change_authorized": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ) + "\n",
        )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V61 adaptive C3 portfolio research")
    parser.add_argument("--input-zip", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    parser.add_argument("--analysis-end", default=ANALYSIS_END_DEFAULT.isoformat())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_v61(
        input_zip=args.input_zip,
        store_path=args.store,
        output_zip=args.output_zip,
        analysis_end=date.fromisoformat(args.analysis_end),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
