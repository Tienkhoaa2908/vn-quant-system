"""V72 standalone weekly-overlay portfolio backtest on frozen C3.

The frozen monthly C3 champion remains the stock-selection baseline.  V72 tests
three predeclared weekly actions independently:

* R07_DD20_08 -> trim 50% of an affected held name to cash once per monthly cycle;
* R08_DD60_12 -> same action under the longer drawdown trigger;
* L15_PERSIST_REL -> swap 50% of the weekly-worst held position into the best
  newly emerging L15 leader, subject to the existing 15% single-name cap.

Weekly signals are formed after the weekly close and execute at the next market
open.  A monthly C3 rebalance has precedence when both would execute on the same
open.  Candidate inference ends at 2025-12-31.  2026 is observed shadow only.

This is research-only.  No broker/order API, no champion replacement, and no
paper/live promotion is authorized.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import dataclass
from datetime import date
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from statistics import fmean, median, pstdev
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70

SCHEMA_VERSION = "weekly_overlay_backtest_v72"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
SIGNFLIP_SAMPLES = 10_000
BOOTSTRAP_SAMPLES = 5_000
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)


@dataclass(frozen=True)
class OverlayPolicy:
    policy_id: str
    kind: str
    cohort_id: str | None
    fraction: float


POLICIES = (
    OverlayPolicy("NO_OVERLAY", "BASE", None, 0.0),
    OverlayPolicy("R07_TRIM50_CASH", "RISK_TRIM", "R07_DD20_08", 0.50),
    OverlayPolicy("R08_TRIM50_CASH", "RISK_TRIM", "R08_DD60_12", 0.50),
    OverlayPolicy("L15_SWAP50_WORST", "LEADER_SWAP", "L15_PERSIST_REL", 0.50),
)


@dataclass(frozen=True)
class WeeklySignal:
    evaluation_day: date
    canonical_day: date
    rows: Mapping[str, Mapping[str, object]]


def _bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _int(value: object, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    rows = list(rows)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_gz(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    rows = list(rows)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_weekly_signals(path: Path) -> tuple[list[WeeklySignal], set[str]]:
    grouped: dict[date, dict[str, object]] = {}
    symbols: set[str] = set()
    for raw in _read_gz(path):
        try:
            evaluation_day = date.fromisoformat(str(raw["evaluation_day"]))
            canonical_day = date.fromisoformat(str(raw["canonical_day"]))
        except (KeyError, ValueError) as exc:
            raise ValueError("V72_BAD_WEEKLY_SIGNAL_DAY") from exc
        symbol = str(raw.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        symbols.add(symbol)
        bucket = grouped.setdefault(evaluation_day, {"canonical_day": canonical_day, "rows": {}})
        if bucket["canonical_day"] != canonical_day:
            raise ValueError(f"V72_CONFLICTING_CANONICAL_DAY:{evaluation_day}")
        row = {
            "symbol": symbol,
            "phase": str(raw.get("phase") or ""),
            "canonical_rank": _int(raw.get("canonical_rank")),
            "preview_rank": _int(raw.get("preview_rank")),
            "prior_preview_rank": _int(raw.get("prior_preview_rank")),
            "preview_score": _float(raw.get("preview_score"), float("-inf")),
            "rank_delta": _int(raw.get("rank_delta"), 0),
            "score_delta": _float(raw.get("score_delta")),
            "eligible_now": _bool(raw.get("eligible_now")),
            "relative_5": _float(raw.get("relative_5")),
            "drawdown_20": _float(raw.get("drawdown_20")),
            "drawdown_60": _float(raw.get("drawdown_60")),
            "volume_ratio_5_20": _float(raw.get("volume_ratio_5_20")),
        }
        bucket["rows"][symbol] = row
    signals = [
        WeeklySignal(day, item["canonical_day"], dict(item["rows"]))
        for day, item in sorted(grouped.items())
    ]
    if not signals:
        raise ValueError("V72_WEEKLY_SIGNALS_EMPTY")
    return signals, symbols


def trigger_matches(cohort_id: str, row: Mapping[str, object]) -> bool:
    canonical = _int(row.get("canonical_rank")) <= 10
    emerging = _int(row.get("canonical_rank")) > 10
    if cohort_id == "R07_DD20_08":
        return canonical and _float(row.get("drawdown_20")) <= -0.08
    if cohort_id == "R08_DD60_12":
        return canonical and _float(row.get("drawdown_60")) <= -0.12
    if cohort_id == "L15_PERSIST_REL":
        return (
            emerging
            and _int(row.get("preview_rank")) <= 5
            and _int(row.get("prior_preview_rank")) <= 10
            and _float(row.get("relative_5")) >= 0.02
            and _float(row.get("volume_ratio_5_20")) >= 1.0
        )
    raise ValueError(f"V72_UNKNOWN_COHORT:{cohort_id}")


def _decorate_new_ledger(
    ledger: list[dict[str, object]],
    before: int,
    *,
    reason: str,
    policy: OverlayPolicy,
    cohort_id: str | None = None,
    paired_symbol: str | None = None,
) -> None:
    for row in ledger[before:]:
        row["execution_reason"] = reason
        row["overlay_policy_id"] = policy.policy_id
        row["overlay_cohort_id"] = cohort_id or ""
        row["paired_symbol"] = paired_symbol or ""


def _monthly_rebalance(
    state: v70.State,
    market: v70.Market,
    snap: v70.Snap,
    spec: v70.Strategy,
    cost: v70.Cost,
    trade_day: date,
    ledger: list[dict[str, object]],
    missing: list[dict[str, object]],
    policy: OverlayPolicy,
    *,
    liquidate: bool,
) -> None:
    before = len(ledger)
    v70._rebalance(state, market, snap, spec, cost, trade_day, ledger, missing, liquidate=liquidate)
    _decorate_new_ledger(ledger, before, reason="MONTHLY_C3_REBALANCE", policy=policy)


def _catchup(
    state: v70.State,
    market: v70.Market,
    snap: v70.Snap,
    spec: v70.Strategy,
    cost: v70.Cost,
    trade_day: date,
    ledger: list[dict[str, object]],
    missing: list[dict[str, object]],
    policy: OverlayPolicy,
) -> None:
    before = len(ledger)
    v70._catchup(state, market, snap, spec, cost, trade_day, ledger, missing)
    _decorate_new_ledger(ledger, before, reason="T2_CATCHUP", policy=policy)


def _apply_risk_trim(
    *,
    state: v70.State,
    market: v70.Market,
    signal: WeeklySignal,
    policy: OverlayPolicy,
    trade_day: date,
    cost: v70.Cost,
    settlement: str,
    acted_in_cycle: set[str],
    ledger: list[dict[str, object]],
    missing: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> None:
    assert policy.cohort_id is not None
    for symbol in sorted(state.shares):
        if symbol in acted_in_cycle:
            continue
        row = signal.rows.get(symbol)
        if row is None or not trigger_matches(policy.cohort_id, row):
            continue
        before_qty = state.shares.get(symbol, 0)
        sell_qty = int(before_qty * policy.fraction) // v70.LOT_SIZE * v70.LOT_SIZE
        if sell_qty <= 0:
            continue
        before_ledger = len(ledger)
        v70._sell(state, market, symbol, sell_qty, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
        _decorate_new_ledger(
            ledger,
            before_ledger,
            reason="WEEKLY_RISK_TRIM",
            policy=policy,
            cohort_id=policy.cohort_id,
        )
        after_qty = state.shares.get(symbol, 0)
        if after_qty == before_qty:
            continue
        state.desired[symbol] = after_qty
        acted_in_cycle.add(symbol)
        actions.append({
            "policy_id": policy.policy_id,
            "cohort_id": policy.cohort_id,
            "signal_day": signal.evaluation_day.isoformat(),
            "trade_day": trade_day.isoformat(),
            "action": "TRIM_TO_CASH",
            "symbol": symbol,
            "paired_symbol": "",
            "shares_before": before_qty,
            "shares_after": after_qty,
            "fraction": policy.fraction,
        })


def _apply_leader_swap(
    *,
    state: v70.State,
    market: v70.Market,
    signal: WeeklySignal,
    policy: OverlayPolicy,
    trade_day: date,
    cost: v70.Cost,
    settlement: str,
    ledger: list[dict[str, object]],
    missing: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> None:
    assert policy.cohort_id is not None
    leaders = [
        row for row in signal.rows.values()
        if trigger_matches(policy.cohort_id, row) and str(row["symbol"]) not in state.shares
    ]
    if not leaders or not state.shares:
        return
    leaders.sort(key=lambda row: (_int(row.get("preview_rank")), -_float(row.get("preview_score")), str(row["symbol"])))
    leader = str(leaders[0]["symbol"])

    held_rows = []
    for symbol in state.shares:
        row = signal.rows.get(symbol)
        if row is not None:
            held_rows.append(row)
    if not held_rows:
        return
    held_rows.sort(key=lambda row: (-_int(row.get("preview_rank")), _float(row.get("preview_score")), str(row["symbol"])))
    worst = str(held_rows[0]["symbol"])
    if worst == leader:
        return

    nav = v70._value(state, market, trade_day, True, missing)
    worst_open = market.so.get((worst, trade_day))
    leader_open = market.so.get((leader, trade_day))
    if worst_open is None or leader_open is None or worst_open <= 0 or leader_open <= 0:
        missing.append({
            "day": trade_day.isoformat(),
            "symbol": leader if leader_open is None else worst,
            "event": "V72_LEADER_SWAP_MISSING_OPEN_SKIP",
        })
        return

    before_worst = state.shares.get(worst, 0)
    sell_qty = int(before_worst * policy.fraction) // v70.LOT_SIZE * v70.LOT_SIZE
    if sell_qty <= 0:
        return
    target_notional = sell_qty * worst_open
    current_leader = state.shares.get(leader, 0)
    cap_shares = int((v70.SINGLE_NAME_CAP * nav) // (leader_open * v70.LOT_SIZE)) * v70.LOT_SIZE
    budget_shares = int(target_notional // (leader_open * v70.LOT_SIZE)) * v70.LOT_SIZE
    buy_qty = max(0, min(budget_shares, cap_shares - current_leader))
    if buy_qty <= 0:
        return

    before_ledger = len(ledger)
    v70._sell(state, market, worst, sell_qty, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
    _decorate_new_ledger(
        ledger,
        before_ledger,
        reason="WEEKLY_LEADER_SWAP_SELL",
        policy=policy,
        cohort_id=policy.cohort_id,
        paired_symbol=leader,
    )
    after_worst = state.shares.get(worst, 0)
    if after_worst == before_worst:
        return
    state.desired[worst] = after_worst
    desired_leader = current_leader + buy_qty
    state.desired[leader] = max(state.desired.get(leader, 0), desired_leader)

    before_buy = len(ledger)
    v70._buy(state, market, leader, buy_qty, trade_day, signal.evaluation_day, cost, settlement, ledger, missing)
    _decorate_new_ledger(
        ledger,
        before_buy,
        reason="WEEKLY_LEADER_SWAP_BUY",
        policy=policy,
        cohort_id=policy.cohort_id,
        paired_symbol=worst,
    )
    actions.append({
        "policy_id": policy.policy_id,
        "cohort_id": policy.cohort_id,
        "signal_day": signal.evaluation_day.isoformat(),
        "trade_day": trade_day.isoformat(),
        "action": "SWAP_WORST_TO_LEADER",
        "symbol": leader,
        "paired_symbol": worst,
        "shares_before": current_leader,
        "shares_after": state.shares.get(leader, 0),
        "fraction": policy.fraction,
        "desired_leader_shares": state.desired.get(leader, 0),
    })


def _mdd(values: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in values:
        peak = max(peak, float(value))
        if peak > 0:
            worst = min(worst, float(value) / peak - 1.0)
    return worst


def _cagr(a: float, b: float, d0: date, d1: date) -> float | None:
    years = (d1 - d0).days / 365.2425
    if a <= 0 or b <= 0 or years <= 0:
        return None
    return (b / a) ** (1.0 / years) - 1.0


def _ratio(values: Sequence[float], kind: str) -> float | None:
    values = list(values)
    if len(values) < 3:
        return None
    if kind == "sharpe":
        den = pstdev(values)
    else:
        den = math.sqrt(fmean(min(0.0, value) ** 2 for value in values))
    return math.sqrt(12.0) * fmean(values) / den if den else None


def _ir(values: Sequence[float]) -> float | None:
    values = list(values)
    return math.sqrt(12.0) * fmean(values) / pstdev(values) if len(values) >= 3 and pstdev(values) > 0 else None


def _annual(periods: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[int, tuple[float, float]] = {}
    for row in periods:
        year = date.fromisoformat(str(row["period_end_day"])).year
        strategy, benchmark = grouped.get(year, (1.0, 1.0))
        grouped[year] = (
            strategy * (1.0 + float(row["strategy_return"])),
            benchmark * (1.0 + float(row["benchmark_return"])),
        )
    return [
        {"year": year, "strategy_return": strategy - 1.0, "benchmark_return": benchmark - 1.0, "alpha_arithmetic": strategy - benchmark}
        for year, (strategy, benchmark) in sorted(grouped.items())
    ]


def _rolling(periods: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    periods = list(periods)
    for index, row in enumerate(periods):
        for window in (3, 6, 12):
            if index + 1 < window:
                continue
            strategy = benchmark = 1.0
            for item in periods[index - window + 1: index + 1]:
                strategy *= 1.0 + float(item["strategy_return"])
                benchmark *= 1.0 + float(item["benchmark_return"])
            output.append({
                "period_end_day": row["period_end_day"],
                "window_months": window,
                "strategy_return": strategy - 1.0,
                "benchmark_return": benchmark - 1.0,
                "alpha_arithmetic": strategy - benchmark,
            })
    return output


def simulate_overlay(
    *,
    market: v70.Market,
    monthly_snaps: Sequence[v70.Snap],
    weekly_signals: Sequence[WeeklySignal],
    policy: OverlayPolicy,
    allocator: str,
    cost: v70.Cost,
    capital: float,
    variant_id: str,
    settlement: str = "IMMEDIATE",
) -> dict[str, object]:
    spec = v70.Strategy(f"V72_{policy.policy_id}_{allocator}", allocator, 1.0, settlement)
    monthly_pairs = [(v70._next(market.cal, snap.day), snap) for snap in monthly_snaps]
    monthly_pairs = [(day, snap) for day, snap in monthly_pairs if day is not None]
    if len(monthly_pairs) < 3:
        raise ValueError("V72_TOO_FEW_MONTHLY_EVENTS")
    monthly_days = [day for day, _ in monthly_pairs]
    snaps = [snap for _, snap in monthly_pairs]
    first, final = monthly_days[0], monthly_days[-1]
    first_pos, final_pos = v70._pos(market.cal, first), v70._pos(market.cal, final)
    if first_pos is None or final_pos is None:
        raise ValueError("V72_MONTHLY_EVENT_NOT_ON_CALENDAR")
    monthly_lookup = {day: index for index, day in enumerate(monthly_days)}

    weekly_lookup: dict[date, list[WeeklySignal]] = {}
    suppressed = 0
    for signal in weekly_signals:
        trade_day = v70._next(market.cal, signal.evaluation_day)
        if trade_day is None or trade_day < first or trade_day > final:
            continue
        if trade_day in monthly_lookup:
            suppressed += 1
            continue
        weekly_lookup.setdefault(trade_day, []).append(signal)

    state = v70.State(float(capital), {}, [], {}, {})
    ledger: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    actions: list[dict[str, object]] = []
    daily: list[dict[str, object]] = []
    periods: list[dict[str, object]] = []
    checkpoint = float(capital)
    exposure_at_month: dict[int, float] = {}
    last_snap = snaps[0]
    acted_in_cycle: set[str] = set()
    benchmark_start = market.io[first]

    for trade_day in market.cal[first_pos: final_pos + 1]:
        if trade_day in monthly_lookup:
            index = monthly_lookup[trade_day]
            snap = snaps[index]
            last_snap = snap
            acted_in_cycle = set()
            _monthly_rebalance(
                state, market, snap, spec, cost, trade_day, ledger, missing, policy,
                liquidate=index == len(monthly_days) - 1,
            )
            nav_open = v70._value(state, market, trade_day, True, missing)
            exposure_at_month[index] = v70._stock_value(state, market, trade_day, True) / nav_open if nav_open else 0.0
            if index >= 1:
                benchmark_return = market.io[trade_day] / market.io[monthly_days[index - 1]] - 1.0
                strategy_return = nav_open / checkpoint - 1.0
                periods.append({
                    "variant_id": variant_id,
                    "policy_id": policy.policy_id,
                    "allocator": allocator,
                    "settlement_mode": settlement,
                    "cost_scenario": cost.name,
                    "period_start_day": monthly_days[index - 1].isoformat(),
                    "period_end_day": trade_day.isoformat(),
                    "strategy_return": strategy_return,
                    "benchmark_return": benchmark_return,
                    "alpha": strategy_return - benchmark_return,
                    "risk_on_at_period_start": snaps[index - 1].risk_on,
                    "actual_stock_exposure_at_period_start": exposure_at_month.get(index - 1),
                })
            checkpoint = nav_open
        else:
            _catchup(state, market, last_snap, spec, cost, trade_day, ledger, missing, policy)
            for signal in sorted(weekly_lookup.get(trade_day, []), key=lambda item: item.evaluation_day):
                if policy.kind == "RISK_TRIM":
                    _apply_risk_trim(
                        state=state, market=market, signal=signal, policy=policy,
                        trade_day=trade_day, cost=cost, settlement=settlement,
                        acted_in_cycle=acted_in_cycle, ledger=ledger, missing=missing, actions=actions,
                    )
                elif policy.kind == "LEADER_SWAP":
                    _apply_leader_swap(
                        state=state, market=market, signal=signal, policy=policy,
                        trade_day=trade_day, cost=cost, settlement=settlement,
                        ledger=ledger, missing=missing, actions=actions,
                    )

        nav_close = v70._value(state, market, trade_day, False, missing)
        stock_value = v70._stock_value(state, market, trade_day, False)
        daily.append({
            "variant_id": variant_id,
            "policy_id": policy.policy_id,
            "allocator": allocator,
            "settlement_mode": settlement,
            "cost_scenario": cost.name,
            "day": trade_day.isoformat(),
            "nav_close_vnd": nav_close,
            "equity": nav_close / capital,
            "benchmark_equity": market.ic[trade_day] / benchmark_start,
            "cash_vnd": state.cash,
            "pending_cash_vnd": sum(value for _, value in state.pending),
            "stock_exposure": stock_value / nav_close if nav_close else 0.0,
            "position_count": len(state.shares),
        })

    final_nav = v70._value(state, market, final, True, missing)
    benchmark_final = capital * market.io[final] / benchmark_start
    monthly_returns = [float(row["strategy_return"]) for row in periods]
    benchmark_returns = [float(row["benchmark_return"]) for row in periods]
    alpha = [strategy - benchmark for strategy, benchmark in zip(monthly_returns, benchmark_returns)]
    down = [(strategy, benchmark) for strategy, benchmark in zip(monthly_returns, benchmark_returns) if benchmark < 0]
    up = [(strategy, benchmark) for strategy, benchmark in zip(monthly_returns, benchmark_returns) if benchmark >= 0]
    participation = [float(row["participation_adv20"]) for row in ledger if row.get("participation_adv20") not in (None, "")]
    modeled_cost = sum(
        float(row.get("fee_vnd") or 0.0)
        + float(row.get("sell_tax_vnd") or 0.0)
        + float(row.get("transfer_fee_vnd") or 0.0)
        + float(row.get("slippage_drag_vnd") or 0.0)
        for row in ledger
    )
    sell_notional = sum(float(row.get("notional_vnd") or 0.0) for row in ledger if row.get("side") == "SELL")
    cagr = _cagr(capital, final_nav, first, final)
    mdd = _mdd([float(row["nav_close_vnd"]) for row in daily] + [final_nav])
    summary = {
        "variant_id": variant_id,
        "policy_id": policy.policy_id,
        "policy_kind": policy.kind,
        "cohort_id": policy.cohort_id or "",
        "fraction": policy.fraction,
        "allocator": allocator,
        "settlement_mode": settlement,
        "cost_scenario": cost.name,
        "initial_capital_vnd": capital,
        "first_entry_day": first.isoformat(),
        "final_liquidation_day": final.isoformat(),
        "period_count": len(periods),
        "total_return": final_nav / capital - 1.0,
        "benchmark_total_return": benchmark_final / capital - 1.0,
        "total_alpha_arithmetic": (final_nav - benchmark_final) / capital,
        "ending_nav_vnd": final_nav,
        "cagr": cagr,
        "max_drawdown_daily": mdd,
        "benchmark_max_drawdown_daily": _mdd([float(row["benchmark_equity"]) for row in daily] + [benchmark_final / capital]),
        "monthly_sharpe_rf0": _ratio(monthly_returns, "sharpe"),
        "monthly_sortino_rf0": _ratio(monthly_returns, "sortino"),
        "calmar": cagr / abs(mdd) if cagr is not None and mdd < 0 else None,
        "information_ratio_monthly": _ir(alpha),
        "positive_month_rate": sum(value > 0 for value in monthly_returns) / len(monthly_returns),
        "beat_benchmark_month_rate": sum(a > b for a, b in zip(monthly_returns, benchmark_returns)) / len(monthly_returns),
        "down_market_month_count": len(down),
        "down_market_mean_alpha": fmean(a - b for a, b in down) if down else None,
        "down_market_beat_rate": sum(a > b for a, b in down) / len(down) if down else None,
        "up_market_month_count": len(up),
        "up_market_mean_alpha": fmean(a - b for a, b in up) if up else None,
        "up_market_beat_rate": sum(a > b for a, b in up) / len(up) if up else None,
        "trade_count": len(ledger),
        "overlay_action_count": len(actions),
        "weekly_monthly_collision_suppressed_count": suppressed,
        "modeled_cost_and_slippage_vnd": modeled_cost,
        "modeled_cost_drag_vs_initial": modeled_cost / capital,
        "mean_monthly_one_way_sell_turnover_vs_initial": sell_notional / capital / max(len(periods), 1),
        "max_adv20_participation": max(participation) if participation else None,
        "trade_rate_adv20_gt_5pct": sum(value > 0.05 for value in participation) / len(participation) if participation else None,
        "trade_rate_adv20_gt_10pct": sum(value > 0.10 for value in participation) / len(participation) if participation else None,
        "missing_price_event_count": len(missing),
        "final_position_count": len(state.shares),
        "final_pending_cash_vnd": sum(value for _, value in state.pending),
        "lot_size": v70.LOT_SIZE,
        "single_name_cap": v70.SINGLE_NAME_CAP,
        "sector_cap_enforced": False,
        "corporate_actions_complete": False,
        "price_basis_confirmed": False,
        "pit_hose_confirmed": False,
    }
    return {
        "summary": summary,
        "periods": periods,
        "annual": _annual(periods),
        "rolling": _rolling(periods),
        "ledger": ledger,
        "daily": daily,
        "missing": missing,
        "actions": actions,
    }


def _block_key(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 2


def _signflip(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for day, delta in paired:
        blocks.setdefault(_block_key(day), []).append(delta)
    observed = fmean(delta for _, delta in paired)
    block_values = [values for _, values in sorted(blocks.items())]
    rng = random.Random(seed)
    extreme = 0
    for _ in range(max(1, repetitions)):
        sample: list[float] = []
        for values in block_values:
            sign = -1.0 if rng.random() < 0.5 else 1.0
            sample.extend(sign * value for value in values)
        if abs(fmean(sample)) >= abs(observed) - 1e-15:
            extreme += 1
    return observed, (extreme + 1.0) / (max(1, repetitions) + 1.0)


def _bootstrap_ci(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for day, delta in paired:
        blocks.setdefault(_block_key(day), []).append(delta)
    values = [block for _, block in sorted(blocks.items())]
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(max(1, repetitions)):
        sample: list[float] = []
        for _index in range(len(values)):
            sample.extend(values[rng.randrange(len(values))])
        stats.append(fmean(sample))
    stats.sort()
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(0.975 * (len(stats) - 1))]
    return lo, hi


def _bh(rows: list[dict[str, object]]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["variant_id"]), str(row["allocator"])), []).append(row)
    for group in grouped.values():
        ordered = sorted(group, key=lambda row: float(row["signflip_two_sided_p"]))
        m = len(ordered)
        running = 1.0
        adjusted = [1.0] * m
        for index in range(m - 1, -1, -1):
            rank = index + 1
            running = min(running, float(ordered[index]["signflip_two_sided_p"]) * m / rank)
            adjusted[index] = min(1.0, running)
        for row, q in zip(ordered, adjusted):
            row["bh_fdr_q"] = q


def _pre2026_metrics(
    monthly_rows: Sequence[Mapping[str, object]],
    daily_rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str, str], dict[str, float]]:
    result: dict[tuple[str, str, str], dict[str, float]] = {}
    keys = sorted({
        (str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))
        for row in monthly_rows
        if str(row.get("cost_scenario")) == "BASE_DNSE" and str(row.get("settlement_mode")) == "IMMEDIATE"
    })
    for key in keys:
        variant, allocator, policy = key
        periods = [
            row for row in monthly_rows
            if str(row.get("variant_id")) == variant
            and str(row.get("allocator")) == allocator
            and str(row.get("policy_id")) == policy
            and str(row.get("cost_scenario")) == "BASE_DNSE"
            and str(row.get("settlement_mode")) == "IMMEDIATE"
            and date.fromisoformat(str(row["period_end_day"])) <= PRIMARY_SELECTION_END
        ]
        if not periods:
            continue
        wealth = 1.0
        returns: list[float] = []
        for row in periods:
            value = float(row["strategy_return"])
            returns.append(value)
            wealth *= 1.0 + value
        drows = [
            row for row in daily_rows
            if str(row.get("variant_id")) == variant
            and str(row.get("allocator")) == allocator
            and str(row.get("policy_id")) == policy
            and str(row.get("cost_scenario")) == "BASE_DNSE"
            and str(row.get("settlement_mode")) == "IMMEDIATE"
            and date.fromisoformat(str(row["day"])) <= PRIMARY_SELECTION_END
        ]
        drows.sort(key=lambda row: str(row["day"]))
        mdd = _mdd([float(row["nav_close_vnd"]) for row in drows]) if drows else 0.0
        sorted_returns = sorted(returns)
        p10 = sorted_returns[int(0.10 * (len(sorted_returns) - 1))]
        first = date.fromisoformat(str(periods[0]["period_start_day"]))
        last = date.fromisoformat(str(periods[-1]["period_end_day"]))
        cagr = (wealth ** (365.2425 / max((last - first).days, 1)) - 1.0) if wealth > 0 else -1.0
        result[key] = {
            "pre2026_total_return": wealth - 1.0,
            "pre2026_cagr": cagr,
            "pre2026_max_drawdown_daily": mdd,
            "pre2026_worst_month": min(returns),
            "pre2026_p10_month": p10,
        }
    return result


def policy_inference(
    monthly_rows: Sequence[Mapping[str, object]],
    daily_rows: Sequence[Mapping[str, object]],
    *,
    signflip_samples: int,
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    metrics = _pre2026_metrics(monthly_rows, daily_rows)
    scopes = sorted({
        (str(row["variant_id"]), str(row["allocator"]))
        for row in monthly_rows
        if str(row.get("cost_scenario")) == "BASE_DNSE" and str(row.get("settlement_mode")) == "IMMEDIATE"
    })
    output: list[dict[str, object]] = []
    policy_by_id = {policy.policy_id: policy for policy in POLICIES}
    for variant, allocator in scopes:
        base_map: dict[tuple[str, str], Mapping[str, object]] = {}
        candidates: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {}
        for row in monthly_rows:
            if (
                str(row.get("variant_id")) != variant
                or str(row.get("allocator")) != allocator
                or str(row.get("cost_scenario")) != "BASE_DNSE"
                or str(row.get("settlement_mode")) != "IMMEDIATE"
            ):
                continue
            period = (str(row.get("period_start_day")), str(row.get("period_end_day")))
            policy_id = str(row.get("policy_id"))
            if policy_id == "NO_OVERLAY":
                base_map[period] = row
            else:
                candidates.setdefault(policy_id, {})[period] = row
        for policy_id, cmap in sorted(candidates.items()):
            paired: list[tuple[date, float]] = []
            annual_candidate: dict[int, float] = {}
            annual_base: dict[int, float] = {}
            for period in sorted(set(base_map) & set(cmap)):
                end = date.fromisoformat(period[1])
                if end > PRIMARY_SELECTION_END:
                    continue
                candidate_return = float(cmap[period]["strategy_return"])
                base_return = float(base_map[period]["strategy_return"])
                paired.append((end, candidate_return - base_return))
                annual_candidate[end.year] = annual_candidate.get(end.year, 1.0) * (1.0 + candidate_return)
                annual_base[end.year] = annual_base.get(end.year, 1.0) * (1.0 + base_return)
            if len(paired) < 24:
                raise ValueError(f"V72_TOO_FEW_PRE2026_PAIRED_MONTHS:{variant}:{allocator}:{policy_id}")
            seed = int(sha256(f"{variant}|{allocator}|{policy_id}".encode()).hexdigest()[:8], 16)
            observed, p = _signflip(paired, signflip_samples, seed)
            ci_low, ci_high = _bootstrap_ci(paired, bootstrap_samples, seed ^ 0x72A1)
            years = sorted(set(annual_candidate) & set(annual_base))
            annual_delta = [
                (annual_candidate[year] - 1.0) - (annual_base[year] - 1.0)
                for year in years
            ]
            deltas = [value for _, value in paired]
            candidate_metrics = metrics[(variant, allocator, policy_id)]
            base_metrics = metrics[(variant, allocator, "NO_OVERLAY")]
            spec = policy_by_id[policy_id]
            output.append({
                "variant_id": variant,
                "allocator": allocator,
                "policy_id": policy_id,
                "policy_kind": spec.kind,
                "cohort_id": spec.cohort_id or "",
                "comparator": "NO_OVERLAY",
                "selection_period_end": PRIMARY_SELECTION_END.isoformat(),
                "paired_month_count": len(paired),
                "block_count": len({_block_key(day) for day, _ in paired}),
                "mean_monthly_return_delta": observed,
                "median_monthly_return_delta": median(deltas),
                "positive_month_delta_rate": sum(value > 0 for value in deltas) / len(deltas),
                "bootstrap_ci025": ci_low,
                "bootstrap_ci975": ci_high,
                "signflip_two_sided_p": p,
                "pre2026_year_count": len(years),
                "positive_annual_delta_rate": sum(value > 0 for value in annual_delta) / len(annual_delta),
                "mean_annual_return_delta": fmean(annual_delta),
                **candidate_metrics,
                "pre2026_total_return_delta": candidate_metrics["pre2026_total_return"] - base_metrics["pre2026_total_return"],
                "pre2026_cagr_delta": candidate_metrics["pre2026_cagr"] - base_metrics["pre2026_cagr"],
                "pre2026_mdd_improvement": candidate_metrics["pre2026_max_drawdown_daily"] - base_metrics["pre2026_max_drawdown_daily"],
                "pre2026_p10_month_improvement": candidate_metrics["pre2026_p10_month"] - base_metrics["pre2026_p10_month"],
                "year_2026_used_for_selection": False,
                "post_selected_mechanism_audit": True,
            })
    _bh(output)
    for row in output:
        return_gate = bool(
            float(row["mean_monthly_return_delta"]) > 0
            and float(row["bh_fdr_q"]) < 0.10
            and float(row["bootstrap_ci025"]) > 0
            and float(row["positive_annual_delta_rate"]) >= 0.60
        )
        risk_gate = bool(
            row["policy_kind"] == "RISK_TRIM"
            and float(row["pre2026_mdd_improvement"]) >= 0.02
            and float(row["pre2026_cagr_delta"]) >= -0.01
            and float(row["pre2026_p10_month_improvement"]) > 0
        )
        row["return_watchlist_gate_passed"] = return_gate
        row["risk_efficiency_gate_passed"] = risk_gate
        row["diagnostic_watchlist_gate_passed"] = return_gate or risk_gate
    return output


def _shadow_2026(monthly_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
    for row in monthly_rows:
        if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
            continue
        if not str(row.get("period_end_day") or "").startswith("2026-"):
            continue
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))
        grouped.setdefault(key, []).append(row)
    annual: dict[tuple[str, str, str], float] = {}
    april: dict[tuple[str, str, str], float] = {}
    benchmark: dict[tuple[str, str, str], float] = {}
    for key, rows in grouped.items():
        strategy_wealth = benchmark_wealth = 1.0
        for row in sorted(rows, key=lambda item: str(item["period_end_day"])):
            strategy_wealth *= 1.0 + float(row["strategy_return"])
            benchmark_wealth *= 1.0 + float(row["benchmark_return"])
            if str(row["period_start_day"]).startswith("2026-04"):
                april[key] = float(row["strategy_return"])
        annual[key] = strategy_wealth - 1.0
        benchmark[key] = benchmark_wealth - 1.0
    output: list[dict[str, object]] = []
    for key, strategy_return in sorted(annual.items()):
        variant, allocator, policy_id = key
        base_key = (variant, allocator, "NO_OVERLAY")
        if base_key not in annual:
            continue
        output.append({
            "variant_id": variant,
            "allocator": allocator,
            "policy_id": policy_id,
            "strategy_return": strategy_return,
            "benchmark_return": benchmark[key],
            "alpha_arithmetic": strategy_return - benchmark[key],
            "policy_minus_base_2026_return": strategy_return - annual[base_key],
            "april_2026_return": april.get(key),
            "april_2026_policy_minus_base": (
                april.get(key) - april.get(base_key)
                if key in april and base_key in april else None
            ),
            "used_for_selection": False,
            "status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        })
    return output


def _cost_drag(summary_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, Mapping[str, object]]] = {}
    for row in summary_rows:
        if str(row.get("settlement_mode")) != "IMMEDIATE" or float(row.get("initial_capital_vnd") or 0) != 1_000_000_000.0:
            continue
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))
        grouped.setdefault(key, {})[str(row["cost_scenario"])] = row
    output: list[dict[str, object]] = []
    for (variant, allocator, policy_id), scenarios in sorted(grouped.items()):
        gross = scenarios.get("GROSS")
        if gross is None:
            continue
        for cost_name in ("BASE_DNSE", "STRESS", "SEVERE"):
            row = scenarios.get(cost_name)
            if row is None:
                continue
            output.append({
                "variant_id": variant,
                "allocator": allocator,
                "policy_id": policy_id,
                "cost_scenario": cost_name,
                "total_return_drag_vs_gross": float(row["total_return"]) - float(gross["total_return"]),
                "cagr_drag_vs_gross": float(row["cagr"]) - float(gross["cagr"]),
            })
    return output


def _baseline_audit(summary_rows: Sequence[Mapping[str, object]], v70_output: Path) -> dict[str, object]:
    v70_rows = _read_csv(v70_output / "v70_backtest_summary.csv")
    expected: dict[tuple[str, str, str], Mapping[str, object]] = {}
    allocator_map = {"C3_EQ_ALWAYS": "EQUAL", "C3_INVOL_ALWAYS": "INVOL60"}
    for row in v70_rows:
        strategy_id = str(row.get("strategy_id") or "")
        if strategy_id not in allocator_map:
            continue
        if str(row.get("settlement_mode")) != "IMMEDIATE" or float(row.get("initial_capital_vnd") or 0) != 1_000_000_000.0:
            continue
        expected[(str(row["variant_id"]), allocator_map[strategy_id], str(row["cost_scenario"]))] = row
    max_return_error = max_cagr_error = max_mdd_error = 0.0
    compared = 0
    for row in summary_rows:
        if str(row.get("policy_id")) != "NO_OVERLAY" or str(row.get("settlement_mode")) != "IMMEDIATE" or float(row.get("initial_capital_vnd") or 0) != 1_000_000_000.0:
            continue
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["cost_scenario"]))
        baseline = expected.get(key)
        if baseline is None:
            raise ValueError(f"V72_V70_BASELINE_MISSING:{key}")
        compared += 1
        max_return_error = max(max_return_error, abs(float(row["total_return"]) - float(baseline["total_return"])))
        max_cagr_error = max(max_cagr_error, abs(float(row["cagr"]) - float(baseline["cagr"])))
        max_mdd_error = max(max_mdd_error, abs(float(row["max_drawdown_daily"]) - float(baseline["max_drawdown_daily"])))
    if compared == 0 or max(max_return_error, max_cagr_error, max_mdd_error) > 1e-10:
        raise ValueError(f"V72_V70_BASELINE_RECONSTRUCTION_DRIFT:{compared}:{max_return_error}:{max_cagr_error}:{max_mdd_error}")
    return {
        "compared_summary_count": compared,
        "max_total_return_error": max_return_error,
        "max_cagr_error": max_cagr_error,
        "max_mdd_error": max_mdd_error,
    }


def analyze(
    *,
    v68_output: Path,
    v70_output: Path,
    store: Path,
    output_dir: Path,
    initial_capital: float = 1_000_000_000.0,
    signflip_samples: int = SIGNFLIP_SAMPLES,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, object]:
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V72_V68_VARIANTS_MISSING")
    v70_report = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if v70_report.get("status") != "SUCCESS" or v70_report.get("champion_model") != CHAMPION_MODEL or bool(v70_report.get("champion_replaced")):
        raise ValueError("V72_V70_BASELINE_CONTRACT_INVALID")

    inputs: dict[str, tuple[list[v70.Snap], list[WeeklySignal]]] = {}
    all_symbols: set[str] = set()
    for variant_dir in sorted(path for path in variants_root.iterdir() if path.is_dir()):
        monthly_path = variant_dir / "v67_c3_monthly_rankings.csv.gz"
        weekly_path = variant_dir / "v67_weekly_signal_states.csv.gz"
        if not monthly_path.is_file() or not weekly_path.is_file():
            continue
        monthly = v70.load_snaps(monthly_path)
        weekly, weekly_symbols = load_weekly_signals(weekly_path)
        inputs[variant_dir.name] = (monthly, weekly)
        all_symbols.update(weekly_symbols)
        for snap in monthly:
            all_symbols.update(snap.symbols)
    if not inputs:
        raise ValueError("V72_NO_VARIANTS")
    market = v70.load_market(store, all_symbols)

    summaries: list[dict[str, object]] = []
    monthly_rows: list[dict[str, object]] = []
    annual_rows: list[dict[str, object]] = []
    rolling_rows: list[dict[str, object]] = []
    daily_rows: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    action_rows: list[dict[str, object]] = []
    capital_rows: list[dict[str, object]] = []

    for variant_id, (monthly, weekly) in sorted(inputs.items()):
        for allocator in ("EQUAL", "INVOL60"):
            for policy in POLICIES:
                for cost in v70.COSTS:
                    result = simulate_overlay(
                        market=market, monthly_snaps=monthly, weekly_signals=weekly,
                        policy=policy, allocator=allocator, cost=cost,
                        capital=initial_capital, variant_id=variant_id,
                    )
                    summaries.append(result["summary"])
                    monthly_rows.extend(result["periods"])
                    annual_rows.extend([
                        {**row, "variant_id": variant_id, "policy_id": policy.policy_id, "allocator": allocator,
                         "settlement_mode": "IMMEDIATE", "cost_scenario": cost.name, "initial_capital_vnd": initial_capital}
                        for row in result["annual"]
                    ])
                    rolling_rows.extend([
                        {**row, "variant_id": variant_id, "policy_id": policy.policy_id, "allocator": allocator,
                         "settlement_mode": "IMMEDIATE", "cost_scenario": cost.name, "initial_capital_vnd": initial_capital}
                        for row in result["rolling"]
                    ])
                    if cost.name == "BASE_DNSE":
                        daily_rows.extend(result["daily"])
                        ledger_rows.extend(result["ledger"])
                        missing_rows.extend({**row, "variant_id": variant_id, "policy_id": policy.policy_id, "allocator": allocator, "cost_scenario": cost.name} for row in result["missing"])
                        action_rows.extend({**row, "variant_id": variant_id, "allocator": allocator, "cost_scenario": cost.name} for row in result["actions"])

                t2_result = simulate_overlay(
                    market=market, monthly_snaps=monthly, weekly_signals=weekly,
                    policy=policy, allocator=allocator, cost=v70.COSTS[1],
                    capital=initial_capital, variant_id=variant_id, settlement="T2_NO_ADVANCE",
                )
                summaries.append(t2_result["summary"])

                for capital in CAPITALS:
                    cap_result = simulate_overlay(
                        market=market, monthly_snaps=monthly, weekly_signals=weekly,
                        policy=policy, allocator=allocator, cost=v70.COSTS[1],
                        capital=capital, variant_id=variant_id,
                    )
                    capital_rows.append(cap_result["summary"])

    baseline_audit = _baseline_audit(summaries, v70_output)
    inference = policy_inference(
        monthly_rows, daily_rows,
        signflip_samples=signflip_samples,
        bootstrap_samples=bootstrap_samples,
    )
    shadow = _shadow_2026(monthly_rows)
    cost_drag = _cost_drag(summaries)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v72_backtest_summary.csv", summaries)
    _write_csv(output_dir / "v72_monthly_returns.csv", monthly_rows)
    _write_csv(output_dir / "v72_annual_returns.csv", annual_rows)
    _write_csv(output_dir / "v72_rolling_alpha.csv", rolling_rows)
    _write_csv(output_dir / "v72_policy_inference.csv", inference)
    _write_csv(output_dir / "v72_2026_shadow.csv", shadow)
    _write_csv(output_dir / "v72_cost_drag.csv", cost_drag)
    _write_csv(output_dir / "v72_capital_sensitivity.csv", capital_rows)
    _write_csv(output_dir / "v72_overlay_actions.csv", action_rows)
    _write_csv(output_dir / "v72_missing_price_events.csv", missing_rows)
    _write_gz(output_dir / "v72_trade_ledger_base.csv.gz", ledger_rows)
    _write_gz(output_dir / "v72_daily_equity_base.csv.gz", daily_rows)

    watchlist = [row for row in inference if bool(row.get("diagnostic_watchlist_gate_passed"))]
    profit_table = [
        row for row in summaries
        if str(row.get("cost_scenario")) == "BASE_DNSE"
        and str(row.get("settlement_mode")) == "IMMEDIATE"
        and float(row.get("initial_capital_vnd") or 0) == float(initial_capital)
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "portfolio_engine_reused": "deep_portfolio_backtest_v70_execution_primitives",
        "baseline_reconstruction_audit": baseline_audit,
        "policies": [policy.__dict__ for policy in POLICIES],
        "policies_combined": False,
        "weekly_signal_execution": "AFTER_WEEKLY_CLOSE_TO_NEXT_MARKET_OPEN",
        "monthly_rebalance_precedence": True,
        "risk_trim_once_per_symbol_per_monthly_cycle": True,
        "leader_max_one_swap_per_week": True,
        "leader_swap_single_name_cap": v70.SINGLE_NAME_CAP,
        "lot_size": v70.LOT_SIZE,
        "cost_scenarios": [cost.name for cost in v70.COSTS],
        "allocators": ["EQUAL", "INVOL60"],
        "capital_sensitivity_vnd": list(CAPITALS),
        "t2_no_advance_sensitivity": True,
        "primary_candidate_selection_end": PRIMARY_SELECTION_END.isoformat(),
        "year_2026_used_for_candidate_selection": False,
        "year_2026_status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        "post_selected_mechanism_audit": True,
        "signflip_samples": signflip_samples,
        "bootstrap_samples_ci_only": bootstrap_samples,
        "multiple_testing": "BH_FDR_WITHIN_VARIANT_AND_ALLOCATOR",
        "diagnostic_watchlist": watchlist,
        "diagnostic_watchlist_count": len(watchlist),
        "profit_reporting": {
            "report_type": "MODELED_COST_DEEP_BACKTEST_WITH_WEEKLY_OVERLAY",
            "base_cost_profit_table": profit_table,
            "daily_equity_output": "v72_daily_equity_base.csv.gz",
            "trade_ledger_output": "v72_trade_ledger_base.csv.gz",
            "overlay_action_output": "v72_overlay_actions.csv",
            "exact_cash_ledger": False,
            "sector_cap_enforced": False,
            "fixed_slippage_is_exact_market_impact": False,
        },
        "adaptive_weight_combined": False,
        "macro_included": False,
        "research_only": True,
        "promotion_authorized": False,
        "automatic_live_orders_allowed": False,
        "limitations": [
            "R07/R08/L15 were historically surfaced before V72; V72 is a post-selected mechanism audit, not a pristine holdout.",
            "2026 is excluded from policy inference and is reported only as observed shadow stress.",
            "PIT HOSE membership, corporate-action/price-basis lineage and PIT sector master remain unresolved canonical data gates.",
            "Modeled costs and fixed slippage are research assumptions, not broker-exact market impact.",
            "Policies are tested standalone; V72 does not stack protection and opportunity actions or adaptive C3 weights.",
            "Historical research cannot authorize live capital without future paper holdout and explicit promotion.",
        ],
    }
    (output_dir / "v72_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--initial-capital", type=float, default=1_000_000_000.0)
    parser.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    report = analyze(
        v68_output=args.v68_output,
        v70_output=args.v70_output,
        store=args.store,
        output_dir=args.output_dir,
        initial_capital=args.initial_capital,
        signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(json.dumps({
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
