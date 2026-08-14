"""V69 matched-control robustness audit for frozen C3 weekly cohorts.

Consumes a completed V68 output plus the canonical read-only market store.  It
never changes C3 weights, cohort thresholds, the source store, or live policy.

Corrections versus V68 exploratory statistics:
- leader cohorts are compared with same-week raw emerging leaders (Top5 or
  Top10 according to the frozen cohort scope), not a full-history mean;
- risk cohorts are compared with same-week unsignalled canonical Top10 names;
- overlapping weekly forward horizons are handled with contiguous two-calendar-
  month time blocks;
- null evidence uses a block sign-flip randomisation test, while bootstrap is
  used only for confidence intervals;
- p-values use finite-simulation correction and are never reported as zero;
- symbol concentration, cohort overlap, recent-era behaviour and August shadow
  cohort matches are exported explicitly.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import csv
from datetime import date
import gzip
import json
from pathlib import Path
import random
import sqlite3
from statistics import fmean, median
from typing import Iterable, Mapping, Sequence

from . import _v64_cohort_contract as cohort_contract

SCHEMA_VERSION = "c3_matched_control_v69"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_HORIZON = 10
HISTORICAL_END = date(2026, 7, 31)
RECENT_ERA_START = date(2023, 1, 1)
SIGNFLIP_SAMPLES_DEFAULT = 10000
BOOTSTRAP_SAMPLES_DEFAULT = 5000
RANDOM_SEED = 69012908
TOP10_LEADER_COHORTS = {"L10_BREAKOUT20", "L11_RELATIVE_LEADER", "L14_MULTI_4OF6"}
SHADOW_FOCUS = ("VPI", "TLG", "BAF")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_gzip_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({str(key) for row in rows for key in row}) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            cooked: dict[str, object] = {}
            for field in fields:
                value = row.get(field)
                if isinstance(value, (dict, list, tuple, set)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                cooked[field] = value
            writer.writerow(cooked)


def _parse_day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _float(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _int(row: Mapping[str, object], key: str, default: int = 10**9) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


class OutcomeStore:
    """Read-only return/path lookup using the canonical local OHLCV store."""

    def __init__(self, store: Path):
        uri = store.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as db:
            columns = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
            required = {"asset_type", "symbol", "day", "open", "close"}
            if not required.issubset(columns):
                raise ValueError("V69_BARS_REQUIRED_COLUMNS_MISSING")
            sql = (
                f'SELECT "{columns["asset_type"]}","{columns["symbol"]}","{columns["day"]}",'
                f'"{columns["open"]}","{columns["close"]}" FROM bars ORDER BY "{columns["day"]}","{columns["symbol"]}"'
            )
            index_open: dict[date, float] = {}
            index_close: dict[date, float] = {}
            stock_open: dict[tuple[str, date], float] = {}
            stock_close: dict[tuple[str, date], float] = {}
            for asset_type, symbol_raw, day_raw, open_raw, close_raw in db.execute(sql):
                symbol = str(symbol_raw or "").strip().upper()
                day = _parse_day(day_raw)
                if not symbol or day is None:
                    continue
                try:
                    open_price, close_price = float(open_raw), float(close_raw)
                except (TypeError, ValueError):
                    continue
                if open_price <= 0 or close_price <= 0:
                    continue
                asset = str(asset_type or "").strip().upper()
                if asset == "INDEX" and symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
                    index_open[day] = open_price
                    index_close[day] = close_price
                elif asset == "STOCK":
                    stock_open[(symbol, day)] = open_price
                    stock_close[(symbol, day)] = close_price
        self.calendar = tuple(sorted(index_open))
        self.index_open = index_open
        self.index_close = index_close
        self.stock_open = stock_open
        self.stock_close = stock_close
        self.calendar_index = {day: idx for idx, day in enumerate(self.calendar)}

    def outcome(self, symbol: str, signal_day: date, horizon: int = PRIMARY_HORIZON) -> dict[str, float] | None:
        pos = self.calendar_index.get(signal_day)
        if pos is None:
            return None
        entry_pos = pos + 1
        exit_pos = entry_pos + horizon
        if exit_pos >= len(self.calendar):
            return None
        entry_day, exit_day = self.calendar[entry_pos], self.calendar[exit_pos]
        stock_entry = self.stock_open.get((symbol, entry_day))
        stock_exit = self.stock_open.get((symbol, exit_day))
        index_entry = self.index_open.get(entry_day)
        index_exit = self.index_open.get(exit_day)
        if not all(value is not None and value > 0 for value in (stock_entry, stock_exit, index_entry, index_exit)):
            return None
        forward = float(stock_exit) / float(stock_entry) - 1.0
        benchmark = float(index_exit) / float(index_entry) - 1.0
        path: list[float] = []
        for idx in range(entry_pos, min(entry_pos + 10, len(self.calendar))):
            close = self.stock_close.get((symbol, self.calendar[idx]))
            if close is not None and close > 0:
                path.append(float(close) / float(stock_entry) - 1.0)
        return {
            "forward_return": forward,
            "forward_excess_return": forward - benchmark,
            "mae_10": min(path) if path else 0.0,
            "mfe_10": max(path) if path else 0.0,
        }


def _time_block_id(day_text: str) -> str:
    day = date.fromisoformat(day_text[:10])
    pair = (day.month - 1) // 2
    return f"{day.year:04d}-B{pair + 1}"


def _block_means(weekly_values: Mapping[str, float]) -> list[float]:
    blocks: dict[str, list[float]] = defaultdict(list)
    for day_text, value in sorted(weekly_values.items()):
        blocks[_time_block_id(day_text)].append(float(value))
    return [fmean(values) for _, values in sorted(blocks.items()) if values]


def _signflip_and_bootstrap(
    weekly_values: Mapping[str, float], *, signflip_samples: int, bootstrap_samples: int, seed: int
) -> dict[str, float | int]:
    blocks = _block_means(weekly_values)
    if not blocks:
        return {
            "block_count": 0,
            "observed_block_mean": 0.0,
            "block_median": 0.0,
            "signflip_two_sided_p": 1.0,
            "bootstrap_ci025": 0.0,
            "bootstrap_ci975": 0.0,
            "positive_block_rate": 0.0,
        }
    observed = fmean(blocks)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(max(1, signflip_samples)):
        simulated = fmean(value if rng.random() >= 0.5 else -value for value in blocks)
        if abs(simulated) >= abs(observed) - 1e-15:
            extreme += 1
    p_value = (extreme + 1.0) / (max(1, signflip_samples) + 1.0)
    boots: list[float] = []
    n = len(blocks)
    for _ in range(max(1, bootstrap_samples)):
        boots.append(fmean(blocks[rng.randrange(n)] for _ in range(n)))
    boots.sort()
    lo = boots[int(0.025 * (len(boots) - 1))]
    hi = boots[int(0.975 * (len(boots) - 1))]
    return {
        "block_count": len(blocks),
        "observed_block_mean": observed,
        "block_median": median(blocks),
        "signflip_two_sided_p": p_value,
        "bootstrap_ci025": lo,
        "bootstrap_ci975": hi,
        "positive_block_rate": sum(value > 0 for value in blocks) / len(blocks),
    }


def _bh(rows: Sequence[dict[str, object]], p_field: str, q_field: str) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: float(item[1][p_field]))
    m = len(ordered)
    running = 1.0
    q_by_index: dict[int, float] = {}
    for position in range(m - 1, -1, -1):
        original_index, row = ordered[position]
        rank = position + 1
        running = min(running, float(row[p_field]) * m / rank)
        q_by_index[original_index] = min(1.0, running)
    for index, row in enumerate(rows):
        row[q_field] = q_by_index.get(index, 1.0)


def _scope_for_leader(cohort_id: str) -> int:
    return 10 if cohort_id in TOP10_LEADER_COHORTS else 5


def _state_key(row: Mapping[str, object]) -> tuple[str, str]:
    return str(row.get("evaluation_day") or ""), str(row.get("symbol") or "").upper()


def _historical_states(rows: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    return [
        row for row in rows
        if row.get("phase") == "HISTORICAL_SELECTION"
        and (_parse_day(row.get("evaluation_day")) or date.max) <= HISTORICAL_END
    ]


def _raw_leader_weekly(
    states: Sequence[Mapping[str, str]], outcomes: OutcomeStore, *, scope: int
) -> dict[str, list[dict[str, float]]]:
    by_week: dict[str, list[dict[str, float]]] = defaultdict(list)
    for row in _historical_states(states):
        if _int(row, "canonical_rank") <= 10 or _int(row, "preview_rank") > scope:
            continue
        day = _parse_day(row.get("evaluation_day"))
        symbol = str(row.get("symbol") or "").upper()
        if day is None or not symbol:
            continue
        outcome = outcomes.outcome(symbol, day)
        if outcome is not None:
            by_week[day.isoformat()].append(outcome)
    return by_week


def _leader_audit(
    events: Sequence[Mapping[str, str]], states: Sequence[Mapping[str, str]], outcomes: OutcomeStore,
    *, variant_id: str, signflip_samples: int, bootstrap_samples: int, seed: int
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    event_rows = [
        row for row in events
        if row.get("phase") == "HISTORICAL_SELECTION" and _int(row, "horizon", 0) == PRIMARY_HORIZON and row.get("kind") == "LEADER"
    ]
    raw_by_scope = {scope: _raw_leader_weekly(states, outcomes, scope=scope) for scope in (5, 10)}
    output: list[dict[str, object]] = []
    concentration: list[dict[str, object]] = []
    for index, spec in enumerate(cohort_contract.LEADER_COHORTS):
        cohort_rows = [row for row in event_rows if row.get("cohort_id") == spec.cohort_id]
        if not cohort_rows:
            continue
        scope = _scope_for_leader(spec.cohort_id)
        by_week: dict[str, list[float]] = defaultdict(list)
        symbols = Counter()
        recent_values: list[float] = []
        for row in cohort_rows:
            day = str(row["evaluation_day"])
            by_week[day].append(_float(row, "forward_excess_return"))
            symbols[str(row.get("symbol") or "").upper()] += 1
            parsed = _parse_day(day)
            if parsed is not None and parsed >= RECENT_ERA_START:
                recent_values.append(_float(row, "forward_excess_return"))
        matched: dict[str, float] = {}
        comparator_weeks = raw_by_scope[scope]
        for day, values in by_week.items():
            controls = comparator_weeks.get(day, [])
            if not controls:
                continue
            matched[day] = fmean(values) - fmean(float(control["forward_excess_return"]) for control in controls)
        stats = _signflip_and_bootstrap(
            matched,
            signflip_samples=signflip_samples,
            bootstrap_samples=bootstrap_samples,
            seed=seed + index,
        )
        total = sum(symbols.values())
        top_counts = symbols.most_common()
        hhi = sum((count / total) ** 2 for _, count in top_counts) if total else 0.0
        output.append({
            "variant_id": variant_id,
            "cohort_id": spec.cohort_id,
            "family": spec.family,
            "comparator": f"SAME_WEEK_RAW_EMERGING_TOP{scope}",
            "event_count": len(cohort_rows),
            "unique_week_count": len(by_week),
            "matched_week_count": len(matched),
            "unique_symbol_count": len(symbols),
            "cohort_mean_forward_excess": fmean(_float(row, "forward_excess_return") for row in cohort_rows),
            "cohort_median_forward_excess": median(_float(row, "forward_excess_return") for row in cohort_rows),
            "matched_week_delta_mean": fmean(matched.values()) if matched else 0.0,
            "matched_week_delta_median": median(matched.values()) if matched else 0.0,
            "matched_week_positive_rate": sum(value > 0 for value in matched.values()) / len(matched) if matched else 0.0,
            "recent_2023_2026_mean_forward_excess": fmean(recent_values) if recent_values else None,
            "top1_symbol_share": top_counts[0][1] / total if total else 0.0,
            "top5_symbol_share": sum(count for _, count in top_counts[:5]) / total if total else 0.0,
            "symbol_hhi": hhi,
            **stats,
        })
        for rank, (symbol, count) in enumerate(top_counts[:10], start=1):
            concentration.append({
                "variant_id": variant_id,
                "kind": "LEADER",
                "cohort_id": spec.cohort_id,
                "rank": rank,
                "symbol": symbol,
                "event_count": count,
                "event_share": count / total if total else 0.0,
            })
    _bh(output, "signflip_two_sided_p", "bh_fdr_q")
    return output, concentration


def _risk_audit(
    events: Sequence[Mapping[str, str]], states: Sequence[Mapping[str, str]], outcomes: OutcomeStore,
    *, variant_id: str, signflip_samples: int, bootstrap_samples: int, seed: int
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    event_rows = [
        row for row in events
        if row.get("phase") == "HISTORICAL_SELECTION" and _int(row, "horizon", 0) == PRIMARY_HORIZON and row.get("kind") == "RISK"
    ]
    state_by_week: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in _historical_states(states):
        if _int(row, "canonical_rank") <= 10:
            state_by_week[str(row["evaluation_day"])].append(row)
    output: list[dict[str, object]] = []
    concentration: list[dict[str, object]] = []
    for index, spec in enumerate(cohort_contract.RISK_COHORTS):
        cohort_rows = [row for row in event_rows if row.get("cohort_id") == spec.cohort_id]
        if not cohort_rows:
            continue
        trigger_keys = {_state_key(row) for row in cohort_rows}
        signalled_by_week: dict[str, list[Mapping[str, str]]] = defaultdict(list)
        for row in cohort_rows:
            signalled_by_week[str(row["evaluation_day"])].append(row)
        matched_return: dict[str, float] = {}
        matched_mae: dict[str, float] = {}
        rebound_rates: list[float] = []
        symbols = Counter(str(row.get("symbol") or "").upper() for row in cohort_rows)
        recent_signal_returns: list[float] = []
        for day_text, signal_rows in signalled_by_week.items():
            day = _parse_day(day_text)
            if day is None:
                continue
            controls: list[dict[str, float]] = []
            for state in state_by_week.get(day_text, []):
                key = _state_key(state)
                if key in trigger_keys:
                    continue
                outcome = outcomes.outcome(str(state.get("symbol") or "").upper(), day)
                if outcome is not None:
                    controls.append(outcome)
            if not controls:
                continue
            signal_return = fmean(_float(row, "forward_return") for row in signal_rows)
            control_return = fmean(control["forward_return"] for control in controls)
            signal_damage = fmean(-_float(row, "mae_10") for row in signal_rows)
            control_damage = fmean(-control["mae_10"] for control in controls)
            matched_return[day_text] = control_return - signal_return
            matched_mae[day_text] = signal_damage - control_damage
            rebound_rates.extend(1.0 if _float(row, "mfe_10") >= 0.05 else 0.0 for row in signal_rows)
            if day >= RECENT_ERA_START:
                recent_signal_returns.extend(_float(row, "forward_return") for row in signal_rows)
        return_stats = _signflip_and_bootstrap(
            matched_return,
            signflip_samples=signflip_samples,
            bootstrap_samples=bootstrap_samples,
            seed=seed + index,
        )
        mae_stats = _signflip_and_bootstrap(
            matched_mae,
            signflip_samples=signflip_samples,
            bootstrap_samples=bootstrap_samples,
            seed=seed + 1000 + index,
        )
        total = sum(symbols.values())
        top_counts = symbols.most_common()
        output.append({
            "variant_id": variant_id,
            "cohort_id": spec.cohort_id,
            "family": spec.family,
            "comparator": "SAME_WEEK_UNSIGNALLED_CANONICAL_TOP10",
            "event_count": len(cohort_rows),
            "unique_week_count": len(signalled_by_week),
            "matched_week_count": len(matched_return),
            "unique_symbol_count": len(symbols),
            "signal_mean_forward_return": fmean(_float(row, "forward_return") for row in cohort_rows),
            "signal_median_forward_return": median(_float(row, "forward_return") for row in cohort_rows),
            "signal_mean_mae10": fmean(_float(row, "mae_10") for row in cohort_rows),
            "signal_loss5_rate": sum(_float(row, "forward_return") <= -0.05 for row in cohort_rows) / len(cohort_rows),
            "signal_mae8_rate": sum(_float(row, "mae_10") <= -0.08 for row in cohort_rows) / len(cohort_rows),
            "signal_rebound5_rate": fmean(rebound_rates) if rebound_rates else 0.0,
            "recent_2023_2026_signal_mean_forward_return": fmean(recent_signal_returns) if recent_signal_returns else None,
            "matched_control_minus_signal_return_mean": fmean(matched_return.values()) if matched_return else 0.0,
            "matched_signal_minus_control_damage_mean": fmean(matched_mae.values()) if matched_mae else 0.0,
            "return_block_count": return_stats["block_count"],
            "return_signflip_p": return_stats["signflip_two_sided_p"],
            "return_ci025": return_stats["bootstrap_ci025"],
            "return_ci975": return_stats["bootstrap_ci975"],
            "mae_block_count": mae_stats["block_count"],
            "mae_signflip_p": mae_stats["signflip_two_sided_p"],
            "mae_ci025": mae_stats["bootstrap_ci025"],
            "mae_ci975": mae_stats["bootstrap_ci975"],
            "top1_symbol_share": top_counts[0][1] / total if total else 0.0,
            "top5_symbol_share": sum(count for _, count in top_counts[:5]) / total if total else 0.0,
            "symbol_hhi": sum((count / total) ** 2 for _, count in top_counts) if total else 0.0,
        })
        for rank, (symbol, count) in enumerate(top_counts[:10], start=1):
            concentration.append({
                "variant_id": variant_id,
                "kind": "RISK",
                "cohort_id": spec.cohort_id,
                "rank": rank,
                "symbol": symbol,
                "event_count": count,
                "event_share": count / total if total else 0.0,
            })
    _bh(output, "return_signflip_p", "return_bh_fdr_q")
    _bh(output, "mae_signflip_p", "mae_bh_fdr_q")
    return output, concentration


def _overlap(events: Sequence[Mapping[str, str]], variant_id: str) -> list[dict[str, object]]:
    by_kind: dict[str, dict[str, set[tuple[str, str]]]] = {"RISK": {}, "LEADER": {}}
    for row in events:
        if row.get("phase") != "HISTORICAL_SELECTION" or _int(row, "horizon", 0) != PRIMARY_HORIZON:
            continue
        kind = str(row.get("kind") or "")
        cohort = str(row.get("cohort_id") or "")
        if kind not in by_kind or not cohort:
            continue
        by_kind[kind].setdefault(cohort, set()).add(_state_key(row))
    output: list[dict[str, object]] = []
    for kind, mapping in by_kind.items():
        cohorts = sorted(mapping)
        for i, left in enumerate(cohorts):
            for right in cohorts[i + 1:]:
                a, b = mapping[left], mapping[right]
                union = a | b
                output.append({
                    "variant_id": variant_id,
                    "kind": kind,
                    "left_cohort": left,
                    "right_cohort": right,
                    "left_count": len(a),
                    "right_count": len(b),
                    "intersection_count": len(a & b),
                    "jaccard": len(a & b) / len(union) if union else 0.0,
                })
    return output


def _risk_on_by_canonical_day(rankings: Sequence[Mapping[str, str]]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for row in rankings:
        day = str(row.get("signal_day") or "")
        text = str(row.get("risk_on") or "").strip().lower()
        if day:
            result[day] = text in {"true", "1", "yes"}
    return result


def _cohort_feature(row: Mapping[str, str], risk_on: bool) -> dict[str, object]:
    return {
        "canonical_rank": _int(row, "canonical_rank"),
        "preview_rank": _int(row, "preview_rank"),
        "prior_preview_rank": _int(row, "prior_preview_rank"),
        "rank_delta": _int(row, "rank_delta", 0),
        "score_delta": _float(row, "score_delta"),
        "distance_ma20": _float(row, "distance_ma20"),
        "distance_ma50": _float(row, "distance_ma50"),
        "return_5": _float(row, "return_5"),
        "return_10": _float(row, "return_10"),
        "return_20": _float(row, "return_20"),
        "relative_5": _float(row, "relative_5"),
        "relative_10": _float(row, "relative_10"),
        "relative_20": _float(row, "relative_20"),
        "drawdown_20": _float(row, "drawdown_20"),
        "drawdown_60": _float(row, "drawdown_60"),
        "volume_ratio_5_20": _float(row, "volume_ratio_5_20"),
        "realized_vol_ratio_20_60": _float(row, "realized_vol_ratio_20_60"),
        "breakout_20_gap": _float(row, "breakout_20_gap"),
        "breakdown_20_low_gap": _float(row, "breakdown_20_low_gap"),
        "risk_on": risk_on,
    }


def _shadow_matches(states: Sequence[Mapping[str, str]], rankings: Sequence[Mapping[str, str]], variant_id: str) -> list[dict[str, object]]:
    risk_on = _risk_on_by_canonical_day(rankings)
    by_symbol_day = {(str(row.get("symbol") or "").upper(), str(row.get("evaluation_day") or "")): row for row in states}
    output: list[dict[str, object]] = []
    for symbol in SHADOW_FOCUS:
        days = sorted(day for (sym, day) in by_symbol_day if sym == symbol and day > HISTORICAL_END.isoformat())
        for day in days:
            row = by_symbol_day[(symbol, day)]
            previous_days = [candidate for candidate in days if candidate < day]
            prior = by_symbol_day.get((symbol, previous_days[-1])) if previous_days else None
            canonical_day = str(row.get("canonical_day") or "")
            current_feature = _cohort_feature(row, risk_on.get(canonical_day, False))
            prior_feature = _cohort_feature(prior, risk_on.get(str(prior.get("canonical_day") or ""), False)) if prior is not None else None
            matches = [spec.cohort_id for spec in cohort_contract.ALL_COHORTS if cohort_contract.cohort_matches(spec.cohort_id, current_feature, prior_feature)]
            output.append({
                "variant_id": variant_id,
                "evaluation_day": day,
                "symbol": symbol,
                "canonical_day": canonical_day,
                "canonical_rank": _int(row, "canonical_rank"),
                "preview_rank": _int(row, "preview_rank"),
                "prior_preview_rank": _int(row, "prior_preview_rank"),
                "eligible_now": row.get("eligible_now"),
                "risk_matches": [item for item in matches if item.startswith("R")],
                "leader_matches": [item for item in matches if item.startswith("L")],
            })
    return output


def analyze(
    *, v68_output: Path, store: Path, output_dir: Path,
    signflip_samples: int = SIGNFLIP_SAMPLES_DEFAULT,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES_DEFAULT,
) -> dict[str, object]:
    report_path = v68_output / "v68_consolidated_report.json"
    if not report_path.is_file():
        raise ValueError("V69_REQUIRES_COMPLETED_V68_OUTPUT")
    v68_report = json.loads(report_path.read_text(encoding="utf-8"))
    if v68_report.get("status") != "SUCCESS":
        raise ValueError("V69_REQUIRES_SUCCESSFUL_V68_OUTPUT")
    outcomes = OutcomeStore(store)
    variants = [str(row.get("variant_id")) for row in v68_report.get("variant_summaries", []) if row.get("status") == "SUCCESS"]
    leader_rows: list[dict[str, object]] = []
    risk_rows: list[dict[str, object]] = []
    concentration_rows: list[dict[str, object]] = []
    overlap_rows: list[dict[str, object]] = []
    shadow_rows: list[dict[str, object]] = []
    for index, variant_id in enumerate(variants):
        variant = v68_output / "variants" / variant_id
        events = _read_gzip_csv(variant / "v67_cohort_events.csv.gz")
        states = _read_gzip_csv(variant / "v67_weekly_signal_states.csv.gz")
        rankings = _read_gzip_csv(variant / "v67_c3_monthly_rankings.csv.gz")
        leaders, leader_conc = _leader_audit(
            events, states, outcomes,
            variant_id=variant_id,
            signflip_samples=signflip_samples,
            bootstrap_samples=bootstrap_samples,
            seed=RANDOM_SEED + index * 10000,
        )
        risks, risk_conc = _risk_audit(
            events, states, outcomes,
            variant_id=variant_id,
            signflip_samples=signflip_samples,
            bootstrap_samples=bootstrap_samples,
            seed=RANDOM_SEED + 500000 + index * 10000,
        )
        leader_rows.extend(leaders)
        risk_rows.extend(risks)
        concentration_rows.extend(leader_conc)
        concentration_rows.extend(risk_conc)
        overlap_rows.extend(_overlap(events, variant_id))
        shadow_rows.extend(_shadow_matches(states, rankings, variant_id))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v69_leader_matched_control.csv", leader_rows)
    _write_csv(output_dir / "v69_risk_matched_control.csv", risk_rows)
    _write_csv(output_dir / "v69_symbol_concentration.csv", concentration_rows)
    _write_csv(output_dir / "v69_cohort_overlap.csv", overlap_rows)
    _write_csv(output_dir / "v69_shadow_focus_matches.csv", shadow_rows)

    # This is an audit table, not a promotion selector.  It intentionally uses
    # fixed descriptive gates and records all candidates that meet them.
    leader_watch = [
        row for row in leader_rows
        if int(row.get("block_count", 0)) >= 12
        and float(row.get("observed_block_mean", 0.0)) > 0.0
        and float(row.get("bh_fdr_q", 1.0)) <= 0.10
        and (row.get("recent_2023_2026_mean_forward_excess") is not None)
        and float(row.get("recent_2023_2026_mean_forward_excess") or 0.0) > 0.0
    ]
    risk_watch = [
        row for row in risk_rows
        if int(row.get("return_block_count", 0)) >= 12
        and float(row.get("matched_control_minus_signal_return_mean", 0.0)) > 0.0
        and float(row.get("return_bh_fdr_q", 1.0)) <= 0.10
        and float(row.get("matched_signal_minus_control_damage_mean", 0.0)) > 0.0
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "cohort_thresholds_changed": False,
        "source_store_mutated": False,
        "primary_horizon": PRIMARY_HORIZON,
        "time_dependence_unit": "CONTIGUOUS_TWO_CALENDAR_MONTH_BLOCKS",
        "signflip_samples": signflip_samples,
        "bootstrap_samples_for_ci_only": bootstrap_samples,
        "p_value_method": "BLOCK_SIGN_FLIP_WITH_PLUS_ONE_FINITE_SIMULATION_CORRECTION",
        "multiple_testing": "BH_FDR_WITHIN_VARIANT_AND_KIND",
        "leader_comparators": {
            "top5_scoped_cohorts": "SAME_WEEK_RAW_EMERGING_TOP5",
            "top10_scoped_cohorts": "SAME_WEEK_RAW_EMERGING_TOP10",
        },
        "risk_comparator": "SAME_WEEK_UNSIGNALLED_CANONICAL_TOP10",
        "variant_count": len(variants),
        "leader_row_count": len(leader_rows),
        "risk_row_count": len(risk_rows),
        "leader_diagnostic_watchlist": leader_watch,
        "risk_diagnostic_watchlist": risk_watch,
        "v68_data_gates": v68_report.get("data_gates", {}),
        "canonical_research_claim_authorized": False,
        "promotion_authorized": False,
        "research_only": True,
        "limitations": [
            "All 36 cohort thresholds were already observed in earlier research; V69 is a robustness audit, not a pristine holdout.",
            "BROAD/SEAM/GAP18 remain diagnostic sensitivity universes until point-in-time HOSE and price-basis lineage are closed.",
            "Matched controls reduce market-state confounding but do not replace a portfolio-level exposure-normalized simulation.",
            "Two-calendar-month blocks are conservative dependence units for overlapping 10-session weekly outcomes, not proof of full independence.",
            "August 2026 remains shadow-only and is excluded from historical inference.",
        ],
    }
    (output_dir / "v69_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES_DEFAULT)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES_DEFAULT)
    args = parser.parse_args(argv)
    report = analyze(
        v68_output=args.v68_output,
        store=args.store,
        output_dir=args.output_dir,
        signflip_samples=max(1000, args.signflip_samples),
        bootstrap_samples=max(1000, args.bootstrap_samples),
    )
    print(json.dumps({
        "schema_version": report["schema_version"],
        "status": report["status"],
        "leader_watch_count": len(report["leader_diagnostic_watchlist"]),
        "risk_watch_count": len(report["risk_diagnostic_watchlist"]),
        "promotion_authorized": report["promotion_authorized"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
