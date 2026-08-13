"""Mutable simulation state and execution primitives for V63."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import c3_adaptive_portfolio_v61 as v61
from . import weekly_micro_capital_v43 as v43
from ._v63_contract import OpportunityLot


@dataclass
class SimState:
    cash: float = 0.0
    holdings: dict[str, int] = field(default_factory=dict)
    average_cost: dict[str, float] = field(default_factory=dict)
    peak_mark: dict[str, float] = field(default_factory=dict)
    outside_counts: dict[str, int] = field(default_factory=dict)
    protection_hits: dict[str, int] = field(default_factory=dict)
    protection_locked: dict[str, bool] = field(default_factory=dict)
    opportunity_lots: dict[str, OpportunityLot] = field(default_factory=dict)
    opportunity_seen_since_signal: set[str] = field(default_factory=set)
    prior_canonical_top10: set[str] | None = None
    current_signal_index: int = -1
    current_snapshot: v43.SignalSnapshot | None = None

    fund_units: float = 0.0
    unit_price: float = 1.0
    peak_unit_price: float = 1.0
    max_drawdown: float = 0.0
    contributions_total: float = 0.0
    fees_total: float = 0.0
    gross_turnover: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    protection_soft_trim_count: int = 0
    protection_full_exit_count: int = 0
    protection_recovery_count: int = 0
    protection_locked_symbol_weeks: int = 0
    opportunity_candidate_events: int = 0
    opportunity_buy_count: int = 0
    opportunity_topup_count: int = 0
    opportunity_exit_count: int = 0
    opportunity_promotion_count: int = 0
    opportunity_one_share_floor_count: int = 0
    opportunity_affordability_miss_count: int = 0
    opportunity_realized_pnl_vnd: float = 0.0
    eligible_new_canonical_entrant_count: int = 0
    early_captured_new_canonical_entrant_count: int = 0
    raw_worst_unrealized_nav: float = 0.0
    raw_worst_peak_damage_nav: float = 0.0
    mature_worst_peak_damage_nav: float = 0.0
    mature_damage_weeks_1pct: int = 0
    missing_trade_bar_count: int = 0
    stale_valuation_count: int = 0
    stock_exposure_sum: float = 0.0
    stock_exposure_count: int = 0
    cashflows: list[tuple[date, float]] = field(default_factory=list)
    benchmark_units: float = 0.0
    benchmark_cashflows: list[tuple[date, float]] = field(default_factory=list)
    weekly_rows: list[dict[str, object]] = field(default_factory=list)
    trade_rows: list[dict[str, object]] = field(default_factory=list)


def sell_position(
    *,
    state: SimState,
    policy_id: str,
    contribution: int,
    scenario: str,
    symbol: str,
    quantity: int,
    trade_day: date,
    prices: v43.PriceStore,
    slippage_bps: float,
    side: str,
    metadata: dict[str, object] | None = None,
) -> tuple[float, float] | None:
    execution = v61._execute_sell(
        symbol=symbol,
        quantity=quantity,
        trade_day=trade_day,
        prices=prices,
        slippage_bps=slippage_bps,
    )
    if execution is None:
        state.missing_trade_bar_count += 1
        return None
    proceeds, gross, cost = execution
    state.cash += proceeds
    state.fees_total += cost
    state.gross_turnover += gross
    state.holdings[symbol] = max(state.holdings.get(symbol, 0) - quantity, 0)
    state.sell_count += 1
    if state.holdings[symbol] <= 0:
        state.average_cost[symbol] = 0.0
        state.peak_mark.pop(symbol, None)
    row: dict[str, object] = {
        "policy": policy_id,
        "contribution": contribution,
        "scenario": scenario,
        "trade_day": trade_day.isoformat(),
        "side": side,
        "symbol": symbol,
        "quantity": quantity,
        "gross_reference_vnd": gross,
        "cash_effect_vnd": proceeds,
    }
    if metadata:
        row.update(metadata)
    state.trade_rows.append(row)
    return proceeds, gross


def buy_position(
    *,
    state: SimState,
    policy_id: str,
    contribution: int,
    scenario: str,
    symbol: str,
    quantity: int,
    trade_day: date,
    raw_price: float,
    slippage_bps: float,
    side: str,
    metadata: dict[str, object] | None = None,
) -> float | None:
    if quantity <= 0:
        return None
    total_cost = v43._buy_total(raw_price, quantity, slippage_bps)
    if total_cost > state.cash + 1e-8:
        return None
    old_qty = state.holdings.get(symbol, 0)
    state.average_cost[symbol] = v61._update_average_cost(
        old_qty,
        state.average_cost.get(symbol, 0.0),
        quantity,
        total_cost,
    )
    state.holdings[symbol] = old_qty + quantity
    state.cash -= total_cost
    gross = raw_price * quantity
    state.fees_total += total_cost - gross
    state.gross_turnover += gross
    state.buy_count += 1
    row: dict[str, object] = {
        "policy": policy_id,
        "contribution": contribution,
        "scenario": scenario,
        "trade_day": trade_day.isoformat(),
        "side": side,
        "symbol": symbol,
        "quantity": quantity,
        "gross_reference_vnd": gross,
        "cash_effect_vnd": -total_cost,
    }
    if metadata:
        row.update(metadata)
    state.trade_rows.append(row)
    return total_cost
