"""V67 local data-readiness census for C3/HOSE research.

Stdlib-only and research-only.  It does not mutate the market store or fetch
network data.  The goal is to prove what is already available locally before
relaxing any point-in-time or price-basis guardrail.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping, Sequence

SCHEMA_VERSION = "hose_data_readiness_v67"

SYMBOL_COLUMNS = (
    "symbol", "ticker", "code", "security_code", "ma", "ma_ck", "ma_chung_khoan",
)
VENUE_COLUMNS = (
    "exchange", "market", "floor", "venue", "board", "trading_place",
    "stock_exchange", "exchange_code", "market_code", "san", "so_giao_dich",
)
EFFECTIVE_START_COLUMNS = (
    "effective_from", "start_date", "from_date", "valid_from", "begin_date",
    "effective_date", "day", "date", "ngay", "ngay_hieu_luc",
)
END_COLUMNS = (
    "effective_to", "end_date", "to_date", "valid_to", "finish_date",
    "ngay_ket_thuc", "ngay_het_hieu_luc",
)
LISTING_ONLY_COLUMNS = (
    "listed_date", "listing_date", "ngay_niem_yet", "listing_day",
)
SENSITIVE_TOKENS = ("secret", "password", "token", "api_key", "apikey", "credential")
CANDIDATE_EXTENSIONS = (".csv", ".gz", ".json", ".jsonl", ".sqlite", ".sqlite3", ".db")
NAME_HINTS = (
    "universe", "membership", "exchange", "venue", "market", "listing", "symbol",
    "ticker", "hose", "hsx", "reference", "pit", "history", "san",
)


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _find(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    lookup = {_norm(col): col for col in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def _safe_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text if len(text) <= 500 else text[:500] + "...[truncated]"


def _redact_metadata(key: str, value: object) -> object:
    low = key.lower()
    if any(token in low for token in SENSITIVE_TOKENS):
        return "[REDACTED]"
    return _safe_scalar(value)


def _query_scalar(db: sqlite3.Connection, sql: str) -> object:
    row = db.execute(sql).fetchone()
    return row[0] if row else None


def inspect_store(store: Path) -> dict[str, object]:
    result: dict[str, object] = {"store": str(store), "exists": store.is_file()}
    if not store.is_file():
        return result
    with sqlite3.connect(store) as db:
        tables = [
            str(row[0])
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if not str(row[0]).startswith("sqlite_")
        ]
        schema = {
            table: [str(row[1]) for row in db.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")')]
            for table in tables
        }
        result["tables"] = schema
        if "bars" in schema:
            cols = {_norm(c): c for c in schema["bars"]}
            result["bars_row_count"] = int(_query_scalar(db, "SELECT COUNT(*) FROM bars") or 0)
            if "day" in cols:
                result["bars_first_day"] = _query_scalar(db, f'SELECT MIN("{cols["day"]}") FROM bars')
                result["bars_last_day"] = _query_scalar(db, f'SELECT MAX("{cols["day"]}") FROM bars')
            if "symbol" in cols:
                result["bars_unique_symbol_count"] = int(_query_scalar(db, f'SELECT COUNT(DISTINCT "{cols["symbol"]}") FROM bars') or 0)
            if "asset_type" in cols:
                asset_rows = db.execute(
                    f'SELECT "{cols["asset_type"]}", COUNT(*), COUNT(DISTINCT "{cols.get("symbol", cols["asset_type"])}") '
                    'FROM bars GROUP BY 1 ORDER BY 1'
                ).fetchall()
                result["bars_by_asset_type"] = [
                    {"asset_type": row[0], "row_count": int(row[1]), "unique_symbol_count": int(row[2])}
                    for row in asset_rows
                ]
            for logical in ("source", "source_version", "price_basis"):
                if logical in cols:
                    values = db.execute(
                        f'SELECT COALESCE(CAST("{cols[logical]}" AS TEXT),"<NULL>"), COUNT(*) '
                        'FROM bars GROUP BY 1 ORDER BY COUNT(*) DESC,1 LIMIT 50'
                    ).fetchall()
                    result[f"bars_{logical}_distribution"] = [
                        {logical: row[0], "row_count": int(row[1])} for row in values
                    ]
            # Coverage by symbol is useful even when venue lineage is absent.
            if "symbol" in cols and "day" in cols:
                rows = db.execute(
                    f'SELECT "{cols["symbol"]}", MIN("{cols["day"]}"), MAX("{cols["day"]}"), COUNT(*) '
                    'FROM bars GROUP BY 1 ORDER BY 1'
                ).fetchall()
                result["symbol_coverage"] = [
                    {"symbol": str(row[0]), "first_day": row[1], "last_day": row[2], "row_count": int(row[3])}
                    for row in rows
                ]
        if "fetched_ranges" in schema:
            cols = {_norm(c): c for c in schema["fetched_ranges"]}
            if "symbol" in cols:
                result["fetched_range_symbol_count"] = int(
                    _query_scalar(db, f'SELECT COUNT(DISTINCT "{cols["symbol"]}") FROM fetched_ranges') or 0
                )
            if "start_day" in cols and "end_day" in cols:
                result["fetched_range_first_requested_day"] = _query_scalar(db, f'SELECT MIN("{cols["start_day"]}") FROM fetched_ranges')
                result["fetched_range_last_requested_day"] = _query_scalar(db, f'SELECT MAX("{cols["end_day"]}") FROM fetched_ranges')
        if "metadata" in schema:
            cols = {_norm(c): c for c in schema["metadata"]}
            if "key" in cols and "value" in cols:
                metadata = {}
                for key, value in db.execute(f'SELECT "{cols["key"]}", "{cols["value"]}" FROM metadata ORDER BY 1'):
                    metadata[str(key)] = _redact_metadata(str(key), value)
                result["metadata"] = metadata
    return result


def _csv_header(path: Path) -> list[str] | None:
    try:
        if path.suffix.lower() == ".gz":
            with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
                return next(csv.reader(handle), None)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return next(csv.reader(handle), None)
    except (OSError, UnicodeError, csv.Error):
        return None


def _json_columns(path: Path) -> list[str] | None:
    try:
        opener = gzip.open if path.suffix.lower() == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig") as handle:  # type: ignore[arg-type]
            if path.name.lower().endswith(".jsonl") or path.name.lower().endswith(".jsonl.gz"):
                line = handle.readline()
                item = json.loads(line) if line else None
            else:
                payload = json.load(handle)
                item = payload[0] if isinstance(payload, list) and payload else payload
            return list(item) if isinstance(item, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return None


def _sqlite_schemas(path: Path) -> list[tuple[str, list[str]]]:
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
            tables = [str(r[0]) for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not str(r[0]).startswith("sqlite_")]
            return [
                (table, [str(r[1]) for r in db.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")')])
                for table in tables
            ]
    except sqlite3.Error:
        return []


def classify_columns(columns: Sequence[str]) -> dict[str, object]:
    symbol = _find(columns, SYMBOL_COLUMNS)
    venue = _find(columns, VENUE_COLUMNS)
    start = _find(columns, EFFECTIVE_START_COLUMNS)
    end = _find(columns, END_COLUMNS)
    listing = _find(columns, LISTING_ONLY_COLUMNS)
    accepted_shape = bool(symbol and venue and start and (end or not listing))
    if not symbol:
        reason = "NO_SYMBOL_COLUMN"
    elif not venue:
        reason = "NO_VENUE_COLUMN"
    elif listing and not start:
        reason = "LISTING_DATE_ONLY_NOT_POINT_IN_TIME"
    elif not start:
        reason = "NO_EFFECTIVE_DATE_OR_INTERVAL"
    else:
        reason = "SHAPE_REQUIRES_CONTENT_VALIDATION" if accepted_shape else "UNSUPPORTED_SHAPE"
    return {
        "columns": list(columns),
        "symbol_col": symbol,
        "venue_col": venue,
        "start_col": start,
        "end_col": end,
        "listing_only_col": listing,
        "shape_candidate": accepted_shape,
        "classification": reason,
    }


def discover_local_candidates(roots: Iterable[Path], *, store: Path | None = None, max_files: int = 5000) -> dict[str, object]:
    inspected = 0
    candidates: list[dict[str, object]] = []
    skipped_limit = False
    store_resolved = store.resolve() if store and store.exists() else None
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if store_resolved and path.resolve() == store_resolved:
                continue
            name = path.name.lower()
            if not any(hint in name for hint in NAME_HINTS):
                continue
            if not (name.endswith(".csv") or name.endswith(".csv.gz") or name.endswith(".json") or name.endswith(".jsonl") or name.endswith(".jsonl.gz") or path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}):
                continue
            inspected += 1
            if inspected > max_files:
                skipped_limit = True
                break
            if name.endswith(".csv") or name.endswith(".csv.gz"):
                cols = _csv_header(path)
                if cols:
                    candidates.append({"path": str(path), "format": "CSV", **classify_columns(cols)})
            elif name.endswith(".json") or name.endswith(".jsonl") or name.endswith(".jsonl.gz"):
                cols = _json_columns(path)
                if cols:
                    candidates.append({"path": str(path), "format": "JSON", **classify_columns(cols)})
            else:
                for table, cols in _sqlite_schemas(path):
                    candidates.append({"path": str(path), "format": "SQLITE", "table": table, **classify_columns(cols)})
        if skipped_limit:
            break
    strict_shape_candidates = [item for item in candidates if item.get("shape_candidate")]
    return {
        "inspected_candidate_file_count": inspected,
        "scan_limit_reached": skipped_limit,
        "candidate_schemas": candidates,
        "strict_shape_candidate_count": len(strict_shape_candidates),
        "strict_shape_candidates": strict_shape_candidates,
        "note": "shape_candidate is not final PIT acceptance; row-level repeated-history/interval validation is still required before use",
    }


def build_report(store: Path, roots: Sequence[Path]) -> dict[str, object]:
    store_report = inspect_store(store)
    local = discover_local_candidates(roots, store=store)
    price_basis = store_report.get("bars_price_basis_distribution", [])
    return {
        "schema_version": SCHEMA_VERSION,
        "store": store_report,
        "local_lineage_scan": local,
        "gates": {
            "exchange_lineage_in_store": any(
                _find(cols, VENUE_COLUMNS)
                for cols in store_report.get("tables", {}).values()  # type: ignore[union-attr]
            ) if isinstance(store_report.get("tables"), dict) else False,
            "price_basis_values_observed": price_basis,
            "research_must_fail_closed_without_point_in_time_hose": True,
            "research_must_not_assume_adjusted_prices": True,
        },
        "research_only": True,
        "network_used": False,
        "store_mutated": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--search-root", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_report(args.store, args.search_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "bars_first_day": report["store"].get("bars_first_day"),
        "bars_last_day": report["store"].get("bars_last_day"),
        "bars_unique_symbol_count": report["store"].get("bars_unique_symbol_count"),
        "strict_shape_candidate_count": report["local_lineage_scan"].get("strict_shape_candidate_count"),
        "price_basis": report["store"].get("bars_price_basis_distribution"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
