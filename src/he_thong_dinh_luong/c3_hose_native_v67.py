"""V67 C3-native HOSE research.

Rebuilds the frozen C3 champion directly from the workstation HOSE market store,
then studies weekly protection/opportunity cohorts on top of that same C3.
No challenger ML, broker access, order generation, or live-policy mutation.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import dataclass
from datetime import date
import gzip
import json
import math
from pathlib import Path
import sqlite3
from statistics import fmean, median
from typing import Iterable, Mapping, Sequence

from . import _v64_cohort_contract as cohort_contract
from . import weekly_micro_capital_v43 as c3

SCHEMA_VERSION = "c3_hose_native_v67"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
HISTORICAL_END_DEFAULT = date(2026, 7, 31)
ANALYSIS_END_DEFAULT = date(2026, 8, 13)
PRICE_MULTIPLIER_DEFAULT = 1000.0
MIN_ADV20_VND = 5_000_000_000.0
MAX_ZERO_VOLUME_60 = 5
HORIZONS = (5, 10, 20)
SHADOW_FOCUS_SYMBOLS = ("VPI", "TLG", "BAF")

VENUE_COLUMNS = ("exchange", "market", "floor", "venue", "board", "trading_place", "stock_exchange", "exchange_code", "market_code")
SYMBOL_COLUMNS = ("symbol", "ticker", "code", "security_code")
START_COLUMNS = ("effective_from", "start_date", "from_date", "listed_date", "listing_date", "valid_from", "begin_date", "day", "date")
END_COLUMNS = ("effective_to", "end_date", "to_date", "delisted_date", "delisting_date", "valid_to", "finish_date")
HOSE_TOKENS = ("HOSE", "HSX", "HO CHI MINH")


@dataclass(frozen=True)
class VenueSource:
    mode: str
    table: str
    symbol_col: str
    venue_col: str
    start_col: str | None = None
    end_col: str | None = None


@dataclass(frozen=True)
class Market:
    calendar: tuple[date, ...]
    index_open: Mapping[date, float]
    index_close: Mapping[date, float]
    stock_open: Mapping[tuple[str, date], float]
    stock_close: Mapping[tuple[str, date], float]
    stock_volume: Mapping[tuple[str, date], int]
    symbols: tuple[str, ...]
    venue_source: VenueSource


@dataclass(frozen=True)
class FeatureState:
    symbol: str
    evaluation_day: date
    eligible: bool
    low_volatility: float
    relative_strength_120: float
    high_52_week: float
    distance_ma20: float
    distance_ma50: float
    return_5: float
    return_10: float
    return_20: float
    relative_5: float
    relative_10: float
    relative_20: float
    drawdown_20: float
    drawdown_60: float
    volume_ratio_5_20: float
    realized_vol_ratio_20_60: float
    breakout_20_gap: float
    breakdown_20_low_gap: float
    adv20_vnd: float
    zero_volume_60: int


@dataclass(frozen=True)
class C3Snapshot:
    day: date
    ranking: tuple[str, ...]
    scores: Mapping[str, float]
    weights: Mapping[str, float]
    risk_on: bool
    eligible_count: int
    history_months: int


def _quote(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _norm(value: str) -> str:
    return str(value).strip().lower()


def _looks_hose(value: object) -> bool:
    text = str(value or "").strip().upper()
    return any(token in text for token in HOSE_TOKENS)


def inspect_schema(db: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [str(row[0]) for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not str(row[0]).startswith("sqlite_")]
    return {table: [str(row[1]) for row in db.execute(f"PRAGMA table_info({_quote(table)})")] for table in tables}


def _find_col(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    lookup = {_norm(col): col for col in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def resolve_venue_source(db: sqlite3.Connection) -> VenueSource:
    schema = inspect_schema(db)
    if "bars" not in schema:
        raise ValueError("V67_BARS_TABLE_MISSING")
    bars_symbol = _find_col(schema["bars"], SYMBOL_COLUMNS)
    bars_venue = _find_col(schema["bars"], VENUE_COLUMNS)
    if bars_symbol and bars_venue:
        return VenueSource("BAR_LEVEL", "bars", bars_symbol, bars_venue)
    interval: list[VenueSource] = []
    static: list[VenueSource] = []
    for table, cols in schema.items():
        if table == "bars":
            continue
        symbol = _find_col(cols, SYMBOL_COLUMNS)
        venue = _find_col(cols, VENUE_COLUMNS)
        if not symbol or not venue:
            continue
        start = _find_col(cols, START_COLUMNS)
        end = _find_col(cols, END_COLUMNS)
        item = VenueSource("INTERVAL" if start else "STATIC", table, symbol, venue, start, end)
        (interval if start else static).append(item)
    if interval:
        interval.sort(key=lambda item: (item.end_col is None, len(item.table), item.table))
        return interval[0]
    if static:
        raise ValueError("V67_STATIC_EXCHANGE_METADATA_NOT_ACCEPTED")
    raise ValueError("V67_HOSE_EXCHANGE_METADATA_NOT_FOUND")


def _date_or_none(value: object) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _membership_intervals(db: sqlite3.Connection, source: VenueSource) -> dict[str, list[tuple[date | None, date | None, bool]]]:
    if source.mode == "BAR_LEVEL":
        return {}
    cols = [source.symbol_col, source.venue_col]
    if source.start_col:
        cols.append(source.start_col)
    if source.end_col:
        cols.append(source.end_col)
    sql = f"SELECT {','.join(_quote(col) for col in cols)} FROM {_quote(source.table)}"
    result: dict[str, list[tuple[date | None, date | None, bool]]] = {}
    for row in db.execute(sql):
        symbol = str(row[0] or "").strip().upper()
        if not symbol:
            continue
        start = _date_or_none(row[2]) if source.start_col else None
        end_index = 3 if source.start_col else 2
        end = _date_or_none(row[end_index]) if source.end_col else None
        result.setdefault(symbol, []).append((start, end, _looks_hose(row[1])))
    for symbol in result:
        result[symbol].sort(key=lambda item: (item[0] or date.min, item[1] or date.max))
    return result


def _is_hose_at(symbol: str, day: date, source: VenueSource, intervals: Mapping[str, Sequence[tuple[date | None, date | None, bool]]], bar_venue: object | None = None) -> bool:
    if source.mode == "BAR_LEVEL":
        return _looks_hose(bar_venue)
    matches = [is_hose for start, end, is_hose in intervals.get(symbol, ()) if (start is None or start <= day) and (end is None or day <= end)]
    if matches and any(value != matches[0] for value in matches):
        raise ValueError(f"V67_CONFLICTING_EXCHANGE_INTERVAL:{symbol}:{day}")
    return bool(matches and matches[0])


def load_market(path: Path, *, price_multiplier: float) -> Market:
    with sqlite3.connect(Path(path)) as db:
        db.row_factory = sqlite3.Row
        source = resolve_venue_source(db)
        intervals = _membership_intervals(db, source)
        schema = inspect_schema(db)
        cols = schema["bars"]
        by_lower = {_norm(col): col for col in cols}
        required = {"symbol", "day", "open", "close", "volume"}
        if not required.issubset(by_lower):
            raise ValueError("V67_BARS_REQUIRED_COLUMNS_MISSING")
        asset_col = by_lower.get("asset_type")
        select = [by_lower["symbol"], by_lower["day"], by_lower["open"], by_lower["close"], by_lower["volume"]]
        if asset_col:
            select.append(asset_col)
        if source.mode == "BAR_LEVEL":
            select.append(source.venue_col)
        sql = f"SELECT {','.join(_quote(col) for col in select)} FROM bars ORDER BY day,symbol"
        index_open: dict[date, float] = {}
        index_close: dict[date, float] = {}
        stock_open: dict[tuple[str, date], float] = {}
        stock_close: dict[tuple[str, date], float] = {}
        stock_volume: dict[tuple[str, date], int] = {}
        symbols: set[str] = set()
        for row in db.execute(sql):
            symbol = str(row[0] or "").strip().upper()
            day = _date_or_none(row[1])
            if not symbol or day is None:
                continue
            try:
                open_price = float(row[2])
                close_price = float(row[3])
                volume = int(row[4])
            except (TypeError, ValueError):
                continue
            asset = str(row[5] or "").strip().upper() if asset_col else ""
            venue_index = 6 if asset_col and source.mode == "BAR_LEVEL" else 5 if source.mode == "BAR_LEVEL" else None
            bar_venue = row[venue_index] if venue_index is not None else None
            is_index = asset == "INDEX" or symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}
            if is_index and symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
                if open_price > 0 and close_price > 0:
                    index_open[day] = open_price
                    index_close[day] = close_price
                continue
            if asset_col and asset not in {"", "STOCK", "EQUITY"}:
                continue
            if not _is_hose_at(symbol, day, source, intervals, bar_venue):
                continue
            if open_price <= 0 or close_price <= 0 or volume < 0:
                continue
            stock_open[(symbol, day)] = open_price * price_multiplier
            stock_close[(symbol, day)] = close_price * price_multiplier
            stock_volume[(symbol, day)] = volume
            symbols.add(symbol)
    if not index_close or not stock_close:
        raise ValueError("V67_STORE_REQUIRES_HOSE_STOCKS_AND_VNINDEX")
    calendar = tuple(sorted(index_close))
    return Market(calendar, index_open, index_close, stock_open, stock_close, stock_volume, tuple(sorted(symbols)), source)


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = fmean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def _stock_closes(market: Market, symbol: str, days: Sequence[date]) -> list[float] | None:
    result: list[float] = []
    for day in days:
        value = market.stock_close.get((symbol, day))
        if value is None or value <= 0:
            return None
        result.append(float(value))
    return result


def _return(market: Market, symbol: str, calendar: Sequence[date], pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = market.stock_close.get((symbol, calendar[pos]))
    old = market.stock_close.get((symbol, calendar[pos - lag]))
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def _index_return(market: Market, calendar: Sequence[date], pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = market.index_close.get(calendar[pos])
    old = market.index_close.get(calendar[pos - lag])
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def feature_state(*, market: Market, symbol: str, evaluation_day: date, calendar_index: Mapping[date, int]) -> FeatureState | None:
    pos = calendar_index.get(evaluation_day)
    if pos is None or pos < 250:
        return None
    calendar = market.calendar
    days250 = calendar[pos - 249:pos + 1]
    days61 = calendar[pos - 60:pos + 1]
    days60 = calendar[pos - 59:pos + 1]
    days50 = calendar[pos - 49:pos + 1]
    days20 = calendar[pos - 19:pos + 1]
    prior20 = calendar[pos - 20:pos]
    closes250 = _stock_closes(market, symbol, days250)
    closes61 = _stock_closes(market, symbol, days61)
    closes60 = _stock_closes(market, symbol, days60)
    closes50 = _stock_closes(market, symbol, days50)
    closes20 = _stock_closes(market, symbol, days20)
    closes_prior20 = _stock_closes(market, symbol, prior20)
    if not all((closes250, closes61, closes60, closes50, closes20, closes_prior20)):
        return None
    close = closes250[-1]
    returns60 = [closes61[i] / closes61[i - 1] - 1.0 for i in range(1, len(closes61))]
    vol60 = _sample_std(returns60)
    if vol60 <= 0.0:
        return None
    r5 = _return(market, symbol, calendar, pos, 5)
    r10 = _return(market, symbol, calendar, pos, 10)
    r20 = _return(market, symbol, calendar, pos, 20)
    r120 = _return(market, symbol, calendar, pos, 120)
    i5 = _index_return(market, calendar, pos, 5)
    i10 = _index_return(market, calendar, pos, 10)
    i20 = _index_return(market, calendar, pos, 20)
    i120 = _index_return(market, calendar, pos, 120)
    if None in (r5, r10, r20, r120, i5, i10, i20, i120):
        return None
    ma20 = fmean(closes20)
    ma50 = fmean(closes50)
    ma250 = fmean(closes250)
    avg_volume20 = fmean(float(market.stock_volume.get((symbol, day), 0)) for day in days20)
    avg_volume5 = fmean(float(market.stock_volume.get((symbol, day), 0)) for day in calendar[pos - 4:pos + 1])
    adv20 = fmean(float(market.stock_close[(symbol, day)]) * float(market.stock_volume.get((symbol, day), 0)) for day in days20)
    zero60 = sum(1 for day in days60 if market.stock_volume.get((symbol, day), 0) <= 0)
    vol20 = _sample_std(returns60[-19:])
    eligible = close >= ma250 and adv20 >= MIN_ADV20_VND and zero60 <= MAX_ZERO_VOLUME_60
    return FeatureState(
        symbol=symbol,
        evaluation_day=evaluation_day,
        eligible=eligible,
        low_volatility=-vol60,
        relative_strength_120=float(r120) - float(i120),
        high_52_week=close / max(closes250),
        distance_ma20=close / ma20 - 1.0,
        distance_ma50=close / ma50 - 1.0,
        return_5=float(r5),
        return_10=float(r10),
        return_20=float(r20),
        relative_5=float(r5) - float(i5),
        relative_10=float(r10) - float(i10),
        relative_20=float(r20) - float(i20),
        drawdown_20=close / max(closes20) - 1.0,
        drawdown_60=close / max(closes60) - 1.0,
        volume_ratio_5_20=avg_volume5 / avg_volume20 if avg_volume20 > 0 else 0.0,
        realized_vol_ratio_20_60=vol20 / vol60 if vol60 > 0 else 0.0,
        breakout_20_gap=close / max(closes_prior20) - 1.0,
        breakdown_20_low_gap=close / min(closes_prior20) - 1.0,
        adv20_vnd=adv20,
        zero_volume_60=zero60,
    )


def score_states(states: Sequence[FeatureState], weights: Mapping[str, float]) -> tuple[tuple[str, ...], dict[str, float]]:
    eligible = [state for state in states if state.eligible]
    if not eligible:
        return (), {}
    low = c3.average_percentile([state.low_volatility for state in eligible])
    rs = c3.average_percentile([state.relative_strength_120 for state in eligible])
    high = c3.average_percentile([state.high_52_week for state in eligible])
    scored: list[tuple[str, float]] = []
    for idx, state in enumerate(eligible):
        score = float(weights["low_volatility"]) * low[idx] + float(weights["relative_strength_120"]) * rs[idx] + float(weights["high_52_week"]) * high[idx]
        scored.append((state.symbol, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return tuple(symbol for symbol, _ in scored), {symbol: score for symbol, score in scored}


def _forward_outcome(*, market: Market, symbol: str, signal_day: date, calendar_index: Mapping[date, int], horizon: int) -> dict[str, object] | None:
    pos = calendar_index.get(signal_day)
    if pos is None:
        return None
    entry_pos = pos + 1
    exit_pos = entry_pos + horizon
    if exit_pos >= len(market.calendar):
        return None
    entry_day = market.calendar[entry_pos]
    exit_day = market.calendar[exit_pos]
    stock_entry = market.stock_open.get((symbol, entry_day))
    stock_exit = market.stock_open.get((symbol, exit_day))
    index_entry = market.index_open.get(entry_day)
    index_exit = market.index_open.get(exit_day)
    if not all(value is not None and value > 0 for value in (stock_entry, stock_exit, index_entry, index_exit)):
        return None
    stock_return = float(stock_exit) / float(stock_entry) - 1.0
    index_return = float(index_exit) / float(index_entry) - 1.0
    path: list[float] = []
    for idx in range(entry_pos, min(entry_pos + 10, len(market.calendar))):
        close = market.stock_close.get((symbol, market.calendar[idx]))
        if close is not None and close > 0:
            path.append(float(close) / float(stock_entry) - 1.0)
    return {
        "entry_day": entry_day.isoformat(),
        "exit_day": exit_day.isoformat(),
        "forward_return": stock_return,
        "forward_excess_return": stock_return - index_return,
        "mae_10": min(path) if path else 0.0,
        "mfe_10": max(path) if path else 0.0,
    }


def _monthly_days(calendar: Sequence[date], end: date) -> list[date]:
    by_month: dict[tuple[int, int], date] = {}
    for day in calendar:
        if day <= end:
            by_month[(day.year, day.month)] = day
    return [by_month[key] for key in sorted(by_month)]


def _weekly_days(calendar: Sequence[date], end: date) -> list[date]:
    by_week: dict[tuple[int, int], date] = {}
    for day in calendar:
        if day <= end:
            iso = day.isocalendar()
            by_week[(iso.year, iso.week)] = day
    return [by_week[key] for key in sorted(by_week)]


def build_monthly_c3(*, market: Market, analysis_end: date) -> tuple[list[C3Snapshot], list[c3.ResearchRow], list[dict[str, object]], list[dict[str, object]]]:
    calendar_index = {day: idx for idx, day in enumerate(market.calendar)}
    training_rows: list[c3.ResearchRow] = []
    snapshots: list[C3Snapshot] = []
    ranking_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    for signal_day in _monthly_days(market.calendar, analysis_end):
        states = [state for symbol in market.symbols if (state := feature_state(market=market, symbol=symbol, evaluation_day=signal_day, calendar_index=calendar_index)) is not None]
        current = [state for state in states if state.eligible]
        history = [row for row in training_rows if row.signal_day < signal_day and row.label_end < signal_day]
        history_months = len({row.signal_day for row in history})
        if history_months >= 12 and current:
            weights = c3.shrunk_component_weights(history)
            ranking, scores = score_states(current, weights)
            pos = calendar_index[signal_day]
            risk_on = pos >= 249 and market.index_close[signal_day] >= fmean(market.index_close[day] for day in market.calendar[pos - 249:pos + 1])
            snapshot = C3Snapshot(signal_day, ranking, scores, dict(weights), risk_on, len(current), history_months)
            snapshots.append(snapshot)
            for rank, symbol in enumerate(ranking, start=1):
                ranking_rows.append({"signal_day": signal_day.isoformat(), "symbol": symbol, "rank": rank, "score": scores[symbol], "risk_on": str(risk_on).lower(), "eligible_count": len(current)})
            weight_rows.append({"signal_day": signal_day.isoformat(), "history_months": history_months, "weight_low_volatility": weights["low_volatility"], "weight_relative_strength_120": weights["relative_strength_120"], "weight_high_52_week": weights["high_52_week"], "uses_only_completed_past_labels": "true"})
        for state in current:
            outcome = _forward_outcome(market=market, symbol=state.symbol, signal_day=signal_day, calendar_index=calendar_index, horizon=20)
            if outcome is None:
                continue
            training_rows.append(c3.ResearchRow(signal_day=signal_day, label_end=date.fromisoformat(str(outcome["exit_day"])), symbol=state.symbol, relative_return=float(outcome["forward_excess_return"]), volatility_60=abs(state.low_volatility), risk_on=False, components={"low_volatility": state.low_volatility, "relative_strength_120": state.relative_strength_120, "high_52_week": state.high_52_week}))
    return snapshots, training_rows, ranking_rows, weight_rows


def _canonical_snapshot(snapshots: Sequence[C3Snapshot], days: Sequence[date], evaluation_day: date) -> C3Snapshot | None:
    month_start = date(evaluation_day.year, evaluation_day.month, 1)
    idx = bisect.bisect_left(days, month_start) - 1
    return snapshots[idx] if idx >= 0 else None


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round(q * (len(ordered) - 1)))
    return ordered[max(0, min(idx, len(ordered) - 1))]


def monthly_baseline_metrics(*, market: Market, snapshots: Sequence[C3Snapshot], historical_end: date) -> list[dict[str, object]]:
    calendar_index = {day: idx for idx, day in enumerate(market.calendar)}
    rows: list[dict[str, object]] = []
    for snapshot in snapshots:
        if snapshot.day > historical_end:
            continue
        for horizon in HORIZONS:
            outcomes = []
            for symbol in snapshot.ranking[:10]:
                outcome = _forward_outcome(market=market, symbol=symbol, signal_day=snapshot.day, calendar_index=calendar_index, horizon=horizon)
                if outcome is not None:
                    outcomes.append(outcome)
            if not outcomes:
                continue
            excess = [float(row["forward_excess_return"]) for row in outcomes]
            absolute = [float(row["forward_return"]) for row in outcomes]
            rows.append({"signal_day": snapshot.day.isoformat(), "horizon": horizon, "top10_count": len(outcomes), "mean_forward_excess": fmean(excess), "median_forward_excess": median(excess), "excess_hit_rate": sum(value > 0 for value in excess) / len(excess), "mean_forward_return": fmean(absolute)})
    return rows


def _cohort_feature_row(*, state: FeatureState, canonical_rank: int, preview_rank: int, prior_preview_rank: int, preview_score: float | None, prior_preview_score: float | None, risk_on: bool) -> dict[str, object]:
    rank_delta = preview_rank - prior_preview_rank if preview_rank < 10**8 and prior_preview_rank < 10**8 else 0
    score_delta = float(preview_score) - float(prior_preview_score) if preview_score is not None and prior_preview_score is not None else 0.0
    return {
        "canonical_rank": canonical_rank,
        "preview_rank": preview_rank,
        "prior_preview_rank": prior_preview_rank,
        "rank_delta": rank_delta,
        "score_delta": score_delta,
        "distance_ma20": state.distance_ma20,
        "distance_ma50": state.distance_ma50,
        "return_5": state.return_5,
        "return_10": state.return_10,
        "return_20": state.return_20,
        "relative_5": state.relative_5,
        "relative_10": state.relative_10,
        "relative_20": state.relative_20,
        "drawdown_20": state.drawdown_20,
        "drawdown_60": state.drawdown_60,
        "volume_ratio_5_20": state.volume_ratio_5_20,
        "realized_vol_ratio_20_60": state.realized_vol_ratio_20_60,
        "breakout_20_gap": state.breakout_20_gap,
        "breakdown_20_low_gap": state.breakdown_20_low_gap,
        "risk_on": risk_on,
    }


def weekly_c3_cohorts(*, market: Market, snapshots: Sequence[C3Snapshot], historical_end: date, analysis_end: date) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    calendar_index = {day: idx for idx, day in enumerate(market.calendar)}
    snapshot_days = [snapshot.day for snapshot in snapshots]
    prior_rank: dict[str, int] = {}
    prior_score: dict[str, float] = {}
    prior_feature: dict[str, dict[str, object]] = {}
    events: list[dict[str, object]] = []
    signal_states: list[dict[str, object]] = []
    shadow_focus: list[dict[str, object]] = []
    for evaluation_day in _weekly_days(market.calendar, analysis_end):
        canonical = _canonical_snapshot(snapshots, snapshot_days, evaluation_day)
        if canonical is None:
            continue
        states = {state.symbol: state for symbol in market.symbols if (state := feature_state(market=market, symbol=symbol, evaluation_day=evaluation_day, calendar_index=calendar_index)) is not None}
        ranking, scores = score_states(list(states.values()), canonical.weights)
        current_rank = {symbol: rank for rank, symbol in enumerate(ranking, start=1)}
        canonical_rank = {symbol: rank for rank, symbol in enumerate(canonical.ranking, start=1)}
        candidates = set(canonical.ranking[:10]) | set(ranking[:20]) | set(SHADOW_FOCUS_SYMBOLS)
        current_feature: dict[str, dict[str, object]] = {}
        phase = "HISTORICAL_SELECTION" if evaluation_day <= historical_end else "SHADOW_ONLY"
        for symbol in sorted(candidates):
            state = states.get(symbol)
            if state is None:
                continue
            pr = current_rank.get(symbol, 10**9)
            ppr = prior_rank.get(symbol, 10**9)
            row = _cohort_feature_row(state=state, canonical_rank=canonical_rank.get(symbol, 10**9), preview_rank=pr, prior_preview_rank=ppr, preview_score=scores.get(symbol), prior_preview_score=prior_score.get(symbol), risk_on=canonical.risk_on)
            current_feature[symbol] = row
            base = {"phase": phase, "evaluation_day": evaluation_day.isoformat(), "canonical_day": canonical.day.isoformat(), "symbol": symbol, "canonical_rank": row["canonical_rank"], "preview_rank": pr, "prior_preview_rank": ppr, "preview_score": scores.get(symbol), "rank_delta": row["rank_delta"], "score_delta": row["score_delta"], "eligible_now": state.eligible, "distance_ma20": state.distance_ma20, "distance_ma50": state.distance_ma50, "return_5": state.return_5, "return_10": state.return_10, "return_20": state.return_20, "relative_5": state.relative_5, "relative_10": state.relative_10, "relative_20": state.relative_20, "drawdown_20": state.drawdown_20, "drawdown_60": state.drawdown_60, "volume_ratio_5_20": state.volume_ratio_5_20, "realized_vol_ratio_20_60": state.realized_vol_ratio_20_60, "breakout_20_gap": state.breakout_20_gap, "breakdown_20_low_gap": state.breakdown_20_low_gap}
            signal_states.append(base)
            if phase == "SHADOW_ONLY" and symbol in SHADOW_FOCUS_SYMBOLS:
                shadow_focus.append(dict(base))
            for cohort in cohort_contract.ALL_COHORTS:
                if not cohort_contract.cohort_matches(cohort.cohort_id, row, prior_feature.get(symbol)):
                    continue
                for horizon in HORIZONS:
                    outcome = _forward_outcome(market=market, symbol=symbol, signal_day=evaluation_day, calendar_index=calendar_index, horizon=horizon)
                    if outcome is None:
                        continue
                    events.append({"phase": phase, "evaluation_day": evaluation_day.isoformat(), "canonical_day": canonical.day.isoformat(), "cohort_id": cohort.cohort_id, "kind": cohort.kind, "family": cohort.family, "symbol": symbol, "horizon": horizon, "canonical_rank": row["canonical_rank"], "preview_rank": pr, **outcome})
        prior_rank = current_rank
        prior_score = scores
        prior_feature = current_feature
    return signal_states, events, shadow_focus


def aggregate_cohort_metrics(events: Sequence[Mapping[str, object]], historical_end: date) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[Mapping[str, object]]] = {}
    for event in events:
        if date.fromisoformat(str(event["evaluation_day"])) <= historical_end:
            grouped.setdefault((str(event["cohort_id"]), int(event["horizon"])), []).append(event)
    raw_leader: dict[int, float] = {}
    for (cohort_id, horizon), rows in grouped.items():
        if cohort_id == "L01_TOP5_RAW" and rows:
            raw_leader[horizon] = fmean(float(row["forward_excess_return"]) for row in rows)
    output: list[dict[str, object]] = []
    for (cohort_id, horizon), rows in sorted(grouped.items()):
        spec = cohort_contract.COHORT_BY_ID[cohort_id]
        returns = [float(row["forward_return"]) for row in rows]
        excess = [float(row["forward_excess_return"]) for row in rows]
        mae = [float(row["mae_10"]) for row in rows]
        weeks = {str(row["evaluation_day"]) for row in rows}
        symbols = {str(row["symbol"]) for row in rows}
        years: dict[int, list[float]] = {}
        selected_metric = [-value for value in returns] if spec.kind == "RISK" else excess
        for row, value in zip(rows, selected_metric):
            years.setdefault(date.fromisoformat(str(row["evaluation_day"])).year, []).append(value)
        eligible_years = [values for values in years.values() if len(values) >= 5]
        output.append({
            "cohort_id": cohort_id,
            "kind": spec.kind,
            "family": spec.family,
            "horizon": horizon,
            "event_count": len(rows),
            "unique_week_count": len(weeks),
            "unique_symbol_count": len(symbols),
            "mean_forward_return": fmean(returns),
            "median_forward_return": median(returns),
            "mean_forward_excess": fmean(excess),
            "median_forward_excess": median(excess),
            "p10_forward_return": _percentile(returns, 0.10),
            "median_mae_10": median(mae),
            "negative_return_rate": sum(value < 0 for value in returns) / len(returns),
            "excess_hit_rate": sum(value > 0 for value in excess) / len(excess),
            "year_positive_rate_for_objective": sum(median(values) > 0 for values in eligible_years) / len(eligible_years) if eligible_years else 0.0,
            "leader_incremental_mean_excess_vs_raw_top5": fmean(excess) - raw_leader.get(horizon, 0.0) if spec.kind == "LEADER" else None,
        })
    return output


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_gzip_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["empty"]
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_study(*, store: Path, output_dir: Path, historical_end: date = HISTORICAL_END_DEFAULT, analysis_end: date = ANALYSIS_END_DEFAULT, price_multiplier: float = PRICE_MULTIPLIER_DEFAULT) -> dict[str, object]:
    market = load_market(store, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, market.calendar[-1])
    snapshots, training_rows, rankings, weights = build_monthly_c3(market=market, analysis_end=effective_end)
    baseline = monthly_baseline_metrics(market=market, snapshots=snapshots, historical_end=historical_end)
    states, events, shadow_focus = weekly_c3_cohorts(market=market, snapshots=snapshots, historical_end=historical_end, analysis_end=effective_end)
    metrics = aggregate_cohort_metrics(events, historical_end)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v67_c3_weight_history.csv", weights)
    _write_gzip_csv(output_dir / "v67_c3_monthly_rankings.csv.gz", rankings)
    _write_csv(output_dir / "v67_c3_monthly_top10_metrics.csv", baseline)
    _write_gzip_csv(output_dir / "v67_weekly_signal_states.csv.gz", states)
    _write_gzip_csv(output_dir / "v67_cohort_events.csv.gz", events)
    _write_csv(output_dir / "v67_cohort_metrics.csv", metrics)
    _write_csv(output_dir / "v67_shadow_focus_vpi_tlg_baf.csv", shadow_focus)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "challenger_models_run": False,
        "workstation_environment_contract": "vn_quant_local_system/.venv",
        "training_source": "LOCAL_POINT_IN_TIME_HOSE_MARKET_STORE",
        "v22_used_as_training_input": False,
        "static_current_hose_mapping_allowed": False,
        "venue_source_mode": market.venue_source.mode,
        "venue_source_table": market.venue_source.table,
        "store_first_day": market.calendar[0].isoformat(),
        "store_last_day": market.calendar[-1].isoformat(),
        "analysis_end_effective": effective_end.isoformat(),
        "historical_selection_end": historical_end.isoformat(),
        "august_2026_shadow_only": True,
        "historical_selection_uses_august_2026": False,
        "hose_symbol_count_seen": len(market.symbols),
        "monthly_snapshot_count": len(snapshots),
        "c3_training_row_count": len(training_rows),
        "monthly_ranking_row_count": len(rankings),
        "weekly_signal_state_count": len(states),
        "cohort_event_count": len(events),
        "cohort_hypothesis_count": len(cohort_contract.ALL_COHORTS),
        "shadow_focus_row_count": len(shadow_focus),
        "causality": "COMPLETED_SIGNAL_CLOSE_TO_NEXT_SESSION_OPEN",
        "c3_weight_training": "ONLY_LABELS_COMPLETED_BEFORE_EACH_SIGNAL_DAY",
        "research_only": True,
        "live_model_change_authorized": False,
        "automatic_live_orders_allowed": False,
        "limitations": [
            "corporate-action and price-basis lineage must still be audited before live promotion",
            "cohort events are overlapping observations and are not independent samples",
            "August 2026 is shadow-only and cannot be used to tune thresholds",
            "portfolio-level benefit requires a later exposure-normalized simulation",
            "challenger ML is intentionally deferred until this C3-native HOSE baseline is verified",
        ],
    }
    (output_dir / "v67_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--historical-end", type=date.fromisoformat, default=HISTORICAL_END_DEFAULT)
    parser.add_argument("--analysis-end", type=date.fromisoformat, default=ANALYSIS_END_DEFAULT)
    parser.add_argument("--price-multiplier", type=float, default=PRICE_MULTIPLIER_DEFAULT)
    args = parser.parse_args(argv)
    report = run_study(store=args.store, output_dir=args.output_dir, historical_end=args.historical_end, analysis_end=args.analysis_end, price_multiplier=args.price_multiplier)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
