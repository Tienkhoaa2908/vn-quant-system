"""Canonical V80 forward-paper driver.

The core module stores immutable observation records and immutable tactical-row
snapshots in the same directory. This driver deliberately enumerates only real
observation records (excluding *.rows.json) so repeated workstation runs remain
idempotent while preserving the frozen-row evidence files.

Canonical execution timing is wall-clock causal: if the observation is frozen
before the Vietnam paper-open cutoff, that same market day's open is still a
future executable price. At or after the cutoff, execution moves to the next
calendar date and then to the first available market session on/after it.
Existing observations are never rewritten by this timing refinement.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Mapping, Sequence

from . import deep_portfolio_backtest_v70 as v70
from . import tactical_forward_paper_v80 as core

PAPER_OPEN_TIME_VN = time(9, 0)
SESSION_AWARE_EXECUTION_CONTRACT = "FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN"


def _observation_record_paths(state_dir: Path) -> list[Path]:
    directory = Path(state_dir) / "observations"
    return [
        path for path in sorted(directory.glob("*.json"))
        if not path.name.endswith(".rows.json")
    ]


def _execution_floor_for_wall(wall_time: datetime) -> datetime.date:
    wall = wall_time.astimezone(core.VN_TZ)
    local_clock = wall.time().replace(tzinfo=None)
    if local_clock < PAPER_OPEN_TIME_VN:
        return wall.date()
    return wall.date() + timedelta(days=1)


def _register_observation_session_aware(
    state_dir: Path,
    target: Mapping[str, object],
    wall_time: datetime,
) -> dict[str, object]:
    """Register once, refining only a brand-new record's legal execution floor.

    The legacy core registrar uses capture-date + 1 unconditionally. That is
    safely conservative after the market has opened, but it unnecessarily skips
    a still-future same-day open when the target was frozen before 09:00 VN.
    This canonical driver corrects only new observations before any fill can be
    processed. Existing persistent observations remain byte/semantic stable.
    """
    state_dir = Path(state_dir)
    observation_id = f"{target['source_monthly_signal_day']}__{target['capture_market_day']}"
    observation_path = state_dir / "observations" / f"{observation_id}.json"
    existed_before = observation_path.is_file()
    record = core.register_observation(state_dir, target, wall_time)
    if existed_before:
        return record

    wall = wall_time.astimezone(core.VN_TZ)
    record = dict(record)
    record["execution_floor_date"] = _execution_floor_for_wall(wall).isoformat()
    record["execution_floor_contract"] = SESSION_AWARE_EXECUTION_CONTRACT
    record["paper_open_time_vn"] = PAPER_OPEN_TIME_VN.isoformat()
    core._atomic_json(observation_path, record)
    return record


def run(
    *,
    store: Path,
    v78_report: Path,
    v78_tactical_rows: Path,
    state_dir: Path,
    output_dir: Path,
    wall_time: datetime | None = None,
) -> dict[str, object]:
    report = core._read_json(v78_report)
    rows = core._read_csv(v78_tactical_rows)
    target = core.build_target(report, rows)
    wall = wall_time.astimezone(core.VN_TZ) if wall_time else datetime.now(core.VN_TZ)
    current = _register_observation_session_aware(state_dir, target, wall)

    state_dir = Path(state_dir)
    records = [core._read_json(path) for path in _observation_record_paths(state_dir)]
    symbols: set[str] = set()
    for record in records:
        tgt = dict(record["target"])
        symbols.update(str(x) for x in tgt.get("monthly_top10", []))
        if tgt.get("leader"):
            symbols.add(str(tgt["leader"]))
        if tgt.get("swap_out"):
            symbols.add(str(tgt["swap_out"]))
    if not symbols:
        raise ValueError("V80_EMPTY_SYMBOL_SET")
    market = v70.load_market(Path(store), sorted(symbols))

    current_id = str(current["observation_id"])
    updated: list[dict[str, object]] = []
    for record in records:
        observation_id = str(record["observation_id"])
        observation_path = state_dir / "observations" / f"{observation_id}.rows.json"
        if observation_id == current_id and not observation_path.is_file():
            core._atomic_json(observation_path, rows)
        if not observation_path.is_file():
            raise ValueError(f"V80_FROZEN_ROWS_MISSING:{observation_id}")
        frozen_rows = json.loads(observation_path.read_text(encoding="utf-8-sig"))
        if not isinstance(frozen_rows, list):
            raise ValueError(f"V80_FROZEN_ROWS_BAD_SCHEMA:{observation_id}")
        frozen_hash = core._canonical_hash(frozen_rows)
        expected = record.get("tactical_rows_hash")
        if expected is None:
            record["tactical_rows_hash"] = frozen_hash
        elif str(expected) != frozen_hash:
            raise ValueError(f"V80_FROZEN_ROWS_DRIFT:{observation_id}")
        record = core.process_record(record, market, frozen_rows)
        core._atomic_json(state_dir / "observations" / f"{observation_id}.json", record)
        updated.append(record)

    observation_rows, action_rows, outcome_rows = core._flatten(updated)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    core._write_csv(output_dir / "v80_observations.csv", observation_rows)
    core._write_csv(output_dir / "v80_actions.csv", action_rows)
    core._write_csv(output_dir / "v80_outcomes.csv", outcome_rows)

    status_counts: dict[str, int] = {}
    for row in action_rows:
        key = str(row.get("status"))
        status_counts[key] = status_counts.get(key, 0) + 1
    result = {
        "schema_version": core.SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": core.CHAMPION_MODEL,
        "frozen_policies": list(core.FROZEN_POLICY_IDS),
        "current_observation_id": current_id,
        "current_capture_market_day": target["capture_market_day"],
        "current_capture_wall_time_vn": current["capture_wall_time_vn"],
        "current_execution_floor_date": current["execution_floor_date"],
        "current_execution_floor_contract": current.get("execution_floor_contract"),
        "paper_open_time_vn": current.get("paper_open_time_vn"),
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
    core._atomic_json(output_dir / "v80_report.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.tactical_forward_paper_v80_driver")
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
            store=args.store,
            v78_report=args.v78_report,
            v78_tactical_rows=args.v78_tactical_rows,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            wall_time=core._parse_wall_time(args.wall_time) if args.wall_time else None,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())