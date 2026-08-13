"""V64 multi-signal weekly cohort research for C3.

This module studies historical risk-deterioration and emerging-leader cohorts.
It does not create portfolio actions or orders. Every outcome starts from the
next session open after a completed weekly observation. August 2026 is shadow
only and excluded from historical candidate selection.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import _v64_cohort_contract as contract
from . import c3_short_horizon_v60 as v60
from . import weekly_micro_capital_v43 as v43

SCHEMA_VERSION = contract.SCHEMA_VERSION
SELECTION_END_DEFAULT = contract.SELECTION_END_DEFAULT
ANALYSIS_END_DEFAULT = contract.ANALYSIS_END_DEFAULT
TURNOVER_IS_VETO = contract.TURNOVER_IS_VETO
LIVE_MODEL_CHANGE_AUTHORIZED = contract.LIVE_MODEL_CHANGE_AUTHORIZED
RISK_COHORTS = contract.RISK_COHORTS
LEADER_COHORTS = contract.LEADER_COHORTS
ALL_COHORTS = contract.ALL_COHORTS
cohort_matches = contract.cohort_matches


def _safe_mean(values: Sequence[float]) -> float:
    return fmean(values) if values else 0.0


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = fmean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def _close_series(market: v60.Market, symbol: str, days: Sequence[date]) -> list[float] | None:
    values: list[float] = []
    for day in days:
        value = market.stock_close.get((symbol, day))
        if value is None or value <= 0:
            return None
        values.append(float(value))
    return values


def _lag_return(market: v60.Market, symbol: str, calendar: Sequence[date], pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = market.stock_close.get((symbol, calendar[pos]))
    old = market.stock_close.get((symbol, calendar[pos - lag]))
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def _index_lag_return(market: v60.Market, calendar: Sequence[date], pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = market.index_close.get(calendar[pos])
    old = market.index_close.get(calendar[pos - lag])
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def build_feature_row(*, symbol: str, evaluation_day: date, canonical: v43.SignalSnapshot, preview_rank: Mapping[str, int], preview_score: Mapping[str, float], prior_rank: Mapping[str, int], prior_score: Mapping[str, float], market: v60.Market, calendar_index: Mapping[date, int]) -> dict[str, object] | None:
    pos = calendar_index.get(evaluation_day)
    if pos is None or pos < 60:
        return None
    calendar = market.calendar
    close = market.stock_close.get((symbol, evaluation_day))
    if close is None or close <= 0:
        return None
    close = float(close)
    days20 = calendar[pos - 19 : pos + 1]
    days50 = calendar[pos - 49 : pos + 1]
    days60 = calendar[pos - 59 : pos + 1]
    prior20 = calendar[pos - 20 : pos]
    closes20 = _close_series(market, symbol, days20)
    closes50 = _close_series(market, symbol, days50)
    closes60 = _close_series(market, symbol, days60)
    closes_prior20 = _close_series(market, symbol, prior20)
    if not closes20 or not closes50 or not closes60 or not closes_prior20:
        return None
    r5 = _lag_return(market, symbol, calendar, pos, 5)
    r10 = _lag_return(market, symbol, calendar, pos, 10)
    r20 = _lag_return(market, symbol, calendar, pos, 20)
    i5 = _index_lag_return(market, calendar, pos, 5)
    i10 = _index_lag_return(market, calendar, pos, 10)
    i20 = _index_lag_return(market, calendar, pos, 20)
    if None in (r5, r10, r20, i5, i10, i20):
        return None
    vols5 = [float(market.stock_volume.get((symbol, day), 0)) for day in calendar[pos - 4 : pos + 1]]
    vols20 = [float(market.stock_volume.get((symbol, day), 0)) for day in days20]
    avg20vol = _safe_mean(vols20)
    volume_ratio = _safe_mean(vols5) / avg20vol if avg20vol > 0 else 0.0
    returns60 = [closes60[i] / closes60[i - 1] - 1.0 for i in range(1, len(closes60))]
    vol60 = _sample_std(returns60)
    vol20 = _sample_std(returns60[-19:])
    vol_ratio = vol20 / vol60 if vol60 > 0 else 0.0
    current_rank = int(preview_rank.get(symbol, 10**9))
    old_rank = int(prior_rank.get(symbol, 10**9))
    current_score = preview_score.get(symbol)
    old_score = prior_score.get(symbol)
    rank_delta = current_rank - old_rank if current_rank < 10**8 and old_rank < 10**8 else 0
    score_delta = float(current_score) - float(old_score) if current_score is not None and old_score is not None else 0.0
    try:
        canonical_rank = list(canonical.ranking).index(symbol) + 1
    except ValueError:
        canonical_rank = 10**9
    ma20 = _safe_mean(closes20)
    ma50 = _safe_mean(closes50)
    return {
        "evaluation_day": evaluation_day.isoformat(), "symbol": symbol, "canonical_rank": canonical_rank,
        "preview_rank": current_rank, "prior_preview_rank": old_rank, "rank_delta": rank_delta,
        "preview_score": float(current_score) if current_score is not None else None,
        "prior_preview_score": float(old_score) if old_score is not None else None, "score_delta": score_delta,
        "distance_ma20": close / ma20 - 1.0 if ma20 > 0 else 0.0,
        "distance_ma50": close / ma50 - 1.0 if ma50 > 0 else 0.0,
        "return_5": float(r5), "return_10": float(r10), "return_20": float(r20),
        "relative_5": float(r5) - float(i5), "relative_10": float(r10) - float(i10), "relative_20": float(r20) - float(i20),
        "drawdown_20": close / max(closes20) - 1.0, "drawdown_60": close / max(closes60) - 1.0,
        "volume_ratio_5_20": volume_ratio, "realized_vol_ratio_20_60": vol_ratio,
        "breakout_20_gap": close / max(closes_prior20) - 1.0, "breakdown_20_low_gap": close / min(closes_prior20) - 1.0,
        "risk_on": bool(canonical.risk_on),
    }


def forward_outcomes(*, symbol: str, evaluation_day: date, market: v60.Market, calendar_index: Mapping[date, int]) -> dict[int, dict[str, float]]:
    pos = calendar_index.get(evaluation_day)
    if pos is None or pos + 1 >= len(market.calendar):
        return {}
    start_day = market.calendar[pos + 1]
    start = market.stock_open.get((symbol, start_day))
    index_start = market.index_open.get(start_day)
    if start is None or start <= 0 or index_start is None or index_start <= 0:
        return {}
    start = float(start)
    index_start = float(index_start)
    path_marks: list[float] = []
    for idx in range(pos + 1, min(pos + 11, len(market.calendar))):
        value = market.stock_close.get((symbol, market.calendar[idx]))
        if value is not None and value > 0:
            path_marks.append(float(value))
    adverse_10 = min((mark / start - 1.0 for mark in path_marks), default=0.0)
    favorable_10 = max((mark / start - 1.0 for mark in path_marks), default=0.0)
    result: dict[int, dict[str, float]] = {}
    for horizon in contract.HORIZONS:
        end_pos = pos + 1 + horizon
        if end_pos >= len(market.calendar):
            continue
        end_day = market.calendar[end_pos]
        end = market.stock_open.get((symbol, end_day))
        index_end = market.index_open.get(end_day)
        if end is None or end <= 0 or index_end is None or index_end <= 0:
            continue
        gross_return = float(end) / start - 1.0
        index_return = float(index_end) / index_start - 1.0
        result[horizon] = {
            "forward_return": gross_return,
            "forward_excess_return": gross_return - index_return,
            "negative_forward_return_magnitude": -gross_return,
            "adverse_excursion_10": adverse_10,
            "favorable_excursion_10": favorable_10,
        }
    return result


def _future_canonical_label(symbol: str, evaluation_day: date, snapshots: Sequence[v43.SignalSnapshot]) -> tuple[bool, str | None]:
    for snapshot in [item for item in snapshots if item.day > evaluation_day][:2]:
        if symbol in set(snapshot.ranking[:10]):
            return True, snapshot.day.isoformat()
    return False, None


def _era(day: date) -> str:
    for name, start, end in contract.ERA_BUCKETS:
        if start <= day <= end:
            return name
    return "OTHER"


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round(q * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def aggregate_metrics(events: Sequence[Mapping[str, object]], *, selection_end: date) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[Mapping[str, object]]] = {}
    for event in events:
        if date.fromisoformat(str(event["evaluation_day"])) <= selection_end:
            grouped.setdefault((str(event["cohort_id"]), int(event["horizon"])), []).append(event)
    output: list[dict[str, object]] = []
    for (cohort_id, horizon), rows in sorted(grouped.items()):
        cohort = contract.COHORT_BY_ID[cohort_id]
        field = "negative_forward_return_magnitude" if cohort.kind == "RISK" else "forward_excess_return"
        values = [float(row[field]) for row in rows]
        by_year: dict[int, list[float]] = {}
        by_era: dict[str, list[float]] = {}
        for row, value in zip(rows, values):
            day = date.fromisoformat(str(row["evaluation_day"]))
            by_year.setdefault(day.year, []).append(value)
            by_era.setdefault(_era(day), []).append(value)
        eligible_years = [vals for vals in by_year.values() if len(vals) >= 5]
        eligible_eras = [vals for name, vals in by_era.items() if name != "OTHER" and len(vals) >= 10]
        future_members = [bool(row.get("future_canonical_top10", False)) for row in rows if cohort.kind == "LEADER"]
        adverse = [float(row["adverse_excursion_10"]) for row in rows]
        output.append({
            "cohort_id": cohort_id, "kind": cohort.kind, "family": cohort.family, "horizon": horizon,
            "event_count": len(rows), "mean_outcome": fmean(values), "median_outcome": median(values),
            "hit_rate": sum(value > 0.0 for value in values) / len(values),
            "p10_outcome": _percentile(values, 0.10), "p90_outcome": _percentile(values, 0.90),
            "eligible_year_count": len(eligible_years), "year_positive_count": sum(median(vals) > 0.0 for vals in eligible_years),
            "year_positive_rate": sum(median(vals) > 0.0 for vals in eligible_years) / len(eligible_years) if eligible_years else 0.0,
            "eligible_era_count": len(eligible_eras), "era_positive_count": sum(median(vals) > 0.0 for vals in eligible_eras),
            "era_positive_rate": sum(median(vals) > 0.0 for vals in eligible_eras) / len(eligible_eras) if eligible_eras else 0.0,
            "median_adverse_excursion_10": median(adverse),
            "future_canonical_top10_rate": sum(future_members) / len(future_members) if future_members else None,
        })
    return output


def build_shortlist(metrics: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    metric_map = {(str(row["cohort_id"]), int(row["horizon"])): row for row in metrics}
    output: list[dict[str, object]] = []
    for cohort in contract.ALL_COHORTS:
        if cohort.kind == "RISK":
            h5 = metric_map.get((cohort.cohort_id, 5))
            h10 = metric_map.get((cohort.cohort_id, 10))
            candidate = bool(h5 and h10 and int(h5["event_count"]) >= 40 and int(h10["event_count"]) >= 40 and float(h5["median_outcome"]) > 0.0 and float(h10["median_outcome"]) > 0.0 and float(h10["mean_outcome"]) > 0.0 and float(h10["year_positive_rate"]) >= 0.60 and float(h10["era_positive_rate"]) >= 0.75 and float(h10["median_adverse_excursion_10"]) <= -0.03)
            score = (float(h10["median_outcome"]) if h10 else -1.0) + 0.5 * (float(h5["median_outcome"]) if h5 else -1.0)
        else:
            h10 = metric_map.get((cohort.cohort_id, 10))
            h15 = metric_map.get((cohort.cohort_id, 15))
            candidate = bool(h10 and h15 and int(h10["event_count"]) >= 40 and int(h15["event_count"]) >= 40 and float(h10["median_outcome"]) > 0.0 and float(h15["median_outcome"]) > 0.0 and float(h10["mean_outcome"]) > 0.0 and float(h10["hit_rate"]) >= 0.50 and float(h10["year_positive_rate"]) >= 0.55 and float(h10["era_positive_rate"]) >= 0.75)
            score = (float(h10["median_outcome"]) if h10 else -1.0) + 0.5 * (float(h15["median_outcome"]) if h15 else -1.0)
        output.append({"cohort_id": cohort.cohort_id, "kind": cohort.kind, "family": cohort.family, "description": cohort.description, "historical_candidate": candidate, "ranking_score": score})
    output.sort(key=lambda row: (not bool(row["historical_candidate"]), -float(row["ranking_score"]), str(row["cohort_id"])))
    return output


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_study(*, input_zip: Path, store_path: Path, output_dir: Path, output_zip: Path, selection_end: date = SELECTION_END_DEFAULT, analysis_end: date = ANALYSIS_END_DEFAULT, price_multiplier: float = v43.PRICE_MULTIPLIER) -> dict[str, object]:
    rows, manifest = v43._load_research_rows(input_zip)
    snapshots, _, _ = v43.build_signal_snapshots(rows)
    market = v60._load_market(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, market.calendar[-1])
    calendar_index = {day: index for index, day in enumerate(market.calendar)}
    signal_days = [snapshot.day for snapshot in snapshots]
    universe_by_day = v60._universe_by_signal(rows)
    weekly_days = v60._weekly_signal_days(market.calendar, end=effective_end)
    prior_rank: dict[str, int] = {}
    prior_score: dict[str, float] = {}
    prior_feature_by_symbol: dict[str, dict[str, object]] = {}
    feature_rows: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    for evaluation_day in weekly_days:
        canonical = v60._canonical_snapshot_for_day(snapshots, signal_days, evaluation_day)
        if canonical is None:
            continue
        universe = universe_by_day.get(canonical.day, tuple(canonical.ranking))
        preview = v60._preview_ranking(evaluation_day=evaluation_day, canonical=canonical, universe=universe, market=market, calendar_index=calendar_index)
        if not preview:
            continue
        current_rank = {row.symbol: row.rank for row in preview}
        current_score = {row.symbol: row.score for row in preview}
        symbols = set(canonical.ranking[:10]) | {row.symbol for row in preview[:20]}
        current_features: dict[str, dict[str, object]] = {}
        for symbol in sorted(symbols):
            feature = build_feature_row(symbol=symbol, evaluation_day=evaluation_day, canonical=canonical, preview_rank=current_rank, preview_score=current_score, prior_rank=prior_rank, prior_score=prior_score, market=market, calendar_index=calendar_index)
            if feature is None:
                continue
            current_features[symbol] = feature
            phase = "HISTORICAL_SELECTION" if evaluation_day <= selection_end else "SHADOW_ONLY"
            feature_rows.append({"phase": phase, "canonical_day": canonical.day.isoformat(), **feature})
            future = forward_outcomes(symbol=symbol, evaluation_day=evaluation_day, market=market, calendar_index=calendar_index)
            if not future:
                continue
            future_member, future_day = _future_canonical_label(symbol, evaluation_day, snapshots)
            prior_feature = prior_feature_by_symbol.get(symbol)
            for cohort in contract.ALL_COHORTS:
                if not contract.cohort_matches(cohort.cohort_id, feature, prior_feature):
                    continue
                for horizon, outcome in future.items():
                    events.append({"phase": phase, "evaluation_day": evaluation_day.isoformat(), "canonical_day": canonical.day.isoformat(), "cohort_id": cohort.cohort_id, "kind": cohort.kind, "family": cohort.family, "symbol": symbol, "horizon": horizon, "preview_rank": feature["preview_rank"], "prior_preview_rank": feature["prior_preview_rank"], "canonical_rank": feature["canonical_rank"], "distance_ma20": feature["distance_ma20"], "distance_ma50": feature["distance_ma50"], "relative_5": feature["relative_5"], "relative_20": feature["relative_20"], "drawdown_20": feature["drawdown_20"], "volume_ratio_5_20": feature["volume_ratio_5_20"], "realized_vol_ratio_20_60": feature["realized_vol_ratio_20_60"], "future_canonical_top10": future_member if cohort.kind == "LEADER" else False, "future_canonical_day": future_day if cohort.kind == "LEADER" else None, **outcome})
        prior_rank = current_rank
        prior_score = current_score
        prior_feature_by_symbol = current_features
    metrics = aggregate_metrics(events, selection_end=selection_end)
    shortlist = build_shortlist(metrics)
    candidates = [row for row in shortlist if bool(row["historical_candidate"])]
    shadow = [row for row in events if row["phase"] == "SHADOW_ONLY"]
    shadow_focus = [row for row in shadow if str(row["symbol"]) in contract.SHADOW_FOCUS_SYMBOLS]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v64_features.csv", feature_rows)
    _write_csv(output_dir / "v64_cohort_events.csv", events)
    _write_csv(output_dir / "v64_historical_metrics.csv", metrics)
    _write_csv(output_dir / "v64_shortlist.csv", shortlist)
    _write_csv(output_dir / "v64_shadow_events.csv", shadow)
    _write_csv(output_dir / "v64_shadow_focus_vpi_tlg_baf.csv", shadow_focus)
    _write_csv(output_dir / "v64_cohort_contract.csv", [cohort.__dict__ for cohort in contract.ALL_COHORTS])
    report = {"schema_version": SCHEMA_VERSION, "status": "SUCCESS", "selection_end": selection_end.isoformat(), "analysis_end_requested": analysis_end.isoformat(), "analysis_end_effective": effective_end.isoformat(), "historical_selection_uses_august_2026": False, "shadow_used_for_policy_selection": False, "causality": "COMPLETED_WEEKLY_CLOSE_TO_NEXT_SESSION_OPEN", "cost_role": "DEFERRED_TO_PORTFOLIO_STAGE", "turnover_is_veto": TURNOVER_IS_VETO, "cohort_count": len(contract.ALL_COHORTS), "risk_cohort_count": len(contract.RISK_COHORTS), "leader_cohort_count": len(contract.LEADER_COHORTS), "feature_row_count": len(feature_rows), "cohort_event_count": len(events), "shadow_event_count": len(shadow), "shadow_focus_event_count": len(shadow_focus), "historical_candidate_count": len(candidates), "historical_candidates": candidates, "shadow_focus_symbols": list(contract.SHADOW_FOCUS_SYMBOLS), "input_manifest_schema_version": manifest.get("schema_version"), "former_v60_holdout_already_consumed": True, "thresholds_predeclared_before_workstation_run": True, "research_only": True, "live_model_change_authorized": LIVE_MODEL_CHANGE_AUTHORIZED, "automatic_live_orders_allowed": False, "limitations": ["no pristine untouched holdout remains after V60+", "point-in-time universe lineage remains incomplete", "price basis and corporate actions remain incompletely verified", "August 2026 is shadow-only and cannot justify threshold changes", "V64 is event-level cohort research; portfolio interactions are deferred"]}
    (output_dir / "v64_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    parser.add_argument("--selection-end", type=date.fromisoformat, default=SELECTION_END_DEFAULT)
    parser.add_argument("--analysis-end", type=date.fromisoformat, default=ANALYSIS_END_DEFAULT)
    parser.add_argument("--price-multiplier", type=float, default=v43.PRICE_MULTIPLIER)
    args = parser.parse_args(argv)
    report = run_study(input_zip=args.input_zip, store_path=args.store, output_dir=args.output_dir, output_zip=args.output_zip, selection_end=args.selection_end, analysis_end=args.analysis_end, price_multiplier=args.price_multiplier)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
