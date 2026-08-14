"""V71 causal adaptive C3 weight-memory ablation.

Frozen champion C3 is reconstructed exactly and never replaced.  Two predeclared
challengers change only the memory used to estimate the same three C3 component
ICs.  Candidate inference ends at 2025-12-31; 2026 is shadow/stress only.
Portfolio evaluation reuses the V70 actual-share deep backtest engine.
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
from statistics import fmean, median
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import weekly_micro_capital_v43 as c3

SCHEMA_VERSION = "c3_adaptive_weight_ablation_v71"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
COMPONENTS = tuple(c3.COMPONENTS)
PRIMARY_SELECTION_END = date(2025, 12, 31)
SIGNFLIP_SAMPLES = 10_000
BOOTSTRAP_SAMPLES = 5_000
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    mode: str
    parameter: int | None = None


CANDIDATES = (
    Candidate(CHAMPION_MODEL, "EXPANDING"),
    Candidate("C3_IC_EWMA_HL24", "EWMA", 24),
    Candidate("C3_IC_ROLLING60", "ROLLING", 60),
)


@dataclass(frozen=True)
class TrainingRow:
    signal_day: date
    label_end: date
    symbol: str
    relative_return: float
    components: Mapping[str, float]


@dataclass(frozen=True)
class ICMonth:
    signal_day: date
    label_end: date
    values: Mapping[str, float]


def _bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


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


def _finite(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V71_NON_FINITE:{name}")
    return number


def _load_training(path: Path) -> list[TrainingRow]:
    result: list[TrainingRow] = []
    for raw in _read_gz(path):
        try:
            row = TrainingRow(
                signal_day=date.fromisoformat(str(raw["signal_day"])),
                label_end=date.fromisoformat(str(raw["label_end"])),
                symbol=str(raw["symbol"]).strip().upper(),
                relative_return=_finite(raw["relative_return_close_t_to_close_t20"], "relative_return"),
                components={name: _finite(raw[name], name) for name in COMPONENTS},
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("V71_BAD_TRAINING_ROW") from exc
        result.append(row)
    if not result:
        raise ValueError("V71_TRAINING_ROWS_EMPTY")
    return result


def _monthly_ics(rows: Sequence[TrainingRow]) -> list[ICMonth]:
    grouped: dict[date, list[TrainingRow]] = {}
    for row in rows:
        grouped.setdefault(row.signal_day, []).append(row)
    result: list[ICMonth] = []
    for signal_day in sorted(grouped):
        month = grouped[signal_day]
        if len(month) < 5:
            continue
        target = [row.relative_return for row in month]
        values = {
            name: c3._spearman([row.components[name] for row in month], target)
            for name in COMPONENTS
        }
        result.append(ICMonth(signal_day, max(row.label_end for row in month), values))
    if len(result) < 12:
        raise ValueError("V71_TOO_FEW_IC_MONTHS")
    return result


def _weights_from_means(means: Mapping[str, float]) -> dict[str, float]:
    """Match frozen C3 exactly: positive IC -> shrink -> raw cap -> one renorm."""
    positive = {name: max(float(means.get(name, 0.0)), 0.0) for name in COMPONENTS}
    total_positive = sum(positive.values())
    empirical = (
        {name: positive[name] / total_positive for name in COMPONENTS}
        if total_positive > 0.0
        else {name: 1.0 / len(COMPONENTS) for name in COMPONENTS}
    )
    equal = 1.0 / len(COMPONENTS)
    raw = {name: 0.50 * equal + 0.50 * empirical[name] for name in COMPONENTS}
    capped = {name: min(raw[name], 0.50) for name in COMPONENTS}
    denominator = sum(capped.values())
    return {name: capped[name] / denominator for name in COMPONENTS}


def adaptive_weights(
    ic_months: Sequence[ICMonth], *, signal_day: date, candidate: Candidate
) -> tuple[dict[str, float], int]:
    history = [
        row for row in ic_months
        if row.signal_day < signal_day and row.label_end < signal_day
    ]
    if len(history) < 12:
        raise ValueError(f"V71_INSUFFICIENT_COMPLETED_IC_HISTORY:{signal_day}")
    if candidate.mode == "EXPANDING":
        selected = history
        observation_weights = [1.0] * len(selected)
    elif candidate.mode == "ROLLING":
        window = int(candidate.parameter or 0)
        if window < 12:
            raise ValueError("V71_ROLLING_WINDOW_TOO_SHORT")
        selected = history[-window:]
        observation_weights = [1.0] * len(selected)
    elif candidate.mode == "EWMA":
        half_life = int(candidate.parameter or 0)
        if half_life < 6:
            raise ValueError("V71_HALF_LIFE_TOO_SHORT")
        selected = history
        newest = len(selected) - 1
        observation_weights = [
            0.5 ** ((newest - index) / half_life)
            for index in range(len(selected))
        ]
    else:
        raise ValueError(f"V71_UNKNOWN_MODE:{candidate.mode}")
    denominator = sum(observation_weights)
    means = {
        name: sum(
            row.values[name] * weight
            for row, weight in zip(selected, observation_weights)
        ) / denominator
        for name in COMPONENTS
    }
    return _weights_from_means(means), len(selected)


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = fmean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def factor_components(market: v70.Market, symbol: str, signal_day: date) -> dict[str, float] | None:
    pos = bisect.bisect_left(market.cal, signal_day)
    if pos >= len(market.cal) or market.cal[pos] != signal_day or pos < 249:
        return None
    days250 = market.cal[pos - 249: pos + 1]
    days61 = market.cal[pos - 60: pos + 1]
    closes250 = [market.sc.get((symbol, day)) for day in days250]
    closes61 = [market.sc.get((symbol, day)) for day in days61]
    if any(value is None or value <= 0 for value in closes250 + closes61):
        return None
    c250 = [float(value) for value in closes250 if value is not None]
    c61 = [float(value) for value in closes61 if value is not None]
    returns60 = [c61[i] / c61[i - 1] - 1.0 for i in range(1, len(c61))]
    vol60 = _sample_std(returns60)
    old_stock = market.sc.get((symbol, market.cal[pos - 120]))
    current_stock = market.sc.get((symbol, signal_day))
    old_index = market.ic.get(market.cal[pos - 120])
    current_index = market.ic.get(signal_day)
    if not all(value is not None and value > 0 for value in (old_stock, current_stock, old_index, current_index)) or vol60 <= 0:
        return None
    return {
        "low_volatility": -vol60,
        "relative_strength_120": float(current_stock) / float(old_stock) - float(current_index) / float(old_index),
        "high_52_week": float(current_stock) / max(c250),
    }


def _group_rankings(rows: Sequence[Mapping[str, str]]) -> dict[date, list[dict[str, str]]]:
    grouped: dict[date, list[dict[str, str]]] = {}
    for raw in rows:
        day = date.fromisoformat(str(raw["signal_day"]))
        row = dict(raw)
        row["rank"] = str(int(raw["rank"]))
        grouped.setdefault(day, []).append(row)
    for day in grouped:
        grouped[day].sort(key=lambda row: int(row["rank"]))
    if len(grouped) < 3:
        raise ValueError("V71_TOO_FEW_BASELINE_SNAPSHOTS")
    return grouped


def _load_recorded_weights(path: Path) -> dict[date, dict[str, float]]:
    result: dict[date, dict[str, float]] = {}
    for row in _read_csv(path):
        result[date.fromisoformat(row["signal_day"])] = {
            "low_volatility": float(row["weight_low_volatility"]),
            "relative_strength_120": float(row["weight_relative_strength_120"]),
            "high_52_week": float(row["weight_high_52_week"]),
        }
    return result


def build_variant_candidates(*, variant_id: str, variant_dir: Path, market: v70.Market) -> dict[str, object]:
    grouped = _group_rankings(_read_gz(variant_dir / "v67_c3_monthly_rankings.csv.gz"))
    training = _load_training(variant_dir / "v67_c3_training_rows.csv.gz")
    training_key = {(row.signal_day, row.symbol): row for row in training}
    ic_months = _monthly_ics(training)
    recorded_weights = _load_recorded_weights(variant_dir / "v67_c3_weight_history.csv")
    candidate_snaps = {candidate.candidate_id: [] for candidate in CANDIDATES}
    ranking_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    predictive_rows: list[dict[str, object]] = []
    overlap_rows: list[dict[str, object]] = []
    max_factor_error = max_weight_error = max_score_error = 0.0
    rank_mismatch = 0

    for signal_day in sorted(grouped):
        baseline_rows = grouped[signal_day]
        symbols = [str(row["symbol"]).strip().upper() for row in baseline_rows]
        risk_on = _bool(baseline_rows[0].get("risk_on"))
        direct: dict[str, dict[str, float]] = {}
        for symbol in symbols:
            components = factor_components(market, symbol, signal_day)
            if components is None:
                raise ValueError(f"V71_FACTOR_STATE_MISSING:{variant_id}:{signal_day}:{symbol}")
            direct[symbol] = components
            old = training_key.get((signal_day, symbol))
            if old is not None:
                for name in COMPONENTS:
                    max_factor_error = max(max_factor_error, abs(components[name] - old.components[name]))

        candidate_top10: dict[str, tuple[str, ...]] = {}
        for candidate in CANDIDATES:
            weights, used = adaptive_weights(ic_months, signal_day=signal_day, candidate=candidate)
            if candidate.candidate_id == CHAMPION_MODEL:
                recorded = recorded_weights.get(signal_day)
                if recorded is None:
                    raise ValueError(f"V71_BASELINE_WEIGHT_MISSING:{signal_day}")
                for name in COMPONENTS:
                    max_weight_error = max(max_weight_error, abs(weights[name] - recorded[name]))
            states = [{"symbol": symbol, **direct[symbol]} for symbol in symbols]
            pct = {
                name: c3.average_percentile([float(row[name]) for row in states])
                for name in COMPONENTS
            }
            for index, row in enumerate(states):
                row["score"] = sum(weights[name] * pct[name][index] for name in COMPONENTS)
            states.sort(key=lambda row: (-float(row["score"]), str(row["symbol"])))
            order = tuple(str(row["symbol"]) for row in states)
            candidate_top10[candidate.candidate_id] = order[:10]
            candidate_snaps[candidate.candidate_id].append(v70.Snap(signal_day, order[:10], risk_on))
            if candidate.candidate_id == CHAMPION_MODEL:
                if order != tuple(symbols):
                    rank_mismatch += 1
                old_score = {str(row["symbol"]).strip().upper(): float(row["score"]) for row in baseline_rows}
                for row in states:
                    max_score_error = max(max_score_error, abs(float(row["score"]) - old_score[str(row["symbol"])]))
            phase = "PRE2026_PRIMARY" if signal_day <= PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW"
            labels = [
                training_key[(signal_day, symbol)].relative_return
                for symbol in order[:10]
                if (signal_day, symbol) in training_key
            ]
            predictive_rows.append({
                "variant_id": variant_id,
                "candidate_id": candidate.candidate_id,
                "signal_day": signal_day.isoformat(),
                "phase": phase,
                "label_count": len(labels),
                "mean_top10_close_close20_excess": fmean(labels) if labels else None,
                "positive_label_rate": sum(value > 0 for value in labels) / len(labels) if labels else None,
                "used_for_candidate_selection": signal_day <= PRIMARY_SELECTION_END,
            })
            weight_rows.append({
                "variant_id": variant_id,
                "candidate_id": candidate.candidate_id,
                "mode": candidate.mode,
                "parameter": candidate.parameter,
                "signal_day": signal_day.isoformat(),
                "completed_ic_month_count_used": used,
                "weight_low_volatility": weights["low_volatility"],
                "weight_relative_strength_120": weights["relative_strength_120"],
                "weight_high_52_week": weights["high_52_week"],
                "uses_only_label_end_before_signal": True,
                "year_2026_used_for_selection": False,
            })
            baseline_rank = {symbol: index for index, symbol in enumerate(symbols, 1)}
            for rank, row in enumerate(states, 1):
                symbol = str(row["symbol"])
                training_row = training_key.get((signal_day, symbol))
                ranking_rows.append({
                    "variant_id": variant_id,
                    "candidate_id": candidate.candidate_id,
                    "signal_day": signal_day.isoformat(),
                    "symbol": symbol,
                    "rank": rank,
                    "baseline_rank": baseline_rank.get(symbol),
                    "score": row["score"],
                    "low_volatility": row["low_volatility"],
                    "relative_strength_120": row["relative_strength_120"],
                    "high_52_week": row["high_52_week"],
                    "risk_on": risk_on,
                    "relative_return_close_t_to_close_t20": training_row.relative_return if training_row else None,
                    "phase": phase,
                })
        frozen = set(candidate_top10[CHAMPION_MODEL])
        for candidate in CANDIDATES[1:]:
            current = set(candidate_top10[candidate.candidate_id])
            overlap_rows.append({
                "variant_id": variant_id,
                "candidate_id": candidate.candidate_id,
                "signal_day": signal_day.isoformat(),
                "top10_jaccard_vs_frozen_c3": len(current & frozen) / len(current | frozen),
                "exact_top10_match": current == frozen,
                "changed_name_count": 10 - len(current & frozen),
                "phase": "PRE2026_PRIMARY" if signal_day <= PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW",
            })

    if max_factor_error > 1e-10:
        raise ValueError(f"V71_FACTOR_RECONSTRUCTION_DRIFT:{max_factor_error}")
    if max_weight_error > 1e-10:
        raise ValueError(f"V71_FROZEN_WEIGHT_RECONSTRUCTION_DRIFT:{max_weight_error}")
    if max_score_error > 1e-10:
        raise ValueError(f"V71_FROZEN_SCORE_RECONSTRUCTION_DRIFT:{max_score_error}")
    if rank_mismatch:
        raise ValueError(f"V71_FROZEN_RANK_RECONSTRUCTION_DRIFT:{rank_mismatch}")
    ic_rows = [{
        "variant_id": variant_id,
        "signal_day": row.signal_day.isoformat(),
        "label_end": row.label_end.isoformat(),
        **{f"ic_{name}": row.values[name] for name in COMPONENTS},
    } for row in ic_months]
    return {
        "candidate_snaps": candidate_snaps,
        "ranking_rows": ranking_rows,
        "weight_rows": weight_rows,
        "predictive_rows": predictive_rows,
        "overlap_rows": overlap_rows,
        "ic_rows": ic_rows,
        "audit": {
            "max_factor_reconstruction_error": max_factor_error,
            "max_frozen_weight_reconstruction_error": max_weight_error,
            "max_frozen_score_reconstruction_error": max_score_error,
            "frozen_rank_mismatch_count": rank_mismatch,
        },
    }


def _decorate(rows: Sequence[Mapping[str, object]], variant: str, candidate: str, allocator: str, source: str) -> list[dict[str, object]]:
    return [{**dict(row), "variant_id": variant, "candidate_id": candidate, "allocator": allocator, "source": source} for row in rows]


def _load_v70_baseline(v70_output: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    strategy_map = {"C3_EQ_ALWAYS": "EQUAL", "C3_INVOL_ALWAYS": "INVOL60"}
    def cooked(rows: Sequence[Mapping[str, str]], *, base_only: bool = False) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for raw in rows:
            strategy = str(raw.get("strategy_id") or "")
            if strategy not in strategy_map:
                continue
            if base_only and str(raw.get("cost_scenario") or "") != "BASE_DNSE":
                continue
            result.append({**dict(raw), "candidate_id": CHAMPION_MODEL, "allocator": strategy_map[strategy], "source": "V70_FROZEN_BASELINE"})
        return result
    return (
        cooked(_read_csv(v70_output / "v70_backtest_summary.csv")),
        cooked(_read_csv(v70_output / "v70_monthly_returns.csv")),
        cooked(_read_csv(v70_output / "v70_annual_returns.csv")),
        cooked(_read_csv(v70_output / "v70_capital_lot_sensitivity.csv")),
        cooked(_read_gz(v70_output / "v70_daily_equity.csv.gz"), base_only=True),
    )


def _block_key(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 2


def _signflip(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for day, delta in paired:
        blocks.setdefault(_block_key(day), []).append(delta)
    block_values = [values for _, values in sorted(blocks.items())]
    observed = fmean(delta for _, delta in paired)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(repetitions):
        sample: list[float] = []
        for values in block_values:
            sign = -1.0 if rng.random() < 0.5 else 1.0
            sample.extend(sign * value for value in values)
        if abs(fmean(sample)) >= abs(observed) - 1e-15:
            extreme += 1
    return observed, (extreme + 1.0) / (repetitions + 1.0)


def _bootstrap_ci(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for day, delta in paired:
        blocks.setdefault(_block_key(day), []).append(delta)
    values = [block for _, block in sorted(blocks.items())]
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(repetitions):
        sample: list[float] = []
        for _index in range(len(values)):
            sample.extend(values[rng.randrange(len(values))])
        stats.append(fmean(sample))
    stats.sort()
    return stats[int(0.025 * (len(stats) - 1))], stats[int(0.975 * (len(stats) - 1))]


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


def candidate_inference(monthly_rows: Sequence[Mapping[str, object]], *, signflip_samples: int, bootstrap_samples: int) -> list[dict[str, object]]:
    scopes = sorted({
        (str(row["variant_id"]), str(row["allocator"]))
        for row in monthly_rows if str(row.get("cost_scenario")) == "BASE_DNSE"
    })
    results: list[dict[str, object]] = []
    for variant, allocator in scopes:
        baseline: dict[tuple[str, str], Mapping[str, object]] = {}
        candidates: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {}
        for row in monthly_rows:
            if str(row.get("variant_id")) != variant or str(row.get("allocator")) != allocator or str(row.get("cost_scenario")) != "BASE_DNSE":
                continue
            key = str(row.get("period_start_day")), str(row.get("period_end_day"))
            cid = str(row.get("candidate_id"))
            if cid == CHAMPION_MODEL:
                baseline[key] = row
            else:
                candidates.setdefault(cid, {})[key] = row
        for cid, cmap in sorted(candidates.items()):
            paired: list[tuple[date, float]] = []
            annual_c: dict[int, float] = {}
            annual_b: dict[int, float] = {}
            for period in sorted(set(baseline) & set(cmap)):
                end = date.fromisoformat(period[1])
                if end > PRIMARY_SELECTION_END:
                    continue
                cr = float(cmap[period]["strategy_return"])
                br = float(baseline[period]["strategy_return"])
                paired.append((end, cr - br))
                annual_c[end.year] = annual_c.get(end.year, 1.0) * (1.0 + cr)
                annual_b[end.year] = annual_b.get(end.year, 1.0) * (1.0 + br)
            if len(paired) < 24:
                raise ValueError(f"V71_TOO_FEW_PRE2026_PAIRED_MONTHS:{variant}:{allocator}:{cid}")
            seed = int(sha256(f"{variant}|{allocator}|{cid}".encode()).hexdigest()[:8], 16)
            observed, p = _signflip(paired, signflip_samples, seed)
            ci_low, ci_high = _bootstrap_ci(paired, bootstrap_samples, seed ^ 0x5A17)
            years = sorted(set(annual_c) & set(annual_b))
            annual_delta = [(annual_c[y] - 1.0) - (annual_b[y] - 1.0) for y in years]
            deltas = [value for _, value in paired]
            results.append({
                "variant_id": variant,
                "allocator": allocator,
                "candidate_id": cid,
                "comparator": CHAMPION_MODEL,
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
                "positive_annual_delta_rate": sum(value > 0 for value in annual_delta) / len(annual_delta) if annual_delta else 0.0,
                "mean_annual_return_delta": fmean(annual_delta) if annual_delta else None,
                "year_2026_used_for_selection": False,
            })
    _bh(results)
    for row in results:
        row["diagnostic_watchlist_gate_passed"] = bool(
            float(row["mean_monthly_return_delta"]) > 0
            and float(row["bh_fdr_q"]) < 0.10
            and float(row["bootstrap_ci025"]) > 0
            and float(row["positive_annual_delta_rate"]) >= 0.60
        )
    return results


def _shadow_2026(annual_rows: Sequence[Mapping[str, object]], monthly_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    annual_map: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for row in annual_rows:
        try:
            if int(float(row["year"])) != 2026 or str(row.get("cost_scenario")) != "BASE_DNSE":
                continue
        except (KeyError, TypeError, ValueError):
            continue
        annual_map[(str(row["variant_id"]), str(row["allocator"]), str(row["candidate_id"]))] = row
    monthly_map: dict[tuple[str, str, str, str], Mapping[str, object]] = {}
    for row in monthly_rows:
        if str(row.get("cost_scenario")) != "BASE_DNSE":
            continue
        start = str(row.get("period_start_day"))
        if not start.startswith("2026-"):
            continue
        monthly_map[(str(row["variant_id"]), str(row["allocator"]), str(row["candidate_id"]), start[:7])] = row
    result: list[dict[str, object]] = []
    for (variant, allocator, cid), row in sorted(annual_map.items()):
        base = annual_map.get((variant, allocator, CHAMPION_MODEL))
        if base is None:
            continue
        april = monthly_map.get((variant, allocator, cid, "2026-04"))
        base_april = monthly_map.get((variant, allocator, CHAMPION_MODEL, "2026-04"))
        result.append({
            "variant_id": variant,
            "allocator": allocator,
            "candidate_id": cid,
            "strategy_return": float(row["strategy_return"]),
            "benchmark_return": float(row["benchmark_return"]),
            "alpha_arithmetic": float(row["alpha_arithmetic"]),
            "candidate_minus_frozen_2026_return": float(row["strategy_return"]) - float(base["strategy_return"]),
            "april_2026_return": float(april["strategy_return"]) if april else None,
            "april_2026_candidate_minus_frozen": float(april["strategy_return"]) - float(base_april["strategy_return"]) if april and base_april else None,
            "used_for_selection": False,
            "status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        })
    return result


def _cost_drag(summary_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, Mapping[str, object]]] = {}
    for row in summary_rows:
        if str(row.get("settlement_mode")) != "IMMEDIATE" or float(row.get("initial_capital_vnd") or 0) != 1_000_000_000.0:
            continue
        grouped.setdefault((str(row["variant_id"]), str(row["candidate_id"]), str(row["allocator"])), {})[str(row["cost_scenario"])] = row
    result: list[dict[str, object]] = []
    for (variant, candidate, allocator), scenarios in sorted(grouped.items()):
        gross = scenarios.get("GROSS")
        if gross is None:
            continue
        for name in ("BASE_DNSE", "STRESS", "SEVERE"):
            row = scenarios.get(name)
            if row is not None:
                result.append({
                    "variant_id": variant,
                    "candidate_id": candidate,
                    "allocator": allocator,
                    "cost_scenario": name,
                    "total_return_drag_vs_gross": float(row["total_return"]) - float(gross["total_return"]),
                    "cagr_drag_vs_gross": float(row["cagr"]) - float(gross["cagr"]),
                })
    return result


def analyze(*, v68_output: Path, v70_output: Path, store: Path, output_dir: Path, signflip_samples: int = SIGNFLIP_SAMPLES, bootstrap_samples: int = BOOTSTRAP_SAMPLES) -> dict[str, object]:
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V71_V68_VARIANTS_MISSING")
    v70_report = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if v70_report.get("status") != "SUCCESS" or v70_report.get("champion_model") != CHAMPION_MODEL or bool(v70_report.get("champion_replaced")):
        raise ValueError("V71_V70_BASELINE_CONTRACT_INVALID")
    baseline_summary, baseline_monthly, baseline_annual, baseline_capital, baseline_daily = _load_v70_baseline(v70_output)

    variant_dirs = sorted(path for path in variants_root.iterdir() if path.is_dir())
    symbols: set[str] = set()
    for variant_dir in variant_dirs:
        for row in _read_gz(variant_dir / "v67_c3_monthly_rankings.csv.gz"):
            symbols.add(str(row["symbol"]).strip().upper())
    if not symbols:
        raise ValueError("V71_NO_RANKING_SYMBOLS")
    market = v70.load_market(store, symbols)

    rankings: list[dict[str, object]] = []
    weights: list[dict[str, object]] = []
    predictive: list[dict[str, object]] = []
    overlap: list[dict[str, object]] = []
    ic_rows: list[dict[str, object]] = []
    audits: dict[str, object] = {}
    snaps_by_variant: dict[str, dict[str, list[v70.Snap]]] = {}
    for variant_dir in variant_dirs:
        built = build_variant_candidates(variant_id=variant_dir.name, variant_dir=variant_dir, market=market)
        snaps_by_variant[variant_dir.name] = built["candidate_snaps"]
        rankings.extend(built["ranking_rows"])
        weights.extend(built["weight_rows"])
        predictive.extend(built["predictive_rows"])
        overlap.extend(built["overlap_rows"])
        ic_rows.extend(built["ic_rows"])
        audits[variant_dir.name] = built["audit"]

    summary_rows: list[dict[str, object]] = list(baseline_summary)
    monthly_rows: list[dict[str, object]] = list(baseline_monthly)
    annual_rows: list[dict[str, object]] = list(baseline_annual)
    capital_rows: list[dict[str, object]] = list(baseline_capital)
    daily_rows: list[dict[str, object]] = list(baseline_daily)
    ledger_rows: list[dict[str, object]] = []

    for variant, candidate_map in sorted(snaps_by_variant.items()):
        for candidate in CANDIDATES[1:]:
            snaps = candidate_map[candidate.candidate_id]
            for allocator in ("EQUAL", "INVOL60"):
                spec = v70.Strategy(f"V71_{candidate.candidate_id}_{allocator}", allocator, 1.0)
                for cost in v70.COSTS:
                    result = v70.simulate(market, snaps, spec, cost, 1_000_000_000.0, variant)
                    summary_rows += _decorate([result["summary"]], variant, candidate.candidate_id, allocator, "V71_ADAPTIVE_C3")
                    monthly_rows += _decorate(result["periods"], variant, candidate.candidate_id, allocator, "V71_ADAPTIVE_C3")
                    annual_rows += _decorate(result["annual"], variant, candidate.candidate_id, allocator, "V71_ADAPTIVE_C3")
                    if cost.name == "BASE_DNSE":
                        ledger_rows += _decorate(result["ledger"], variant, candidate.candidate_id, allocator, "V71_ADAPTIVE_C3")
                        daily_rows += _decorate(result["daily"], variant, candidate.candidate_id, allocator, "V71_ADAPTIVE_C3")
                t2 = v70.Strategy(f"V71_{candidate.candidate_id}_{allocator}_T2", allocator, 1.0, "T2_NO_ADVANCE")
                result = v70.simulate(market, snaps, t2, v70.COSTS[1], 1_000_000_000.0, variant)
                summary_rows += _decorate([result["summary"]], variant, candidate.candidate_id, allocator, "V71_T2_SENSITIVITY")
                for capital in CAPITALS:
                    result = v70.simulate(market, snaps, spec, v70.COSTS[1], capital, variant)
                    capital_rows += _decorate([result["summary"]], variant, candidate.candidate_id, allocator, "V71_CAPITAL_SENSITIVITY")

    inference = candidate_inference(monthly_rows, signflip_samples=signflip_samples, bootstrap_samples=bootstrap_samples)
    shadow = _shadow_2026(annual_rows, monthly_rows)
    cost_drag = _cost_drag(summary_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v71_component_ic_history.csv", ic_rows)
    _write_csv(output_dir / "v71_weight_history.csv", weights)
    _write_gz(output_dir / "v71_rankings.csv.gz", rankings)
    _write_csv(output_dir / "v71_top10_overlap.csv", overlap)
    _write_csv(output_dir / "v71_predictive_proxy.csv", predictive)
    _write_csv(output_dir / "v71_backtest_summary.csv", summary_rows)
    _write_csv(output_dir / "v71_monthly_returns.csv", monthly_rows)
    _write_csv(output_dir / "v71_annual_returns.csv", annual_rows)
    _write_csv(output_dir / "v71_candidate_inference.csv", inference)
    _write_csv(output_dir / "v71_2026_shadow.csv", shadow)
    _write_csv(output_dir / "v71_cost_drag.csv", cost_drag)
    _write_csv(output_dir / "v71_capital_sensitivity.csv", capital_rows)
    _write_gz(output_dir / "v71_trade_ledger_base.csv.gz", ledger_rows)
    _write_gz(output_dir / "v71_daily_equity_base.csv.gz", daily_rows)

    watchlist = [row for row in inference if bool(row.get("diagnostic_watchlist_gate_passed"))]
    profit_table = [{
        "variant_id": str(row.get("variant_id")),
        "candidate_id": str(row.get("candidate_id")),
        "allocator": str(row.get("allocator")),
        "total_return": float(row["total_return"]),
        "benchmark_total_return": float(row["benchmark_total_return"]),
        "total_alpha_arithmetic": float(row["total_alpha_arithmetic"]),
        "cagr": float(row["cagr"]),
        "max_drawdown_daily": float(row["max_drawdown_daily"]),
        "benchmark_max_drawdown_daily": float(row["benchmark_max_drawdown_daily"]),
    } for row in summary_rows
      if str(row.get("cost_scenario")) == "BASE_DNSE"
      and str(row.get("settlement_mode")) == "IMMEDIATE"
      and float(row.get("initial_capital_vnd") or 0) == 1_000_000_000.0]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "adaptive_candidates": [{"candidate_id": item.candidate_id, "mode": item.mode, "parameter": item.parameter} for item in CANDIDATES[1:]],
        "component_set_changed": False,
        "c3_training_label": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE",
        "weight_shrinkage_to_equal": 0.50,
        "raw_component_cap_before_renormalization": 0.50,
        "uses_only_completed_label_end_before_signal": True,
        "primary_candidate_selection_end": PRIMARY_SELECTION_END.isoformat(),
        "year_2026_used_for_candidate_selection": False,
        "year_2026_status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        "signflip_samples": signflip_samples,
        "bootstrap_samples_ci_only": bootstrap_samples,
        "inference_dependence_unit": "CONTIGUOUS_TWO_CALENDAR_MONTH_BLOCKS",
        "multiple_testing": "BH_FDR_WITHIN_VARIANT_AND_ALLOCATOR",
        "portfolio_engine_reused": "deep_portfolio_backtest_v70",
        "portfolio_execution": "MONTHLY_TOP10_ACTUAL_SHARES_NEXT_OPEN",
        "allocators": ["EQUAL", "INVOL60"],
        "cost_scenarios": [cost.name for cost in v70.COSTS],
        "capital_sensitivity_vnd": list(CAPITALS),
        "t2_no_advance_sensitivity": True,
        "profit_reporting": {
            "report_type": "MODELED_COST_DEEP_BACKTEST",
            "equity_curve_output": "v71_daily_equity_base.csv.gz",
            "base_cost_profit_table": profit_table,
            "exact_cash_ledger": False,
            "sector_cap_enforced": False,
            "fixed_slippage_is_exact_market_impact": False,
        },
        "frozen_reconstruction_audit": audits,
        "diagnostic_watchlist": watchlist,
        "diagnostic_watchlist_count": len(watchlist),
        "v69_weekly_overlay_integration_deferred": True,
        "macro_included": False,
        "research_only": True,
        "promotion_authorized": False,
        "automatic_live_orders_allowed": False,
        "limitations": [
            "Adaptive candidates were generated after historical V70 review and are not pristine independent holdouts.",
            "2026 is excluded from candidate inference and reported only as observed stress.",
            "PIT HOSE, price basis/corporate actions and PIT sector master remain unresolved data gates.",
            "V71 tests C3 weight memory only; components and training-label semantics are frozen.",
            "V69 L15/R07/R08 integration is deferred to avoid stacking post-selected mechanisms.",
            "This is modeled-cost research P&L, not broker-exact cash P&L.",
            "Historical evidence cannot authorize live capital without future paper holdout and explicit promotion.",
        ],
    }
    (output_dir / "v71_report.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    report = analyze(v68_output=args.v68_output, v70_output=args.v70_output, store=args.store, output_dir=args.output_dir, signflip_samples=args.signflip_samples, bootstrap_samples=args.bootstrap_samples)
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
