"""V83 capital-discipline research on frozen C3.

This package deliberately stops new-leader research. It asks three narrower
questions with fixed, causal rules:

1. When a held C3 name is both absolutely and relatively underwater at the next
   monthly signal, does blocking only the *incremental add* help?
2. Does a 50% cash trim help only after the already-existing V79 SEVERE_DRAG
   condition repeats at two consecutive weekly checkpoints?
3. For brand-new monthly names, is T+1 open systematically worse than T+2 open
   or a 50/50 T+1/T+2 staged entry?

No threshold grid or model search occurs here. 2026 is shadow-only and is never
used to select a rule. The historical portfolio simulations use V70 execution
primitives, EQUAL allocation, immediate settlement and the existing V70 cost
scenarios.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import tactical_capital_policy_v79 as v79
from . import weekly_overlay_backtest_v72 as v72

SCHEMA_VERSION = "capital_discipline_audit_v83"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
INITIAL_CAPITAL_VND = 1_000_000_000.0
BASE_STRATEGY = v70.Strategy("V83_C3_EQ_ALWAYS", "EQUAL", 1.0, "IMMEDIATE")


@dataclass(frozen=True)
class DisciplinePolicy:
    policy_id: str
    block_underwater_adds: bool = False
    persist2_severe_trim50: bool = False


POLICIES = (
    DisciplinePolicy("C3_BASE"),
    DisciplinePolicy("NO_ADD_UNDERWATER", block_underwater_adds=True),
    DisciplinePolicy("PERSIST2_SEVERE_TRIM50", persist2_severe_trim50=True),
    DisciplinePolicy("NO_ADD_PLUS_PERSIST2_TRIM50", True, True),
)
SEVERE_POLICY = v79.CapitalPolicy("V83_SEVERE_PROBE", "V83", risk_rule="SEVERE_DRAG", risk_fraction=0.50)


def _f(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


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
            key = str(key)
            if key not in seen:
                seen.add(key); fields.append(key)
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _scope(day: date) -> str:
    return "PRE2026" if day <= PRIMARY_SELECTION_END else ("Y2026" if day.year == 2026 else "POST2026")


def _next_session(cal: Sequence[date], day: date) -> date | None:
    pos = bisect.bisect_right(cal, day)
    return cal[pos] if pos < len(cal) else None


def _cycle_drag(market: v70.Market, symbol: str, prior_signal: date, current_signal: date) -> dict[str, object] | None:
    entry = v70._next(market.cal, prior_signal)
    if entry is None or current_signal < entry:
        return None
    so = market.so.get((symbol, entry)); sc = market.sc.get((symbol, current_signal))
    io = market.io.get(entry); ic = market.ic.get(current_signal)
    if None in (so, sc, io, ic) or min(float(so), float(sc), float(io), float(ic)) <= 0:
        return None
    stock = float(sc) / float(so) - 1.0
    bench = float(ic) / float(io) - 1.0
    return {
        "entry_day": entry.isoformat(),
        "stock_return": stock,
        "benchmark_return": bench,
        "relative_return": stock - bench,
        "underwater_and_lagging": stock < 0.0 and stock - bench < 0.0,
    }


def _latest_cycle_signal(signals: Sequence[v72.WeeklySignal], canonical_day: date, before_day: date) -> v72.WeeklySignal | None:
    candidates = [s for s in signals if s.canonical_day == canonical_day and s.evaluation_day <= before_day]
    return max(candidates, key=lambda s: s.evaluation_day) if candidates else None


def _monthly_trade_days(market: v70.Market, snaps: Sequence[v70.Snap]) -> dict[date, date]:
    out: dict[date, date] = {}
    for snap in snaps:
        trade = v70._next(market.cal, snap.day)
        if trade is not None:
            out[snap.day] = trade
    return out


def _next_monthly_trade_after(snaps: Sequence[v70.Snap], trade_days: Mapping[date, date], canonical_day: date) -> date | None:
    ordered = [snap.day for snap in sorted(snaps, key=lambda x: x.day)]
    try:
        idx = ordered.index(canonical_day)
    except ValueError:
        return None
    if idx + 1 >= len(ordered):
        return None
    return trade_days.get(ordered[idx + 1])


def _rebalance_with_no_add(
    state: v70.State,
    market: v70.Market,
    snap: v70.Snap,
    prior_snap: v70.Snap | None,
    policy: DisciplinePolicy,
    cost: v70.Cost,
    trade_day: date,
    ledger: list[dict[str, object]],
    missing: list[dict[str, object]],
    events: list[dict[str, object]],
) -> None:
    v70._settle(state, trade_day)
    nav = v70._value(state, market, trade_day, True, missing)
    desired = v70._target(state, market, snap, BASE_STRATEGY, trade_day, nav, missing)
    original = dict(desired)
    if policy.block_underwater_adds and prior_snap is not None:
        for symbol in sorted(set(state.shares) & set(desired)):
            current = int(state.shares.get(symbol, 0)); target = int(desired.get(symbol, 0))
            if target <= current:
                continue
            drag = _cycle_drag(market, symbol, prior_snap.day, snap.day)
            if not drag or not _b(drag.get("underwater_and_lagging")):
                continue
            desired[symbol] = current
            raw = market.so.get((symbol, trade_day))
            events.append({
                "policy_id": policy.policy_id,
                "event": "BLOCK_INCREMENTAL_ADD",
                "signal_day": snap.day.isoformat(),
                "trade_day": trade_day.isoformat(),
                "symbol": symbol,
                "blocked_shares": target - current,
                "blocked_notional_raw_vnd": (target - current) * float(raw) if raw else None,
                **drag,
                "scope": _scope(snap.day),
            })
    state.desired = dict(desired)
    for symbol in sorted(set(state.shares) | set(desired)):
        if state.shares.get(symbol, 0) > desired.get(symbol, 0):
            v70._sell(state, market, symbol, state.shares.get(symbol, 0) - desired.get(symbol, 0), trade_day, snap.day, cost, "IMMEDIATE", ledger, missing)
    for symbol in sorted(desired, key=lambda s: (-desired[s], s)):
        if desired[symbol] > state.shares.get(symbol, 0):
            v70._buy(state, market, symbol, desired[symbol] - state.shares.get(symbol, 0), trade_day, snap.day, cost, "IMMEDIATE", ledger, missing)
    for row in ledger:
        if row.get("signal_day") == snap.day.isoformat() and row.get("trade_day") == trade_day.isoformat():
            row.setdefault("policy_id", policy.policy_id)
            row.setdefault("execution_reason", "MONTHLY_REBALANCE")
    # record whether the target actually wanted to add, even when not blocked
    for symbol in sorted(set(state.shares) & set(original)):
        _ = symbol


def _simulate(
    market: v70.Market,
    snaps: Sequence[v70.Snap],
    weekly: Sequence[v72.WeeklySignal],
    policy: DisciplinePolicy,
    cost: v70.Cost,
    initial_capital: float,
) -> dict[str, object]:
    snaps = sorted(snaps, key=lambda s: s.day)
    trade_days = _monthly_trade_days(market, snaps)
    if len(trade_days) < 2:
        raise ValueError("V83_TOO_FEW_MONTHLY_TRADES")
    first_trade = min(trade_days.values())
    last_signal = max(trade_days)
    last_trade = trade_days[last_signal]
    state = v70.State(cash=float(initial_capital), shares={}, pending=[], mark={}, desired={})
    ledger: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    discipline_events: list[dict[str, object]] = []
    monthly_by_trade = {trade_days[snap.day]: (idx, snap) for idx, snap in enumerate(snaps) if snap.day in trade_days}
    weekly_by_trade: dict[date, list[v72.WeeklySignal]] = defaultdict(list)
    for signal in weekly:
        trade = v70._next(market.cal, signal.evaluation_day)
        boundary = _next_monthly_trade_after(snaps, trade_days, signal.canonical_day)
        if trade is None or (boundary is not None and trade >= boundary):
            continue
        weekly_by_trade[trade].append(signal)

    severe_streak: dict[tuple[date, str], int] = defaultdict(int)
    acted: set[tuple[date, str]] = set()
    daily_nav: list[tuple[date, float]] = []
    start_pos = bisect.bisect_left(market.cal, first_trade)
    for day in market.cal[start_pos:]:
        if day in monthly_by_trade:
            idx, snap = monthly_by_trade[day]
            prior = snaps[idx - 1] if idx > 0 else None
            _rebalance_with_no_add(state, market, snap, prior, policy, cost, day, ledger, missing, discipline_events)
        if policy.persist2_severe_trim50:
            for signal in sorted(weekly_by_trade.get(day, []), key=lambda x: x.evaluation_day):
                for symbol in sorted(list(state.shares)):
                    row = signal.rows.get(symbol)
                    if row is None:
                        continue
                    drag = v79.period_drag_metrics(market, symbol, signal)
                    key = (signal.canonical_day, symbol)
                    matched = v79._risk_match(SEVERE_POLICY, row, drag)
                    severe_streak[key] = severe_streak[key] + 1 if matched else 0
                    if severe_streak[key] < 2 or key in acted:
                        continue
                    before = int(state.shares.get(symbol, 0))
                    qty = int(before * 0.50) // v70.LOT_SIZE * v70.LOT_SIZE
                    if qty <= 0:
                        acted.add(key); continue
                    mark = len(ledger)
                    v70._sell(state, market, symbol, qty, day, signal.evaluation_day, cost, "IMMEDIATE", ledger, missing)
                    after = int(state.shares.get(symbol, 0))
                    if after < before:
                        acted.add(key)
                        state.desired[symbol] = after
                        for item in ledger[mark:]:
                            item["policy_id"] = policy.policy_id
                            item["execution_reason"] = "PERSIST2_SEVERE_TRIM50"
                        discipline_events.append({
                            "policy_id": policy.policy_id,
                            "event": "PERSIST2_SEVERE_TRIM50",
                            "canonical_day": signal.canonical_day.isoformat(),
                            "evaluation_day": signal.evaluation_day.isoformat(),
                            "trade_day": day.isoformat(),
                            "symbol": symbol,
                            "shares_before": before,
                            "shares_after": after,
                            "shares_sold": before - after,
                            "severe_streak": severe_streak[key],
                            "preview_rank": row.get("preview_rank"),
                            "prior_preview_rank": row.get("prior_preview_rank"),
                            "relative_5": row.get("relative_5"),
                            "drawdown_20": row.get("drawdown_20"),
                            "drawdown_60": row.get("drawdown_60"),
                            "period_return": drag.get("period_return") if drag else None,
                            "period_relative_return": drag.get("period_relative_return") if drag else None,
                            "scope": _scope(signal.evaluation_day),
                        })
        if day >= first_trade:
            daily_nav.append((day, v70._value(state, market, day, False, missing)))
        if day >= last_trade and day == market.cal[-1]:
            break
    if not daily_nav:
        raise ValueError("V83_EMPTY_NAV")
    start_day, start_nav = daily_nav[0]
    end_day, end_nav = daily_nav[-1]
    return {
        "policy_id": policy.policy_id,
        "cost_scenario": cost.name,
        "initial_capital_vnd": float(initial_capital),
        "start_day": start_day.isoformat(),
        "end_day": end_day.isoformat(),
        "ending_nav_vnd": end_nav,
        "net_profit_vnd": end_nav - float(initial_capital),
        "total_return": end_nav / float(initial_capital) - 1.0,
        "cagr": v70._cagr(float(initial_capital), end_nav, start_day, end_day),
        "max_drawdown": v70._mdd([nav for _, nav in daily_nav]),
        "trade_count": len(ledger),
        "modeled_cost_and_slippage_vnd": sum(
            _f(row.get("fee_vnd")) + _f(row.get("sell_tax_vnd")) + _f(row.get("transfer_fee_vnd")) + _f(row.get("slippage_drag_vnd"))
            for row in ledger
        ),
        "discipline_event_count": len(discipline_events),
        "events": discipline_events,
        "ledger": ledger,
        "missing": missing,
    }


def _entry_timing_rows(market: v70.Market, snaps: Sequence[v70.Snap], variant_id: str) -> list[dict[str, object]]:
    snaps = sorted(snaps, key=lambda s: s.day)
    rows: list[dict[str, object]] = []
    for idx in range(1, len(snaps) - 1):
        prev, snap, nxt = snaps[idx - 1], snaps[idx], snaps[idx + 1]
        new_symbols = sorted(set(snap.symbols) - set(prev.symbols))
        t1 = v70._next(market.cal, snap.day)
        t2 = v70._next(market.cal, t1) if t1 else None
        boundary = v70._next(market.cal, nxt.day)
        if t1 is None or t2 is None or boundary is None:
            continue
        for symbol in new_symbols:
            p1 = market.so.get((symbol, t1)); p2 = market.so.get((symbol, t2)); pend = market.so.get((symbol, boundary))
            signal_close = market.sc.get((symbol, snap.day))
            if None in (p1, p2, pend, signal_close) or min(float(p1), float(p2), float(pend), float(signal_close)) <= 0:
                continue
            staged = 2.0 / (1.0 / float(p1) + 1.0 / float(p2))
            rows.append({
                "variant_id": variant_id,
                "scope": _scope(snap.day),
                "signal_day": snap.day.isoformat(),
                "symbol": symbol,
                "t1_day": t1.isoformat(),
                "t2_day": t2.isoformat(),
                "boundary_day": boundary.isoformat(),
                "signal_close_vnd": float(signal_close),
                "t1_open_vnd": float(p1),
                "t2_open_vnd": float(p2),
                "staged_effective_open_vnd": staged,
                "t1_gap_from_signal_close": float(p1) / float(signal_close) - 1.0,
                "t2_price_improvement_vs_t1": float(p1) / float(p2) - 1.0,
                "staged_price_improvement_vs_t1": float(p1) / staged - 1.0,
                "t1_to_boundary_return": float(pend) / float(p1) - 1.0,
                "t2_to_boundary_return": float(pend) / float(p2) - 1.0,
                "staged_to_boundary_return": float(pend) / staged - 1.0,
            })
    return rows


def _entry_summary(rows: Sequence[Mapping[str, object]], variant_id: str, scope: str) -> dict[str, object]:
    chosen = [r for r in rows if r.get("variant_id") == variant_id and (scope == "ALL" or r.get("scope") == scope)]
    if not chosen:
        return {"variant_id": variant_id, "scope": scope, "count": 0}
    t2_imp = [_f(r["t2_price_improvement_vs_t1"]) for r in chosen]
    stage_imp = [_f(r["staged_price_improvement_vs_t1"]) for r in chosen]
    t1_ret = [_f(r["t1_to_boundary_return"]) for r in chosen]
    t2_ret = [_f(r["t2_to_boundary_return"]) for r in chosen]
    stage_ret = [_f(r["staged_to_boundary_return"]) for r in chosen]
    return {
        "variant_id": variant_id,
        "scope": scope,
        "count": len(chosen),
        "mean_t1_gap_from_signal_close": fmean(_f(r["t1_gap_from_signal_close"]) for r in chosen),
        "mean_t2_price_improvement_vs_t1": fmean(t2_imp),
        "median_t2_price_improvement_vs_t1": median(t2_imp),
        "t2_cheaper_rate": sum(x > 0 for x in t2_imp) / len(t2_imp),
        "mean_staged_price_improvement_vs_t1": fmean(stage_imp),
        "staged_cheaper_rate": sum(x > 0 for x in stage_imp) / len(stage_imp),
        "mean_boundary_return_t1": fmean(t1_ret),
        "mean_boundary_return_t2": fmean(t2_ret),
        "mean_boundary_return_staged": fmean(stage_ret),
        "mean_boundary_return_delta_t2_vs_t1": fmean(b - a for a, b in zip(t1_ret, t2_ret)),
        "mean_boundary_return_delta_staged_vs_t1": fmean(b - a for a, b in zip(t1_ret, stage_ret)),
    }


def analyze(*, v68_output: Path, v70_output: Path, store: Path, output_dir: Path, initial_capital: float = INITIAL_CAPITAL_VND) -> dict[str, object]:
    report70 = json.loads((Path(v70_output) / "v70_report.json").read_text(encoding="utf-8-sig"))
    if report70.get("status") != "SUCCESS" or report70.get("champion_model") != CHAMPION_MODEL:
        raise ValueError("V83_V70_BASELINE_CONTRACT_INVALID")
    variants_root = Path(v68_output) / "variants"
    inputs: dict[str, tuple[list[v70.Snap], list[v72.WeeklySignal]]] = {}
    symbols: set[str] = set()
    for variant_dir in sorted(path for path in variants_root.iterdir() if path.is_dir()):
        monthly = variant_dir / "v67_c3_monthly_rankings.csv.gz"
        weekly_path = variant_dir / "v67_weekly_signal_states.csv.gz"
        if not monthly.is_file() or not weekly_path.is_file():
            continue
        snaps = v70.load_snaps(monthly)
        weekly, weekly_symbols = v72.load_weekly_signals(weekly_path)
        inputs[variant_dir.name] = (snaps, weekly)
        symbols.update(weekly_symbols)
        for snap in snaps:
            symbols.update(snap.symbols)
    if not inputs:
        raise ValueError("V83_NO_VARIANTS")
    market = v70.load_market(Path(store), symbols)
    summary_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    entry_rows: list[dict[str, object]] = []
    for variant_id, (snaps, weekly) in sorted(inputs.items()):
        entry_rows.extend(_entry_timing_rows(market, snaps, variant_id))
        for cost in (v70.COSTS[0], v70.COSTS[1], v70.COSTS[2]):
            base: dict[str, object] | None = None
            for policy in POLICIES:
                result = _simulate(market, snaps, weekly, policy, cost, initial_capital)
                row = {k: v for k, v in result.items() if k not in {"events", "ledger", "missing"}}
                row["variant_id"] = variant_id
                if policy.policy_id == "C3_BASE":
                    base = row
                if base is not None:
                    row["incremental_nav_vs_c3_vnd"] = _f(row["ending_nav_vnd"]) - _f(base["ending_nav_vnd"])
                    row["total_return_uplift_vs_c3"] = _f(row["total_return"]) - _f(base["total_return"])
                    row["cagr_uplift_vs_c3"] = _f(row.get("cagr")) - _f(base.get("cagr"))
                    row["mdd_improvement_vs_c3"] = _f(row.get("max_drawdown")) - _f(base.get("max_drawdown"))
                summary_rows.append(row)
                for event in result["events"]:
                    event_rows.append({"variant_id": variant_id, "cost_scenario": cost.name, **event})
    entry_summary = [
        _entry_summary(entry_rows, variant, scope)
        for variant in sorted(inputs)
        for scope in ("ALL", "PRE2026", "Y2026")
    ]
    primary_variant = "GAP18_CLEAN" if "GAP18_CLEAN" in inputs else sorted(inputs)[0]
    primary = [r for r in summary_rows if r["variant_id"] == primary_variant and r["cost_scenario"] == "BASE_DNSE"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "primary_variant": primary_variant,
        "initial_capital_vnd": float(initial_capital),
        "policy_ids": [p.policy_id for p in POLICIES],
        "primary_base_dnse": primary,
        "entry_timing_primary_pre2026": next((r for r in entry_summary if r["variant_id"] == primary_variant and r["scope"] == "PRE2026"), {}),
        "entry_timing_primary_2026_shadow": next((r for r in entry_summary if r["variant_id"] == primary_variant and r["scope"] == "Y2026"), {}),
        "historical_threshold_search_reopened": False,
        "historical_model_search_reopened": False,
        "new_leader_research_reopened": False,
        "year_2026_used_to_select": False,
        "promotion_authorized": False,
        "live_orders_allowed": False,
        "interpretation": "POST_SELECTION_CAPITAL_DISCIPLINE_DIAGNOSTIC",
    }
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    _csv(out / "v83_portfolio_summary.csv", summary_rows)
    _csv(out / "v83_discipline_events.csv", event_rows)
    _csv(out / "v83_entry_timing_events.csv", entry_rows)
    _csv(out / "v83_entry_timing_summary.csv", entry_summary)
    (out / "v83_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--initial-capital", type=float, default=INITIAL_CAPITAL_VND)
    args = parser.parse_args(argv)
    try:
        report = analyze(v68_output=args.v68_output, v70_output=args.v70_output, store=args.store, output_dir=args.output_dir, initial_capital=args.initial_capital)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
