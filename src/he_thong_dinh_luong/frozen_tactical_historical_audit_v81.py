"""V81 descriptive historical audit of the frozen V80 tactical policies.

This module deliberately does not search or tune thresholds.  It replays the
already-selected V80/V79 policies over the existing V68 causal weekly states and
V70 execution primitives to measure event frequency, replacement regret,
horizon behavior, regime dependence, concentration, costs, settlement and
capital sensitivity.  Results are post-selection diagnostics only.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import tactical_capital_policy_v79 as v79
from . import weekly_overlay_backtest_v72 as v72

SCHEMA_VERSION = "frozen_tactical_historical_audit_v81"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
INITIAL_CAPITAL = 1_000_000_000.0
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)
FROZEN_POLICY_IDS = (
    "NO_OVERLAY",
    "L15_SWAP25_WORST",
    "L15_SWAP50_WORST",
    "L15_CASH_ADD25_SLOT",
)
HORIZONS = (5, 10, 20)
L15_CONTRACT = (
    "canonical_rank>10 AND preview_rank<=5 AND prior_preview_rank<=10 AND "
    "relative_5>=0.02 AND volume_ratio_5_20>=1"
)


def _f(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


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
            key = str(key)
            if key not in seen:
                seen.add(key)
                fields.append(key)
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
            key = str(key)
            if key not in seen:
                seen.add(key)
                fields.append(key)
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _quantile(values: Sequence[float], q: float) -> float | None:
    values = sorted(float(x) for x in values)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return values[lo]
    w = pos - lo
    return values[lo] * (1.0 - w) + values[hi] * w


def _scope(day: date) -> str:
    return "PRE2026" if day <= PRIMARY_SELECTION_END else ("Y2026" if day.year == 2026 else "POST2026")


def _market_regime(market: v70.Market, evaluation_day: date) -> tuple[str, float | None]:
    pos = bisect.bisect_right(market.cal, evaluation_day) - 1
    if pos < 60:
        return "INSUFFICIENT_60D", None
    start = market.cal[pos - 60]
    now = market.cal[pos]
    if start not in market.ic or now not in market.ic or market.ic[start] <= 0:
        return "INSUFFICIENT_60D", None
    ret = market.ic[now] / market.ic[start] - 1.0
    if ret >= 0.05:
        return "BULL_60D", ret
    if ret <= -0.05:
        return "BEAR_60D", ret
    return "SIDEWAYS_60D", ret


def _next_monthly_boundary(market: v70.Market, snaps: Sequence[v70.Snap], canonical_day: date) -> date | None:
    ordered = sorted(snaps, key=lambda snap: snap.day)
    for index, snap in enumerate(ordered):
        if snap.day != canonical_day:
            continue
        if index + 1 >= len(ordered):
            return None
        return v70._next(market.cal, ordered[index + 1].day)
    return None


def _horizon_day(market: v70.Market, trade_day: date, horizon: int) -> date | None:
    pos = v70._pos(market.cal, trade_day)
    if pos is None or pos + horizon >= len(market.cal):
        return None
    return market.cal[pos + horizon]


def _open_to_close(market: v70.Market, symbol: str, trade_day: date, end_day: date) -> float | None:
    op = market.so.get((symbol, trade_day)); cl = market.sc.get((symbol, end_day))
    if op is None or cl is None or op <= 0 or cl <= 0:
        return None
    return float(cl) / float(op) - 1.0


def _open_to_open(market: v70.Market, symbol: str, trade_day: date, end_day: date) -> float | None:
    op = market.so.get((symbol, trade_day)); end = market.so.get((symbol, end_day))
    if op is None or end is None or op <= 0 or end <= 0:
        return None
    return float(end) / float(op) - 1.0


def _index_open_to_close(market: v70.Market, trade_day: date, end_day: date) -> float | None:
    op = market.io.get(trade_day); cl = market.ic.get(end_day)
    if op is None or cl is None or op <= 0 or cl <= 0:
        return None
    return float(cl) / float(op) - 1.0


def _index_open_to_open(market: v70.Market, trade_day: date, end_day: date) -> float | None:
    op = market.io.get(trade_day); end = market.io.get(end_day)
    if op is None or end is None or op <= 0 or end <= 0:
        return None
    return float(end) / float(op) - 1.0


def build_signal_event_ledger(
    market: v70.Market,
    snaps: Sequence[v70.Snap],
    weekly: Sequence[v72.WeeklySignal],
    variant_id: str,
) -> list[dict[str, object]]:
    """Describe frozen exact-L15 observations without changing the trigger."""
    snap_by_day = {snap.day: snap for snap in snaps}
    seen_leaders: dict[date, set[str]] = defaultdict(set)
    rows: list[dict[str, object]] = []
    for signal in sorted(weekly, key=lambda item: item.evaluation_day):
        candidates = [dict(row) for row in signal.rows.values() if v79._l15(row)]
        if not candidates:
            continue
        candidates.sort(key=lambda row: (_i(row.get("preview_rank")), -_f(row.get("preview_score"), -1e99), str(row.get("symbol"))))
        snap = snap_by_day.get(signal.canonical_day)
        if snap is None:
            continue
        available = [row for row in candidates if str(row.get("symbol")) not in seen_leaders[signal.canonical_day]]
        selected = available[0] if available else None
        trade_day = v70._next(market.cal, signal.evaluation_day)
        boundary = _next_monthly_boundary(market, snaps, signal.canonical_day)
        collision = bool(trade_day is not None and boundary is not None and trade_day >= boundary)
        actionable = selected is not None and trade_day is not None and not collision
        if actionable:
            seen_leaders[signal.canonical_day].add(str(selected["symbol"]))
        leader = selected if selected is not None else candidates[0]
        regime, trend60 = _market_regime(market, signal.evaluation_day)
        rows.append({
            "variant_id": variant_id,
            "signal_day": signal.evaluation_day.isoformat(),
            "canonical_day": signal.canonical_day.isoformat(),
            "scope": _scope(signal.evaluation_day),
            "year": signal.evaluation_day.year,
            "month": signal.evaluation_day.strftime("%Y-%m"),
            "iso_week": f"{signal.evaluation_day.isocalendar().year}-W{signal.evaluation_day.isocalendar().week:02d}",
            "raw_exact_l15": True,
            "exact_candidate_count": len(candidates),
            "selected_actionable_event": actionable,
            "selected_leader": str(leader.get("symbol")),
            "selected_leader_preview_rank": leader.get("preview_rank"),
            "selected_leader_prior_preview_rank": leader.get("prior_preview_rank"),
            "selected_leader_relative_5": leader.get("relative_5"),
            "selected_leader_volume_ratio_5_20": leader.get("volume_ratio_5_20"),
            "selected_leader_eligible_now": leader.get("eligible_now"),
            "trade_day": trade_day.isoformat() if trade_day else None,
            "monthly_boundary_trade_day": boundary.isoformat() if boundary else None,
            "monthly_collision_suppressed": collision,
            "risk_on": snap.risk_on,
            "causal_regime_60d": regime,
            "index_trailing_60_session_return": trend60,
            "threshold_search_reopened": False,
        })
    return rows


def normalize_action_pair(action: Mapping[str, object]) -> tuple[str, str]:
    kind = str(action.get("action") or "")
    symbol = str(action.get("symbol") or "")
    paired = str(action.get("paired_symbol") or "")
    if kind == "SWAP_WORST_TO_LEADER":
        return paired, symbol
    if kind == "L15_SWAP_WORST":
        return symbol, paired
    if kind == "ADD_L15_FROM_IDLE_CASH":
        return "", symbol
    return "", ""


def build_action_horizons(
    market: v70.Market,
    snaps_by_variant: Mapping[str, Sequence[v70.Snap]],
    weekly_by_variant: Mapping[str, Sequence[v72.WeeklySignal]],
    action_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    signal_lookup: dict[tuple[str, date], v72.WeeklySignal] = {}
    for variant, signals in weekly_by_variant.items():
        for signal in signals:
            signal_lookup[(variant, signal.evaluation_day)] = signal
    out: list[dict[str, object]] = []
    for action in action_rows:
        variant = str(action["variant_id"]); policy = str(action["policy_id"])
        signal_day = date.fromisoformat(str(action["signal_day"])); trade_day = date.fromisoformat(str(action["trade_day"]))
        signal = signal_lookup.get((variant, signal_day))
        canonical = signal.canonical_day if signal is not None else None
        boundary = _next_monthly_boundary(market, snaps_by_variant[variant], canonical) if canonical else None
        incumbent, leader = normalize_action_pair(action)
        if not leader:
            continue
        regime, trend60 = _market_regime(market, signal_day)
        base = {
            "variant_id": variant,
            "allocator": action.get("allocator"),
            "policy_id": policy,
            "cost_scenario": action.get("cost_scenario"),
            "signal_day": signal_day.isoformat(),
            "trade_day": trade_day.isoformat(),
            "canonical_day": canonical.isoformat() if canonical else None,
            "scope": _scope(signal_day),
            "action": action.get("action"),
            "leader": leader,
            "incumbent": incumbent or None,
            "risk_on": next((snap.risk_on for snap in snaps_by_variant[variant] if canonical and snap.day == canonical), None),
            "causal_regime_60d": regime,
            "index_trailing_60_session_return": trend60,
        }
        for horizon in HORIZONS:
            end_day = _horizon_day(market, trade_day, horizon)
            censored = bool(end_day is not None and boundary is not None and end_day >= boundary)
            leader_return = incumbent_return = index_return = None
            if end_day is not None and not censored:
                leader_return = _open_to_close(market, leader, trade_day, end_day)
                incumbent_return = _open_to_close(market, incumbent, trade_day, end_day) if incumbent else None
                index_return = _index_open_to_close(market, trade_day, end_day)
            spread = leader_return - incumbent_return if leader_return is not None and incumbent_return is not None else None
            out.append({**base, "horizon": f"H{horizon}", "evaluation_day": end_day.isoformat() if end_day else None,
                "censored_by_monthly_rebalance": censored, "leader_return": leader_return,
                "incumbent_return": incumbent_return, "index_return": index_return,
                "leader_minus_incumbent": spread,
                "replacement_regret": spread < 0 if spread is not None else None,
                "leader_minus_index": leader_return - index_return if leader_return is not None and index_return is not None else None})
        if boundary is not None:
            leader_return = _open_to_open(market, leader, trade_day, boundary)
            incumbent_return = _open_to_open(market, incumbent, trade_day, boundary) if incumbent else None
            index_return = _index_open_to_open(market, trade_day, boundary)
            spread = leader_return - incumbent_return if leader_return is not None and incumbent_return is not None else None
            out.append({**base, "horizon": "MONTHLY_REBALANCE", "evaluation_day": boundary.isoformat(),
                "censored_by_monthly_rebalance": False, "leader_return": leader_return,
                "incumbent_return": incumbent_return, "index_return": index_return,
                "leader_minus_incumbent": spread,
                "replacement_regret": spread < 0 if spread is not None else None,
                "leader_minus_index": leader_return - index_return if leader_return is not None and index_return is not None else None})
    return out


def _group_stats(values: Sequence[float]) -> dict[str, object]:
    values = [float(x) for x in values if math.isfinite(float(x))]
    if not values:
        return {"count": 0, "mean": None, "median": None, "p10": None, "p90": None, "positive_rate": None}
    return {"count": len(values), "mean": fmean(values), "median": median(values),
            "p10": _quantile(values, 0.10), "p90": _quantile(values, 0.90),
            "positive_rate": sum(x > 0 for x in values) / len(values)}


def summarize_signal_frequency(events: Sequence[Mapping[str, object]], snaps_by_variant: Mapping[str, Sequence[v70.Snap]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for variant in sorted(snaps_by_variant):
        variant_events = [row for row in events if str(row["variant_id"]) == variant]
        for scope in ("ALL", "PRE2026", "Y2026"):
            rows = variant_events if scope == "ALL" else [row for row in variant_events if str(row["scope"]) == scope]
            selected = [row for row in rows if _b(row.get("selected_actionable_event"))]
            leaders = Counter(str(row["selected_leader"]) for row in selected)
            months = sorted({str(row["month"]) for row in selected})
            out.append({"variant_id": variant, "scope": scope, "raw_exact_l15_week_count": len(rows),
                "actionable_signal_event_count": len(selected), "active_month_count": len(months),
                "active_iso_week_count": len({str(row["iso_week"]) for row in selected}),
                "unique_leader_count": len(leaders), "top_leader": leaders.most_common(1)[0][0] if leaders else None,
                "top_leader_event_share": leaders.most_common(1)[0][1] / len(selected) if selected else None})
    return out


def summarize_concentration(action_horizons: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    unique_actions: dict[tuple[str, str, str, str, str], Mapping[str, object]] = {}
    for row in action_horizons:
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]), str(row["signal_day"]), str(row["trade_day"]))
        unique_actions.setdefault(key, row)
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in unique_actions.values():
        grouped[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))].append(row)
    out: list[dict[str, object]] = []
    for key, rows in sorted(grouped.items()):
        leaders = Counter(str(row["leader"]) for row in rows); incumbents = Counter(str(row["incumbent"]) for row in rows if row.get("incumbent"))
        n = len(rows)
        leader_hhi = sum((count / n) ** 2 for count in leaders.values()) if n else None
        inc_n = sum(incumbents.values())
        inc_hhi = sum((count / inc_n) ** 2 for count in incumbents.values()) if inc_n else None
        out.append({"variant_id": key[0], "allocator": key[1], "policy_id": key[2], "action_count": n,
            "unique_leader_count": len(leaders), "leader_hhi": leader_hhi,
            "top1_leader_share": leaders.most_common(1)[0][1] / n if n else None,
            "top3_leader_share": sum(c for _, c in leaders.most_common(3)) / n if n else None,
            "unique_incumbent_count": len(incumbents), "incumbent_hhi": inc_hhi,
            "top1_incumbent_share": incumbents.most_common(1)[0][1] / inc_n if inc_n else None,
            "top3_incumbent_share": sum(c for _, c in incumbents.most_common(3)) / inc_n if inc_n else None})
    return out


def summarize_horizons(action_horizons: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in action_horizons:
        groups[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]), str(row["horizon"]), str(row["scope"]))].append(row)
    out: list[dict[str, object]] = []
    for key, rows in sorted(groups.items()):
        valid = [row for row in rows if not _b(row.get("censored_by_monthly_rebalance")) and row.get("leader_return") is not None]
        spreads = [_f(row["leader_minus_incumbent"]) for row in valid if row.get("leader_minus_incumbent") is not None]
        leader_alpha = [_f(row["leader_minus_index"]) for row in valid if row.get("leader_minus_index") is not None]
        spread_stats = _group_stats(spreads); alpha_stats = _group_stats(leader_alpha)
        out.append({"variant_id": key[0], "allocator": key[1], "policy_id": key[2], "horizon": key[3], "scope": key[4],
            "row_count": len(rows), "valid_count": len(valid), "censored_count": len(rows) - len(valid),
            "replacement_spread_mean": spread_stats["mean"], "replacement_spread_median": spread_stats["median"],
            "replacement_spread_p10": spread_stats["p10"], "replacement_spread_p90": spread_stats["p90"],
            "replacement_win_rate": spread_stats["positive_rate"],
            "replacement_regret_rate": (1.0 - float(spread_stats["positive_rate"])) if spread_stats["positive_rate"] is not None else None,
            "leader_minus_index_mean": alpha_stats["mean"], "leader_minus_index_positive_rate": alpha_stats["positive_rate"]})
    return out


def summarize_regime(action_horizons: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in action_horizons:
        if str(row.get("horizon")) not in {"H10", "H20", "MONTHLY_REBALANCE"}:
            continue
        groups[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]), str(row["horizon"]), str(row["causal_regime_60d"]))].append(row)
    out: list[dict[str, object]] = []
    for key, rows in sorted(groups.items()):
        spreads = [_f(row["leader_minus_incumbent"]) for row in rows if row.get("leader_minus_incumbent") is not None and not _b(row.get("censored_by_monthly_rebalance"))]
        alpha = [_f(row["leader_minus_index"]) for row in rows if row.get("leader_minus_index") is not None and not _b(row.get("censored_by_monthly_rebalance"))]
        s = _group_stats(spreads); a = _group_stats(alpha)
        out.append({"variant_id": key[0], "allocator": key[1], "policy_id": key[2], "horizon": key[3],
            "causal_regime_60d": key[4], "valid_replacement_count": s["count"],
            "replacement_spread_mean": s["mean"], "replacement_win_rate": s["positive_rate"],
            "leader_minus_index_mean": a["mean"], "leader_minus_index_positive_rate": a["positive_rate"]})
    return out


def _contribution_share(values: Sequence[float], topn: int, positive: bool) -> float | None:
    vals = [float(x) for x in values if (x > 0 if positive else x < 0)]
    if not vals:
        return None
    mags = sorted((abs(x) for x in vals), reverse=True)
    total = sum(mags)
    return sum(mags[:topn]) / total if total else None


def portfolio_delta_diagnostics(period_rows: Sequence[Mapping[str, object]], action_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in period_rows:
        if str(row.get("cost_scenario")) == "BASE_DNSE" and str(row.get("settlement_mode")) == "IMMEDIATE":
            grouped[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))].append(row)
    action_days: dict[tuple[str, str, str], list[date]] = defaultdict(list)
    for row in action_rows:
        action_days[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))].append(date.fromisoformat(str(row["trade_day"])))
    out: list[dict[str, object]] = []
    scopes = ("ALL", "PRE2026", "Y2026")
    bases = {(v, a): rows for (v, a, p), rows in grouped.items() if p == "NO_OVERLAY"}
    for (variant, allocator, policy), rows in sorted(grouped.items()):
        if policy == "NO_OVERLAY":
            continue
        base_map = {(str(r["period_start_day"]), str(r["period_end_day"])): r for r in bases.get((variant, allocator), [])}
        cand_map = {(str(r["period_start_day"]), str(r["period_end_day"])): r for r in rows}
        for scope in scopes:
            deltas: list[float] = []; cand_comp = base_comp = 1.0; action_periods = 0
            for period in sorted(set(base_map) & set(cand_map)):
                end = date.fromisoformat(period[1])
                if scope == "PRE2026" and end > PRIMARY_SELECTION_END:
                    continue
                if scope == "Y2026" and end.year != 2026:
                    continue
                if scope == "ALL" or scope in {"PRE2026", "Y2026"}:
                    cr = _f(cand_map[period]["strategy_return"]); br = _f(base_map[period]["strategy_return"])
                    deltas.append(cr - br); cand_comp *= 1.0 + cr; base_comp *= 1.0 + br
                    start = date.fromisoformat(period[0])
                    if any(start <= d < end for d in action_days.get((variant, allocator, policy), [])):
                        action_periods += 1
            if not deltas:
                continue
            out.append({"variant_id": variant, "allocator": allocator, "policy_id": policy, "scope": scope,
                "paired_month_count": len(deltas), "action_period_count": action_periods,
                "mean_monthly_delta": fmean(deltas), "median_monthly_delta": median(deltas),
                "positive_month_delta_rate": sum(x > 0 for x in deltas) / len(deltas),
                "compounded_return_delta": (cand_comp - 1.0) - (base_comp - 1.0),
                "top1_positive_delta_share": _contribution_share(deltas, 1, True),
                "top3_positive_delta_share": _contribution_share(deltas, 3, True),
                "top5_positive_delta_share": _contribution_share(deltas, 5, True),
                "top1_negative_delta_share": _contribution_share(deltas, 1, False),
                "top3_negative_delta_share": _contribution_share(deltas, 3, False),
                "best_month_delta": max(deltas), "worst_month_delta": min(deltas)})
    return out


def no_trigger_month_diagnostics(period_rows: Sequence[Mapping[str, object]], signal_events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    active_days: dict[str, list[date]] = defaultdict(list)
    for row in signal_events:
        if _b(row.get("selected_actionable_event")):
            active_days[str(row["variant_id"])].append(date.fromisoformat(str(row["signal_day"])))
    out: list[dict[str, object]] = []
    for row in period_rows:
        if str(row.get("policy_id")) != "NO_OVERLAY" or str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
            continue
        start = date.fromisoformat(str(row["period_start_day"])); end = date.fromisoformat(str(row["period_end_day"])); variant = str(row["variant_id"])
        out.append({"variant_id": variant, "allocator": row["allocator"], "period_start_day": start.isoformat(),
            "period_end_day": end.isoformat(), "scope": _scope(end),
            "exact_l15_event_in_period": any(start <= d < end for d in active_days.get(variant, [])),
            "baseline_return": row["strategy_return"], "benchmark_return": row["benchmark_return"], "baseline_alpha": row["alpha"]})
    return out


def robustness_tables(summaries: Sequence[Mapping[str, object]], capital_rows: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    base: dict[tuple[str, str, str, str, float], Mapping[str, object]] = {}
    for row in summaries:
        if str(row["policy_id"]) == "NO_OVERLAY":
            base[(str(row["variant_id"]), str(row["allocator"]), str(row["cost_scenario"]), str(row["settlement_mode"]), float(row["initial_capital_vnd"]))] = row
    cost_rows: list[dict[str, object]] = []; t2_rows: list[dict[str, object]] = []
    for row in summaries:
        if str(row["policy_id"]) == "NO_OVERLAY":
            continue
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["cost_scenario"]), str(row["settlement_mode"]), float(row["initial_capital_vnd"]))
        b = base.get(key)
        if b is None:
            continue
        payload = {"variant_id": row["variant_id"], "allocator": row["allocator"], "policy_id": row["policy_id"],
            "cost_scenario": row["cost_scenario"], "settlement_mode": row["settlement_mode"],
            "total_return": row["total_return"], "baseline_total_return": b["total_return"],
            "total_return_delta": _f(row["total_return"]) - _f(b["total_return"]),
            "cagr_delta": _f(row.get("cagr")) - _f(b.get("cagr")),
            "mdd_improvement": _f(row.get("max_drawdown_daily")) - _f(b.get("max_drawdown_daily")),
            "action_count": row.get("overlay_action_count"), "modeled_cost_vnd": row.get("modeled_cost_and_slippage_vnd"),
            "max_adv20_participation": row.get("max_adv20_participation")}
        (t2_rows if str(row["settlement_mode"]) == "T2_NO_ADVANCE" else cost_rows).append(payload)
    cap_base: dict[tuple[str, str, float], Mapping[str, object]] = {}
    for row in capital_rows:
        if str(row["policy_id"]) == "NO_OVERLAY":
            cap_base[(str(row["variant_id"]), str(row["allocator"]), float(row["initial_capital_vnd"]))] = row
    cap_out: list[dict[str, object]] = []
    for row in capital_rows:
        if str(row["policy_id"]) == "NO_OVERLAY":
            continue
        b = cap_base.get((str(row["variant_id"]), str(row["allocator"]), float(row["initial_capital_vnd"])))
        if b is None:
            continue
        cap_out.append({"variant_id": row["variant_id"], "allocator": row["allocator"], "policy_id": row["policy_id"],
            "initial_capital_vnd": row["initial_capital_vnd"],
            "total_return_delta": _f(row["total_return"]) - _f(b["total_return"]),
            "cagr_delta": _f(row.get("cagr")) - _f(b.get("cagr")),
            "mdd_improvement": _f(row.get("max_drawdown_daily")) - _f(b.get("max_drawdown_daily")),
            "action_count": row.get("overlay_action_count"), "max_adv20_participation": row.get("max_adv20_participation"),
            "trade_rate_adv20_gt_5pct": row.get("trade_rate_adv20_gt_5pct"), "trade_rate_adv20_gt_10pct": row.get("trade_rate_adv20_gt_10pct")})
    return cost_rows, t2_rows, cap_out


def analyze(*, v68_output: Path, v70_output: Path, store: Path, output_dir: Path, initial_capital: float = INITIAL_CAPITAL) -> dict[str, object]:
    v70_report = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if v70_report.get("status") != "SUCCESS" or v70_report.get("champion_model") != CHAMPION_MODEL or _b(v70_report.get("champion_replaced")):
        raise ValueError("V81_V70_BASELINE_CONTRACT_INVALID")
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V81_V68_VARIANTS_MISSING")
    inputs: dict[str, tuple[list[v70.Snap], list[v72.WeeklySignal]]] = {}; symbols: set[str] = set()
    for variant_dir in sorted(path for path in variants_root.iterdir() if path.is_dir()):
        monthly_path = variant_dir / "v67_c3_monthly_rankings.csv.gz"; weekly_path = variant_dir / "v67_weekly_signal_states.csv.gz"
        if not monthly_path.is_file() or not weekly_path.is_file():
            continue
        snaps = v70.load_snaps(monthly_path); weekly, weekly_symbols = v72.load_weekly_signals(weekly_path)
        inputs[variant_dir.name] = (snaps, weekly); symbols.update(weekly_symbols)
        for snap in snaps:
            symbols.update(snap.symbols)
    if not inputs:
        raise ValueError("V81_NO_VARIANTS")
    market = v70.load_market(store, symbols)
    policies = [v79._POLICY_BY_ID[policy_id] for policy_id in FROZEN_POLICY_IDS]
    summaries: list[dict[str, object]] = []; period_rows: list[dict[str, object]] = []; daily_rows: list[dict[str, object]] = []
    action_rows: list[dict[str, object]] = []; ledger_rows: list[dict[str, object]] = []; capital_rows: list[dict[str, object]] = []
    signal_events: list[dict[str, object]] = []
    snaps_by_variant = {variant: snaps for variant, (snaps, _) in inputs.items()}
    weekly_by_variant = {variant: weekly for variant, (_, weekly) in inputs.items()}
    for variant, (snaps, weekly) in sorted(inputs.items()):
        signal_events.extend(build_signal_event_ledger(market, snaps, weekly, variant))
        for allocator in ("EQUAL", "INVOL60"):
            for policy in policies:
                for cost in v70.COSTS:
                    result = v79.simulate_capital_policy(market=market, monthly_snaps=snaps, weekly_signals=weekly,
                        policy=policy, allocator=allocator, cost=cost, capital=initial_capital, variant_id=variant)
                    summaries.append(result["summary"])
                    if cost.name == "BASE_DNSE":
                        period_rows.extend(result["periods"]); daily_rows.extend(result["daily"])
                        action_rows.extend({**row, "variant_id": variant, "allocator": allocator, "cost_scenario": cost.name} for row in result["actions"])
                        ledger_rows.extend({**row, "variant_id": variant, "allocator": allocator, "policy_id": policy.policy_id, "cost_scenario": cost.name} for row in result["ledger"])
                t2 = v79.simulate_capital_policy(market=market, monthly_snaps=snaps, weekly_signals=weekly,
                    policy=policy, allocator=allocator, cost=v70.COSTS[1], capital=initial_capital, variant_id=variant,
                    settlement="T2_NO_ADVANCE")
                summaries.append(t2["summary"])
                for capital in CAPITALS:
                    cap = v79.simulate_capital_policy(market=market, monthly_snaps=snaps, weekly_signals=weekly,
                        policy=policy, allocator=allocator, cost=v70.COSTS[1], capital=capital, variant_id=variant)
                    capital_rows.append(cap["summary"])
    baseline_audit = v72._baseline_audit(summaries, v70_output)
    action_horizons = build_action_horizons(market, snaps_by_variant, weekly_by_variant, action_rows)
    frequency = summarize_signal_frequency(signal_events, snaps_by_variant)
    horizon_summary = summarize_horizons(action_horizons)
    concentration = summarize_concentration(action_horizons)
    regime = summarize_regime(action_horizons)
    portfolio_delta = portfolio_delta_diagnostics(period_rows, action_rows)
    no_trigger = no_trigger_month_diagnostics(period_rows, signal_events)
    cost_robust, t2_robust, capital_robust = robustness_tables(summaries, capital_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    _csv(output_dir / "v81_signal_events.csv", signal_events)
    _csv(output_dir / "v81_signal_frequency.csv", frequency)
    _csv(output_dir / "v81_action_horizons.csv", action_horizons)
    _csv(output_dir / "v81_horizon_summary.csv", horizon_summary)
    _csv(output_dir / "v81_regime_summary.csv", regime)
    _csv(output_dir / "v81_concentration.csv", concentration)
    _csv(output_dir / "v81_portfolio_delta_diagnostics.csv", portfolio_delta)
    _csv(output_dir / "v81_no_trigger_months.csv", no_trigger)
    _csv(output_dir / "v81_cost_robustness.csv", cost_robust)
    _csv(output_dir / "v81_t2_robustness.csv", t2_robust)
    _csv(output_dir / "v81_capital_robustness.csv", capital_robust)
    _csv(output_dir / "v81_backtest_summary.csv", summaries)
    _gzcsv(output_dir / "v81_trade_ledger_base.csv.gz", ledger_rows)
    _gzcsv(output_dir / "v81_daily_equity_base.csv.gz", daily_rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "frozen_policy_ids": list(FROZEN_POLICY_IDS),
        "exact_l15_contract": L15_CONTRACT,
        "exact_l15_delegated_to_v72_v79": True,
        "historical_threshold_search_reopened": False,
        "historical_model_search_reopened": False,
        "post_selection_descriptive_audit": True,
        "selection_authorized_from_v81": False,
        "promotion_authorized": False,
        "live_orders_allowed": False,
        "year_2026_used_to_tune": False,
        "primary_selection_end_reference": PRIMARY_SELECTION_END.isoformat(),
        "baseline_reconstruction_audit": baseline_audit,
        "variant_count": len(inputs),
        "signal_event_count": len(signal_events),
        "executed_action_count": len(action_rows),
        "action_horizon_row_count": len(action_horizons),
        "robustness": {"allocators": ["EQUAL", "INVOL60"], "costs": [cost.name for cost in v70.COSTS],
            "settlement_sensitivity": "T2_NO_ADVANCE", "capitals_vnd": list(CAPITALS),
            "lot_size": v70.LOT_SIZE, "single_name_cap": v70.SINGLE_NAME_CAP},
        "diagnostic_regime_definition": {"BULL_60D": ">= +5% trailing 60 market sessions",
            "BEAR_60D": "<= -5% trailing 60 market sessions", "SIDEWAYS_60D": "otherwise"},
        "data_gates": {"pit_hose_closed": False, "price_basis_closed": False,
            "corporate_actions_complete": False, "pit_sector_master_closed": False},
        "limitations": [
            "V81 is post-selection descriptive replay, not a new unbiased selection sample.",
            "No threshold/model/policy is changed from the frozen V80/V79 definitions.",
            "2026 may be displayed descriptively but is not used to retune the frozen policies.",
            "PIT HOSE, price basis, corporate actions and PIT sector lineage remain fail-closed.",
            "Causal 60-session regime buckets are diagnostics only and do not alter trading rules.",
        ],
    }
    (output_dir / "v81_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--initial-capital", type=float, default=INITIAL_CAPITAL)
    args = parser.parse_args(argv)
    report = analyze(v68_output=args.v68_output, v70_output=args.v70_output, store=args.store,
                     output_dir=args.output_dir, initial_capital=args.initial_capital)
    print(json.dumps({key: report[key] for key in (
        "status", "variant_count", "signal_event_count", "executed_action_count",
        "historical_threshold_search_reopened", "selection_authorized_from_v81",
        "promotion_authorized", "live_orders_allowed")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
