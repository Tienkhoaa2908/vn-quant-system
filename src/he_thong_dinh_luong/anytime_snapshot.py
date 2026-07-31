"""Provisional DNSE market snapshot that can run at any time.

The snapshot never overwrites the canonical EOD publication and never updates the live
paper ledger. During a trading session, today's 1D candle is explicitly provisional.
Outside a trading session, the latest available DNSE candle is used and staleness is
reported in the manifest.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from hashlib import sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path
from statistics import fmean, pstdev
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import eod_hang_ngay as core
from .nguon_dnse import DnseRestSource
from .portfolio_weighting import (
    ALLOCATOR_MODEL,
    REFERENCE_MODEL,
    dynamic_capital_budget,
    optimized_weights,
    reference_scores,
)
from .web_local_core import artifact_paths, latest_successful_eod, read_csv_rows

SCHEMA_VERSION = "anytime_snapshot_v1"
TOP_K = 10


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _csv_bytes(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _returns(closes: Sequence[float], window: int) -> float:
    if len(closes) <= window or closes[-window - 1] <= 0:
        return 0.0
    return closes[-1] / closes[-window - 1] - 1.0


def _volatility(closes: Sequence[float], window: int) -> float:
    if len(closes) < window + 1:
        return 0.0
    returns = [closes[index] / closes[index - 1] - 1.0 for index in range(len(closes) - window, len(closes))]
    return pstdev(returns) if len(returns) > 1 else 0.0


def _ma(closes: Sequence[float], window: int) -> float:
    if len(closes) < window:
        return 0.0
    return fmean(closes[-window:])


def _series(rows: Sequence[Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    output: dict[str, list[dict[str, object]]] = {}
    for raw in rows:
        symbol = str(raw.get("ma", "")).strip().upper()
        day = str(raw.get("ngay", "")).strip()[:10]
        if not symbol or not day:
            continue
        output.setdefault(symbol, []).append({
            "ma": symbol,
            "ngay": day,
            "gia_mo_cua": _float(raw.get("gia_mo_cua")),
            "gia_dong_cua": _float(raw.get("gia_dong_cua")),
            "khoi_luong": int(_float(raw.get("khoi_luong"))),
            "nguon": str(raw.get("nguon", "")),
            "phien_ban": str(raw.get("phien_ban", "")),
            "co_so_gia": str(raw.get("co_so_gia", "")),
            "raw_sha256": str(raw.get("raw_sha256", "")),
        })
    for values in output.values():
        values.sort(key=lambda row: str(row["ngay"]))
    return output


def _replace_or_append(values: list[dict[str, object]], row: core.EodRow, *, provisional: bool) -> None:
    payload = row.payload()
    raw_hash = sha256(_json_bytes(payload)).hexdigest()
    normalized = {
        "ma": row.symbol,
        "ngay": row.day.isoformat(),
        "gia_mo_cua": row.open,
        "gia_dong_cua": row.close,
        "khoi_luong": row.volume,
        "nguon": row.source,
        "phien_ban": row.version,
        "co_so_gia": "DNSE_1D_PROVISIONAL" if provisional else "DNSE_1D_LATEST_AVAILABLE",
        "raw_sha256": raw_hash,
    }
    for index, existing in enumerate(values):
        if existing["ngay"] == normalized["ngay"]:
            values[index] = normalized
            break
    else:
        values.append(normalized)
    values.sort(key=lambda item: str(item["ngay"]))


def _feature_row(
    symbol: str,
    values: Sequence[Mapping[str, object]],
    benchmark_closes: Sequence[float],
    *,
    snapshot_day: date,
    latest_final_day: date,
    benchmark_intraday_return: float,
) -> dict[str, object] | None:
    usable = [row for row in values if _float(row.get("gia_dong_cua")) > 0]
    closes = [_float(row["gia_dong_cua"]) for row in usable]
    if len(closes) < 251:
        return None
    ma60 = _ma(closes, 60)
    ma120 = _ma(closes, 120)
    ma250 = _ma(closes, 250)
    previous_final = next(
        (_float(row["gia_dong_cua"]) for row in reversed(usable) if str(row["ngay"]) <= latest_final_day.isoformat()),
        closes[-1],
    )
    intraday_return = closes[-1] / previous_final - 1.0 if previous_final > 0 and snapshot_day > latest_final_day else 0.0
    return {
        "symbol": symbol,
        "dong_luong_12_1": closes[-21] / closes[-251] - 1.0,
        "suc_manh_tuong_doi_120": _returns(closes, 120) - _returns(benchmark_closes, 120),
        "bien_dong_60": _volatility(closes, 60),
        "khoang_cach_ma60": closes[-1] / ma60 - 1.0 if ma60 > 0 else 0.0,
        "khoang_cach_ma120": closes[-1] / ma120 - 1.0 if ma120 > 0 else 0.0,
        "khoang_cach_ma250": closes[-1] / ma250 - 1.0 if ma250 > 0 else 0.0,
        "loi_nhuan_20": _returns(closes, 20),
        "loi_nhuan_60": _returns(closes, 60),
        "loi_nhuan_120": _returns(closes, 120),
        "loi_nhuan_250": _returns(closes, 250),
        "gia_tren_ma250": 1.0 if ma250 > 0 and closes[-1] > ma250 else 0.0,
        "intraday_relative_return": intraday_return - benchmark_intraday_return,
        "latest_close": closes[-1],
    }


def _regime(benchmark_closes: Sequence[float]) -> tuple[str, float, float]:
    ma250 = _ma(benchmark_closes, 250)
    momentum60 = _returns(benchmark_closes, 60)
    above = bool(ma250 > 0 and benchmark_closes[-1] > ma250)
    if above and momentum60 > 0:
        return "RISK_ON", 1.0, momentum60
    if above or momentum60 > 0:
        return "NEUTRAL", 1.0 if above else 0.0, momentum60
    return "RISK_OFF", 0.0, momentum60


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
    final_run = latest_successful_eod(root)
    if final_run is None:
        raise ValueError("FINAL_EOD_BASE_NOT_FOUND")
    final_paths = artifact_paths(final_run)
    publication_rows = read_csv_rows(final_paths["publication"], limit=10_000_000)
    if not publication_rows:
        raise ValueError("FINAL_PUBLICATION_EMPTY")
    final_model = _read_json(final_paths["model"])
    latest_final_day = max(date.fromisoformat(str(row["ngay"])[:10]) for row in publication_rows)
    series = _series(publication_rows)
    symbols = sorted(symbol for symbol in series if symbol != "VNINDEX")
    current = (now or datetime.now(core.VN_TZ)).astimezone(core.VN_TZ)
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
        is_current_day = snapshot_day == today
        provisional = is_current_day and current.hour < 18
        if snapshot_day < today:
            data_status = "LAST_AVAILABLE"
        elif provisional:
            data_status = "PROVISIONAL_INTRADAY"
        else:
            data_status = "FINAL_UNCONFIRMED"
        benchmark_values = series.setdefault("VNINDEX", [])
        for row in benchmark_rows:
            if row.day >= latest_final_day:
                _replace_or_append(benchmark_values, row, provisional=provisional and row.day == snapshot_day)
        raw["VNINDEX"] = [row.payload() for row in benchmark_rows]

        fresh_symbols: set[str] = set()
        for symbol in symbols:
            try:
                fetched = tuple(client.fetch(symbol, fetch_start, today))
                raw[symbol] = [row.payload() for row in fetched]
                eligible_rows = [row for row in fetched if row.day <= snapshot_day]
                if eligible_rows:
                    latest = max(eligible_rows, key=lambda row: row.day)
                    _replace_or_append(series[symbol], latest, provisional=provisional and latest.day == snapshot_day)
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

    benchmark_closes = [_float(row["gia_dong_cua"]) for row in series["VNINDEX"] if _float(row["gia_dong_cua"]) > 0]
    previous_benchmark = next(
        (_float(row["gia_dong_cua"]) for row in reversed(series["VNINDEX"]) if str(row["ngay"]) <= latest_final_day.isoformat()),
        benchmark_closes[-1],
    )
    benchmark_intraday = benchmark_closes[-1] / previous_benchmark - 1.0 if snapshot_day > latest_final_day and previous_benchmark > 0 else 0.0
    feature_rows: list[dict[str, object]] = []
    for symbol in symbols:
        row = _feature_row(
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

    scores, components, confidence = reference_scores(feature_rows)
    for index, row in enumerate(feature_rows):
        # Intraday relative strength is useful but deliberately limited to 10%.
        row["reference_score"] = 0.90 * scores[index] + 0.10 * max(0.0, min(1.0, 0.5 + 5.0 * _float(row["intraday_relative_return"])))
        row["reference_confidence"] = confidence[index]
        row["components"] = components[index]
    feature_rows.sort(key=lambda row: (-_float(row["reference_score"]), str(row["symbol"])))

    regime, _, benchmark_momentum60 = _regime(benchmark_closes)
    breadth = fmean(_float(row["gia_tren_ma250"]) for row in feature_rows)
    validation = final_model.get("momentum_validation") if isinstance(final_model.get("momentum_validation"), Mapping) else {}
    validation_ic = _float(validation.get("mean_rank_ic"))
    validation_return = _float(validation.get("top_k_relative_return"))
    budget = dynamic_capital_budget(
        regime=regime,
        validation_rank_ic=validation_ic,
        validation_top_return=validation_return,
        breadth_above_ma250=breadth,
        provisional=data_status == "PROVISIONAL_INTRADAY",
    )
    weights, selected_symbols = optimized_weights(
        symbols=[str(row["symbol"]) for row in feature_rows],
        scores=[_float(row["reference_score"]) for row in feature_rows],
        confidence=[_float(row["reference_confidence"]) for row in feature_rows],
        volatility_60=[_float(row["bien_dong_60"]) for row in feature_rows],
        eligible=[bool(_float(row["gia_tren_ma250"]) >= 0.5) for row in feature_rows],
        budget_pct=budget,
        top_k=TOP_K,
    )
    rank_by_symbol = {str(row["symbol"]): rank for rank, row in enumerate(feature_rows, start=1)}
    selected_set = set(selected_symbols)
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
            "champion_model": str(final_model.get("champion_model", "momentum_baseline")),
            "reference_model": REFERENCE_MODEL,
            "champion_score": format(_float(row["reference_score"]), ".12g"),
            "champion_rank": rank_by_symbol[symbol],
            "selected_top_k": str(selected).lower(),
            "technical_weight_pct": format(weight, ".12g"),
            "reference_confidence": format(_float(row["reference_confidence"]), ".12g"),
            "momentum_12_1": format(_float(row["dong_luong_12_1"]), ".12g"),
            "relative_strength_120": format(_float(row["suc_manh_tuong_doi_120"]), ".12g"),
            "volatility_60": format(_float(row["bien_dong_60"]), ".12g"),
            "intraday_relative_return": format(_float(row["intraday_relative_return"]), ".12g"),
            "above_ma250": str(bool(_float(row["gia_tren_ma250"]) >= 0.5)).lower(),
            "market_regime": regime,
            "capital_budget_pct": budget,
            "research_eligible": "false",
        })
        if selected:
            allocations.append({
                "rank": len(allocations) + 1,
                "symbol": symbol,
                "target_weight_pct": format(weight, ".12g"),
                "champion_model": str(final_model.get("champion_model", "momentum_baseline")),
                "allocation_model": ALLOCATOR_MODEL,
                "status": "PROVISIONAL_SELECTED" if data_status == "PROVISIONAL_INTRADAY" else "SELECTED",
            })

    comparison = dict(final_model)
    comparison.update({
        "schema_version": SCHEMA_VERSION,
        "signal_date": snapshot_day.isoformat(),
        "as_of": current.isoformat(timespec="seconds"),
        "data_status": data_status,
        "reference_model": REFERENCE_MODEL,
        "allocation_model": ALLOCATOR_MODEL,
        "market_regime": regime,
        "capital_budget_pct": budget,
        "breadth_above_ma250": breadth,
        "benchmark_momentum_60": benchmark_momentum60,
        "snapshot_coverage": coverage,
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
    }
    summary_lines = [
        f"As of: {current.isoformat(timespec='seconds')}",
        f"Data status: {data_status}",
        f"Snapshot session: {snapshot_day.isoformat()}",
        f"Base final EOD: {latest_final_day.isoformat()}",
        f"Coverage: {coverage:.2%}",
        f"Market regime: {regime}",
        f"Breadth above MA250: {breadth:.2%}",
        f"Reference model: {REFERENCE_MODEL}",
        f"Allocation model: {ALLOCATOR_MODEL}",
        f"Dynamic capital budget: {budget}%",
        f"Selected: {', '.join(selected_symbols)}",
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
    (raw_dir / "primary.json").write_bytes(_json_bytes({
        "source": "dnse_openapi", "as_of": current.isoformat(), "rows": raw, "errors": errors,
    }))
    flattened = [row for symbol in sorted(series) for row in series[symbol]]
    publication_path = publication_dir / core.PUB_FILES[0]
    publication_path.write_bytes(_csv_bytes(flattened, core.PUB_FIELDS))
    prediction_path = prediction_dir / "latest_prediction.csv"
    prediction_path.write_bytes(_csv_bytes(predictions, tuple(predictions[0])))
    model_path = prediction_dir / "model_comparison.json"
    model_path.write_bytes(_json_bytes(comparison))
    allocation_path = destination / "paper_portfolio.csv"
    allocation_path.write_bytes(_csv_bytes(allocations, tuple(allocations[0]) if allocations else (
        "rank", "symbol", "target_weight_pct", "champion_model", "allocation_model", "status"
    )))
    quality_path = destination / "data_quality_report.json"
    quality_path.write_bytes(_json_bytes(quality))
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
        "champion_model": final_model.get("champion_model", ""),
        "reference_model": REFERENCE_MODEL,
        "allocation_model": ALLOCATOR_MODEL,
        "technical_validation_only": True,
        "research_eligible": False,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
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
        "capital_budget_pct": budget,
        "selected_symbols": selected_symbols,
        "output_dir": str(destination),
        "output_zip": str(archive_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.anytime_snapshot")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-coverage", type=float, default=0.80)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(data_root=args.data_root, output_dir=args.output_dir, min_coverage=args.min_coverage)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
