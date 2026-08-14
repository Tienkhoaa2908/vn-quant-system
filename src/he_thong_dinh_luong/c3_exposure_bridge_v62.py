"""V62 exposure-normalized C3 preview-bridge portfolio research.

V61 produced two important diagnostics that make a direct live-policy verdict
unsafe: its tactical sleeve was sized as only 5%-10% of one weekly contribution
(often below one-share affordability), and the inherited V43 core simulator
reinvested at most one weekly contribution after exits, allowing realized cash
to accumulate.  V62 fixes those *research-harness* confounders without changing
the frozen monthly C3 selector.

The study keeps causal timing strict: only a completed prior weekly close may
change a later session-open action.  August-2026 events are excluded from the
default analysis end.  The former V60 holdout has already been consumed, so all
results remain historical/cross-era diagnostics only.
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

from . import c3_adaptive_portfolio_v61 as v61
from . import c3_short_horizon_v60 as v60
from . import weekly_micro_capital_v43 as v43

SCHEMA_VERSION = "c3_exposure_bridge_v62"
ANALYSIS_END_DEFAULT = date(2026, 7, 31)
SYMBOL_CAP = 0.15
BRIDGE_ONE_SHARE_CAP = 0.05
CORE_MAX_ORDERS_PER_WEEK = 10
MATURE_MIN_WEEK = 13
MATURE_MIN_POSITIONS = 5


@dataclass(frozen=True)
class Policy:
    policy_id: str
    route_mode: str = "ALL"
    trim_fraction: float = 0.0
    breakdown_hits_required: int = 0
    hysteresis: bool = True
    minimum_signal_age_sessions: int = 0
    bridge_filter: str = "NONE"
    bridge_target_fraction_nav: float = 0.0
    bridge_max_total_fraction_nav: float = 0.10
    bridge_horizon_sessions: int = 15
    risk_on_stock_fraction: float = 1.0
    risk_off_stock_fraction: float = 0.50


POLICIES: tuple[Policy, ...] = (
    Policy("RECYCLE_BASELINE"),
    Policy("RECYCLE_NOADD20", route_mode="NOT_BREAKDOWN20"),
    Policy(
        "RECYCLE_TRIM25_BREAK1",
        route_mode="NOT_BREAKDOWN20",
        trim_fraction=0.25,
        breakdown_hits_required=1,
    ),
    Policy(
        "RECYCLE_AGE10_TRIM25_BREAK2",
        route_mode="NOT_BREAKDOWN20",
        trim_fraction=0.25,
        breakdown_hits_required=2,
        minimum_signal_age_sessions=10,
    ),
    Policy(
        "RECYCLE_BRIDGE3",
        bridge_filter="PERSIST_OR_VELOCITY",
        bridge_target_fraction_nav=0.03,
    ),
    Policy(
        "RECYCLE_BRIDGE5",
        bridge_filter="PERSIST_OR_VELOCITY",
        bridge_target_fraction_nav=0.05,
    ),
    Policy(
        "RECYCLE_AGE10_TRIM25_BRIDGE3",
        route_mode="NOT_BREAKDOWN20",
        trim_fraction=0.25,
        breakdown_hits_required=2,
        minimum_signal_age_sessions=10,
        bridge_filter="PERSIST_OR_VELOCITY",
        bridge_target_fraction_nav=0.03,
    ),
)
POLICY_BY_ID = {policy.policy_id: policy for policy in POLICIES}


@dataclass
class BridgeLot:
    quantity: int
    entry_day: date
    entry_total_cost_vnd: float


def _safe_mean(values: Sequence[float]) -> float:
    return fmean(values) if values else 0.0


def _annualized(total_return: float, first_day: date, last_day: date) -> float:
    elapsed = max((last_day - first_day).days, 1)
    if total_return <= -1.0:
        return -1.0
    return (1.0 + total_return) ** (365.25 / elapsed) - 1.0


def _stock_fraction(policy: Policy, risk_on: bool) -> float:
    return policy.risk_on_stock_fraction if risk_on else policy.risk_off_stock_fraction


def _bridge_qualifies(
    *,
    policy: Policy,
    preview: v61.PreviewState,
    symbol: str,
) -> bool:
    if policy.bridge_filter == "NONE":
        return False
    rank = v61._preview_rank(preview, symbol)
    previous = int(preview.prior_rank_by_symbol.get(symbol, 10**9))
    volume_ratio = float(preview.volume_ratio_5_20.get(symbol, 0.0))
    return_5 = float(preview.return_5.get(symbol, 0.0))
    distance = float(preview.distance_ma20.get(symbol, 0.0))
    persistent = previous <= 10
    velocity = 6 <= previous <= 20 and previous - rank >= 3
    not_extended = return_5 <= 0.10 and distance <= 0.08
    volume_ok = volume_ratio >= 1.0
    if policy.bridge_filter == "PERSIST_OR_VELOCITY":
        return (persistent or velocity) and volume_ok and not_extended
    raise ValueError(f"V62_UNKNOWN_BRIDGE_FILTER:{policy.bridge_filter}")


def bridge_candidates(
    *,
    policy: Policy,
    preview: v61.PreviewState | None,
    snapshot: v43.SignalSnapshot,
    held_symbols: set[str],
) -> list[str]:
    if policy.bridge_filter == "NONE" or preview is None:
        return []
    if not v61._preview_valid_for_snapshot(preview, snapshot):
        return []
    canonical_top10 = set(snapshot.ranking[:10])
    result: list[str] = []
    for symbol in preview.ranking[:5]:
        if symbol in canonical_top10 or symbol in held_symbols:
            continue
        if _bridge_qualifies(policy=policy, preview=preview, symbol=symbol):
            result.append(symbol)
    return result


def bridge_budget_quantity(
    *,
    raw_price: float,
    cash: float,
    account_value: float,
    current_symbol_quantity: int,
    tactical_market_value: float,
    policy: Policy,
    slippage_bps: float,
) -> tuple[float, int, bool]:
    """NAV-sized bridge starter with a guarded one-share affordability floor."""
    if (
        raw_price <= 0.0
        or cash <= 0.0
        or account_value <= 0.0
        or policy.bridge_target_fraction_nav <= 0.0
    ):
        return 0.0, 0, False
    aggregate_room = max(
        policy.bridge_max_total_fraction_nav * account_value - tactical_market_value,
        0.0,
    )
    symbol_room = max(SYMBOL_CAP * account_value - current_symbol_quantity * raw_price, 0.0)
    target_budget = min(
        cash,
        policy.bridge_target_fraction_nav * account_value,
        aggregate_room,
        symbol_room,
    )
    quantity = v43.affordable_quantity(target_budget, raw_price, slippage_bps)
    if quantity > 0:
        return target_budget, quantity, False

    # The V61 5%-of-weekly-contribution sleeve often could not afford one share.
    # Permit exactly one share only when that share remains a small NAV starter.
    one_share_total = v43._buy_total(raw_price, 1, slippage_bps)
    one_share_market = raw_price
    one_share_allowed = (
        one_share_total <= cash + 1e-8
        and one_share_market <= BRIDGE_ONE_SHARE_CAP * account_value + 1e-8
        and one_share_market <= aggregate_room + 1e-8
        and one_share_market <= symbol_room + 1e-8
    )
    if one_share_allowed:
        return one_share_total, 1, True
    return target_budget, 0, False


def _open_stock_value(
    *,
    holdings: Mapping[str, int],
    prices: v43.PriceStore,
    day: date,
) -> float:
    total = 0.0
    for symbol, quantity in holdings.items():
        if quantity <= 0:
            continue
        mark = prices.opens.get((symbol, day))
        if mark is None:
            mark = prices.latest_close(symbol, day)
        if mark is not None:
            total += quantity * float(mark)
    return total


def _target_weights(
    *,
    snapshot: v43.SignalSnapshot,
    target_symbols: Sequence[str],
    stock_fraction: float,
) -> dict[str, float]:
    base = v43.capped_inverse_vol_weights(
        snapshot.ranking,
        snapshot.volatility,
        target_count=10,
        symbol_cap=SYMBOL_CAP,
    )
    return {
        symbol: float(base.get(symbol, 0.0)) * stock_fraction
        for symbol in target_symbols
    }


def _core_buy_loop(
    *,
    policy: Policy,
    snapshot: v43.SignalSnapshot,
    preview: v61.PreviewState | None,
    preview_valid: bool,
    trade_day: date,
    holdings: dict[str, int],
    average_cost: dict[str, float],
    cash: float,
    prices: v43.PriceStore,
    slippage_bps: float,
    blocked_symbols: set[str],
) -> tuple[float, float, int, list[dict[str, object]]]:
    """Recycle available cash toward the stock-sleeve target, with symbol caps."""
    trades: list[dict[str, object]] = []
    fees_total = 0.0
    buy_count = 0
    canonical_targets = list(snapshot.ranking[:10])
    target_symbols = v61._route_targets(
        policy=v61.Policy(
            policy_id="V62_ROUTE_PROXY",
            route_mode=policy.route_mode,
        ),
        canonical_targets=canonical_targets,
        preview=preview if preview_valid else None,
        snapshot=snapshot,
    )
    target_symbols = [symbol for symbol in target_symbols if symbol not in blocked_symbols]
    stock_fraction = _stock_fraction(policy, snapshot.risk_on)
    if not target_symbols or stock_fraction <= 0.0:
        return cash, fees_total, buy_count, trades

    for _ in range(CORE_MAX_ORDERS_PER_WEEK):
        account_value, _ = v43._account_value(cash, holdings, prices, trade_day, use_open=True)
        if account_value <= 0.0 or cash <= 0.0:
            break
        stock_value = _open_stock_value(holdings=holdings, prices=prices, day=trade_day)
        stock_gap = max(stock_fraction * account_value - stock_value, 0.0)
        if stock_gap <= 1e-8:
            break
        weights = _target_weights(
            snapshot=snapshot,
            target_symbols=target_symbols,
            stock_fraction=stock_fraction,
        )
        candidates: list[tuple[float, int, str]] = []
        for rank, symbol in enumerate(target_symbols):
            raw_price = prices.opens.get((symbol, trade_day))
            if raw_price is None or raw_price <= 0.0:
                continue
            current_value = holdings.get(symbol, 0) * float(raw_price)
            target_value = float(weights.get(symbol, 0.0)) * account_value
            gap = max(target_value - current_value, 0.0)
            if gap > 0.0:
                candidates.append((gap, -rank, symbol))
        if not candidates:
            break
        candidates.sort(reverse=True)
        executed = False
        for gap, _, symbol in candidates:
            raw_price = float(prices.opens[(symbol, trade_day)])
            budget = min(cash, stock_gap, gap)
            quantity = v61._position_cap_quantity(
                symbol=symbol,
                current_qty=holdings.get(symbol, 0),
                budget=budget,
                account_value=account_value,
                trade_day=trade_day,
                prices=prices,
                slippage_bps=slippage_bps,
            )
            if quantity <= 0:
                continue
            total_cost = v43._buy_total(raw_price, quantity, slippage_bps)
            while quantity > 0 and total_cost > cash + 1e-8:
                quantity -= 1
                total_cost = v43._buy_total(raw_price, quantity, slippage_bps)
            if quantity <= 0:
                continue
            old_qty = holdings.get(symbol, 0)
            average_cost[symbol] = v61._update_average_cost(
                old_qty,
                average_cost.get(symbol, 0.0),
                quantity,
                total_cost,
            )
            holdings[symbol] = old_qty + quantity
            cash -= total_cost
            gross = raw_price * quantity
            fees_total += total_cost - gross
            buy_count += 1
            trades.append({
                "side": "BUY_CORE_RECYCLE",
                "symbol": symbol,
                "quantity": quantity,
                "gross_reference_vnd": gross,
                "cash_effect_vnd": -total_cost,
                "preview_rank": v61._preview_rank(preview, symbol) if preview_valid else "",
                "route_mode": policy.route_mode,
            })
            executed = True
            break
        if not executed:
            break
    return cash, fees_total, buy_count, trades


def _simulate(
    *,
    policy: Policy,
    contribution: int,
    scenario: str,
    snapshots: Sequence[v43.SignalSnapshot],
    prices: v43.PriceStore,
    weekly_days: Sequence[date],
    preview_states: Mapping[date, v61.PreviewState],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    slippage_bps = float(v43.SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    observation_days = sorted(preview_states)
    calendar_index = v61._calendar_index(prices.calendar)

    cash = 0.0
    holdings: dict[str, int] = {}
    average_cost: dict[str, float] = {}
    peak_mark: dict[str, float] = {}
    outside_counts: dict[str, int] = {}
    breakdown_hits: dict[str, int] = {}
    trimmed_episode: dict[str, bool] = {}
    bridge_lots: dict[str, BridgeLot] = {}
    bridge_seen_since_signal: set[str] = set()
    prior_canonical_top10: set[str] | None = None
    current_signal_index = -1
    current_snapshot: v43.SignalSnapshot | None = None

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
    bridge_candidate_events = 0
    bridge_buy_count = 0
    bridge_exit_count = 0
    bridge_promotion_count = 0
    bridge_one_share_floor_count = 0
    bridge_affordability_miss_count = 0
    bridge_realized_pnl_vnd = 0.0
    eligible_new_canonical_entrant_count = 0
    early_captured_new_canonical_entrant_count = 0
    raw_worst_unrealized_nav = 0.0
    raw_worst_peak_damage_nav = 0.0
    mature_worst_peak_damage_nav = 0.0
    mature_damage_weeks_1pct = 0
    missing_trade_bar_count = 0
    stale_valuation_count = 0
    stock_exposure_sum = 0.0
    stock_exposure_count = 0
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
        preview = v61._latest_preview_before(trade_day, observation_days, preview_states)
        preview_valid = v61._preview_valid_for_snapshot(preview, current_snapshot)

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

        canonical_top10 = set(current_snapshot.ranking[:10])
        if signal_changed:
            if prior_canonical_top10 is not None:
                new_entrants = canonical_top10 - prior_canonical_top10
                eligible = new_entrants & bridge_seen_since_signal
                captured = {
                    symbol for symbol in eligible
                    if symbol in bridge_lots and holdings.get(symbol, 0) > 0
                }
                eligible_new_canonical_entrant_count += len(eligible)
                early_captured_new_canonical_entrant_count += len(captured)
            for symbol in list(bridge_lots):
                if symbol in canonical_top10 and holdings.get(symbol, 0) > 0:
                    bridge_lots.pop(symbol, None)
                    bridge_promotion_count += 1
                    trade_rows.append({
                        "policy": policy.policy_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        "trade_day": trade_day.isoformat(),
                        "side": "BRIDGE_PROMOTED_TO_CORE",
                        "symbol": symbol,
                        "quantity": holdings.get(symbol, 0),
                        "gross_reference_vnd": 0.0,
                        "cash_effect_vnd": 0.0,
                    })
            prior_canonical_top10 = set(canonical_top10)
            bridge_seen_since_signal = set()

        monthly_exits: list[str] = []
        if signal_changed:
            rank_by_symbol = {
                symbol: rank
                for rank, symbol in enumerate(current_snapshot.ranking, start=1)
            }
            monthly_exits = v43.compute_exit_symbols(
                holdings,
                rank_by_symbol,
                outside_counts,
                exit_rank=20,
                exit_months=2,
            )
        blocked_symbols: set[str] = set()
        for symbol in monthly_exits:
            quantity = holdings.get(symbol, 0)
            execution = v61._execute_sell(
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
            bridge_lots.pop(symbol, None)
            outside_counts[symbol] = 0
            breakdown_hits[symbol] = 0
            trimmed_episode[symbol] = False
            sell_count += 1
            blocked_symbols.add(symbol)
            trade_rows.append({
                "policy": policy.policy_id,
                "contribution": contribution,
                "scenario": scenario,
                "trade_day": trade_day.isoformat(),
                "side": "SELL_P1",
                "symbol": symbol,
                "quantity": quantity,
                "gross_reference_vnd": gross,
                "cash_effect_vnd": proceeds,
                "preview_rank": v61._preview_rank(preview, symbol) if preview_valid else "",
            })

        for symbol, lot in list(bridge_lots.items()):
            if holdings.get(symbol, 0) <= 0:
                bridge_lots.pop(symbol, None)
                continue
            age = v61._sessions_between(calendar_index, lot.entry_day, trade_day)
            rank = v61._preview_rank(preview, symbol) if preview_valid else 10**9
            if age < policy.bridge_horizon_sessions and rank <= 20:
                continue
            quantity = min(lot.quantity, holdings.get(symbol, 0))
            execution = v61._execute_sell(
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
            holdings[symbol] -= quantity
            bridge_lots.pop(symbol, None)
            bridge_exit_count += 1
            sell_count += 1
            bridge_realized_pnl_vnd += proceeds - lot.entry_total_cost_vnd
            blocked_symbols.add(symbol)
            if holdings[symbol] <= 0:
                average_cost[symbol] = 0.0
                peak_mark.pop(symbol, None)
            trade_rows.append({
                "policy": policy.policy_id,
                "contribution": contribution,
                "scenario": scenario,
                "trade_day": trade_day.isoformat(),
                "side": "SELL_BRIDGE",
                "symbol": symbol,
                "quantity": quantity,
                "gross_reference_vnd": gross,
                "cash_effect_vnd": proceeds,
                "bridge_age_sessions": age,
                "preview_rank": rank if preview_valid else "",
            })

        if preview_valid and preview is not None:
            signal_age = v61._sessions_between(
                calendar_index,
                current_snapshot.day,
                preview.observation_day,
            )
            for symbol in current_snapshot.ranking[:10]:
                if holdings.get(symbol, 0) <= 0:
                    continue
                rank = v61._preview_rank(preview, symbol)
                if rank > 20:
                    breakdown_hits[symbol] = breakdown_hits.get(symbol, 0) + 1
                elif rank <= 10:
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
                if quantity <= 0 or quantity >= holdings[symbol]:
                    continue
                execution = v61._execute_sell(
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
                holdings[symbol] -= quantity
                trim_count += 1
                sell_count += 1
                trimmed_episode[symbol] = True
                blocked_symbols.add(symbol)
                trade_rows.append({
                    "policy": policy.policy_id,
                    "contribution": contribution,
                    "scenario": scenario,
                    "trade_day": trade_day.isoformat(),
                    "side": "SELL_PREVIEW_TRIM",
                    "symbol": symbol,
                    "quantity": quantity,
                    "gross_reference_vnd": gross,
                    "cash_effect_vnd": proceeds,
                    "preview_rank": rank,
                    "breakdown_hits": breakdown_hits.get(symbol, 0),
                    "signal_age_sessions": signal_age,
                })

        candidates = bridge_candidates(
            policy=policy,
            preview=preview if preview_valid else None,
            snapshot=current_snapshot,
            held_symbols={symbol for symbol, quantity in holdings.items() if quantity > 0},
        )
        bridge_candidate_events += len(candidates)
        bridge_seen_since_signal.update(candidates)
        chosen_bridge = candidates[0] if candidates else None
        if chosen_bridge is not None and preview is not None:
            raw_price = prices.opens.get((chosen_bridge, trade_day))
            account_value_open, _ = v43._account_value(
                cash,
                holdings,
                prices,
                trade_day,
                use_open=True,
            )
            tactical_market_value = 0.0
            for symbol, lot in bridge_lots.items():
                if holdings.get(symbol, 0) <= 0:
                    continue
                mark = prices.opens.get((symbol, trade_day)) or prices.latest_close(symbol, trade_day)
                if mark is not None:
                    tactical_market_value += min(lot.quantity, holdings[symbol]) * float(mark)
            if raw_price is not None:
                _, quantity, used_floor = bridge_budget_quantity(
                    raw_price=float(raw_price),
                    cash=cash,
                    account_value=account_value_open,
                    current_symbol_quantity=holdings.get(chosen_bridge, 0),
                    tactical_market_value=tactical_market_value,
                    policy=policy,
                    slippage_bps=slippage_bps,
                )
                if quantity > 0:
                    total_cost = v43._buy_total(float(raw_price), quantity, slippage_bps)
                    if total_cost <= cash + 1e-8:
                        old_qty = holdings.get(chosen_bridge, 0)
                        average_cost[chosen_bridge] = v61._update_average_cost(
                            old_qty,
                            average_cost.get(chosen_bridge, 0.0),
                            quantity,
                            total_cost,
                        )
                        holdings[chosen_bridge] = old_qty + quantity
                        cash -= total_cost
                        gross = float(raw_price) * quantity
                        fees_total += total_cost - gross
                        gross_turnover += gross
                        bridge_lots[chosen_bridge] = BridgeLot(
                            quantity=quantity,
                            entry_day=trade_day,
                            entry_total_cost_vnd=total_cost,
                        )
                        bridge_buy_count += 1
                        buy_count += 1
                        bridge_one_share_floor_count += int(used_floor)
                        trade_rows.append({
                            "policy": policy.policy_id,
                            "contribution": contribution,
                            "scenario": scenario,
                            "trade_day": trade_day.isoformat(),
                            "side": "BUY_BRIDGE",
                            "symbol": chosen_bridge,
                            "quantity": quantity,
                            "gross_reference_vnd": gross,
                            "cash_effect_vnd": -total_cost,
                            "preview_rank": v61._preview_rank(preview, chosen_bridge),
                            "volume_ratio_5_20": preview.volume_ratio_5_20.get(chosen_bridge, 0.0),
                            "return_5": preview.return_5.get(chosen_bridge, 0.0),
                            "distance_ma20": preview.distance_ma20.get(chosen_bridge, 0.0),
                            "used_one_share_floor": str(bool(used_floor)).lower(),
                        })
                else:
                    bridge_affordability_miss_count += 1
            else:
                bridge_affordability_miss_count += 1

        cash, extra_fees, core_buys, core_trades = _core_buy_loop(
            policy=policy,
            snapshot=current_snapshot,
            preview=preview,
            preview_valid=preview_valid,
            trade_day=trade_day,
            holdings=holdings,
            average_cost=average_cost,
            cash=cash,
            prices=prices,
            slippage_bps=slippage_bps,
            blocked_symbols=blocked_symbols,
        )
        fees_total += extra_fees
        buy_count += core_buys
        for row in core_trades:
            gross_turnover += float(row["gross_reference_vnd"])
            trade_rows.append({
                "policy": policy.policy_id,
                "contribution": contribution,
                "scenario": scenario,
                "trade_day": trade_day.isoformat(),
                **row,
            })

        end_value, stale_end = v43._account_value(cash, holdings, prices, trade_day, use_open=False)
        stale_valuation_count += stale_end
        unit_price = end_value / fund_units if fund_units > 0.0 else 1.0
        peak_unit_price = max(peak_unit_price, unit_price)
        drawdown = unit_price / peak_unit_price - 1.0
        max_drawdown = min(max_drawdown, drawdown)

        live_positions = {
            symbol: quantity
            for symbol, quantity in holdings.items()
            if quantity > 0
        }
        stock_value_end = max(end_value - cash, 0.0)
        stock_exposure = stock_value_end / end_value if end_value > 0.0 else 0.0
        stock_exposure_sum += stock_exposure
        stock_exposure_count += 1
        weekly_worst_unrealized = 0.0
        weekly_worst_peak = 0.0
        mature_damage_count = 0
        largest_weight = 0.0
        for symbol, quantity in live_positions.items():
            mark = prices.latest_close(symbol, trade_day)
            if mark is None or end_value <= 0.0:
                continue
            mark = float(mark)
            weight = quantity * mark / end_value
            largest_weight = max(largest_weight, weight)
            peak_mark[symbol] = max(float(peak_mark.get(symbol, mark)), mark)
            cost_basis = average_cost.get(symbol, 0.0)
            if cost_basis > 0.0:
                unrealized_nav = quantity * (mark - cost_basis) / end_value
                weekly_worst_unrealized = min(weekly_worst_unrealized, unrealized_nav)
            peak_damage = quantity * (mark - peak_mark[symbol]) / end_value
            weekly_worst_peak = min(weekly_worst_peak, peak_damage)
            if (
                week_number >= MATURE_MIN_WEEK
                and len(live_positions) >= MATURE_MIN_POSITIONS
                and peak_damage <= -0.01
            ):
                mature_damage_count += 1
        raw_worst_unrealized_nav = min(raw_worst_unrealized_nav, weekly_worst_unrealized)
        raw_worst_peak_damage_nav = min(raw_worst_peak_damage_nav, weekly_worst_peak)
        if week_number >= MATURE_MIN_WEEK and len(live_positions) >= MATURE_MIN_POSITIONS:
            mature_worst_peak_damage_nav = min(mature_worst_peak_damage_nav, weekly_worst_peak)
            mature_damage_weeks_1pct += mature_damage_count

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
            "cash_vnd": cash,
            "portfolio_value_vnd": end_value,
            "unit_price": unit_price,
            "drawdown": drawdown,
            "position_count": len(live_positions),
            "largest_symbol_weight": largest_weight,
            "stock_exposure_ratio": stock_exposure,
            "target_stock_fraction": _stock_fraction(policy, current_snapshot.risk_on),
            "weekly_worst_single_name_unrealized_nav": weekly_worst_unrealized,
            "weekly_worst_weighted_peak_damage_nav": weekly_worst_peak,
            "mature_risk_window": str(
                week_number >= MATURE_MIN_WEEK and len(live_positions) >= MATURE_MIN_POSITIONS
            ).lower(),
            "mature_damage_count_1pct": mature_damage_count,
            "bridge_candidates": "|".join(candidates),
            "chosen_bridge": chosen_bridge or "",
        })

    if not weekly_rows:
        raise ValueError("V62_NO_WEEKLY_SIMULATION_ROWS")
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
    annualized = _annualized(total_return, first_day, final_day)
    calmar = annualized / abs(max_drawdown) if max_drawdown < 0.0 else None
    final_cash = float(weekly_rows[-1]["cash_vnd"])
    early_capture_rate = (
        early_captured_new_canonical_entrant_count / eligible_new_canonical_entrant_count
        if eligible_new_canonical_entrant_count > 0
        else None
    )
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
        "xirr_excess": (
            portfolio_xirr - benchmark_xirr
            if portfolio_xirr is not None and benchmark_xirr is not None
            else None
        ),
        "unitized_total_return": total_return,
        "annualized_unitized_return": annualized,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "ending_cash_vnd": final_cash,
        "ending_cash_ratio": final_cash / final_value if final_value > 0.0 else 0.0,
        "average_stock_exposure_ratio": (
            stock_exposure_sum / stock_exposure_count
            if stock_exposure_count > 0
            else 0.0
        ),
        "buy_order_count": buy_count,
        "sell_order_count": sell_count,
        "preview_trim_count": trim_count,
        "bridge_candidate_event_count": bridge_candidate_events,
        "bridge_buy_count": bridge_buy_count,
        "bridge_exit_count": bridge_exit_count,
        "bridge_promotion_count": bridge_promotion_count,
        "bridge_one_share_floor_count": bridge_one_share_floor_count,
        "bridge_affordability_miss_count": bridge_affordability_miss_count,
        "bridge_realized_pnl_vnd": bridge_realized_pnl_vnd,
        "eligible_new_canonical_entrant_count": eligible_new_canonical_entrant_count,
        "early_captured_new_canonical_entrant_count": early_captured_new_canonical_entrant_count,
        "early_capture_rate": early_capture_rate,
        "raw_worst_single_name_unrealized_nav": raw_worst_unrealized_nav,
        "raw_worst_weighted_peak_damage_nav": raw_worst_peak_damage_nav,
        "mature_worst_weighted_peak_damage_nav": mature_worst_peak_damage_nav,
        "mature_single_name_damage_weeks_1pct": mature_damage_weeks_1pct,
        "estimated_total_cost_vnd": fees_total,
        "gross_turnover_vnd": gross_turnover,
        "turnover_to_contributions": (
            gross_turnover / contributions_total if contributions_total > 0.0 else 0.0
        ),
        "missing_trade_bar_count": missing_trade_bar_count,
        "stale_valuation_count": stale_valuation_count,
        "live_capital_approved": False,
    }
    return summary, weekly_rows, trade_rows


def _yearly_metrics(weekly_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int, str, int], list[Mapping[str, object]]] = {}
    for row in weekly_rows:
        year = date.fromisoformat(str(row["trade_day"])).year
        key = (str(row["policy"]), int(row["contribution"]), str(row["scenario"]), year)
        grouped.setdefault(key, []).append(row)
    result: list[dict[str, object]] = []
    for (policy, contribution, scenario, year), rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: str(row["trade_day"]))
        first = float(ordered[0]["unit_price"])
        last = float(ordered[-1]["unit_price"])
        yearly_return = last / first - 1.0 if first > 0.0 else 0.0
        mature_rows = [
            row for row in ordered
            if str(row.get("mature_risk_window", "false")).lower() == "true"
        ]
        result.append({
            "policy": policy,
            "contribution": contribution,
            "scenario": scenario,
            "year": year,
            "unitized_return": yearly_return,
            "max_drawdown": min(float(row["drawdown"]) for row in ordered),
            "mature_worst_weighted_peak_damage_nav": (
                min(float(row["weekly_worst_weighted_peak_damage_nav"]) for row in mature_rows)
                if mature_rows
                else 0.0
            ),
            "average_stock_exposure_ratio": _safe_mean(
                [float(row["stock_exposure_ratio"]) for row in ordered]
            ),
        })
    return result


def _baseline_compare(
    summaries: Sequence[Mapping[str, object]],
    yearly: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    baseline = {
        (int(row["contribution"]), str(row["scenario"])): row
        for row in summaries
        if row["policy"] == "RECYCLE_BASELINE"
    }
    yearly_base = {
        (int(row["contribution"]), str(row["scenario"]), int(row["year"])): row
        for row in yearly
        if row["policy"] == "RECYCLE_BASELINE"
    }
    result: list[dict[str, object]] = []
    for policy in POLICIES:
        if policy.policy_id == "RECYCLE_BASELINE":
            continue
        cells = [row for row in summaries if row["policy"] == policy.policy_id]
        return_diffs: list[float] = []
        calmar_diffs: list[float] = []
        tail_diffs: list[float] = []
        exposure_diffs: list[float] = []
        cost_diffs: list[float] = []
        severe_diffs: list[float] = []
        return_wins = 0
        calmar_wins = 0
        tail_wins = 0
        for row in cells:
            key = (int(row["contribution"]), str(row["scenario"]))
            base = baseline[key]
            rd = float(row["annualized_unitized_return"]) - float(base["annualized_unitized_return"])
            cd = float(row.get("calmar") or -999.0) - float(base.get("calmar") or -999.0)
            td = float(row["mature_worst_weighted_peak_damage_nav"]) - float(base["mature_worst_weighted_peak_damage_nav"])
            ed = float(row["average_stock_exposure_ratio"]) - float(base["average_stock_exposure_ratio"])
            return_diffs.append(rd)
            calmar_diffs.append(cd)
            tail_diffs.append(td)
            exposure_diffs.append(ed)
            cost_diffs.append(float(row["estimated_total_cost_vnd"]) - float(base["estimated_total_cost_vnd"]))
            return_wins += int(rd > 0.0)
            calmar_wins += int(cd > 0.0)
            tail_wins += int(td > 0.0)
            if row["scenario"] == "SEVERE":
                severe_diffs.append(rd)
        year_wins = 0
        year_total = 0
        for row in yearly:
            if row["policy"] != policy.policy_id:
                continue
            key = (int(row["contribution"]), str(row["scenario"]), int(row["year"]))
            base = yearly_base.get(key)
            if base is None:
                continue
            year_total += 1
            year_wins += int(float(row["unitized_return"]) > float(base["unitized_return"]))
        median_exposure_diff = median(exposure_diffs) if exposure_diffs else 0.0
        robust = bool(
            return_diffs
            and median(return_diffs) > 0.0
            and return_wins >= 6
            and calmar_wins >= 6
            and tail_wins >= 7
            and median(tail_diffs) >= 0.0
            and abs(median_exposure_diff) <= 0.05
            and median(severe_diffs or [-1.0]) >= 0.0
            and year_total > 0
            and year_wins / year_total >= 0.55
        )
        result.append({
            "policy": policy.policy_id,
            "cell_count": len(cells),
            "return_better_cells": return_wins,
            "calmar_better_cells": calmar_wins,
            "mature_peak_tail_better_cells": tail_wins,
            "median_annualized_return_diff": median(return_diffs),
            "median_calmar_diff": median(calmar_diffs),
            "median_mature_peak_tail_diff": median(tail_diffs),
            "median_average_stock_exposure_diff": median_exposure_diff,
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
            -float(row["median_calmar_diff"]),
            -float(row["median_annualized_return_diff"]),
            str(row["policy"]),
        )
    )
    return result


def _legacy_v61_audit(
    *,
    snapshots: Sequence[v43.SignalSnapshot],
    prices: v43.PriceStore,
    preview_states: Mapping[date, v61.PreviewState],
    weekly_days: Sequence[date],
) -> dict[str, object]:
    summary, weekly, _ = v61._custom_simulate(
        policy=v61.POLICY_BY_ID["BASELINE_P1"],
        contribution=250_000,
        scenario="BASE",
        snapshots=snapshots,
        prices=prices,
        weekly_days=weekly_days,
        preview_states=preview_states,
    )
    average_stock_exposure = _safe_mean([
        max(1.0 - float(row["cash_vnd"]) / float(row["portfolio_value_vnd"]), 0.0)
        if float(row["portfolio_value_vnd"]) > 0.0 else 0.0
        for row in weekly
    ])
    return {
        "policy": "V61_BASELINE_P1",
        "contribution": 250000,
        "scenario": "BASE",
        "final_value_vnd": summary["final_value_vnd"],
        "ending_cash_ratio": summary["ending_cash_ratio"],
        "average_stock_exposure_ratio": average_stock_exposure,
        "note": "diagnostic_only_inherited_one_contribution_redeployment_cap",
    }


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
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8-sig")


def run_v62(
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
    preview_states = v61.build_preview_states(
        rows=rows,
        snapshots=snapshots,
        market=market,
        analysis_end=effective_end,
    )
    weekly_days = v43._weekly_days(
        prices.calendar,
        start=snapshots[0].day,
        end=effective_end,
    )
    legacy_audit = _legacy_v61_audit(
        snapshots=snapshots,
        prices=prices,
        preview_states=preview_states,
        weekly_days=weekly_days,
    )

    summaries: list[dict[str, object]] = []
    weekly_all: list[dict[str, object]] = []
    trades_all: list[dict[str, object]] = []
    for contribution in sorted(set(int(value) for value in contributions)):
        if contribution <= 0:
            raise ValueError("V62_CONTRIBUTION_MUST_BE_POSITIVE")
        for scenario in v43.SCENARIOS:
            for policy in POLICIES:
                summary, weekly, trades = _simulate(
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
    primary = [
        row for row in summaries
        if int(row["contribution"]) == 250_000 and str(row["scenario"]) == "BASE"
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "analysis_end_requested": analysis_end.isoformat(),
        "analysis_end_effective": effective_end.isoformat(),
        "simulation_count": len(summaries),
        "policy_count": len(POLICIES),
        "preview_state_count": len(preview_states),
        "legacy_v61_baseline_audit": legacy_audit,
        "primary_250k_base": primary,
        "historical_robustness_candidates": candidates,
        "decision": {
            "status": "RESEARCH_CANDIDATES_FOUND" if candidates else "NO_ROBUST_POLICY_FOUND",
            "live_model_change_authorized": False,
            "paper_research_requires_manual_review": True,
            "reason": "NO_PRISTINE_HOLDOUT_AFTER_V60_EXPOSURE_NORMALIZED_HISTORICAL_DIAGNOSTIC_ONLY",
        },
        "research_scope": {
            "canonical_selection_model_changed": False,
            "monthly_P1_exit_retained": True,
            "recycles_realized_cash": True,
            "core_deployment_normalized_to_regime_stock_target": True,
            "risk_on_stock_fraction": 1.0,
            "risk_off_stock_fraction": 0.5,
            "preview_bridge_uses_nav_sizing": True,
            "one_share_floor_is_guarded_by_5pct_nav_cap": True,
            "mature_single_name_tail_excludes_bootstrap_weeks": True,
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
            "sector_history_constraint_not_modelled": True,
            "corporate_actions_complete": False,
            "point_in_time_universe_complete": False,
            "price_basis_confirmed": False,
            "bridge_thresholds_are_predeclared_not_optimized": True,
            "regime_stock_fraction_is_research_policy_not_live_authorization": True,
        },
        "source_manifest": source_manifest,
    }

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        raise FileExistsError(f"V62_OUTPUT_EXISTS:{output_zip}")
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "v62_report.json",
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        )
        archive.writestr("v62_policy_summaries.csv", _csv_bytes(summaries))
        archive.writestr("v62_policy_comparison.csv", _csv_bytes(comparisons))
        archive.writestr("v62_yearly_robustness.csv", _csv_bytes(yearly))
        archive.writestr("v62_trades.csv", _csv_bytes(trades_all))
        archive.writestr("v62_weekly_paths.csv", _csv_bytes(weekly_all))
        archive.writestr(
            "v62_policy_contract.json",
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
                    "mature_risk_window": {
                        "minimum_week_number": MATURE_MIN_WEEK,
                        "minimum_position_count": MATURE_MIN_POSITIONS,
                    },
                    "bridge_one_share_cap_nav": BRIDGE_ONE_SHARE_CAP,
                    "core_max_orders_per_week": CORE_MAX_ORDERS_PER_WEEK,
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
    parser = argparse.ArgumentParser(description="V62 exposure-normalized C3 preview-bridge research")
    parser.add_argument("--input-zip", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    parser.add_argument("--analysis-end", default=ANALYSIS_END_DEFAULT.isoformat())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_v62(
        input_zip=args.input_zip,
        store_path=args.store,
        output_zip=args.output_zip,
        analysis_end=date.fromisoformat(args.analysis_end),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
