"""V73 causal C3 factor-health regime ablation with V70 deep backtest.

Research only. Frozen C3 ranking/components are unchanged. V73 asks whether a
predeclared monthly exposure gate based solely on *completed* historical IC
observations can improve the frozen C3 portfolio. Candidate inference stops at
2025-12-31; 2026 is observed shadow only.
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
import random
from statistics import fmean, median
from typing import Mapping, Sequence

from . import c3_adaptive_weight_v71 as v71
from . import deep_portfolio_backtest_v70 as v70

SCHEMA_VERSION = "c3_factor_health_regime_v73"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
SIGNFLIP_SAMPLES = 10_000
BOOTSTRAP_SAMPLES = 5_000
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)
SOFT_EXPOSURE = 0.50


@dataclass(frozen=True)
class GateSpec:
    policy_id: str
    window: int
    mode: str


GATES = (
    GateSpec("FH_RS3_SOFT50", 3, "RS_ONLY"),
    GateSpec("FH_MOM3_AVG_SOFT50", 3, "MOM_AVG"),
    GateSpec("FH_MOM6_AVG_SOFT50", 6, "MOM_AVG"),
)
BASE_POLICY = "NO_FACTOR_HEALTH_GATE"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
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


def _decorate(
    rows: Sequence[Mapping[str, object]], *, variant: str, policy_id: str,
    allocator: str, settlement: str, cost_scenario: str, capital: float,
) -> list[dict[str, object]]:
    return [{
        **dict(row),
        "variant_id": variant,
        "policy_id": policy_id,
        "allocator": allocator,
        "settlement_mode": settlement,
        "cost_scenario": cost_scenario,
        "initial_capital_vnd": capital,
    } for row in rows]


def completed_ic_history(ic_months: Sequence[v71.ICMonth], signal_day: date) -> list[v71.ICMonth]:
    """Causal history: both signal and label must be fully before current signal."""
    return [
        row for row in ic_months
        if row.signal_day < signal_day and row.label_end < signal_day
    ]


def gate_state(ic_months: Sequence[v71.ICMonth], signal_day: date, spec: GateSpec) -> dict[str, object]:
    history = completed_ic_history(ic_months, signal_day)
    if len(history) < max(12, spec.window):
        raise ValueError(f"V73_INSUFFICIENT_COMPLETED_IC_HISTORY:{signal_day}:{spec.policy_id}")
    recent = history[-spec.window:]
    rs = fmean(float(row.values["relative_strength_120"]) for row in recent)
    h52 = fmean(float(row.values["high_52_week"]) for row in recent)
    mom = 0.5 * (rs + h52)
    if spec.mode == "RS_ONLY":
        trigger = rs <= 0.0
    elif spec.mode == "MOM_AVG":
        trigger = mom <= 0.0
    else:
        raise ValueError(f"V73_UNKNOWN_GATE_MODE:{spec.mode}")
    return {
        "signal_day": signal_day.isoformat(),
        "policy_id": spec.policy_id,
        "window_completed_ic_months": spec.window,
        "gate_mode": spec.mode,
        "completed_ic_history_count": len(history),
        "recent_rs120_ic_mean": rs,
        "recent_high52_ic_mean": h52,
        "recent_momentum_pair_ic_mean": mom,
        "gate_active": trigger,
        "target_exposure_if_active": SOFT_EXPOSURE,
        "year_2026_used_for_selection": False,
        "phase": "PRE2026_PRIMARY" if signal_day <= PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW",
    }


def build_gate_snaps(
    *, variant_id: str, variant_dir: Path,
) -> tuple[dict[str, list[v70.Snap]], list[dict[str, object]]]:
    base_snaps = v70.load_snaps(variant_dir / "v67_c3_monthly_rankings.csv.gz")
    training = v71._load_training(variant_dir / "v67_c3_training_rows.csv.gz")
    ic_months = v71._monthly_ics(training)
    result: dict[str, list[v70.Snap]] = {BASE_POLICY: list(base_snaps)}
    rows: list[dict[str, object]] = []
    for spec in GATES:
        gated: list[v70.Snap] = []
        for snap in base_snaps:
            state = gate_state(ic_months, snap.day, spec)
            rows.append({"variant_id": variant_id, **state})
            # v70 interprets snap.risk_on=True as 100% exposure and False as
            # Strategy.risk_off.  Here the flag is deliberately repurposed for
            # this isolated factor-health exposure ablation; ranking is unchanged.
            gated.append(v70.Snap(snap.day, snap.symbols, not bool(state["gate_active"])))
        result[spec.policy_id] = gated
    return result, rows


def _block_key(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 2


def _signflip(paired: Sequence[tuple[date, float]], repetitions: int, seed: int) -> tuple[float, float]:
    blocks: dict[tuple[int, int], list[float]] = {}
    for day, delta in paired:
        blocks.setdefault(_block_key(day), []).append(delta)
    observed = fmean(delta for _, delta in paired)
    block_values = [values for _, values in sorted(blocks.items())]
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


def _pre2026_daily_mdd(daily_rows: Sequence[Mapping[str, object]], *, variant: str, allocator: str, policy: str) -> float:
    values = [
        float(row["nav_close_vnd"])
        for row in daily_rows
        if str(row.get("variant_id")) == variant
        and str(row.get("allocator")) == allocator
        and str(row.get("policy_id")) == policy
        and str(row.get("cost_scenario")) == "BASE_DNSE"
        and str(row.get("settlement_mode")) == "IMMEDIATE"
        and str(row.get("day")) <= PRIMARY_SELECTION_END.isoformat()
    ]
    if len(values) < 20:
        raise ValueError(f"V73_TOO_FEW_PRE2026_DAILY_VALUES:{variant}:{allocator}:{policy}")
    return v70._mdd(values)


def candidate_inference(
    monthly_rows: Sequence[Mapping[str, object]], daily_rows: Sequence[Mapping[str, object]],
    *, signflip_samples: int, bootstrap_samples: int,
) -> list[dict[str, object]]:
    scopes = sorted({
        (str(row["variant_id"]), str(row["allocator"]))
        for row in monthly_rows
        if str(row.get("cost_scenario")) == "BASE_DNSE"
        and str(row.get("settlement_mode")) == "IMMEDIATE"
        and float(row.get("initial_capital_vnd") or 0.0) == 1_000_000_000.0
    })
    output: list[dict[str, object]] = []
    for variant, allocator in scopes:
        base: dict[tuple[str, str], Mapping[str, object]] = {}
        candidates: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {}
        for row in monthly_rows:
            if str(row.get("variant_id")) != variant or str(row.get("allocator")) != allocator:
                continue
            if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
                continue
            if float(row.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
                continue
            key = str(row["period_start_day"]), str(row["period_end_day"])
            policy = str(row["policy_id"])
            if policy == BASE_POLICY:
                base[key] = row
            else:
                candidates.setdefault(policy, {})[key] = row
        for policy, cmap in sorted(candidates.items()):
            paired: list[tuple[date, float]] = []
            annual_c: dict[int, float] = {}
            annual_b: dict[int, float] = {}
            for key in sorted(set(base) & set(cmap)):
                end = date.fromisoformat(key[1])
                if end > PRIMARY_SELECTION_END:
                    continue
                cr = float(cmap[key]["strategy_return"])
                br = float(base[key]["strategy_return"])
                paired.append((end, cr - br))
                annual_c[end.year] = annual_c.get(end.year, 1.0) * (1.0 + cr)
                annual_b[end.year] = annual_b.get(end.year, 1.0) * (1.0 + br)
            if len(paired) < 24:
                raise ValueError(f"V73_TOO_FEW_PRE2026_PAIRED_MONTHS:{variant}:{allocator}:{policy}")
            seed = abs(hash((variant, allocator, policy, "v73"))) & 0xFFFFFFFF
            observed, p = _signflip(paired, signflip_samples, seed)
            ci_low, ci_high = _bootstrap_ci(paired, bootstrap_samples, seed ^ 0x71373)
            years = sorted(set(annual_c) & set(annual_b))
            annual_delta = [(annual_c[y] - 1.0) - (annual_b[y] - 1.0) for y in years]
            base_mdd = _pre2026_daily_mdd(daily_rows, variant=variant, allocator=allocator, policy=BASE_POLICY)
            candidate_mdd = _pre2026_daily_mdd(daily_rows, variant=variant, allocator=allocator, policy=policy)
            deltas = [value for _, value in paired]
            output.append({
                "variant_id": variant,
                "allocator": allocator,
                "policy_id": policy,
                "comparator": BASE_POLICY,
                "selection_period_end": PRIMARY_SELECTION_END.isoformat(),
                "paired_month_count": len(paired),
                "block_count": len({_block_key(day) for day, _ in paired}),
                "mean_monthly_return_delta": observed,
                "median_monthly_return_delta": median(deltas),
                "positive_month_delta_rate": sum(value > 0.0 for value in deltas) / len(deltas),
                "bootstrap_ci025": ci_low,
                "bootstrap_ci975": ci_high,
                "signflip_two_sided_p": p,
                "pre2026_year_count": len(years),
                "positive_annual_delta_rate": sum(value > 0.0 for value in annual_delta) / len(annual_delta),
                "mean_annual_return_delta": fmean(annual_delta),
                "pre2026_base_mdd": base_mdd,
                "pre2026_candidate_mdd": candidate_mdd,
                "pre2026_mdd_improvement": candidate_mdd - base_mdd,
                "year_2026_used_for_selection": False,
                "post_selected_mechanism_audit": True,
            })
    _bh(output)
    for row in output:
        row["diagnostic_watchlist_gate_passed"] = bool(
            float(row["mean_monthly_return_delta"]) > 0.0
            and float(row["bh_fdr_q"]) < 0.10
            and float(row["bootstrap_ci025"]) > 0.0
            and float(row["positive_annual_delta_rate"]) >= 0.60
            and float(row["pre2026_mdd_improvement"]) >= -0.02
        )
    return output


def _shadow_2026(annual_rows: Sequence[Mapping[str, object]], monthly_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    annual_map: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for row in annual_rows:
        try:
            if int(float(row["year"])) != 2026:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
            continue
        if float(row.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
            continue
        annual_map[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]))] = row
    monthly_map: dict[tuple[str, str, str, str], Mapping[str, object]] = {}
    for row in monthly_rows:
        if str(row.get("cost_scenario")) != "BASE_DNSE" or str(row.get("settlement_mode")) != "IMMEDIATE":
            continue
        if float(row.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
            continue
        start = str(row.get("period_start_day"))
        if start.startswith("2026-"):
            monthly_map[(str(row["variant_id"]), str(row["allocator"]), str(row["policy_id"]), start[:7])] = row
    output: list[dict[str, object]] = []
    for key, row in sorted(annual_map.items()):
        variant, allocator, policy = key
        base = annual_map.get((variant, allocator, BASE_POLICY))
        if base is None:
            continue
        april = monthly_map.get((variant, allocator, policy, "2026-04"))
        base_april = monthly_map.get((variant, allocator, BASE_POLICY, "2026-04"))
        output.append({
            "variant_id": variant,
            "allocator": allocator,
            "policy_id": policy,
            "strategy_return": float(row["strategy_return"]),
            "benchmark_return": float(row["benchmark_return"]),
            "alpha_arithmetic": float(row["alpha_arithmetic"]),
            "policy_minus_base_2026_return": float(row["strategy_return"]) - float(base["strategy_return"]),
            "april_2026_return": float(april["strategy_return"]) if april else None,
            "april_2026_policy_minus_base": (
                float(april["strategy_return"]) - float(base_april["strategy_return"])
                if april and base_april else None
            ),
            "used_for_selection": False,
            "status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        })
    return output


def _cost_drag(summary_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, Mapping[str, object]]] = {}
    for row in summary_rows:
        if str(row.get("settlement_mode")) != "IMMEDIATE" or float(row.get("initial_capital_vnd") or 0.0) != 1_000_000_000.0:
            continue
        grouped.setdefault((str(row["variant_id"]), str(row["policy_id"]), str(row["allocator"])), {})[str(row["cost_scenario"])] = row
    output: list[dict[str, object]] = []
    for (variant, policy, allocator), scenarios in sorted(grouped.items()):
        gross = scenarios.get("GROSS")
        if gross is None:
            continue
        for name in ("BASE_DNSE", "STRESS", "SEVERE"):
            row = scenarios.get(name)
            if row is not None:
                output.append({
                    "variant_id": variant,
                    "policy_id": policy,
                    "allocator": allocator,
                    "cost_scenario": name,
                    "total_return_drag_vs_gross": float(row["total_return"]) - float(gross["total_return"]),
                    "cagr_drag_vs_gross": float(row["cagr"]) - float(gross["cagr"]),
                })
    return output


def _baseline_v70_summary(v70_output: Path) -> list[dict[str, str]]:
    rows = _read_csv(v70_output / "v70_backtest_summary.csv")
    return [
        row for row in rows
        if str(row.get("strategy_id")) in {"C3_EQ_ALWAYS", "C3_INVOL_ALWAYS"}
    ]


def _audit_baseline(v70_rows: Sequence[Mapping[str, object]], v73_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    v70_map: dict[tuple[str, str, str, str, float], Mapping[str, object]] = {}
    for row in v70_rows:
        allocator = "EQUAL" if str(row["strategy_id"]) == "C3_EQ_ALWAYS" else "INVOL60"
        key = (str(row["variant_id"]), allocator, str(row["settlement_mode"]), str(row["cost_scenario"]), float(row["initial_capital_vnd"]))
        v70_map[key] = row
    compared = 0
    max_return = max_cagr = max_mdd = 0.0
    for row in v73_rows:
        if str(row.get("policy_id")) != BASE_POLICY:
            continue
        key = (str(row["variant_id"]), str(row["allocator"]), str(row["settlement_mode"]), str(row["cost_scenario"]), float(row["initial_capital_vnd"]))
        old = v70_map.get(key)
        if old is None:
            continue
        compared += 1
        max_return = max(max_return, abs(float(row["total_return"]) - float(old["total_return"])))
        max_cagr = max(max_cagr, abs(float(row["cagr"]) - float(old["cagr"])))
        max_mdd = max(max_mdd, abs(float(row["max_drawdown_daily"]) - float(old["max_drawdown_daily"])))
    if compared < 24 or max(max_return, max_cagr, max_mdd) > 1e-10:
        raise ValueError(f"V73_BASELINE_RECONSTRUCTION_DRIFT:{compared}:{max_return}:{max_cagr}:{max_mdd}")
    return {
        "compared_summary_count": compared,
        "max_total_return_error": max_return,
        "max_cagr_error": max_cagr,
        "max_mdd_error": max_mdd,
    }


def analyze(
    *, v68_output: Path, v70_output: Path, store: Path, output_dir: Path,
    signflip_samples: int = SIGNFLIP_SAMPLES, bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, object]:
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V73_V68_VARIANTS_MISSING")
    v70_report = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if v70_report.get("status") != "SUCCESS" or v70_report.get("champion_model") != CHAMPION_MODEL:
        raise ValueError("V73_V70_BASELINE_CONTRACT_INVALID")

    variant_dirs = sorted(path for path in variants_root.iterdir() if path.is_dir())
    snap_maps: dict[str, dict[str, list[v70.Snap]]] = {}
    gate_rows: list[dict[str, object]] = []
    symbols: set[str] = set()
    for variant_dir in variant_dirs:
        built, rows = build_gate_snaps(variant_id=variant_dir.name, variant_dir=variant_dir)
        snap_maps[variant_dir.name] = built
        gate_rows.extend(rows)
        for snap in built[BASE_POLICY]:
            symbols.update(snap.symbols)
    if not symbols:
        raise ValueError("V73_NO_SYMBOLS")
    market = v70.load_market(store, symbols)

    summary_rows: list[dict[str, object]] = []
    monthly_rows: list[dict[str, object]] = []
    annual_rows: list[dict[str, object]] = []
    rolling_rows: list[dict[str, object]] = []
    daily_rows: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    capital_rows: list[dict[str, object]] = []

    policy_exposure = {BASE_POLICY: 1.0, **{spec.policy_id: SOFT_EXPOSURE for spec in GATES}}
    for variant, policy_map in sorted(snap_maps.items()):
        for policy_id, snaps in policy_map.items():
            for allocator in ("EQUAL", "INVOL60"):
                exposure = policy_exposure[policy_id]
                for cost in v70.COSTS:
                    spec = v70.Strategy(f"V73_{policy_id}_{allocator}", allocator, exposure)
                    result = v70.simulate(market, snaps, spec, cost, 1_000_000_000.0, variant)
                    summary_rows += _decorate([result["summary"]], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    monthly_rows += _decorate(result["periods"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    annual_rows += _decorate(result["annual"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    rolling_rows += _decorate(result["rolling"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                    if cost.name == "BASE_DNSE":
                        daily_rows += _decorate(result["daily"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                        ledger_rows += _decorate(result["ledger"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                        missing_rows += _decorate(result["missing"], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario=cost.name, capital=1_000_000_000.0)
                t2_spec = v70.Strategy(f"V73_{policy_id}_{allocator}_T2", allocator, exposure, "T2_NO_ADVANCE")
                t2 = v70.simulate(market, snaps, t2_spec, v70.COSTS[1], 1_000_000_000.0, variant)
                summary_rows += _decorate([t2["summary"]], variant=variant, policy_id=policy_id, allocator=allocator, settlement="T2_NO_ADVANCE", cost_scenario="BASE_DNSE", capital=1_000_000_000.0)
                for capital in CAPITALS:
                    spec = v70.Strategy(f"V73_{policy_id}_{allocator}_CAP", allocator, exposure)
                    cap_result = v70.simulate(market, snaps, spec, v70.COSTS[1], capital, variant)
                    capital_rows += _decorate([cap_result["summary"]], variant=variant, policy_id=policy_id, allocator=allocator, settlement="IMMEDIATE", cost_scenario="BASE_DNSE", capital=capital)

    baseline_audit = _audit_baseline(_baseline_v70_summary(v70_output), summary_rows)
    inference = candidate_inference(monthly_rows, daily_rows, signflip_samples=signflip_samples, bootstrap_samples=bootstrap_samples)
    shadow = _shadow_2026(annual_rows, monthly_rows)
    cost_drag = _cost_drag(summary_rows)
    watchlist = [row for row in inference if bool(row.get("diagnostic_watchlist_gate_passed"))]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v73_factor_health_state.csv", gate_rows)
    _write_csv(output_dir / "v73_backtest_summary.csv", summary_rows)
    _write_csv(output_dir / "v73_monthly_returns.csv", monthly_rows)
    _write_csv(output_dir / "v73_annual_returns.csv", annual_rows)
    _write_csv(output_dir / "v73_rolling_alpha.csv", rolling_rows)
    _write_csv(output_dir / "v73_candidate_inference.csv", inference)
    _write_csv(output_dir / "v73_2026_shadow.csv", shadow)
    _write_csv(output_dir / "v73_cost_drag.csv", cost_drag)
    _write_csv(output_dir / "v73_capital_sensitivity.csv", capital_rows)
    _write_csv(output_dir / "v73_missing_price_events.csv", missing_rows)
    _write_gz(output_dir / "v73_trade_ledger_base.csv.gz", ledger_rows)
    _write_gz(output_dir / "v73_daily_equity_base.csv.gz", daily_rows)

    profit_table = [{
        "variant_id": str(row["variant_id"]),
        "allocator": str(row["allocator"]),
        "policy_id": str(row["policy_id"]),
        "total_return": float(row["total_return"]),
        "benchmark_total_return": float(row["benchmark_total_return"]),
        "total_alpha_arithmetic": float(row["total_alpha_arithmetic"]),
        "cagr": float(row["cagr"]),
        "max_drawdown_daily": float(row["max_drawdown_daily"]),
        "trade_count": int(float(row["trade_count"])),
        "modeled_cost_drag_vs_initial": float(row["modeled_cost_drag_vs_initial"]),
    } for row in summary_rows
      if str(row.get("cost_scenario")) == "BASE_DNSE"
      and str(row.get("settlement_mode")) == "IMMEDIATE"
      and float(row.get("initial_capital_vnd") or 0.0) == 1_000_000_000.0]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "components_changed": False,
        "ranking_changed": False,
        "c3_training_label": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE",
        "candidate_gates": [
            {"policy_id": spec.policy_id, "window": spec.window, "mode": spec.mode, "risk_exposure": SOFT_EXPOSURE}
            for spec in GATES
        ],
        "factor_health_source": "V67_MONTHLY_COMPONENT_IC_WITH_LABEL_END_BEFORE_SIGNAL",
        "primary_candidate_selection_end": PRIMARY_SELECTION_END.isoformat(),
        "year_2026_used_for_candidate_selection": False,
        "year_2026_status": "OBSERVED_STRESS_NOT_SELECTION_SET",
        "post_selected_mechanism_audit": True,
        "signflip_samples": signflip_samples,
        "bootstrap_samples_ci_only": bootstrap_samples,
        "inference_dependence_unit": "CONTIGUOUS_TWO_CALENDAR_MONTH_BLOCKS",
        "multiple_testing": "BH_FDR_WITHIN_VARIANT_AND_ALLOCATOR",
        "portfolio_engine_reused": "deep_portfolio_backtest_v70",
        "portfolio_execution": "MONTHLY_FROZEN_C3_TOP10_ACTUAL_SHARES_NEXT_OPEN",
        "allocators": ["EQUAL", "INVOL60"],
        "cost_scenarios": [cost.name for cost in v70.COSTS],
        "capital_sensitivity_vnd": list(CAPITALS),
        "t2_no_advance_sensitivity": True,
        "baseline_reconstruction_audit": baseline_audit,
        "diagnostic_watchlist": watchlist,
        "diagnostic_watchlist_count": len(watchlist),
        "weekly_overlays_combined": False,
        "adaptive_weight_combined": False,
        "macro_included": False,
        "profit_reporting": {
            "report_type": "MODELED_COST_DEEP_BACKTEST",
            "profit_table": profit_table,
            "equity_curve_output": "v73_daily_equity_base.csv.gz",
            "costs_included": True,
            "exact_cash_ledger": False,
            "sector_cap_enforced": False,
        },
        "limitations": [
            "Factor-health gates were designed after historical V70/V71/V72 review and are post-selected mechanism audits, not pristine independent holdouts.",
            "2026 is excluded from candidate inference and is reported only as observed stress.",
            "PIT HOSE, price-basis/corporate-action and PIT-sector data gates remain unresolved for canonical HOSE claims.",
            "V73 changes exposure only; frozen C3 ranking, components and label semantics remain unchanged.",
            "Modeled costs/fixed slippage are research assumptions rather than exact broker market impact.",
        ],
        "research_only": True,
        "promotion_authorized": False,
        "automatic_live_orders_allowed": False,
    }
    (output_dir / "v73_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signflip-samples", type=int, default=SIGNFLIP_SAMPLES)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    args = parser.parse_args(argv)
    report = analyze(
        v68_output=args.v68_output,
        v70_output=args.v70_output,
        store=args.store,
        output_dir=args.output_dir,
        signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples,
    )
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
