"""V60 causal C3 short-horizon / preview-entry research.

The current live C3 policy uses monthly canonical Top-10 as the buy universe and
latest preview only as a blocking guard. This study asks whether preview leaders
carry tradeable 5-10 session alpha and whether canonical leaders decay before
the monthly sell gate can react.

Research only. No broker access and no live policy mutation.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
import sqlite3
from statistics import fmean, median
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import weekly_micro_capital_v43 as v43

SCHEMA_VERSION = "c3_short_horizon_v60"
ANALYSIS_END_DEFAULT = date(2026, 7, 31)
HOLDOUT_START_DEFAULT = date(2022, 1, 1)
HORIZONS = (1, 3, 5, 10, 15, 20)
TRADE_HORIZONS = (5, 10)
COHORTS = (
    "PREVIEW_TOP10",
    "NEW_PREVIEW_TOP10",
    "NEW_PREVIEW_TOP5",
    "CANONICAL_TOP10_RETAINED",
    "CANONICAL_TOP10_DROPPED20",
)
MIN_ADV20_VND = 5_000_000_000.0
MAX_ZERO_VOLUME_60 = 5


@dataclass(frozen=True)
class Market:
    calendar: tuple[date, ...]
    index_open: Mapping[date, float]
    index_close: Mapping[date, float]
    stock_open: Mapping[tuple[str, date], float]
    stock_close: Mapping[tuple[str, date], float]
    stock_volume: Mapping[tuple[str, date], int]


@dataclass(frozen=True)
class PreviewRow:
    symbol: str
    rank: int
    score: float
    volatility_60: float


def _load_market(path: Path, *, price_multiplier: float) -> Market:
    with sqlite3.connect(Path(path)) as db:
        db.row_factory = sqlite3.Row
        index_rows = db.execute(
            """
            SELECT day,open,close FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
            ORDER BY day
            """
        ).fetchall()
        stock_rows = db.execute(
            """
            SELECT symbol,day,open,close,volume FROM bars
            WHERE upper(asset_type)='STOCK'
            ORDER BY symbol,day
            """
        ).fetchall()
    if not index_rows or not stock_rows:
        raise ValueError("V60_STORE_REQUIRES_STOCKS_AND_VNINDEX")
    index_open: dict[date, float] = {}
    index_close: dict[date, float] = {}
    for row in index_rows:
        day = date.fromisoformat(str(row["day"]))
        index_open[day] = float(row["open"])
        index_close[day] = float(row["close"])
    stock_open: dict[tuple[str, date], float] = {}
    stock_close: dict[tuple[str, date], float] = {}
    stock_volume: dict[tuple[str, date], int] = {}
    for row in stock_rows:
        symbol = str(row["symbol"]).upper()
        day = date.fromisoformat(str(row["day"]))
        stock_open[(symbol, day)] = float(row["open"]) * price_multiplier
        stock_close[(symbol, day)] = float(row["close"]) * price_multiplier
        stock_volume[(symbol, day)] = int(row["volume"])
    calendar = tuple(sorted(index_close))
    return Market(
        calendar=calendar,
        index_open=index_open,
        index_close=index_close,
        stock_open=stock_open,
        stock_close=stock_close,
        stock_volume=stock_volume,
    )


def _weekly_signal_days(calendar: Sequence[date], *, end: date) -> list[date]:
    by_week: dict[tuple[int, int], date] = {}
    for day in calendar:
        if day > end:
            continue
        iso = day.isocalendar()
        by_week[(iso.year, iso.week)] = day  # last session of each ISO week
    return [by_week[key] for key in sorted(by_week)]


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _canonical_snapshot_for_day(
    snapshots: Sequence[v43.SignalSnapshot],
    signal_days: Sequence[date],
    evaluation_day: date,
) -> v43.SignalSnapshot | None:
    """Use only a month that is known completed before the evaluation month."""
    cutoff = _month_start(evaluation_day)
    index = bisect.bisect_left(signal_days, cutoff) - 1
    return snapshots[index] if index >= 0 else None


def _universe_by_signal(rows: Sequence[v43.ResearchRow]) -> dict[date, tuple[str, ...]]:
    by_day: dict[date, set[str]] = {}
    for row in rows:
        by_day.setdefault(row.signal_day, set()).add(row.symbol)
    return {day: tuple(sorted(symbols)) for day, symbols in by_day.items()}


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = fmean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _preview_ranking(
    *,
    evaluation_day: date,
    canonical: v43.SignalSnapshot,
    universe: Sequence[str],
    market: Market,
    calendar_index: Mapping[date, int],
) -> list[PreviewRow]:
    position = calendar_index.get(evaluation_day)
    if position is None or position < 250:
        return []
    calendar = market.calendar
    window250 = calendar[position - 249 : position + 1]
    window61 = calendar[position - 60 : position + 1]
    window60 = calendar[position - 59 : position + 1]
    window20 = calendar[position - 19 : position + 1]
    day120 = calendar[position - 120]
    index_return120 = market.index_close[evaluation_day] / market.index_close[day120] - 1.0

    features: list[tuple[str, float, float, float]] = []
    for symbol in universe:
        required = set(window250) | set(window61) | {day120}
        if any((symbol, day) not in market.stock_close for day in required):
            continue
        closes250 = [market.stock_close[(symbol, day)] for day in window250]
        closes61 = [market.stock_close[(symbol, day)] for day in window61]
        returns60 = [closes61[i] / closes61[i - 1] - 1.0 for i in range(1, len(closes61))]
        volatility60 = _sample_std(returns60)
        if volatility60 <= 0.0:
            continue
        close = market.stock_close[(symbol, evaluation_day)]
        above_ma250 = close >= fmean(closes250)
        adv20 = fmean(
            market.stock_close[(symbol, day)] * market.stock_volume.get((symbol, day), 0)
            for day in window20
        )
        zero60 = sum(1 for day in window60 if market.stock_volume.get((symbol, day), 0) <= 0)
        if not above_ma250 or adv20 < MIN_ADV20_VND or zero60 > MAX_ZERO_VOLUME_60:
            continue
        stock_return120 = close / market.stock_close[(symbol, day120)] - 1.0
        rs120 = stock_return120 - index_return120
        high52 = close / max(closes250)
        features.append((symbol, -volatility60, rs120, high52))
    if not features:
        return []

    low_pct = v43.average_percentile([row[1] for row in features])
    rs_pct = v43.average_percentile([row[2] for row in features])
    high_pct = v43.average_percentile([row[3] for row in features])
    scored: list[tuple[str, float, float]] = []
    for index, (symbol, low, rs, high) in enumerate(features):
        score = (
            float(canonical.weights["low_volatility"]) * low_pct[index]
            + float(canonical.weights["relative_strength_120"]) * rs_pct[index]
            + float(canonical.weights["high_52_week"]) * high_pct[index]
        )
        scored.append((symbol, score, abs(low)))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [
        PreviewRow(symbol=symbol, rank=rank, score=score, volatility_60=volatility)
        for rank, (symbol, score, volatility) in enumerate(scored, start=1)
    ]


def _phase(day: date, holdout_start: date) -> str:
    return "HOLDOUT" if day >= holdout_start else "CALIBRATION"


def _age_bucket(age: int) -> str:
    if age <= 5:
        return "01_05"
    if age <= 10:
        return "06_10"
    if age <= 15:
        return "11_15"
    if age <= 20:
        return "16_20"
    return "21_PLUS"


def _event_return(
    *,
    symbol: str,
    signal_day: date,
    horizon: int,
    market: Market,
    calendar_index: Mapping[date, int],
    slippage_bps: float,
) -> dict[str, object] | None:
    signal_index = calendar_index.get(signal_day)
    if signal_index is None:
        return None
    entry_index = signal_index + 1
    exit_index = entry_index + horizon
    if exit_index >= len(market.calendar):
        return None
    entry_day = market.calendar[entry_index]
    exit_day = market.calendar[exit_index]
    stock_entry = market.stock_open.get((symbol, entry_day))
    stock_exit = market.stock_open.get((symbol, exit_day))
    index_entry = market.index_open.get(entry_day)
    index_exit = market.index_open.get(exit_day)
    if not all(value is not None and value > 0 for value in (stock_entry, stock_exit, index_entry, index_exit)):
        return None
    buy = v43._buy_total(float(stock_entry), 1, slippage_bps)
    sell = v43._sell_proceeds(float(stock_exit), 1, slippage_bps)
    net_return = sell / buy - 1.0
    benchmark_return = float(index_exit) / float(index_entry) - 1.0
    return {
        "entry_day": entry_day.isoformat(),
        "exit_day": exit_day.isoformat(),
        "net_return": net_return,
        "benchmark_return": benchmark_return,
        "net_excess_return": net_return - benchmark_return,
    }


def _cohort_members(
    preview: Sequence[PreviewRow], canonical: v43.SignalSnapshot
) -> dict[str, list[str]]:
    preview_rank = {row.symbol: row.rank for row in preview}
    preview_top10 = [row.symbol for row in preview[:10]]
    preview_top5 = [row.symbol for row in preview[:5]]
    canonical_top10 = list(canonical.ranking[:10])
    canonical_set = set(canonical_top10)
    return {
        "PREVIEW_TOP10": preview_top10,
        "NEW_PREVIEW_TOP10": [symbol for symbol in preview_top10 if symbol not in canonical_set],
        "NEW_PREVIEW_TOP5": [symbol for symbol in preview_top5 if symbol not in canonical_set],
        "CANONICAL_TOP10_RETAINED": [symbol for symbol in canonical_top10 if preview_rank.get(symbol, 10**9) <= 10],
        "CANONICAL_TOP10_DROPPED20": [symbol for symbol in canonical_top10 if preview_rank.get(symbol, 10**9) > 20],
    }


def _aggregate(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int, str], list[float]] = {}
    for event in events:
        key = (
            str(event["phase"]),
            str(event["cohort"]),
            int(event["horizon"]),
            str(event["scenario"]),
        )
        grouped.setdefault(key, []).append(float(event["net_excess_return"]))
    output: list[dict[str, object]] = []
    for key, values in sorted(grouped.items()):
        ordered = sorted(values)
        p10_index = max(int(math.floor(0.10 * (len(ordered) - 1))), 0)
        output.append(
            {
                "phase": key[0],
                "cohort": key[1],
                "horizon": key[2],
                "scenario": key[3],
                "event_count": len(values),
                "mean_net_excess_return": fmean(values),
                "median_net_excess_return": median(values),
                "hit_rate": sum(value > 0.0 for value in values) / len(values),
                "p10_net_excess_return": ordered[p10_index],
            }
        )
    return output


def _aggregate_decay(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int], list[float]] = {}
    for row in rows:
        key = (str(row["phase"]), str(row["age_bucket"]), int(row["horizon"]))
        grouped.setdefault(key, []).append(float(row["net_excess_return"]))
    return [
        {
            "phase": phase,
            "age_bucket": bucket,
            "horizon": horizon,
            "observation_count": len(values),
            "mean_net_excess_return": fmean(values),
            "median_net_excess_return": median(values),
            "hit_rate": sum(value > 0.0 for value in values) / len(values),
        }
        for (phase, bucket, horizon), values in sorted(grouped.items())
    ]


def _choose_candidate(metrics: Sequence[Mapping[str, object]]) -> dict[str, object] | None:
    candidates = [
        row
        for row in metrics
        if row["phase"] == "CALIBRATION"
        and row["scenario"] == "BASE"
        and row["cohort"] in {"NEW_PREVIEW_TOP10", "NEW_PREVIEW_TOP5"}
        and int(row["horizon"]) in TRADE_HORIZONS
        and int(row["event_count"]) >= 50
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            -float(row["mean_net_excess_return"]),
            -float(row["median_net_excess_return"]),
            -int(row["event_count"]),
            str(row["cohort"]),
            int(row["horizon"]),
        )
    )
    return dict(candidates[0])


def _decision(
    selected: Mapping[str, object] | None,
    metrics: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if selected is None:
        return {"status": "NO_CANDIDATE", "promote_to_paper_research": False}
    cohort = str(selected["cohort"])
    horizon = int(selected["horizon"])
    holdout = [
        row
        for row in metrics
        if row["phase"] == "HOLDOUT"
        and row["cohort"] == cohort
        and int(row["horizon"]) == horizon
    ]
    by_scenario = {str(row["scenario"]): row for row in holdout}
    required = [by_scenario.get(name) for name in v43.SCENARIOS]
    robust = bool(
        all(row is not None for row in required)
        and all(int(row["event_count"]) >= 30 for row in required if row is not None)
        and all(float(row["mean_net_excess_return"]) > 0.0 for row in required if row is not None)
        and all(float(row["hit_rate"]) >= 0.50 for row in required if row is not None)
    )
    return {
        "status": "PROMOTE_TO_PAPER_RESEARCH" if robust else "REJECT_OR_INCONCLUSIVE",
        "promote_to_paper_research": robust,
        "selected_from_calibration": dict(selected),
        "holdout": [dict(row) for row in holdout],
        "live_model_change_authorized": False,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_study(
    *,
    input_zip: Path,
    store_path: Path,
    output_dir: Path,
    output_zip: Path,
    analysis_end: date = ANALYSIS_END_DEFAULT,
    holdout_start: date = HOLDOUT_START_DEFAULT,
    price_multiplier: float = v43.PRICE_MULTIPLIER,
) -> dict[str, object]:
    rows, manifest = v43._load_research_rows(input_zip)
    snapshots, _, _ = v43.build_signal_snapshots(rows)
    market = _load_market(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, market.calendar[-1])
    calendar_index = {day: index for index, day in enumerate(market.calendar)}
    signal_days = [snapshot.day for snapshot in snapshots]
    universe_by_day = _universe_by_signal(rows)
    weekly_days = _weekly_signal_days(market.calendar, end=effective_end)

    events: list[dict[str, object]] = []
    decay_rows: list[dict[str, object]] = []
    preview_rows_output: list[dict[str, object]] = []

    for evaluation_day in weekly_days:
        canonical = _canonical_snapshot_for_day(snapshots, signal_days, evaluation_day)
        if canonical is None:
            continue
        universe = universe_by_day.get(canonical.day, ())
        if not universe:
            continue
        preview = _preview_ranking(
            evaluation_day=evaluation_day,
            canonical=canonical,
            universe=universe,
            market=market,
            calendar_index=calendar_index,
        )
        if not preview:
            continue
        preview_rank = {row.symbol: row.rank for row in preview}
        cohort_members = _cohort_members(preview, canonical)
        age_sessions = calendar_index[evaluation_day] - calendar_index.get(canonical.day, calendar_index[evaluation_day])

        for row in preview[:20]:
            preview_rows_output.append(
                {
                    "evaluation_day": evaluation_day.isoformat(),
                    "canonical_day": canonical.day.isoformat(),
                    "age_sessions": age_sessions,
                    "symbol": row.symbol,
                    "preview_rank": row.rank,
                    "canonical_rank": (
                        list(canonical.ranking).index(row.symbol) + 1
                        if row.symbol in canonical.ranking
                        else None
                    ),
                    "score": row.score,
                }
            )

        for cohort, symbols in cohort_members.items():
            for symbol in symbols:
                for horizon in TRADE_HORIZONS:
                    for scenario, config in v43.SCENARIOS.items():
                        result = _event_return(
                            symbol=symbol,
                            signal_day=evaluation_day,
                            horizon=horizon,
                            market=market,
                            calendar_index=calendar_index,
                            slippage_bps=float(config["slippage_bps"]),
                        )
                        if result is None:
                            continue
                        events.append(
                            {
                                "phase": _phase(evaluation_day, holdout_start),
                                "evaluation_day": evaluation_day.isoformat(),
                                "canonical_day": canonical.day.isoformat(),
                                "age_sessions": age_sessions,
                                "cohort": cohort,
                                "symbol": symbol,
                                "preview_rank": preview_rank.get(symbol),
                                "canonical_rank": (
                                    list(canonical.ranking).index(symbol) + 1
                                    if symbol in canonical.ranking
                                    else None
                                ),
                                "horizon": horizon,
                                "scenario": scenario,
                                **result,
                            }
                        )

        # Signal-decay diagnostic for canonical Top-10. BASE friction only.
        for symbol in canonical.ranking[:10]:
            for horizon in HORIZONS:
                result = _event_return(
                    symbol=symbol,
                    signal_day=evaluation_day,
                    horizon=horizon,
                    market=market,
                    calendar_index=calendar_index,
                    slippage_bps=float(v43.SCENARIOS["BASE"]["slippage_bps"]),
                )
                if result is None:
                    continue
                decay_rows.append(
                    {
                        "phase": _phase(evaluation_day, holdout_start),
                        "evaluation_day": evaluation_day.isoformat(),
                        "canonical_day": canonical.day.isoformat(),
                        "age_sessions": age_sessions,
                        "age_bucket": _age_bucket(age_sessions),
                        "symbol": symbol,
                        "preview_rank": preview_rank.get(symbol),
                        "horizon": horizon,
                        **result,
                    }
                )

    metrics = _aggregate(events)
    decay_metrics = _aggregate_decay(decay_rows)
    selected = _choose_candidate(metrics)
    decision = _decision(selected, metrics)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "preview_top20_weekly.csv", preview_rows_output)
    _write_csv(output_dir / "event_returns.csv", events)
    _write_csv(output_dir / "event_metrics.csv", metrics)
    _write_csv(output_dir / "canonical_signal_decay.csv", decay_rows)
    _write_csv(output_dir / "canonical_signal_decay_metrics.csv", decay_metrics)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "analysis_end_requested": analysis_end.isoformat(),
        "analysis_end_effective": effective_end.isoformat(),
        "holdout_start": holdout_start.isoformat(),
        "august_2026_excluded": effective_end <= date(2026, 7, 31),
        "weekly_evaluation_timing": "WEEK_LAST_CLOSE_TO_NEXT_SESSION_OPEN",
        "canonical_rule": "MOST_RECENT_COMPLETED_MONTH_ONLY",
        "preview_can_add_new_candidates_in_study": True,
        "live_policy_preview_can_add_new_candidates": False,
        "horizons": list(HORIZONS),
        "trade_horizons": list(TRADE_HORIZONS),
        "cohorts": list(COHORTS),
        "weekly_preview_count": len({row["evaluation_day"] for row in preview_rows_output}),
        "event_count": len(events),
        "decay_observation_count": len(decay_rows),
        "selected_candidate": selected,
        "decision": decision,
        "input_manifest_schema_version": manifest.get("schema_version"),
        "live_model_change_authorized": False,
        "automatic_live_orders_allowed": False,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=path.name)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--analysis-end", type=date.fromisoformat, default=ANALYSIS_END_DEFAULT)
    parser.add_argument("--holdout-start", type=date.fromisoformat, default=HOLDOUT_START_DEFAULT)
    parser.add_argument("--price-multiplier", type=float, default=v43.PRICE_MULTIPLIER)
    args = parser.parse_args(argv)
    report = run_study(
        input_zip=args.input_zip,
        store_path=args.store,
        output_dir=args.output_dir,
        output_zip=args.output_zip,
        analysis_end=args.analysis_end,
        holdout_start=args.holdout_start,
        price_multiplier=args.price_multiplier,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
