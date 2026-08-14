"""Mandatory portfolio-profit report for C3 research packages.

This is a gross, execution-aligned research backtest of the C3 monthly Top-10
ranking, not a final production portfolio simulator. It rebalances at the next
VNINDEX trading-session open after each completed monthly C3 signal and exits
at the next monthly rebalance open, so periods are non-overlapping.

Two C3 curves are reported for every V68 sensitivity universe:
- C3_TOP10_ALWAYS_INVESTED_GROSS
- C3_TOP10_RISK_ON_CASH_GROSS (100% cash when the monthly C3 snapshot says
  risk_on=false)

A VNINDEX open-to-open benchmark is reported on the same rebalance calendar.
Fees, sell tax, slippage, lot size, sector caps and allocation constraints are
not included here and must not be implied by this report.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from contextlib import closing
from datetime import date
import gzip
import json
import math
from pathlib import Path
import sqlite3
from statistics import fmean
from typing import Mapping, Sequence

SCHEMA_VERSION = "c3_portfolio_profit_v69"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
ALWAYS = "C3_TOP10_ALWAYS_INVESTED_GROSS"
REGIME = "C3_TOP10_RISK_ON_CASH_GROSS"
BENCHMARK = "VNINDEX_OPEN_TO_OPEN"


def _read_rankings(path: Path) -> dict[date, dict[str, object]]:
    result: dict[date, dict[str, object]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                day = date.fromisoformat(str(row["signal_day"]))
                rank = int(row["rank"])
            except (KeyError, TypeError, ValueError):
                continue
            bucket = result.setdefault(day, {"symbols": [], "risk_on": False})
            if rank <= 10:
                bucket["symbols"].append((rank, str(row["symbol"]).strip().upper()))
            text = str(row.get("risk_on", "")).strip().lower()
            bucket["risk_on"] = text in {"true", "1", "yes"}
    cooked: dict[date, dict[str, object]] = {}
    for day, row in result.items():
        symbols = [symbol for _, symbol in sorted(row["symbols"])]
        if symbols:
            cooked[day] = {"symbols": symbols, "risk_on": bool(row["risk_on"])}
    return cooked


def _load_open_store(store: Path, needed_symbols: set[str]) -> tuple[list[date], dict[date, float], dict[tuple[str, date], float]]:
    uri = store.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        cols = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        required = {"symbol", "day", "open", "asset_type"}
        if not required.issubset(cols):
            raise ValueError("V69_PROFIT_BARS_REQUIRED_COLUMNS_MISSING")
        sql = (
            f'SELECT "{cols["symbol"]}","{cols["day"]}","{cols["open"]}","{cols["asset_type"]}" '
            'FROM "bars" ORDER BY 2,1'
        )
        index_open: dict[date, float] = {}
        stock_open: dict[tuple[str, date], float] = {}
        for symbol_raw, day_raw, open_raw, asset_raw in db.execute(sql):
            symbol = str(symbol_raw or "").strip().upper()
            try:
                day = date.fromisoformat(str(day_raw)[:10])
                value = float(open_raw)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            asset = str(asset_raw or "").strip().upper()
            if symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"} and asset == "INDEX":
                index_open[day] = value
            elif asset in {"STOCK", "EQUITY", ""} and symbol in needed_symbols:
                stock_open[(symbol, day)] = value
    if not index_open:
        raise ValueError("V69_PROFIT_VNINDEX_OPEN_MISSING")
    return sorted(index_open), index_open, stock_open


def _next_session(calendar: Sequence[date], signal_day: date) -> date | None:
    pos = bisect.bisect_right(calendar, signal_day)
    return calendar[pos] if pos < len(calendar) else None


def _max_drawdown(values: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def _cagr(start_value: float, end_value: float, start_day: date, end_day: date) -> float | None:
    years = (end_day - start_day).days / 365.2425
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return None
    return (end_value / start_value) ** (1.0 / years) - 1.0


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields = sorted({str(k) for row in rows for k in row}) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def analyze(*, v68_output: Path, store: Path, output_dir: Path) -> dict[str, object]:
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V69_PROFIT_V68_VARIANTS_MISSING")
    variant_rankings: dict[str, dict[date, dict[str, object]]] = {}
    needed_symbols: set[str] = set()
    for variant_dir in sorted(path for path in variants_root.iterdir() if path.is_dir()):
        path = variant_dir / "v67_c3_monthly_rankings.csv.gz"
        if not path.is_file():
            continue
        rows = _read_rankings(path)
        variant_rankings[variant_dir.name] = rows
        for row in rows.values():
            needed_symbols.update(str(symbol) for symbol in row["symbols"])
    if not variant_rankings:
        raise ValueError("V69_PROFIT_NO_VARIANT_RANKINGS")

    calendar, index_open, stock_open = _load_open_store(store, needed_symbols)
    curve_rows: list[dict[str, object]] = []
    annual_acc: dict[tuple[str, str, int], float] = {}
    summary_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for variant_id, rankings in sorted(variant_rankings.items()):
        signal_days = sorted(rankings)
        strategy_equity = {ALWAYS: 1.0, REGIME: 1.0, BENCHMARK: 1.0}
        strategy_paths = {ALWAYS: [1.0], REGIME: [1.0], BENCHMARK: [1.0]}
        period_returns = {ALWAYS: [], REGIME: [], BENCHMARK: []}
        first_entry: date | None = None
        last_exit: date | None = None
        complete_periods = 0
        total_periods = max(0, len(signal_days) - 1)
        turnover_values: list[float] = []
        prior_symbols: set[str] | None = None

        for current_day, next_day in zip(signal_days, signal_days[1:]):
            current = rankings[current_day]
            symbols = [str(x) for x in current["symbols"]]
            entry_day = _next_session(calendar, current_day)
            exit_day = _next_session(calendar, next_day)
            if entry_day is None or exit_day is None:
                missing_rows.append({"variant_id": variant_id, "signal_day": current_day.isoformat(), "reason": "REBALANCE_SESSION_MISSING"})
                continue
            missing = [symbol for symbol in symbols if stock_open.get((symbol, entry_day)) is None or stock_open.get((symbol, exit_day)) is None]
            if missing:
                missing_rows.append({
                    "variant_id": variant_id,
                    "signal_day": current_day.isoformat(),
                    "entry_day": entry_day.isoformat(),
                    "exit_day": exit_day.isoformat(),
                    "reason": "SELECTED_SYMBOL_OPEN_MISSING",
                    "symbols": ",".join(sorted(missing)),
                })
                continue
            if index_open.get(entry_day) is None or index_open.get(exit_day) is None:
                missing_rows.append({"variant_id": variant_id, "signal_day": current_day.isoformat(), "reason": "VNINDEX_OPEN_MISSING"})
                continue
            stock_returns = [stock_open[(symbol, exit_day)] / stock_open[(symbol, entry_day)] - 1.0 for symbol in symbols]
            portfolio_return = fmean(stock_returns)
            benchmark_return = index_open[exit_day] / index_open[entry_day] - 1.0
            risk_on = bool(current["risk_on"])
            regime_return = portfolio_return if risk_on else 0.0
            current_set = set(symbols)
            turnover = 1.0 if prior_symbols is None else 1.0 - len(current_set & prior_symbols) / max(1, len(current_set))
            turnover_values.append(turnover)
            prior_symbols = current_set
            if first_entry is None:
                first_entry = entry_day
            last_exit = exit_day
            complete_periods += 1

            for strategy, ret in ((ALWAYS, portfolio_return), (REGIME, regime_return), (BENCHMARK, benchmark_return)):
                strategy_equity[strategy] *= 1.0 + ret
                strategy_paths[strategy].append(strategy_equity[strategy])
                period_returns[strategy].append(ret)
                annual_acc[(variant_id, strategy, entry_day.year)] = annual_acc.get((variant_id, strategy, entry_day.year), 1.0) * (1.0 + ret)
                curve_rows.append({
                    "variant_id": variant_id,
                    "strategy": strategy,
                    "signal_day": current_day.isoformat(),
                    "entry_day": entry_day.isoformat(),
                    "exit_day": exit_day.isoformat(),
                    "risk_on": risk_on,
                    "selected_count": len(symbols),
                    "one_way_turnover": turnover if strategy != BENCHMARK else 0.0,
                    "period_return": ret,
                    "equity": strategy_equity[strategy],
                })

        for strategy in (ALWAYS, REGIME, BENCHMARK):
            total_return = strategy_equity[strategy] - 1.0
            summary_rows.append({
                "variant_id": variant_id,
                "strategy": strategy,
                "first_entry_day": first_entry.isoformat() if first_entry else None,
                "last_exit_day": last_exit.isoformat() if last_exit else None,
                "completed_period_count": complete_periods,
                "expected_period_count": total_periods,
                "complete_period_rate": complete_periods / total_periods if total_periods else 0.0,
                "total_return": total_return,
                "ending_equity_from_1": strategy_equity[strategy],
                "cagr": _cagr(1.0, strategy_equity[strategy], first_entry, last_exit) if first_entry and last_exit else None,
                "max_drawdown_period_level": _max_drawdown(strategy_paths[strategy]),
                "mean_period_return": fmean(period_returns[strategy]) if period_returns[strategy] else None,
                "positive_period_rate": sum(ret > 0 for ret in period_returns[strategy]) / len(period_returns[strategy]) if period_returns[strategy] else None,
                "mean_one_way_turnover": fmean(turnover_values) if strategy != BENCHMARK and turnover_values else 0.0,
                "costs_included": False,
                "fees_included": False,
                "sell_tax_included": False,
                "slippage_included": False,
                "lot_size_included": False,
                "sector_caps_included": False,
            })

    annual_rows = [
        {"variant_id": variant, "strategy": strategy, "year": year, "annual_return": wealth - 1.0}
        for (variant, strategy, year), wealth in sorted(annual_acc.items())
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v69_portfolio_equity_curve.csv", curve_rows)
    _write_csv(output_dir / "v69_portfolio_annual_returns.csv", annual_rows)
    _write_csv(output_dir / "v69_portfolio_profit_summary.csv", summary_rows)
    _write_csv(output_dir / "v69_portfolio_missing_prices.csv", missing_rows)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if not missing_rows else "SUCCESS_WITH_MISSING_PRICE_PERIODS",
        "champion_model": CHAMPION_MODEL,
        "portfolio_contract": "MONTHLY_C3_TOP10_EQUAL_WEIGHT_NEXT_OPEN_TO_NEXT_REBALANCE_OPEN",
        "strategies": [ALWAYS, REGIME, BENCHMARK],
        "gross_only": True,
        "costs_included": False,
        "missing_price_period_count": len(missing_rows),
        "summary": summary_rows,
        "limitations": [
            "This is a gross C3 ranking-portfolio report, not the final allocation/backtest engine.",
            "Fees, sell tax, slippage, lot size, sector caps and position caps are excluded.",
            "Price-basis and point-in-time HOSE lineage gates remain separate from this diagnostic profit report.",
            "The final monthly signal has no next rebalance and is intentionally not compounded into completed-period performance.",
        ],
        "research_only": True,
        "promotion_authorized": False,
    }
    (output_dir / "v69_profit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = analyze(v68_output=args.v68_output, store=args.store, output_dir=args.output_dir)
    print(json.dumps({
        "schema_version": report["schema_version"],
        "status": report["status"],
        "missing_price_period_count": report["missing_price_period_count"],
        "gross_only": report["gross_only"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
