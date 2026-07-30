"""Orchestrator EOD incremental: bat kip tat ca phien thieu roi moi du doan."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Callable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from . import eod_hang_ngay as core
from .nguon_dnse import DnseRestSource

SCHEMA_VERSION = "eod_daily_quant_v3"
VN_TZ = core.VN_TZ
EodRow = core.EodRow
VnstockSource = core.VnstockSource
Source = core.Source
PUB_FILES = core.PUB_FILES
PUB_FIELDS = core.PUB_FIELDS
FEATURE_PREFIX = core.FEATURE_PREFIX

# Re-export de test hop dong nho khong phu thuoc mang.
_crosscheck = core._crosscheck
_csv_bytes = core._csv_bytes
_json_bytes = core._json_bytes
_sha_bytes = core._sha_bytes


def _source_from_name(name: str) -> Source:
    normalized = name.strip().lower()
    if normalized == "dnse":
        return DnseRestSource.from_env()
    if normalized in {"kbs", "vci"}:
        return VnstockSource(normalized)
    raise ValueError(f"EOD_SOURCE_UNSUPPORTED:{name}")


def _accepted_incremental_rows(
    *,
    symbol: str,
    primary_rows: Sequence[EodRow],
    secondary_rows: Sequence[EodRow],
    required_sessions: Sequence[date],
    price_tolerance_bps: float,
    volume_tolerance_ratio: float,
) -> tuple[tuple[EodRow, ...], tuple[str, ...]]:
    """Chi chap nhan mot ma khi tat ca phien thieu deu co va khop hai nguon."""
    primary = core._by_day(primary_rows)
    secondary = core._by_day(secondary_rows)
    accepted: list[EodRow] = []
    reasons: list[str] = []
    for session in required_sessions:
        left = primary.get(session)
        right = secondary.get(session)
        if left is None or right is None:
            reasons.append(f"MISSING_SESSION:{session}")
            continue
        mismatch = core._crosscheck(
            left, right, price_tolerance_bps, volume_tolerance_ratio
        )
        if mismatch:
            reasons.extend(f"{session}:{reason}" for reason in mismatch)
            continue
        accepted.append(left)
    if reasons:
        return (), tuple(sorted(set(reasons)))
    if len(accepted) != len(required_sessions):
        return (), (f"INCREMENTAL_COUNT_MISMATCH:{symbol}",)
    return tuple(accepted), ()


def _benchmark_history(
    primary_rows: Sequence[EodRow],
    secondary_rows: Sequence[EodRow],
    *,
    price_tolerance_bps: float,
) -> tuple[EodRow, ...]:
    """Benchmark chi can close; bo qua volume mismatch nhung chan open/close mismatch."""
    primary = core._by_day(primary_rows)
    secondary = core._by_day(secondary_rows)
    output: list[EodRow] = []
    for session in sorted(set(primary) & set(secondary)):
        mismatch = core._crosscheck(
            primary[session], secondary[session], price_tolerance_bps, 1.0
        )
        price_mismatch = [reason for reason in mismatch if reason != "VOLUME_MISMATCH"]
        if not price_mismatch:
            output.append(primary[session])
    return tuple(output)


def run(
    *,
    data_root: Path,
    output_dir: Path,
    target_date: date | None = None,
    prediction_input: Path | None = None,
    primary: Source | None = None,
    secondary: Source | None = None,
    min_coverage: float = 0.95,
    price_tolerance_bps: float = 10.0,
    volume_tolerance_ratio: float = 0.05,
    now: datetime | None = None,
    forward_runner: Callable[..., Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if not 0 < min_coverage <= 1:
        raise ValueError("MIN_COVERAGE_INVALID")
    current = now or datetime.now(VN_TZ)
    if current.tzinfo is None:
        raise ValueError("NOW_MUST_BE_TIMEZONE_AWARE")
    current_vn = current.astimezone(VN_TZ)
    today = current_vn.date()
    target = target_date or today
    if target == today and current_vn.hour < 18:
        raise ValueError("MARKET_NOT_FINAL_BEFORE_18H_VN")

    root = Path(data_root)
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    source_zip = prediction_input or root / "prediction_input.zip"
    if not source_zip.is_file():
        raise ValueError("PREDICTION_INPUT_NOT_FOUND")

    base = core.discover_publication(root)
    base_rows, fields = core._read_csv(base / PUB_FILES[0])
    if fields != PUB_FIELDS:
        raise ValueError("BASE_PUBLICATION_SCHEMA_INVALID")
    symbols = sorted({row["ma"].strip().upper() for row in base_rows})
    latest_local = max(date.fromisoformat(row["ngay"]) for row in base_rows)

    primary = primary or DnseRestSource.from_env()
    secondary = secondary or VnstockSource("kbs")
    if primary.name == secondary.name:
        raise ValueError("EOD_SOURCES_MUST_DIFFER")

    benchmark_start = min(latest_local - timedelta(days=10), target - timedelta(days=650))
    primary_benchmark = tuple(
        primary.fetch("VNINDEX", benchmark_start, target, is_index=True)
    )
    secondary_benchmark = tuple(
        secondary.fetch("VNINDEX", benchmark_start, target, is_index=True)
    )
    benchmark = _benchmark_history(
        primary_benchmark,
        secondary_benchmark,
        price_tolerance_bps=price_tolerance_bps,
    )
    sessions = [row.day for row in benchmark if row.day <= target]
    if not sessions:
        raise ValueError("BENCHMARK_COMMON_SESSION_NOT_FOUND")
    session = max(sessions)
    if target == today and target.weekday() < 5 and session < target:
        raise ValueError(f"EOD_NOT_PUBLISHED:{session}")

    required_sessions = tuple(
        day for day in sorted(set(sessions)) if latest_local < day <= session
    )
    # Cho phep chay lai cung ngay de tai tao output, nhung van doi chieu phien hien tai.
    sessions_to_check = required_sessions or (session,)
    fetch_start = min(latest_local - timedelta(days=10), sessions_to_check[0])

    destination.mkdir(parents=True)
    raw_dir = destination / "raw"
    raw_dir.mkdir()

    accepted_incremental: list[EodRow] = []
    accepted_current_symbols: set[str] = set()
    results: list[dict[str, object]] = []
    raw_primary: dict[str, object] = {}
    raw_secondary: dict[str, object] = {}

    for symbol in symbols:
        try:
            left_rows = tuple(primary.fetch(symbol, fetch_start, target))
            right_rows = tuple(secondary.fetch(symbol, fetch_start, target))
            raw_primary[symbol] = [row.payload() for row in left_rows]
            raw_secondary[symbol] = [row.payload() for row in right_rows]
            accepted, reasons = _accepted_incremental_rows(
                symbol=symbol,
                primary_rows=left_rows,
                secondary_rows=right_rows,
                required_sessions=sessions_to_check,
                price_tolerance_bps=price_tolerance_bps,
                volume_tolerance_ratio=volume_tolerance_ratio,
            )
            if reasons:
                results.append({
                    "symbol": symbol,
                    "status": "MISSING_OR_MISMATCH",
                    "reasons": list(reasons),
                })
                continue
            if any(row.day == session for row in accepted):
                accepted_current_symbols.add(symbol)
            if required_sessions:
                accepted_incremental.extend(accepted)
            results.append({
                "symbol": symbol,
                "status": "ACCEPTED",
                "accepted_sessions": [row.day.isoformat() for row in accepted],
            })
        except Exception as exc:
            results.append({
                "symbol": symbol,
                "status": "SOURCE_ERROR",
                "reasons": [f"{type(exc).__name__}:{exc}"],
            })

    primary_raw_path = raw_dir / "primary.json"
    secondary_raw_path = raw_dir / "secondary.json"
    primary_raw_path.write_bytes(core._json_bytes({
        "role": "primary",
        "source": primary.name,
        "version": primary.version,
        "session": session.isoformat(),
        "required_sessions": [day.isoformat() for day in required_sessions],
        "rows": raw_primary,
    }))
    secondary_raw_path.write_bytes(core._json_bytes({
        "role": "secondary",
        "source": secondary.name,
        "version": secondary.version,
        "session": session.isoformat(),
        "required_sessions": [day.isoformat() for day in required_sessions],
        "rows": raw_secondary,
    }))

    coverage = len(accepted_current_symbols) / len(symbols)
    quality = {
        "schema_version": SCHEMA_VERSION,
        "status": "FINAL" if coverage >= min_coverage else "NOT_FINAL",
        "target_date": target.isoformat(),
        "session_date": session.isoformat(),
        "base_latest_date": latest_local.isoformat(),
        "required_incremental_sessions": [day.isoformat() for day in required_sessions],
        "base_publication": str(base),
        "sources": {
            "primary": {"name": primary.name, "version": primary.version},
            "secondary": {"name": secondary.name, "version": secondary.version},
        },
        "symbol_count": len(symbols),
        "accepted_current_count": len(accepted_current_symbols),
        "accepted_incremental_row_count": len(accepted_incremental),
        "coverage": coverage,
        "minimum_coverage": min_coverage,
        "price_tolerance_bps": price_tolerance_bps,
        "volume_tolerance_ratio": volume_tolerance_ratio,
        "results": results,
        "raw_sha256": {
            "primary.json": core._sha_file(primary_raw_path),
            "secondary.json": core._sha_file(secondary_raw_path),
        },
    }
    quality_path = destination / "data_quality_report.json"
    quality_path.write_bytes(core._json_bytes(quality))
    if coverage < min_coverage:
        raise ValueError(f"EOD_DATA_NOT_FINAL:{coverage:.6f}")

    merged = core._merge_rows(base_rows, accepted_incremental)
    publication_dir = destination / "updated_publication"
    core._write_publication(publication_dir, merged, base, f"eod_{session}")

    blobs, _ = core._load_prediction_zip(source_zip)
    features, omitted = core._feature_rows(
        merged, benchmark, session, blobs["cau_hinh.json"]
    )
    feature_coverage = len(features) / len(symbols)
    if feature_coverage < min_coverage:
        raise ValueError(
            f"FEATURE_COVERAGE_NOT_FINAL:{len(features)}/{len(symbols)}"
        )

    daily_input = destination / "daily_prediction_input.zip"
    core._daily_input(source_zip, daily_input, features, session)
    if forward_runner is None:
        from .nghien_cuu_moc_4.du_doan_tien_phuong import run_forward_prediction
        forward_runner = run_forward_prediction
    prediction_dir = destination / "prediction"
    forward = dict(forward_runner(
        input_zip=daily_input,
        output_dir=prediction_dir,
        top_k=10,
        validation_months=12,
        seed=20260730,
    ))

    latest_prediction = prediction_dir / "latest_prediction.csv"
    model_comparison = prediction_dir / "model_comparison.json"
    paper_fields = (
        "signal_date", "symbol", "champion_model", "rank",
        "target_weight_pct", "status",
    )
    paper = destination / "paper_portfolio.csv"
    paper.write_bytes(core._csv_bytes(
        core._paper_rows(latest_prediction), paper_fields
    ))
    summary = destination / "daily_prediction_summary.txt"
    summary.write_text("\n".join([
        "Data status: FINAL",
        f"Session date: {session}",
        f"Prediction for: next trading session after {session}",
        f"Primary source: {primary.name} {primary.version}",
        f"Secondary source: {secondary.name} {secondary.version}",
        f"Missing sessions caught up: {len(required_sessions)}",
        f"Data coverage: {len(accepted_current_symbols)}/{len(symbols)} ({coverage:.2%})",
        f"Feature coverage: {len(features)}/{len(symbols)} ({feature_coverage:.2%})",
        f"Champion model: {forward.get('champion_model')}",
        f"Market regime: {forward.get('market_regime')}",
        f"Technical capital budget: {forward.get('capital_budget_pct')}%",
        f"Top 10: {', '.join(forward.get('top_symbols', []))}",
        "Research eligible: false",
        "Use: technical ranking and paper trading only.",
        "",
    ]), encoding="utf-8")

    final_files = {
        "data_quality_report.json": quality_path,
        "daily_prediction_summary.txt": summary,
        "latest_prediction.csv": latest_prediction,
        "model_comparison.json": model_comparison,
        "paper_portfolio.csv": paper,
        "prediction_manifest.json": prediction_dir / "manifest.json",
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_bytes(core._json_bytes({
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "session_date": session.isoformat(),
        "base_latest_date": latest_local.isoformat(),
        "required_incremental_sessions": [day.isoformat() for day in required_sessions],
        "sources": {
            "primary": {"name": primary.name, "version": primary.version},
            "secondary": {"name": secondary.name, "version": secondary.version},
        },
        "daily_prediction_input_sha256": core._sha_file(daily_input),
        "technical_validation_only": True,
        "research_eligible": False,
        "raw_excluded_from_zip": True,
        "feature_omitted": omitted,
        "files": {
            name: {"sha256": core._sha_file(path), "size": path.stat().st_size}
            for name, path in final_files.items()
        },
    }))
    final_files["manifest.json"] = manifest_path
    output_zip = destination / "daily_quant_output.zip"
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        for name, path in sorted(final_files.items()):
            archive.write(path, arcname=name)

    return {
        "status": "SUCCESS",
        "session_date": session.isoformat(),
        "caught_up_session_count": len(required_sessions),
        "coverage": coverage,
        "feature_count": len(features),
        "primary_source": primary.name,
        "secondary_source": secondary.name,
        "champion_model": forward.get("champion_model"),
        "top_symbols": forward.get("top_symbols", []),
        "output_zip": str(output_zip),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.eod_hang_ngay_v2"
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prediction-input", type=Path)
    parser.add_argument("--target-date", type=date.fromisoformat)
    parser.add_argument("--primary-source", choices=("dnse", "kbs", "vci"), default="dnse")
    parser.add_argument("--secondary-source", choices=("dnse", "kbs", "vci"), default="kbs")
    parser.add_argument("--min-coverage", type=float, default=0.95)
    parser.add_argument("--price-tolerance-bps", type=float, default=10.0)
    parser.add_argument("--volume-tolerance-ratio", type=float, default=0.05)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.primary_source == args.secondary_source:
            raise ValueError("EOD_SOURCES_MUST_DIFFER")
        primary = _source_from_name(args.primary_source)
        secondary = _source_from_name(args.secondary_source)
        result = run(
            data_root=args.data_root,
            output_dir=args.output_dir,
            prediction_input=args.prediction_input,
            target_date=args.target_date,
            primary=primary,
            secondary=secondary,
            min_coverage=args.min_coverage,
            price_tolerance_bps=args.price_tolerance_bps,
            volume_tolerance_ratio=args.volume_tolerance_ratio,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
