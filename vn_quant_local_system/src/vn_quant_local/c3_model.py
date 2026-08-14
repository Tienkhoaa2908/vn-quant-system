"""Frozen C3 monthly ranking model for the local workstation.

The implementation is a self-contained snapshot of the research contract used
in V27/V34/V41/V43:

* components: low volatility, relative strength 120, 52-week-high ratio;
* cross-sectional average percentiles with tie handling;
* adaptive component weights from completed past labels only;
* 50% shrinkage to equal weights and 50% maximum component weight;
* current eligibility: exact history, MA250 and a configurable ADV20 floor.

The canonical signal is monthly. A latest-day preview is also produced but is
explicitly marked non-canonical and is not used by the default weekly plan.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import sqlite3
from statistics import fmean
from typing import Mapping, Sequence
from zipfile import ZipFile

from .core import load_config, paths, state_db, utc_now

MODEL_ID = "C3_STABLE_3_PAST_IC_SHRUNK"
COMPONENTS = ("low_volatility", "relative_strength_120", "high_52_week")


@dataclass(frozen=True)
class HistoricalRow:
    signal_day: date
    label_end: date
    symbol: str
    relative_return: float
    low_volatility: float
    relative_strength_120: float
    high_52_week: float


@dataclass(frozen=True)
class CurrentFeature:
    signal_day: date
    symbol: str
    close_price: float
    volatility_60: float
    relative_strength_120: float
    high_52_week: float
    above_ma250: bool
    adv20_vnd: float
    zero_volume_60: int
    exact_history: bool
    eligible: bool


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _finite(value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite value")
    return number


def average_percentile(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: (float(values[index]), index))
    denominator = max(len(values) - 1, 1)
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and float(values[order[end]]) == float(values[order[start]]):
            end += 1
        percentile = ((start + end - 1) / 2.0) / denominator
        for position in range(start, end):
            result[order[position]] = percentile
        start = end
    return result


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        return 0.0
    lm = fmean(left)
    rm = fmean(right)
    numerator = sum((x - lm) * (y - rm) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - lm) ** 2 for x in left) * sum((y - rm) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0.0 else 0.0


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _pearson(average_percentile(left), average_percentile(right))


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("sample std requires >=2 observations")
    mean = fmean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def load_historical_rows(reference_zip: Path) -> tuple[list[HistoricalRow], set[str]]:
    with ZipFile(reference_zip) as archive:
        labels: dict[tuple[str, str], Mapping[str, str]] = {}
        with archive.open("nhan.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            for row in reader:
                key = (str(row.get("ngay") or ""), str(row.get("ma") or "").upper())
                labels[key] = row

        rows: list[HistoricalRow] = []
        latest_valid_day: date | None = None
        latest_symbols: set[str] = set()
        with archive.open("feature_raw.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            for feature in reader:
                if not _truthy(feature.get("hop_le")):
                    continue
                signal_raw = str(feature.get("ngay") or "")
                symbol = str(feature.get("ma") or "").upper()
                try:
                    signal_day = date.fromisoformat(signal_raw)
                except ValueError:
                    continue
                if latest_valid_day is None or signal_day > latest_valid_day:
                    latest_valid_day = signal_day
                    latest_symbols = {symbol}
                elif signal_day == latest_valid_day:
                    latest_symbols.add(symbol)

                if not _truthy(feature.get("eligible")):
                    continue
                label = labels.get((signal_raw, symbol))
                if label is None:
                    continue
                try:
                    rows.append(
                        HistoricalRow(
                            signal_day=signal_day,
                            label_end=date.fromisoformat(str(label.get("ngay_ket_thuc_nhan") or "")),
                            symbol=symbol,
                            relative_return=_finite(label.get("loi_nhuan_tuong_doi")),
                            low_volatility=-abs(_finite(feature.get("bien_dong_60"))),
                            relative_strength_120=_finite(feature.get("suc_manh_tuong_doi_120")),
                            high_52_week=_finite(feature.get("ty_le_dinh_52_tuan")),
                        )
                    )
                except (TypeError, ValueError):
                    continue
    rows.sort(key=lambda row: (row.signal_day, row.symbol))
    if not rows:
        raise ValueError("Reference ZIP không có historical rows dùng được")
    if not latest_symbols:
        latest_symbols = {row.symbol for row in rows}
    return rows, latest_symbols


def component_weights(rows: Sequence[HistoricalRow], *, before_day: date) -> dict[str, float]:
    eligible_history = [
        row for row in rows if row.signal_day < before_day and row.label_end < before_day
    ]
    by_day: dict[date, list[HistoricalRow]] = defaultdict(list)
    for row in eligible_history:
        by_day[row.signal_day].append(row)

    monthly_ics = {name: [] for name in COMPONENTS}
    for day_rows in by_day.values():
        if len(day_rows) < 5:
            continue
        returns = [row.relative_return for row in day_rows]
        values = {
            "low_volatility": [row.low_volatility for row in day_rows],
            "relative_strength_120": [row.relative_strength_120 for row in day_rows],
            "high_52_week": [row.high_52_week for row in day_rows],
        }
        for name in COMPONENTS:
            monthly_ics[name].append(_spearman(values[name], returns))

    means = {
        name: fmean(monthly_ics[name]) if monthly_ics[name] else 0.0
        for name in COMPONENTS
    }
    positive = {name: max(value, 0.0) for name, value in means.items()}
    total_positive = sum(positive.values())
    equal = 1.0 / len(COMPONENTS)
    empirical = (
        {name: positive[name] / total_positive for name in COMPONENTS}
        if total_positive > 0.0
        else {name: equal for name in COMPONENTS}
    )
    raw = {name: 0.5 * equal + 0.5 * empirical[name] for name in COMPONENTS}
    capped = {name: min(value, 0.5) for name, value in raw.items()}
    total = sum(capped.values())
    return {name: capped[name] / total for name in COMPONENTS}


def _market_rows(market_db: Path) -> tuple[list[date], dict[date, tuple[float, int]], dict[str, dict[date, tuple[float, int]]]]:
    db = sqlite3.connect(market_db)
    db.row_factory = sqlite3.Row
    try:
        index_rows = db.execute(
            """
            SELECT day,close,volume FROM bars
            WHERE upper(asset_type)='INDEX'
              AND upper(symbol) IN ('VNINDEX','VN-INDEX','VN_INDEX')
            ORDER BY day
            """
        ).fetchall()
        stock_rows = db.execute(
            """
            SELECT symbol,day,close,volume FROM bars
            WHERE upper(asset_type)='STOCK'
            ORDER BY symbol,day
            """
        ).fetchall()
    finally:
        db.close()
    if not index_rows or not stock_rows:
        raise ValueError("Market DB thiếu STOCK hoặc VNINDEX")
    index = {
        date.fromisoformat(str(row["day"])): (float(row["close"]), int(row["volume"]))
        for row in index_rows
    }
    stocks: dict[str, dict[date, tuple[float, int]]] = defaultdict(dict)
    for row in stock_rows:
        stocks[str(row["symbol"]).upper()][date.fromisoformat(str(row["day"]))] = (
            float(row["close"]), int(row["volume"])
        )
    return sorted(index), index, dict(stocks)


def _signal_days(calendar: Sequence[date]) -> tuple[date, date]:
    if not calendar:
        raise ValueError("Market calendar rỗng")
    latest = calendar[-1]
    months: dict[tuple[int, int], date] = {}
    for day in calendar:
        months[(day.year, day.month)] = day
    ordered = sorted(months)
    if len(ordered) < 2:
        raise ValueError("Cần ít nhất hai tháng dữ liệu")
    canonical = months[ordered[-2]]
    return canonical, latest


def _features_for_day(
    *,
    signal_day: date,
    calendar: Sequence[date],
    index: Mapping[date, tuple[float, int]],
    stocks: Mapping[str, Mapping[date, tuple[float, int]]],
    universe: set[str],
    price_multiplier: float,
    min_adv20_vnd: float,
    max_zero_volume_60: int,
) -> tuple[list[CurrentFeature], bool]:
    position = {day: i for i, day in enumerate(calendar)}.get(signal_day)
    if position is None or position < 250:
        raise ValueError(f"Không đủ 250 phiên tại {signal_day}")
    window_250 = calendar[position - 249 : position + 1]
    window_61 = calendar[position - 60 : position + 1]
    window_60 = calendar[position - 59 : position + 1]
    window_20 = calendar[position - 19 : position + 1]
    day_120 = calendar[position - 120]

    index_closes_250 = [index[day][0] for day in window_250]
    market_risk_on = index_closes_250[-1] >= fmean(index_closes_250)
    index_return_120 = index[signal_day][0] / index[day_120][0] - 1.0

    result: list[CurrentFeature] = []
    for symbol in sorted(universe):
        mapping = stocks.get(symbol, {})
        exact = all(day in mapping for day in set(window_250) | set(window_61) | {day_120})
        if not exact:
            continue
        closes_250 = [mapping[day][0] for day in window_250]
        closes_61 = [mapping[day][0] for day in window_61]
        returns_60 = [closes_61[i] / closes_61[i - 1] - 1.0 for i in range(1, len(closes_61))]
        volatility_60 = _sample_std(returns_60)
        close = mapping[signal_day][0]
        stock_return_120 = close / mapping[day_120][0] - 1.0
        rs120 = stock_return_120 - index_return_120
        high52 = close / max(closes_250)
        above = close >= fmean(closes_250)
        adv20 = fmean(
            mapping[day][0] * price_multiplier * mapping[day][1]
            for day in window_20
        )
        zero60 = sum(1 for day in window_60 if mapping[day][1] <= 0)
        eligible = above and adv20 >= min_adv20_vnd and zero60 <= max_zero_volume_60
        result.append(
            CurrentFeature(
                signal_day=signal_day,
                symbol=symbol,
                close_price=close * price_multiplier,
                volatility_60=volatility_60,
                relative_strength_120=rs120,
                high_52_week=high52,
                above_ma250=above,
                adv20_vnd=adv20,
                zero_volume_60=zero60,
                exact_history=True,
                eligible=eligible,
            )
        )
    if not result:
        raise ValueError(f"Không có feature rows tại {signal_day}")
    return result, market_risk_on


def rank_features(features: Sequence[CurrentFeature], weights: Mapping[str, float]) -> list[dict[str, object]]:
    eligible = [row for row in features if row.eligible]
    if not eligible:
        raise ValueError("Không có cổ phiếu eligible")
    low_pct = average_percentile([-row.volatility_60 for row in eligible])
    rs_pct = average_percentile([row.relative_strength_120 for row in eligible])
    high_pct = average_percentile([row.high_52_week for row in eligible])
    rows: list[dict[str, object]] = []
    for index, row in enumerate(eligible):
        score = (
            float(weights["low_volatility"]) * low_pct[index]
            + float(weights["relative_strength_120"]) * rs_pct[index]
            + float(weights["high_52_week"]) * high_pct[index]
        )
        rows.append(
            {
                "symbol": row.symbol,
                "score": score,
                "low_volatility_pct": low_pct[index],
                "relative_strength_120_pct": rs_pct[index],
                "high_52_week_pct": high_pct[index],
                "volatility_60": row.volatility_60,
                "close_price": row.close_price,
                "above_ma250": row.above_ma250,
                "eligible": row.eligible,
                "adv20_vnd": row.adv20_vnd,
                "zero_volume_60": row.zero_volume_60,
            }
        )
    rows.sort(key=lambda item: (-float(item["score"]), str(item["symbol"])))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_model() -> dict[str, object]:
    p = paths()
    if not p.market_db.is_file() or not p.reference_zip.is_file():
        raise FileNotFoundError("Chưa bootstrap data local")
    config = load_config()
    model_cfg = config.get("model", {})
    if not isinstance(model_cfg, Mapping):
        model_cfg = {}
    price_multiplier = float(model_cfg.get("price_multiplier", 1000.0))
    min_adv20 = float(model_cfg.get("min_adv20_vnd", 5_000_000_000.0))
    max_zero = int(model_cfg.get("max_zero_volume_60", 5))

    started = utc_now()
    run_id = "model-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    with state_db() as db:
        db.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?)",
            (run_id, "MODEL", started, None, "RUNNING", "{}"),
        )

    output_dir = p.outputs / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        historical, universe = load_historical_rows(p.reference_zip)
        calendar, index, stocks = _market_rows(p.market_db)
        canonical_day, preview_day = _signal_days(calendar)
        all_payloads: dict[str, object] = {}
        ranking_records: list[tuple[object, ...]] = []

        for signal_kind, signal_day in (
            ("MONTHLY_CANONICAL", canonical_day),
            ("LATEST_PREVIEW", preview_day),
        ):
            weights = component_weights(historical, before_day=signal_day)
            features, risk_on = _features_for_day(
                signal_day=signal_day,
                calendar=calendar,
                index=index,
                stocks=stocks,
                universe=universe,
                price_multiplier=price_multiplier,
                min_adv20_vnd=min_adv20,
                max_zero_volume_60=max_zero,
            )
            ranking = rank_features(features, weights)
            payload = {
                "schema_version": "vn_quant_local_c3_v1",
                "run_id": run_id,
                "model": MODEL_ID,
                "signal_kind": signal_kind,
                "signal_day": signal_day.isoformat(),
                "market_risk_on": risk_on,
                "component_weights": weights,
                "candidate_universe_count": len(universe),
                "feature_complete_count": len(features),
                "eligible_count": len(ranking),
                "ranking": ranking,
                "research_only": True,
                "live_capital_approved": False,
            }
            all_payloads[signal_kind] = payload
            (output_dir / f"ranking_{signal_kind.lower()}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_csv(output_dir / f"ranking_{signal_kind.lower()}.csv", ranking)
            for row in ranking:
                ranking_records.append(
                    (
                        run_id,
                        signal_day.isoformat(),
                        signal_kind,
                        int(row["rank"]),
                        str(row["symbol"]),
                        float(row["score"]),
                        float(row["low_volatility_pct"]),
                        float(row["relative_strength_120_pct"]),
                        float(row["high_52_week_pct"]),
                        float(row["volatility_60"]),
                        float(row["close_price"]),
                        1 if row["above_ma250"] else 0,
                        1 if row["eligible"] else 0,
                    )
                )

        report = {
            "status": "SUCCESS",
            "run_id": run_id,
            "started_at": started,
            "finished_at": utc_now(),
            "model": MODEL_ID,
            "market_db_sha256": sha256(p.market_db.read_bytes()).hexdigest(),
            "reference_zip_sha256": sha256(p.reference_zip.read_bytes()).hexdigest(),
            "signals": all_payloads,
            "default_weekly_signal": "MONTHLY_CANONICAL",
            "latest_preview_is_non_canonical": True,
            "research_only": True,
        }
        (output_dir / "model_run_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with state_db() as db:
            db.executemany(
                """
                INSERT INTO rankings(
                    run_id,signal_day,signal_kind,rank,symbol,score,
                    low_volatility_pct,relative_strength_120_pct,high_52_week_pct,
                    volatility_60,close_price,above_ma250,eligible
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                ranking_records,
            )
            db.execute(
                "UPDATE runs SET finished_at=?,status='SUCCESS',details_json=? WHERE run_id=?",
                (report["finished_at"], json.dumps(report, sort_keys=True), run_id),
            )
        return report
    except Exception as exc:
        failure = {
            "status": "FAILED",
            "run_id": run_id,
            "error": f"{type(exc).__name__}:{exc}",
            "finished_at": utc_now(),
        }
        (output_dir / "failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with state_db() as db:
            db.execute(
                "UPDATE runs SET finished_at=?,status='FAILED',details_json=? WHERE run_id=?",
                (failure["finished_at"], json.dumps(failure, sort_keys=True), run_id),
            )
        raise
