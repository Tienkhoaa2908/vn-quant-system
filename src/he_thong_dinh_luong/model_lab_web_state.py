"""Shared read-only state helpers for integrated Model Lab screens."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, UnicodeError, csv.Error):
        return []


def latest_model_lab_run(data_root: Path) -> Path | None:
    root = Path(data_root) / "model-lab-live"
    pointer = root / "LATEST.txt"
    if pointer.is_file():
        try:
            pointed = Path(pointer.read_text(encoding="utf-8-sig").strip())
        except OSError:
            pointed = Path()
        if pointed.is_dir():
            return pointed
    runs = root / "runs"
    candidates = [path for path in runs.glob("*") if path.is_dir()] if runs.is_dir() else []
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def resolve_artifacts(run_dir: Path, status: Mapping[str, object]) -> Path | None:
    raw = status.get("artifacts_dir")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.is_dir():
            return path
    local = Path(run_dir) / "artifacts"
    return local if local.is_dir() else None


def load_model_lab_state(data_root: Path) -> dict[str, object]:
    run = latest_model_lab_run(data_root)
    if run is None:
        return {
            "available": False,
            "status": "NOT_RUN",
            "phase": "IDLE",
            "progress": 0.0,
            "message": "Chưa chạy Model Lab.",
            "run_dir": "",
            "artifacts_dir": "",
            "summary": {},
            "leaderboard": [],
            "nav": [],
        }
    status = _json(run / "run_status.json")
    artifacts = resolve_artifacts(run, status)
    summary = _json(artifacts / "model_lab_summary.json") if artifacts else {}
    leaderboard = _csv(artifacts / "model_leaderboard.csv") if artifacts else []
    nav = _csv(artifacts / "oos_nav.csv") if artifacts else []
    return {
        "available": True,
        "status": status.get("status", "UNKNOWN"),
        "phase": status.get("phase", "UNKNOWN"),
        "progress": float(status.get("progress") or 0.0),
        "message": status.get("message", ""),
        "updated_at": status.get("updated_at", ""),
        "error": status.get("error"),
        "run_dir": str(run.resolve()),
        "artifacts_dir": str(artifacts.resolve()) if artifacts else "",
        "summary": summary,
        "leaderboard": leaderboard,
        "nav": nav,
    }


def compact_leaderboard(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        def number(name: str) -> float | str:
            raw = row.get(name, "")
            if raw == "":
                return ""
            try:
                return round(float(raw), 4)
            except (TypeError, ValueError):
                return raw
        result.append({
            "model": row.get("model", ""),
            "family": row.get("family", ""),
            "status": row.get("status", ""),
            "rank_ic": number("mean_rank_ic"),
            "ic_positive": number("positive_rank_ic_ratio"),
            "excess": number("relative_total_return"),
            "sharpe": number("sharpe"),
            "drawdown": number("max_drawdown"),
            "turnover": number("mean_set_turnover"),
            "gate": row.get("gate_passed", "false"),
            "error": row.get("error", ""),
        })
    return result


def model_lab_grade(state: Mapping[str, object]) -> tuple[str, str]:
    summary = state.get("summary") if isinstance(state.get("summary"), Mapping) else {}
    grade = str(summary.get("evidence_grade") or "")
    champion = str(summary.get("research_champion") or "")
    if grade:
        return grade, champion or "NO_MODEL_APPROVED"
    status = str(state.get("status") or "NOT_RUN")
    if status == "RUNNING":
        return "ĐANG KIỂM ĐỊNH", str(state.get("phase") or "")
    if status == "FAILED":
        return "MODEL LAB LỖI", str(state.get("error") or "")
    return "CHƯA KIỂM ĐỊNH", "Chạy cập nhật toàn bộ để đánh giá model."
