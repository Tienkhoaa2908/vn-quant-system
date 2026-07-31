"""Explicit handoff between market pipeline and Model Lab.

Model Lab must consume the research package produced by the latest finalized EOD
run.  It must never silently fall back to a static ``prediction_input.zip``.
"""
from __future__ import annotations

import csv
from datetime import date
from hashlib import sha256
from io import TextIOWrapper
import json
from pathlib import Path
from typing import Mapping
from zipfile import ZipFile

SCHEMA_VERSION = "vn_quant_workflow_handoff_v1"
HANDOFF_FILE = "workflow_handoff.json"


def sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def research_input_signal_date(path: Path) -> date:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"RESEARCH_INPUT_NOT_FOUND:{source}")
    latest: date | None = None
    with ZipFile(source) as archive:
        if "feature_raw.csv" not in archive.namelist():
            raise ValueError("RESEARCH_INPUT_FEATURE_RAW_MISSING")
        with archive.open("feature_raw.csv") as binary:
            reader = csv.DictReader(TextIOWrapper(binary, encoding="utf-8-sig", newline=""))
            if not reader.fieldnames or "ngay" not in reader.fieldnames:
                raise ValueError("RESEARCH_INPUT_FEATURE_DATE_COLUMN_MISSING")
            for row in reader:
                raw = str(row.get("ngay") or "").strip()[:10]
                if not raw:
                    continue
                current = date.fromisoformat(raw)
                latest = current if latest is None or current > latest else latest
    if latest is None:
        raise ValueError("RESEARCH_INPUT_FEATURE_DATES_EMPTY")
    return latest


def _successful_sibling_manifest(candidate: Path) -> bool:
    manifest = candidate.parent / "manifest.json"
    if not manifest.is_file():
        return False
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, Mapping) and payload.get("status") == "SUCCESS"


def latest_final_research_input(data_root: Path) -> Path:
    root = Path(data_root).resolve()
    candidates: list[tuple[date, float, Path]] = []
    for path in root.rglob("daily_prediction_input.zip"):
        if not path.is_file() or not _successful_sibling_manifest(path):
            continue
        try:
            signal = research_input_signal_date(path)
            modified = path.stat().st_mtime
        except (OSError, ValueError):
            continue
        candidates.append((signal, modified, path.resolve()))
    if not candidates:
        raise FileNotFoundError("FINAL_RESEARCH_INPUT_NOT_FOUND")
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2])))
    return candidates[-1][2]


def read_market_session(output_dir: Path) -> date:
    root = Path(output_dir)
    for name in ("manifest.json", "data_quality_report.json"):
        path = root / name
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        raw = payload.get("session_date") or payload.get("target_date")
        if raw:
            return date.fromisoformat(str(raw)[:10])
    raise ValueError("MARKET_OUTPUT_SESSION_NOT_FOUND")


def write_handoff(
    *,
    output_dir: Path,
    resolved_mode: str,
    research_input: Path,
    market_session: date,
    research_scope: str,
) -> Path:
    output = Path(output_dir).resolve()
    source = Path(research_input).resolve()
    signal = research_input_signal_date(source)
    if resolved_mode == "final" and signal != market_session:
        raise ValueError(
            f"FINAL_RESEARCH_INPUT_SIGNAL_MISMATCH:{signal}:{market_session}"
        )
    if resolved_mode == "snapshot" and signal > market_session:
        raise ValueError(
            f"SNAPSHOT_RESEARCH_INPUT_FROM_FUTURE:{signal}:{market_session}"
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "READY",
        "resolved_mode": resolved_mode,
        "market_session_date": market_session.isoformat(),
        "research_input_path": str(source),
        "research_input_sha256": sha256_file(source),
        "research_input_signal_date": signal.isoformat(),
        "research_scope": research_scope,
        "static_prediction_input_fallback_used": False,
        "research_ready": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    path = output / HANDOFF_FILE
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def load_handoff(output_dir: Path) -> dict[str, object]:
    path = Path(output_dir) / HANDOFF_FILE
    if not path.is_file():
        raise FileNotFoundError(f"WORKFLOW_HANDOFF_MISSING:{path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("WORKFLOW_HANDOFF_SCHEMA_INVALID")
    if payload.get("status") != "READY" or payload.get("research_ready") is not True:
        raise ValueError("WORKFLOW_HANDOFF_NOT_READY")
    source = Path(str(payload.get("research_input_path") or ""))
    if not source.is_file():
        raise FileNotFoundError(f"WORKFLOW_HANDOFF_INPUT_MISSING:{source}")
    actual_hash = sha256_file(source)
    if actual_hash != payload.get("research_input_sha256"):
        raise ValueError("WORKFLOW_HANDOFF_INPUT_HASH_MISMATCH")
    actual_signal = research_input_signal_date(source).isoformat()
    if actual_signal != payload.get("research_input_signal_date"):
        raise ValueError("WORKFLOW_HANDOFF_INPUT_SIGNAL_MISMATCH")
    return payload
