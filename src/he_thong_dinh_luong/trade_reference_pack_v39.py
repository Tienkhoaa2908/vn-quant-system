"""Authoritative decision-surface reference pack for the frozen C3 policy.

V39 turns the V38 acquisition surface into a persistent local workspace.  The
first run seeds exact 510/510/52 templates.  Later runs validate locally saved
official source documents, compile the V36 sector/corporate-action inputs and
emit a self-contained assurance record.  It never downloads data, infers a
sector, backfills the future holdout, or grants live-capital permission.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

from .trade_evidence_accelerator_v38_io import (
    load_verified_bundle,
    read_csv_bytes,
    sha256_file,
    write_csv,
    write_json,
)

SCHEMA_VERSION = "vn_quant_trade_reference_pack_v39"
ASSURANCE_SCHEMA = "exact_ledger_decision_surface_assurance_v39"
EXPECTED_POLICY_ID = "c3-top10-cap3-c32fe6ec8c2fd4ce"
PRICE_BASIS_MODE = "RAW_UNADJUSTED_EXECUTION_PRICES"
PRICE_MULTIPLIER = 1000.0

REPORT_FILE = "trade_reference_pack_v39.json"
GAPS_FILE = "trade_reference_gaps_v39.csv"
COMPILED_SECTOR_FILE = "sector_master_point_in_time.csv"
COMPILED_ACTIONS_FILE = "corporate_actions.csv"
COMPILED_OPS_FILE = "operational_checklist_v37.json"
ASSURANCE_FILE = "exact_ledger_decision_surface_assurance_v39.json"

SECTOR_WORK_FILE = "sector_evidence_v39.csv"
WINDOW_WORK_FILE = "corporate_action_window_evidence_v39.csv"
EVENT_WORK_FILE = "corporate_action_events_v39.csv"
PRICE_WORK_FILE = "price_basis_execution_evidence_v39.csv"
CONTRACT_WORK_FILE = "execution_contract_evidence_v39.json"
OPS_WORK_FILE = "workstation_controls_v39.json"
SOURCE_DIR = "source_documents"

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_TRUE = {"1", "true", "yes", "y"}
SUPPORTED_EVENTS = {
    "CASH_DIVIDEND",
    "STOCK_DIVIDEND",
    "SPLIT",
    "REVERSE_SPLIT",
}
OPS_KEYS = (
    "data_freshness_fail_closed",
    "idempotent_daily_run_verified",
    "kill_switch_tested",
    "manual_order_confirmation_required",
    "account_sync_verified",
    "position_reconciliation_verified",
    "stale_signal_rejected",
    "duplicate_order_prevention_tested",
    "no_automatic_live_orders",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _truth(value: object) -> bool:
    return str(value or "").strip().lower() in _TRUE


def _safe_source_file(workspace: Path, filename: str, expected_sha: str) -> tuple[bool, str]:
    leaf = Path(str(filename).strip())
    if not leaf.name or leaf.name != str(filename).strip() or leaf.name in {".", ".."}:
        return False, "SOURCE_FILENAME_INVALID"
    if not _SHA_RE.fullmatch(str(expected_sha).strip().lower()):
        return False, "SOURCE_SHA256_INVALID"
    source = workspace / SOURCE_DIR / leaf.name
    if not source.is_file():
        return False, "SOURCE_FILE_MISSING"
    if sha256_file(source) != str(expected_sha).strip().lower():
        return False, "SOURCE_FILE_HASH_MISMATCH"
    return True, ""


def _key_digest(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> str:
    canonical = [
        "|".join(str(row.get(field) or "").strip() for field in fields)
        for row in rows
    ]
    canonical.sort()
    return sha256(("\n".join(canonical) + "\n").encode("utf-8")).hexdigest()


def _seed_workspace(
    workspace: Path,
    sector_required: Sequence[Mapping[str, str]],
    window_required: Sequence[Mapping[str, str]],
    price_required: Sequence[Mapping[str, str]],
    ops_candidate: Mapping[str, object],
) -> list[str]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / SOURCE_DIR).mkdir(exist_ok=True)
    created: list[str] = []

    sector_path = workspace / SECTOR_WORK_FILE
    if not sector_path.exists():
        rows = [
            {
                "signal_date": row.get("signal_date", ""),
                "execution_day": row.get("execution_day", ""),
                "symbol": row.get("symbol", ""),
                "sector": "",
                "effective_from": "",
                "effective_to": "",
                "source_document_id": "",
                "source_filename": "",
                "source_url": "",
                "source_sha256": "",
                "verified": False,
            }
            for row in sector_required
        ]
        write_csv(
            sector_path,
            rows,
            (
                "signal_date", "execution_day", "symbol", "sector",
                "effective_from", "effective_to", "source_document_id",
                "source_filename", "source_url", "source_sha256", "verified",
            ),
        )
        created.append(SECTOR_WORK_FILE)

    windows_path = workspace / WINDOW_WORK_FILE
    if not windows_path.exists():
        rows = [
            {
                "signal_date": row.get("signal_date", ""),
                "holding_start": row.get("holding_start", ""),
                "holding_end": row.get("holding_end", ""),
                "symbol": row.get("symbol", ""),
                "event_count": "",
                "source_document_id": "",
                "source_filename": "",
                "source_url": "",
                "source_sha256": "",
                "source_checked": False,
                "verified_complete": False,
            }
            for row in window_required
        ]
        write_csv(
            windows_path,
            rows,
            (
                "signal_date", "holding_start", "holding_end", "symbol",
                "event_count", "source_document_id", "source_filename",
                "source_url", "source_sha256", "source_checked",
                "verified_complete",
            ),
        )
        created.append(WINDOW_WORK_FILE)

    events_path = workspace / EVENT_WORK_FILE
    if not events_path.exists():
        write_csv(
            events_path,
            [],
            (
                "source_event_id", "symbol", "event_date", "event_type",
                "adjustment_factor", "cash_amount_vnd", "source_document_id",
                "source_filename", "source_url", "source_sha256", "verified",
            ),
        )
        created.append(EVENT_WORK_FILE)

    price_path = workspace / PRICE_WORK_FILE
    if not price_path.exists():
        rows = [
            {
                "execution_day": row.get("execution_day", ""),
                "crosscheck_symbol_count": "",
                "source_document_id": "",
                "source_filename": "",
                "official_source_url": "",
                "source_sha256": "",
                "verified": False,
            }
            for row in price_required
        ]
        write_csv(
            price_path,
            rows,
            (
                "execution_day", "crosscheck_symbol_count",
                "source_document_id", "source_filename",
                "official_source_url", "source_sha256", "verified",
            ),
        )
        created.append(PRICE_WORK_FILE)

    contract_path = workspace / CONTRACT_WORK_FILE
    if not contract_path.exists():
        write_json(
            contract_path,
            {
                "schema_version": "execution_contract_evidence_v39",
                "price_basis_mode": PRICE_BASIS_MODE,
                "price_unit_vnd_multiplier": PRICE_MULTIPLIER,
                "cash_dividend_tax_bps": None,
                "source_document_id": "",
                "source_filename": "",
                "source_url": "",
                "source_sha256": "",
                "reviewer": "",
                "reviewed_at": "",
                "verified": False,
            },
        )
        created.append(CONTRACT_WORK_FILE)

    ops_path = workspace / OPS_WORK_FILE
    if not ops_path.exists():
        checklist = dict(ops_candidate.get("checklist") or {})
        value = {key: checklist.get(key) is True for key in OPS_KEYS}
        value.update(
            {
                "account_sync_evidence_document_id": "",
                "account_sync_evidence_filename": "",
                "account_sync_evidence_sha256": "",
                "position_reconciliation_evidence_document_id": "",
                "position_reconciliation_evidence_filename": "",
                "position_reconciliation_evidence_sha256": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
        write_json(ops_path, value)
        created.append(OPS_WORK_FILE)
    return created


def _validate_exact_keys(
    rows: Sequence[Mapping[str, str]],
    required: Sequence[Mapping[str, str]],
    fields: Sequence[str],
    prefix: str,
) -> list[dict[str, str]]:
    expected = {
        tuple(str(row.get(field) or "").strip() for field in fields)
        for row in required
    }
    observed = {
        tuple(str(row.get(field) or "").strip() for field in fields)
        for row in rows
    }
    gaps: list[dict[str, str]] = []
    for key in sorted(expected - observed):
        gaps.append({"workstream": prefix, "key": "|".join(key), "reason": "REQUIRED_KEY_MISSING"})
    for key in sorted(observed - expected):
        gaps.append({"workstream": prefix, "key": "|".join(key), "reason": "UNEXPECTED_KEY"})
    if len(rows) != len(observed):
        gaps.append({"workstream": prefix, "key": "", "reason": "DUPLICATE_KEY"})
    return gaps


def _validate_workspace(
    workspace: Path,
    sector_required: Sequence[Mapping[str, str]],
    window_required: Sequence[Mapping[str, str]],
    price_required: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    sector_rows = _read_csv(workspace / SECTOR_WORK_FILE)
    window_rows = _read_csv(workspace / WINDOW_WORK_FILE)
    event_rows = _read_csv(workspace / EVENT_WORK_FILE)
    price_rows = _read_csv(workspace / PRICE_WORK_FILE)
    contract = json.loads((workspace / CONTRACT_WORK_FILE).read_text(encoding="utf-8-sig"))
    ops = json.loads((workspace / OPS_WORK_FILE).read_text(encoding="utf-8-sig"))
    if not isinstance(contract, Mapping) or not isinstance(ops, Mapping):
        raise ValueError("V39_JSON_WORKSPACE_NOT_OBJECT")

    gaps: list[dict[str, str]] = []
    gaps.extend(_validate_exact_keys(
        sector_rows, sector_required,
        ("signal_date", "execution_day", "symbol"), "SECTOR",
    ))
    gaps.extend(_validate_exact_keys(
        window_rows, window_required,
        ("signal_date", "holding_start", "holding_end", "symbol"), "CORPORATE_ACTION_WINDOW",
    ))
    gaps.extend(_validate_exact_keys(
        price_rows, price_required, ("execution_day",), "PRICE_BASIS",
    ))

    sector_valid = 0
    for row in sector_rows:
        key = f"{row.get('signal_date')}|{row.get('symbol')}"
        try:
            execution = date.fromisoformat(str(row.get("execution_day") or ""))
            start = date.fromisoformat(str(row.get("effective_from") or ""))
            end = date.fromisoformat(str(row.get("effective_to") or ""))
            date_ok = start <= execution <= end
        except ValueError:
            date_ok = False
        source_ok, source_reason = _safe_source_file(
            workspace,
            str(row.get("source_filename") or ""),
            str(row.get("source_sha256") or ""),
        )
        ok = bool(
            str(row.get("sector") or "").strip()
            and str(row.get("source_document_id") or "").strip()
            and str(row.get("source_url") or "").strip()
            and date_ok and source_ok and _truth(row.get("verified"))
        )
        sector_valid += int(ok)
        if not ok:
            reason = source_reason or "SECTOR_ROW_NOT_VERIFIED"
            gaps.append({"workstream": "SECTOR", "key": key, "reason": reason})

    window_valid = 0
    window_by_symbol: dict[str, list[dict[str, str]]] = {}
    for row in window_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        window_by_symbol.setdefault(symbol, []).append(dict(row))
        key = f"{row.get('signal_date')}|{symbol}"
        try:
            start = date.fromisoformat(str(row.get("holding_start") or ""))
            end = date.fromisoformat(str(row.get("holding_end") or ""))
            count = int(str(row.get("event_count") or ""))
            numeric_ok = end > start and count >= 0
        except ValueError:
            numeric_ok = False
        source_ok, source_reason = _safe_source_file(
            workspace,
            str(row.get("source_filename") or ""),
            str(row.get("source_sha256") or ""),
        )
        ok = bool(
            numeric_ok
            and str(row.get("source_document_id") or "").strip()
            and str(row.get("source_url") or "").strip()
            and source_ok
            and _truth(row.get("source_checked"))
            and _truth(row.get("verified_complete"))
        )
        window_valid += int(ok)
        if not ok:
            gaps.append({
                "workstream": "CORPORATE_ACTION_WINDOW",
                "key": key,
                "reason": source_reason or "WINDOW_NOT_VERIFIED_COMPLETE",
            })

    event_valid = 0
    seen_event_ids: set[str] = set()
    event_count_by_window: dict[tuple[str, str, str, str], int] = {}
    for row in event_rows:
        event_id = str(row.get("source_event_id") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        event_type = str(row.get("event_type") or "").strip().upper()
        key = event_id or f"line-{event_valid + 2}"
        source_ok, source_reason = _safe_source_file(
            workspace,
            str(row.get("source_filename") or ""),
            str(row.get("source_sha256") or ""),
        )
        try:
            event_day = date.fromisoformat(str(row.get("event_date") or ""))
            factor_text = str(row.get("adjustment_factor") or "").strip()
            cash_text = str(row.get("cash_amount_vnd") or "").strip()
            factor = float(factor_text) if factor_text else 0.0
            cash = float(cash_text) if cash_text else 0.0
            numeric_ok = all(math.isfinite(x) for x in (factor, cash))
            if event_type == "CASH_DIVIDEND":
                numeric_ok = numeric_ok and cash > 0.0
            else:
                numeric_ok = numeric_ok and factor > 0.0
        except (ValueError, TypeError):
            event_day = date.min
            numeric_ok = False
        matching_windows: list[dict[str, str]] = []
        for window in window_by_symbol.get(symbol, []):
            try:
                start = date.fromisoformat(str(window.get("holding_start") or ""))
                end = date.fromisoformat(str(window.get("holding_end") or ""))
            except ValueError:
                continue
            if start < event_day <= end:
                matching_windows.append(window)
        ok = bool(
            event_id and event_id not in seen_event_ids
            and symbol and event_type in SUPPORTED_EVENTS
            and numeric_ok and matching_windows
            and str(row.get("source_document_id") or "").strip()
            and str(row.get("source_url") or "").strip()
            and source_ok and _truth(row.get("verified"))
        )
        seen_event_ids.add(event_id)
        event_valid += int(ok)
        if not ok:
            gaps.append({
                "workstream": "CORPORATE_ACTION_EVENT",
                "key": key,
                "reason": source_reason or "EVENT_ROW_INVALID_OR_OUTSIDE_WINDOW",
            })
        if ok:
            for window in matching_windows:
                wkey = (
                    str(window.get("signal_date") or ""),
                    str(window.get("holding_start") or ""),
                    str(window.get("holding_end") or ""),
                    symbol,
                )
                event_count_by_window[wkey] = event_count_by_window.get(wkey, 0) + 1

    for row in window_rows:
        key_tuple = (
            str(row.get("signal_date") or ""),
            str(row.get("holding_start") or ""),
            str(row.get("holding_end") or ""),
            str(row.get("symbol") or "").strip().upper(),
        )
        try:
            expected_count = int(str(row.get("event_count") or ""))
        except ValueError:
            continue
        observed_count = event_count_by_window.get(key_tuple, 0)
        if observed_count != expected_count:
            gaps.append({
                "workstream": "CORPORATE_ACTION_WINDOW",
                "key": "|".join(key_tuple),
                "reason": f"EVENT_COUNT_MISMATCH:{observed_count}!={expected_count}",
            })

    price_valid = 0
    for row in price_rows:
        key = str(row.get("execution_day") or "")
        source_ok, source_reason = _safe_source_file(
            workspace,
            str(row.get("source_filename") or ""),
            str(row.get("source_sha256") or ""),
        )
        try:
            date.fromisoformat(key)
            crosschecks = int(str(row.get("crosscheck_symbol_count") or ""))
            numeric_ok = crosschecks > 0
        except ValueError:
            numeric_ok = False
        ok = bool(
            numeric_ok
            and str(row.get("source_document_id") or "").strip()
            and str(row.get("official_source_url") or "").strip()
            and source_ok and _truth(row.get("verified"))
        )
        price_valid += int(ok)
        if not ok:
            gaps.append({
                "workstream": "PRICE_BASIS",
                "key": key,
                "reason": source_reason or "PRICE_DATE_NOT_VERIFIED",
            })

    contract_source_ok, contract_source_reason = _safe_source_file(
        workspace,
        str(contract.get("source_filename") or ""),
        str(contract.get("source_sha256") or ""),
    )
    try:
        multiplier = float(contract.get("price_unit_vnd_multiplier"))
        dividend_tax_bps = float(contract.get("cash_dividend_tax_bps"))
        contract_numeric = (
            math.isfinite(multiplier) and multiplier == PRICE_MULTIPLIER
            and math.isfinite(dividend_tax_bps)
            and 0.0 <= dividend_tax_bps < 10_000.0
        )
    except (TypeError, ValueError):
        multiplier = 0.0
        dividend_tax_bps = -1.0
        contract_numeric = False
    contract_valid = bool(
        contract.get("schema_version") == "execution_contract_evidence_v39"
        and contract.get("price_basis_mode") == PRICE_BASIS_MODE
        and contract_numeric
        and str(contract.get("source_document_id") or "").strip()
        and str(contract.get("source_url") or "").strip()
        and str(contract.get("reviewer") or "").strip()
        and str(contract.get("reviewed_at") or "").strip()
        and contract_source_ok and contract.get("verified") is True
    )
    if not contract_valid:
        gaps.append({
            "workstream": "EXECUTION_CONTRACT",
            "key": "GLOBAL",
            "reason": contract_source_reason or "EXECUTION_CONTRACT_NOT_VERIFIED",
        })

    ops_values = {key: ops.get(key) is True for key in OPS_KEYS}
    ops_valid_count = sum(ops_values.values())
    for key in OPS_KEYS:
        if not ops_values[key]:
            gaps.append({"workstream": "OPERATIONS", "key": key, "reason": "CONTROL_NOT_VERIFIED"})
    for prefix in ("account_sync", "position_reconciliation"):
        source_ok, reason = _safe_source_file(
            workspace,
            str(ops.get(f"{prefix}_evidence_filename") or ""),
            str(ops.get(f"{prefix}_evidence_sha256") or ""),
        )
        if not source_ok or not str(ops.get(f"{prefix}_evidence_document_id") or "").strip():
            gaps.append({
                "workstream": "OPERATIONS",
                "key": prefix,
                "reason": reason or "WORKSTATION_EVIDENCE_MISSING",
            })

    unique_gaps = [dict(row) for row in {
        (row["workstream"], row["key"], row["reason"]): row for row in gaps
    }.values()]
    unique_gaps.sort(key=lambda row: (row["workstream"], row["key"], row["reason"]))
    ready = not unique_gaps
    return {
        "ready": ready,
        "gaps": unique_gaps,
        "sector_rows": sector_rows,
        "window_rows": window_rows,
        "event_rows": event_rows,
        "price_rows": price_rows,
        "contract": dict(contract),
        "ops": dict(ops),
        "metrics": {
            "sector_verified": sector_valid,
            "sector_required": len(sector_required),
            "windows_verified": window_valid,
            "windows_required": len(window_required),
            "events_verified": event_valid,
            "event_rows": len(event_rows),
            "price_dates_verified": price_valid,
            "price_dates_required": len(price_required),
            "execution_contract_verified": contract_valid,
            "operational_controls_verified": ops_valid_count,
            "operational_controls_required": len(OPS_KEYS),
        },
        "price_multiplier": multiplier,
        "cash_dividend_tax_bps": dividend_tax_bps,
    }


def _compile(
    output_dir: Path,
    validation: Mapping[str, object],
    v36: Mapping[str, object],
    v38: Mapping[str, object],
) -> dict[str, object]:
    sector_rows = list(validation["sector_rows"])
    event_rows = list(validation["event_rows"])
    ops = dict(validation["ops"])

    sector_compiled: list[dict[str, object]] = []
    seen_sector: set[tuple[str, str, str, str]] = set()
    for row in sector_rows:
        key = (
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("sector") or "").strip(),
            str(row.get("effective_from") or ""),
            str(row.get("effective_to") or ""),
        )
        if key in seen_sector:
            continue
        seen_sector.add(key)
        sector_compiled.append({
            "symbol": key[0],
            "sector": key[1],
            "effective_from": key[2],
            "effective_to": key[3],
            "source": str(row.get("source_document_id") or ""),
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        })
    sector_compiled.sort(key=lambda row: (row["symbol"], row["effective_from"], row["sector"]))
    sector_path = output_dir / COMPILED_SECTOR_FILE
    write_csv(
        sector_path,
        sector_compiled,
        ("symbol", "sector", "effective_from", "effective_to", "source", "confirmed_at"),
    )

    actions_compiled = [
        {
            "source_event_id": str(row.get("source_event_id") or ""),
            "symbol": str(row.get("symbol") or "").strip().upper(),
            "event_date": str(row.get("event_date") or ""),
            "event_type": str(row.get("event_type") or "").strip().upper(),
            "adjustment_factor": str(row.get("adjustment_factor") or ""),
            "cash_amount_vnd": str(row.get("cash_amount_vnd") or ""),
            "source": str(row.get("source_document_id") or ""),
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        for row in event_rows
    ]
    actions_compiled.sort(key=lambda row: (row["event_date"], row["symbol"], row["source_event_id"]))
    actions_path = output_dir / COMPILED_ACTIONS_FILE
    write_csv(
        actions_path,
        actions_compiled,
        (
            "source_event_id", "symbol", "event_date", "event_type",
            "adjustment_factor", "cash_amount_vnd", "source", "confirmed_at",
        ),
    )

    ops_path = output_dir / COMPILED_OPS_FILE
    write_json(ops_path, {key: ops.get(key) is True for key in OPS_KEYS})

    v36_report = dict(v36["report"])
    assurance = {
        "schema_version": ASSURANCE_SCHEMA,
        "policy_id": EXPECTED_POLICY_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_v36_artifact_sha256": v36["sha256"],
        "source_v38_artifact_sha256": v38["sha256"],
        "sqlite_sha256": str((v36_report.get("source") or {}).get("sqlite_sha256") or ""),
        "invalid_ohlcv_export_sha256": str(
            (v36_report.get("data_integrity") or {}).get("invalid_ohlcv_export_sha256") or ""
        ),
        "sector_master_sha256": sha256_file(sector_path),
        "corporate_actions_sha256": sha256_file(actions_path),
        "operational_checklist_sha256": sha256_file(ops_path),
        "price_basis_confirmed": True,
        "price_basis_mode": PRICE_BASIS_MODE,
        "price_unit_vnd_multiplier": validation["price_multiplier"],
        "cash_dividend_tax_bps": validation["cash_dividend_tax_bps"],
        "point_in_time_sector_master_complete": True,
        "corporate_actions_complete": True,
        "invalid_ohlcv_quarantine_approved": True,
        "decision_surface": {
            "sector_key_count": len(validation["sector_rows"]),
            "corporate_action_window_count": len(validation["window_rows"]),
            "corporate_action_event_count": len(validation["event_rows"]),
            "price_execution_date_count": len(validation["price_rows"]),
            "sector_key_digest": _key_digest(
                validation["sector_rows"], ("signal_date", "execution_day", "symbol")
            ),
            "corporate_action_window_digest": _key_digest(
                validation["window_rows"],
                ("signal_date", "holding_start", "holding_end", "symbol"),
            ),
            "price_execution_date_digest": _key_digest(
                validation["price_rows"], ("execution_day",)
            ),
        },
        "source_document_hashes": sorted({
            str(row.get("source_sha256") or "")
            for group in (
                validation["sector_rows"], validation["window_rows"],
                validation["event_rows"], validation["price_rows"],
            )
            for row in group
            if str(row.get("source_sha256") or "")
        }),
        "reviewer": str(validation["contract"].get("reviewer") or ""),
        "reviewed_at": str(validation["contract"].get("reviewed_at") or ""),
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    assurance_path = output_dir / ASSURANCE_FILE
    write_json(assurance_path, assurance)
    return {
        "sector_path": str(sector_path),
        "actions_path": str(actions_path),
        "ops_path": str(ops_path),
        "assurance_path": str(assurance_path),
        "sector_sha256": assurance["sector_master_sha256"],
        "actions_sha256": assurance["corporate_actions_sha256"],
        "ops_sha256": assurance["operational_checklist_sha256"],
        "assurance_sha256": sha256_file(assurance_path),
        "action_event_count": len(actions_compiled),
    }


def run_v39(
    *,
    v36_artifact_zip: Path,
    v38_artifact_zip: Path,
    workspace_dir: Path,
    output_dir: Path,
    expected_v36_sha256: str = "",
    expected_v38_sha256: str = "",
) -> dict[str, object]:
    out = Path(output_dir).resolve()
    if out.exists():
        raise FileExistsError(f"V39_OUTPUT_EXISTS:{out}")
    out.mkdir(parents=True)
    workspace = Path(workspace_dir).resolve()

    v36 = load_verified_bundle(
        v36_artifact_zip,
        manifest_name="analysis_bundle_manifest_v36.json",
        report_name="integrated_data_ledger_v36.json",
        expected_sha256=expected_v36_sha256,
    )
    v38 = load_verified_bundle(
        v38_artifact_zip,
        manifest_name="analysis_bundle_manifest_v38.json",
        report_name="trade_evidence_accelerator_v38.json",
        expected_sha256=expected_v38_sha256,
    )
    v36_report = dict(v36["report"])
    v38_report = dict(v38["report"])
    if v36_report.get("policy_id") != EXPECTED_POLICY_ID or v38_report.get("policy_id") != EXPECTED_POLICY_ID:
        raise ValueError("V39_POLICY_ID_MISMATCH")
    members = dict(v38["members"])
    required_members = {
        "required_sector_keys_v38.csv",
        "required_corporate_action_windows_v38.csv",
        "required_price_basis_dates_v38.csv",
        "operational_dry_run_v38.json",
    }
    missing = required_members - set(members)
    if missing:
        raise ValueError("V39_V38_MEMBER_MISSING:" + "|".join(sorted(missing)))
    sector_required = read_csv_bytes(members["required_sector_keys_v38.csv"])
    window_required = read_csv_bytes(members["required_corporate_action_windows_v38.csv"])
    price_required = read_csv_bytes(members["required_price_basis_dates_v38.csv"])
    ops_candidate = json.loads(members["operational_dry_run_v38.json"].decode("utf-8-sig"))
    created = _seed_workspace(
        workspace, sector_required, window_required, price_required, ops_candidate
    )
    validation = _validate_workspace(
        workspace, sector_required, window_required, price_required
    )
    write_csv(out / GAPS_FILE, validation["gaps"], ("workstream", "key", "reason"))
    compiled: dict[str, object] = {}
    if validation["ready"]:
        compiled = _compile(out, validation, v36, v38)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "decision": "READY_FOR_EXACT_LEDGER" if validation["ready"] else "REFERENCE_DATA_BLOCKED",
        "objective": "AUTHORITATIVE_DECISION_SURFACE_TO_EXACT_LEDGER",
        "policy_id": EXPECTED_POLICY_ID,
        "workspace_dir": str(workspace),
        "workspace_files_created_this_run": created,
        "source_v36": {
            "path": v36["path"], "sha256": v36["sha256"],
            "manifest_entry_count": v36["manifest_entry_count"],
        },
        "source_v38": {
            "path": v38["path"], "sha256": v38["sha256"],
            "manifest_entry_count": v38["manifest_entry_count"],
        },
        "metrics": validation["metrics"],
        "gap_count": len(validation["gaps"]),
        "gaps_by_workstream": {
            workstream: sum(row["workstream"] == workstream for row in validation["gaps"])
            for workstream in sorted({row["workstream"] for row in validation["gaps"]})
        },
        "reference_pack_ready": validation["ready"],
        "compiled": compiled,
        "next_action": (
            "RUN_EXACT_LEDGER_AND_V37_AUTOMATICALLY"
            if validation["ready"]
            else "COMPLETE_LOCAL_V39_WORKSPACE_FROM_OFFICIAL_SOURCE_DOCUMENTS"
        ),
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    write_json(out / REPORT_FILE, report)
    return report
