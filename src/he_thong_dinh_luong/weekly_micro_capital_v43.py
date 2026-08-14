"""V43 weekly micro-capital accumulation research protocol.

The module keeps the frozen C3 monthly ranking model and evaluates small,
recurring weekly contributions with odd-lot purchases. It is research-only:
no broker API, no live order generation, and no live-capital approval.
"""
from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import sqlite3
from statistics import fmean, median
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

SCHEMA_VERSION = "weekly_micro_capital_v43"
MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
COMPONENTS = ("low_volatility", "relative_strength_120", "high_52_week")
CONTRIBUTIONS = (200_000, 250_000, 300_000)
PRICE_MULTIPLIER = 1000.0

POLICIES: Mapping[str, Mapping[str, object]] = {
    "P1_TOP10_UNDERWEIGHT_BUFFER20": {
        "target_count": 10,
        "exit_rank": 20,
        "exit_months": 2,
        "buy_rule": "UNDERWEIGHT",
        "risk_off_fraction": 1.0,
        "risk_on_release_multiple": 1.0,
        "symbol_cap": 0.15,
    },
    "P2_TOP5_UNDERWEIGHT_BUFFER15": {
        "target_count": 5,
        "exit_rank": 15,
        "exit_months": 2,
        "buy_rule": "UNDERWEIGHT",
        "risk_off_fraction": 1.0,
        "risk_on_release_multiple": 1.0,
        "symbol_cap": 0.25,
    },
    "P3_TOP10_HIGHEST_RANK_IMMEDIATE_EXIT": {
        "target_count": 10,
        "exit_rank": 10,
        "exit_months": 1,
        "buy_rule": "HIGHEST_RANK",
        "risk_off_fraction": 1.0,
        "risk_on_release_multiple": 1.0,
        "symbol_cap": 0.15,
    },
    "P4_TOP10_ROUND_ROBIN_BUFFER20": {
        "target_count": 10,
        "exit_rank": 20,
        "exit_months": 2,
        "buy_rule": "ROUND_ROBIN",
        "risk_off_fraction": 1.0,
        "risk_on_release_multiple": 1.0,
        "symbol_cap": 0.15,
    },
    "P5_TOP10_UNDERWEIGHT_IMMEDIATE_EXIT": {
        "target_count": 10,
        "exit_rank": 10,
        "exit_months": 1,
        "buy_rule": "UNDERWEIGHT",
        "risk_off_fraction": 1.0,
        "risk_on_release_multiple": 1.0,
        "symbol_cap": 0.15,
    },
    "P6_TOP10_UNDERWEIGHT_BUFFER20_RISK_HALF": {
        "target_count": 10,
        "exit_rank": 20,
        "exit_months": 2,
        "buy_rule": "UNDERWEIGHT",
        "risk_off_fraction": 0.5,
        "risk_on_release_multiple": 3.0,
        "symbol_cap": 0.15,
    },
}

SCENARIOS: Mapping[str, Mapping[str, float]] = {
    "BASE": {"slippage_bps": 20.0},
    "STRESS": {"slippage_bps": 50.0},
    "SEVERE": {"slippage_bps": 100.0},
}

BROKER_FEE_BPS = 15.0
EXCHANGE_FEE_BPS = 2.7
SELL_TAX_BPS = 10.0
TRANSFER_FEE_PER_SHARE = 0.3


@dataclass(frozen=True)
class ResearchRow:
    signal_day: date
    label_end: date
    symbol: str
    relative_return: float
    volatility_60: float
    risk_on: bool
    components: Mapping[str, float]


@dataclass(frozen=True)
class SignalSnapshot:
    day: date
    ranking: tuple[str, ...]
    weights: Mapping[str, float]
    volatility: Mapping[str, float]
    risk_on: bool


@dataclass
class PriceStore:
    opens: dict[tuple[str, date], float]
    closes: dict[tuple[str, date], float]
    history_days: dict[str, list[date]]
    history_closes: dict[str, list[float]]
    index_open: dict[date, float]
    index_close: dict[date, float]
    calendar: list[date]

    def latest_close(self, symbol: str, day: date) -> float | None:
        days = self.history_days.get(symbol)
        closes = self.history_closes.get(symbol)
        if not days or not closes:
            return None
        position = bisect.bisect_right(days, day) - 1
        return closes[position] if position >= 0 else None


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _finite(value: object, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V43_NON_FINITE:{name}")
    return number


def average_percentile(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(
        range(len(values)),
        key=lambda index: (float(values[index]), index),
    )
    denominator = max(len(values) - 1, 1)
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while (
            end < len(order)
            and float(values[order[end]]) == float(values[order[start]])
        ):
            end += 1
        percentile = ((start + end - 1) / 2.0) / denominator
        for position in range(start, end):
            result[order[position]] = percentile
        start = end
    return result


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        return 0.0
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0.0 else 0.0


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _pearson(average_percentile(left), average_percentile(right))


def _monthly_component_ics(
    rows: Sequence[ResearchRow],
) -> dict[str, list[float]]:
    by_day: dict[date, list[ResearchRow]] = {}
    for row in rows:
        by_day.setdefault(row.signal_day, []).append(row)
    result = {name: [] for name in COMPONENTS}
    for day_rows in by_day.values():
        if len(day_rows) < 5:
            continue
        returns = [row.relative_return for row in day_rows]
        for name in COMPONENTS:
            result[name].append(
                _spearman(
                    [row.components[name] for row in day_rows],
                    returns,
                )
            )
    return result


def shrunk_component_weights(
    rows: Sequence[ResearchRow],
    *,
    shrinkage_to_equal: float = 0.50,
    max_component_weight: float = 0.50,
) -> dict[str, float]:
    history = _monthly_component_ics(rows)
    means = {
        name: fmean(history[name]) if history[name] else 0.0
        for name in COMPONENTS
    }
    positive = {name: max(value, 0.0) for name, value in means.items()}
    positive_total = sum(positive.values())
    empirical = (
        {
            name: positive[name] / positive_total
            for name in COMPONENTS
        }
        if positive_total > 0.0
        else {name: 1.0 / len(COMPONENTS) for name in COMPONENTS}
    )
    equal = 1.0 / len(COMPONENTS)
    raw = {
        name: (
            shrinkage_to_equal * equal
            + (1.0 - shrinkage_to_equal) * empirical[name]
        )
        for name in COMPONENTS
    }
    capped = {
        name: min(value, max_component_weight)
        for name, value in raw.items()
    }
    total = sum(capped.values())
    return {name: capped[name] / total for name in COMPONENTS}


def _load_research_rows(
    path: Path,
) -> tuple[list[ResearchRow], dict[str, object]]:
    source = Path(path)
    if not source.is_file():
        raise ValueError("V43_INPUT_ZIP_NOT_FOUND")
    with ZipFile(source) as archive:
        required = {"feature_raw.csv", "nhan.csv", "manifest.json"}
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError(
                "V43_INPUT_FILES_MISSING:" + "|".join(sorted(missing))
            )
        manifest = json.loads(
            archive.read("manifest.json").decode("utf-8-sig")
        )
        with archive.open("nhan.csv") as raw:
            labels = {
                (
                    str(row.get("ngay") or ""),
                    str(row.get("ma") or "").upper(),
                ): row
                for row in csv.DictReader(
                    io.TextIOWrapper(
                        raw,
                        encoding="utf-8-sig",
                        newline="",
                    )
                )
            }
        rows: list[ResearchRow] = []
        with archive.open("feature_raw.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    newline="",
                )
            )
            for feature in reader:
                if not _truthy(feature.get("hop_le")):
                    continue
                if not _truthy(feature.get("eligible")):
                    continue
                key = (
                    str(feature.get("ngay") or ""),
                    str(feature.get("ma") or "").upper(),
                )
                label = labels.get(key)
                if label is None:
                    continue
                try:
                    signal_day = date.fromisoformat(key[0])
                    label_end = date.fromisoformat(
                        str(label.get("ngay_ket_thuc_nhan") or "")
                    )
                    relative_return = _finite(
                        label.get("loi_nhuan_tuong_doi"),
                        name="loi_nhuan_tuong_doi",
                    )
                    volatility = max(
                        abs(
                            _finite(
                                feature.get("bien_dong_60"),
                                name="bien_dong_60",
                            )
                        ),
                        1e-8,
                    )
                    rows.append(
                        ResearchRow(
                            signal_day=signal_day,
                            label_end=label_end,
                            symbol=key[1],
                            relative_return=relative_return,
                            volatility_60=volatility,
                            risk_on=_truthy(
                                feature.get("vnindex_tren_ma250")
                            ),
                            components={
                                "low_volatility": -volatility,
                                "relative_strength_120": _finite(
                                    feature.get("suc_manh_tuong_doi_120"),
                                    name="suc_manh_tuong_doi_120",
                                ),
                                "high_52_week": _finite(
                                    feature.get("ty_le_dinh_52_tuan"),
                                    name="ty_le_dinh_52_tuan",
                                ),
                            },
                        )
                    )
                except (TypeError, ValueError):
                    continue
    rows.sort(key=lambda row: (row.signal_day, row.symbol))
    if not rows:
        raise ValueError("V43_NO_USABLE_RESEARCH_ROWS")
    return rows, dict(manifest)


def build_signal_snapshots(
    rows: Sequence[ResearchRow],
    *,
    minimum_history_months: int = 12,
) -> tuple[
    list[SignalSnapshot],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    by_day: dict[date, list[ResearchRow]] = {}
    for row in rows:
        by_day.setdefault(row.signal_day, []).append(row)
    dates = sorted(by_day)
    snapshots: list[SignalSnapshot] = []
    ranking_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    for signal_day in dates:
        history = [
            row
            for row in rows
            if row.signal_day < signal_day and row.label_end < signal_day
        ]
        history_months = len({row.signal_day for row in history})
        if history_months < minimum_history_months:
            continue
        current = by_day[signal_day]
        weights = shrunk_component_weights(history)
        ranked_components: dict[str, list[float]] = {}
        for name in COMPONENTS:
            ranked_components[name] = average_percentile(
                [row.components[name] for row in current]
            )
        scored: list[tuple[str, float, float]] = []
        for index, row in enumerate(current):
            score = sum(
                weights[name] * ranked_components[name][index]
                for name in COMPONENTS
            )
            scored.append((row.symbol, score, row.volatility_60))
        scored.sort(key=lambda item: (-item[1], item[0]))
        ranking = tuple(item[0] for item in scored)
        risk_on = median(
            [1.0 if row.risk_on else 0.0 for row in current]
        ) >= 0.5
        snapshots.append(
            SignalSnapshot(
                day=signal_day,
                ranking=ranking,
                weights=dict(weights),
                volatility={
                    symbol: volatility
                    for symbol, _, volatility in scored
                },
                risk_on=risk_on,
            )
        )
        for rank, (symbol, score, volatility) in enumerate(
            scored,
            start=1,
        ):
            ranking_rows.append(
                {
                    "signal_day": signal_day.isoformat(),
                    "symbol": symbol,
                    "rank": rank,
                    "score": score,
                    "volatility_60": volatility,
                    "risk_on": str(risk_on).lower(),
                }
            )
        weight_rows.append(
            {
                "signal_day": signal_day.isoformat(),
                "history_months": history_months,
                "weight_low_volatility": weights["low_volatility"],
                "weight_relative_strength_120": weights[
                    "relative_strength_120"
                ],
                "weight_high_52_week": weights["high_52_week"],
                "uses_only_completed_past_labels": "true",
            }
        )
    if not snapshots:
        raise ValueError("V43_NO_SIGNAL_SNAPSHOTS")
    return snapshots, ranking_rows, weight_rows


def _load_prices(
    path: Path,
    *,
    price_multiplier: float,
) -> PriceStore:
    db = sqlite3.connect(Path(path))
    db.row_factory = sqlite3.Row
    try:
        stock_rows = db.execute(
            """
            SELECT symbol,day,open,close
            FROM bars
            WHERE upper(asset_type)='STOCK'
            ORDER BY symbol,day
            """
        ).fetchall()
        index_rows = db.execute(
            """
            SELECT day,open,close
            FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
            ORDER BY day
            """
        ).fetchall()
    finally:
        db.close()
    if not stock_rows or not index_rows:
        raise ValueError("V43_STORE_REQUIRES_STOCKS_AND_VNINDEX")
    opens: dict[tuple[str, date], float] = {}
    closes: dict[tuple[str, date], float] = {}
    history_days: dict[str, list[date]] = {}
    history_closes: dict[str, list[float]] = {}
    for row in stock_rows:
        symbol = str(row["symbol"]).upper()
        day = date.fromisoformat(str(row["day"]))
        open_price = float(row["open"]) * price_multiplier
        close_price = float(row["close"]) * price_multiplier
        opens[(symbol, day)] = open_price
        closes[(symbol, day)] = close_price
        history_days.setdefault(symbol, []).append(day)
        history_closes.setdefault(symbol, []).append(close_price)
    index_open: dict[date, float] = {}
    index_close: dict[date, float] = {}
    for row in index_rows:
        day = date.fromisoformat(str(row["day"]))
        index_open[day] = float(row["open"])
        index_close[day] = float(row["close"])
    calendar = sorted(index_open)
    return PriceStore(
        opens,
        closes,
        history_days,
        history_closes,
        index_open,
        index_close,
        calendar,
    )


def _weekly_days(
    calendar: Sequence[date],
    *,
    start: date,
    end: date,
) -> list[date]:
    by_week: dict[tuple[int, int], date] = {}
    for day in calendar:
        if day < start or day > end:
            continue
        iso = day.isocalendar()
        by_week.setdefault((iso.year, iso.week), day)
    return [by_week[key] for key in sorted(by_week)]


def capped_inverse_vol_weights(
    ranking: Sequence[str],
    volatility: Mapping[str, float],
    *,
    target_count: int,
    symbol_cap: float,
) -> dict[str, float]:
    selected = [
        symbol
        for symbol in ranking[:target_count]
        if symbol in volatility
    ]
    if not selected:
        return {}
    raw = {
        symbol: 1.0 / max(float(volatility[symbol]), 1e-8)
        for symbol in selected
    }
    remaining = set(selected)
    weights = {symbol: 0.0 for symbol in selected}
    remaining_weight = 1.0
    while remaining and remaining_weight > 1e-12:
        raw_total = sum(raw[symbol] for symbol in remaining)
        if raw_total <= 0.0:
            share = remaining_weight / len(remaining)
            for symbol in remaining:
                weights[symbol] += share
            break
        capped_any = False
        for symbol in list(remaining):
            proposed = remaining_weight * raw[symbol] / raw_total
            available = symbol_cap - weights[symbol]
            if proposed >= available - 1e-12:
                weights[symbol] += max(available, 0.0)
                remaining_weight -= max(available, 0.0)
                remaining.remove(symbol)
                capped_any = True
        if not capped_any:
            for symbol in remaining:
                weights[symbol] += (
                    remaining_weight * raw[symbol] / raw_total
                )
            remaining_weight = 0.0
    total = sum(weights.values())
    if total > 1.0 + 1e-8:
        weights = {
            symbol: value / total
            for symbol, value in weights.items()
        }
    return weights


def compute_exit_symbols(
    holdings: Mapping[str, int],
    rank_by_symbol: Mapping[str, int],
    outside_counts: dict[str, int],
    *,
    exit_rank: int,
    exit_months: int,
) -> list[str]:
    exits: list[str] = []
    for symbol, quantity in holdings.items():
        if quantity <= 0:
            continue
        rank = int(rank_by_symbol.get(symbol, 10**9))
        outside_counts[symbol] = (
            outside_counts.get(symbol, 0) + 1
            if rank > exit_rank
            else 0
        )
        if outside_counts[symbol] >= exit_months:
            exits.append(symbol)
    return sorted(exits)


def _account_value(
    cash: float,
    holdings: Mapping[str, int],
    prices: PriceStore,
    day: date,
    *,
    use_open: bool,
) -> tuple[float, int]:
    value = cash
    stale_count = 0
    for symbol, quantity in holdings.items():
        if quantity <= 0:
            continue
        direct = (
            prices.opens.get((symbol, day))
            if use_open
            else prices.closes.get((symbol, day))
        )
        price = (
            direct
            if direct is not None
            else prices.latest_close(symbol, day)
        )
        if price is None:
            stale_count += 1
            continue
        if direct is None:
            stale_count += 1
        value += quantity * price
    return value, stale_count


def _buy_total(
    price: float,
    quantity: int,
    slippage_bps: float,
) -> float:
    execution = price * (1.0 + slippage_bps / 10_000.0)
    fees = (
        execution
        * quantity
        * (BROKER_FEE_BPS + EXCHANGE_FEE_BPS)
        / 10_000.0
    )
    return execution * quantity + fees


def _sell_proceeds(
    price: float,
    quantity: int,
    slippage_bps: float,
) -> float:
    execution = price * (1.0 - slippage_bps / 10_000.0)
    gross = execution * quantity
    rate_cost = (
        gross
        * (BROKER_FEE_BPS + EXCHANGE_FEE_BPS + SELL_TAX_BPS)
        / 10_000.0
    )
    transfer = quantity * TRANSFER_FEE_PER_SHARE
    return gross - rate_cost - transfer


def affordable_quantity(
    budget: float,
    price: float,
    slippage_bps: float,
) -> int:
    if budget <= 0.0 or price <= 0.0:
        return 0
    per_share = _buy_total(price, 1, slippage_bps)
    return max(int(budget // per_share), 0)


def _choose_buy_symbol(
    *,
    rule: str,
    target_symbols: Sequence[str],
    target_weights: Mapping[str, float],
    holdings: Mapping[str, int],
    prices: PriceStore,
    day: date,
    account_value: float,
    budget: float,
    slippage_bps: float,
    round_robin_pointer: int,
) -> tuple[str | None, int]:
    candidates = [
        symbol
        for symbol in target_symbols
        if prices.opens.get((symbol, day))
    ]
    affordable = [
        symbol
        for symbol in candidates
        if affordable_quantity(
            budget,
            float(prices.opens[(symbol, day)]),
            slippage_bps,
        )
        >= 1
    ]
    if not affordable:
        return None, round_robin_pointer
    if rule == "HIGHEST_RANK":
        return affordable[0], round_robin_pointer
    if rule == "ROUND_ROBIN":
        if not target_symbols:
            return None, round_robin_pointer
        for offset in range(len(target_symbols)):
            index = (
                round_robin_pointer + offset
            ) % len(target_symbols)
            symbol = target_symbols[index]
            if symbol in affordable:
                return symbol, (index + 1) % len(target_symbols)
        return None, round_robin_pointer
    gaps: list[tuple[float, int, str]] = []
    for rank, symbol in enumerate(target_symbols):
        price = (
            prices.latest_close(symbol, day)
            or prices.opens.get((symbol, day))
        )
        actual = holdings.get(symbol, 0) * float(price or 0.0)
        target = float(target_weights.get(symbol, 0.0)) * account_value
        gaps.append((target - actual, -rank, symbol))
    gaps.sort(reverse=True)
    for _, _, symbol in gaps:
        if symbol in affordable:
            return symbol, round_robin_pointer
    return affordable[0], round_robin_pointer


def xirr(
    cashflows: Sequence[tuple[date, float]],
) -> float | None:
    if not cashflows:
        return None
    if not any(value < 0 for _, value in cashflows):
        return None
    if not any(value > 0 for _, value in cashflows):
        return None
    ordered = sorted(cashflows)
    start = ordered[0][0]

    def npv(rate: float) -> float:
        return sum(
            value
            / ((1.0 + rate) ** ((day - start).days / 365.25))
            for day, value in ordered
        )

    low = -0.9999
    high = 1.0
    low_value = npv(low)
    high_value = npv(high)
    while low_value * high_value > 0.0 and high < 1024.0:
        high *= 2.0
        high_value = npv(high)
    if low_value * high_value > 0.0:
        return None
    for _ in range(200):
        middle = (low + high) / 2.0
        value = npv(middle)
        if abs(value) < 1e-9:
            return middle
        if low_value * value <= 0.0:
            high = middle
        else:
            low = middle
            low_value = value
    return (low + high) / 2.0


def _simulate(
    *,
    policy_id: str,
    contribution: int,
    scenario: str,
    snapshots: Sequence[SignalSnapshot],
    prices: PriceStore,
    weekly_days: Sequence[date],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    policy = POLICIES[policy_id]
    slippage_bps = float(SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    cash = 0.0
    holdings: dict[str, int] = {}
    outside_counts: dict[str, int] = {}
    current_signal_index = -1
    current_snapshot: SignalSnapshot | None = None
    round_robin_pointer = 0
    fund_units = 0.0
    unit_price = 1.0
    peak_unit_price = 1.0
    max_drawdown = 0.0
    contributions_total = 0.0
    fees_total = 0.0
    buy_count = 0
    sell_count = 0
    missing_trade_bar_count = 0
    stale_valuation_count = 0
    cashflows: list[tuple[date, float]] = []
    weekly_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []

    for week_number, trade_day in enumerate(weekly_days, start=1):
        snapshot_index = bisect.bisect_left(
            signal_days,
            trade_day,
        ) - 1
        if snapshot_index < 0:
            continue
        signal_changed = snapshot_index != current_signal_index
        if signal_changed:
            current_signal_index = snapshot_index
            current_snapshot = snapshots[snapshot_index]
        assert current_snapshot is not None

        value_before, stale_before = _account_value(
            cash,
            holdings,
            prices,
            trade_day,
            use_open=True,
        )
        stale_valuation_count += stale_before
        if fund_units > 0.0:
            unit_price = value_before / fund_units
        issued_units = contribution / max(unit_price, 1e-12)
        fund_units += issued_units
        cash += contribution
        contributions_total += contribution
        cashflows.append((trade_day, -float(contribution)))

        index_open = prices.index_open.get(trade_day)
        if index_open and index_open > 0.0:
            benchmark_units += contribution / index_open
            benchmark_cashflows.append(
                (trade_day, -float(contribution))
            )

        sell_symbols: list[str] = []
        if signal_changed:
            rank_by_symbol = {
                symbol: rank
                for rank, symbol in enumerate(
                    current_snapshot.ranking,
                    start=1,
                )
            }
            sell_symbols = compute_exit_symbols(
                holdings,
                rank_by_symbol,
                outside_counts,
                exit_rank=int(policy["exit_rank"]),
                exit_months=int(policy["exit_months"]),
            )
        for symbol in sell_symbols:
            quantity = holdings.get(symbol, 0)
            if quantity <= 0:
                continue
            raw_price = prices.opens.get((symbol, trade_day))
            if raw_price is None:
                missing_trade_bar_count += 1
                trade_rows.append(
                    {
                        "policy": policy_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        "trade_day": trade_day.isoformat(),
                        "side": "SELL_SKIPPED_MISSING_BAR",
                        "symbol": symbol,
                        "quantity": quantity,
                        "gross_reference_vnd": "",
                        "cash_effect_vnd": 0.0,
                    }
                )
                continue
            proceeds = _sell_proceeds(
                raw_price,
                quantity,
                slippage_bps,
            )
            gross = raw_price * quantity
            fees_total += gross - proceeds
            cash += proceeds
            holdings[symbol] = 0
            outside_counts[symbol] = 0
            sell_count += 1
            trade_rows.append(
                {
                    "policy": policy_id,
                    "contribution": contribution,
                    "scenario": scenario,
                    "trade_day": trade_day.isoformat(),
                    "side": "SELL",
                    "symbol": symbol,
                    "quantity": quantity,
                    "gross_reference_vnd": gross,
                    "cash_effect_vnd": proceeds,
                }
            )

        target_count = int(policy["target_count"])
        target_symbols = list(
            current_snapshot.ranking[:target_count]
        )
        target_weights = capped_inverse_vol_weights(
            current_snapshot.ranking,
            current_snapshot.volatility,
            target_count=target_count,
            symbol_cap=float(policy["symbol_cap"]),
        )
        if current_snapshot.risk_on:
            weekly_budget = min(
                cash,
                contribution
                * float(policy["risk_on_release_multiple"]),
            )
        else:
            weekly_budget = min(
                cash,
                contribution * float(policy["risk_off_fraction"]),
            )
        account_value_open, _ = _account_value(
            cash,
            holdings,
            prices,
            trade_day,
            use_open=True,
        )
        buy_symbol, round_robin_pointer = _choose_buy_symbol(
            rule=str(policy["buy_rule"]),
            target_symbols=target_symbols,
            target_weights=target_weights,
            holdings=holdings,
            prices=prices,
            day=trade_day,
            account_value=account_value_open,
            budget=weekly_budget,
            slippage_bps=slippage_bps,
            round_robin_pointer=round_robin_pointer,
        )
        buy_quantity = 0
        if buy_symbol is not None:
            raw_price = float(prices.opens[(buy_symbol, trade_day)])
            buy_quantity = affordable_quantity(
                weekly_budget,
                raw_price,
                slippage_bps,
            )
            total_cost = _buy_total(
                raw_price,
                buy_quantity,
                slippage_bps,
            )
            while buy_quantity > 0 and total_cost > cash + 1e-8:
                buy_quantity -= 1
                total_cost = _buy_total(
                    raw_price,
                    buy_quantity,
                    slippage_bps,
                )
            if buy_quantity > 0:
                gross = raw_price * buy_quantity
                fees_total += total_cost - gross
                cash -= total_cost
                holdings[buy_symbol] = (
                    holdings.get(buy_symbol, 0) + buy_quantity
                )
                buy_count += 1
                trade_rows.append(
                    {
                        "policy": policy_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        "trade_day": trade_day.isoformat(),
                        "side": "BUY",
                        "symbol": buy_symbol,
                        "quantity": buy_quantity,
                        "gross_reference_vnd": gross,
                        "cash_effect_vnd": -total_cost,
                    }
                )

        end_value, stale_end = _account_value(
            cash,
            holdings,
            prices,
            trade_day,
            use_open=False,
        )
        stale_valuation_count += stale_end
        unit_price = (
            end_value / fund_units
            if fund_units > 0.0
            else 1.0
        )
        peak_unit_price = max(peak_unit_price, unit_price)
        drawdown = unit_price / peak_unit_price - 1.0
        max_drawdown = min(max_drawdown, drawdown)
        live_positions = {
            symbol: quantity
            for symbol, quantity in holdings.items()
            if quantity > 0
        }
        largest_weight = 0.0
        for symbol, quantity in live_positions.items():
            mark = prices.latest_close(symbol, trade_day)
            if mark is not None and end_value > 0.0:
                largest_weight = max(
                    largest_weight,
                    quantity * mark / end_value,
                )
        weekly_rows.append(
            {
                "policy": policy_id,
                "contribution": contribution,
                "scenario": scenario,
                "week_number": week_number,
                "trade_day": trade_day.isoformat(),
                "signal_day": current_snapshot.day.isoformat(),
                "risk_on": str(current_snapshot.risk_on).lower(),
                "weekly_contribution_vnd": contribution,
                "buy_budget_vnd": weekly_budget,
                "buy_symbol": buy_symbol or "",
                "buy_quantity": buy_quantity,
                "cash_vnd": cash,
                "portfolio_value_vnd": end_value,
                "unit_price": unit_price,
                "drawdown": drawdown,
                "position_count": len(live_positions),
                "largest_symbol_weight": largest_weight,
                "stale_valuation_count": stale_end,
            }
        )

    if not weekly_rows:
        raise ValueError("V43_NO_WEEKLY_SIMULATION_ROWS")
    final_day = date.fromisoformat(
        str(weekly_rows[-1]["trade_day"])
    )
    final_value = float(weekly_rows[-1]["portfolio_value_vnd"])
    cashflows.append((final_day, final_value))
    index_close = prices.index_close.get(final_day)
    benchmark_final = (
        benchmark_units * index_close
        if index_close
        else 0.0
    )
    benchmark_cashflows.append((final_day, benchmark_final))
    live_positions = {
        symbol: quantity
        for symbol, quantity in holdings.items()
        if quantity > 0
    }
    largest_weight = (
        max(
            (
                quantity
                * float(prices.latest_close(symbol, final_day) or 0.0)
                / final_value
                for symbol, quantity in live_positions.items()
            ),
            default=0.0,
        )
        if final_value > 0.0
        else 0.0
    )
    portfolio_xirr = xirr(cashflows)
    benchmark_xirr = xirr(benchmark_cashflows)
    summary = {
        "policy": policy_id,
        "contribution": contribution,
        "scenario": scenario,
        "week_count": len(weekly_rows),
        "total_contributed_vnd": contributions_total,
        "final_value_vnd": final_value,
        "absolute_profit_vnd": final_value - contributions_total,
        "xirr": portfolio_xirr,
        "benchmark_final_value_vnd": benchmark_final,
        "benchmark_xirr": benchmark_xirr,
        "xirr_excess": (
            portfolio_xirr - benchmark_xirr
            if portfolio_xirr is not None
            and benchmark_xirr is not None
            else None
        ),
        "unitized_total_return": unit_price - 1.0,
        "max_drawdown": max_drawdown,
        "ending_cash_vnd": cash,
        "ending_cash_ratio": (
            cash / final_value
            if final_value > 0.0
            else 0.0
        ),
        "position_count": len(live_positions),
        "largest_symbol_weight": largest_weight,
        "buy_order_count": buy_count,
        "sell_order_count": sell_count,
        "estimated_total_cost_vnd": fees_total,
        "missing_trade_bar_count": missing_trade_bar_count,
        "stale_valuation_count": stale_valuation_count,
        "odd_lot_share_unit": 1,
        "live_capital_approved": False,
    }
    return summary, weekly_rows, trade_rows


def _csv_bytes(
    rows: Sequence[Mapping[str, object]],
) -> bytes:
    if not rows:
        return b""
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {field: row.get(field, "") for field in fields}
        )
    return output.getvalue().encode("utf-8-sig")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def run_v43(
    *,
    input_zip: Path,
    store_path: Path,
    output_dir: Path,
    output_zip: Path,
    contributions: Sequence[int] = CONTRIBUTIONS,
    price_multiplier: float = PRICE_MULTIPLIER,
) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(f"V43_OUTPUT_EXISTS:{output_dir}")
    rows, input_manifest = _load_research_rows(input_zip)
    snapshots, ranking_rows, weight_rows = build_signal_snapshots(rows)
    prices = _load_prices(
        store_path,
        price_multiplier=price_multiplier,
    )
    start = snapshots[0].day
    end = min(snapshots[-1].day, prices.calendar[-1])
    weekly_days = _weekly_days(
        prices.calendar,
        start=start,
        end=end,
    )
    summaries: list[dict[str, object]] = []
    weekly_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    for contribution in sorted(
        set(int(value) for value in contributions)
    ):
        if contribution <= 0:
            raise ValueError("V43_CONTRIBUTION_MUST_BE_POSITIVE")
        for scenario in SCENARIOS:
            for policy_id in POLICIES:
                summary, weekly, trades = _simulate(
                    policy_id=policy_id,
                    contribution=contribution,
                    scenario=scenario,
                    snapshots=snapshots,
                    prices=prices,
                    weekly_days=weekly_days,
                )
                summaries.append(summary)
                weekly_rows.extend(weekly)
                trade_rows.extend(trades)
    primary = [
        row
        for row in summaries
        if int(row["contribution"]) == 250_000
        and str(row["scenario"]) == "BASE"
    ]
    best_xirr = max(
        primary,
        key=lambda row: float(row.get("xirr") or -999.0),
    )
    balanced = max(
        primary,
        key=lambda row: (
            float(row.get("xirr_excess") or -999.0)
            - 0.50 * abs(float(row.get("max_drawdown") or 0.0))
            - 0.10 * float(row.get("ending_cash_ratio") or 0.0)
        ),
    )
    contract = {
        "schema_version": SCHEMA_VERSION,
        "model": MODEL,
        "ranking_frequency": "MONTHLY",
        "contribution_frequency": (
            "FIRST_VNINDEX_TRADING_DAY_OF_ISO_WEEK"
        ),
        "weekly_contributions_vnd": sorted(
            set(int(value) for value in contributions)
        ),
        "maximum_buy_orders_per_week": 1,
        "odd_lot_share_unit": 1,
        "sell_policy_evaluated_on_new_monthly_signal": True,
        "costs": {
            "broker_fee_bps_each_side": BROKER_FEE_BPS,
            "exchange_fee_bps_each_side": EXCHANGE_FEE_BPS,
            "sell_tax_bps": SELL_TAX_BPS,
            "transfer_fee_vnd_per_share": TRANSFER_FEE_PER_SHARE,
            "slippage_scenarios_bps_each_side": {
                name: values["slippage_bps"]
                for name, values in SCENARIOS.items()
            },
        },
        "policies": POLICIES,
        "permissions": {
            "research_only": True,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        },
        "limitations": {
            "odd_lot_order_book_history_available": False,
            "broker_minimum_fee_modelled": False,
            "corporate_actions_complete": False,
            "point_in_time_universe_complete": False,
            "price_basis_confirmed": False,
        },
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "model": MODEL,
        "input_zip": str(input_zip.resolve()),
        "input_zip_sha256": sha256(
            input_zip.read_bytes()
        ).hexdigest(),
        "store_path": str(store_path.resolve()),
        "store_sha256": sha256(
            store_path.read_bytes()
        ).hexdigest(),
        "input_manifest_schema": input_manifest.get("schema_version"),
        "signal_snapshot_count": len(snapshots),
        "first_signal_day": snapshots[0].day.isoformat(),
        "last_signal_day": snapshots[-1].day.isoformat(),
        "weekly_trade_day_count": len(weekly_days),
        "simulation_count": len(summaries),
        "primary_comparison": {
            "contribution_vnd": 250_000,
            "scenario": "BASE",
            "highest_xirr_policy": best_xirr,
            "balanced_policy": balanced,
        },
        "summary_rows": summaries,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    files = {
        "weekly_micro_capital_summary_v43.csv": _csv_bytes(summaries),
        "weekly_micro_capital_ledger_v43.csv": _csv_bytes(weekly_rows),
        "weekly_micro_capital_trades_v43.csv": _csv_bytes(trade_rows),
        "monthly_c3_rankings_v43.csv": _csv_bytes(ranking_rows),
        "monthly_c3_weights_v43.csv": _csv_bytes(weight_rows),
        "weekly_micro_capital_contract_v43.json": _json_bytes(contract),
        "weekly_micro_capital_report_v43.json": _json_bytes(report),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "files": {
            name: {
                "sha256": _sha(payload),
                "size_bytes": len(payload),
            }
            for name, payload in sorted(files.items())
        },
    }
    files["manifest.json"] = _json_bytes(manifest)
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
            raise ValueError(f"V43_ZIP_CRC_FAILED:{bad}")
    return {
        "status": "SUCCESS",
        "output_dir": str(output_dir.resolve()),
        "output_zip": str(output_zip.resolve()),
        "output_zip_sha256": sha256(
            output_zip.read_bytes()
        ).hexdigest(),
        "simulation_count": len(summaries),
        "primary_highest_xirr_policy": best_xirr["policy"],
        "primary_balanced_policy": balanced["policy"],
        "live_capital_approved": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="V43 weekly micro-capital accumulation research"
    )
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument(
        "--contribution",
        type=int,
        action="append",
        dest="contributions",
    )
    parser.add_argument(
        "--price-multiplier",
        type=float,
        default=PRICE_MULTIPLIER,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_v43(
            input_zip=args.input_zip,
            store_path=args.store,
            output_dir=args.output_dir,
            output_zip=args.output_zip,
            contributions=args.contributions or CONTRIBUTIONS,
            price_multiplier=args.price_multiplier,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
