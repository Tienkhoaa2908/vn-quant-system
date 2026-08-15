"""V80 fresh forward-paper registry for frozen C3 tactical opportunity actions.

No historical search occurs here. Exact-L15 is inherited from V72/V78/V79.
Each observed tactical event is frozen after the workstation capture wall time and
can execute only at the first market session on/after Vietnam capture date + 1.
The three frozen challengers are evaluated as independent current-cycle 1bn VND
counterfactual portfolios against the same C3 Equal baseline.
"""
from __future__ import annotations

import argparse
import bisect
import copy
import csv
import hashlib
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from . import c3_tactical_terminal_v78 as v78
from . import deep_portfolio_backtest_v70 as v70
from . import tactical_capital_policy_v79 as v79
from . import weekly_overlay_backtest_v72 as v72

SCHEMA_VERSION = "tactical_forward_paper_v80"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
INITIAL_PAPER_NAV_VND = 1_000_000_000.0
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FROZEN_POLICY_IDS = (
    "L15_SWAP25_WORST",
    "L15_SWAP50_WORST",
    "L15_CASH_ADD25_SLOT",
)
HORIZONS = (5, 10, 20)
BASE_STRATEGY = v70.Strategy("V80_C3_EQ_ALWAYS", "EQUAL", 1.0, "IMMEDIATE")
BASE_COST = next(cost for cost in v70.COSTS if cost.name == "BASE_DNSE")


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(_json_text(value), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


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
            writer.writerow({field: row.get(field, "") for field in fields})


def _i(value: object, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _f(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _b(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _parse_wall_time(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(VN_TZ)
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TZ)
    return parsed.astimezone(VN_TZ)


def _state_to_json(state: v70.State) -> dict[str, object]:
    return {
        "cash": float(state.cash),
        "shares": {str(k): int(v) for k, v in state.shares.items()},
        "pending": [[d.isoformat(), float(v)] for d, v in state.pending],
        "mark": {str(k): float(v) for k, v in state.mark.items()},
        "desired": {str(k): int(v) for k, v in state.desired.items()},
    }


def _state_from_json(raw: Mapping[str, object]) -> v70.State:
    return v70.State(
        cash=float(raw.get("cash", 0.0)),
        shares={str(k): int(v) for k, v in dict(raw.get("shares", {})).items()},
        pending=[(date.fromisoformat(str(d)), float(v)) for d, v in raw.get("pending", [])],
        mark={str(k): float(v) for k, v in dict(raw.get("mark", {})).items()},
        desired={str(k): int(v) for k, v in dict(raw.get("desired", {})).items()},
    )


def build_target(report: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if report.get("status") != "SUCCESS":
        raise ValueError("V80_REQUIRES_SUCCESSFUL_V78_REPORT")
    if report.get("operational_champion") != CHAMPION_MODEL or report.get("live_orders_allowed") is not False:
        raise ValueError("V80_V78_FROZEN_ARCHITECTURE_MISMATCH")
    tactical = report.get("tactical_semantics") or {}
    if not _b(dict(tactical).get("l15_exact_trigger_required_for_swap_advice")):
        raise ValueError("V80_EXACT_L15_CONTRACT_MISSING")

    normalized = [dict(row) for row in rows]
    held = [row for row in normalized if _i(row.get("canonical_rank")) <= 10]
    leaders = [row for row in normalized if v79._l15(row)]
    held.sort(key=lambda row: (-_i(row.get("preview_rank")), _f(row.get("preview_score")), str(row.get("symbol"))))
    leaders.sort(key=lambda row: (_i(row.get("preview_rank")), -_f(row.get("preview_score"), -1e99), str(row.get("symbol"))))

    leader = str(leaders[0]["symbol"]) if leaders else None
    incumbent = str(held[0]["symbol"]) if leaders and held else None
    active = bool(leader and incumbent)
    pair = dict(report.get("l15_swap_pair") or {})
    if bool(pair.get("active")) != active:
        raise ValueError("V80_V78_L15_ACTIVE_MISMATCH")
    if active and (str(pair.get("leader")) != leader or str(pair.get("swap_out")) != incumbent):
        raise ValueError("V80_V78_L15_PAIR_MISMATCH")

    monthly_top10 = [str(value).upper() for value in report.get("monthly_top10", [])]
    if len(monthly_top10) != 10 or len(set(monthly_top10)) != 10:
        raise ValueError("V80_MONTHLY_TOP10_INVALID")
    source_signal_day = date.fromisoformat(str(report["source_monthly_signal_day"]))
    capture_day = date.fromisoformat(str(report["capture_day"]))
    target = {
        "schema_version": SCHEMA_VERSION,
        "champion_model": CHAMPION_MODEL,
        "source_monthly_signal_day": source_signal_day.isoformat(),
        "capture_market_day": capture_day.isoformat(),
        "risk_on": bool(report.get("risk_on")),
        "monthly_top10": monthly_top10,
        "exact_l15_active": active,
        "leader": leader,
        "swap_out": incumbent,
        "leader_evidence": None,
        "incumbent_evidence": None,
        "frozen_policies": list(FROZEN_POLICY_IDS),
        "incumbent_health_can_trigger_trade": False,
        "live_orders_allowed": False,
    }
    if active:
        leader_row = next(row for row in leaders if str(row["symbol"]) == leader)
        incumbent_row = next(row for row in held if str(row["symbol"]) == incumbent)
        target["leader_evidence"] = {
            key: leader_row.get(key) for key in (
                "canonical_rank", "preview_rank", "prior_preview_rank", "relative_5",
                "volume_ratio_5_20", "eligible_now", "l15_trigger",
            )
        }
        target["incumbent_evidence"] = {
            key: incumbent_row.get(key) for key in (
                "canonical_rank", "preview_rank", "preview_score", "relative_5",
                "drawdown_20", "drawdown_60", "dragging_current_period", "action",
            )
        }
    return target


def _action_templates(target: Mapping[str, object]) -> list[dict[str, object]]:
    active = bool(target.get("exact_l15_active"))
    leader = target.get("leader")
    incumbent = target.get("swap_out")
    common = {
        "leader": leader,
        "incumbent": incumbent,
        "source_monthly_signal_day": target["source_monthly_signal_day"],
        "capture_market_day": target["capture_market_day"],
        "counterfactual_basis": "CURRENT_CYCLE_NORMALIZED_1B_C3_EQUAL_BASE_DNSE",
        "automatic_live_order": False,
    }
    if not active:
        return [
            {"policy_id": policy_id, "status": "NO_ACTION_NO_EXACT_L15", **common}
            for policy_id in FROZEN_POLICY_IDS
        ]
    return [
        {"policy_id": "L15_SWAP25_WORST", "status": "PENDING_FIRST_EXECUTION", "fraction": 0.25, **common},
        {"policy_id": "L15_SWAP50_WORST", "status": "PENDING_FIRST_EXECUTION", "fraction": 0.50, **common},
        {"policy_id": "L15_CASH_ADD25_SLOT",
         "status": "PENDING_FIRST_EXECUTION" if bool(target.get("risk_on")) else "INELIGIBLE_RISK_OFF",
         "slot_fraction": 0.25, **common},
    ]


def register_observation(state_dir: Path, target: Mapping[str, object], wall_time: datetime) -> dict[str, object]:
    state_dir = Path(state_dir)
    observations = state_dir / "observations"
    observations.mkdir(parents=True, exist_ok=True)
    target_hash = _canonical_hash(target)
    observation_id = f"{target['source_monthly_signal_day']}__{target['capture_market_day']}"
    path = observations / f"{observation_id}.json"
    if path.is_file():
        existing = _read_json(path)
        if existing.get("target_hash") != target_hash:
            raise ValueError(f"V80_TARGET_DRIFT:{observation_id}")
        return existing

    wall_time = wall_time.astimezone(VN_TZ)
    record = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": observation_id,
        "target_hash": target_hash,
        "target": dict(target),
        "capture_wall_time_vn": wall_time.isoformat(),
        "capture_vn_date": wall_time.date().isoformat(),
        "execution_floor_date": (wall_time.date() + timedelta(days=1)).isoformat(),
        "execution_floor_contract": "FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1",
        "actions": _action_templates(target),
    }
    _atomic_json(path, record)

    registry_path = state_dir / "registry.json"
    if registry_path.is_file():
        registry = _read_json(registry_path)
        if tuple(registry.get("frozen_policies", [])) != FROZEN_POLICY_IDS:
            raise ValueError("V80_REGISTRY_POLICY_DRIFT")
    else:
        registry = {
            "schema_version": SCHEMA_VERSION,
            "champion_model": CHAMPION_MODEL,
            "frozen_policies": list(FROZEN_POLICY_IDS),
            "initial_paper_nav_vnd": INITIAL_PAPER_NAV_VND,
            "created_wall_time_vn": wall_time.isoformat(),
            "no_historical_selection": True,
            "live_orders_allowed": False,
            "observation_ids": [],
        }
    ids = list(registry.get("observation_ids", []))
    if observation_id not in ids:
        ids.append(observation_id)
    registry["observation_ids"] = sorted(ids)
    _atomic_json(registry_path, registry)
    return record


def _first_session_on_or_after(cal: Sequence[date], floor: date) -> date | None:
    pos = bisect.bisect_left(cal, floor)
    return cal[pos] if pos < len(cal) else None


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _monthly_boundary_execution(cal: Sequence[date], source_signal_day: date) -> date | None:
    target_y, target_m = _next_month(source_signal_day.year, source_signal_day.month)
    after_y, after_m = _next_month(target_y, target_m)
    target_days = [d for d in cal if (d.year, d.month) == (target_y, target_m)]
    later_days = [d for d in cal if (d.year, d.month) >= (after_y, after_m)]
    if not target_days or not later_days:
        return None
    signal_day = max(target_days)
    return v70._next(list(cal), signal_day)


def _baseline_state_at_fill(
    market: v70.Market,
    target: Mapping[str, object],
    fill_day: date,
) -> tuple[v70.State, list[dict[str, object]], list[dict[str, object]]]:
    source = date.fromisoformat(str(target["source_monthly_signal_day"]))
    entry_day = v70._next(market.cal, source)
    if entry_day is None or entry_day > fill_day:
        raise ValueError("V80_MONTHLY_BASELINE_ENTRY_UNAVAILABLE")
    snap = v70.Snap(source, tuple(str(x) for x in target["monthly_top10"]), bool(target.get("risk_on")))
    state = v70.State(cash=INITIAL_PAPER_NAV_VND, shares={}, pending=[], mark={}, desired={})
    ledger: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    v70._rebalance(state, market, snap, BASE_STRATEGY, BASE_COST, entry_day, ledger, missing)
    v70._value(state, market, fill_day, True, missing)
    return state, ledger, missing


def _signal_from_record(record: Mapping[str, object], tactical_rows: Sequence[Mapping[str, object]]) -> v72.WeeklySignal:
    target = dict(record["target"])
    rows = {str(row["symbol"]): dict(row) for row in tactical_rows}
    return v72.WeeklySignal(
        evaluation_day=date.fromisoformat(str(target["capture_market_day"])),
        canonical_day=date.fromisoformat(str(target["source_monthly_signal_day"])),
        rows=rows,
    )


def _validate_fill_against_market(action: Mapping[str, object], market: v70.Market) -> None:
    fill = action.get("fill")
    if not isinstance(fill, Mapping):
        return
    day = date.fromisoformat(str(fill["trade_day"]))
    for symbol_key, raw_key in (("incumbent", "incumbent_raw_open_vnd"), ("leader", "leader_raw_open_vnd")):
        symbol = action.get(symbol_key)
        if not symbol or fill.get(raw_key) is None:
            continue
        now = market.so.get((str(symbol), day))
        if now is None or abs(float(now) - float(fill[raw_key])) > 1e-8:
            raise ValueError(f"V80_FILL_MARKET_DRIFT:{action['policy_id']}:{symbol}:{day}")


def _fill_action(
    action: dict[str, object], record: Mapping[str, object], market: v70.Market,
    tactical_rows: Sequence[Mapping[str, object]], fill_day: date,
) -> None:
    target = dict(record["target"])
    baseline, baseline_ledger, baseline_missing = _baseline_state_at_fill(market, target, fill_day)
    challenger = copy.deepcopy(baseline)
    signal = _signal_from_record(record, tactical_rows)
    policy_id = str(action["policy_id"])
    ledger: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    incumbent = str(action.get("incumbent") or "")
    leader = str(action.get("leader") or "")
    inc_open = market.so.get((incumbent, fill_day)) if incumbent else None
    leader_open = market.so.get((leader, fill_day)) if leader else None
    if leader_open is None or (policy_id.startswith("L15_SWAP") and inc_open is None):
        action["status"] = "FAILED_MISSING_EXECUTION_OPEN"
        action["failed_trade_day"] = fill_day.isoformat()
        return

    if policy_id in {"L15_SWAP25_WORST", "L15_SWAP50_WORST"}:
        fraction = float(action["fraction"])
        policy = v79.CapitalPolicy(policy_id, "V80_FROZEN_FORWARD", leader_mode="SWAP_WORST", leader_fraction=fraction)
        before_inc = challenger.shares.get(incumbent, 0)
        before_leader = challenger.shares.get(leader, 0)
        bi, ai, bl, al = v79._rotate(
            challenger, market, signal, policy, incumbent, leader, fraction, fill_day,
            BASE_COST, "IMMEDIATE", ledger, missing,
        )
        if ai == bi or al == bl:
            action["status"] = "NO_CAPACITY_AT_EXECUTION"
            action["failed_trade_day"] = fill_day.isoformat()
            return
        action["executed_incumbent_fraction_of_position"] = (bi - ai) / bi if bi else 0.0
        action["incumbent_shares_before"] = before_inc
        action["incumbent_shares_after"] = ai
        action["leader_shares_before"] = before_leader
        action["leader_shares_after"] = al
    elif policy_id == "L15_CASH_ADD25_SLOT":
        if not bool(target.get("risk_on")):
            action["status"] = "INELIGIBLE_RISK_OFF"
            return
        policy = v79._POLICY_BY_ID[policy_id]
        idle_cash_before = challenger.cash
        before_leader = challenger.shares.get(leader, 0)
        bl, al = v79._buy_cash(
            challenger, market, signal, policy, leader, float(action["slot_fraction"]), fill_day,
            BASE_COST, "IMMEDIATE", ledger, missing,
        )
        if al == bl:
            action["status"] = "NO_IDLE_CASH_CAPACITY_AT_EXECUTION"
            action["failed_trade_day"] = fill_day.isoformat()
            action["idle_cash_before_vnd"] = idle_cash_before
            return
        action["idle_cash_before_vnd"] = idle_cash_before
        action["leader_shares_before"] = before_leader
        action["leader_shares_after"] = al
    else:
        raise ValueError(f"V80_UNKNOWN_POLICY:{policy_id}")

    action["status"] = "FILLED_PAPER"
    action["fill"] = {
        "trade_day": fill_day.isoformat(),
        "execution_contract": "CAPTURE_AFTER_CLOSE_TO_FIRST_LEGAL_NEXT_SESSION_OPEN",
        "incumbent_raw_open_vnd": float(inc_open) if inc_open is not None else None,
        "leader_raw_open_vnd": float(leader_open) if leader_open is not None else None,
        "baseline_state": _state_to_json(baseline),
        "challenger_state": _state_to_json(challenger),
        "baseline_monthly_entry_ledger": baseline_ledger,
        "tactical_trade_ledger": ledger,
        "missing_price_events": baseline_missing + missing,
        "cost_scenario": BASE_COST.name,
        "initial_paper_nav_vnd": INITIAL_PAPER_NAV_VND,
        "live_order": False,
    }
    action.setdefault("outcomes", {})


def _portfolio_value(state_raw: Mapping[str, object], market: v70.Market, day: date, *, open_: bool) -> float:
    state = _state_from_json(state_raw)
    missing: list[dict[str, object]] = []
    return float(v70._value(state, market, day, open_, missing))


def _outcome_payload(action: Mapping[str, object], market: v70.Market, day: date, label: str, *, open_: bool) -> dict[str, object]:
    fill = dict(action["fill"])
    baseline = _portfolio_value(fill["baseline_state"], market, day, open_=open_)
    challenger = _portfolio_value(fill["challenger_state"], market, day, open_=open_)
    delta = challenger - baseline
    return {
        "label": label,
        "evaluation_day": day.isoformat(),
        "price_point": "OPEN" if open_ else "CLOSE",
        "baseline_nav_vnd": baseline,
        "challenger_nav_vnd": challenger,
        "incremental_pnl_vnd": delta,
        "incremental_return_on_initial_nav": delta / INITIAL_PAPER_NAV_VND,
    }


def _merge_outcome(action: dict[str, object], key: str, payload: Mapping[str, object]) -> None:
    outcomes = dict(action.get("outcomes") or {})
    existing = outcomes.get(key)
    if existing is not None and _canonical_hash(existing) != _canonical_hash(payload):
        raise ValueError(f"V80_OUTCOME_DRIFT:{action['policy_id']}:{key}")
    outcomes[key] = dict(payload)
    action["outcomes"] = outcomes


def process_record(
    record: dict[str, object], market: v70.Market, tactical_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    target = dict(record["target"])
    floor = date.fromisoformat(str(record["execution_floor_date"]))
    source = date.fromisoformat(str(target["source_monthly_signal_day"]))
    boundary = _monthly_boundary_execution(market.cal, source)
    legal_day = _first_session_on_or_after(market.cal, floor)

    actions = [dict(action) for action in record.get("actions", [])]
    for action in actions:
        _validate_fill_against_market(action, market)
        status = str(action.get("status"))
        if status == "PENDING_FIRST_EXECUTION" and legal_day is not None:
            if boundary is not None and legal_day >= boundary:
                action["status"] = "CANCELLED_MONTHLY_REBALANCE_PRECEDENCE"
                action["monthly_boundary_trade_day"] = boundary.isoformat()
            else:
                _fill_action(action, record, market, tactical_rows, legal_day)

        if action.get("status") != "FILLED_PAPER":
            continue
        fill_day = date.fromisoformat(str(dict(action["fill"])["trade_day"]))
        pos = bisect.bisect_left(market.cal, fill_day)
        for horizon in HORIZONS:
            out_pos = pos + horizon
            if out_pos >= len(market.cal):
                continue
            out_day = market.cal[out_pos]
            if boundary is not None and out_day >= boundary:
                censored = {
                    "label": f"H{horizon}",
                    "censored_by_monthly_rebalance": True,
                    "monthly_boundary_trade_day": boundary.isoformat(),
                }
                _merge_outcome(action, f"H{horizon}", censored)
                continue
            _merge_outcome(action, f"H{horizon}", _outcome_payload(action, market, out_day, f"H{horizon}", open_=False))
        if boundary is not None and boundary in market.cal:
            _merge_outcome(action, "MONTHLY_REBALANCE", _outcome_payload(action, market, boundary, "MONTHLY_REBALANCE", open_=True))
            action["status"] = "CLOSED_AT_MONTHLY_REBALANCE"
            action["monthly_boundary_trade_day"] = boundary.isoformat()

    record["actions"] = actions
    return record


def _flatten(records: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    observations: list[dict[str, object]] = []
    actions: list[dict[str, object]] = []
    outcomes: list[dict[str, object]] = []
    for record in records:
        target = dict(record["target"])
        observations.append({
            "observation_id": record["observation_id"],
            "capture_wall_time_vn": record["capture_wall_time_vn"],
            "execution_floor_date": record["execution_floor_date"],
            "source_monthly_signal_day": target["source_monthly_signal_day"],
            "capture_market_day": target["capture_market_day"],
            "risk_on": target["risk_on"],
            "exact_l15_active": target["exact_l15_active"],
            "leader": target.get("leader"),
            "swap_out": target.get("swap_out"),
            "target_hash": record["target_hash"],
        })
        for action in record.get("actions", []):
            fill = dict(action.get("fill") or {})
            actions.append({
                "observation_id": record["observation_id"],
                "policy_id": action.get("policy_id"),
                "status": action.get("status"),
                "leader": action.get("leader"),
                "incumbent": action.get("incumbent"),
                "fraction": action.get("fraction"),
                "slot_fraction": action.get("slot_fraction"),
                "trade_day": fill.get("trade_day"),
                "idle_cash_before_vnd": action.get("idle_cash_before_vnd"),
                "executed_incumbent_fraction_of_position": action.get("executed_incumbent_fraction_of_position"),
                "live_order": False,
            })
            for key, outcome in dict(action.get("outcomes") or {}).items():
                outcomes.append({
                    "observation_id": record["observation_id"],
                    "policy_id": action.get("policy_id"),
                    "outcome_key": key,
                    **dict(outcome),
                })
    return observations, actions, outcomes


def run(
    *, store: Path, v78_report: Path, v78_tactical_rows: Path, state_dir: Path,
    output_dir: Path, wall_time: datetime | None = None,
) -> dict[str, object]:
    report = _read_json(v78_report)
    rows = _read_csv(v78_tactical_rows)
    target = build_target(report, rows)
    wall = wall_time.astimezone(VN_TZ) if wall_time else datetime.now(VN_TZ)
    current = register_observation(state_dir, target, wall)

    state_dir = Path(state_dir)
    records = [_read_json(path) for path in sorted((state_dir / "observations").glob("*.json"))]
    symbols: set[str] = set()
    for record in records:
        tgt = dict(record["target"])
        symbols.update(str(x) for x in tgt.get("monthly_top10", []))
        if tgt.get("leader"): symbols.add(str(tgt["leader"]))
        if tgt.get("swap_out"): symbols.add(str(tgt["swap_out"]))
    if not symbols:
        raise ValueError("V80_EMPTY_SYMBOL_SET")
    market = v70.load_market(Path(store), sorted(symbols))

    current_rows = rows
    updated: list[dict[str, object]] = []
    current_id = str(current["observation_id"])
    for record in records:
        observation_path = state_dir / "observations" / f"{record['observation_id']}.rows.json"
        if str(record["observation_id"]) == current_id and not observation_path.is_file():
            _atomic_json(observation_path, current_rows)
        if not observation_path.is_file():
            raise ValueError(f"V80_FROZEN_ROWS_MISSING:{record['observation_id']}")
        frozen_rows = json.loads(observation_path.read_text(encoding="utf-8-sig"))
        frozen_hash = _canonical_hash(frozen_rows)
        expected = record.get("tactical_rows_hash")
        if expected is None:
            record["tactical_rows_hash"] = frozen_hash
        elif str(expected) != frozen_hash:
            raise ValueError(f"V80_FROZEN_ROWS_DRIFT:{record['observation_id']}")
        record = process_record(record, market, frozen_rows)
        _atomic_json(state_dir / "observations" / f"{record['observation_id']}.json", record)
        updated.append(record)

    observation_rows, action_rows, outcome_rows = _flatten(updated)
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v80_observations.csv", observation_rows)
    _write_csv(output_dir / "v80_actions.csv", action_rows)
    _write_csv(output_dir / "v80_outcomes.csv", outcome_rows)
    status_counts: dict[str, int] = {}
    for row in action_rows:
        key = str(row.get("status"))
        status_counts[key] = status_counts.get(key, 0) + 1
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "frozen_policies": list(FROZEN_POLICY_IDS),
        "current_observation_id": current_id,
        "current_capture_market_day": target["capture_market_day"],
        "current_capture_wall_time_vn": current["capture_wall_time_vn"],
        "current_execution_floor_date": current["execution_floor_date"],
        "current_exact_l15_active": target["exact_l15_active"],
        "current_leader": target.get("leader"),
        "current_swap_out": target.get("swap_out"),
        "observation_count": len(observation_rows),
        "action_count": len(action_rows),
        "outcome_count": len(outcome_rows),
        "action_status_counts": status_counts,
        "counterfactual_basis": "CURRENT_CYCLE_NORMALIZED_1B_C3_EQUAL_BASE_DNSE",
        "historical_threshold_search_reopened": False,
        "incumbent_health_auto_sell": False,
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }
    _atomic_json(output_dir / "v80_report.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.tactical_forward_paper_v80")
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--v78-report", type=Path, required=True)
    parser.add_argument("--v78-tactical-rows", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--wall-time")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            store=args.store, v78_report=args.v78_report, v78_tactical_rows=args.v78_tactical_rows,
            state_dir=args.state_dir, output_dir=args.output_dir,
            wall_time=_parse_wall_time(args.wall_time) if args.wall_time else None,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
