"""V56 research-only tail-risk overlay study for C3/P1.

The live model is not changed. This module reuses the frozen C3 walk-forward
ranking and V43.1 execution assumptions, then adds daily risk overlays for the
single-loser problem. Signals use close t and execute at next-session open.
Risk-exited symbols cannot be repurchased until the next canonical month.
The motivating August-2026 episode is excluded from parameter selection:
calibration ends 2021-12-31, holdout begins 2022-01-01, study ends 2026-07-31.
"""
from __future__ import annotations

import argparse
import bisect
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import weekly_micro_capital_v43 as base
from . import weekly_micro_capital_v43_1 as v43_1

SCHEMA_VERSION = "tail_risk_overlay_v56"
MODEL = base.MODEL
BASE_POLICY = "P1_TOP10_UNDERWEIGHT_BUFFER20"
DEFAULT_ANALYSIS_END = date(2026, 7, 31)
DEFAULT_HOLDOUT_START = date(2022, 1, 1)
PRIMARY_CONTRIBUTION = 250_000
PRIMARY_SCENARIO = "BASE"


@dataclass(frozen=True)
class OverlaySpec:
    overlay_id: str
    stock_stop_loss: float | None = None
    nav_loss_budget: float | None = None
    ma_confirmation_days: int | None = None
    cooldown_until_next_signal: bool = True


OVERLAYS: tuple[OverlaySpec, ...] = (
    OverlaySpec("BASELINE"),
    OverlaySpec("STOP_08", stock_stop_loss=0.08),
    OverlaySpec("STOP_10", stock_stop_loss=0.10),
    OverlaySpec("STOP_12", stock_stop_loss=0.12),
    OverlaySpec("NAVLOSS_075", nav_loss_budget=0.0075),
    OverlaySpec("NAVLOSS_100", nav_loss_budget=0.0100),
    OverlaySpec("NAVLOSS_125", nav_loss_budget=0.0125),
    OverlaySpec("NAVLOSS_100_MA20", nav_loss_budget=0.0100, ma_confirmation_days=20),
    OverlaySpec("STOP_10_MA20", stock_stop_loss=0.10, ma_confirmation_days=20),
)


def _sma(prices: base.PriceStore, symbol: str, day: date, window: int) -> float | None:
    days = prices.history_days.get(symbol) or []
    closes = prices.history_closes.get(symbol) or []
    if not days or not closes or window <= 0:
        return None
    end = bisect.bisect_right(days, day)
    values = closes[max(0, end - window):end]
    if len(values) < window:
        return None
    return fmean(float(value) for value in values)


def risk_trigger(
    spec: OverlaySpec,
    *,
    close_price: float,
    average_cost: float,
    position_quantity: int,
    portfolio_nav: float,
    moving_average: float | None,
) -> dict[str, object] | None:
    if spec.overlay_id == "BASELINE":
        return None
    if close_price <= 0 or average_cost <= 0 or position_quantity <= 0 or portfolio_nav <= 0:
        return None
    stock_return = close_price / average_cost - 1.0
    loss_nav = (close_price - average_cost) * position_quantity / portfolio_nav
    stop_hit = spec.stock_stop_loss is not None and stock_return <= -float(spec.stock_stop_loss)
    nav_hit = spec.nav_loss_budget is not None and loss_nav <= -float(spec.nav_loss_budget)
    if not (stop_hit or nav_hit):
        return None
    if spec.ma_confirmation_days is not None:
        if moving_average is None or moving_average <= 0 or close_price >= moving_average:
            return None
    reasons: list[str] = []
    if stop_hit:
        reasons.append("STOCK_STOP")
    if nav_hit:
        reasons.append("NAV_LOSS_BUDGET")
    if spec.ma_confirmation_days is not None:
        reasons.append(f"BELOW_MA{spec.ma_confirmation_days}")
    return {
        "reason": "+".join(reasons),
        "stock_return": stock_return,
        "position_loss_nav": loss_nav,
        "close_price_vnd": close_price,
        "average_cost_vnd": average_cost,
        "moving_average_vnd": moving_average,
    }


def can_buy_symbol(symbol: str, *, current_signal_index: int, cooldown_signal_index: Mapping[str, int]) -> bool:
    return int(cooldown_signal_index.get(symbol, -10**9)) < current_signal_index


def _sell_all(
    *, symbol: str, day: date, reason: str, slippage_bps: float, cash: float,
    holdings: dict[str, int], average_cost: dict[str, float], prices: base.PriceStore,
    trade_rows: list[dict[str, object]], trigger: Mapping[str, object] | None = None,
) -> tuple[float, float, int]:
    quantity = int(holdings.get(symbol, 0))
    if quantity <= 0:
        return cash, 0.0, 0
    raw_price = prices.opens.get((symbol, day))
    if raw_price is None or raw_price <= 0:
        trade_rows.append({"trade_day": day.isoformat(), "side": "SELL_SKIPPED_MISSING_BAR", "symbol": symbol, "quantity": quantity, "reason": reason})
        return cash, 0.0, 0
    gross = float(raw_price) * quantity
    proceeds = base._sell_proceeds(float(raw_price), quantity, slippage_bps)
    cost_basis = average_cost.get(symbol, 0.0) * quantity
    realized_return = proceeds / cost_basis - 1.0 if cost_basis > 0 else None
    holdings[symbol] = 0
    average_cost.pop(symbol, None)
    row = {
        "trade_day": day.isoformat(), "side": "SELL", "symbol": symbol,
        "quantity": quantity, "reason": reason, "gross_reference_vnd": gross,
        "cash_effect_vnd": proceeds, "realized_return": realized_return,
    }
    if trigger:
        row.update({
            "trigger_reason": trigger.get("reason"),
            "trigger_stock_return": trigger.get("stock_return"),
            "trigger_position_loss_nav": trigger.get("position_loss_nav"),
            "trigger_close_price_vnd": trigger.get("close_price_vnd"),
        })
    trade_rows.append(row)
    return cash + proceeds, gross - proceeds, 1


def _position_tail(*, holdings: Mapping[str, int], average_cost: Mapping[str, float], prices: base.PriceStore, day: date, nav: float) -> tuple[float, float]:
    worst_nav = 0.0
    worst_return = 0.0
    if nav <= 0:
        return worst_nav, worst_return
    for symbol, quantity in holdings.items():
        if quantity <= 0:
            continue
        mark = prices.latest_close(symbol, day)
        cost = average_cost.get(symbol, 0.0)
        if mark is None or mark <= 0 or cost <= 0:
            continue
        worst_return = min(worst_return, float(mark) / cost - 1.0)
        worst_nav = min(worst_nav, (float(mark) - cost) * quantity / nav)
    return worst_nav, worst_return


def simulate_overlay(
    *, spec: OverlaySpec, contribution: int, scenario: str,
    snapshots: Sequence[base.SignalSnapshot], prices: base.PriceStore,
    weekly_days: Sequence[date], analysis_end: date,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    policy = v43_1.POLICIES[BASE_POLICY]
    slippage_bps = float(base.SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    weekly_set = {day for day in weekly_days if day <= analysis_end}
    calendar = [day for day in prices.calendar if weekly_days and weekly_days[0] <= day <= analysis_end]
    if not calendar:
        raise ValueError("V56_NO_CALENDAR")

    cash = 0.0
    holdings: dict[str, int] = {}
    average_cost: dict[str, float] = {}
    outside_counts: dict[str, int] = {}
    cooldown_signal_index: dict[str, int] = {}
    pending_risk: dict[str, dict[str, object]] = {}
    current_signal_index = -1
    current_snapshot: base.SignalSnapshot | None = None
    round_robin_pointer = 0
    fund_units = 0.0
    unit_price = 1.0
    peak_unit_price = 1.0
    max_drawdown = 0.0
    contributions_total = 0.0
    fees_total = 0.0
    buy_count = sell_count = risk_exit_count = missing_trade_bar_count = 0
    cashflows: list[tuple[date, float]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []
    daily_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    weekly_counter = 0

    for day in calendar:
        snapshot_index = bisect.bisect_left(signal_days, day) - 1
        if day in weekly_set and snapshot_index >= 0:
            weekly_counter += 1
            value_before, _ = base._account_value(cash, holdings, prices, day, use_open=True)
            if fund_units > 0.0:
                unit_price = value_before / fund_units
            fund_units += contribution / max(unit_price, 1e-12)
            cash += contribution
            contributions_total += contribution
            cashflows.append((day, -float(contribution)))
            index_open = prices.index_open.get(day)
            if index_open and index_open > 0:
                benchmark_units += contribution / float(index_open)
                benchmark_cashflows.append((day, -float(contribution)))

        for symbol in sorted(tuple(pending_risk)):
            if holdings.get(symbol, 0) <= 0:
                pending_risk.pop(symbol, None)
                continue
            trigger = pending_risk[symbol]
            before_qty = holdings.get(symbol, 0)
            cash, cost, count = _sell_all(
                symbol=symbol, day=day, reason="RISK_OVERLAY", slippage_bps=slippage_bps,
                cash=cash, holdings=holdings, average_cost=average_cost, prices=prices,
                trade_rows=trade_rows, trigger=trigger,
            )
            if count:
                fees_total += cost
                sell_count += count
                risk_exit_count += count
                outside_counts[symbol] = 0
                if spec.cooldown_until_next_signal:
                    cooldown_signal_index[symbol] = max(snapshot_index, 0)
                pending_risk.pop(symbol, None)
            elif before_qty > 0:
                missing_trade_bar_count += 1

        if day in weekly_set and snapshot_index >= 0:
            signal_changed = snapshot_index != current_signal_index
            if signal_changed:
                current_signal_index = snapshot_index
                current_snapshot = snapshots[snapshot_index]
                ranks = {symbol: rank for rank, symbol in enumerate(current_snapshot.ranking, start=1)}
                sell_symbols = base.compute_exit_symbols(
                    holdings, ranks, outside_counts,
                    exit_rank=int(policy["exit_rank"]), exit_months=int(policy["exit_months"]),
                )
                for symbol in sell_symbols:
                    cash, cost, count = _sell_all(
                        symbol=symbol, day=day, reason="MONTHLY_EXIT", slippage_bps=slippage_bps,
                        cash=cash, holdings=holdings, average_cost=average_cost, prices=prices,
                        trade_rows=trade_rows,
                    )
                    fees_total += cost
                    sell_count += count
                    if count:
                        outside_counts[symbol] = 0
                    elif holdings.get(symbol, 0) > 0:
                        missing_trade_bar_count += 1
                    pending_risk.pop(symbol, None)
            assert current_snapshot is not None
            target_count = int(policy["target_count"])
            target_symbols = list(current_snapshot.ranking[:target_count])
            target_weights = base.capped_inverse_vol_weights(
                current_snapshot.ranking, current_snapshot.volatility,
                target_count=target_count, symbol_cap=float(policy["symbol_cap"]),
            )
            eligible_targets = [
                symbol for symbol in target_symbols
                if can_buy_symbol(symbol, current_signal_index=current_signal_index, cooldown_signal_index=cooldown_signal_index)
            ]
            account_value_open, _ = base._account_value(cash, holdings, prices, day, use_open=True)
            cash_ceiling = v43_1.deployable_cash(
                policy_id=BASE_POLICY, cash=cash, contribution=contribution,
                risk_on=current_snapshot.risk_on,
            )
            buy_symbol, round_robin_pointer, buy_budget, _, _ = v43_1._buy_candidates(
                rule=str(policy["buy_rule"]), target_symbols=eligible_targets,
                target_weights=target_weights, holdings=holdings, prices=prices, day=day,
                account_value=account_value_open, deployable=cash_ceiling,
                contribution=contribution, target_count=target_count,
                base_symbol_cap=float(policy["symbol_cap"]), slippage_bps=slippage_bps,
                round_robin_pointer=round_robin_pointer,
            )
            if buy_symbol is not None:
                raw_price = float(prices.opens[(buy_symbol, day)])
                quantity = base.affordable_quantity(buy_budget, raw_price, slippage_bps)
                total_cost = base._buy_total(raw_price, quantity, slippage_bps)
                while quantity > 0 and total_cost > cash + 1e-8:
                    quantity -= 1
                    total_cost = base._buy_total(raw_price, quantity, slippage_bps)
                if quantity > 0:
                    old_qty = int(holdings.get(buy_symbol, 0))
                    old_cost = average_cost.get(buy_symbol, 0.0) * old_qty
                    new_qty = old_qty + quantity
                    average_cost[buy_symbol] = (old_cost + total_cost) / new_qty
                    holdings[buy_symbol] = new_qty
                    cash -= total_cost
                    fees_total += total_cost - raw_price * quantity
                    buy_count += 1
                    trade_rows.append({
                        "trade_day": day.isoformat(), "side": "BUY", "symbol": buy_symbol,
                        "quantity": quantity, "reason": "P1_UNDERWEIGHT",
                        "gross_reference_vnd": raw_price * quantity, "cash_effect_vnd": -total_cost,
                        "average_cost_after_vnd": average_cost[buy_symbol],
                    })

        if fund_units <= 0.0:
            continue
        end_value, _ = base._account_value(cash, holdings, prices, day, use_open=False)
        unit_price = end_value / fund_units
        peak_unit_price = max(peak_unit_price, unit_price)
        drawdown = unit_price / peak_unit_price - 1.0
        max_drawdown = min(max_drawdown, drawdown)
        live_positions = {symbol: quantity for symbol, quantity in holdings.items() if quantity > 0}
        largest_weight = 0.0
        for symbol, quantity in live_positions.items():
            mark = prices.latest_close(symbol, day)
            if mark is not None and end_value > 0:
                largest_weight = max(largest_weight, quantity * float(mark) / end_value)
        worst_loss_nav, worst_stock_return = _position_tail(
            holdings=live_positions, average_cost=average_cost, prices=prices, day=day, nav=end_value,
        )
        daily_rows.append({
            "overlay": spec.overlay_id, "contribution": contribution, "scenario": scenario,
            "day": day.isoformat(), "unit_price": unit_price, "portfolio_value_vnd": end_value,
            "cash_vnd": cash, "cash_ratio": cash / end_value if end_value > 0 else 0.0,
            "drawdown": drawdown, "position_count": len(live_positions),
            "largest_symbol_weight": largest_weight, "worst_position_loss_nav": worst_loss_nav,
            "worst_position_return": worst_stock_return,
        })
        if spec.overlay_id != "BASELINE":
            for symbol, quantity in live_positions.items():
                if symbol in pending_risk:
                    continue
                close_price = prices.latest_close(symbol, day)
                cost = average_cost.get(symbol, 0.0)
                if close_price is None or close_price <= 0 or cost <= 0:
                    continue
                ma = _sma(prices, symbol, day, int(spec.ma_confirmation_days)) if spec.ma_confirmation_days is not None else None
                trigger = risk_trigger(
                    spec, close_price=float(close_price), average_cost=cost,
                    position_quantity=quantity, portfolio_nav=end_value, moving_average=ma,
                )
                if trigger is not None:
                    pending_risk[symbol] = {**trigger, "trigger_day": day.isoformat(), "signal_index": current_signal_index}

    if not daily_rows:
        raise ValueError("V56_NO_SIMULATION_ROWS")
    final_day = date.fromisoformat(str(daily_rows[-1]["day"]))
    final_value = float(daily_rows[-1]["portfolio_value_vnd"])
    cashflows.append((final_day, final_value))
    benchmark_close = prices.index_close.get(final_day)
    benchmark_final = benchmark_units * float(benchmark_close) if benchmark_close is not None else 0.0
    benchmark_cashflows.append((final_day, benchmark_final))
    portfolio_xirr = base.xirr(cashflows)
    benchmark_xirr = base.xirr(benchmark_cashflows)
    return {
        "schema_version": SCHEMA_VERSION, "overlay": spec.overlay_id,
        "contribution": contribution, "scenario": scenario, "analysis_end": analysis_end.isoformat(),
        "day_count": len(daily_rows), "week_count": weekly_counter,
        "total_contributed_vnd": contributions_total, "final_value_vnd": final_value,
        "absolute_profit_vnd": final_value - contributions_total, "xirr": portfolio_xirr,
        "benchmark_xirr": benchmark_xirr,
        "xirr_excess": portfolio_xirr - benchmark_xirr if portfolio_xirr is not None and benchmark_xirr is not None else None,
        "max_drawdown": max_drawdown,
        "worst_position_loss_nav": min(float(row["worst_position_loss_nav"]) for row in daily_rows),
        "worst_position_return": min(float(row["worst_position_return"]) for row in daily_rows),
        "buy_order_count": buy_count, "sell_order_count": sell_count,
        "risk_exit_count": risk_exit_count, "estimated_total_cost_vnd": fees_total,
        "missing_trade_bar_count": missing_trade_bar_count, "ending_cash_vnd": cash,
        "ending_cash_ratio": cash / final_value if final_value > 0 else 0.0,
        "live_capital_approved": False,
    }, daily_rows, trade_rows


def segment_metrics(rows: Sequence[Mapping[str, object]], *, start: date | None, end: date) -> dict[str, object]:
    selected = [row for row in rows if (start is None or date.fromisoformat(str(row["day"])) >= start) and date.fromisoformat(str(row["day"])) <= end]
    if len(selected) < 2:
        return {"day_count": len(selected), "annualized_return": None, "max_drawdown": None, "worst_position_loss_nav": None, "worst_position_return": None}
    first_day = date.fromisoformat(str(selected[0]["day"]))
    last_day = date.fromisoformat(str(selected[-1]["day"]))
    first_unit = float(selected[0]["unit_price"])
    last_unit = float(selected[-1]["unit_price"])
    years = max((last_day - first_day).days / 365.25, 1.0 / 365.25)
    annualized = (last_unit / first_unit) ** (1.0 / years) - 1.0 if first_unit > 0 and last_unit > 0 else None
    peak = float(selected[0]["unit_price"])
    max_dd = 0.0
    for row in selected:
        value = float(row["unit_price"])
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return {
        "day_count": len(selected), "first_day": first_day.isoformat(), "last_day": last_day.isoformat(),
        "annualized_return": annualized, "max_drawdown": max_dd,
        "worst_position_loss_nav": min(float(row["worst_position_loss_nav"]) for row in selected),
        "worst_position_return": min(float(row["worst_position_return"]) for row in selected),
        "median_largest_symbol_weight": median(float(row["largest_symbol_weight"]) for row in selected),
        "max_largest_symbol_weight": max(float(row["largest_symbol_weight"]) for row in selected),
    }


def _candidate_selection(summaries: Sequence[Mapping[str, object]]) -> dict[str, object]:
    primary = [row for row in summaries if int(row["contribution"]) == PRIMARY_CONTRIBUTION and str(row["scenario"]) == PRIMARY_SCENARIO]
    by_overlay = {str(row["overlay"]): row for row in primary}
    base_cal = dict(by_overlay["BASELINE"]["calibration"])
    eligible: list[tuple[float, str, Mapping[str, object]]] = []
    for overlay_id, row in by_overlay.items():
        if overlay_id == "BASELINE":
            continue
        cal = dict(row["calibration"])
        required = (cal.get("annualized_return"), base_cal.get("annualized_return"), cal.get("max_drawdown"), base_cal.get("max_drawdown"), cal.get("worst_position_loss_nav"), base_cal.get("worst_position_loss_nav"))
        if any(value is None for value in required):
            continue
        return_diff = float(cal["annualized_return"]) - float(base_cal["annualized_return"])
        dd_improvement = float(cal["max_drawdown"]) - float(base_cal["max_drawdown"])
        tail_improvement = float(cal["worst_position_loss_nav"]) - float(base_cal["worst_position_loss_nav"])
        if return_diff < -0.01 or dd_improvement < -0.005 or tail_improvement <= 0:
            continue
        score = 2.0 * tail_improvement + dd_improvement + 0.25 * return_diff
        eligible.append((score, overlay_id, row))
    if not eligible:
        return {"selected_overlay": "BASELINE", "selection_status": "NO_CALIBRATION_CANDIDATE_PASSED", "selection_uses_holdout": False}
    eligible.sort(reverse=True, key=lambda item: (item[0], item[1]))
    score, overlay_id, row = eligible[0]
    return {"selected_overlay": overlay_id, "selection_status": "SELECTED_ON_CALIBRATION_ONLY", "calibration_score": score, "calibration_metrics": row["calibration"], "selection_uses_holdout": False}


def _holdout_decision(summaries: Sequence[Mapping[str, object]], *, selected_overlay: str) -> dict[str, object]:
    if selected_overlay == "BASELINE":
        return {"decision": "NO_OVERLAY_SELECTED", "reason": "No candidate passed calibration constraints."}
    index = {(int(row["contribution"]), str(row["scenario"]), str(row["overlay"])): row for row in summaries}
    return_diffs: list[float] = []
    dd_improvements: list[float] = []
    tail_improvements: list[float] = []
    cells = tail_wins = dd_wins = 0
    for contribution in sorted(set(int(row["contribution"]) for row in summaries)):
        for scenario in base.SCENARIOS:
            baseline = index.get((contribution, scenario, "BASELINE"))
            selected = index.get((contribution, scenario, selected_overlay))
            if baseline is None or selected is None:
                continue
            b, s = dict(baseline["holdout"]), dict(selected["holdout"])
            required = (b.get("annualized_return"), s.get("annualized_return"), b.get("max_drawdown"), s.get("max_drawdown"), b.get("worst_position_loss_nav"), s.get("worst_position_loss_nav"))
            if any(value is None for value in required):
                continue
            r = float(s["annualized_return"]) - float(b["annualized_return"])
            d = float(s["max_drawdown"]) - float(b["max_drawdown"])
            t = float(s["worst_position_loss_nav"]) - float(b["worst_position_loss_nav"])
            return_diffs.append(r); dd_improvements.append(d); tail_improvements.append(t)
            cells += 1; tail_wins += int(t > 0); dd_wins += int(d > 0)
    if not cells:
        return {"decision": "INCONCLUSIVE", "reason": "No holdout cells."}
    median_return, median_dd, median_tail = median(return_diffs), median(dd_improvements), median(tail_improvements)
    promote = tail_wins >= math.ceil(cells * 0.75) and dd_wins >= math.ceil(cells * 0.50) and median_return >= -0.005 and median_tail >= 0.001
    reject = median_return < -0.015 or median_dd < -0.01
    decision = "PROMOTE_TO_PAPER_RESEARCH" if promote else "REJECT" if reject else "INCONCLUSIVE"
    return {"decision": decision, "holdout_cell_count": cells, "tail_improvement_wins": tail_wins, "drawdown_improvement_wins": dd_wins, "median_annualized_return_diff": median_return, "median_max_drawdown_improvement": median_dd, "median_worst_position_loss_nav_improvement": median_tail, "live_model_change_authorized": False}


def _baseline_parity(*, summaries: Sequence[Mapping[str, object]], snapshots: Sequence[base.SignalSnapshot], prices: base.PriceStore, weekly_days: Sequence[date], analysis_end: date) -> dict[str, object]:
    primary = next(row for row in summaries if row["overlay"] == "BASELINE" and int(row["contribution"]) == PRIMARY_CONTRIBUTION and row["scenario"] == PRIMARY_SCENARIO)
    old, _, _ = v43_1._simulate(policy_id=BASE_POLICY, contribution=PRIMARY_CONTRIBUTION, scenario=PRIMARY_SCENARIO, snapshots=snapshots, prices=prices, weekly_days=[day for day in weekly_days if day <= analysis_end])
    final_diff = abs(float(primary["final_value_vnd"]) - float(old["final_value_vnd"]))
    xirr_new, xirr_old = primary.get("xirr"), old.get("xirr")
    xirr_diff = abs(float(xirr_new) - float(xirr_old)) if xirr_new is not None and xirr_old is not None else None
    return {"status": "PASS" if final_diff <= 0.01 and (xirr_diff is None or xirr_diff <= 1e-10) else "FAIL", "final_value_abs_diff_vnd": final_diff, "xirr_abs_diff": xirr_diff, "v56_final_value_vnd": primary["final_value_vnd"], "v43_1_final_value_vnd": old["final_value_vnd"]}


def _flat_summary(row: Mapping[str, object]) -> dict[str, object]:
    result = {key: value for key, value in row.items() if key not in {"calibration", "holdout"}}
    for prefix in ("calibration", "holdout"):
        for key, value in dict(row[prefix]).items():
            result[f"{prefix}_{key}"] = value
    return result


def run_study(*, input_zip: Path, store_path: Path, output_dir: Path, output_zip: Path, contributions: Sequence[int] = base.CONTRIBUTIONS, price_multiplier: float = base.PRICE_MULTIPLIER, analysis_end: date = DEFAULT_ANALYSIS_END, holdout_start: date = DEFAULT_HOLDOUT_START) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(f"V56_OUTPUT_EXISTS:{output_dir}")
    rows, input_manifest = base._load_research_rows(input_zip)
    snapshots, _, _ = base.build_signal_snapshots(rows)
    prices = base._load_prices(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, snapshots[-1].day, prices.calendar[-1])
    weekly_days = base._weekly_days(prices.calendar, start=snapshots[0].day, end=effective_end)
    if not weekly_days:
        raise ValueError("V56_NO_WEEKLY_DAYS")
    if holdout_start >= effective_end:
        raise ValueError("V56_HOLDOUT_START_AFTER_END")
    calibration_end = date.fromordinal(holdout_start.toordinal() - 1)
    summaries: list[dict[str, object]] = []
    all_daily: list[dict[str, object]] = []
    all_trades: list[dict[str, object]] = []
    for contribution in sorted(set(int(value) for value in contributions)):
        if contribution <= 0:
            raise ValueError("V56_CONTRIBUTION_MUST_BE_POSITIVE")
        for scenario in base.SCENARIOS:
            for spec in OVERLAYS:
                summary, daily, trades = simulate_overlay(spec=spec, contribution=contribution, scenario=scenario, snapshots=snapshots, prices=prices, weekly_days=weekly_days, analysis_end=effective_end)
                summary["calibration"] = segment_metrics(daily, start=None, end=calibration_end)
                summary["holdout"] = segment_metrics(daily, start=holdout_start, end=effective_end)
                summaries.append(summary); all_daily.extend(daily)
                all_trades.extend({"overlay": spec.overlay_id, "contribution": contribution, "scenario": scenario, **trade} for trade in trades)
    parity = _baseline_parity(summaries=summaries, snapshots=snapshots, prices=prices, weekly_days=weekly_days, analysis_end=effective_end)
    if parity["status"] != "PASS":
        raise ValueError("V56_BASELINE_PARITY_FAILED:" + json.dumps(parity, sort_keys=True))
    selection = _candidate_selection(summaries)
    holdout = _holdout_decision(summaries, selected_overlay=str(selection["selected_overlay"]))
    report = {
        "schema_version": SCHEMA_VERSION, "status": "SUCCESS", "model": MODEL,
        "base_policy": BASE_POLICY, "input_manifest_schema": input_manifest.get("schema_version"),
        "input_zip_sha256": sha256(input_zip.read_bytes()).hexdigest(),
        "store_sha256": sha256(store_path.read_bytes()).hexdigest(),
        "first_signal_day": snapshots[0].day.isoformat(), "last_signal_day_available": snapshots[-1].day.isoformat(),
        "effective_analysis_end": effective_end.isoformat(), "holdout_start": holdout_start.isoformat(),
        "calibration_end": calibration_end.isoformat(), "motivating_august_2026_episode_excluded_from_selection": True,
        "overlay_count": len(OVERLAYS), "simulation_count": len(summaries),
        "baseline_parity": parity, "selection": selection, "holdout_decision": holdout,
        "summary_rows": summaries,
        "permissions": {"research_only": True, "live_model_change_authorized": False, "automatic_live_orders_allowed": False},
        "limitations": {"corporate_actions_complete": False, "point_in_time_universe_complete": False, "odd_lot_order_book_history_available": False, "risk_signal_uses_daily_close_next_open_execution": True, "risk_exit_cooldown_until_next_monthly_signal": True, "parameter_selection_uses_holdout": False},
    }
    files = {
        "tail_risk_summary_v56.csv": base._csv_bytes([_flat_summary(row) for row in summaries]),
        "tail_risk_daily_v56.csv": base._csv_bytes(all_daily),
        "tail_risk_trades_v56.csv": base._csv_bytes(all_trades),
        "tail_risk_report_v56.json": base._json_bytes(report),
    }
    files["manifest.json"] = base._json_bytes({"schema_version": SCHEMA_VERSION, "status": "SUCCESS", "files": {name: {"sha256": base._sha(payload), "size_bytes": len(payload)} for name, payload in sorted(files.items())}})
    output_dir.mkdir(parents=True)
    for name, payload in sorted(files.items()):
        (output_dir / name).write_bytes(payload)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_zip, "w", ZIP_DEFLATED) as archive:
        for name in sorted(files):
            archive.writestr(name, files[name])
    with ZipFile(output_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V56_ZIP_CRC_FAILED:{bad}")
    return {"status": "SUCCESS", "output_dir": str(output_dir.resolve()), "output_zip": str(output_zip.resolve()), "output_zip_sha256": sha256(output_zip.read_bytes()).hexdigest(), "selected_overlay": selection["selected_overlay"], "holdout_decision": holdout["decision"], "baseline_parity": parity["status"], "live_model_change_authorized": False}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V56 tail-risk overlay research")
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--contribution", type=int, action="append", dest="contributions")
    parser.add_argument("--price-multiplier", type=float, default=base.PRICE_MULTIPLIER)
    parser.add_argument("--analysis-end", type=date.fromisoformat, default=DEFAULT_ANALYSIS_END)
    parser.add_argument("--holdout-start", type=date.fromisoformat, default=DEFAULT_HOLDOUT_START)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_study(input_zip=args.input_zip, store_path=args.store, output_dir=args.output_dir, output_zip=args.output_zip, contributions=args.contributions or base.CONTRIBUTIONS, price_multiplier=args.price_multiplier, analysis_end=args.analysis_end, holdout_start=args.holdout_start)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "schema_version": SCHEMA_VERSION, "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
