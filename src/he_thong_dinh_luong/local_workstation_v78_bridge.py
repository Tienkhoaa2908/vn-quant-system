"""Read/refresh V78 tactical research for the existing VN Quant Local Workstation.

This module is intentionally independent from the Workstation implementation. It
is imported by the already-existing local ``vn_quant_local.webapp`` only after the
V78 compatibility installer adds a narrow API bridge. No live order API is
exposed here.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from threading import Lock

_REFRESH_LOCK = Lock()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except OSError:
        return []


def _paths(system_root: Path) -> dict[str, Path]:
    system_root = Path(system_root).resolve()
    repo_root = system_root.parent
    live = system_root / "data" / "v78-c3-tactical"
    return {
        "system_root": system_root,
        "repo_root": repo_root,
        "live": live,
        "store": system_root / "data" / "market" / "dnse_ohlcv.sqlite3",
        "v77_state": repo_root / "du_lieu" / "v77-paper-oos-state",
        "v78_state": repo_root / "du_lieu" / "v78-tactical-state",
        "artifacts": repo_root / "artifacts",
    }


def read_v78_tactical_snapshot(system_root: Path) -> dict[str, object]:
    """Return the stable V78 payload without mutating state or market data."""
    p = _paths(system_root)
    report = _read_json(p["live"] / "LATEST.json")
    if not report:
        report = _read_json(p["live"] / "v78_report.json")
    if not report:
        return {
            "status": "NOT_READY",
            "message": "Chưa có snapshot V78. Bấm Cập nhật Tactical hoặc chạy runner V78.",
            "operational_champion": "C3_STABLE_3_PAST_IC_SHRUNK",
            "live_orders_allowed": False,
            "research_only": True,
            "tactical_rows": [],
            "incumbent_health": [],
            "emerging_radar": [],
            "recent_v72": [],
            "recent_ridge": [],
        }
    return {
        "status": str(report.get("status") or "SUCCESS"),
        "message": "V78 tactical snapshot đã sẵn sàng.",
        "operational_champion": report.get("operational_champion"),
        "secondary_model": report.get("secondary_model"),
        "capture_day": report.get("capture_day"),
        "source_monthly_signal_day": report.get("source_monthly_signal_day"),
        "risk_on": report.get("risk_on"),
        "report": report,
        "tactical_rows": _read_csv(p["live"] / "v78_tactical_rows.csv"),
        "incumbent_health": _read_csv(p["live"] / "v78_incumbent_health.csv"),
        "emerging_radar": _read_csv(p["live"] / "v78_emerging_radar.csv"),
        "recent_v72": _read_csv(p["live"] / "v78_recent_v72.csv"),
        "recent_ridge": _read_csv(p["live"] / "v78_recent_ridge.csv"),
        "live_orders_allowed": False,
        "research_only": True,
    }


def refresh_v78_tactical_snapshot(system_root: Path) -> dict[str, object]:
    """Recompute the current advisory snapshot using the frozen V78 driver."""
    from . import c3_tactical_terminal_v78_driver as driver

    p = _paths(system_root)
    if not p["store"].is_file():
        raise ValueError("V78_WEB_MARKET_STORE_MISSING")
    if not (p["v77_state"] / "freeze_manifest.json").is_file():
        raise ValueError("V78_WEB_V77_FREEZE_MISSING")
    p["live"].mkdir(parents=True, exist_ok=True)
    p["v78_state"].mkdir(parents=True, exist_ok=True)
    p["artifacts"].mkdir(parents=True, exist_ok=True)
    with _REFRESH_LOCK:
        report = driver.run(
            store=p["store"],
            v77_state_dir=p["v77_state"],
            tactical_state_dir=p["v78_state"],
            output_dir=p["live"],
            artifact_root=p["artifacts"],
        )
        (p["live"] / "LATEST.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return read_v78_tactical_snapshot(p["system_root"])
