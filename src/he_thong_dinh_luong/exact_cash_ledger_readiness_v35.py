"""Fail-closed readiness audit for an exact cash-ledger shadow backtest.

V35 does not compute returns. It verifies the frozen V34.1 policy, audits the
canonical OHLCV SQLite store, and checks whether the external data contracts
needed by an exact ledger are present. A blocked readiness outcome is a
successful audit, not an execution failure.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence
from urllib.parse import quote
import zipfile

SCHEMA_VERSION = "exact_cash_ledger_readiness_v35"
REPORT_FILE = "exact_cash_ledger_readiness_v35.json"
GATES_FILE = "readiness_gates_v35.csv"
SCHEMA_FILE = "sqlite_schema_v35.csv"
BLOCKERS_FILE = "readiness_blockers_v35.csv"
EXPECTED_POLICY_ID = "c3-top10-cap3-c32fe6ec8c2fd4ce"
EXPECTED_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
EXPECTED_BREADTH = 10
EXPECTED_CAP = 3

ALIASES = {
    "day": ("day", "date", "ngay"),
    "symbol": ("symbol", "ma", "ticker"),
    "open": ("open", "gia_mo_cua"),
    "high": ("high", "gia_cao_nhat"),
    "low": ("low", "gia_thap_nhat"),
    "close": ("close", "gia_dong_cua"),
    "volume": ("volume", "khoi_luong"),
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _verified_v34(path: Path, expected_sha256: str) -> dict[str, object]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError("V35_V34_ARTIFACT_NOT_FOUND")
    actual_sha = _sha256(source)
    if expected_sha256 and actual_sha != expected_sha256:
        raise ValueError(f"V35_V34_SHA256_MISMATCH:{actual_sha}")
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V35_V34_ZIP_CRC_ERROR:{bad}")
        names = archive.namelist()
        manifest_names = [n for n in names if n.endswith("/analysis_bundle_manifest_v34.json")]
        policy_names = [n for n in names if n.endswith("/frozen_policy_v34.json")]
        if len(manifest_names) != 1 or len(policy_names) != 1:
            raise ValueError("V35_V34_REQUIRED_MEMBER_NOT_UNIQUE")
        manifest_payload = archive.read(manifest_names[0])
        manifest = json.loads(manifest_payload.decode("utf-8-sig"))
        if manifest.get("status") != "SUCCESS":
            raise ValueError("V35_V34_STATUS_NOT_SUCCESS")
        for item in manifest.get("files", []):
            member = str(item.get("path") or "")
            prefix = manifest_names[0].rsplit("/", 1)[0]
            full = f"{prefix}/{member}"
            payload = archive.read(full)
            if len(payload) != int(item.get("size_bytes", -1)):
                raise ValueError(f"V35_V34_MANIFEST_SIZE_MISMATCH:{member}")
            if _sha_bytes(payload) != str(item.get("sha256") or ""):
                raise ValueError(f"V35_V34_MANIFEST_HASH_MISMATCH:{member}")
        policy_payload = archive.read(policy_names[0])
        policy = json.loads(policy_payload.decode("utf-8-sig"))
    frozen = policy.get("policy") if isinstance(policy.get("policy"), Mapping) else {}
    permissions = policy.get("permissions") if isinstance(policy.get("permissions"), Mapping) else {}
    if policy.get("policy_id") != EXPECTED_POLICY_ID:
        raise ValueError("V35_POLICY_ID_MISMATCH")
    if frozen.get("model") != EXPECTED_MODEL:
        raise ValueError("V35_MODEL_MISMATCH")
    if int(frozen.get("breadth", -1)) != EXPECTED_BREADTH:
        raise ValueError("V35_BREADTH_MISMATCH")
    if int(frozen.get("fixed_voluntary_replacement_cap", -1)) != EXPECTED_CAP:
        raise ValueError("V35_CAP_MISMATCH")
    if permissions.get("live_capital_approved") is not False:
        raise ValueError("V35_LIVE_PERMISSION_INVALID")
    return {
        "artifact_sha256": actual_sha,
        "analysis_manifest_sha256": _sha_bytes(manifest_payload),
        "policy_sha256": _sha_bytes(policy_payload),
        "policy": policy,
    }


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(Path(path).resolve().as_posix())}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _resolve_columns(columns: Sequence[str]) -> dict[str, str | None]:
    lowered = {str(name).lower(): str(name) for name in columns}
    result: dict[str, str | None] = {}
    for logical, aliases in ALIASES.items():
        result[logical] = next((lowered[a] for a in aliases if a in lowered), None)
    return result


def audit_sqlite(path: Path, expected_sha256: str = "") -> dict[str, object]:
    store = Path(path).resolve()
    if not store.is_file():
        raise ValueError("V35_SQLITE_NOT_FOUND")
    actual_sha = _sha256(store)
    if expected_sha256 and actual_sha != expected_sha256:
        raise ValueError(f"V35_SQLITE_SHA256_MISMATCH:{actual_sha}")
    connection = _connect_readonly(store)
    try:
        tables = [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        if "bars" not in tables:
            raise ValueError("V35_BARS_TABLE_MISSING")
        schema_rows = [
            {
                "table": "bars",
                "column_index": int(row["cid"]),
                "column": str(row["name"]),
                "declared_type": str(row["type"] or ""),
                "not_null": bool(row["notnull"]),
                "primary_key": bool(row["pk"]),
            }
            for row in connection.execute("PRAGMA table_info(bars)")
        ]
        columns = [str(row["column"]) for row in schema_rows]
        resolved = _resolve_columns(columns)
        missing = [name for name, value in resolved.items() if value is None]
        if missing:
            raise ValueError("V35_BARS_COLUMNS_MISSING:" + "|".join(missing))
        q = lambda name: '"' + str(resolved[name]).replace('"', '""') + '"'
        stats = connection.execute(
            f"""SELECT COUNT(*) AS row_count,
                       MIN({q('day')}) AS first_day,
                       MAX({q('day')}) AS last_day,
                       COUNT(DISTINCT {q('day')}) AS distinct_days,
                       COUNT(DISTINCT {q('symbol')}) AS distinct_symbols
                FROM bars"""
        ).fetchone()
        duplicate_keys = connection.execute(
            f"""SELECT COUNT(*) AS duplicate_key_count FROM (
                    SELECT {q('day')}, {q('symbol')}
                    FROM bars GROUP BY {q('day')}, {q('symbol')}
                    HAVING COUNT(*) > 1
                )"""
        ).fetchone()["duplicate_key_count"]
        invalid_ohlcv = connection.execute(
            f"""SELECT COUNT(*) AS invalid_count FROM bars
                WHERE {q('day')} IS NULL OR {q('symbol')} IS NULL
                   OR {q('open')} IS NULL OR {q('high')} IS NULL
                   OR {q('low')} IS NULL OR {q('close')} IS NULL
                   OR {q('volume')} IS NULL
                   OR CAST({q('open')} AS REAL) <= 0
                   OR CAST({q('high')} AS REAL) <= 0
                   OR CAST({q('low')} AS REAL) <= 0
                   OR CAST({q('close')} AS REAL) <= 0
                   OR CAST({q('volume')} AS REAL) < 0
                   OR CAST({q('high')} AS REAL) < MAX(CAST({q('open')} AS REAL), CAST({q('close')} AS REAL))
                   OR CAST({q('low')} AS REAL) > MIN(CAST({q('open')} AS REAL), CAST({q('close')} AS REAL))
            """
        ).fetchone()["invalid_count"]
        t1 = connection.execute(
            f"""WITH ordered AS (
                    SELECT {q('day')} AS day, {q('symbol')} AS symbol,
                           LEAD({q('day')}) OVER (
                               PARTITION BY {q('symbol')} ORDER BY {q('day')}
                           ) AS next_day,
                           LEAD({q('open')}) OVER (
                               PARTITION BY {q('symbol')} ORDER BY {q('day')}
                           ) AS next_open
                    FROM bars
                )
                SELECT
                    SUM(CASE WHEN next_day IS NOT NULL THEN 1 ELSE 0 END) AS eligible_rows,
                    SUM(CASE WHEN next_day IS NOT NULL
                              AND next_open IS NOT NULL
                              AND CAST(next_open AS REAL) > 0
                             THEN 1 ELSE 0 END) AS covered_rows
                FROM ordered"""
        ).fetchone()
        conflicts = None
        if "conflicts" in tables:
            conflicts = int(connection.execute("SELECT COUNT(*) AS n FROM conflicts").fetchone()["n"])
    finally:
        connection.close()
    eligible_rows = int(t1["eligible_rows"] or 0)
    covered_rows = int(t1["covered_rows"] or 0)
    return {
        "path": str(store),
        "sha256": actual_sha,
        "tables": tables,
        "schema_rows": schema_rows,
        "resolved_columns": resolved,
        "row_count": int(stats["row_count"]),
        "first_day": str(stats["first_day"]),
        "last_day": str(stats["last_day"]),
        "distinct_days": int(stats["distinct_days"]),
        "distinct_symbols": int(stats["distinct_symbols"]),
        "duplicate_key_count": int(duplicate_keys),
        "invalid_ohlcv_row_count": int(invalid_ohlcv),
        "conflict_row_count": conflicts,
        "t1_open_eligible_row_count": eligible_rows,
        "t1_open_covered_row_count": covered_rows,
        "t1_open_coverage_ratio": covered_rows / eligible_rows if eligible_rows else 0.0,
    }


def _read_csv_contract(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"V35_CSV_HEADER_MISSING:{Path(path).name}")
        return [dict(row) for row in reader], list(reader.fieldnames)


def audit_sector_master(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"provided": False, "valid": False, "row_count": 0, "blocker": "POINT_IN_TIME_SECTOR_MASTER_MISSING"}
    source = Path(path).resolve()
    if not source.is_file():
        return {"provided": True, "valid": False, "row_count": 0, "blocker": "POINT_IN_TIME_SECTOR_MASTER_NOT_FOUND"}
    rows, fields = _read_csv_contract(source)
    required = {"symbol", "sector", "effective_from", "effective_to"}
    missing = sorted(required - set(fields))
    valid_rows = 0
    invalid_rows = 0
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        try:
            symbol = str(row.get("symbol") or "").strip().upper()
            sector = str(row.get("sector") or "").strip()
            start = date.fromisoformat(str(row.get("effective_from") or ""))
            end_text = str(row.get("effective_to") or "").strip()
            end = date.fromisoformat(end_text) if end_text else None
            key = (symbol, start.isoformat(), end.isoformat() if end else "")
            ok = bool(symbol and sector and (end is None or end >= start) and key not in seen)
            seen.add(key)
        except ValueError:
            ok = False
        valid_rows += int(ok)
        invalid_rows += int(not ok)
    valid = not missing and bool(rows) and invalid_rows == 0
    return {
        "provided": True,
        "path": str(source),
        "sha256": _sha256(source),
        "fields": fields,
        "missing_fields": missing,
        "row_count": len(rows),
        "valid_row_count": valid_rows,
        "invalid_row_count": invalid_rows,
        "valid": valid,
        "blocker": "" if valid else "POINT_IN_TIME_SECTOR_MASTER_INVALID",
    }


def audit_corporate_actions(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"provided": False, "valid": False, "row_count": 0, "blocker": "CORPORATE_ACTION_INVENTORY_MISSING"}
    source = Path(path).resolve()
    if not source.is_file():
        return {"provided": True, "valid": False, "row_count": 0, "blocker": "CORPORATE_ACTION_INVENTORY_NOT_FOUND"}
    rows, fields = _read_csv_contract(source)
    required = {"symbol", "event_date", "event_type"}
    missing = sorted(required - set(fields))
    has_value_field = bool({"adjustment_factor", "cash_amount_vnd"} & set(fields))
    invalid_rows = 0
    for row in rows:
        try:
            symbol = str(row.get("symbol") or "").strip().upper()
            event_type = str(row.get("event_type") or "").strip().upper()
            date.fromisoformat(str(row.get("event_date") or ""))
            factor = str(row.get("adjustment_factor") or "").strip()
            cash = str(row.get("cash_amount_vnd") or "").strip()
            numeric_ok = False
            for value in (factor, cash):
                if value:
                    number = float(value)
                    numeric_ok = numeric_ok or math.isfinite(number)
            ok = bool(symbol and event_type and numeric_ok)
        except (ValueError, TypeError):
            ok = False
        invalid_rows += int(not ok)
    valid = not missing and has_value_field and bool(rows) and invalid_rows == 0
    return {
        "provided": True,
        "path": str(source),
        "sha256": _sha256(source),
        "fields": fields,
        "missing_fields": missing,
        "has_value_field": has_value_field,
        "row_count": len(rows),
        "invalid_row_count": invalid_rows,
        "valid": valid,
        "blocker": "" if valid else "CORPORATE_ACTION_INVENTORY_INVALID",
    }


def run_v35(
    *,
    v34_artifact_zip: Path,
    sqlite_store: Path,
    output_dir: Path,
    expected_v34_sha256: str = "",
    expected_sqlite_sha256: str = "",
    sector_master: Path | None = None,
    corporate_actions: Path | None = None,
    price_basis_confirmed: bool = False,
    initial_capital_vnd: int = 1_000_000_000,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"V35_OUTPUT_EXISTS:{destination}")
    if initial_capital_vnd <= 0:
        raise ValueError("V35_INITIAL_CAPITAL_INVALID")
    frozen = _verified_v34(v34_artifact_zip, expected_v34_sha256)
    sqlite_audit = audit_sqlite(sqlite_store, expected_sqlite_sha256)
    sector = audit_sector_master(sector_master)
    actions = audit_corporate_actions(corporate_actions)

    gates = [
        ("V34_POLICY_VERIFIED", True, ""),
        ("SQLITE_UNIQUE_DAY_SYMBOL", sqlite_audit["duplicate_key_count"] == 0, "SQLITE_DUPLICATE_DAY_SYMBOL"),
        ("SQLITE_OHLCV_VALID", sqlite_audit["invalid_ohlcv_row_count"] == 0, "SQLITE_INVALID_OHLCV"),
        ("SQLITE_CONFLICTS_ZERO", sqlite_audit["conflict_row_count"] in (None, 0), "SQLITE_CONFLICTS_PRESENT"),
        ("T1_OPEN_COVERAGE_COMPLETE", sqlite_audit["t1_open_coverage_ratio"] == 1.0, "T1_OPEN_COVERAGE_INCOMPLETE"),
        ("PRICE_BASIS_CONFIRMED", bool(price_basis_confirmed), "PRICE_BASIS_UNCONFIRMED"),
        ("POINT_IN_TIME_SECTOR_MASTER_VALID", bool(sector["valid"]), str(sector["blocker"])),
        ("CORPORATE_ACTION_INVENTORY_VALID", bool(actions["valid"]), str(actions["blocker"])),
        ("INVERSE_VOLATILITY_ALLOCATOR_AVAILABLE", True, ""),
        ("SINGLE_NAME_CAP_15_AVAILABLE", True, ""),
        ("LOT_SIZE_100_LEDGER_REQUIRED", True, ""),
        ("SECTOR_CAP_25_DATA_READY", bool(sector["valid"]), str(sector["blocker"])),
    ]
    gate_rows = [
        {"gate": name, "passed": passed, "blocker": "" if passed else blocker}
        for name, passed, blocker in gates
    ]
    blockers = sorted({row["blocker"] for row in gate_rows if row["blocker"]})
    ready = not blockers
    recommendation = (
        "READY_TO_IMPLEMENT_EXACT_CASH_LEDGER_SHADOW_BACKTEST"
        if ready
        else "BLOCKED_COMPLETE_DATA_CONTRACTS_BEFORE_EXACT_LEDGER"
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "audit_outcome": "READY" if ready else "BLOCKED",
        "recommendation": recommendation,
        "policy_id": EXPECTED_POLICY_ID,
        "frozen_policy": {
            "model": EXPECTED_MODEL,
            "breadth": EXPECTED_BREADTH,
            "fixed_voluntary_replacement_cap": EXPECTED_CAP,
            "source_v34_artifact_sha256": frozen["artifact_sha256"],
            "source_v34_policy_sha256": frozen["policy_sha256"],
        },
        "initial_capital_vnd_for_future_shadow_ledger": int(initial_capital_vnd),
        "sqlite": {k: v for k, v in sqlite_audit.items() if k not in {"schema_rows", "tables"}},
        "sector_master": sector,
        "corporate_actions": actions,
        "price_basis_confirmed": bool(price_basis_confirmed),
        "gates": gate_rows,
        "blockers": blockers,
        "exact_cash_ledger_pnl_computed": False,
        "historical_promotion_allowed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "actionable": False,
    }
    destination.mkdir(parents=True)
    _write_json(destination / REPORT_FILE, report)
    _write_csv(destination / GATES_FILE, gate_rows, ("gate", "passed", "blocker"))
    _write_csv(
        destination / SCHEMA_FILE,
        sqlite_audit["schema_rows"],
        ("table", "column_index", "column", "declared_type", "not_null", "primary_key"),
    )
    _write_csv(destination / BLOCKERS_FILE, [{"blocker": item} for item in blockers], ("blocker",))
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v34-artifact-zip", type=Path, required=True)
    parser.add_argument("--sqlite-store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v34-sha256", default="")
    parser.add_argument("--expected-sqlite-sha256", default="")
    parser.add_argument("--sector-master", type=Path)
    parser.add_argument("--corporate-actions", type=Path)
    parser.add_argument("--price-basis-confirmed", action="store_true")
    parser.add_argument("--initial-capital-vnd", type=int, default=1_000_000_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_v35(
        v34_artifact_zip=args.v34_artifact_zip,
        sqlite_store=args.sqlite_store,
        output_dir=args.output_dir,
        expected_v34_sha256=args.expected_v34_sha256,
        expected_sqlite_sha256=args.expected_sqlite_sha256,
        sector_master=args.sector_master,
        corporate_actions=args.corporate_actions,
        price_basis_confirmed=args.price_basis_confirmed,
        initial_capital_vnd=args.initial_capital_vnd,
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
