"""Read-only V82 dashboard bridge for the approved VN Quant Local Workstation.

V82 combines three already-existing evidence surfaces without mutating them:
- V78 current tactical snapshot;
- V80 persistent forward-paper registry;
- audited V81 post-selection profit snapshot.

No broker/order endpoint is exposed and no research threshold is changed here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .local_workstation_v78_bridge import read_v78_tactical_snapshot


def _read_json(path: Path) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _paths(system_root: Path) -> dict[str, Path]:
    system_root = Path(system_root).resolve()
    repo_root = system_root.parent
    return {
        "system_root": system_root,
        "repo_root": repo_root,
        "v80_state": repo_root / "du_lieu" / "v80-tactical-paper-state",
        "v81_profit": repo_root / "tai_lieu_dieu_phoi" / "v81_profit_snapshot_20260818.json",
    }


def _v80_summary(state_dir: Path) -> dict[str, object]:
    observation_dir = Path(state_dir) / "observations"
    records: list[Mapping[str, object]] = []
    if observation_dir.is_dir():
        for path in sorted(observation_dir.glob("*.json")):
            if path.name.endswith(".rows.json"):
                continue
            value = _read_json(path)
            if isinstance(value, dict) and value.get("observation_id"):
                records.append(value)

    actions: list[Mapping[str, object]] = []
    outcomes: list[Mapping[str, object]] = []
    for record in records:
        for item in record.get("actions", []) if isinstance(record.get("actions"), list) else []:
            if isinstance(item, dict):
                actions.append(item)
        for item in record.get("outcomes", []) if isinstance(record.get("outcomes"), list) else []:
            if isinstance(item, dict):
                outcomes.append(item)

    status_counts: dict[str, int] = {}
    for item in actions:
        key = str(item.get("status") or "UNKNOWN")
        status_counts[key] = status_counts.get(key, 0) + 1

    latest = records[-1] if records else {}
    target = latest.get("target") if isinstance(latest.get("target"), dict) else {}
    return {
        "status": "READY" if records else "NOT_READY",
        "observation_count": len(records),
        "action_count": len(actions),
        "outcome_count": len(outcomes),
        "action_status_counts": status_counts,
        "latest_observation_id": latest.get("observation_id"),
        "latest_capture_wall_time_vn": latest.get("capture_wall_time_vn"),
        "latest_execution_floor_date": latest.get("execution_floor_date"),
        "latest_execution_floor_contract": latest.get("execution_floor_contract"),
        "latest_exact_l15_active": target.get("exact_l15_active"),
        "latest_leader": target.get("leader"),
        "latest_swap_out": target.get("swap_out"),
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }


def read_v82_dashboard(system_root: Path) -> dict[str, object]:
    p = _paths(system_root)
    tactical = read_v78_tactical_snapshot(p["system_root"])
    profit = _read_json(p["v81_profit"])
    if not isinstance(profit, dict):
        profit = {}
    paper = _v80_summary(p["v80_state"])
    return {
        "schema_version": "local_workstation_v82_dashboard",
        "status": "SUCCESS",
        "operational_champion": "C3_STABLE_3_PAST_IC_SHRUNK",
        "primary_tactical_paper_challenger": "L15_SWAP50_WORST",
        "tactical_v78": tactical,
        "paper_v80": paper,
        "historical_profit_v81": profit,
        "evidence_labels": {
            "v78": "CURRENT_TACTICAL_ADVISORY",
            "v80": "FRESH_FORWARD_PAPER",
            "v81": "POST_SELECTION_HISTORICAL_DIAGNOSTIC",
        },
        "historical_threshold_search_reopened": False,
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }
