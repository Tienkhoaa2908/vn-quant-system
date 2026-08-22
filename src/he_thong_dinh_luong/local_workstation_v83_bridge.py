"""Read-only V83 capital-discipline bridge for the approved workstation web.

Primary product emphasis is now capital discipline, not discovering new leaders.
The bridge classifies current C3 incumbents into NO_ADD / CUT_WATCH / RECOVERED
using already-existing V78/V79 health semantics and exposes model entry gaps.
Any V83 historical result is labelled diagnostic; this module cannot place orders.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import deep_portfolio_backtest_v70 as v70
from .local_workstation_v82_bridge import read_v82_dashboard


def _f(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value: object, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _b(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _previous_v80_rows(repo_root: Path, current_capture_day: str | None) -> dict[str, dict[str, object]]:
    obs = repo_root / "du_lieu" / "v80-tactical-paper-state" / "observations"
    candidates: list[tuple[str, Path]] = []
    if obs.is_dir():
        for path in obs.glob("*.rows.json"):
            parts = path.name.removesuffix(".rows.json").split("__")
            if len(parts) != 2:
                continue
            capture = parts[1]
            if current_capture_day and capture >= current_capture_day:
                continue
            candidates.append((capture, path))
    if not candidates:
        return {}
    path = max(candidates, key=lambda item: item[0])[1]
    try:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    return {str(row.get("symbol")): dict(row) for row in rows if isinstance(row, dict) and row.get("symbol")}


def _cut_watch(row: dict[str, object]) -> bool:
    if _i(row.get("canonical_rank")) > 10:
        return False
    persistent_rank_decay = _i(row.get("preview_rank")) > 15 and _i(row.get("prior_preview_rank")) > 10
    drag = _b(row.get("dragging_current_period")) and _f(row.get("relative_5")) <= -0.02
    severe = (
        not _b(row.get("eligible_now"))
        or _f(row.get("drawdown_20")) <= -0.08
        or _f(row.get("drawdown_60")) <= -0.12
    )
    return persistent_rank_decay and drag and severe


def _entry_gaps(system_root: Path, tactical: dict[str, object]) -> list[dict[str, object]]:
    report = tactical.get("report") if isinstance(tactical.get("report"), dict) else {}
    symbols = [str(x) for x in report.get("monthly_top10", [])]
    signal_raw = report.get("source_monthly_signal_day")
    entry_raw = report.get("period_execution_start_day")
    if not symbols or not signal_raw or not entry_raw:
        return []
    signal = date.fromisoformat(str(signal_raw)); entry = date.fromisoformat(str(entry_raw))
    store = Path(system_root) / "data" / "market" / "dnse_ohlcv.sqlite3"
    if not store.is_file():
        return []
    try:
        market = v70.load_market(store, symbols)
    except Exception:
        return []
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        close = market.sc.get((symbol, signal)); op = market.so.get((symbol, entry))
        if close is None or op is None or close <= 0 or op <= 0:
            continue
        rows.append({
            "symbol": symbol,
            "signal_day": signal.isoformat(),
            "entry_day": entry.isoformat(),
            "signal_close_vnd": float(close),
            "entry_open_vnd": float(op),
            "entry_gap": float(op) / float(close) - 1.0,
        })
    rows.sort(key=lambda row: (-abs(float(row["entry_gap"])), str(row["symbol"])))
    return rows


def read_v83_dashboard(system_root: Path) -> dict[str, object]:
    system_root = Path(system_root).resolve(); repo_root = system_root.parent
    base = read_v82_dashboard(system_root)
    tactical = base.get("tactical_v78") if isinstance(base.get("tactical_v78"), dict) else {}
    rows = [dict(row) for row in tactical.get("tactical_rows", []) if isinstance(row, dict)]
    capture_day = str(tactical.get("capture_day") or "") or None
    prior = _previous_v80_rows(repo_root, capture_day)

    no_add: list[dict[str, object]] = []
    cut_watch: list[dict[str, object]] = []
    recovered: list[dict[str, object]] = []
    for row in rows:
        if _i(row.get("canonical_rank")) > 10:
            continue
        symbol = str(row.get("symbol") or "")
        dragging = _b(row.get("dragging_current_period"))
        health_alert = _b(row.get("r07_trigger")) or _b(row.get("r08_trigger"))
        payload = {
            "symbol": symbol,
            "monthly_rank": _i(row.get("canonical_rank"), 0),
            "current_rank": _i(row.get("preview_rank"), 0),
            "period_return": _f(row.get("period_return")),
            "period_relative_return": _f(row.get("period_relative_return")),
            "relative_5": _f(row.get("relative_5")),
            "drawdown_20": _f(row.get("drawdown_20")),
            "drawdown_60": _f(row.get("drawdown_60")),
            "action": row.get("action"),
        }
        if dragging or health_alert:
            no_add.append({**payload, "reason": "CURRENT_DRAG" if dragging else "HEALTH_ALERT"})
        if _cut_watch(row):
            cut_watch.append({**payload, "reason": "PERSISTENT_SEVERE_DRAG"})
        old = prior.get(symbol)
        if old and _b(old.get("dragging_current_period")) and not dragging:
            recovered.append({**payload, "reason": "RECOVERED_FROM_PRIOR_DRAG"})

    no_add.sort(key=lambda x: (x["period_relative_return"], x["period_return"], x["symbol"]))
    cut_watch.sort(key=lambda x: (x["period_relative_return"], x["symbol"]))
    recovered.sort(key=lambda x: (-x["period_relative_return"], x["symbol"]))
    research = _read_json(system_root / "data" / "v83-capital-discipline" / "LATEST.json")
    return {
        "schema_version": "local_workstation_v83_capital_discipline",
        "status": "SUCCESS",
        "operational_champion": "C3_STABLE_3_PAST_IC_SHRUNK",
        "primary_product_focus": "CAPITAL_DISCIPLINE",
        "no_add_now": no_add,
        "cut_watch_now": cut_watch,
        "recovered_now": recovered,
        "entry_gap_current_cycle": _entry_gaps(system_root, tactical),
        "historical_v83": research,
        "research_policy": {
            "new_leader_research_reopened": False,
            "no_add_rule": "BLOCK_INCREMENTAL_ADD_WHEN_ABSOLUTE_AND_RELATIVE_CYCLE_RETURN_ARE_BOTH_NEGATIVE",
            "cut_rule": "PERSIST2_OF_EXISTING_V79_SEVERE_DRAG_THEN_TRIM50_RESEARCH_ONLY",
            "entry_audit": "COMPARE_T1_OPEN_VS_T2_OPEN_VS_50_50_STAGED_FOR_NEW_MONTHLY_NAMES",
        },
        "archived_evidence": {
            "v80": base.get("paper_v80", {}),
            "v81": base.get("historical_profit_v81", {}),
        },
        "historical_threshold_search_reopened": False,
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }
