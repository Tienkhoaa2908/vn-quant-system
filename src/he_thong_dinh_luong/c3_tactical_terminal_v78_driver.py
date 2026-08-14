"""Safety wrapper for V78 operational tactical output.

The core preview ranks only currently eligible names. This wrapper additionally
keeps every prior-month C3 Top10 incumbent visible when it loses current
eligibility, so a falling/illiquid incumbent can never disappear from the health
screen merely because it failed the new-month eligibility filter.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from . import c3_tactical_terminal_v78 as core
from . import deep_portfolio_backtest_v70 as v70
from . import learned_ranking_challenger_v76 as v76
from . import paper_oos_data_lineage_v77 as v77


def _incumbent_fallback_row(
    market: v70.Market,
    *,
    symbol: str,
    canonical_rank: int,
    capture_day: date,
    ridge_monthly_top10: set[str],
) -> dict[str, object]:
    raw = v76._raw_features(market, symbol, capture_day)
    relative_5 = float(raw["relative_5"]) if raw else 0.0
    drawdown_20 = float(raw["drawdown_20"]) if raw else -1.0
    drawdown_60 = float(raw["drawdown_60"]) if raw else -1.0
    volume_ratio = core._volume_ratio(raw) if raw else 0.0
    return {
        "evaluation_day": capture_day.isoformat(),
        "symbol": symbol,
        "canonical_rank": canonical_rank,
        "preview_rank": None,
        "preview_score": None,
        "rank_delta": None,
        "eligible_now": False,
        "relative_5": relative_5,
        "drawdown_20": drawdown_20,
        "drawdown_60": drawdown_60,
        "volume_ratio_5_20": volume_ratio,
        "ridge_monthly_top10": symbol in ridge_monthly_top10,
    }


def _ridge_recent_from_file(path: Path) -> list[dict[str, object]]:
    rows = []
    for raw in core._read_csv(path):
        if str(raw.get("variant_id") or "") != "GAP18_CLEAN":
            continue
        if str(raw.get("allocator") or "") != "EQUAL":
            continue
        if str(raw.get("cost_scenario") or "") != "BASE_DNSE":
            continue
        policy = str(raw.get("policy_id") or "")
        if policy not in {v76.BASE_POLICY, core.SECONDARY_MODEL}:
            continue
        row = dict(raw); row["model_key"] = policy; rows.append(row)
    return core.recent_window_summary(
        rows,
        policy_field="model_key",
        baseline_id=v76.BASE_POLICY,
        candidate_ids=(core.SECONDARY_MODEL,),
    )


def run(
    *,
    store: Path,
    v77_state_dir: Path,
    tactical_state_dir: Path,
    output_dir: Path,
    artifact_root: Path | None = None,
    v72_monthly: Path | None = None,
    v76_monthly: Path | None = None,
) -> dict[str, object]:
    store = Path(store); v77_state_dir = Path(v77_state_dir)
    freeze_path = v77_state_dir / "freeze_manifest.json"
    if not store.is_file() or not freeze_path.is_file():
        raise ValueError("V78_REQUIRES_EXISTING_V77_FREEZE_AND_STORE")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    if freeze.get("champion_model") != core.OPERATIONAL_CHAMPION or freeze.get("shadow_model") != core.SECONDARY_MODEL:
        raise ValueError("V78_V77_MODEL_DEFINITION_MISMATCH")
    symbols = [str(value).upper() for value in freeze.get("variant_symbols", [])]
    if len(symbols) < 10:
        raise ValueError("V78_FROZEN_SYMBOL_SET_INVALID")
    market = v70.load_market(store, symbols)
    capture_day = core._latest_market_day(market)
    rank_snapshot = v77._build_rank_snapshot(
        store=store,
        fixed_symbols=symbols,
        capture_day=capture_day,
        wall_date=capture_day,
        month_close_confirmed=False,
    )
    monthly_ranking = rank_snapshot["rankings"][core.OPERATIONAL_CHAMPION]
    monthly_map = {str(row["symbol"]): int(row["rank"]) for row in monthly_ranking}
    monthly_top10_symbols = [str(row["symbol"]) for row in monthly_ranking if int(row["rank"]) <= 10]
    ridge_top10 = {str(row["symbol"]) for row in rank_snapshot["rankings"][core.SECONDARY_MODEL][:10]}

    preview = core._build_preview(
        market,
        symbols,
        capture_day,
        monthly_ranking,
        rank_snapshot["c3_weights"],
        ridge_top10,
    )
    present = {str(row["symbol"]) for row in preview}
    for symbol in monthly_top10_symbols:
        if symbol not in present:
            preview.append(_incumbent_fallback_row(
                market,
                symbol=symbol,
                canonical_rank=monthly_map[symbol],
                capture_day=capture_day,
                ridge_monthly_top10=ridge_top10,
            ))

    prior = core._prior_week_preview(tactical_state_dir, capture_day)
    tactical_rows, swap_pair = core.classify_tactical_rows(preview, prior_preview_rank=prior)
    preview_path = core._persist_preview(tactical_state_dir, capture_day, preview)

    artifact_root = Path(artifact_root) if artifact_root else None
    if v72_monthly is None and artifact_root:
        v72_monthly = core._find_latest(artifact_root, "v72_monthly_returns.csv")
    if v76_monthly is None and artifact_root:
        v76_monthly = core._find_latest(artifact_root, "v76_monthly_returns.csv")

    v72_recent: list[dict[str, object]] = []
    if v72_monthly and Path(v72_monthly).is_file():
        rows72 = core._filter_v72_recent(core._read_csv(Path(v72_monthly)))
        v72_recent = core.recent_window_summary(
            rows72,
            policy_field="policy_id",
            baseline_id="NO_OVERLAY",
            candidate_ids=("L15_SWAP50_WORST", "R08_TRIM50_CASH"),
        )
    ridge_recent: list[dict[str, object]] = []
    if v76_monthly and Path(v76_monthly).is_file():
        ridge_recent = _ridge_recent_from_file(Path(v76_monthly))

    top10 = [row for row in tactical_rows if core._int(row.get("canonical_rank")) <= 10]
    top10.sort(key=lambda row: core._int(row.get("canonical_rank")))
    health = [row for row in top10 if row.get("action") in {"WATCH", "RISK_ALERT_R08", "L15_SWAP_OUT_CANDIDATE"}]
    emerging = [row for row in tactical_rows if row.get("action") in {"L15_SWAP_IN_CANDIDATE", "WATCH_EMERGING", "RIDGE_CONFIRMATION"}]
    emerging.sort(key=lambda row: core._int(row.get("preview_rank")))
    ranked_now = [row for row in tactical_rows if row.get("preview_rank") not in (None, "")]
    ranked_now.sort(key=lambda row: core._int(row.get("preview_rank")))

    report = {
        "schema_version": core.SCHEMA_VERSION,
        "status": "SUCCESS",
        "operational_champion": core.OPERATIONAL_CHAMPION,
        "operational_champion_finalized": True,
        "secondary_model": core.SECONDARY_MODEL,
        "secondary_role": "SHADOW_CONFIRMATION_AND_EMERGENCE_RADAR_ONLY",
        "primary_variant": core.PRIMARY_VARIANT,
        "primary_allocator": core.PRIMARY_ALLOCATOR,
        "capture_day": capture_day.isoformat(),
        "source_monthly_signal_day": rank_snapshot["source_signal_day"],
        "risk_on": bool(rank_snapshot["risk_on"]),
        "c3_weights": rank_snapshot["c3_weights"],
        "eligible_now_count": sum(bool(row.get("eligible_now")) for row in tactical_rows),
        "monthly_top10": [str(row["symbol"]) for row in top10],
        "current_preview_top10": [str(row["symbol"]) for row in ranked_now[:10]],
        "ridge_monthly_top10": sorted(ridge_top10),
        "incumbent_health_alert_count": len(health),
        "emerging_radar_count": len(emerging),
        "l15_swap_pair": swap_pair,
        "preview_state_path": str(preview_path),
        "prior_week_preview_available": bool(prior),
        "incumbent_visibility_fail_closed": True,
        "tactical_semantics": {
            "monthly_c3_top10_remains_core": True,
            "prior_month_top10_never_hidden_by_current_eligibility_failure": True,
            "r07_r08_are_advisory_health_alerts": True,
            "r07_r08_auto_sell": False,
            "l15_exact_trigger_required_for_swap_advice": True,
            "l15_fraction": 0.50,
            "no_live_order": True,
        },
        "recent_regime_evidence": {
            "windows_months": list(core.RECENT_WINDOWS),
            "v72_monthly_source": str(v72_monthly) if v72_monthly else None,
            "v72": v72_recent,
            "v76_monthly_source": str(v76_monthly) if v76_monthly else None,
            "ridge": ridge_recent,
            "interpretation": "Recent fixed windows are regime evidence only; C3 remains operational main model regardless of Ridge/overlay recent shadow behavior.",
        },
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    core._write_csv(output_dir / "v78_tactical_rows.csv", tactical_rows)
    core._write_csv(output_dir / "v78_incumbent_health.csv", health)
    core._write_csv(output_dir / "v78_emerging_radar.csv", emerging)
    core._write_csv(output_dir / "v78_recent_v72.csv", v72_recent)
    core._write_csv(output_dir / "v78_recent_ridge.csv", ridge_recent)
    (output_dir / "v78_report.json").write_text(core._json_text(report), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.c3_tactical_terminal_v78_driver")
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--v77-state-dir", type=Path, required=True)
    parser.add_argument("--tactical-state-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--v72-monthly", type=Path)
    parser.add_argument("--v76-monthly", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run(
            store=args.store,
            v77_state_dir=args.v77_state_dir,
            tactical_state_dir=args.tactical_state_dir,
            output_dir=args.output_dir,
            artifact_root=args.artifact_root,
            v72_monthly=args.v72_monthly,
            v76_monthly=args.v76_monthly,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "status": report["status"],
        "operational_champion": report["operational_champion"],
        "capture_day": report["capture_day"],
        "monthly_top10": report["monthly_top10"],
        "current_preview_top10": report["current_preview_top10"],
        "incumbent_health_alert_count": report["incumbent_health_alert_count"],
        "emerging_radar_count": report["emerging_radar_count"],
        "l15_swap_pair": report["l15_swap_pair"],
        "recent_v72_rows": len(report["recent_regime_evidence"]["v72"]),
        "recent_ridge_rows": len(report["recent_regime_evidence"]["ridge"]),
        "live_orders_allowed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
