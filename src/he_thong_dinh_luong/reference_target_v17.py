"""Load the latest verified frozen-reference target for contribution planning."""
from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from typing import Mapping
from zipfile import BadZipFile, ZipFile

SIGNAL_SCHEMA = "model_lab_reference_signal_v16"
SIGNAL_FILE = "paper_portfolio.csv"
MANIFEST_FILE = "manifest.json"


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _rows(payload: bytes) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    ]


def load_reference_target(path: Path) -> dict[str, object]:
    source = Path(path)
    if not source.is_file():
        raise ValueError("REFERENCE_TARGET_SIGNAL_NOT_FOUND")
    try:
        with ZipFile(source) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"REFERENCE_TARGET_CRC_ERROR:{bad}")
            names = set(archive.namelist())
            if SIGNAL_FILE not in names or MANIFEST_FILE not in names:
                raise ValueError("REFERENCE_TARGET_SCHEMA_INVALID")
            signal_payload = archive.read(SIGNAL_FILE)
            manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8-sig"))
    except BadZipFile as exc:
        raise ValueError("REFERENCE_TARGET_INVALID_ZIP") from exc
    if not isinstance(manifest, Mapping):
        raise ValueError("REFERENCE_TARGET_MANIFEST_INVALID")
    if manifest.get("schema_version") != SIGNAL_SCHEMA:
        raise ValueError("REFERENCE_TARGET_SCHEMA_MISMATCH")
    if manifest.get("status") != "SUCCESS":
        raise ValueError("REFERENCE_TARGET_NOT_SUCCESS")
    if manifest.get("automatic_live_orders_allowed") is True:
        raise ValueError("REFERENCE_TARGET_LIVE_ORDER_FLAG_INVALID")
    if manifest.get("live_capital_approved") is True:
        raise ValueError("REFERENCE_TARGET_LIVE_CAPITAL_FLAG_INVALID")
    contract = dict(manifest.get("files") or {}).get(SIGNAL_FILE)
    if not isinstance(contract, Mapping):
        raise ValueError("REFERENCE_TARGET_MANIFEST_ENTRY_MISSING")
    if str(contract.get("sha256") or "") != _sha(signal_payload):
        raise ValueError("REFERENCE_TARGET_HASH_MISMATCH")
    if int(contract.get("size", -1)) != len(signal_payload):
        raise ValueError("REFERENCE_TARGET_SIZE_MISMATCH")

    rows = _rows(signal_payload)
    if not rows:
        raise ValueError("REFERENCE_TARGET_EMPTY")
    dates = {str(row.get("signal_date") or "").strip() for row in rows}
    models = {str(row.get("champion_model") or "").strip() for row in rows}
    if len(dates) != 1 or "" in dates:
        raise ValueError("REFERENCE_TARGET_SIGNAL_DATE_INVALID")
    if len(models) != 1 or "" in models:
        raise ValueError("REFERENCE_TARGET_MODEL_INVALID")
    ranks: set[int] = set()
    symbols: set[str] = set()
    total_weight = 0.0
    normalized: list[dict[str, object]] = []
    for raw in rows:
        symbol = str(raw.get("symbol") or "").strip().upper()
        rank = int(float(str(raw.get("rank") or "0")))
        weight = float(str(raw.get("target_weight_pct") or "0"))
        if not symbol or symbol in symbols:
            raise ValueError("REFERENCE_TARGET_SYMBOL_INVALID_OR_DUPLICATE")
        if rank <= 0 or rank in ranks:
            raise ValueError("REFERENCE_TARGET_RANK_INVALID_OR_DUPLICATE")
        if weight <= 0 or weight > 100:
            raise ValueError("REFERENCE_TARGET_WEIGHT_INVALID")
        symbols.add(symbol)
        ranks.add(rank)
        total_weight += weight
        normalized.append({
            "signal_date": next(iter(dates)),
            "symbol": symbol,
            "champion_model": next(iter(models)),
            "rank": rank,
            "target_weight_pct": weight,
            "status": str(raw.get("status") or ""),
        })
    if total_weight > 100.000001:
        raise ValueError("REFERENCE_TARGET_TOTAL_WEIGHT_EXCEEDS_100")
    normalized.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))
    return {
        "signal_path": str(source),
        "signal_date": next(iter(dates)),
        "champion_model": next(iter(models)),
        "policy_id": str(manifest.get("policy_id") or ""),
        "target_weight_total_pct": total_weight,
        "allocation_rows": normalized,
        "predictions": [
            {
                "signal_date": row["signal_date"],
                "symbol": row["symbol"],
                "champion_rank": row["rank"],
                "rank": row["rank"],
                "selected_top_k": "true",
                "score": "",
                "above_ma250": "",
            }
            for row in normalized
        ],
        "model": {
            "signal_date": next(iter(dates)),
            "champion_model": next(iter(models)),
            "historical_reference_model": next(iter(models)),
            "historical_reference_status": "HISTORICALLY_VALIDATED_REFERENCE",
            "reference_policy_id": str(manifest.get("policy_id") or ""),
            "capital_budget_pct": total_weight,
            "research_eligible": True,
            "live_capital_approved": False,
        },
    }


def load_latest_reference_target(data_root: Path) -> dict[str, object]:
    root = Path(data_root) / "reference-ops-v16"
    candidates = sorted(
        root.glob("reference-signal-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if root.is_dir() else []
    errors: list[str] = []
    for path in candidates:
        try:
            return load_reference_target(path)
        except Exception as exc:
            errors.append(f"{path.name}:{type(exc).__name__}:{exc}")
    if errors:
        raise ValueError("REFERENCE_TARGET_NO_VALID_SIGNAL:" + "|".join(errors))
    raise ValueError("REFERENCE_TARGET_NO_SIGNAL_ARCHIVE")


__all__ = ["load_reference_target", "load_latest_reference_target"]
