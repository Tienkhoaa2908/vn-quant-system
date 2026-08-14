"""V43.1 weekly micro-capital accumulation with explicit cash redeployment.

V43 correctly generated the frozen C3 rankings and weekly cash-flow ledger, but
regular policies capped every weekly buy at the new contribution. Sale proceeds
therefore accumulated as idle cash and made the policy comparison non-decisive.

V43.1 keeps the same signals, costs, exits, odd-lot unit, contribution schedule,
and one-buy-order-per-week constraint. It changes only portfolio construction:

* regular policies may reuse all available cash;
* the risk-half policy still deploys only half of the new contribution in
  risk-off weeks, but may redeploy accumulated cash after risk-on resumes;
* a single weekly order is limited by the selected symbol's target shortfall and
  a dynamic ramp-up concentration cap, so full cash is not dumped into one name.

Research only. No broker API and no live-capital approval.
"""
from __future__ import annotations

import bisect
from datetime import date
import json
from statistics import fmean, median
from typing import Mapping, Sequence

from . import weekly_micro_capital_v43 as base

SCHEMA_VERSION = "weekly_micro_capital_v43_1"

POLICIES: dict[str, dict[str, object]] = {
    policy_id: {
        **dict(values),
        "cash_redeployment_mode": (
            "RISK_OFF_HALF_THEN_FULL_AVAILABLE_ON_RISK_ON"
            if policy_id == "P6_TOP10_UNDERWEIGHT_BUFFER20_RISK_HALF"
            else "FULL_AVAILABLE_CASH_WITH_TARGET_GAP_LIMIT"
        ),
    }
    for policy_id, values in base.POLICIES.items()
}


def deployable_cash(
    *,
    policy_id: str,
    cash: float,
    contribution: int,
    risk_on: bool,
) -> float:
    """Return the cash ceiling for this week's single buy order."""
    if cash <= 0.0:
        return 0.0
    if policy_id == "P6_TOP10_UNDERWEIGHT_BUFFER20_RISK_HALF" and not risk_on:
        return min(
            cash,
            contribution * float(POLICIES[policy_id]["risk_off_fraction"]),
        )
    return cash


def effective_symbol_cap(
    *,
    base_cap: float,
    target_count: int,
    established_target_positions: int,
    symbol_already_held: bool,
) -> float:
    """Relax concentration only during the unavoidable one-order ramp-up."""
    if target_count <= 0:
        return max(min(base_cap, 1.0), 0.0)
    resulting_count = max(
        established_target_positions + (0 if symbol_already_held else 1),
        1,
    )
    ramp_cap = 1.0 / min(resulting_count, target_count)
    return min(1.0, max(float(base_cap), ramp_cap))


def candidate_budget(
    *,
    symbol: str,
    target_symbols: Sequence[str],
    target_weights: Mapping[str, float],
    holdings: Mapping[str, int],
    prices: base.PriceStore,
    day: date,
    account_value: float,
    deployable: float,
    contribution: int,
    target_count: int,
    base_symbol_cap: float,
    slippage_bps: float,
) -> tuple[float, float, float]:
    """Return executable budget, target shortfall, and effective cap."""
    raw_price = prices.opens.get((symbol, day))
    if raw_price is None or raw_price <= 0.0 or deployable <= 0.0:
        return 0.0, 0.0, float(base_symbol_cap)

    actual_value = holdings.get(symbol, 0) * float(raw_price)
    target_value = float(target_weights.get(symbol, 0.0)) * account_value
    target_gap = max(target_value - actual_value, 0.0)
    established = sum(
        1 for target in target_symbols if holdings.get(target, 0) > 0
    )
    cap = effective_symbol_cap(
        base_cap=base_symbol_cap,
        target_count=target_count,
        established_target_positions=established,
        symbol_already_held=holdings.get(symbol, 0) > 0,
    )
    cap_gap = max(cap * account_value - actual_value, 0.0)
    one_share_cost = base._buy_total(float(raw_price), 1, slippage_bps)
    desired = max(
        target_gap,
        min(float(contribution), deployable),
        one_share_cost,
    )
    budget = min(deployable, desired, cap_gap)
    if budget + 1e-9 < one_share_cost:
        return 0.0, target_gap, cap
    return budget, target_gap, cap


def _buy_candidates(
    *,
    rule: str,
    target_symbols: Sequence[str],
    target_weights: Mapping[str, float],
    holdings: Mapping[str, int],
    prices: base.PriceStore,
    day: date,
    account_value: float,
    deployable: float,
    contribution: int,
    target_count: int,
    base_symbol_cap: float,
    slippage_bps: float,
    round_robin_pointer: int,
) -> tuple[str | None, int, float, float, float]:
    details: dict[str, tuple[float, float, float]] = {}
    for symbol in target_symbols:
        budget, gap, cap = candidate_budget(
            symbol=symbol,
            target_symbols=target_symbols,
            target_weights=target_weights,
            holdings=holdings,
            prices=prices,
            day=day,
            account_value=account_value,
            deployable=deployable,
            contribution=contribution,
            target_count=target_count,
            base_symbol_cap=base_symbol_cap,
            slippage_bps=slippage_bps,
        )
        raw_price = prices.opens.get((symbol, day))
        if raw_price is None:
            continue
        if base.affordable_quantity(
            budget,
            float(raw_price),
            slippage_bps,
        ) >= 1:
            details[symbol] = (budget, gap, cap)
    if not details:
        return None, round_robin_pointer, 0.0, 0.0, float(base_symbol_cap)

    if rule == "HIGHEST_RANK":
        symbol = next(symbol for symbol in target_symbols if symbol in details)
        budget, gap, cap = details[symbol]
        return symbol, round_robin_pointer, budget, gap, cap

    if rule == "ROUND_ROBIN":
        for offset in range(len(target_symbols)):
            index = (round_robin_pointer + offset) % len(target_symbols)
            symbol = target_symbols[index]
            if symbol in details:
                budget, gap, cap = details[symbol]
                return (
                    symbol,
                    (index + 1) % len(target_symbols),
                    budget,
                    gap,
                    cap,
                )

    ranked = sorted(
        (
            (details[symbol][1], -rank, symbol)
            for rank, symbol in enumerate(target_symbols)
            if symbol in details
        ),
        reverse=True,
    )
    _, _, symbol = ranked[0]
    budget, gap, cap = details[symbol]
    return symbol, round_robin_pointer, budget, gap, cap


def _simulate(
    *,
    policy_id: str,
    contribution: int,
    scenario: str,
    snapshots: Sequence[base.SignalSnapshot],
    prices: base.PriceStore,
    weekly_days: Sequence[date],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    policy = POLICIES[policy_id]
    slippage_bps = float(base.SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    cash = 0.0
    holdings: dict[str, int] = {}
    outside_counts: dict[str, int] = {}
    current_signal_index = -1
    current_snapshot: base.SignalSnapshot | None = None
    round_robin_pointer = 0
    fund_units = 0.0
    unit_price = 1.0
    peak_unit_price = 1.0
    max_drawdown = 0.0
    contributions_total = 0.0
    fees_total = 0.0
    buy_count = 0
    sell_count = 0
    missing_trade_bar_count = 0
    stale_valuation_count = 0
    cashflows: list[tuple[date, float]] = []
    weekly_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []
    weekly_cash_ratios: list[float] = []

    for week_number, trade_day in enumerate(weekly_days, start=1):
        snapshot_index = bisect.bisect_left(signal_days, trade_day) - 1
        if snapshot_index < 0:
            continue
        signal_changed = snapshot_index != current_signal_index
        if signal_changed:
            current_signal_index = snapshot_index
            current_snapshot = snapshots[snapshot_index]
        assert current_snapshot is not None

        value_before, stale_before = base._account_value(
            cash,
            holdings,
            prices,
            trade_day,
            use_open=True,
        )
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

        sell_symbols: list[str] = []
        if signal_changed:
            rank_by_symbol = {
                symbol: rank
                for rank, symbol in enumerate(
                    current_snapshot.ranking,
                    start=1,
                )
            }
            sell_symbols = base.compute_exit_symbols(
                holdings,
                rank_by_symbol,
                outside_counts,
                exit_rank=int(policy["exit_rank"]),
                exit_months=int(policy["exit_months"]),
            )
        for symbol in sell_symbols:
            quantity = holdings.get(symbol, 0)
            if quantity <= 0:
                continue
            raw_price = prices.opens.get((symbol, trade_day))
            if raw_price is None:
                missing_trade_bar_count += 1
                trade_rows.append(
                    {
                        "policy": policy_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        "trade_day": trade_day.isoformat(),
                        "side": "SELL_SKIPPED_MISSING_BAR",
                        "symbol": symbol,
                        "quantity": quantity,
                        "gross_reference_vnd": "",
                        "cash_effect_vnd": 0.0,
                    }
                )
                continue
            proceeds = base._sell_proceeds(
                raw_price,
                quantity,
                slippage_bps,
            )
            gross = raw_price * quantity
            fees_total += gross - proceeds
            cash += proceeds
            holdings[symbol] = 0
            outside_counts[symbol] = 0
            sell_count += 1
            trade_rows.append(
                {
                    "policy": policy_id,
                    "contribution": contribution,
                    "scenario": scenario,
                    "trade_day": trade_day.isoformat(),
                    "side": "SELL",
                    "symbol": symbol,
                    "quantity": quantity,
                    "gross_reference_vnd": gross,
                    "cash_effect_vnd": proceeds,
                }
            )

        target_count = int(policy["target_count"])
        target_symbols = list(current_snapshot.ranking[:target_count])
        target_weights = base.capped_inverse_vol_weights(
            current_snapshot.ranking,
            current_snapshot.volatility,
            target_count=target_count,
            symbol_cap=float(policy["symbol_cap"]),
        )
        account_value_open, _ = base._account_value(
            cash,
            holdings,
            prices,
            trade_day,
            use_open=True,
        )
        cash_ceiling = deployable_cash(
            policy_id=policy_id,
            cash=cash,
            contribution=contribution,
            risk_on=current_snapshot.risk_on,
        )
        (
            buy_symbol,
            round_robin_pointer,
            buy_budget,
            target_gap,
            effective_cap,
        ) = _buy_candidates(
            rule=str(policy["buy_rule"]),
            target_symbols=target_symbols,
            target_weights=target_weights,
            holdings=holdings,
            prices=prices,
            day=trade_day,
            account_value=account_value_open,
            deployable=cash_ceiling,
            contribution=contribution,
            target_count=target_count,
            base_symbol_cap=float(policy["symbol_cap"]),
            slippage_bps=slippage_bps,
            round_robin_pointer=round_robin_pointer,
        )

        cash_before_buy = cash
        buy_quantity = 0
        if buy_symbol is not None:
            raw_price = float(prices.opens[(buy_symbol, trade_day)])
            buy_quantity = base.affordable_quantity(
                buy_budget,
                raw_price,
                slippage_bps,
            )
            total_cost = base._buy_total(
                raw_price,
                buy_quantity,
                slippage_bps,
            )
            while buy_quantity > 0 and total_cost > cash + 1e-8:
                buy_quantity -= 1
                total_cost = base._buy_total(
                    raw_price,
                    buy_quantity,
                    slippage_bps,
                )
            if buy_quantity > 0:
                gross = raw_price * buy_quantity
                fees_total += total_cost - gross
                cash -= total_cost
                holdings[buy_symbol] = (
                    holdings.get(buy_symbol, 0) + buy_quantity
                )
                buy_count += 1
                trade_rows.append(
                    {
                        "policy": policy_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        "trade_day": trade_day.isoformat(),
                        "side": "BUY",
                        "symbol": buy_symbol,
                        "quantity": buy_quantity,
                        "gross_reference_vnd": gross,
                        "cash_effect_vnd": -total_cost,
                    }
                )

        end_value, stale_end = base._account_value(
            cash,
            holdings,
            prices,
            trade_day,
            use_open=False,
        )
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
        largest_weight = 0.0
        for symbol, quantity in live_positions.items():
            mark = prices.latest_close(symbol, trade_day)
            if mark is not None and end_value > 0.0:
                largest_weight = max(
                    largest_weight,
                    quantity * mark / end_value,
                )
        cash_ratio = cash / end_value if end_value > 0.0 else 0.0
        weekly_cash_ratios.append(cash_ratio)
        weekly_rows.append(
            {
                "policy": policy_id,
                "contribution": contribution,
                "scenario": scenario,
                "week_number": week_number,
                "trade_day": trade_day.isoformat(),
                "signal_day": current_snapshot.day.isoformat(),
                "risk_on": str(current_snapshot.risk_on).lower(),
                "weekly_contribution_vnd": contribution,
                "cash_available_before_buy_vnd": cash_before_buy,
                "cash_deployment_ceiling_vnd": cash_ceiling,
                "buy_budget_vnd": buy_budget,
                "target_gap_vnd": target_gap,
                "effective_symbol_cap": effective_cap,
                "buy_symbol": buy_symbol or "",
                "buy_quantity": buy_quantity,
                "cash_vnd": cash,
                "cash_ratio": cash_ratio,
                "portfolio_value_vnd": end_value,
                "unit_price": unit_price,
                "drawdown": drawdown,
                "position_count": len(live_positions),
                "largest_symbol_weight": largest_weight,
                "stale_valuation_count": stale_end,
            }
        )

    if not weekly_rows:
        raise ValueError("V43_1_NO_WEEKLY_SIMULATION_ROWS")
    final_day = date.fromisoformat(str(weekly_rows[-1]["trade_day"]))
    final_value = float(weekly_rows[-1]["portfolio_value_vnd"])
    cashflows.append((final_day, final_value))
    index_close = prices.index_close.get(final_day)
    benchmark_final = (
        benchmark_units * index_close if index_close else 0.0
    )
    benchmark_cashflows.append((final_day, benchmark_final))
    live_positions = {
        symbol: quantity
        for symbol, quantity in holdings.items()
        if quantity > 0
    }
    largest_weight = (
        max(
            (
                quantity
                * float(prices.latest_close(symbol, final_day) or 0.0)
                / final_value
                for symbol, quantity in live_positions.items()
            ),
            default=0.0,
        )
        if final_value > 0.0
        else 0.0
    )
    portfolio_xirr = base.xirr(cashflows)
    benchmark_xirr = base.xirr(benchmark_cashflows)
    ending_cash_ratio = cash / final_value if final_value > 0.0 else 0.0
    summary = {
        "protocol_version": SCHEMA_VERSION,
        "policy": policy_id,
        "contribution": contribution,
        "scenario": scenario,
        "week_count": len(weekly_rows),
        "total_contributed_vnd": contributions_total,
        "final_value_vnd": final_value,
        "absolute_profit_vnd": final_value - contributions_total,
        "xirr": portfolio_xirr,
        "benchmark_final_value_vnd": benchmark_final,
        "benchmark_xirr": benchmark_xirr,
        "xirr_excess": (
            portfolio_xirr - benchmark_xirr
            if portfolio_xirr is not None
            and benchmark_xirr is not None
            else None
        ),
        "unitized_total_return": unit_price - 1.0,
        "max_drawdown": max_drawdown,
        "ending_cash_vnd": cash,
        "ending_cash_ratio": ending_cash_ratio,
        "average_weekly_cash_ratio": fmean(weekly_cash_ratios),
        "median_weekly_cash_ratio": median(weekly_cash_ratios),
        "weeks_cash_ratio_above_50pct": sum(
            ratio > 0.50 for ratio in weekly_cash_ratios
        ),
        "cash_redeployment_mode": policy["cash_redeployment_mode"],
        "position_count": len(live_positions),
        "largest_symbol_weight": largest_weight,
        "buy_order_count": buy_count,
        "sell_order_count": sell_count,
        "estimated_total_cost_vnd": fees_total,
        "missing_trade_bar_count": missing_trade_bar_count,
        "stale_valuation_count": stale_valuation_count,
        "odd_lot_share_unit": 1,
        "live_capital_approved": False,
    }
    return summary, weekly_rows, trade_rows


def run_v43_1(**kwargs: object) -> dict[str, object]:
    old_simulate = base._simulate
    old_schema = base.SCHEMA_VERSION
    old_policies = base.POLICIES
    try:
        base._simulate = _simulate
        base.SCHEMA_VERSION = SCHEMA_VERSION
        base.POLICIES = POLICIES
        return base.run_v43(**kwargs)
    finally:
        base._simulate = old_simulate
        base.SCHEMA_VERSION = old_schema
        base.POLICIES = old_policies


def main(argv: Sequence[str] | None = None) -> int:
    args = base._parser().parse_args(argv)
    try:
        result = run_v43_1(
            input_zip=args.input_zip,
            store_path=args.store,
            output_dir=args.output_dir,
            output_zip=args.output_zip,
            contributions=args.contributions or base.CONTRIBUTIONS,
            price_multiplier=args.price_multiplier,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "schema_version": SCHEMA_VERSION,
                    "error": f"{type(exc).__name__}:{exc}",
                },
                sort_keys=True,
            )
        )
        return 2
    result = {**result, "schema_version": SCHEMA_VERSION}
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
