"""V79 unified tactical capital-action research on frozen C3.

Research-only layer above C3_STABLE_3_PAST_IC_SHRUNK. It studies incumbent
risk cuts, exact-L15 emerging admission, weak-to-strong rotation and a combined
policy in one causal matrix. Weekly information is formed after close and can
execute only at the next market open. Candidate selection ends 2025-12-31;
2026 is observed shadow/stress only.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import weekly_overlay_backtest_v72 as v72

SCHEMA_VERSION = "tactical_capital_policy_v79"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
BASELINE_POLICY_ID = "NO_OVERLAY"
SIGNFLIP_SAMPLES = 10_000
BOOTSTRAP_SAMPLES = 5_000
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)
BASE_SLOT_WEIGHT = 0.10


@dataclass(frozen=True)
class CapitalPolicy:
    policy_id: str
    family: str
    risk_rule: str = "NONE"
    risk_fraction: float = 0.0
    leader_mode: str = "NONE"
    leader_fraction: float = 0.0
    cash_slot_fraction: float = 0.0
    anchor_v72_id: str | None = None
    fallback_trim_to_cash: bool = False
    fallback_cash_add: bool = False


POLICIES = (
    CapitalPolicy("NO_OVERLAY", "BASELINE", anchor_v72_id="NO_OVERLAY"),
    CapitalPolicy("R07_TRIM50_CASH", "V72_ANCHOR", anchor_v72_id="R07_TRIM50_CASH"),
    CapitalPolicy("R08_TRIM50_CASH", "V72_ANCHOR", anchor_v72_id="R08_TRIM50_CASH"),
    CapitalPolicy("L15_SWAP50_WORST", "V72_ANCHOR", anchor_v72_id="L15_SWAP50_WORST"),
    CapitalPolicy("DRAG_PERSIST_TRIM25_CASH", "INCUMBENT_CUT", risk_rule="DRAG_PERSIST", risk_fraction=0.25),
    CapitalPolicy("DRAG_PERSIST_TRIM50_CASH", "INCUMBENT_CUT", risk_rule="DRAG_PERSIST", risk_fraction=0.50),
    CapitalPolicy("SEVERE_DRAG_EXIT100_CASH", "INCUMBENT_CUT", risk_rule="SEVERE_DRAG", risk_fraction=1.00),
    CapitalPolicy("L15_SWAP25_WORST", "EMERGING_ADD", leader_mode="SWAP_WORST", leader_fraction=0.25),
    CapitalPolicy("L15_CASH_ADD25_SLOT", "EMERGING_ADD", leader_mode="CASH_ADD", cash_slot_fraction=0.25),
    CapitalPolicy("DRAG_L15_ROTATE25", "ROTATION", risk_rule="DRAG_PERSIST", risk_fraction=0.25,
                  leader_mode="PAIR_RISK", leader_fraction=0.25, fallback_trim_to_cash=True),
    CapitalPolicy("DRAG_L15_ROTATE50", "ROTATION", risk_rule="DRAG_PERSIST", risk_fraction=0.50,
                  leader_mode="PAIR_RISK", leader_fraction=0.50, fallback_trim_to_cash=True),
    CapitalPolicy("COMBINED50_CASHFALLBACK25", "COMBINED", risk_rule="DRAG_PERSIST", risk_fraction=0.50,
                  leader_mode="PAIR_RISK", leader_fraction=0.50, cash_slot_fraction=0.25,
                  fallback_trim_to_cash=True, fallback_cash_add=True),
)
_POLICY_BY_ID = {policy.policy_id: policy for policy in POLICIES}
if len(_POLICY_BY_ID) != len(POLICIES):
    raise RuntimeError("V79_DUPLICATE_POLICY_ID")


def _f(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _i(value: object, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _b(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    rows = list(rows)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(str(key)); fields.append(str(key))
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _gzcsv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    rows = list(rows)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(str(key)); fields.append(str(key))
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def period_drag_metrics(market: v70.Market, symbol: str, signal: v72.WeeklySignal) -> dict[str, object] | None:
    """Month-to-date drag from tradable next-open after monthly signal to weekly close."""
    entry_day = v70._next(market.cal, signal.canonical_day)
    if entry_day is None or signal.evaluation_day < entry_day:
        return None
    values = (
        market.so.get((symbol, entry_day)),
        market.sc.get((symbol, signal.evaluation_day)),
        market.io.get(entry_day),
        market.ic.get(signal.evaluation_day),
    )
    if any(value is None for value in values):
        return None
    stock_open, stock_close, index_open, index_close = (float(value) for value in values)
    if min(stock_open, stock_close, index_open, index_close) <= 0:
        return None
    stock_return = stock_close / stock_open - 1.0
    benchmark_return = index_close / index_open - 1.0
    relative_return = stock_return - benchmark_return
    return {
        "period_entry_day": entry_day.isoformat(),
        "period_return": stock_return,
        "period_benchmark_return": benchmark_return,
        "period_relative_return": relative_return,
        "dragging_current_period": stock_return < 0.0 and relative_return < 0.0,
    }


def _risk_match(policy: CapitalPolicy, row: Mapping[str, object], drag: Mapping[str, object] | None) -> bool:
    if _i(row.get("canonical_rank")) > 10 or policy.risk_rule == "NONE":
        return False
    if policy.risk_rule == "R07":
        return _f(row.get("drawdown_20")) <= -0.08
    if policy.risk_rule == "R08":
        return _f(row.get("drawdown_60")) <= -0.12
    prior = _i(row.get("prior_preview_rank"))
    persistent = _i(row.get("preview_rank")) > 15 and prior < 10**9 and prior > 10
    drag_persist = bool(
        drag and drag.get("dragging_current_period") and persistent and _f(row.get("relative_5")) <= -0.02
    )
    if policy.risk_rule == "DRAG_PERSIST":
        return drag_persist
    if policy.risk_rule == "SEVERE_DRAG":
        severe = (
            not _b(row.get("eligible_now"))
            or _f(row.get("drawdown_20")) <= -0.08
            or _f(row.get("drawdown_60")) <= -0.12
        )
        return drag_persist and severe
    raise ValueError(f"V79_UNKNOWN_RISK_RULE:{policy.risk_rule}")


def _l15(row: Mapping[str, object]) -> bool:
    return v72.trigger_matches("L15_PERSIST_REL", row)


def _risk_candidates(
    market: v70.Market,
    state: v70.State,
    signal: v72.WeeklySignal,
    policy: CapitalPolicy,
    acted: set[str],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for symbol in state.shares:
        if symbol in acted:
            continue
        row = signal.rows.get(symbol)
        if row is None:
            continue
        drag = period_drag_metrics(market, symbol, signal)
        if not _risk_match(policy, row, drag):
            continue
        result.append({**row, **(drag or {})})
    result.sort(key=lambda row: (
        _f(row.get("period_relative_return"), 0.0),
        _f(row.get("period_return"), 0.0),
        -_i(row.get("preview_rank")),
        str(row.get("symbol")),
    ))
    return result


def _leaders(signal: v72.WeeklySignal, state: v70.State, acted: set[str]) -> list[Mapping[str, object]]:
    result = [
        row for row in signal.rows.values()
        if _l15(row) and str(row["symbol"]) not in state.shares and str(row["symbol"]) not in acted
    ]
    result.sort(key=lambda row: (_i(row.get("preview_rank")), -_f(row.get("preview_score"), -1e99), str(row["symbol"])))
    return result


def _decorate(ledger: list[dict[str, object]], before: int, policy: CapitalPolicy, reason: str, paired: str = "") -> None:
    for row in ledger[before:]:
        row["execution_reason"] = reason
        row["overlay_policy_id"] = policy.policy_id
        row["overlay_cohort_id"] = "V79_TACTICAL_CAPITAL_POLICY"
        row["paired_symbol"] = paired


def _sell_fraction(
    state: v70.State, market: v70.Market, signal: v72.WeeklySignal, policy: CapitalPolicy,
    symbol: str, fraction: float, trade_day: date, cost: v70.Cost, settlement: str,
    ledger: list[dict[str, object]], missing: list[dict[str, object]], reason: str,
) -> tuple[int, int]:
    before = state.shares.get(symbol, 0)
    quantity = int(before * fraction) // v70.LOT_SIZE * v70.LOT_SIZE
    if quantity <= 0:
        return before, before
    mark = len(ledger)
    v70._sell(state, market, symbol, quantity, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
    _decorate(ledger, mark, policy, reason)
    after = state.shares.get(symbol, 0)
    if after != before:
        state.desired[symbol] = after
    return before, after


def _buy_cash(
    state: v70.State, market: v70.Market, signal: v72.WeeklySignal, policy: CapitalPolicy,
    leader: str, slot_fraction: float, trade_day: date, cost: v70.Cost, settlement: str,
    ledger: list[dict[str, object]], missing: list[dict[str, object]],
) -> tuple[int, int]:
    raw = market.so.get((leader, trade_day))
    if raw is None or raw <= 0:
        missing.append({"day": trade_day.isoformat(), "symbol": leader, "event": "V79_CASH_ADD_MISSING_OPEN_SKIP"})
        return state.shares.get(leader, 0), state.shares.get(leader, 0)
    nav = v70._value(state, market, trade_day, True, missing)
    current = state.shares.get(leader, 0)
    cap_shares = int((v70.SINGLE_NAME_CAP * nav) // (raw * v70.LOT_SIZE)) * v70.LOT_SIZE
    target_vnd = min(state.cash, nav * BASE_SLOT_WEIGHT * slot_fraction)
    budget = int(target_vnd // (raw * v70.LOT_SIZE)) * v70.LOT_SIZE
    quantity = max(0, min(budget, cap_shares - current))
    if quantity <= 0:
        return current, current
    mark = len(ledger)
    v70._buy(state, market, leader, quantity, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
    _decorate(ledger, mark, policy, "WEEKLY_L15_CASH_ADD")
    after = state.shares.get(leader, 0)
    if after != current:
        state.desired[leader] = max(state.desired.get(leader, 0), after)
    return current, after


def _rotate(
    state: v70.State, market: v70.Market, signal: v72.WeeklySignal, policy: CapitalPolicy,
    incumbent: str, leader: str, fraction: float, trade_day: date, cost: v70.Cost, settlement: str,
    ledger: list[dict[str, object]], missing: list[dict[str, object]],
) -> tuple[int, int, int, int]:
    incumbent_open = market.so.get((incumbent, trade_day)); leader_open = market.so.get((leader, trade_day))
    if incumbent_open is None or leader_open is None or incumbent_open <= 0 or leader_open <= 0:
        missing.append({"day": trade_day.isoformat(), "symbol": leader, "event": "V79_ROTATION_MISSING_OPEN_SKIP"})
        return state.shares.get(incumbent, 0), state.shares.get(incumbent, 0), state.shares.get(leader, 0), state.shares.get(leader, 0)
    nav = v70._value(state, market, trade_day, True, missing)
    before_inc = state.shares.get(incumbent, 0)
    sell_qty = int(before_inc * fraction) // v70.LOT_SIZE * v70.LOT_SIZE
    current_leader = state.shares.get(leader, 0)
    if sell_qty <= 0:
        return before_inc, before_inc, current_leader, current_leader
    cap_shares = int((v70.SINGLE_NAME_CAP * nav) // (leader_open * v70.LOT_SIZE)) * v70.LOT_SIZE
    budget_shares = int((sell_qty * incumbent_open) // (leader_open * v70.LOT_SIZE)) * v70.LOT_SIZE
    buy_qty = max(0, min(budget_shares, cap_shares - current_leader))
    if buy_qty <= 0:
        return before_inc, before_inc, current_leader, current_leader
    mark = len(ledger)
    v70._sell(state, market, incumbent, sell_qty, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
    _decorate(ledger, mark, policy, "WEEKLY_ROTATE_SELL", leader)
    after_inc = state.shares.get(incumbent, 0)
    if after_inc == before_inc:
        return before_inc, before_inc, current_leader, current_leader
    state.desired[incumbent] = after_inc
    state.desired[leader] = max(state.desired.get(leader, 0), current_leader + buy_qty)
    mark = len(ledger)
    v70._buy(state, market, leader, buy_qty, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
    _decorate(ledger, mark, policy, "WEEKLY_ROTATE_BUY", incumbent)
    return before_inc, after_inc, current_leader, state.shares.get(leader, 0)


def _risk_payload(row: Mapping[str, object]) -> dict[str, object]:
    keys = (
        "period_entry_day", "period_return", "period_benchmark_return", "period_relative_return",
        "dragging_current_period", "preview_rank", "prior_preview_rank", "relative_5",
        "drawdown_20", "drawdown_60", "eligible_now",
    )
    return {key: row.get(key) for key in keys}


def _apply_week(
    state: v70.State, market: v70.Market, signal: v72.WeeklySignal, policy: CapitalPolicy,
    last_snap: v70.Snap, trade_day: date, cost: v70.Cost, settlement: str,
    acted_risk: set[str], acted_leaders: set[str], ledger: list[dict[str, object]],
    missing: list[dict[str, object]], actions: list[dict[str, object]],
) -> None:
    leaders = _leaders(signal, state, acted_leaders)
    risks = _risk_candidates(market, state, signal, policy, acted_risk)

    if policy.leader_mode == "PAIR_RISK":
        if leaders and risks:
            leader = str(leaders[0]["symbol"]); risk = risks[0]; incumbent = str(risk["symbol"])
            bi, ai, bl, al = _rotate(state, market, signal, policy, incumbent, leader, policy.leader_fraction,
                                      trade_day, cost, settlement, ledger, missing)
            if ai != bi:
                acted_risk.add(incumbent); acted_leaders.add(leader)
                actions.append({"policy_id": policy.policy_id, "policy_family": policy.family,
                    "signal_day": signal.evaluation_day.isoformat(), "trade_day": trade_day.isoformat(),
                    "action": "ROTATE_RISK_TO_L15", "symbol": incumbent, "paired_symbol": leader,
                    "shares_before": bi, "shares_after": ai, "leader_shares_before": bl,
                    "leader_shares_after": al, "fraction": policy.leader_fraction, **_risk_payload(risk)})
            return
        if risks and policy.fallback_trim_to_cash:
            risk = risks[0]; symbol = str(risk["symbol"])
            before, after = _sell_fraction(state, market, signal, policy, symbol, policy.risk_fraction,
                                             trade_day, cost, settlement, ledger, missing,
                                             "WEEKLY_COMBINED_TRIM_NO_LEADER")
            if after != before:
                acted_risk.add(symbol)
                actions.append({"policy_id": policy.policy_id, "policy_family": policy.family,
                    "signal_day": signal.evaluation_day.isoformat(), "trade_day": trade_day.isoformat(),
                    "action": "TRIM_RISK_TO_CASH_NO_L15", "symbol": symbol, "paired_symbol": "",
                    "shares_before": before, "shares_after": after, "fraction": policy.risk_fraction,
                    **_risk_payload(risk)})
            return
        if leaders and policy.fallback_cash_add and last_snap.risk_on:
            leader = str(leaders[0]["symbol"])
            before, after = _buy_cash(state, market, signal, policy, leader, policy.cash_slot_fraction,
                                       trade_day, cost, settlement, ledger, missing)
            if after != before:
                acted_leaders.add(leader)
                actions.append({"policy_id": policy.policy_id, "policy_family": policy.family,
                    "signal_day": signal.evaluation_day.isoformat(), "trade_day": trade_day.isoformat(),
                    "action": "ADD_L15_FROM_IDLE_CASH", "symbol": leader, "paired_symbol": "",
                    "shares_before": before, "shares_after": after, "slot_fraction": policy.cash_slot_fraction})
            return

    if policy.leader_mode == "SWAP_WORST" and leaders and state.shares:
        held = [signal.rows[symbol] for symbol in state.shares if symbol in signal.rows]
        if not held:
            return
        held.sort(key=lambda row: (-_i(row.get("preview_rank")), _f(row.get("preview_score")), str(row["symbol"])))
        leader = str(leaders[0]["symbol"]); incumbent = str(held[0]["symbol"])
        bi, ai, bl, al = _rotate(state, market, signal, policy, incumbent, leader, policy.leader_fraction,
                                  trade_day, cost, settlement, ledger, missing)
        if ai != bi:
            acted_leaders.add(leader)
            actions.append({"policy_id": policy.policy_id, "policy_family": policy.family,
                "signal_day": signal.evaluation_day.isoformat(), "trade_day": trade_day.isoformat(),
                "action": "L15_SWAP_WORST", "symbol": incumbent, "paired_symbol": leader,
                "shares_before": bi, "shares_after": ai, "leader_shares_before": bl,
                "leader_shares_after": al, "fraction": policy.leader_fraction})
        return

    if policy.leader_mode == "CASH_ADD" and leaders and last_snap.risk_on:
        leader = str(leaders[0]["symbol"])
        before, after = _buy_cash(state, market, signal, policy, leader, policy.cash_slot_fraction,
                                   trade_day, cost, settlement, ledger, missing)
        if after != before:
            acted_leaders.add(leader)
            actions.append({"policy_id": policy.policy_id, "policy_family": policy.family,
                "signal_day": signal.evaluation_day.isoformat(), "trade_day": trade_day.isoformat(),
                "action": "ADD_L15_FROM_IDLE_CASH", "symbol": leader, "paired_symbol": "",
                "shares_before": before, "shares_after": after, "slot_fraction": policy.cash_slot_fraction})
        return

    if policy.risk_rule != "NONE":
        for risk in risks:
            symbol = str(risk["symbol"])
            before, after = _sell_fraction(state, market, signal, policy, symbol, policy.risk_fraction,
                                             trade_day, cost, settlement, ledger, missing, "WEEKLY_V79_RISK_CUT")
            if after == before:
                continue
            acted_risk.add(symbol)
            actions.append({"policy_id": policy.policy_id, "policy_family": policy.family,
                "signal_day": signal.evaluation_day.isoformat(), "trade_day": trade_day.isoformat(),
                "action": "EXIT_TO_CASH" if policy.risk_fraction >= 0.999999 else "TRIM_TO_CASH",
                "symbol": symbol, "paired_symbol": "", "shares_before": before, "shares_after": after,
                "fraction": policy.risk_fraction, **_risk_payload(risk)})


def simulate_capital_policy(
    *, market: v70.Market, monthly_snaps: Sequence[v70.Snap], weekly_signals: Sequence[v72.WeeklySignal],
    policy: CapitalPolicy, allocator: str, cost: v70.Cost, capital: float, variant_id: str,
    settlement: str = "IMMEDIATE",
) -> dict[str, object]:
    if policy.anchor_v72_id:
        anchor = next(item for item in v72.POLICIES if item.policy_id == policy.anchor_v72_id)
        result = v72.simulate_overlay(market=market, monthly_snaps=monthly_snaps, weekly_signals=weekly_signals,
                                      policy=anchor, allocator=allocator, cost=cost, capital=capital,
                                      variant_id=variant_id, settlement=settlement)
        result["summary"]["policy_family"] = policy.family
        return result

    spec = v70.Strategy(f"V79_{policy.policy_id}_{allocator}", allocator, 1.0, settlement)
    pairs = [(v70._next(market.cal, snap.day), snap) for snap in monthly_snaps]
    pairs = [(day, snap) for day, snap in pairs if day is not None]
    if len(pairs) < 3:
        raise ValueError("V79_TOO_FEW_MONTHLY_EVENTS")
    monthly_days = [day for day, _ in pairs]; snaps = [snap for _, snap in pairs]
    first, final = monthly_days[0], monthly_days[-1]
    first_pos, final_pos = v70._pos(market.cal, first), v70._pos(market.cal, final)
    if first_pos is None or final_pos is None:
        raise ValueError("V79_MONTHLY_EVENT_NOT_ON_CALENDAR")
    monthly_lookup = {day: index for index, day in enumerate(monthly_days)}
    weekly_lookup: dict[date, list[v72.WeeklySignal]] = {}; suppressed = 0
    for signal in weekly_signals:
        trade_day = v70._next(market.cal, signal.evaluation_day)
        if trade_day is None or trade_day < first or trade_day > final:
            continue
        if trade_day in monthly_lookup:
            suppressed += 1; continue
        weekly_lookup.setdefault(trade_day, []).append(signal)

    state = v70.State(float(capital), {}, [], {}, {})
    ledger: list[dict[str, object]] = []; missing: list[dict[str, object]] = []
    actions: list[dict[str, object]] = []; daily: list[dict[str, object]] = []; periods: list[dict[str, object]] = []
    checkpoint = float(capital); exposure_at_month: dict[int, float] = {}; last_snap = snaps[0]
    acted_risk: set[str] = set(); acted_leaders: set[str] = set(); benchmark_start = market.io[first]
    shell_policy = v72.OverlayPolicy(policy.policy_id, "V79", None, 0.0)

    for trade_day in market.cal[first_pos:final_pos + 1]:
        if trade_day in monthly_lookup:
            index = monthly_lookup[trade_day]; snap = snaps[index]; last_snap = snap
            acted_risk = set(); acted_leaders = set()
            v72._monthly_rebalance(state, market, snap, spec, cost, trade_day, ledger, missing,
                                   shell_policy, liquidate=index == len(monthly_days) - 1)
            nav_open = v70._value(state, market, trade_day, True, missing)
            exposure_at_month[index] = v70._stock_value(state, market, trade_day, True) / nav_open if nav_open else 0.0
            if index >= 1:
                benchmark_return = market.io[trade_day] / market.io[monthly_days[index - 1]] - 1.0
                strategy_return = nav_open / checkpoint - 1.0
                periods.append({"variant_id": variant_id, "policy_id": policy.policy_id,
                    "policy_family": policy.family, "allocator": allocator, "settlement_mode": settlement,
                    "cost_scenario": cost.name, "period_start_day": monthly_days[index - 1].isoformat(),
                    "period_end_day": trade_day.isoformat(), "strategy_return": strategy_return,
                    "benchmark_return": benchmark_return, "alpha": strategy_return - benchmark_return,
                    "risk_on_at_period_start": snaps[index - 1].risk_on,
                    "actual_stock_exposure_at_period_start": exposure_at_month.get(index - 1)})
            checkpoint = nav_open
        else:
            v72._catchup(state, market, last_snap, spec, cost, trade_day, ledger, missing, shell_policy)
            for signal in sorted(weekly_lookup.get(trade_day, []), key=lambda item: item.evaluation_day):
                _apply_week(state, market, signal, policy, last_snap, trade_day, cost, settlement,
                            acted_risk, acted_leaders, ledger, missing, actions)
        nav_close = v70._value(state, market, trade_day, False, missing)
        stock_value = v70._stock_value(state, market, trade_day, False)
        daily.append({"variant_id": variant_id, "policy_id": policy.policy_id, "policy_family": policy.family,
            "allocator": allocator, "settlement_mode": settlement, "cost_scenario": cost.name,
            "day": trade_day.isoformat(), "nav_close_vnd": nav_close, "equity": nav_close / capital,
            "benchmark_equity": market.ic[trade_day] / benchmark_start, "cash_vnd": state.cash,
            "pending_cash_vnd": sum(value for _, value in state.pending),
            "stock_exposure": stock_value / nav_close if nav_close else 0.0, "position_count": len(state.shares)})

    final_nav = v70._value(state, market, final, True, missing)
    benchmark_final = capital * market.io[final] / benchmark_start
    monthly = [float(row["strategy_return"]) for row in periods]
    bench = [float(row["benchmark_return"]) for row in periods]; alpha = [a - b for a, b in zip(monthly, bench)]
    down = [(a, b) for a, b in zip(monthly, bench) if b < 0]; up = [(a, b) for a, b in zip(monthly, bench) if b >= 0]
    participation = [float(row["participation_adv20"]) for row in ledger if row.get("participation_adv20") not in (None, "")]
    modeled_cost = sum(float(row.get("fee_vnd") or 0.0) + float(row.get("sell_tax_vnd") or 0.0)
                       + float(row.get("transfer_fee_vnd") or 0.0) + float(row.get("slippage_drag_vnd") or 0.0)
                       for row in ledger)
    sell_notional = sum(float(row.get("notional_vnd") or 0.0) for row in ledger if row.get("side") == "SELL")
    cagr = v72._cagr(capital, final_nav, first, final)
    mdd = v72._mdd([float(row["nav_close_vnd"]) for row in daily] + [final_nav])
    summary = {"variant_id": variant_id, "policy_id": policy.policy_id, "policy_family": policy.family,
        "risk_rule": policy.risk_rule, "risk_fraction": policy.risk_fraction, "leader_mode": policy.leader_mode,
        "leader_fraction": policy.leader_fraction, "cash_slot_fraction": policy.cash_slot_fraction,
        "allocator": allocator, "settlement_mode": settlement, "cost_scenario": cost.name,
        "initial_capital_vnd": capital, "first_entry_day": first.isoformat(), "final_liquidation_day": final.isoformat(),
        "period_count": len(periods), "total_return": final_nav / capital - 1.0,
        "benchmark_total_return": benchmark_final / capital - 1.0,
        "total_alpha_arithmetic": (final_nav - benchmark_final) / capital, "ending_nav_vnd": final_nav,
        "cagr": cagr, "max_drawdown_daily": mdd,
        "benchmark_max_drawdown_daily": v72._mdd([float(row["benchmark_equity"]) for row in daily] + [benchmark_final / capital]),
        "monthly_sharpe_rf0": v72._ratio(monthly, "sharpe"), "monthly_sortino_rf0": v72._ratio(monthly, "sortino"),
        "calmar": cagr / abs(mdd) if cagr is not None and mdd < 0 else None,
        "information_ratio_monthly": v72._ir(alpha), "positive_month_rate": sum(x > 0 for x in monthly) / len(monthly),
        "beat_benchmark_month_rate": sum(a > b for a, b in zip(monthly, bench)) / len(monthly),
        "down_market_month_count": len(down), "down_market_mean_alpha": fmean(a - b for a, b in down) if down else None,
        "down_market_beat_rate": sum(a > b for a, b in down) / len(down) if down else None,
        "up_market_month_count": len(up), "up_market_mean_alpha": fmean(a - b for a, b in up) if up else None,
        "up_market_beat_rate": sum(a > b for a, b in up) / len(up) if up else None,
        "trade_count": len(ledger), "overlay_action_count": len(actions),
        "weekly_monthly_collision_suppressed_count": suppressed, "modeled_cost_and_slippage_vnd": modeled_cost,
        "modeled_cost_drag_vs_initial": modeled_cost / capital,
        "mean_monthly_one_way_sell_turnover_vs_initial": sell_notional / capital / max(len(periods), 1),
        "max_adv20_participation": max(participation) if participation else None,
        "trade_rate_adv20_gt_5pct": sum(x > 0.05 for x in participation) / len(participation) if participation else None,
        "trade_rate_adv20_gt_10pct": sum(x > 0.10 for x in participation) / len(participation) if participation else None,
        "missing_price_event_count": len(missing), "final_position_count": len(state.shares),
        "final_pending_cash_vnd": sum(value for _, value in state.pending), "lot_size": v70.LOT_SIZE,
        "single_name_cap": v70.SINGLE_NAME_CAP, "sector_cap_enforced": False,
        "corporate_actions_complete": False, "price_basis_confirmed": False, "pit_hose_confirmed": False}
    return {"summary": summary, "periods": periods, "annual": v72._annual(periods), "rolling": v72._rolling(periods),
            "ledger": ledger, "daily": daily, "missing": missing, "actions": actions}


def policy_inference(
    monthly_rows: Sequence[Mapping[str, object]], daily_rows: Sequence[Mapping[str, object]],
    *, signflip_samples: int, bootstrap_samples: int,
) -> list[dict[str, object]]:
    metrics = v72._pre2026_metrics(monthly_rows, daily_rows)
    scopes = sorted({(str(row["variant_id"]), str(row["allocator"])) for row in monthly_rows
                     if str(row.get("cost_scenario")) == "BASE_DNSE" and str(row.get("settlement_mode")) == "IMMEDIATE"})
    output: list[dict[str, object]] = []
    for variant, allocator in scopes:
        base: dict[tuple[str, str], Mapping[str, object]] = {}; candidates: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {}
        for row in monthly_rows:
            if str(row.get("variant_id")) != variant or str(row.get("allocator")) != allocator \
                    or str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
                continue
            period = (str(row["period_start_day"]), str(row["period_end_day"])); policy_id = str(row["policy_id"])
            if policy_id == BASELINE_POLICY_ID:
                base[period] = row
            else:
                candidates.setdefault(policy_id, {})[period] = row
        for policy_id, cmap in sorted(candidates.items()):
            paired: list[tuple[date, float]] = []; annual_candidate: dict[int, float] = {}; annual_base: dict[int, float] = {}
            for period in sorted(set(base) & set(cmap)):
                end = date.fromisoformat(period[1])
                if end > PRIMARY_SELECTION_END:
                    continue
                candidate_return = float(cmap[period]["strategy_return"]); base_return = float(base[period]["strategy_return"])
                paired.append((end, candidate_return - base_return))
                annual_candidate[end.year] = annual_candidate.get(end.year, 1.0) * (1.0 + candidate_return)
                annual_base[end.year] = annual_base.get(end.year, 1.0) * (1.0 + base_return)
            if len(paired) < 24:
                raise ValueError(f"V79_TOO_FEW_PRE2026_PAIRED_MONTHS:{variant}:{allocator}:{policy_id}")
            seed = int(sha256(f"V79|{variant}|{allocator}|{policy_id}".encode()).hexdigest()[:8], 16)
            observed, p_value = v72._signflip(paired, signflip_samples, seed)
            ci_low, ci_high = v72._bootstrap_ci(paired, bootstrap_samples, seed ^ 0x79A1)
            years = sorted(set(annual_candidate) & set(annual_base)); deltas = [value for _, value in paired]
            annual_delta = [(annual_candidate[year] - 1.0) - (annual_base[year] - 1.0) for year in years]
            candidate_metrics = metrics[(variant, allocator, policy_id)]; base_metrics = metrics[(variant, allocator, BASELINE_POLICY_ID)]
            policy = _POLICY_BY_ID[policy_id]
            output.append({"variant_id": variant, "allocator": allocator, "policy_id": policy_id,
                "policy_family": policy.family, "comparator": BASELINE_POLICY_ID,
                "selection_period_end": PRIMARY_SELECTION_END.isoformat(), "paired_month_count": len(paired),
                "block_count": len({v72._block_key(day) for day, _ in paired}), "mean_monthly_return_delta": observed,
                "median_monthly_return_delta": median(deltas), "positive_month_delta_rate": sum(x > 0 for x in deltas) / len(deltas),
                "bootstrap_ci025": ci_low, "bootstrap_ci975": ci_high, "signflip_two_sided_p": p_value,
                "pre2026_year_count": len(years), "positive_annual_delta_rate": sum(x > 0 for x in annual_delta) / len(annual_delta),
                "mean_annual_return_delta": fmean(annual_delta), **candidate_metrics,
                "pre2026_total_return_delta": candidate_metrics["pre2026_total_return"] - base_metrics["pre2026_total_return"],
                "pre2026_cagr_delta": candidate_metrics["pre2026_cagr"] - base_metrics["pre2026_cagr"],
                "pre2026_mdd_improvement": candidate_metrics["pre2026_max_drawdown_daily"] - base_metrics["pre2026_max_drawdown_daily"],
                "pre2026_p10_month_improvement": candidate_metrics["pre2026_p10_month"] - base_metrics["pre2026_p10_month"],
                "year_2026_used_for_selection": False, "post_selected_mechanism_audit": True})
    v72._bh(output)
    for row in output:
        return_gate = bool(float(row["mean_monthly_return_delta"]) > 0 and float(row["bh_fdr_q"]) < 0.10
                           and float(row["bootstrap_ci025"]) > 0 and float(row["positive_annual_delta_rate"]) >= 0.60)
        risk_family = str(row["policy_family"]) in {"INCUMBENT_CUT", "ROTATION", "COMBINED"}
        risk_gate = bool(risk_family and float(row["pre2026_mdd_improvement"]) >= 0.02
                         and float(row["pre2026_cagr_delta"]) >= -0.01 and float(row["pre2026_p10_month_improvement"]) > 0)
        row["return_watchlist_gate_passed"] = return_gate; row["risk_efficiency_gate_passed"] = risk_gate
        row["diagnostic_watchlist_gate_passed"] = return_gate or risk_gate
    return output


def _family_summary(inference: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
    for row in inference:
        groups.setdefault((str(row["variant_id"]), str(row["allocator"]), str(row["policy_family"])), []).append(row)
    result: list[dict[str, object]] = []
    for (variant, allocator, family), rows in sorted(groups.items()):
        best = max(rows, key=lambda row: float(row["pre2026_total_return_delta"])); best_mdd = max(rows, key=lambda row: float(row["pre2026_mdd_improvement"]))
        result.append({"variant_id": variant, "allocator": allocator, "policy_family": family, "candidate_count": len(rows),
            "best_policy_id": best["policy_id"], "best_mean_monthly_return_delta": best["mean_monthly_return_delta"],
            "best_pre2026_cagr_delta": best["pre2026_cagr_delta"], "best_pre2026_mdd_policy": best_mdd["policy_id"],
            "best_pre2026_mdd_improvement": best_mdd["pre2026_mdd_improvement"],
            "any_watchlist_gate_passed": any(bool(row.get("diagnostic_watchlist_gate_passed")) for row in rows),
            "selection_role": "FAMILY_ABLATION_ONLY_NOT_PROMOTION"})
    return result


def analyze(
    *, v68_output: Path, v70_output: Path, store: Path, output_dir: Path,
    initial_capital: float = 1_000_000_000.0, signflip_samples: int = SIGNFLIP_SAMPLES,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, object]:
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V79_V68_VARIANTS_MISSING")
    v70_report = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if v70_report.get("status") != "SUCCESS" or v70_report.get("champion_model") != CHAMPION_MODEL or _b(v70_report.get("champion_replaced")):
        raise ValueError("V79_V70_BASELINE_CONTRACT_INVALID")
    inputs: dict[str, tuple[list[v70.Snap], list[v72.WeeklySignal]]] = {}; symbols: set[str] = set()
    for variant_dir in sorted(path for path in variants_root.iterdir() if path.is_dir()):
        monthly_path = variant_dir / "v67_c3_monthly_rankings.csv.gz"; weekly_path = variant_dir / "v67_weekly_signal_states.csv.gz"
        if not monthly_path.is_file() or not weekly_path.is_file():
            continue
        monthly = v70.load_snaps(monthly_path); weekly, weekly_symbols = v72.load_weekly_signals(weekly_path)
        inputs[variant_dir.name] = (monthly, weekly); symbols.update(weekly_symbols)
        for snap in monthly:
            symbols.update(snap.symbols)
    if not inputs:
        raise ValueError("V79_NO_VARIANTS")
    market = v70.load_market(store, symbols)
    summaries: list[dict[str, object]] = []; monthly_rows: list[dict[str, object]] = []
    annual_rows: list[dict[str, object]] = []; rolling_rows: list[dict[str, object]] = []
    daily_rows: list[dict[str, object]] = []; ledger_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []; action_rows: list[dict[str, object]] = []; capital_rows: list[dict[str, object]] = []
    for variant_id, (monthly, weekly) in sorted(inputs.items()):
        for allocator in ("EQUAL", "INVOL60"):
            for policy in POLICIES:
                for cost in v70.COSTS:
                    result = simulate_capital_policy(market=market, monthly_snaps=monthly, weekly_signals=weekly,
                        policy=policy, allocator=allocator, cost=cost, capital=initial_capital, variant_id=variant_id)
                    summaries.append(result["summary"]); monthly_rows.extend(result["periods"])
                    annual_rows.extend({**row, "variant_id": variant_id, "policy_id": policy.policy_id,
                        "policy_family": policy.family, "allocator": allocator, "settlement_mode": "IMMEDIATE",
                        "cost_scenario": cost.name, "initial_capital_vnd": initial_capital} for row in result["annual"])
                    rolling_rows.extend({**row, "variant_id": variant_id, "policy_id": policy.policy_id,
                        "policy_family": policy.family, "allocator": allocator, "settlement_mode": "IMMEDIATE",
                        "cost_scenario": cost.name, "initial_capital_vnd": initial_capital} for row in result["rolling"])
                    if cost.name == "BASE_DNSE":
                        daily_rows.extend(result["daily"])
                        ledger_rows.extend({**row, "variant_id": variant_id, "policy_id": policy.policy_id,
                            "policy_family": policy.family, "allocator": allocator, "cost_scenario": cost.name} for row in result["ledger"])
                        missing_rows.extend({**row, "variant_id": variant_id, "policy_id": policy.policy_id,
                            "policy_family": policy.family, "allocator": allocator, "cost_scenario": cost.name} for row in result["missing"])
                        action_rows.extend({**row, "variant_id": variant_id, "allocator": allocator,
                            "cost_scenario": cost.name} for row in result["actions"])
                t2 = simulate_capital_policy(market=market, monthly_snaps=monthly, weekly_signals=weekly, policy=policy,
                    allocator=allocator, cost=v70.COSTS[1], capital=initial_capital, variant_id=variant_id,
                    settlement="T2_NO_ADVANCE")
                summaries.append(t2["summary"])
                for capital in CAPITALS:
                    cap = simulate_capital_policy(market=market, monthly_snaps=monthly, weekly_signals=weekly,
                        policy=policy, allocator=allocator, cost=v70.COSTS[1], capital=capital, variant_id=variant_id)
                    capital_rows.append(cap["summary"])
    baseline_audit = v72._baseline_audit(summaries, v70_output)
    inference = policy_inference(monthly_rows, daily_rows, signflip_samples=signflip_samples, bootstrap_samples=bootstrap_samples)
    shadow = v72._shadow_2026(monthly_rows); cost_drag = v72._cost_drag(summaries); family = _family_summary(inference)
    output_dir.mkdir(parents=True, exist_ok=True)
    _csv(output_dir / "v79_backtest_summary.csv", summaries); _csv(output_dir / "v79_monthly_returns.csv", monthly_rows)
    _csv(output_dir / "v79_annual_returns.csv", annual_rows); _csv(output_dir / "v79_rolling_alpha.csv", rolling_rows)
    _csv(output_dir / "v79_policy_inference.csv", inference); _csv(output_dir / "v79_family_ablation.csv", family)
    _csv(output_dir / "v79_2026_shadow.csv", shadow); _csv(output_dir / "v79_cost_drag.csv", cost_drag)
    _csv(output_dir / "v79_capital_sensitivity.csv", capital_rows); _csv(output_dir / "v79_actions.csv", action_rows)
    _csv(output_dir / "v79_missing_price_events.csv", missing_rows); _gzcsv(output_dir / "v79_trade_ledger_base.csv.gz", ledger_rows)
    _gzcsv(output_dir / "v79_daily_equity_base.csv.gz", daily_rows)
    watchlist = [row for row in inference if _b(row.get("diagnostic_watchlist_gate_passed"))]
    profit_table = [row for row in summaries if str(row.get("cost_scenario")) == "BASE_DNSE"
                    and str(row.get("settlement_mode")) == "IMMEDIATE"
                    and float(row.get("initial_capital_vnd") or 0.0) == float(initial_capital)]
    report = {"schema_version": SCHEMA_VERSION, "status": "SUCCESS", "champion_model": CHAMPION_MODEL,
        "champion_replaced": False, "research_only": True, "promotion_authorized": False,
        "automatic_live_orders_allowed": False, "historical_model_search_reopened": False,
        "portfolio_engine": "V70_EXECUTION_PRIMITIVES", "weekly_signal_source": "V68_CAUSAL_WEEKLY_SIGNAL_STATES",
        "weekly_execution": "AFTER_CLOSE_TO_NEXT_MARKET_OPEN", "monthly_rebalance_precedence": True,
        "period_drag_contract": "NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_WEEKLY_EVALUATION_CLOSE_GROSS",
        "incumbent_persistence_required": True, "exact_l15_reused": True,
        "policy_matrix": [policy.__dict__ for policy in POLICIES], "policy_count": len(POLICIES),
        "baseline_reconstruction_audit": baseline_audit,
        "primary_candidate_selection_end": PRIMARY_SELECTION_END.isoformat(),
        "year_2026_used_for_candidate_selection": False, "year_2026_status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        "signflip_samples": signflip_samples, "bootstrap_samples_ci_only": bootstrap_samples,
        "multiple_testing": "BH_FDR_WITHIN_VARIANT_AND_ALLOCATOR_ACROSS_ALL_NONBASE_POLICIES",
        "diagnostic_watchlist": watchlist, "diagnostic_watchlist_count": len(watchlist), "family_ablation": family,
        "profit_reporting": {"required": True, "base_cost_profit_table": profit_table},
        "robustness": {"cost_scenarios": [cost.name for cost in v70.COSTS], "allocators": ["EQUAL", "INVOL60"],
            "capital_sensitivity_vnd": list(CAPITALS), "t2_no_advance": True, "lot_size": v70.LOT_SIZE,
            "single_name_cap": v70.SINGLE_NAME_CAP},
        "data_gates": {"pit_hose_closed": False, "price_basis_closed": False,
            "corporate_actions_complete": False, "pit_sector_master_closed": False},
        "limitations": ["2026 is shadow/stress and not used to tune V79 thresholds.",
            "PIT HOSE membership, price basis, corporate actions and PIT sector lineage remain fail-closed.",
            "Sector cap 25% is not promotion-ready until a PIT sector master exists.",
            "Cash-add uses only genuinely available simulated cash and never leverage.",
            "V79 changes capital-action policy only; C3 ranking architecture and weights remain frozen."]}
    (output_dir / "v79_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True); parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True); parser.add_argument("--initial-capital", type=float, default=1_000_000_000.0)
    parser.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES); parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    report = analyze(v68_output=args.v68_output, v70_output=args.v70_output, store=args.store,
        output_dir=args.output_dir, initial_capital=args.initial_capital, signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples)
    print(json.dumps({"schema_version": report["schema_version"], "status": report["status"],
        "policy_count": report["policy_count"], "diagnostic_watchlist_count": report["diagnostic_watchlist_count"],
        "champion_replaced": report["champion_replaced"], "promotion_authorized": report["promotion_authorized"],
        "automatic_live_orders_allowed": report["automatic_live_orders_allowed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
