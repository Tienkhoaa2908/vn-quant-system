"""V78 operational C3 tactical layer.

C3_STABLE_3_PAST_IC_SHRUNK is the finalized operational ranking core.  This
module does not search for a new champion.  It adds an advisory intra-month
layer using the exact existing C3 components plus the previously researched
V72 trigger definitions:

* incumbent health: R07/R08 drawdown alerts on last monthly Top10;
* emerging leaders: L15 persistence/relative-strength/volume trigger;
* Ridge: monthly shadow confirmation only, never an automatic replacement.

The module also summarizes fixed recent 6/12/18-month windows from already
observed V72/V76 monthly-return artifacts when those files are present.  Those
windows are regime evidence, not a new universal promotion test.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from datetime import date
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import learned_ranking_challenger_v76 as v76
from . import paper_oos_data_lineage_v77 as v77
from . import weekly_overlay_backtest_v72 as v72

SCHEMA_VERSION = "c3_tactical_terminal_v78"
OPERATIONAL_CHAMPION = "C3_STABLE_3_PAST_IC_SHRUNK"
SECONDARY_MODEL = "V76_RIDGE_RANK"
PRIMARY_VARIANT = "GAP18_CLEAN_FROZEN_AT_V77"
PRIMARY_ALLOCATOR = "EQUAL"
ADV20_MIN_VND = 5_000_000_000.0
ZERO_VOLUME60_MAX = 5
RECENT_WINDOWS = (6, 12, 18)
RECENT_POLICIES = ("NO_OVERLAY", "L15_SWAP50_WORST", "R08_TRIM50_CASH")


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
                seen.add(str(key)); fields.append(str(key))
    fields = fields or ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _float(value: object, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _int(value: object, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _latest_market_day(market: v70.Market) -> date:
    if not market.cal:
        raise ValueError("V78_MARKET_CALENDAR_EMPTY")
    return market.cal[-1]


def _eligible_now(market: v70.Market, symbol: str, day: date) -> bool:
    pos = bisect.bisect_left(market.cal, day)
    if pos >= len(market.cal) or market.cal[pos] != day or pos < 249:
        return False
    closes = [market.sc.get((symbol, d)) for d in market.cal[pos - 249:pos + 1]]
    if any(value is None or value <= 0 for value in closes):
        return False
    close = float(closes[-1])
    if close < fmean(float(value) for value in closes):
        return False
    adv = v70.adv20(market, symbol, day)
    if adv is None or float(adv) < ADV20_MIN_VND:
        return False
    vol_days = market.cal[max(0, pos - 59):pos + 1]
    if len(vol_days) < 60:
        return False
    zero_volume = sum(int(market.vol.get((symbol, d), 0)) <= 0 for d in vol_days)
    return zero_volume <= ZERO_VOLUME60_MAX


def _volume_ratio(raw: Mapping[str, float]) -> float:
    value = float(raw.get("log_volume_ratio_5_20", 0.0))
    return math.exp(value)


def _build_preview(
    market: v70.Market,
    symbols: Sequence[str],
    capture_day: date,
    monthly_ranking: Sequence[Mapping[str, object]],
    c3_weights: Mapping[str, object],
    ridge_monthly_top10: set[str],
) -> list[dict[str, object]]:
    monthly_rank = {str(row["symbol"]): int(row["rank"]) for row in monthly_ranking}
    raw_rows: list[tuple[str, dict[str, float]]] = []
    for symbol in symbols:
        if not _eligible_now(market, symbol, capture_day):
            continue
        raw = v76._raw_features(market, symbol, capture_day)
        if raw is not None:
            raw_rows.append((symbol, raw))
    if len(raw_rows) < 10:
        raise ValueError(f"V78_TOO_FEW_CURRENT_ELIGIBLE:{len(raw_rows)}")

    names = ("low_volatility", "relative_strength_120", "high_52_week")
    pct: dict[str, dict[str, float]] = {}
    day_symbols = [symbol for symbol, _ in raw_rows]
    for name in names:
        values = [float(raw[name]) for _, raw in raw_rows]
        ranks = v76.c3.average_percentile(values)
        pct[name] = dict(zip(day_symbols, [float(x) for x in ranks]))

    weights = {name: float(c3_weights[name]) for name in names}
    scored: list[tuple[str, float, dict[str, float]]] = []
    for symbol, raw in raw_rows:
        score = sum(weights[name] * pct[name][symbol] for name in names)
        scored.append((symbol, float(score), raw))
    scored.sort(key=lambda item: (-item[1], item[0]))

    output: list[dict[str, object]] = []
    for preview_rank, (symbol, score, raw) in enumerate(scored, start=1):
        canonical_rank = monthly_rank.get(symbol, 10**9)
        output.append({
            "evaluation_day": capture_day.isoformat(),
            "symbol": symbol,
            "canonical_rank": canonical_rank,
            "preview_rank": preview_rank,
            "preview_score": score,
            "rank_delta": canonical_rank - preview_rank if canonical_rank < 10**9 else None,
            "eligible_now": True,
            "relative_5": float(raw["relative_5"]),
            "drawdown_20": float(raw["drawdown_20"]),
            "drawdown_60": float(raw["drawdown_60"]),
            "volume_ratio_5_20": _volume_ratio(raw),
            "ridge_monthly_top10": symbol in ridge_monthly_top10,
        })
    return output


def _preview_state_files(state_dir: Path) -> list[Path]:
    return sorted((Path(state_dir) / "previews").glob("*.csv"))


def _prior_week_preview(state_dir: Path, capture_day: date) -> dict[str, int]:
    candidates: list[tuple[date, Path]] = []
    current_iso = capture_day.isocalendar()[:2]
    for path in _preview_state_files(state_dir):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if day < capture_day and day.isocalendar()[:2] != current_iso:
            candidates.append((day, path))
    if not candidates:
        return {}
    _, path = max(candidates)
    return {str(row["symbol"]): _int(row.get("preview_rank")) for row in _read_csv(path)}


def _persist_preview(state_dir: Path, capture_day: date, rows: Sequence[Mapping[str, object]]) -> Path:
    directory = Path(state_dir) / "previews"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{capture_day.isoformat()}.csv"
    if path.is_file():
        old = _read_csv(path)
        old_core = [(row.get("symbol"), row.get("preview_rank"), row.get("preview_score")) for row in old]
        new_core = [(str(row.get("symbol")), str(row.get("preview_rank")), str(row.get("preview_score"))) for row in rows]
        normalized_old = [(str(a), str(b), str(c)) for a, b, c in old_core]
        if normalized_old != new_core:
            raise ValueError(f"V78_PREVIEW_STATE_DRIFT:{capture_day}")
        return path
    _write_csv(path, rows)
    return path


def classify_tactical_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    prior_preview_rank: Mapping[str, int] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    prior_preview_rank = prior_preview_rank or {}
    decorated: list[dict[str, object]] = []
    for raw in rows:
        row = dict(raw)
        symbol = str(row["symbol"])
        canonical = _int(row.get("canonical_rank"))
        preview = _int(row.get("preview_rank"))
        prior = int(prior_preview_rank.get(symbol, 10**9))
        row["prior_preview_rank"] = prior if prior < 10**9 else None
        held = canonical <= 10
        r07 = held and float(row.get("drawdown_20") or 0.0) <= -0.08
        r08 = held and float(row.get("drawdown_60") or 0.0) <= -0.12
        l15 = (
            not held
            and preview <= 5
            and prior <= 10
            and float(row.get("relative_5") or 0.0) >= 0.02
            and float(row.get("volume_ratio_5_20") or 0.0) >= 1.0
        )
        row["r07_trigger"] = r07
        row["r08_trigger"] = r08
        row["l15_trigger"] = l15
        if held and r08:
            action = "RISK_ALERT_R08"
            reason = "Top10 tháng trước đang drawdown60 <= -12%; cảnh báo, không auto-sell."
        elif held and (r07 or preview > 15 or float(row.get("relative_5") or 0.0) <= -0.02):
            action = "WATCH"
            reason = "Top10 tháng trước suy yếu intra-month; theo dõi trước khi tái phân bổ."
        elif held:
            action = "CORE_HOLD"
            reason = "Vẫn là incumbent C3; chưa có trigger giảm vị thế."
        elif l15:
            action = "L15_SWAP_IN_CANDIDATE"
            reason = "Leader mới: preview<=5, persisted<=10, relative5>=2%, volume ratio>=1."
        elif preview <= 5 and float(row.get("relative_5") or 0.0) > 0:
            action = "WATCH_EMERGING"
            reason = "Đang nổi lên trước cuối tháng nhưng chưa đủ persistence/volume cho L15."
        elif bool(row.get("ridge_monthly_top10")) and preview <= 15:
            action = "RIDGE_CONFIRMATION"
            reason = "Ridge shadow đồng thuận; chỉ dùng làm confirmation, không thay C3."
        else:
            action = "RADAR"
            reason = "Không có tactical action."
        row["action"] = action
        row["reason"] = reason
        decorated.append(row)

    leaders = [row for row in decorated if row["action"] == "L15_SWAP_IN_CANDIDATE"]
    held_rows = [row for row in decorated if _int(row.get("canonical_rank")) <= 10]
    pair: dict[str, object] = {"active": False, "leader": None, "swap_out": None, "advisory_only": True}
    if leaders and held_rows:
        leaders.sort(key=lambda row: (_int(row.get("preview_rank")), -float(row.get("preview_score") or 0.0), str(row["symbol"])))
        held_rows.sort(key=lambda row: (-_int(row.get("preview_rank")), float(row.get("preview_score") or 0.0), str(row["symbol"])))
        leader = leaders[0]
        worst = held_rows[0]
        leader["action"] = "L15_SWAP_IN_CANDIDATE"
        worst["action"] = "L15_SWAP_OUT_CANDIDATE"
        worst["reason"] = f"Nếu thực hiện L15 advisory, đây là incumbent có preview yếu nhất để đổi 50% sang {leader['symbol']}."
        pair = {
            "active": True,
            "leader": leader["symbol"],
            "swap_out": worst["symbol"],
            "fraction": 0.50,
            "advisory_only": True,
        }
    return decorated, pair


def _compound(rows: Sequence[Mapping[str, object]], field: str) -> float:
    wealth = 1.0
    for row in rows:
        value = _float(row.get(field))
        if value is None:
            continue
        wealth *= 1.0 + value
    return wealth - 1.0


def recent_window_summary(
    rows: Sequence[Mapping[str, object]],
    *,
    policy_field: str,
    baseline_id: str,
    candidate_ids: Sequence[str],
    windows: Sequence[int] = RECENT_WINDOWS,
) -> list[dict[str, object]]:
    usable = [row for row in rows if row.get("period_end_day") and _float(row.get("strategy_return")) is not None]
    if not usable:
        return []
    by_policy: dict[str, list[Mapping[str, object]]] = {}
    for row in usable:
        by_policy.setdefault(str(row.get(policy_field) or ""), []).append(row)
    for group in by_policy.values():
        group.sort(key=lambda row: str(row["period_end_day"]))
    baseline = by_policy.get(baseline_id, [])
    if not baseline:
        return []
    output: list[dict[str, object]] = []
    for window in windows:
        base_tail = baseline[-window:]
        if len(base_tail) < window:
            continue
        end_days = [str(row["period_end_day"]) for row in base_tail]
        base_return = _compound(base_tail, "strategy_return")
        benchmark_return = _compound(base_tail, "benchmark_return")
        for candidate in candidate_ids:
            candidate_map = {str(row["period_end_day"]): row for row in by_policy.get(candidate, [])}
            candidate_tail = [candidate_map[day] for day in end_days if day in candidate_map]
            if len(candidate_tail) != window:
                continue
            candidate_return = _compound(candidate_tail, "strategy_return")
            wins = sum(float(c["strategy_return"]) > float(b["strategy_return"]) for c, b in zip(candidate_tail, base_tail))
            output.append({
                "window_months": window,
                "start_day": base_tail[0]["period_start_day"],
                "end_day": base_tail[-1]["period_end_day"],
                "baseline_id": baseline_id,
                "candidate_id": candidate,
                "baseline_return": base_return,
                "candidate_return": candidate_return,
                "candidate_minus_baseline": candidate_return - base_return,
                "benchmark_return": benchmark_return,
                "candidate_month_win_rate": wins / window,
                "selection_role": "RECENT_REGIME_EVIDENCE_ONLY",
            })
    return output


def _filter_v72_recent(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    result = []
    for row in rows:
        if str(row.get("variant_id") or "") != "GAP18_CLEAN":
            continue
        if str(row.get("allocator") or "") != "EQUAL":
            continue
        if str(row.get("cost_scenario") or "") != "BASE_DNSE":
            continue
        if str(row.get("settlement_mode") or "IMMEDIATE") != "IMMEDIATE":
            continue
        policy = str(row.get("policy_id") or "")
        if policy in RECENT_POLICIES:
            result.append(row)
    return result


def _filter_v76_recent(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    result = []
    for row in rows:
        if str(row.get("variant_id") or "") != "GAP18_CLEAN":
            continue
        if str(row.get("allocator") or "") != "EQUAL":
            continue
        if str(row.get("cost_scenario") or "") != "BASE_DNSE":
            continue
        model = str(row.get("policy_id") or row.get("model_id") or row.get("ranking_policy") or "")
        if model in {"C3_STABLE_3_PAST_IC_SHRUNK", "V76_RIDGE_RANK", "C3_FROZEN", "NO_CHANGE_C3"}:
            clone = dict(row); clone["model_key"] = model; result.append(clone)
    return result


def _ridge_recent_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    ids = {str(row.get("model_key") or "") for row in rows}
    ridge = "V76_RIDGE_RANK" if "V76_RIDGE_RANK" in ids else None
    baseline = next((item for item in ("C3_STABLE_3_PAST_IC_SHRUNK", "C3_FROZEN", "NO_CHANGE_C3") if item in ids), None)
    if not ridge or not baseline:
        return []
    return recent_window_summary(rows, policy_field="model_key", baseline_id=baseline, candidate_ids=(ridge,))


def _find_latest(root: Path, name: str) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.rglob(name) if path.is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


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
    store = Path(store)
    v77_state_dir = Path(v77_state_dir)
    freeze_path = v77_state_dir / "freeze_manifest.json"
    if not store.is_file() or not freeze_path.is_file():
        raise ValueError("V78_REQUIRES_EXISTING_V77_FREEZE_AND_STORE")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    if freeze.get("champion_model") != OPERATIONAL_CHAMPION or freeze.get("shadow_model") != SECONDARY_MODEL:
        raise ValueError("V78_V77_MODEL_DEFINITION_MISMATCH")
    symbols = [str(value).upper() for value in freeze.get("variant_symbols", [])]
    if len(symbols) < 10:
        raise ValueError("V78_FROZEN_SYMBOL_SET_INVALID")

    market = v70.load_market(store, symbols)
    capture_day = _latest_market_day(market)
    rank_snapshot = v77._build_rank_snapshot(
        store=store,
        fixed_symbols=symbols,
        capture_day=capture_day,
        wall_date=capture_day,
        month_close_confirmed=False,
    )
    monthly_ranking = rank_snapshot["rankings"][OPERATIONAL_CHAMPION]
    ridge_top10 = {str(row["symbol"]) for row in rank_snapshot["rankings"][SECONDARY_MODEL][:10]}
    preview = _build_preview(
        market, symbols, capture_day, monthly_ranking,
        rank_snapshot["c3_weights"], ridge_top10,
    )
    prior = _prior_week_preview(tactical_state_dir, capture_day)
    tactical_rows, swap_pair = classify_tactical_rows(preview, prior_preview_rank=prior)
    preview_path = _persist_preview(tactical_state_dir, capture_day, preview)

    artifact_root = Path(artifact_root) if artifact_root else None
    if v72_monthly is None and artifact_root:
        v72_monthly = _find_latest(artifact_root, "v72_monthly_returns.csv")
    if v76_monthly is None and artifact_root:
        v76_monthly = _find_latest(artifact_root, "v76_monthly_returns.csv")

    v72_recent: list[dict[str, object]] = []
    if v72_monthly and Path(v72_monthly).is_file():
        rows = _filter_v72_recent(_read_csv(Path(v72_monthly)))
        v72_recent = recent_window_summary(
            rows,
            policy_field="policy_id",
            baseline_id="NO_OVERLAY",
            candidate_ids=("L15_SWAP50_WORST", "R08_TRIM50_CASH"),
        )
    v76_recent: list[dict[str, object]] = []
    if v76_monthly and Path(v76_monthly).is_file():
        v76_recent = _ridge_recent_summary(_filter_v76_recent(_read_csv(Path(v76_monthly))))

    top10 = [row for row in tactical_rows if _int(row.get("canonical_rank")) <= 10]
    top10.sort(key=lambda row: _int(row.get("canonical_rank")))
    emerging = [row for row in tactical_rows if row.get("action") in {"L15_SWAP_IN_CANDIDATE", "WATCH_EMERGING", "RIDGE_CONFIRMATION"}]
    emerging.sort(key=lambda row: _int(row.get("preview_rank")))
    health = [row for row in top10 if row.get("action") in {"WATCH", "RISK_ALERT_R08", "L15_SWAP_OUT_CANDIDATE"}]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "operational_champion": OPERATIONAL_CHAMPION,
        "operational_champion_finalized": True,
        "secondary_model": SECONDARY_MODEL,
        "secondary_role": "SHADOW_CONFIRMATION_AND_EMERGENCE_RADAR_ONLY",
        "primary_variant": PRIMARY_VARIANT,
        "primary_allocator": PRIMARY_ALLOCATOR,
        "capture_day": capture_day.isoformat(),
        "source_monthly_signal_day": rank_snapshot["source_signal_day"],
        "risk_on": bool(rank_snapshot["risk_on"]),
        "c3_weights": rank_snapshot["c3_weights"],
        "eligible_now_count": len(tactical_rows),
        "monthly_top10": [str(row["symbol"]) for row in top10],
        "current_preview_top10": [str(row["symbol"]) for row in sorted(tactical_rows, key=lambda row: _int(row.get("preview_rank")))[:10]],
        "ridge_monthly_top10": sorted(ridge_top10),
        "incumbent_health_alert_count": len(health),
        "emerging_radar_count": len(emerging),
        "l15_swap_pair": swap_pair,
        "preview_state_path": str(preview_path),
        "prior_week_preview_available": bool(prior),
        "tactical_semantics": {
            "monthly_c3_top10_remains_core": True,
            "r07_r08_are_advisory_health_alerts": True,
            "r07_r08_auto_sell": False,
            "l15_exact_trigger_required_for_swap_advice": True,
            "l15_fraction": 0.50,
            "no_live_order": True,
        },
        "recent_regime_evidence": {
            "windows_months": list(RECENT_WINDOWS),
            "v72_monthly_source": str(v72_monthly) if v72_monthly else None,
            "v72": v72_recent,
            "v76_monthly_source": str(v76_monthly) if v76_monthly else None,
            "ridge": v76_recent,
            "interpretation": "Recent windows are fixed regime evidence only; they do not replace the long-run frozen champion evidence.",
        },
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }

    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v78_tactical_rows.csv", tactical_rows)
    _write_csv(output_dir / "v78_incumbent_health.csv", health)
    _write_csv(output_dir / "v78_emerging_radar.csv", emerging)
    _write_csv(output_dir / "v78_recent_v72.csv", v72_recent)
    _write_csv(output_dir / "v78_recent_ridge.csv", v76_recent)
    (output_dir / "v78_report.json").write_text(_json_text(report), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.c3_tactical_terminal_v78")
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
