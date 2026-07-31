"""Corrected anytime snapshot with benchmark-history and attribution gates."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import fmean
from typing import Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from . import anytime_snapshot as legacy
from . import eod_hang_ngay as eod_core
from .model_quality_audit import audit_prediction_input
from .nguon_dnse import DnseRestSource
from .portfolio_weighting import (
    ALLOCATOR_MODEL,
    REFERENCE_MODEL,
    average_percentile,
    dynamic_capital_budget,
    optimized_weights,
    reference_scores,
)

SCHEMA_VERSION = "anytime_snapshot_v2"
TOP_K = 10
MIN_BENCHMARK_BARS = 251


def _metric_source(model: Mapping[str, object], champion: str) -> Mapping[str, object]:
    key = {
        "momentum_baseline": "momentum_validation",
        REFERENCE_MODEL: "robust_reference_validation",
        "lightgbm_ranker": "lightgbm_validation",
    }.get(champion, "momentum_validation")
    value = model.get(key)
    return value if isinstance(value, Mapping) else {}


def run(
    *,
    data_root: Path,
    output_dir: Path,
    now: datetime | None = None,
    source: DnseRestSource | None = None,
    min_coverage: float = 0.80,
) -> dict[str, object]:
    if not 0 < min_coverage <= 1:
        raise ValueError("SNAPSHOT_MIN_COVERAGE_INVALID")
    root = Path(data_root)
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    final_run = legacy.latest_successful_eod(root)
    if final_run is None:
        raise ValueError("FINAL_EOD_BASE_NOT_FOUND")
    final_paths = legacy.artifact_paths(final_run)
    publication_rows = legacy.read_csv_rows(final_paths["publication"], limit=10_000_000)
    if not publication_rows:
        raise ValueError("FINAL_PUBLICATION_EMPTY")
    final_model = legacy._read_json(final_paths["model"])
    latest_final_day = max(date.fromisoformat(str(row["ngay"])[:10]) for row in publication_rows)
    series = legacy._series(publication_rows)
    symbols = sorted(symbol for symbol in series if symbol != "VNINDEX")
    current = (now or datetime.now(eod_core.VN_TZ)).astimezone(eod_core.VN_TZ)
    today = current.date()
    fetch_start = latest_final_day - timedelta(days=7)
    client = source or DnseRestSource.from_env()
    close_client = source is None
    raw: dict[str, object] = {}
    errors: dict[str, str] = {}
    try:
        benchmark_rows = tuple(client.fetch("VNINDEX", fetch_start, today, is_index=True))
        if not benchmark_rows:
            raise ValueError("SNAPSHOT_BENCHMARK_EMPTY")
        snapshot_day = max(row.day for row in benchmark_rows)
        provisional = snapshot_day == today and current.hour < 18
        data_status = (
            "LAST_AVAILABLE" if snapshot_day < today
            else "PROVISIONAL_INTRADAY" if provisional
            else "FINAL_UNCONFIRMED"
        )

        # Use the complete benchmark response, not only rows after the latest final stock day.
        benchmark_values: list[dict[str, object]] = []
        for row in benchmark_rows:
            if row.day <= snapshot_day:
                legacy._replace_or_append(
                    benchmark_values,
                    row,
                    provisional=provisional and row.day == snapshot_day,
                )
        benchmark_values.sort(key=lambda row: str(row["ngay"]))
        unique_benchmark_days = {str(row["ngay"])[:10] for row in benchmark_values}
        if len(unique_benchmark_days) < MIN_BENCHMARK_BARS:
            raise ValueError(
                f"SNAPSHOT_BENCHMARK_HISTORY_INSUFFICIENT:{len(unique_benchmark_days)}<{MIN_BENCHMARK_BARS}"
            )
        series["VNINDEX"] = benchmark_values
        raw["VNINDEX"] = [row.payload() for row in benchmark_rows]

        fresh_symbols: set[str] = set()
        for symbol in symbols:
            try:
                fetched = tuple(client.fetch(symbol, fetch_start, today))
                raw[symbol] = [row.payload() for row in fetched]
                eligible_rows = [row for row in fetched if row.day <= snapshot_day]
                if eligible_rows:
                    latest = max(eligible_rows, key=lambda row: row.day)
                    legacy._replace_or_append(
                        series[symbol],
                        latest,
                        provisional=provisional and latest.day == snapshot_day,
                    )
                    if latest.day == snapshot_day:
                        fresh_symbols.add(symbol)
            except Exception as exc:
                errors[symbol] = f"{type(exc).__name__}:{exc}"
    finally:
        if close_client:
            client.close()

    coverage = len(fresh_symbols) / len(symbols) if symbols else 0.0
    if coverage < min_coverage and snapshot_day > latest_final_day:
        raise ValueError(f"SNAPSHOT_COVERAGE_TOO_LOW:{coverage:.6f}")

    benchmark_closes = [
        legacy._float(row["gia_dong_cua"])
        for row in series["VNINDEX"]
        if legacy._float(row["gia_dong_cua"]) > 0
    ]
    if len(benchmark_closes) < MIN_BENCHMARK_BARS:
        raise ValueError("SNAPSHOT_BENCHMARK_CLOSE_HISTORY_INSUFFICIENT")
    previous_benchmark = next(
        (
            legacy._float(row["gia_dong_cua"])
            for row in reversed(series["VNINDEX"])
            if str(row["ngay"]) <= latest_final_day.isoformat()
        ),
        benchmark_closes[-1],
    )
    benchmark_intraday = (
        benchmark_closes[-1] / previous_benchmark - 1.0
        if snapshot_day > latest_final_day and previous_benchmark > 0
        else 0.0
    )
    feature_rows: list[dict[str, object]] = []
    for symbol in symbols:
        row = legacy._feature_row(
            symbol,
            series[symbol],
            benchmark_closes,
            snapshot_day=snapshot_day,
            latest_final_day=latest_final_day,
            benchmark_intraday_return=benchmark_intraday,
        )
        if row is not None:
            feature_rows.append(row)
    if not feature_rows:
        raise ValueError("SNAPSHOT_FEATURES_EMPTY")

    robust_raw, components, confidence = reference_scores(feature_rows)
    robust_scores: list[float] = []
    for index, row in enumerate(feature_rows):
        intraday_component = max(
            0.0,
            min(1.0, 0.5 + 5.0 * legacy._float(row["intraday_relative_return"])),
        )
        robust_scores.append(0.90 * robust_raw[index] + 0.10 * intraday_component)
        row["reference_confidence"] = confidence[index]
        row["components"] = components[index]
    robust_percentile = average_percentile(robust_scores)
    momentum_percentile = average_percentile(
        [legacy._float(row["dong_luong_12_1"]) for row in feature_rows]
    )
    for index, row in enumerate(feature_rows):
        row["ranking_score"] = robust_percentile[index]
        row["reference_score"] = robust_percentile[index]
        row["momentum_percentile"] = momentum_percentile[index]
    feature_rows.sort(key=lambda row: (-legacy._float(row["ranking_score"]), str(row["symbol"])))
    ranking_rank = {str(row["symbol"]): index for index, row in enumerate(feature_rows, start=1)}

    champion = str(final_model.get("champion_model") or "momentum_baseline")
    champion_scores_by_symbol: dict[str, float] = {}
    if champion == "momentum_baseline":
        champion_scores_by_symbol = {
            str(row["symbol"]): legacy._float(row["momentum_percentile"])
            for row in feature_rows
        }
    elif champion == REFERENCE_MODEL:
        champion_scores_by_symbol = {
            str(row["symbol"]): legacy._float(row["reference_score"])
            for row in feature_rows
        }
    champion_order = sorted(
        champion_scores_by_symbol,
        key=lambda symbol: (-champion_scores_by_symbol[symbol], symbol),
    )
    champion_rank = {symbol: index for index, symbol in enumerate(champion_order, start=1)}

    audit: dict[str, object] = {}
    audit_error = ""
    input_zip = root / "prediction_input.zip"
    if input_zip.is_file():
        try:
            audit = audit_prediction_input(input_zip, validation_months=12, top_k=TOP_K)
        except Exception as exc:
            audit_error = f"{type(exc).__name__}:{exc}"
    else:
        audit_error = "PREDICTION_INPUT_NOT_FOUND"
    if isinstance(audit.get("momentum_validation"), Mapping):
        final_model["momentum_validation"] = audit["momentum_validation"]
    if isinstance(audit.get("robust_reference_validation"), Mapping):
        final_model["robust_reference_validation"] = audit["robust_reference_validation"]
        final_model["robust_reference_monthly_diagnostics"] = audit.get(
            "robust_reference_monthly_diagnostics", []
        )

    regime, _, benchmark_momentum60 = legacy._regime(benchmark_closes)
    breadth = fmean(legacy._float(row["gia_tren_ma250"]) for row in feature_rows)
    validation = _metric_source(final_model, champion)
    budget = dynamic_capital_budget(
        regime=regime,
        validation_rank_ic=legacy._float(validation.get("mean_rank_ic")),
        validation_top_return=legacy._float(validation.get("top_k_relative_return")),
        breadth_above_ma250=breadth,
        provisional=data_status == "PROVISIONAL_INTRADAY",
    )
    weights, selected_symbols = optimized_weights(
        symbols=[str(row["symbol"]) for row in feature_rows],
        scores=[legacy._float(row["ranking_score"]) for row in feature_rows],
        confidence=[legacy._float(row["reference_confidence"]) for row in feature_rows],
        volatility_60=[legacy._float(row["bien_dong_60"]) for row in feature_rows],
        eligible=[legacy._float(row["gia_tren_ma250"]) >= 0.5 for row in feature_rows],
        budget_pct=budget,
        top_k=TOP_K,
    )
    selected_set = set(selected_symbols)
    deployed_budget = sum(weights.values())

    predictions: list[dict[str, object]] = []
    allocations: list[dict[str, object]] = []
    for row in feature_rows:
        symbol = str(row["symbol"])
        weight = weights.get(symbol, 0.0)
        selected = symbol in selected_set and weight > 0
        predictions.append({
            "signal_date": snapshot_day.isoformat(),
            "as_of": current.isoformat(timespec="seconds"),
            "data_status": data_status,
            "symbol": symbol,
            "ranking_model": REFERENCE_MODEL,
            "ranking_score": format(legacy._float(row["ranking_score"]), ".12g"),
            "ranking_rank": ranking_rank[symbol],
            "champion_model": champion,
            "champion_score": (
                format(champion_scores_by_symbol[symbol], ".12g")
                if symbol in champion_scores_by_symbol else ""
            ),
            "champion_rank": champion_rank.get(symbol, ""),
            "reference_model": REFERENCE_MODEL,
            "reference_score": format(legacy._float(row["reference_score"]), ".12g"),
            "reference_confidence": format(legacy._float(row["reference_confidence"]), ".12g"),
            "selected_top_k": str(selected).lower(),
            "technical_weight_pct": format(weight, ".12g"),
            "allocation_model": ALLOCATOR_MODEL,
            "momentum_12_1": format(legacy._float(row["dong_luong_12_1"]), ".12g"),
            "momentum_percentile": format(legacy._float(row["momentum_percentile"]), ".12g"),
            "relative_strength_120": format(legacy._float(row["suc_manh_tuong_doi_120"]), ".12g"),
            "volatility_60": format(legacy._float(row["bien_dong_60"]), ".12g"),
            "intraday_relative_return": format(legacy._float(row["intraday_relative_return"]), ".12g"),
            "above_ma250": str(legacy._float(row["gia_tren_ma250"]) >= 0.5).lower(),
            "market_regime": regime,
            "capital_budget_pct": budget,
            "research_eligible": "false",
        })
        if selected:
            allocations.append({
                "rank": len(allocations) + 1,
                "symbol": symbol,
                "target_weight_pct": format(weight, ".12g"),
                "ranking_model": REFERENCE_MODEL,
                "champion_model": champion,
                "allocation_model": ALLOCATOR_MODEL,
                "status": "PROVISIONAL_SELECTED" if data_status == "PROVISIONAL_INTRADAY" else "SELECTED",
            })

    comparison = dict(final_model)
    comparison.update({
        "schema_version": SCHEMA_VERSION,
        "signal_date": snapshot_day.isoformat(),
        "as_of": current.isoformat(timespec="seconds"),
        "data_status": data_status,
        "ranking_model": REFERENCE_MODEL,
        "champion_model": champion,
        "reference_model": REFERENCE_MODEL,
        "allocation_model": ALLOCATOR_MODEL,
        "market_regime": regime,
        "capital_budget_pct": budget,
        "deployed_budget_pct": deployed_budget,
        "breadth_above_ma250": breadth,
        "benchmark_momentum_60": benchmark_momentum60,
        "benchmark_bar_count": len(benchmark_closes),
        "benchmark_history_status": "PASS",
        "snapshot_coverage": coverage,
        "robust_validation_status": "PASS" if audit.get("robust_reference_validation") else "MISSING",
        "model_quality_audit_error": audit_error,
        "technical_validation_only": True,
        "research_eligible": False,
        "limitations": sorted(set(list(final_model.get("limitations", [])) + [
            "provisional_snapshot_not_canonical_eod",
            "intraday_1d_candle_can_change_until_market_final",
            "sector_cap_not_enforced_without_trusted_sector_master",
        ])),
    })
    quality = {
        "status": "SUCCESS",
        "quality_tier": "PRIMARY_PROVISIONAL_DNSE" if data_status == "PROVISIONAL_INTRADAY" else "PRIMARY_LATEST_AVAILABLE_DNSE",
        "data_status": data_status,
        "session_date": snapshot_day.isoformat(),
        "as_of": current.isoformat(timespec="seconds"),
        "base_latest_date": latest_final_day.isoformat(),
        "symbol_count": len(symbols),
        "accepted_current_count": len(fresh_symbols),
        "primary_coverage": coverage,
        "source_error_count": len(errors),
        "source_errors": errors,
        "benchmark_bar_count": len(benchmark_closes),
        "benchmark_history_status": "PASS",
    }
    summary_lines = [
        f"As of: {current.isoformat(timespec='seconds')}",
        f"Data status: {data_status}",
        f"Snapshot session: {snapshot_day.isoformat()}",
        f"Base final EOD: {latest_final_day.isoformat()}",
        f"Coverage: {coverage:.2%}",
        f"Benchmark bars: {len(benchmark_closes)}",
        f"Market regime: {regime}",
        f"Breadth above MA250: {breadth:.2%}",
        f"Validation champion: {champion}",
        f"Live ranking model: {REFERENCE_MODEL}",
        f"Allocation model: {ALLOCATOR_MODEL}",
        f"Dynamic capital budget: {budget}%",
        f"Deployed budget: {deployed_budget:.4f}%",
        f"Selected: {', '.join(selected_symbols)}",
        f"Robust OOS validation: {'PASS' if audit.get('robust_reference_validation') else 'MISSING'}",
        "Research eligible: false",
        "Snapshot is provisional and never updates the official paper ledger.",
        "",
    ]

    destination.mkdir(parents=True)
    raw_dir = destination / "raw"
    prediction_dir = destination / "prediction"
    publication_dir = destination / "updated_publication"
    raw_dir.mkdir()
    prediction_dir.mkdir()
    publication_dir.mkdir()
    (raw_dir / "primary.json").write_bytes(legacy._json_bytes({
        "source": "dnse_openapi", "as_of": current.isoformat(), "rows": raw, "errors": errors,
    }))
    flattened = [row for symbol in sorted(series) for row in series[symbol]]
    publication_path = publication_dir / eod_core.PUB_FILES[0]
    publication_path.write_bytes(legacy._csv_bytes(flattened, eod_core.PUB_FIELDS))
    prediction_path = prediction_dir / "latest_prediction.csv"
    prediction_path.write_bytes(legacy._csv_bytes(predictions, tuple(predictions[0])))
    model_path = prediction_dir / "model_comparison.json"
    model_path.write_bytes(legacy._json_bytes(comparison))
    allocation_path = destination / "paper_portfolio.csv"
    allocation_path.write_bytes(legacy._csv_bytes(
        allocations,
        tuple(allocations[0]) if allocations else (
            "rank", "symbol", "target_weight_pct", "ranking_model", "champion_model", "allocation_model", "status"
        ),
    ))
    quality_path = destination / "data_quality_report.json"
    quality_path.write_bytes(legacy._json_bytes(quality))
    summary_path = destination / "daily_prediction_summary.txt"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "data_status": data_status,
        "session_date": snapshot_day.isoformat(),
        "as_of": current.isoformat(timespec="seconds"),
        "primary_coverage": coverage,
        "quality_tier": quality["quality_tier"],
        "champion_model": champion,
        "ranking_model": REFERENCE_MODEL,
        "reference_model": REFERENCE_MODEL,
        "allocation_model": ALLOCATOR_MODEL,
        "technical_validation_only": True,
        "research_eligible": False,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_bytes(legacy._json_bytes(manifest))
    archive_path = destination / "snapshot_quant_output.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path, name in (
            (prediction_path, "prediction/latest_prediction.csv"),
            (model_path, "prediction/model_comparison.json"),
            (allocation_path, "paper_portfolio.csv"),
            (quality_path, "data_quality_report.json"),
            (summary_path, "daily_prediction_summary.txt"),
            (manifest_path, "manifest.json"),
        ):
            archive.write(path, arcname=name)
    return {
        "status": "SUCCESS",
        "data_status": data_status,
        "session_date": snapshot_day.isoformat(),
        "coverage": coverage,
        "benchmark_bar_count": len(benchmark_closes),
        "capital_budget_pct": budget,
        "deployed_budget_pct": deployed_budget,
        "selected_symbols": selected_symbols,
        "output_dir": str(destination),
        "output_zip": str(archive_path),
    }
