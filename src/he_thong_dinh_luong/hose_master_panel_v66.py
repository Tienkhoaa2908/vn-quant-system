"""V66 HOSE 11-year master-panel builder.

Research-only. The panel is built directly from the workstation market SQLite
store. It never places orders or mutates live/paper policy.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
import gzip
import json
import math
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping, Sequence

import numpy as np

SCHEMA_VERSION = "hose_master_panel_v66"
PRICE_MULTIPLIER_DEFAULT = 1000.0
MIN_ADV20_VND = 5_000_000_000.0
MAX_ZERO_VOLUME_60 = 5
VENUE_COLUMNS = ("exchange", "market", "floor", "venue", "board", "trading_place", "stock_exchange", "exchange_code", "market_code")
SYMBOL_COLUMNS = ("symbol", "ticker", "code", "security_code")
START_COLUMNS = ("effective_from", "start_date", "from_date", "listed_date", "listing_date", "valid_from", "begin_date", "day", "date")
END_COLUMNS = ("effective_to", "end_date", "to_date", "delisted_date", "delisting_date", "valid_to", "finish_date")
HOSE_TOKENS = ("HOSE", "HSX", "HO CHI MINH")
FEATURE_FIELDS = (
    "return_1", "return_5", "return_10", "return_20", "return_60", "return_120", "return_250",
    "relative_5", "relative_20", "relative_60", "relative_120",
    "distance_ma10", "distance_ma20", "distance_ma50", "distance_ma100", "distance_ma250", "ma20_slope5",
    "drawdown_20", "drawdown_60", "drawdown_250",
    "realized_vol_10", "realized_vol_20", "realized_vol_60", "vol_ratio_20_60",
    "volume_ratio_5_20", "log_adv20_vnd", "zero_volume_60",
    "breakout_20_gap", "breakdown_20_low_gap", "gap_1", "intraday_return", "range_20",
    "index_return_20", "index_return_60", "index_distance_ma250",
    "cs_rel20", "cs_rel120", "cs_lowvol", "cs_drawdown20", "cs_volume", "cs_ma20", "cs_adv20",
)
TARGET_FIELDS = (
    "fwd_return_5", "fwd_excess_5", "fwd_return_10", "fwd_excess_10", "fwd_return_20", "fwd_excess_20",
    "mae_10", "mfe_10", "target_opportunity_10", "target_damage_10",
)
PANEL_FIELDS = (
    "signal_day", "symbol", "venue_source_mode", "venue_source_table", "feature_complete",
    "liquid_universe", "eligible_long", "market_risk_on",
) + FEATURE_FIELDS + TARGET_FIELDS + ("label_end_20",)


@dataclass(frozen=True)
class VenueSource:
    mode: str
    table: str
    symbol_col: str
    venue_col: str
    start_col: str | None = None
    end_col: str | None = None


@dataclass(frozen=True)
class BarSeries:
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray


def _norm_name(value: str) -> str:
    return str(value).strip().lower()


def _quote(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _table_columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({_quote(table)})")]


def inspect_schema(db: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [str(row[0]) for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not str(row[0]).startswith("sqlite_")]
    return {table: _table_columns(db, table) for table in tables}


def _find_col(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    by_lower = {_norm_name(col): col for col in columns}
    for candidate in candidates:
        if candidate in by_lower:
            return by_lower[candidate]
    return None


def _looks_hose(value: object) -> bool:
    text = str(value or "").strip().upper()
    return any(token in text for token in HOSE_TOKENS)


def resolve_venue_source(db: sqlite3.Connection) -> VenueSource:
    schema = inspect_schema(db)
    if "bars" not in schema:
        raise ValueError("V66_BARS_TABLE_MISSING")
    bars_symbol = _find_col(schema["bars"], SYMBOL_COLUMNS)
    bars_venue = _find_col(schema["bars"], VENUE_COLUMNS)
    if bars_symbol and bars_venue:
        return VenueSource("BAR_LEVEL", "bars", bars_symbol, bars_venue)
    interval_candidates: list[VenueSource] = []
    static_candidates: list[VenueSource] = []
    for table, cols in schema.items():
        if table == "bars":
            continue
        symbol = _find_col(cols, SYMBOL_COLUMNS)
        venue = _find_col(cols, VENUE_COLUMNS)
        if not symbol or not venue:
            continue
        start = _find_col(cols, START_COLUMNS)
        end = _find_col(cols, END_COLUMNS)
        candidate = VenueSource("INTERVAL" if start else "STATIC", table, symbol, venue, start, end)
        (interval_candidates if start else static_candidates).append(candidate)
    if interval_candidates:
        interval_candidates.sort(key=lambda item: (item.end_col is None, len(item.table), item.table))
        return interval_candidates[0]
    if static_candidates:
        static_candidates.sort(key=lambda item: (len(item.table), item.table))
        return static_candidates[0]
    raise ValueError("V66_HOSE_EXCHANGE_METADATA_NOT_FOUND")


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
    sql = f"SELECT {','.join(_quote(c) for c in cols)} FROM {_quote(source.table)}"
    output: dict[str, list[tuple[date | None, date | None, bool]]] = {}
    for row in db.execute(sql):
        symbol = str(row[0] or "").strip().upper()
        if not symbol:
            continue
        start = _date_or_none(row[2]) if source.start_col else None
        end_index = 3 if source.start_col else 2
        end = _date_or_none(row[end_index]) if source.end_col else None
        output.setdefault(symbol, []).append((start, end, _looks_hose(row[1])))
    for symbol in output:
        output[symbol].sort(key=lambda item: (item[0] or date.min, item[1] or date.max))
    return output


def _is_hose_at(symbol: str, day: date, source: VenueSource, intervals: Mapping[str, Sequence[tuple[date | None, date | None, bool]]], bar_venue: object | None) -> bool:
    if source.mode == "BAR_LEVEL":
        return _looks_hose(bar_venue)
    items = intervals.get(symbol, ())
    if source.mode == "STATIC":
        return any(item[2] for item in items)
    matches = [venue for start, end, venue in items if (start is None or start <= day) and (end is None or day <= end)]
    if matches and any(value != matches[0] for value in matches):
        raise ValueError(f"V66_CONFLICTING_EXCHANGE_INTERVAL:{symbol}:{day}")
    return bool(matches and matches[0])


def _sample_std(values: np.ndarray) -> float:
    clean = values[np.isfinite(values)]
    return float(np.std(clean, ddof=1)) if clean.size >= 2 else float("nan")


def _pct_rank(values: list[float], *, reverse: bool = False) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: values[i], reverse=reverse)
    ranks = [0.0] * n
    pos = 0
    while pos < n:
        end = pos + 1
        while end < n and values[order[end]] == values[order[pos]]:
            end += 1
        avg_rank = (pos + 1 + end) / 2.0
        for k in range(pos, end):
            ranks[order[k]] = avg_rank
        pos = end
    if n == 1:
        return [0.5]
    return [(rank - 1.0) / (n - 1.0) for rank in ranks]


def _last_sessions_by_week(calendar: Sequence[date]) -> list[date]:
    by_week: dict[tuple[int, int], date] = {}
    for day in calendar:
        iso = day.isocalendar()
        by_week[(iso.year, iso.week)] = day
    return [by_week[key] for key in sorted(by_week)]


def _build_arrays(db: sqlite3.Connection, source: VenueSource, price_multiplier: float) -> tuple[list[date], dict[str, BarSeries], dict[tuple[str, date], object], np.ndarray, np.ndarray]:
    schema = inspect_schema(db)
    cols = schema["bars"]
    by_lower = {_norm_name(c): c for c in cols}
    required = {"symbol", "day", "open", "close", "volume"}
    if not required.issubset(by_lower):
        raise ValueError("V66_BARS_REQUIRED_COLUMNS_MISSING")
    high_col = by_lower.get("high", by_lower["close"])
    low_col = by_lower.get("low", by_lower["close"])
    asset_col = by_lower.get("asset_type")
    venue_col = source.venue_col if source.mode == "BAR_LEVEL" else None
    select_cols = [by_lower["symbol"], by_lower["day"], by_lower["open"], high_col, low_col, by_lower["close"], by_lower["volume"]]
    if asset_col:
        select_cols.append(asset_col)
    if venue_col and venue_col not in select_cols:
        select_cols.append(venue_col)
    rows = db.execute(f"SELECT {','.join(_quote(c) for c in select_cols)} FROM bars ORDER BY day,symbol").fetchall()
    parsed: list[tuple[str, date, float, float, float, float, float]] = []
    index_rows: list[tuple[date, float, float]] = []
    venue_by_bar: dict[tuple[str, date], object] = {}
    for row in rows:
        symbol = str(row[0] or "").strip().upper()
        day = _date_or_none(row[1])
        if not symbol or day is None:
            continue
        try:
            o, h, l, c = map(float, row[2:6])
            volume = float(row[6])
        except (TypeError, ValueError):
            continue
        offset = 7
        asset = str(row[offset]).strip().upper() if asset_col else "STOCK"
        if asset_col:
            offset += 1
        venue = row[offset] if venue_col and offset < len(row) else None
        if asset == "INDEX" and symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
            index_rows.append((day, o, c))
            continue
        if asset_col and asset != "STOCK":
            continue
        if venue_col:
            venue_by_bar[(symbol, day)] = venue
        parsed.append((symbol, day, o * price_multiplier, h * price_multiplier, l * price_multiplier, c * price_multiplier, volume))
    if not index_rows:
        raise ValueError("V66_VNINDEX_MISSING")
    calendar = sorted({row[0] for row in index_rows})
    day_index = {day: i for i, day in enumerate(calendar)}
    n = len(calendar)
    index_open = np.full(n, np.nan)
    index_close = np.full(n, np.nan)
    for day, o, c in index_rows:
        idx = day_index.get(day)
        if idx is not None:
            index_open[idx] = float(o)
            index_close[idx] = float(c)
    if np.isnan(index_close).any():
        raise ValueError("V66_VNINDEX_CALENDAR_GAPS")
    arrays: dict[str, BarSeries] = {}
    for symbol in sorted({row[0] for row in parsed}):
        arrays[symbol] = BarSeries(*(np.full(n, np.nan) for _ in range(5)))
    for symbol, day, o, h, l, c, volume in parsed:
        idx = day_index.get(day)
        if idx is None:
            continue
        series = arrays[symbol]
        series.open[idx], series.high[idx], series.low[idx], series.close[idx], series.volume[idx] = o, h, l, c, volume
    return calendar, arrays, venue_by_bar, index_open, index_close


def _ret(arr: np.ndarray, pos: int, lag: int) -> float:
    if pos < lag or not np.isfinite(arr[pos]) or not np.isfinite(arr[pos - lag]) or arr[pos - lag] <= 0:
        return float("nan")
    return float(arr[pos] / arr[pos - lag] - 1.0)


def _ma(arr: np.ndarray, pos: int, window: int) -> float:
    if pos + 1 < window:
        return float("nan")
    values = arr[pos - window + 1:pos + 1]
    return float(np.mean(values)) if values.size == window and not np.isnan(values).any() else float("nan")


def _weekly_row(*, symbol: str, pos: int, calendar: Sequence[date], series: BarSeries, index_close: np.ndarray, source: VenueSource, intervals: Mapping[str, Sequence[tuple[date | None, date | None, bool]]], venue_by_bar: Mapping[tuple[str, date], object]) -> dict[str, object] | None:
    day = calendar[pos]
    if pos < 250 or not _is_hose_at(symbol, day, source, intervals, venue_by_bar.get((symbol, day))):
        return None
    c = series.close
    if not np.isfinite(c[pos]) or c[pos] <= 0:
        return None
    windows: dict[int, np.ndarray] = {}
    for window in (10, 20, 50, 60, 100, 120, 250):
        values = c[pos - window + 1:pos + 1]
        if values.size != window or np.isnan(values).any():
            return None
        windows[window] = values
    returns = {lag: _ret(c, pos, lag) for lag in (1, 5, 10, 20, 60, 120, 250)}
    index_returns = {lag: _ret(index_close, pos, lag) for lag in (5, 20, 60, 120)}
    if any(not math.isfinite(v) for v in list(returns.values()) + list(index_returns.values())):
        return None
    ma = {window: float(np.mean(windows[window])) for window in (10, 20, 50, 100, 250)}
    ma20_prev = _ma(c, pos - 5, 20)
    if not math.isfinite(ma20_prev) or ma20_prev <= 0:
        return None
    daily_ret60 = windows[60][1:] / windows[60][:-1] - 1.0
    vol10, vol20, vol60 = _sample_std(daily_ret60[-9:]), _sample_std(daily_ret60[-19:]), _sample_std(daily_ret60)
    if not all(math.isfinite(v) and v >= 0 for v in (vol10, vol20, vol60)):
        return None
    vol20_values = series.volume[pos - 19:pos + 1]
    vol60_values = series.volume[pos - 59:pos + 1]
    if np.isnan(vol20_values).any() or np.isnan(vol60_values).any():
        return None
    avg20vol = float(np.mean(vol20_values))
    avg5vol = float(np.mean(series.volume[pos - 4:pos + 1]))
    adv20 = float(np.mean(windows[20] * vol20_values))
    zero60 = int(np.sum(vol60_values <= 0))
    prior20 = c[pos - 20:pos]
    ranges = (series.high[pos - 19:pos + 1] - series.low[pos - 19:pos + 1]) / windows[20]
    if np.isnan(prior20).any() or np.isnan(ranges).any():
        return None
    open_now, prior_close = series.open[pos], c[pos - 1]
    index_ma250 = _ma(index_close, pos, 250)
    if not all(math.isfinite(v) and v > 0 for v in (open_now, prior_close, index_ma250)):
        return None
    liquid = adv20 >= MIN_ADV20_VND and zero60 <= MAX_ZERO_VOLUME_60
    risk_on = bool(index_close[pos] >= index_ma250)
    eligible_long = bool(liquid and c[pos] >= ma[250])
    return {
        "signal_day": day.isoformat(), "symbol": symbol, "venue_source_mode": source.mode, "venue_source_table": source.table,
        "feature_complete": True, "liquid_universe": liquid, "eligible_long": eligible_long, "market_risk_on": risk_on,
        "return_1": returns[1], "return_5": returns[5], "return_10": returns[10], "return_20": returns[20], "return_60": returns[60], "return_120": returns[120], "return_250": returns[250],
        "relative_5": returns[5] - index_returns[5], "relative_20": returns[20] - index_returns[20], "relative_60": returns[60] - index_returns[60], "relative_120": returns[120] - index_returns[120],
        "distance_ma10": c[pos] / ma[10] - 1.0, "distance_ma20": c[pos] / ma[20] - 1.0, "distance_ma50": c[pos] / ma[50] - 1.0, "distance_ma100": c[pos] / ma[100] - 1.0, "distance_ma250": c[pos] / ma[250] - 1.0,
        "ma20_slope5": ma[20] / ma20_prev - 1.0,
        "drawdown_20": c[pos] / float(np.max(windows[20])) - 1.0, "drawdown_60": c[pos] / float(np.max(windows[60])) - 1.0, "drawdown_250": c[pos] / float(np.max(windows[250])) - 1.0,
        "realized_vol_10": vol10, "realized_vol_20": vol20, "realized_vol_60": vol60, "vol_ratio_20_60": vol20 / vol60 if vol60 > 0 else 0.0,
        "volume_ratio_5_20": avg5vol / avg20vol if avg20vol > 0 else 0.0, "log_adv20_vnd": math.log1p(max(0.0, adv20)), "zero_volume_60": zero60,
        "breakout_20_gap": c[pos] / float(np.max(prior20)) - 1.0, "breakdown_20_low_gap": c[pos] / float(np.min(prior20)) - 1.0,
        "gap_1": open_now / prior_close - 1.0, "intraday_return": c[pos] / open_now - 1.0, "range_20": float(np.mean(ranges)),
        "index_return_20": index_returns[20], "index_return_60": index_returns[60], "index_distance_ma250": index_close[pos] / index_ma250 - 1.0,
    }


def _attach_cross_sectional(rows: list[dict[str, object]]) -> None:
    specs = (("relative_20", "cs_rel20", False), ("relative_120", "cs_rel120", False), ("realized_vol_60", "cs_lowvol", True), ("drawdown_20", "cs_drawdown20", False), ("volume_ratio_5_20", "cs_volume", False), ("distance_ma20", "cs_ma20", False), ("log_adv20_vnd", "cs_adv20", False))
    for source, target, reverse in specs:
        ranks = _pct_rank([float(row[source]) for row in rows], reverse=reverse)
        for row, rank in zip(rows, ranks):
            row[target] = rank


def _attach_targets(rows: list[dict[str, object]], *, pos: int, calendar: Sequence[date], series_by_symbol: Mapping[str, BarSeries], index_open: np.ndarray) -> None:
    if pos + 21 >= len(calendar):
        for row in rows:
            for field in TARGET_FIELDS:
                row[field] = ""
            row["label_end_20"] = ""
        return
    for row in rows:
        series = series_by_symbol[str(row["symbol"])]
        entry_pos = pos + 1
        entry, benchmark_entry = series.open[entry_pos], index_open[entry_pos]
        if not all(np.isfinite(v) and v > 0 for v in (entry, benchmark_entry)):
            for field in TARGET_FIELDS:
                row[field] = ""
            row["label_end_20"] = ""
            continue
        valid = True
        for horizon in (5, 10, 20):
            end_pos = entry_pos + horizon
            stock_end, index_end = series.open[end_pos], index_open[end_pos]
            if not all(np.isfinite(v) and v > 0 for v in (stock_end, index_end)):
                valid = False
                break
            stock_return = float(stock_end / entry - 1.0)
            row[f"fwd_return_{horizon}"] = stock_return
            row[f"fwd_excess_{horizon}"] = stock_return - float(index_end / benchmark_entry - 1.0)
        if not valid:
            for field in TARGET_FIELDS:
                row[field] = ""
            row["label_end_20"] = ""
            continue
        future_low = series.low[entry_pos:entry_pos + 10]
        future_high = series.high[entry_pos:entry_pos + 10]
        row["mae_10"] = "" if np.isnan(future_low).any() else float(np.min(future_low) / entry - 1.0)
        row["mfe_10"] = "" if np.isnan(future_high).any() else float(np.max(future_high) / entry - 1.0)
        row["target_opportunity_10"] = ""
        row["target_damage_10"] = ""
        row["label_end_20"] = calendar[entry_pos + 20].isoformat()
    eligible = [row for row in rows if row.get("fwd_excess_10") not in ("", None) and bool(row["eligible_long"])]
    liquid = [row for row in rows if row.get("fwd_excess_10") not in ("", None) and bool(row["liquid_universe"])]
    eligible_ids = {id(row) for row in eligible}
    liquid_ids = {id(row) for row in liquid}
    if len(eligible) >= 10:
        q80 = float(np.quantile([float(row["fwd_excess_10"]) for row in eligible], 0.80))
        for row in rows:
            if id(row) in eligible_ids:
                row["target_opportunity_10"] = int(float(row["fwd_excess_10"]) >= q80)
    if len(liquid) >= 10:
        q20 = float(np.quantile([float(row["fwd_excess_10"]) for row in liquid], 0.20))
        for row in rows:
            if id(row) in liquid_ids:
                mae = row.get("mae_10")
                severe_path = mae not in ("", None) and float(mae) <= -0.08
                row["target_damage_10"] = int(float(row["fwd_excess_10"]) <= q20 or severe_path)


def _write_csv_gz(path: Path, rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build_master_panel(*, store_path: Path, output_dir: Path, price_multiplier: float = PRICE_MULTIPLIER_DEFAULT, require_point_in_time_exchange: bool = True) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(Path(store_path)) as db:
        db.row_factory = sqlite3.Row
        schema = inspect_schema(db)
        (output_dir / "v66_sqlite_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        source = resolve_venue_source(db)
        if require_point_in_time_exchange and source.mode == "STATIC":
            raise ValueError(f"V66_STATIC_EXCHANGE_METADATA_NOT_ACCEPTED:{source.table}:{source.venue_col}")
        intervals = _membership_intervals(db, source)
        calendar, series_by_symbol, venue_by_bar, index_open, index_close = _build_arrays(db, source, price_multiplier)
    weekly_days = _last_sessions_by_week(calendar)
    day_index = {day: i for i, day in enumerate(calendar)}
    panel_rows: list[dict[str, object]] = []
    weekly_audit: list[dict[str, object]] = []
    per_symbol_rows: dict[str, int] = {}
    for day in weekly_days:
        pos = day_index[day]
        current = []
        for symbol, series in series_by_symbol.items():
            row = _weekly_row(symbol=symbol, pos=pos, calendar=calendar, series=series, index_close=index_close, source=source, intervals=intervals, venue_by_bar=venue_by_bar)
            if row is not None:
                current.append(row)
        if not current:
            continue
        _attach_cross_sectional(current)
        _attach_targets(current, pos=pos, calendar=calendar, series_by_symbol=series_by_symbol, index_open=index_open)
        panel_rows.extend(current)
        for row in current:
            symbol = str(row["symbol"])
            per_symbol_rows[symbol] = per_symbol_rows.get(symbol, 0) + 1
        weekly_audit.append({
            "signal_day": day.isoformat(), "hose_feature_complete_count": len(current),
            "liquid_count": sum(bool(row["liquid_universe"]) for row in current),
            "eligible_long_count": sum(bool(row["eligible_long"]) for row in current),
            "opportunity_label_count": sum(row.get("target_opportunity_10") not in ("", None) for row in current),
            "damage_label_count": sum(row.get("target_damage_10") not in ("", None) for row in current),
        })
    if not panel_rows:
        raise ValueError("V66_NO_HOSE_PANEL_ROWS")
    _write_csv_gz(output_dir / "v66_hose_master_panel.csv.gz", panel_rows, PANEL_FIELDS)
    with (output_dir / "v66_weekly_universe_audit.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(weekly_audit[0].keys()), lineterminator="\n"); writer.writeheader(); writer.writerows(weekly_audit)
    with (output_dir / "v66_symbol_coverage.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["symbol", "weekly_row_count"], lineterminator="\n"); writer.writeheader(); writer.writerows({"symbol": symbol, "weekly_row_count": count} for symbol, count in sorted(per_symbol_rows.items()))
    dates = [date.fromisoformat(str(row["signal_day"])) for row in panel_rows]
    report = {
        "schema_version": SCHEMA_VERSION, "status": "SUCCESS", "store_path": str(store_path), "venue_source": source.__dict__,
        "point_in_time_exchange_required": require_point_in_time_exchange, "point_in_time_exchange_satisfied": source.mode in {"BAR_LEVEL", "INTERVAL"},
        "calendar_first_day": calendar[0].isoformat(), "calendar_last_day": calendar[-1].isoformat(),
        "panel_first_signal_day": min(dates).isoformat(), "panel_last_signal_day": max(dates).isoformat(),
        "weekly_signal_count": len({row["signal_day"] for row in panel_rows}), "distinct_hose_symbol_count": len(per_symbol_rows), "panel_row_count": len(panel_rows),
        "liquid_row_count": sum(bool(row["liquid_universe"]) for row in panel_rows), "eligible_long_row_count": sum(bool(row["eligible_long"]) for row in panel_rows),
        "opportunity_label_row_count": sum(row.get("target_opportunity_10") not in ("", None) for row in panel_rows), "damage_label_row_count": sum(row.get("target_damage_10") not in ("", None) for row in panel_rows),
        "feature_fields": list(FEATURE_FIELDS), "target_fields": list(TARGET_FIELDS), "master_panel_is_primary_ml_input": True, "v22_used_as_training_input": False,
        "research_only": True, "automatic_live_orders_allowed": False,
    }
    (output_dir / "v66_panel_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--price-multiplier", type=float, default=PRICE_MULTIPLIER_DEFAULT)
    parser.add_argument("--allow-static-exchange", action="store_true")
    args = parser.parse_args(argv)
    report = build_master_panel(store_path=args.store, output_dir=args.output_dir, price_multiplier=args.price_multiplier, require_point_in_time_exchange=not args.allow_static_exchange)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
