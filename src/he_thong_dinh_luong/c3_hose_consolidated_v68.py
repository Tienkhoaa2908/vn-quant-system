"""V68 consolidated C3/HOSE research orchestrator.

One workstation run performs data-readiness census, market-store basis/provenance
audit, best-effort HOSE lineage probing, multiple C3-native sensitivity studies,
cluster-aware cohort robustness, and cross-universe stability analysis.

The key distinction is explicit:
- provisional/sensitivity universes MAY be used to accelerate diagnostic research;
- unresolved price-basis or point-in-time HOSE lineage STILL blocks canonical
  research claims, policy promotion, paper/live promotion, and broker actions.

No challenger ML, no order generation, and no mutation of the canonical market
store are allowed here.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import random
import sqlite3
from statistics import fmean, median, pstdev
import tempfile
from typing import Iterable, Mapping, Sequence

from . import c3_hose_native_driver_v67 as c3driver
from . import hose_data_readiness_v67 as readiness
from . import hose_lineage_price_probe_v67 as lineage_probe
from . import market_store_basis_audit_v67 as basis_audit

SCHEMA_VERSION = "c3_hose_consolidated_v68"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
HISTORICAL_END = "2026-07-31"
ANALYSIS_END = "2026-08-13"
PRIMARY_HORIZON = 10
DEFAULT_BOOTSTRAP_SAMPLES = 2000
RANDOM_SEED = 68012908


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_gzip_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({str(key) for row in rows for key in row.keys()}) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            cooked: dict[str, object] = {}
            for field in fields:
                value = row.get(field)
                if isinstance(value, (dict, list, tuple, set)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                cooked[field] = value
            writer.writerow(cooked)


def _store_stock_symbols(store: Path) -> list[str]:
    uri = store.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        cols = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        if not {"symbol", "asset_type"}.issubset(cols):
            raise ValueError("V68_BARS_SYMBOL_ASSET_COLUMNS_MISSING")
        sql = (
            f"SELECT DISTINCT {_q(cols['symbol'])} FROM bars "
            f"WHERE UPPER(COALESCE({_q(cols['asset_type'])},''))='STOCK' ORDER BY 1"
        )
        return [str(row[0]).strip().upper() for row in db.execute(sql) if str(row[0] or "").strip()]


def _create_diagnostic_store(source: Path, dest: Path, symbols: Sequence[str]) -> None:
    """Create a minimal temporary store; canonical source is opened read-only."""
    wanted = {str(symbol).upper() for symbol in symbols}
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as src, sqlite3.connect(dest) as dst:
        cols = {str(r[1]).lower(): str(r[1]) for r in src.execute('PRAGMA table_info("bars")')}
        required = {"symbol", "day", "open", "close", "volume", "asset_type"}
        if not required.issubset(cols):
            raise ValueError("V68_BARS_REQUIRED_COLUMNS_MISSING")
        dst.execute(
            "CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, "
            "volume INTEGER, asset_type TEXT, exchange TEXT)"
        )
        selected = [cols[key] for key in ("symbol", "day", "open", "close", "volume", "asset_type")]
        sql = f"SELECT {','.join(_q(col) for col in selected)} FROM bars ORDER BY {_q(cols['day'])},{_q(cols['symbol'])}"
        batch: list[tuple[object, ...]] = []
        for symbol, day, open_price, close_price, volume, asset_type in src.execute(sql):
            sym = str(symbol or "").strip().upper()
            asset = str(asset_type or "").strip().upper()
            is_index = asset == "INDEX" and sym in {"VNINDEX", "VN-INDEX", "VN_INDEX"}
            if not is_index and not (asset == "STOCK" and sym in wanted):
                continue
            batch.append((sym, day, open_price, close_price, volume, asset, "" if is_index else "HOSE_DIAGNOSTIC"))
            if len(batch) >= 10000:
                dst.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", batch)
                batch.clear()
        if batch:
            dst.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", batch)
        dst.execute("CREATE INDEX idx_v68_bars_symbol_day ON bars(symbol,day)")
        dst.commit()


def _strict_pit_symbols(lineage: Mapping[str, object]) -> set[str]:
    rows = lineage.get("symbol_lineage_rows", [])
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("symbol") or "").upper()
        for row in rows
        if isinstance(row, dict) and row.get("pit_accepted_for_research") is True
    }


def _variant_contract(
    *, all_symbols: Sequence[str], basis: Mapping[str, object], lineage: Mapping[str, object]
) -> list[dict[str, object]]:
    all_set = set(all_symbols)
    gap_events = basis.get("gap_events", []) if isinstance(basis.get("gap_events"), list) else []
    gap18 = {str(row.get("symbol") or "").upper() for row in gap_events if isinstance(row, dict)}
    seams = {
        str(row.get("symbol") or "").upper()
        for row in basis.get("mixed_basis_seam_candidates", [])
        if isinstance(row, dict)
    }
    strict = _strict_pit_symbols(lineage)
    variants: list[dict[str, object]] = [
        {
            "variant_id": "BROAD_PROVISIONAL",
            "symbols": sorted(all_set),
            "universe_contract": "ALL_LOCAL_STOCKS_PROVISIONALLY_TREATED_AS_HOSE_FOR_SENSITIVITY_ONLY",
            "promotion_eligible": False,
        },
        {
            "variant_id": "SEAM_CLEAN",
            "symbols": sorted(all_set - seams),
            "universe_contract": "BROAD_PROVISIONAL_EXCLUDING_PROVENANCE_SEAM_CANDIDATE_SYMBOLS",
            "promotion_eligible": False,
        },
        {
            "variant_id": "GAP18_CLEAN",
            "symbols": sorted(all_set - gap18),
            "universe_contract": "BROAD_PROVISIONAL_EXCLUDING_ANY_SYMBOL_WITH_GE18PCT_CONSECUTIVE_SESSION_GAP",
            "promotion_eligible": False,
        },
    ]
    strict_clean = sorted((strict & all_set) - gap18)
    if len(strict_clean) >= 10:
        variants.append(
            {
                "variant_id": "STRICT_PIT_PRICE_CLEAN",
                "symbols": strict_clean,
                "universe_contract": "PIT_ACCEPTED_BY_LINEAGE_PROBE_AND_NO_GE18PCT_GAP",
                "promotion_eligible": False,  # price basis remains unverified globally until separately closed
            }
        )
    return variants


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _bh_qvalues(rows: list[dict[str, object]], p_field: str = "bootstrap_two_sided_p") -> None:
    indexed = [(i, float(row[p_field])) for i, row in enumerate(rows)]
    indexed.sort(key=lambda item: item[1])
    m = len(indexed)
    qvals = [1.0] * m
    running = 1.0
    for rank_from_end in range(m - 1, -1, -1):
        original_i, p = indexed[rank_from_end]
        rank = rank_from_end + 1
        running = min(running, p * m / rank)
        qvals[original_i] = min(1.0, running)
    for row, q in zip(rows, qvals):
        row["bh_fdr_q"] = q


def _cohort_robustness(events: Sequence[Mapping[str, str]], *, bootstrap_samples: int, seed: int) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[str, str, int], list[Mapping[str, str]]] = {}
    for row in events:
        if row.get("phase") != "HISTORICAL_SELECTION":
            continue
        try:
            key = (str(row["kind"]), str(row["cohort_id"]), int(row["horizon"]))
        except (KeyError, TypeError, ValueError):
            continue
        grouped.setdefault(key, []).append(row)

    robust: list[dict[str, object]] = []
    year_era: list[dict[str, object]] = []
    rng = random.Random(seed)

    for (kind, cohort_id, horizon), rows in sorted(grouped.items()):
        by_week: dict[str, list[float]] = {}
        by_year: dict[int, list[float]] = {}
        by_era: dict[str, list[float]] = {}
        symbols: set[str] = set()
        for row in rows:
            try:
                ret = float(row["forward_return"])
                excess = float(row["forward_excess_return"])
                day = str(row["evaluation_day"])
                year = int(day[:4])
            except (KeyError, TypeError, ValueError):
                continue
            objective = -ret if kind == "RISK" else excess
            by_week.setdefault(day, []).append(objective)
            by_year.setdefault(year, []).append(objective)
            era = "2015_2019" if year <= 2019 else "2020_2022" if year <= 2022 else "2023_2026"
            by_era.setdefault(era, []).append(objective)
            symbols.add(str(row.get("symbol") or ""))
        week_means = [fmean(values) for _, values in sorted(by_week.items())]
        if not week_means:
            continue
        boots: list[float] = []
        for _ in range(max(1, bootstrap_samples)):
            boots.append(fmean(week_means[rng.randrange(len(week_means))] for _ in week_means))
        nonpos = sum(value <= 0 for value in boots) / len(boots)
        nonneg = sum(value >= 0 for value in boots) / len(boots)
        p = min(1.0, 2.0 * min(nonpos, nonneg))
        robust.append(
            {
                "kind": kind,
                "cohort_id": cohort_id,
                "horizon": horizon,
                "event_count": len(rows),
                "unique_week_count": len(week_means),
                "unique_symbol_count": len(symbols),
                "week_cluster_objective_mean": fmean(week_means),
                "week_cluster_objective_median": median(week_means),
                "bootstrap_ci025": _quantile(boots, 0.025),
                "bootstrap_ci50": _quantile(boots, 0.50),
                "bootstrap_ci975": _quantile(boots, 0.975),
                "bootstrap_positive_probability": sum(value > 0 for value in boots) / len(boots),
                "bootstrap_two_sided_p": p,
            }
        )
        for period_type, mapping in (("YEAR", by_year), ("ERA", by_era)):
            for period, values in sorted(mapping.items(), key=lambda item: str(item[0])):
                year_era.append(
                    {
                        "kind": kind,
                        "cohort_id": cohort_id,
                        "horizon": horizon,
                        "period_type": period_type,
                        "period": period,
                        "event_count": len(values),
                        "objective_mean": fmean(values),
                        "objective_median": median(values),
                        "objective_positive_rate": sum(value > 0 for value in values) / len(values),
                    }
                )
    for kind in ("RISK", "LEADER"):
        for horizon in (5, 10, 20):
            subset = [row for row in robust if row["kind"] == kind and row["horizon"] == horizon]
            _bh_qvalues(subset)
    return robust, year_era


def _monthly_by_year(rows: Sequence[Mapping[str, str]], variant_id: str) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], list[float]] = {}
    for row in rows:
        try:
            year = int(str(row["signal_day"])[:4])
            horizon = int(row["horizon"])
            value = float(row["mean_forward_excess"])
        except (KeyError, TypeError, ValueError):
            continue
        grouped.setdefault((year, horizon), []).append(value)
    return [
        {
            "variant_id": variant_id,
            "year": year,
            "horizon": horizon,
            "month_count": len(values),
            "mean_monthly_top10_excess": fmean(values),
            "median_monthly_top10_excess": median(values),
            "positive_month_rate": sum(value > 0 for value in values) / len(values),
        }
        for (year, horizon), values in sorted(grouped.items())
    ]


def _weight_summary(rows: Sequence[Mapping[str, str]], variant_id: str) -> list[dict[str, object]]:
    fields = (
        "weight_low_volatility",
        "weight_relative_strength_120",
        "weight_high_52_week",
    )
    output: list[dict[str, object]] = []
    for field in fields:
        values: list[float] = []
        for row in rows:
            try:
                values.append(float(row[field]))
            except (KeyError, TypeError, ValueError):
                pass
        if values:
            output.append(
                {
                    "variant_id": variant_id,
                    "weight": field,
                    "snapshot_count": len(values),
                    "mean": fmean(values),
                    "median": median(values),
                    "min": min(values),
                    "max": max(values),
                    "pstdev": pstdev(values) if len(values) > 1 else 0.0,
                }
            )
    return output


def _top10_sets(rows: Sequence[Mapping[str, str]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in rows:
        try:
            if int(row["rank"]) > 10:
                continue
            result.setdefault(str(row["signal_day"]), set()).add(str(row["symbol"]))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _cross_variant_overlap(rankings: Mapping[str, dict[str, set[str]]]) -> list[dict[str, object]]:
    variants = sorted(rankings)
    output: list[dict[str, object]] = []
    for i, left in enumerate(variants):
        for right in variants[i + 1 :]:
            shared = sorted(set(rankings[left]) & set(rankings[right]))
            jac: list[float] = []
            exact = 0
            for day in shared:
                a, b = rankings[left][day], rankings[right][day]
                union = a | b
                score = len(a & b) / len(union) if union else 1.0
                jac.append(score)
                exact += int(a == b)
            output.append(
                {
                    "left_variant": left,
                    "right_variant": right,
                    "shared_snapshot_count": len(shared),
                    "mean_top10_jaccard": fmean(jac) if jac else 0.0,
                    "median_top10_jaccard": median(jac) if jac else 0.0,
                    "exact_top10_set_rate": exact / len(shared) if shared else 0.0,
                    "latest_shared_day": shared[-1] if shared else None,
                    "latest_left_top10": sorted(rankings[left][shared[-1]]) if shared else [],
                    "latest_right_top10": sorted(rankings[right][shared[-1]]) if shared else [],
                }
            )
    return output


def _join_candidate_metrics(
    variant_id: str,
    robustness: Sequence[Mapping[str, object]],
    metrics: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    metric_lookup: dict[tuple[str, int], Mapping[str, str]] = {}
    for row in metrics:
        try:
            metric_lookup[(str(row["cohort_id"]), int(row["horizon"]))] = row
        except (KeyError, TypeError, ValueError):
            continue
    output: list[dict[str, object]] = []
    for row in robustness:
        if int(row["horizon"]) != PRIMARY_HORIZON:
            continue
        metric = metric_lookup.get((str(row["cohort_id"]), PRIMARY_HORIZON), {})
        cooked = dict(row)
        cooked["variant_id"] = variant_id
        for key in (
            "mean_forward_return",
            "median_forward_return",
            "mean_forward_excess",
            "median_forward_excess",
            "p10_forward_return",
            "leader_incremental_mean_excess_vs_raw_top5",
            "year_positive_rate_for_objective",
        ):
            value = metric.get(key) if isinstance(metric, Mapping) else None
            try:
                cooked[key] = float(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                cooked[key] = value
        output.append(cooked)
    return output


def run_consolidated(
    *,
    store: Path,
    output_dir: Path,
    search_roots: Sequence[Path] = (),
    allow_network: bool = True,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    readiness_report = readiness.build_report(store, list(search_roots))
    basis_report = basis_audit.build_report(store)
    lineage_report = lineage_probe.build_report(store, allow_network=allow_network, timeout=15.0)

    (output_dir / "v68_data_readiness.json").write_text(json.dumps(readiness_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "v68_basis_audit.json").write_text(json.dumps(basis_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "v68_lineage_probe.json").write_text(json.dumps(lineage_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    all_symbols = _store_stock_symbols(store)
    variants = _variant_contract(all_symbols=all_symbols, basis=basis_report, lineage=lineage_report)
    variant_summaries: list[dict[str, object]] = []
    monthly_year: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    robustness_rows: list[dict[str, object]] = []
    year_era_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    ranking_sets: dict[str, dict[str, set[str]]] = {}
    shadow_rows: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="v68-c3-") as tmp:
        tmp_root = Path(tmp)
        for index, spec in enumerate(variants):
            variant_id = str(spec["variant_id"])
            symbols = list(spec["symbols"])
            if len(symbols) < 10:
                variant_summaries.append(
                    {
                        "variant_id": variant_id,
                        "status": "SKIPPED_TOO_FEW_SYMBOLS",
                        "symbol_count": len(symbols),
                        "universe_contract": spec["universe_contract"],
                        "promotion_eligible": False,
                    }
                )
                continue
            temp_store = tmp_root / f"{variant_id}.sqlite3"
            _create_diagnostic_store(store, temp_store, symbols)
            variant_out = output_dir / "variants" / variant_id
            report = c3driver.run_study(
                store=temp_store,
                output_dir=variant_out,
                historical_end=__import__("datetime").date.fromisoformat(HISTORICAL_END),
                analysis_end=__import__("datetime").date.fromisoformat(ANALYSIS_END),
                price_multiplier=1000.0,
            )
            report["v68_variant_id"] = variant_id
            report["v68_universe_contract"] = spec["universe_contract"]
            report["v68_provisional_universe"] = variant_id != "STRICT_PIT_PRICE_CLEAN"
            report["v68_promotion_eligible"] = False
            (variant_out / "v68_variant_contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            baseline_csv = _read_csv(variant_out / "v67_c3_monthly_top10_metrics.csv")
            weights_csv = _read_csv(variant_out / "v67_c3_weight_history.csv")
            rankings_csv = _read_gzip_csv(variant_out / "v67_c3_monthly_rankings.csv.gz")
            events_csv = _read_gzip_csv(variant_out / "v67_cohort_events.csv.gz")
            metrics_csv = _read_csv(variant_out / "v67_cohort_metrics.csv")
            shadow_csv = _read_csv(variant_out / "v67_shadow_focus_vpi_tlg_baf.csv")

            robust, year_era = _cohort_robustness(events_csv, bootstrap_samples=bootstrap_samples, seed=RANDOM_SEED + index)
            for row in robust:
                row["variant_id"] = variant_id
            for row in year_era:
                row["variant_id"] = variant_id
            robustness_rows.extend(robust)
            year_era_rows.extend(year_era)
            candidate_rows.extend(_join_candidate_metrics(variant_id, robust, metrics_csv))
            monthly_year.extend(_monthly_by_year(baseline_csv, variant_id))
            weight_rows.extend(_weight_summary(weights_csv, variant_id))
            ranking_sets[variant_id] = _top10_sets(rankings_csv)
            for row in shadow_csv:
                shadow_rows.append({"variant_id": variant_id, **row})

            h20 = [float(row["mean_forward_excess"]) for row in baseline_csv if row.get("horizon") == "20"]
            variant_summaries.append(
                {
                    "variant_id": variant_id,
                    "status": report.get("status"),
                    "symbol_count": len(symbols),
                    "universe_contract": spec["universe_contract"],
                    "promotion_eligible": False,
                    "monthly_snapshot_count": report.get("monthly_snapshot_count"),
                    "c3_training_row_count": report.get("c3_training_row_count"),
                    "weekly_signal_state_count": report.get("weekly_signal_state_count"),
                    "cohort_event_count": report.get("cohort_event_count"),
                    "historical_monthly_top10_h20_mean_excess": fmean(h20) if h20 else None,
                }
            )

    overlap_rows = _cross_variant_overlap(ranking_sets)
    gap_events = basis_report.get("gap_events", []) if isinstance(basis_report.get("gap_events"), list) else []
    gap_symbols = sorted({str(row.get("symbol") or "") for row in gap_events if isinstance(row, dict)})
    seam_symbols = sorted({str(row.get("symbol") or "") for row in basis_report.get("mixed_basis_seam_candidates", []) if isinstance(row, dict)})

    primary_candidates = [row for row in candidate_rows if int(row.get("horizon", 0)) == PRIMARY_HORIZON]
    protection = sorted(
        [row for row in primary_candidates if row.get("kind") == "RISK"],
        key=lambda row: (
            -float(row.get("bootstrap_positive_probability") or 0.0),
            -float(row.get("week_cluster_objective_mean") or 0.0),
            float(row.get("bh_fdr_q") or 1.0),
        ),
    )[:12]
    opportunity = sorted(
        [row for row in primary_candidates if row.get("kind") == "LEADER"],
        key=lambda row: (
            -float(row.get("leader_incremental_mean_excess_vs_raw_top5") or -999.0),
            -float(row.get("bootstrap_positive_probability") or 0.0),
            float(row.get("bh_fdr_q") or 1.0),
        ),
    )[:12]

    price_gate = bool(readiness_report.get("gates", {}).get("price_basis_values_observed")) and all(
        str(item.get("price_basis", "")).upper() not in {"CHUA_XAC_NHAN", "UNKNOWN", "<NULL>", ""}
        for item in readiness_report.get("store", {}).get("bars_price_basis_distribution", [])
        if isinstance(item, dict)
    )
    hose_gate = bool(_strict_pit_symbols(lineage_report)) and bool(lineage_report.get("research_gate", {}).get("hose_pit_gate_closed"))

    _write_csv(output_dir / "v68_variant_summary.csv", variant_summaries)
    _write_csv(output_dir / "v68_monthly_baseline_by_year.csv", monthly_year)
    _write_csv(output_dir / "v68_c3_weight_summary.csv", weight_rows)
    _write_csv(output_dir / "v68_cohort_robustness.csv", robustness_rows)
    _write_csv(output_dir / "v68_cohort_year_era.csv", year_era_rows)
    _write_csv(output_dir / "v68_primary_candidate_table.csv", candidate_rows)
    _write_csv(output_dir / "v68_cross_variant_top10_overlap.csv", overlap_rows)
    _write_csv(output_dir / "v68_shadow_focus_all_variants.csv", shadow_rows)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "challenger_ml_run": False,
        "canonical_environment": "vn_quant_local_system/.venv",
        "historical_end": HISTORICAL_END,
        "analysis_end": ANALYSIS_END,
        "august_2026_shadow_only": True,
        "source_store_mutated": False,
        "network_scope": "BEST_EFFORT_HOSE_PUBLIC_METADATA_ONLY",
        "local_stock_symbol_count": len(all_symbols),
        "variant_count": len(variants),
        "variant_summaries": variant_summaries,
        "gap18_symbol_count": len(gap_symbols),
        "gap18_symbols": gap_symbols,
        "mixed_basis_seam_symbol_count": len(seam_symbols),
        "mixed_basis_seam_symbols": seam_symbols,
        "lineage_network_error": lineage_report.get("network_error"),
        "strict_pit_symbol_count": len(_strict_pit_symbols(lineage_report)),
        "data_gates": {
            "price_basis_gate_closed": price_gate,
            "hose_point_in_time_gate_closed": hose_gate,
            "canonical_research_claim_authorized": bool(price_gate and hose_gate),
            "diagnostic_c3_allowed": True,
            "promotion_authorized": False,
        },
        "robustness": {
            "bootstrap_samples_per_cohort_horizon": bootstrap_samples,
            "cluster_unit": "WEEK",
            "multiple_testing": "BH_FDR_WITHIN_KIND_AND_HORIZON_ON_BOOTSTRAP_TWO_SIDED_P",
            "raw_event_count_not_treated_as_independent_sample_size": True,
        },
        "top_protection_candidates_primary_horizon": protection,
        "top_opportunity_candidates_primary_horizon": opportunity,
        "limitations": [
            "BROAD_PROVISIONAL, SEAM_CLEAN and GAP18_CLEAN are diagnostic sensitivity universes, not verified point-in-time HOSE universes.",
            "Excluding gap symbols is a sensitivity test, not a corporate-action adjustment method.",
            "Price-basis and point-in-time HOSE gates still block canonical claims and promotion.",
            "August 2026 is shadow-only and must not be used to tune thresholds.",
            "Portfolio-level benefit still requires a later exposure-normalized simulation after data lineage is closed.",
        ],
        "research_only": True,
        "live_model_change_authorized": False,
        "automatic_live_orders_allowed": False,
    }
    (output_dir / "v68_consolidated_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--search-root", type=Path, action="append", default=[])
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args(argv)
    report = run_consolidated(
        store=args.store,
        output_dir=args.output_dir,
        search_roots=args.search_root,
        allow_network=not args.no_network,
        bootstrap_samples=max(100, args.bootstrap_samples),
    )
    print(json.dumps({
        "schema_version": report["schema_version"],
        "status": report["status"],
        "champion_model": report["champion_model"],
        "variant_count": report["variant_count"],
        "price_basis_gate_closed": report["data_gates"]["price_basis_gate_closed"],
        "hose_point_in_time_gate_closed": report["data_gates"]["hose_point_in_time_gate_closed"],
        "diagnostic_c3_allowed": report["data_gates"]["diagnostic_c3_allowed"],
        "promotion_authorized": report["data_gates"]["promotion_authorized"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
