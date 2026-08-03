"""Compact, fail-closed bulk importer for the persistent V39 workspace.

The core V39 contract validates 510 sector keys, 510 corporate-action windows
and 52 price-basis dates. This helper does not weaken that contract. It only
expands compact, reviewer-approved interval records into the exact per-key
workspace rows before the normal V39 validator rechecks source files, hashes,
dates, event counts and verification flags.
"""
from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path
from typing import Mapping, Sequence

SECTOR_IMPORT_FILE = "sector_intervals_import_v39.csv"
ACTION_COVERAGE_IMPORT_FILE = "corporate_action_coverage_import_v39.csv"
PRICE_COVERAGE_IMPORT_FILE = "price_basis_coverage_import_v39.csv"
AUDIT_FILE = "bulk_import_audit_v39.json"

SECTOR_WORK_FILE = "sector_evidence_v39.csv"
WINDOW_WORK_FILE = "corporate_action_window_evidence_v39.csv"
EVENT_WORK_FILE = "corporate_action_events_v39.csv"
PRICE_WORK_FILE = "price_basis_execution_evidence_v39.csv"

_TRUE = {"1", "true", "yes", "y"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"V39_BULK_HEADER_MISSING:{path.name}")
        return [dict(row) for row in reader]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _require_fields(path: Path, rows: Sequence[Mapping[str, str]], required: set[str]) -> None:
    if not rows:
        return
    missing = sorted(required - set(rows[0]))
    if missing:
        raise ValueError(f"V39_BULK_FIELDS_MISSING:{path.name}:" + "|".join(missing))


def _parse_day(value: object, code: str) -> date:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise ValueError(f"{code}:{value}") from exc


def _unique_match(matches: Sequence[Mapping[str, str]], key: str, code: str) -> Mapping[str, str] | None:
    if not matches:
        return None
    signatures = {
        tuple(sorted((str(k), str(v)) for k, v in row.items()))
        for row in matches
    }
    if len(signatures) != 1:
        raise ValueError(f"{code}:{key}:{len(matches)}")
    return matches[0]


def _sector_match(rows: Sequence[Mapping[str, str]], symbol: str, execution: date) -> Mapping[str, str] | None:
    matches = []
    for row in rows:
        if str(row.get("symbol") or "").strip().upper() != symbol:
            continue
        start = _parse_day(row.get("effective_from"), "V39_BULK_SECTOR_START_INVALID")
        end = _parse_day(row.get("effective_to"), "V39_BULK_SECTOR_END_INVALID")
        if start <= execution <= end:
            matches.append(row)
    return _unique_match(matches, f"{symbol}|{execution.isoformat()}", "V39_BULK_SECTOR_CONFLICT")


def _coverage_match(
    rows: Sequence[Mapping[str, str]],
    *,
    symbol: str | None,
    start: date,
    end: date,
    code: str,
) -> Mapping[str, str] | None:
    exact: list[Mapping[str, str]] = []
    wildcard: list[Mapping[str, str]] = []
    for row in rows:
        row_symbol = str(row.get("symbol") or "*").strip().upper() or "*"
        coverage_start = _parse_day(row.get("coverage_from"), f"{code}_START_INVALID")
        coverage_end = _parse_day(row.get("coverage_to"), f"{code}_END_INVALID")
        if coverage_start <= start and coverage_end >= end:
            if symbol is None or row_symbol == "*":
                wildcard.append(row)
            elif row_symbol == symbol:
                exact.append(row)
            elif row_symbol == "*":
                wildcard.append(row)
    chosen = exact if exact else wildcard
    key = f"{symbol or '*'}|{start.isoformat()}|{end.isoformat()}"
    return _unique_match(chosen, key, f"{code}_CONFLICT")


def _event_counts(event_rows: Sequence[Mapping[str, str]]) -> list[tuple[str, date]]:
    output: list[tuple[str, date]] = []
    for index, row in enumerate(event_rows, start=2):
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError(f"V39_BULK_EVENT_SYMBOL_MISSING:{index}")
        output.append((symbol, _parse_day(row.get("event_date"), "V39_BULK_EVENT_DATE_INVALID")))
    return output


def apply_bulk_import(workspace_dir: Path) -> dict[str, object]:
    workspace = Path(workspace_dir).resolve()
    required_work = (SECTOR_WORK_FILE, WINDOW_WORK_FILE, EVENT_WORK_FILE, PRICE_WORK_FILE)
    missing_work = [name for name in required_work if not (workspace / name).is_file()]
    if missing_work:
        raise ValueError("V39_BULK_WORKSPACE_NOT_SEEDED:" + "|".join(missing_work))

    sector_work = _read_csv(workspace / SECTOR_WORK_FILE)
    window_work = _read_csv(workspace / WINDOW_WORK_FILE)
    event_work = _read_csv(workspace / EVENT_WORK_FILE)
    price_work = _read_csv(workspace / PRICE_WORK_FILE)

    sector_import_path = workspace / SECTOR_IMPORT_FILE
    action_import_path = workspace / ACTION_COVERAGE_IMPORT_FILE
    price_import_path = workspace / PRICE_COVERAGE_IMPORT_FILE
    sector_import = _read_csv(sector_import_path) if sector_import_path.is_file() else []
    action_import = _read_csv(action_import_path) if action_import_path.is_file() else []
    price_import = _read_csv(price_import_path) if price_import_path.is_file() else []

    _require_fields(
        sector_import_path,
        sector_import,
        {
            "symbol", "sector", "effective_from", "effective_to",
            "source_document_id", "source_filename", "source_url",
            "source_sha256", "verified",
        },
    )
    _require_fields(
        action_import_path,
        action_import,
        {
            "symbol", "coverage_from", "coverage_to", "source_document_id",
            "source_filename", "source_url", "source_sha256",
            "source_checked", "verified_complete",
        },
    )
    _require_fields(
        price_import_path,
        price_import,
        {
            "coverage_from", "coverage_to", "crosscheck_symbol_count",
            "source_document_id", "source_filename", "official_source_url",
            "source_sha256", "verified",
        },
    )

    sector_expanded = 0
    if sector_import:
        for row in sector_work:
            symbol = str(row.get("symbol") or "").strip().upper()
            execution = _parse_day(row.get("execution_day"), "V39_BULK_EXECUTION_DAY_INVALID")
            match = _sector_match(sector_import, symbol, execution)
            if match is None:
                continue
            for field in (
                "sector", "effective_from", "effective_to", "source_document_id",
                "source_filename", "source_url", "source_sha256", "verified",
            ):
                row[field] = match.get(field, "")
            sector_expanded += 1
        _write_csv(workspace / SECTOR_WORK_FILE, sector_work, tuple(sector_work[0]))

    event_index = _event_counts(event_work)
    windows_expanded = 0
    if action_import:
        for row in window_work:
            symbol = str(row.get("symbol") or "").strip().upper()
            start = _parse_day(row.get("holding_start"), "V39_BULK_HOLDING_START_INVALID")
            end = _parse_day(row.get("holding_end"), "V39_BULK_HOLDING_END_INVALID")
            match = _coverage_match(
                action_import,
                symbol=symbol,
                start=start,
                end=end,
                code="V39_BULK_ACTION_COVERAGE",
            )
            if match is None:
                continue
            row["event_count"] = sum(
                event_symbol == symbol and start < event_day <= end
                for event_symbol, event_day in event_index
            )
            for field in (
                "source_document_id", "source_filename", "source_url",
                "source_sha256", "source_checked", "verified_complete",
            ):
                row[field] = match.get(field, "")
            windows_expanded += 1
        _write_csv(workspace / WINDOW_WORK_FILE, window_work, tuple(window_work[0]))

    price_expanded = 0
    if price_import:
        for row in price_work:
            execution = _parse_day(row.get("execution_day"), "V39_BULK_PRICE_DAY_INVALID")
            match = _coverage_match(
                price_import,
                symbol=None,
                start=execution,
                end=execution,
                code="V39_BULK_PRICE_COVERAGE",
            )
            if match is None:
                continue
            for field in (
                "crosscheck_symbol_count", "source_document_id", "source_filename",
                "official_source_url", "source_sha256", "verified",
            ):
                row[field] = match.get(field, "")
            price_expanded += 1
        _write_csv(workspace / PRICE_WORK_FILE, price_work, tuple(price_work[0]))

    audit = {
        "schema_version": "vn_quant_trade_reference_bulk_import_v39",
        "workspace_dir": str(workspace),
        "input_files_present": {
            SECTOR_IMPORT_FILE: sector_import_path.is_file(),
            ACTION_COVERAGE_IMPORT_FILE: action_import_path.is_file(),
            PRICE_COVERAGE_IMPORT_FILE: price_import_path.is_file(),
        },
        "compact_rows": {
            "sector_intervals": len(sector_import),
            "corporate_action_coverages": len(action_import),
            "price_basis_coverages": len(price_import),
            "corporate_action_events": len(event_work),
        },
        "expanded_rows": {
            "sector_keys": sector_expanded,
            "corporate_action_windows": windows_expanded,
            "price_basis_dates": price_expanded,
        },
        "approval_invented": False,
        "source_hash_validation_delegated_to_core_v39": True,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(workspace / AUDIT_FILE, audit)
    return audit
