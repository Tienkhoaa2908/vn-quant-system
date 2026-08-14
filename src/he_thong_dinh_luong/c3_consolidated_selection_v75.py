"""V75 consolidated C3-anchored stock-selection optimization.

Research only. Frozen C3 remains comparator truth. V75 batches multiple
predeclared ranking challengers, winner-capture diagnostics, optional macro PIT,
paired inference, and V70 deep backtest in one workstation package.
"""
from __future__ import annotations

import bisect
import csv
import gzip
import json
import math
import random
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import c3_factor_health_regime_v73 as v73
from . import macro_pit_ablation_v74 as v74
from . import weekly_micro_capital_v43 as c3

SCHEMA_VERSION = "c3_consolidated_selection_v75"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
BASE_POLICY = "C3_BASELINE"
SIGNFLIP_SAMPLES = 10_000
BOOTSTRAP_SAMPLES = 5_000
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)
AUX_FEATURES = (
    "relative_20",
    "relative_10",
    "relative_5",
    "momentum_acceleration",
    "breakout_20_gap",
    "distance_ma20",
    "log_volume_ratio_5_20",
    "stability",
)
RANKING_POLICIES = (
    BASE_POLICY,
    "C3_FAST_REL20_25",
    "C3_FAST_ACCEL_25",
    "C3_FRESH_BREAKOUT_25",
    "C3_AUX_IC36_35",
)
MACRO_MIN_MONTHS = 48


@dataclass(frozen=True)
class FeatureRow:
    signal_day: date
    symbol: str
    baseline_rank: int
    baseline_score: float
    risk_on: bool
    values: Mapping[str, float]


def _read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    v73._write_csv(path, rows)


def _write_gz(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    v73._write_gz(path, rows)


def _rank_pct(values: Sequence[float]) -> list[float]:
    return [float(x) for x in c3.average_percentile([float(v) for v in values])]


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = fmean(values)
    return math.sqrt(sum((x - avg) ** 2 for x in values) / (len(values) - 1))


def _ret(m: v70.Market, symbol: str, pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = m.sc.get((symbol, m.cal[pos]))
    old = m.sc.get((symbol, m.cal[pos - lag]))
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def _iret(m: v70.Market, pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = m.ic.get(m.cal[pos])
    old = m.ic.get(m.cal[pos - lag])
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def _features(m: v70.Market, symbol: str, day: date) -> dict[str, float] | None:
    pos = bisect.bisect_left(m.cal, day)
    if pos >= len(m.cal) or m.cal[pos] != day or pos < 250:
        return None
    closes = [m.sc.get((symbol, d)) for d in m.cal[pos - 249:pos + 1]]
    if any(x is None or x <= 0 for x in closes):
        return None
    c = [float(x) for x in closes]
    r5, r10, r20, r120 = (_ret(m, symbol, pos, lag) for lag in (5, 10, 20, 120))
    i5, i10, i20, i120 = (_iret(m, pos, lag) for lag in (5, 10, 20, 120))
    if None in (r5, r10, r20, r120, i5, i10, i20, i120):
        return None
    prior20 = c[-21:-1]
    ma20 = fmean(c[-20:])
    volumes20 = [float(m.vol.get((symbol, d), 0)) for d in m.cal[pos - 19:pos + 1]]
    avg20 = fmean(volumes20)
    avg5 = fmean(volumes20[-5:])
    tail61 = c[-61:]
    returns60 = [tail61[i] / tail61[i - 1] - 1.0 for i in range(1, len(tail61))]
    vol60 = _std(returns60)
    vol20 = _std(returns60[-20:])
    rel120 = float(r120) - float(i120)
    rel20 = float(r20) - float(i20)
    return {
        "relative_20": rel20,
        "relative_10": float(r10) - float(i10),
        "relative_5": float(r5) - float(i5),
        "momentum_acceleration": rel20 - rel120 / 6.0,
        "breakout_20_gap": c[-1] / max(prior20) - 1.0,
        "distance_ma20": c[-1] / ma20 - 1.0,
        "log_volume_ratio_5_20": math.log(max(1e-9, avg5 / avg20)) if avg20 > 0 else 0.0,
        "stability": -(vol20 / vol60) if vol60 > 0 else 0.0,
    }


def _load_rank_rows(variant_dir: Path) -> list[dict[str, str]]:
    rows = _read_csv(variant_dir / "v67_c3_monthly_rankings.csv.gz")
    if not rows:
        raise ValueError(f"V75_EMPTY_RANKING:{variant_dir.name}")
    return rows


def _load_labels(variant_dir: Path) -> dict[tuple[date, str], tuple[date, float]]:
    result: dict[tuple[date, str], tuple[date, float]] = {}
    for row in _read_csv(variant_dir / "v67_c3_training_rows.csv.gz"):
        try:
            sd = date.fromisoformat(row["signal_day"])
            le = date.fromisoformat(row["label_end"])
            sym = str(row["symbol"]).strip().upper()
            y = float(row["relative_return_close_t_to_close_t20"])
        except (KeyError, TypeError, ValueError):
            continue
        result[(sd, sym)] = (le, y)
    return result


def build_feature_rows(variant_dir: Path, market: v70.Market) -> list[FeatureRow]:
    output: list[FeatureRow] = []
    for raw in _load_rank_rows(variant_dir):
        try:
            sd = date.fromisoformat(raw["signal_day"])
            sym = str(raw["symbol"]).strip().upper()
            brank = int(raw["rank"])
            bscore = float(raw["score"])
        except (KeyError, TypeError, ValueError):
            continue
        values = _features(market, sym, sd)
        if values is None:
            values = {name: 0.0 for name in AUX_FEATURES}
        output.append(FeatureRow(sd, sym, brank, bscore, v70._bool(raw.get("risk_on")), values))
    if not output:
        raise ValueError(f"V75_NO_FEATURE_ROWS:{variant_dir.name}")
    return output


def _pearson(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y) or len(x) < 3:
        return 0.0
    ax, ay = fmean(x), fmean(y)
    dx = [v - ax for v in x]
    dy = [v - ay for v in y]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return sum(a * b for a, b in zip(dx, dy)) / den if den else 0.0


def monthly_feature_ics(rows: Sequence[FeatureRow], labels: Mapping[tuple[date, str], tuple[date, float]]) -> list[dict[str, object]]:
    by_day: dict[date, list[FeatureRow]] = {}
    for row in rows:
        by_day.setdefault(row.signal_day, []).append(row)
    output: list[dict[str, object]] = []
    for sd, group in sorted(by_day.items()):
        valid = [(row, labels.get((sd, row.symbol))) for row in group]
        valid = [(row, label) for row, label in valid if label is not None]
        if len(valid) < 8:
            continue
        label_end = max(label[0] for _, label in valid)
        target = [float(label[1]) for _, label in valid]
        target_pct = _rank_pct(target)
        record: dict[str, object] = {"signal_day": sd.isoformat(), "label_end": label_end.isoformat(), "n": len(valid)}
        for name in AUX_FEATURES:
            xpct = _rank_pct([float(row.values[name]) for row, _ in valid])
            record[f"ic_{name}"] = _pearson(xpct, target_pct)
        output.append(record)
    return output


def _aux_weights(ic_rows: Sequence[Mapping[str, object]], signal_day: date) -> dict[str, float]:
    history = [
        row for row in ic_rows
        if date.fromisoformat(str(row["signal_day"])) < signal_day
        and date.fromisoformat(str(row["label_end"])) < signal_day
    ][-36:]
    if len(history) < 12:
        return {}
    means = {name: fmean(float(row[f"ic_{name}"]) for row in history) for name in AUX_FEATURES}
    positive = {k: v for k, v in means.items() if v > 0.0}
    if not positive:
        return {}
    total = sum(positive.values())
    raw = {k: v / total for k, v in positive.items()}
    equal = 1.0 / len(raw)
    shrunk = {k: 0.5 * w + 0.5 * equal for k, w in raw.items()}
    den = sum(shrunk.values())
    return {k: v / den for k, v in shrunk.items()}


def build_candidate_rankings(rows: Sequence[FeatureRow], ic_rows: Sequence[Mapping[str, object]]) -> tuple[dict[str, list[v70.Snap]], list[dict[str, object]], list[dict[str, object]]]:
    by_day: dict[date, list[FeatureRow]] = {}
    for row in rows:
        by_day.setdefault(row.signal_day, []).append(row)
    snaps = {policy: [] for policy in RANKING_POLICIES}
    rank_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    for sd, group in sorted(by_day.items()):
        group = sorted(group, key=lambda r: (r.baseline_rank, r.symbol))
        risk = group[0].risk_on
        baseline = {r.symbol: r.baseline_score for r in group}
        pct = {name: dict(zip([r.symbol for r in group], _rank_pct([r.values[name] for r in group]))) for name in AUX_FEATURES}
        dynamic_w = _aux_weights(ic_rows, sd)
        scores: dict[str, dict[str, float]] = {BASE_POLICY: baseline}
        scores["C3_FAST_REL20_25"] = {r.symbol: 0.75 * r.baseline_score + 0.25 * pct["relative_20"][r.symbol] for r in group}
        scores["C3_FAST_ACCEL_25"] = {r.symbol: 0.75 * r.baseline_score + 0.25 * pct["momentum_acceleration"][r.symbol] for r in group}
        scores["C3_FRESH_BREAKOUT_25"] = {r.symbol: 0.75 * r.baseline_score + 0.25 * pct["breakout_20_gap"][r.symbol] for r in group}
        if dynamic_w:
            aux = {r.symbol: sum(dynamic_w[name] * pct[name][r.symbol] for name in dynamic_w) for r in group}
            scores["C3_AUX_IC36_35"] = {r.symbol: 0.65 * r.baseline_score + 0.35 * aux[r.symbol] for r in group}
        else:
            scores["C3_AUX_IC36_35"] = dict(baseline)
        weight_rows.append({
            "signal_day": sd.isoformat(),
            "policy_id": "C3_AUX_IC36_35",
            "completed_ic_months_used": min(36, sum(date.fromisoformat(str(row["signal_day"])) < sd and date.fromisoformat(str(row["label_end"])) < sd for row in ic_rows)),
            **{f"weight_{name}": dynamic_w.get(name, 0.0) for name in AUX_FEATURES},
            "fallback_to_frozen": not bool(dynamic_w),
        })
        for policy in RANKING_POLICIES:
            ordered = sorted(scores[policy].items(), key=lambda item: (-item[1], item[0]))
            syms = tuple(sym for sym, _ in ordered[:10])
            snaps[policy].append(v70.Snap(sd, syms, risk))
            for rank, (sym, score) in enumerate(ordered, start=1):
                rank_rows.append({"signal_day": sd.isoformat(), "policy_id": policy, "symbol": sym, "rank": rank, "score": score, "risk_on": risk, "eligible_count": len(ordered)})
    return snaps, rank_rows, weight_rows


def _winner_capture(variant: str, rank_rows: Sequence[Mapping[str, object]], labels: Mapping[tuple[date, str], tuple[date, float]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by: dict[tuple[date, str], list[Mapping[str, object]]] = {}
    for row in rank_rows:
        sd = date.fromisoformat(str(row["signal_day"]))
        by.setdefault((sd, str(row["policy_id"])), []).append(row)
    monthly: list[dict[str, object]] = []
    for (sd, policy), group in sorted(by.items()):
        if sd > PRIMARY_SELECTION_END:
            continue
        labeled = []
        for row in group:
            sym = str(row["symbol"])
            label = labels.get((sd, sym))
            if label is not None:
                labeled.append((sym, int(row["rank"]), float(label[1])))
        if len(labeled) < 10:
            continue
        future = sorted(labeled, key=lambda x: (-x[2], x[0]))
        k = min(10, len(future))
        winners = {sym for sym, _, _ in future[:k]}
        dec = max(1, math.ceil(len(future) * 0.10))
        losers = {sym for sym, _, _ in future[-dec:]}
        top = [item for item in labeled if item[1] <= 10]
        top_syms = {sym for sym, _, _ in top}
        monthly.append({
            "variant_id": variant,
            "signal_day": sd.isoformat(),
            "policy_id": policy,
            "labeled_count": len(labeled),
            "future_winner_count": len(winners),
            "winner_top10_capture_rate": len(winners & top_syms) / len(winners),
            "loser_top10_contamination_rate": len(losers & top_syms) / max(1, len(top_syms)),
            "mean_top10_forward_excess": fmean(y for _, _, y in top) if top else None,
            "mean_rank_of_future_winners": fmean(rank for sym, rank, _ in labeled if sym in winners),
            "year_2026_used_for_selection": False,
        })
    baseline = {(row["variant_id"], row["signal_day"]): row for row in monthly if row["policy_id"] == BASE_POLICY}
    aggregate: list[dict[str, object]] = []
    for policy in sorted({str(row["policy_id"]) for row in monthly}):
        selected = [row for row in monthly if row["policy_id"] == policy]
        if not selected:
            continue
        dc, dl = [], []
        for row in selected:
            base = baseline.get((row["variant_id"], row["signal_day"]))
            if base is not None:
                dc.append(float(row["winner_top10_capture_rate"]) - float(base["winner_top10_capture_rate"]))
                dl.append(float(row["loser_top10_contamination_rate"]) - float(base["loser_top10_contamination_rate"]))
        aggregate.append({
            "variant_id": variant,
            "policy_id": policy,
            "month_count": len(selected),
            "mean_winner_top10_capture_rate": fmean(float(r["winner_top10_capture_rate"]) for r in selected),
            "mean_loser_top10_contamination_rate": fmean(float(r["loser_top10_contamination_rate"]) for r in selected),
            "mean_top10_forward_excess": fmean(float(r["mean_top10_forward_excess"]) for r in selected if r["mean_top10_forward_excess"] is not None),
            "mean_rank_of_future_winners": fmean(float(r["mean_rank_of_future_winners"]) for r in selected),
            "mean_capture_delta_vs_frozen": fmean(dc) if dc else 0.0,
            "mean_contamination_delta_vs_frozen": fmean(dl) if dl else 0.0,
        })
    return monthly, aggregate


def _safe_macro_collect() -> tuple[list[v74.MacroRelease], dict[str, object]]:
    errors: list[str] = []
    releases: list[v74.MacroRelease] = []
    for archives, language in ((v74.NSO_ARCHIVES, "en"), (v74.NSO_FALLBACK_ARCHIVES, "vi")):
        try:
            releases.extend(v74._collect_language(archives, language))
        except Exception as exc:
            errors.append(f"{language}:{type(exc).__name__}:{exc}")
    releases = v74._dedupe_first_release(releases)
    counts = {series: sum(row.series == series for row in releases) for series in ("CPI", "IIP")}
    usable = min(counts.values()) >= MACRO_MIN_MONTHS
    return releases, {
        "status": "USABLE_LATE_ERA_DIAGNOSTIC" if usable else "MACRO_LANE_BLOCKED",
        "counts": counts,
        "minimum_required_each_series": MACRO_MIN_MONTHS,
        "errors": errors,
        "publication_date_pit": True,
    }


def _macro_snaps(base: Sequence[v70.Snap], releases: Sequence[v74.MacroRelease]) -> tuple[dict[str, list[v70.Snap]], list[dict[str, object]], dict[str, date]]:
    result: dict[str, list[v70.Snap]] = {}
    states: list[dict[str, object]] = []
    starts: dict[str, date] = {}
    for spec in v74.GATES:
        out: list[v70.Snap] = []
        for snap in base:
            try:
                state = v74.macro_state(releases, snap.day, spec)
                active = bool(state["gate_active"])
                starts.setdefault(spec.policy_id, snap.day)
                states.append({**state, "macro_ready": True})
            except ValueError as exc:
                if "INSUFFICIENT_PUBLISHED_MACRO_HISTORY" not in str(exc):
                    raise
                active = False
                states.append({"signal_day": snap.day.isoformat(), "policy_id": spec.policy_id, "macro_ready": False, "gate_active": False, "publication_date_pit_enforced": True})
            out.append(v70.Snap(snap.day, snap.symbols, not active))
        result[spec.policy_id] = out
    return result, states, starts


def _decorate(rows, *, variant, policy, allocator, settlement, cost, capital):
    return v73._decorate(rows, variant=variant, policy_id=policy, allocator=allocator, settlement=settlement, cost_scenario=cost, capital=capital)


def _run_policy(market: v70.Market, snaps: Sequence[v70.Snap], variant: str, policy: str, allocator: str, risk_off: float) -> dict[str, list[dict[str, object]]]:
    out = {"summary": [], "monthly": [], "annual": [], "rolling": [], "daily": [], "ledger": [], "missing": [], "capital": []}
    for cost in v70.COSTS:
        spec = v70.Strategy(f"V75_{policy}_{allocator}", allocator, risk_off)
        r = v70.simulate(market, snaps, spec, cost, 1_000_000_000.0, variant)
        out["summary"] += _decorate([r["summary"]], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
        out["monthly"] += _decorate(r["periods"], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
        out["annual"] += _decorate(r["annual"], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
        out["rolling"] += _decorate(r["rolling"], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
        if cost.name == "BASE_DNSE":
            out["daily"] += _decorate(r["daily"], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
            out["ledger"] += _decorate(r["ledger"], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
            out["missing"] += _decorate(r["missing"], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost=cost.name, capital=1_000_000_000.0)
    t2 = v70.Strategy(f"V75_{policy}_{allocator}_T2", allocator, risk_off, "T2_NO_ADVANCE")
    r2 = v70.simulate(market, snaps, t2, v70.COSTS[1], 1_000_000_000.0, variant)
    out["summary"] += _decorate([r2["summary"]], variant=variant, policy=policy, allocator=allocator, settlement="T2_NO_ADVANCE", cost="BASE_DNSE", capital=1_000_000_000.0)
    for capital in CAPITALS:
        spec = v70.Strategy(f"V75_{policy}_{allocator}_CAP", allocator, risk_off)
        rc = v70.simulate(market, snaps, spec, v70.COSTS[1], capital, variant)
        out["capital"] += _decorate([rc["summary"]], variant=variant, policy=policy, allocator=allocator, settlement="IMMEDIATE", cost="BASE_DNSE", capital=capital)
    return out


def _baseline_audit(v70_output: Path, summary: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ref_rows = [row for row in _read_csv(v70_output / "v70_backtest_summary.csv") if str(row.get("strategy_id")) in {"C3_EQ_ALWAYS", "C3_INVOL_ALWAYS"}]
    ref = {}
    for row in ref_rows:
        allocator = "EQUAL" if row["strategy_id"] == "C3_EQ_ALWAYS" else "INVOL60"
        ref[(row["variant_id"], allocator, row["settlement_mode"], row["cost_scenario"], float(row["initial_capital_vnd"]))] = row
    compared = 0
    e_ret = e_cagr = e_mdd = 0.0
    for row in summary:
        if row.get("policy_id") != BASE_POLICY:
            continue
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["settlement_mode"]), str(row["cost_scenario"]), float(row["initial_capital_vnd"]))
        old = ref.get(key)
        if old is None:
            continue
        compared += 1
        e_ret = max(e_ret, abs(float(row["total_return"]) - float(old["total_return"])))
        e_cagr = max(e_cagr, abs(float(row["cagr"]) - float(old["cagr"])))
        e_mdd = max(e_mdd, abs(float(row["max_drawdown_daily"]) - float(old["max_drawdown_daily"])))
    if compared < 24 or max(e_ret, e_cagr, e_mdd) > 1e-10:
        raise ValueError(f"V75_BASELINE_RECONSTRUCTION_DRIFT:{compared}:{e_ret}:{e_cagr}:{e_mdd}")
    return {"compared_summary_count": compared, "max_total_return_error": e_ret, "max_cagr_error": e_cagr, "max_mdd_error": e_mdd}


def _block_key(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 2


def _signflip(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for d, x in paired:
        blocks.setdefault(_block_key(d), []).append(x)
    observed = fmean(x for _, x in paired)
    rng = random.Random(seed)
    vals = list(blocks.values())
    extreme = 0
    for _ in range(repetitions):
        sample = []
        for block in vals:
            sign = -1.0 if rng.random() < 0.5 else 1.0
            sample.extend(sign * x for x in block)
        if abs(fmean(sample)) >= abs(observed) - 1e-15:
            extreme += 1
    return observed, (extreme + 1.0) / (repetitions + 1.0)


def _bootstrap(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for d, x in paired:
        blocks.setdefault(_block_key(d), []).append(x)
    vals = list(blocks.values())
    rng = random.Random(seed)
    stats = []
    for _ in range(repetitions):
        sample = []
        for _j in range(len(vals)):
            sample.extend(vals[rng.randrange(len(vals))])
        stats.append(fmean(sample))
    stats.sort()
    return stats[int(0.025 * (len(stats) - 1))], stats[int(0.975 * (len(stats) - 1))]


def _mdd_pre2026(daily, variant, allocator, policy):
    vals = [float(r["nav_close_vnd"]) for r in daily if str(r.get("variant_id")) == variant and str(r.get("allocator")) == allocator and str(r.get("policy_id")) == policy and str(r.get("cost_scenario")) == "BASE_DNSE" and str(r.get("settlement_mode")) == "IMMEDIATE" and str(r.get("day")) <= PRIMARY_SELECTION_END.isoformat()]
    return v70._mdd(vals) if len(vals) >= 20 else 0.0


def candidate_inference(monthly, daily, policy_start: Mapping[str, date], *, signflip_samples: int, bootstrap_samples: int):
    scopes = sorted({(str(r["variant_id"]), str(r["allocator"])) for r in monthly if str(r.get("cost_scenario")) == "BASE_DNSE" and str(r.get("settlement_mode")) == "IMMEDIATE" and float(r.get("initial_capital_vnd") or 0.0) == 1_000_000_000.0})
    out = []
    for variant, allocator in scopes:
        base = {}
        cand: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {}
        for r in monthly:
            if str(r.get("variant_id")) != variant or str(r.get("allocator")) != allocator:
                continue
            if str(r.get("cost_scenario")) != "BASE_DNSE" or str(r.get("settlement_mode")) != "IMMEDIATE" or float(r.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
                continue
            key = (str(r["period_start_day"]), str(r["period_end_day"]))
            p = str(r["policy_id"])
            if p == BASE_POLICY:
                base[key] = r
            else:
                cand.setdefault(p, {})[key] = r
        for policy, cmap in cand.items():
            paired = []
            ann_c, ann_b = {}, {}
            start = policy_start.get(policy)
            for key in sorted(set(base) & set(cmap)):
                end = date.fromisoformat(key[1])
                if end > PRIMARY_SELECTION_END or (start is not None and end < start):
                    continue
                cr, br = float(cmap[key]["strategy_return"]), float(base[key]["strategy_return"])
                paired.append((end, cr - br))
                ann_c[end.year] = ann_c.get(end.year, 1.0) * (1.0 + cr)
                ann_b[end.year] = ann_b.get(end.year, 1.0) * (1.0 + br)
            if len(paired) < 24:
                continue
            seed = int.from_bytes(sha256(f"{variant}|{allocator}|{policy}|v75".encode()).digest()[:4], "big")
            mean_delta, p = _signflip(paired, signflip_samples, seed)
            lo, hi = _bootstrap(paired, bootstrap_samples, seed ^ 0x75A75)
            years = sorted(set(ann_c) & set(ann_b))
            annual_delta = [(ann_c[y] - 1.0) - (ann_b[y] - 1.0) for y in years]
            bmdd = _mdd_pre2026(daily, variant, allocator, BASE_POLICY)
            cmdd = _mdd_pre2026(daily, variant, allocator, policy)
            out.append({"variant_id": variant, "allocator": allocator, "policy_id": policy, "selection_period_end": PRIMARY_SELECTION_END.isoformat(), "paired_month_count": len(paired), "block_count": len({_block_key(d) for d, _ in paired}), "mean_monthly_return_delta": mean_delta, "median_monthly_return_delta": median(x for _, x in paired), "positive_month_delta_rate": sum(x > 0 for _, x in paired) / len(paired), "bootstrap_ci025": lo, "bootstrap_ci975": hi, "signflip_two_sided_p": p, "pre2026_year_count": len(years), "positive_annual_delta_rate": sum(x > 0 for x in annual_delta) / len(annual_delta), "mean_annual_return_delta": fmean(annual_delta), "pre2026_base_mdd": bmdd, "pre2026_candidate_mdd": cmdd, "pre2026_mdd_improvement": cmdd - bmdd, "year_2026_used_for_selection": False})
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for r in out:
        groups.setdefault((str(r["variant_id"]), str(r["allocator"])), []).append(r)
    for group in groups.values():
        ordered = sorted(group, key=lambda r: float(r["signflip_two_sided_p"]))
        m = len(ordered)
        running = 1.0
        adjusted = [1.0] * m
        for i in range(m - 1, -1, -1):
            running = min(running, float(ordered[i]["signflip_two_sided_p"]) * m / (i + 1))
            adjusted[i] = min(1.0, running)
        for r, q in zip(ordered, adjusted):
            r["bh_fdr_q"] = q
            r["diagnostic_watchlist_gate_passed"] = bool(float(r["mean_monthly_return_delta"]) > 0.0 and q < 0.10 and float(r["bootstrap_ci025"]) > 0.0 and float(r["positive_annual_delta_rate"]) >= 0.60 and float(r["pre2026_mdd_improvement"]) >= -0.02)
    return out


def _shadow_2026(annual, monthly):
    amap = {}
    for r in annual:
        try:
            if int(float(r["year"])) != 2026:
                continue
        except Exception:
            continue
        if str(r.get("cost_scenario")) == "BASE_DNSE" and str(r.get("settlement_mode")) == "IMMEDIATE" and float(r.get("initial_capital_vnd") or 0.0) == 1_000_000_000.0:
            amap[(str(r["variant_id"]), str(r["allocator"]), str(r["policy_id"]))] = r
    mmap = {}
    for r in monthly:
        if str(r.get("cost_scenario")) != "BASE_DNSE" or str(r.get("settlement_mode")) != "IMMEDIATE" or float(r.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
            continue
        start = str(r.get("period_start_day"))
        if start.startswith("2026-"):
            mmap[(str(r["variant_id"]), str(r["allocator"]), str(r["policy_id"]), start[:7])] = r
    out = []
    for key, r in sorted(amap.items()):
        variant, allocator, policy = key
        base = amap.get((variant, allocator, BASE_POLICY))
        if base is None:
            continue
        april = mmap.get((variant, allocator, policy, "2026-04"))
        base_april = mmap.get((variant, allocator, BASE_POLICY, "2026-04"))
        out.append({"variant_id": variant, "allocator": allocator, "policy_id": policy, "strategy_return": float(r["strategy_return"]), "benchmark_return": float(r["benchmark_return"]), "alpha_arithmetic": float(r["alpha_arithmetic"]), "policy_minus_frozen_2026_return": float(r["strategy_return"]) - float(base["strategy_return"]), "april_2026_return": float(april["strategy_return"]) if april else None, "april_2026_policy_minus_frozen": float(april["strategy_return"]) - float(base_april["strategy_return"]) if april and base_april else None, "used_for_selection": False, "status": "OBSERVED_STRESS_NOT_SELECTION_SET"})
    return out


def analyze(*, v68_output: Path, v70_output: Path, store: Path, output_dir: Path, allow_macro_network: bool = True, signflip_samples: int = SIGNFLIP_SAMPLES, bootstrap_samples: int = BOOTSTRAP_SAMPLES):
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V75_V68_VARIANTS_MISSING")
    report70 = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if report70.get("status") != "SUCCESS" or report70.get("champion_model") != CHAMPION_MODEL:
        raise ValueError("V75_V70_BASELINE_INVALID")
    variant_dirs = sorted(p for p in variants_root.iterdir() if p.is_dir())
    symbols = set()
    for vd in variant_dirs:
        for r in _load_rank_rows(vd):
            symbols.add(str(r["symbol"]).strip().upper())
    market = v70.load_market(store, symbols)
    all_summary, all_monthly, all_annual, all_rolling = [], [], [], []
    all_daily, all_ledger, all_missing, all_capital = [], [], [], []
    all_ranks, all_ic, all_aux_weights = [], [], []
    all_capture_monthly, all_capture_agg = [], []
    policy_start: dict[str, date] = {}
    variant_snaps: dict[str, dict[str, list[v70.Snap]]] = {}
    for vd in variant_dirs:
        feature_rows = build_feature_rows(vd, market)
        labels = _load_labels(vd)
        ic_rows = monthly_feature_ics(feature_rows, labels)
        snaps, ranking_rows, aux_weights = build_candidate_rankings(feature_rows, ic_rows)
        variant_snaps[vd.name] = snaps
        all_ranks += [{"variant_id": vd.name, **r} for r in ranking_rows]
        all_ic += [{"variant_id": vd.name, **r} for r in ic_rows]
        all_aux_weights += [{"variant_id": vd.name, **r} for r in aux_weights]
        cm, ca = _winner_capture(vd.name, ranking_rows, labels)
        all_capture_monthly += cm
        all_capture_agg += ca
    macro_releases: list[v74.MacroRelease] = []
    macro_status = {"status": "MACRO_NETWORK_DISABLED", "counts": {"CPI": 0, "IIP": 0}, "publication_date_pit": True}
    macro_states = []
    if allow_macro_network:
        macro_releases, macro_status = _safe_macro_collect()
        if macro_status["status"] == "USABLE_LATE_ERA_DIAGNOSTIC":
            for vd in variant_dirs:
                base = variant_snaps[vd.name][BASE_POLICY]
                ms, states, starts = _macro_snaps(base, macro_releases)
                variant_snaps[vd.name].update(ms)
                macro_states += [{"variant_id": vd.name, **r} for r in states]
                for k, v in starts.items():
                    policy_start[k] = min(policy_start.get(k, v), v)
    for variant, policies in sorted(variant_snaps.items()):
        for policy, snaps in sorted(policies.items()):
            risk_off = 0.50 if policy.startswith("MACRO_") else 1.0
            for allocator in ("EQUAL", "INVOL60"):
                r = _run_policy(market, snaps, variant, policy, allocator, risk_off)
                all_summary += r["summary"]; all_monthly += r["monthly"]; all_annual += r["annual"]; all_rolling += r["rolling"]
                all_daily += r["daily"]; all_ledger += r["ledger"]; all_missing += r["missing"]; all_capital += r["capital"]
    audit = _baseline_audit(v70_output, all_summary)
    inference = candidate_inference(all_monthly, all_daily, policy_start, signflip_samples=signflip_samples, bootstrap_samples=bootstrap_samples)
    shadow = _shadow_2026(all_annual, all_monthly)
    watchlist = [r for r in inference if bool(r.get("diagnostic_watchlist_gate_passed"))]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v75_candidate_rankings.csv", all_ranks)
    _write_csv(output_dir / "v75_aux_feature_ic_history.csv", all_ic)
    _write_csv(output_dir / "v75_aux_dynamic_weights.csv", all_aux_weights)
    _write_csv(output_dir / "v75_winner_capture_monthly.csv", all_capture_monthly)
    _write_csv(output_dir / "v75_winner_capture_summary.csv", all_capture_agg)
    _write_csv(output_dir / "v75_backtest_summary.csv", all_summary)
    _write_csv(output_dir / "v75_monthly_returns.csv", all_monthly)
    _write_csv(output_dir / "v75_annual_returns.csv", all_annual)
    _write_csv(output_dir / "v75_rolling_alpha.csv", all_rolling)
    _write_csv(output_dir / "v75_candidate_inference.csv", inference)
    _write_csv(output_dir / "v75_2026_shadow.csv", shadow)
    _write_csv(output_dir / "v75_capital_sensitivity.csv", all_capital)
    _write_csv(output_dir / "v75_missing_price_events.csv", all_missing)
    _write_gz(output_dir / "v75_daily_equity_base.csv.gz", all_daily)
    _write_gz(output_dir / "v75_trade_ledger_base.csv.gz", all_ledger)
    _write_csv(output_dir / "v75_macro_state.csv", macro_states)
    _write_csv(output_dir / "v75_macro_release_history.csv", v74._release_rows(macro_releases))
    (output_dir / "v75_macro_coverage.json").write_text(json.dumps(macro_status, indent=2, sort_keys=True), encoding="utf-8")
    report = {
        "schema_version": SCHEMA_VERSION, "status": "SUCCESS", "research_only": True,
        "champion_model": CHAMPION_MODEL, "champion_replaced": False,
        "c3_training_label": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE", "tradable_execution": "NEXT_SESSION_OPEN",
        "primary_selection_end": PRIMARY_SELECTION_END.isoformat(), "year_2026_used_for_candidate_selection": False,
        "ranking_policies": list(RANKING_POLICIES), "macro_status": macro_status, "macro_optional_nonblocking": True,
        "baseline_reconstruction_audit": audit, "candidate_inference_count": len(inference),
        "watchlist_candidate_count": len(watchlist), "watchlist_candidates": watchlist,
        "winner_capture_rows": len(all_capture_monthly), "deep_backtest_completed": True,
        "cost_scenarios": [x.name for x in v70.COSTS], "allocators": ["EQUAL", "INVOL60"],
        "capital_sensitivity_vnd": list(CAPITALS), "pit_hose_gate_closed": False, "price_basis_gate_closed": False,
        "canonical_hose_claim_authorized": False, "promotion_authorized": False, "automatic_live_orders_allowed": False,
    }
    (output_dir / "v75_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--v68-output", type=Path, required=True)
    p.add_argument("--v70-output", type=Path, required=True)
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--no-macro-network", action="store_true")
    p.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES)
    p.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    a = p.parse_args(argv)
    report = analyze(v68_output=a.v68_output, v70_output=a.v70_output, store=a.store, output_dir=a.output_dir, allow_macro_network=not a.no_macro_network, signflip_samples=a.signflip_samples, bootstrap_samples=a.bootstrap_samples)
    print(json.dumps({"status": report["status"], "champion_model": report["champion_model"], "watchlist_candidate_count": report["watchlist_candidate_count"], "macro_status": report["macro_status"]["status"], "promotion_authorized": report["promotion_authorized"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
