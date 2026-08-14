"""V65 robustness audit for the frozen V64 multi-signal cohort matrix.

Research only. Reads V64 outputs, performs dependence-aware robustness checks,
multiple-testing correction, overlap diagnostics, canonical freshness audit, and
shadow signal-state reconstruction that does not require future outcomes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
import random
from statistics import fmean, median
from typing import Iterable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import _v64_cohort_contract as contract

SCHEMA_VERSION = "c3_multisignal_robustness_v65"
BOOTSTRAP_REPS_DEFAULT = 10000
RANDOM_SEED = 20260814
LIVE_MODEL_CHANGE_AUTHORIZED = False
AUTOMATIC_LIVE_ORDERS_ALLOWED = False


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _f(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    if value in (None, ""):
        return default
    return float(value)


def _i(row: Mapping[str, object], key: str, default: int = 0) -> int:
    value = row.get(key)
    if value in (None, ""):
        return default
    return int(float(value))


def _b(row: Mapping[str, object], key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in {"1", "true", "yes"}


def _outcome(row: Mapping[str, object]) -> float:
    return -_f(row, "forward_return") if row["kind"] == "RISK" else _f(row, "forward_excess_return")


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round(q * (len(ordered) - 1)))
    return ordered[max(0, min(idx, len(ordered) - 1))]


def _cluster_groups(rows: Sequence[Mapping[str, object]], cluster_field: str) -> list[list[float]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(str(row[cluster_field]), []).append(_outcome(row))
    return list(grouped.values())


def cluster_bootstrap(rows: Sequence[Mapping[str, object]], *, cluster_field: str, reps: int, seed: int) -> dict[str, float]:
    groups = _cluster_groups(rows, cluster_field)
    if not groups:
        return {"mean_low": 0.0, "mean_mid": 0.0, "mean_high": 0.0, "median_low": 0.0, "median_mid": 0.0, "median_high": 0.0}
    rng = random.Random(seed)
    means: list[float] = []
    medians: list[float] = []
    n = len(groups)
    for _ in range(reps):
        values: list[float] = []
        for _ in range(n):
            values.extend(groups[rng.randrange(n)])
        means.append(fmean(values))
        medians.append(median(values))
    return {
        "mean_low": _quantile(means, 0.025), "mean_mid": _quantile(means, 0.50), "mean_high": _quantile(means, 0.975),
        "median_low": _quantile(medians, 0.025), "median_mid": _quantile(medians, 0.50), "median_high": _quantile(medians, 0.975),
    }


def cluster_signflip_p(rows: Sequence[Mapping[str, object]], *, cluster_field: str, reps: int, seed: int) -> float:
    groups = _cluster_groups(rows, cluster_field)
    if not groups:
        return 1.0
    cluster_means = [fmean(group) for group in groups]
    observed = fmean(cluster_means)
    rng = random.Random(seed)
    ge = 0
    for _ in range(reps):
        simulated = fmean(value * (1.0 if rng.random() >= 0.5 else -1.0) for value in cluster_means)
        if simulated >= observed:
            ge += 1
    return (ge + 1.0) / (reps + 1.0)


def bh_adjust(rows: Sequence[Mapping[str, object]], *, p_field: str = "p_value") -> dict[str, float]:
    ordered = sorted(((str(row["cohort_id"]), float(row[p_field])) for row in rows), key=lambda x: x[1])
    m = len(ordered)
    raw = [min(1.0, p * m / (index + 1)) for index, (_, p) in enumerate(ordered)]
    adjusted = raw[:]
    for index in range(m - 2, -1, -1):
        adjusted[index] = min(adjusted[index], adjusted[index + 1])
    return {ordered[index][0]: adjusted[index] for index in range(m)}


def canonical_freshness(features: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    pairs = sorted({(str(row["evaluation_day"]), str(row["canonical_day"])) for row in features})
    output = []
    for evaluation_text, canonical_text in pairs:
        evaluation = date.fromisoformat(evaluation_text)
        canonical = date.fromisoformat(canonical_text)
        month_gap = (evaluation.year - canonical.year) * 12 + evaluation.month - canonical.month
        output.append({"evaluation_day": evaluation_text, "canonical_day": canonical_text, "calendar_age_days": (evaluation - canonical).days, "month_gap": month_gap, "canonical_stale_for_monthly_context": month_gap > 1})
    return output


def shadow_signal_state(features: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    ordered = sorted(features, key=lambda row: (str(row["evaluation_day"]), str(row["symbol"])))
    prior_by_symbol: dict[str, dict[str, object]] = {}
    output: list[dict[str, object]] = []
    for raw in ordered:
        feature = dict(raw)
        for key in ("canonical_rank", "preview_rank", "prior_preview_rank", "rank_delta"):
            feature[key] = _i(raw, key)
        for key in ("score_delta", "distance_ma20", "distance_ma50", "return_5", "return_10", "return_20", "relative_5", "relative_10", "relative_20", "drawdown_20", "drawdown_60", "volume_ratio_5_20", "realized_vol_ratio_20_60", "breakout_20_gap", "breakdown_20_low_gap"):
            feature[key] = _f(raw, key)
        feature["risk_on"] = _b(raw, "risk_on")
        symbol = str(raw["symbol"])
        prior = prior_by_symbol.get(symbol)
        matches = [cohort.cohort_id for cohort in contract.ALL_COHORTS if contract.cohort_matches(cohort.cohort_id, feature, prior)]
        if str(raw.get("phase")) == "SHADOW_ONLY":
            output.append({"evaluation_day": raw["evaluation_day"], "canonical_day": raw["canonical_day"], "symbol": symbol, "canonical_rank": feature["canonical_rank"], "preview_rank": feature["preview_rank"], "prior_preview_rank": feature["prior_preview_rank"], "distance_ma20": feature["distance_ma20"], "distance_ma50": feature["distance_ma50"], "relative_5": feature["relative_5"], "relative_20": feature["relative_20"], "drawdown_20": feature["drawdown_20"], "volume_ratio_5_20": feature["volume_ratio_5_20"], "realized_vol_ratio_20_60": feature["realized_vol_ratio_20_60"], "breakout_20_gap": feature["breakout_20_gap"], "matched_cohort_count": len(matches), "matched_cohorts": "|".join(matches)})
        prior_by_symbol[symbol] = feature
    return output


def overlap_diagnostics(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    states: dict[str, set[tuple[str, str]]] = {}
    kinds: dict[str, str] = {}
    for row in events:
        if str(row["phase"]) != "HISTORICAL_SELECTION" or _i(row, "horizon") != 10:
            continue
        cohort = str(row["cohort_id"])
        states.setdefault(cohort, set()).add((str(row["evaluation_day"]), str(row["symbol"])))
        kinds[cohort] = str(row["kind"])
    output: list[dict[str, object]] = []
    ids = sorted(states)
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            if kinds[left] != kinds[right]:
                continue
            a, b = states[left], states[right]
            union = a | b
            jaccard = len(a & b) / len(union) if union else 0.0
            if jaccard >= 0.30:
                output.append({"kind": kinds[left], "left_cohort": left, "right_cohort": right, "left_states": len(a), "right_states": len(b), "intersection_states": len(a & b), "jaccard": jaccard})
    return sorted(output, key=lambda row: (-float(row["jaccard"]), str(row["left_cohort"]), str(row["right_cohort"])))


def dependency_diagnostics(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in events:
        if str(row["phase"]) == "HISTORICAL_SELECTION" and _i(row, "horizon") == 10:
            grouped.setdefault(str(row["cohort_id"]), []).append(row)
    output = []
    for cohort_id, rows in sorted(grouped.items()):
        symbols: dict[str, int] = {}
        by_symbol_dates: dict[str, list[date]] = {}
        for row in rows:
            symbol = str(row["symbol"])
            symbols[symbol] = symbols.get(symbol, 0) + 1
            by_symbol_dates.setdefault(symbol, []).append(date.fromisoformat(str(row["evaluation_day"])))
        counts = sorted(symbols.values(), reverse=True)
        repeated = 0
        for days in by_symbol_dates.values():
            days = sorted(days)
            repeated += sum((days[i] - days[i - 1]).days <= 8 for i in range(1, len(days)))
        output.append({"cohort_id": cohort_id, "kind": str(rows[0]["kind"]), "event_count": len(rows), "unique_week_count": len({str(row["evaluation_day"]) for row in rows}), "unique_symbol_count": len(symbols), "top5_symbol_share": sum(counts[:5]) / len(rows), "top10_symbol_share": sum(counts[:10]) / len(rows), "consecutive_week_repeat_share": repeated / len(rows)})
    return output


def yearly_diagnostics(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[float]] = {}
    kinds: dict[str, str] = {}
    for row in events:
        if str(row["phase"]) != "HISTORICAL_SELECTION" or _i(row, "horizon") != 10:
            continue
        year = date.fromisoformat(str(row["evaluation_day"])).year
        cohort = str(row["cohort_id"])
        grouped.setdefault((cohort, year), []).append(_outcome(row))
        kinds[cohort] = str(row["kind"])
    output = []
    for (cohort, year), values in sorted(grouped.items()):
        output.append({"cohort_id": cohort, "kind": kinds[cohort], "year": year, "event_count": len(values), "mean_outcome": fmean(values), "median_outcome": median(values), "hit_rate": sum(value > 0 for value in values) / len(values)})
    return output


def risk_diagnostics(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output = []
    for cohort in contract.RISK_COHORTS:
        for horizon in (5, 10):
            rows = [row for row in events if row["phase"] == "HISTORICAL_SELECTION" and row["cohort_id"] == cohort.cohort_id and _i(row, "horizon") == horizon]
            if not rows:
                continue
            returns = [_f(row, "forward_return") for row in rows]
            output.append({"cohort_id": cohort.cohort_id, "horizon": horizon, "event_count": len(rows), "mean_forward_return": fmean(returns), "median_forward_return": median(returns), "rebound_positive_rate": sum(value > 0 for value in returns) / len(returns), "loss_5pct_rate": sum(value <= -0.05 for value in returns) / len(returns), "loss_10pct_rate": sum(value <= -0.10 for value in returns) / len(returns), "median_adverse_excursion_10": median(_f(row, "adverse_excursion_10") for row in rows)})
    return output


def leader_incremental(events: Sequence[Mapping[str, object]], *, reps: int) -> list[dict[str, object]]:
    raw_rows = [row for row in events if row["phase"] == "HISTORICAL_SELECTION" and row["cohort_id"] == "L01_TOP5_RAW" and _i(row, "horizon") == 10]
    raw_map = {(str(row["evaluation_day"]), str(row["symbol"])): row for row in raw_rows}
    output = []
    for cohort in contract.LEADER_COHORTS:
        if cohort.cohort_id == "L01_TOP5_RAW":
            continue
        rows = [row for row in events if row["phase"] == "HISTORICAL_SELECTION" and row["cohort_id"] == cohort.cohort_id and _i(row, "horizon") == 10]
        keys = {(str(row["evaluation_day"]), str(row["symbol"])) for row in rows}
        subset = [raw_map[key] for key in keys if key in raw_map]
        complement = [row for key, row in raw_map.items() if key not in keys]
        matched: dict[str, dict[str, list[float]]] = {}
        for row in subset:
            matched.setdefault(str(row["evaluation_day"]), {"subset": [], "other": []})["subset"].append(_f(row, "forward_excess_return"))
        for row in complement:
            matched.setdefault(str(row["evaluation_day"]), {"subset": [], "other": []})["other"].append(_f(row, "forward_excess_return"))
        diffs = [fmean(groups["subset"]) - fmean(groups["other"]) for groups in matched.values() if groups["subset"] and groups["other"]]
        p_value = 1.0
        if diffs:
            observed = fmean(diffs)
            rng = random.Random(RANDOM_SEED + sum(ord(ch) for ch in cohort.cohort_id))
            ge = 0
            for _ in range(reps):
                simulated = fmean(value * (1 if rng.random() >= 0.5 else -1) for value in diffs)
                if simulated >= observed:
                    ge += 1
            p_value = (ge + 1) / (reps + 1)
        output.append({"cohort_id": cohort.cohort_id, "event_count": len(rows), "raw_top5_overlap_count": len(subset), "raw_top5_overlap_rate": len(subset) / len(rows) if rows else 0.0, "subset_mean_excess": fmean(_f(row, "forward_excess_return") for row in subset) if subset else 0.0, "raw_complement_mean_excess": fmean(_f(row, "forward_excess_return") for row in complement) if complement else 0.0, "matched_week_count": len(diffs), "matched_week_mean_incremental": fmean(diffs) if diffs else 0.0, "matched_week_median_incremental": median(diffs) if diffs else 0.0, "matched_week_signflip_p": p_value})
    return output


def robustness_table(events: Sequence[Mapping[str, object]], v64_metrics: Sequence[Mapping[str, object]], dependency: Sequence[Mapping[str, object]], *, reps: int) -> list[dict[str, object]]:
    metric_map = {(str(row["cohort_id"]), _i(row, "horizon")): row for row in v64_metrics}
    dep_map = {str(row["cohort_id"]): row for row in dependency}
    rows_out = []
    for index, cohort in enumerate(contract.ALL_COHORTS):
        rows = [row for row in events if row["phase"] == "HISTORICAL_SELECTION" and row["cohort_id"] == cohort.cohort_id and _i(row, "horizon") == 10]
        if not rows:
            continue
        week_ci = cluster_bootstrap(rows, cluster_field="evaluation_day", reps=reps, seed=RANDOM_SEED + index)
        symbol_ci = cluster_bootstrap(rows, cluster_field="symbol", reps=reps, seed=RANDOM_SEED + 1000 + index)
        p = cluster_signflip_p(rows, cluster_field="evaluation_day", reps=reps, seed=RANDOM_SEED + 2000 + index)
        metric = metric_map[(cohort.cohort_id, 10)]
        rows_out.append({"cohort_id": cohort.cohort_id, "kind": cohort.kind, "family": cohort.family, "event_count": len(rows), "mean_outcome": _f(metric, "mean_outcome"), "median_outcome": _f(metric, "median_outcome"), "hit_rate": _f(metric, "hit_rate"), "year_positive_rate": _f(metric, "year_positive_rate"), "era_positive_rate": _f(metric, "era_positive_rate"), "week_boot_mean_low": week_ci["mean_low"], "week_boot_mean_high": week_ci["mean_high"], "week_boot_median_low": week_ci["median_low"], "week_boot_median_high": week_ci["median_high"], "symbol_boot_mean_low": symbol_ci["mean_low"], "symbol_boot_mean_high": symbol_ci["mean_high"], "symbol_boot_median_low": symbol_ci["median_low"], "symbol_boot_median_high": symbol_ci["median_high"], "p_value": p, "top5_symbol_share": _f(dep_map.get(cohort.cohort_id, {}), "top5_symbol_share"), "consecutive_week_repeat_share": _f(dep_map.get(cohort.cohort_id, {}), "consecutive_week_repeat_share")})
    for kind in ("RISK", "LEADER"):
        group = [row for row in rows_out if row["kind"] == kind]
        q_map = bh_adjust(group)
        for row in group:
            row["bh_q_within_kind"] = q_map[row["cohort_id"]]
    for row in rows_out:
        robust = (int(row["event_count"]) >= 100 and float(row["week_boot_mean_low"]) > 0.0 and float(row["symbol_boot_mean_low"]) > 0.0 and float(row["bh_q_within_kind"]) <= 0.10 and float(row["median_outcome"]) > 0.0 and float(row["year_positive_rate"]) >= 0.60 and float(row["era_positive_rate"]) >= 0.75)
        row["robust_historical_mechanism"] = robust
        row["promotion_authorized"] = False
    return sorted(rows_out, key=lambda row: (not bool(row["robust_historical_mechanism"]), float(row["bh_q_within_kind"]), -float(row["mean_outcome"])))


def run_audit(*, v64_dir: Path, output_dir: Path, output_zip: Path, bootstrap_reps: int = BOOTSTRAP_REPS_DEFAULT) -> dict[str, object]:
    features = _read_csv(v64_dir / "v64_features.csv")
    events = _read_csv(v64_dir / "v64_cohort_events.csv")
    metrics = _read_csv(v64_dir / "v64_historical_metrics.csv")
    freshness = canonical_freshness(features)
    shadow_state = shadow_signal_state(features)
    overlap = overlap_diagnostics(events)
    dependency = dependency_diagnostics(events)
    yearly = yearly_diagnostics(events)
    risk = risk_diagnostics(events)
    incremental = leader_incremental(events, reps=bootstrap_reps)
    robust = robustness_table(events, metrics, dependency, reps=bootstrap_reps)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v65_canonical_freshness.csv", freshness)
    _write_csv(output_dir / "v65_shadow_signal_state.csv", shadow_state)
    _write_csv(output_dir / "v65_overlap_pairs.csv", overlap)
    _write_csv(output_dir / "v65_dependency.csv", dependency)
    _write_csv(output_dir / "v65_yearly_h10.csv", yearly)
    _write_csv(output_dir / "v65_risk_false_positive.csv", risk)
    _write_csv(output_dir / "v65_leader_incremental_vs_raw_top5.csv", incremental)
    _write_csv(output_dir / "v65_robustness_h10.csv", robust)
    focus = [row for row in shadow_state if row["symbol"] in contract.SHADOW_FOCUS_SYMBOLS]
    _write_csv(output_dir / "v65_shadow_focus_vpi_tlg_baf_state.csv", focus)
    robust_ids = [row["cohort_id"] for row in robust if bool(row["robust_historical_mechanism"])]
    stale_shadow = [row for row in freshness if bool(row["canonical_stale_for_monthly_context"]) and date.fromisoformat(str(row["evaluation_day"])) > contract.SELECTION_END_DEFAULT]
    report = {"schema_version": SCHEMA_VERSION, "status": "SUCCESS", "bootstrap_reps": bootstrap_reps, "random_seed": RANDOM_SEED, "cohort_count": len(contract.ALL_COHORTS), "multiple_testing": "BH_FDR_WITHIN_KIND_ON_WEEK_CLUSTER_SIGNFLIP_P", "week_cluster_bootstrap": True, "symbol_cluster_bootstrap": True, "overlap_diagnostics": True, "leader_incremental_vs_raw_top5": True, "risk_false_positive_diagnostics": True, "shadow_signal_state_does_not_require_future_outcomes": True, "shadow_focus_symbols": list(contract.SHADOW_FOCUS_SYMBOLS), "robust_historical_mechanisms": robust_ids, "robust_historical_mechanism_count": len(robust_ids), "shadow_canonical_stale": bool(stale_shadow), "shadow_stale_rows": stale_shadow, "research_only": True, "live_model_change_authorized": LIVE_MODEL_CHANGE_AUTHORIZED, "automatic_live_orders_allowed": AUTOMATIC_LIVE_ORDERS_ALLOWED, "limitations": ["no pristine untouched holdout remains after V60+", "V65 reuses the already-observed historical archive and therefore grades robustness, not fresh out-of-sample alpha", "point-in-time universe lineage remains incomplete", "price basis and corporate actions remain incompletely verified", "portfolio sizing and simultaneous gate interactions remain deferred"]}
    (output_dir / "v65_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        for file in sorted(output_dir.iterdir()):
            if file.is_file():
                archive.write(file, arcname=file.name)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v64-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--bootstrap-reps", type=int, default=BOOTSTRAP_REPS_DEFAULT)
    args = parser.parse_args(argv)
    report = run_audit(v64_dir=args.v64_dir, output_dir=args.output_dir, output_zip=args.output_zip, bootstrap_reps=args.bootstrap_reps)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
