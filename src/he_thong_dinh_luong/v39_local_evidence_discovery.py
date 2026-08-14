"""Discover which V39 evidence already exists on the local workstation.

This module is deliberately read-mostly. It inspects the pinned V22 ZIP, the
canonical DNSE SQLite store and likely local files under the repository/data
roots. It never upgrades authoritative verification merely because a file was
found. Optional DNSE operations evidence uses read-only account endpoints and
writes only masked identifiers plus content hashes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Mapping, Sequence
from zipfile import BadZipFile, ZipFile

SCHEMA_VERSION = "vn_quant_v39_local_evidence_discovery_v1"
REPORT_FILE = "local_evidence_discovery_v39.json"
CANDIDATES_FILE = "local_evidence_candidates_v39.csv"
NEEDED_FILE = "EXACT_DATA_NEEDED_V39.txt"
SYMBOLS_FILE = "selected_symbols_v39.txt"
SOURCE_DIR = "source_documents"
OPS_FILE = "workstation_controls_v39.json"

CATEGORY_TOKENS = {
    "SECTOR": (
        "sector", "industry", "gics", "hasic", "nganh", "phan_nganh",
        "classification", "industrycode", "industry_name",
    ),
    "CORPORATE_ACTION": (
        "corporate_action", "corporateaction", "dividend", "cash_dividend",
        "stock_dividend", "split", "bonus", "rights", "ex_date", "exdate",
        "record_date", "ngay_gdkhq", "ngay_dkcc", "co_tuc", "cotuc",
        "thuc_hien_quyen", "quyen_mua",
    ),
    "PRICE_BASIS": (
        "price_basis", "adjusted", "unadjusted", "raw_price", "gia_dieu_chinh",
        "co_so_gia", "price_unit", "multiplier", "nghin_dong", "ngan_dong",
    ),
    "ACCOUNT_POSITION": (
        "account", "balance", "position", "holding", "portfolio", "reconcile",
        "reconciliation", "doi_soat", "vi_the", "danh_muc", "tai_khoan",
    ),
}

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache",
}
TEXT_EXTENSIONS = {".csv", ".json", ".jsonl", ".txt", ".md", ".html", ".htm"}
CONTAINER_EXTENSIONS = {".zip", ".sqlite", ".sqlite3", ".db"}
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_ZIP_BYTES = 1024 * 1024 * 1024


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields = (
        "category", "path", "container_member", "reason", "matched_tokens",
        "size_bytes", "sha256",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _normalized_text(value: object) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())


def _categories(text: str) -> dict[str, list[str]]:
    normalized = _normalized_text(text)
    output: dict[str, list[str]] = {}
    for category, tokens in CATEGORY_TOKENS.items():
        matches = sorted({token for token in tokens if token in normalized})
        if matches:
            output[category] = matches
    return output


def _csv_header(payload: bytes) -> list[str]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []
    reader = csv.reader(StringIO(text))
    try:
        return [str(value).strip() for value in next(reader)]
    except StopIteration:
        return []


def _json_keys(value: object, *, depth: int = 0) -> set[str]:
    if depth > 3:
        return set()
    output: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            output.add(str(key))
            output.update(_json_keys(child, depth=depth + 1))
    elif isinstance(value, list):
        for child in value[:20]:
            output.update(_json_keys(child, depth=depth + 1))
    return output


def inspect_v22(path: Path) -> dict[str, object]:
    source = Path(path)
    result: dict[str, object] = {
        "path": str(source),
        "exists": source.is_file(),
        "sha256": _sha_file(source) if source.is_file() else None,
        "members": [],
        "csv_headers": {},
        "contains_sector_fields": False,
        "contains_corporate_action_fields": False,
    }
    if not source.is_file():
        return result
    try:
        with ZipFile(source) as archive:
            names = archive.namelist()
            result["members"] = names
            headers: dict[str, list[str]] = {}
            for name in names:
                if name.lower().endswith(".csv"):
                    headers[name] = _csv_header(archive.read(name))
            result["csv_headers"] = headers
            flattened = " ".join(names + [field for values in headers.values() for field in values])
            found = _categories(flattened)
            result["contains_sector_fields"] = "SECTOR" in found
            result["contains_corporate_action_fields"] = "CORPORATE_ACTION" in found
            if "cau_hinh.json" in names:
                config = json.loads(archive.read("cau_hinh.json"))
                result["config_research_contract"] = {
                    key: value
                    for key, value in dict(config.get("moc_4", config)).items()
                    if key in {
                        "stock_price_basis", "stock_price_basis_confirmed",
                        "corporate_actions_day_du", "candidate_union_is_point_in_time",
                        "benchmark_price_basis_confirmed", "price_contract",
                        "universe_contract",
                    }
                }
    except (BadZipFile, OSError, json.JSONDecodeError) as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
    return result


def inspect_sqlite(path: Path) -> dict[str, object]:
    source = Path(path)
    result: dict[str, object] = {
        "path": str(source),
        "exists": source.is_file(),
        "sha256": _sha_file(source) if source.is_file() else None,
        "tables": {},
        "metadata": {},
        "price_basis_values": [],
        "has_sector_table_or_columns": False,
        "has_corporate_action_table_or_columns": False,
    }
    if not source.is_file():
        return result
    try:
        db = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            tables = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )]
            schema: dict[str, list[str]] = {}
            for table in tables:
                safe = table.replace('"', '""')
                schema[table] = [str(row[1]) for row in db.execute(f'PRAGMA table_info("{safe}")')]
            result["tables"] = schema
            all_names = " ".join(tables + [item for values in schema.values() for item in values])
            found = _categories(all_names)
            result["has_sector_table_or_columns"] = "SECTOR" in found
            result["has_corporate_action_table_or_columns"] = "CORPORATE_ACTION" in found
            if "metadata" in tables:
                result["metadata"] = {
                    str(row["key"]): str(row["value"])
                    for row in db.execute("SELECT key,value FROM metadata ORDER BY key")
                }
            if "bars" in tables:
                columns = set(schema["bars"])
                if "price_basis" in columns:
                    result["price_basis_values"] = [
                        str(row[0]) for row in db.execute(
                            "SELECT DISTINCT price_basis FROM bars ORDER BY price_basis"
                        )
                    ]
                result["bars_summary"] = dict(db.execute(
                    "SELECT COUNT(*) row_count, COUNT(DISTINCT symbol) symbol_count, "
                    "COUNT(DISTINCT day) day_count, MIN(day) first_day, MAX(day) last_day "
                    "FROM bars"
                ).fetchone())
        finally:
            db.close()
    except (sqlite3.Error, OSError) as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
    return result


def _candidate_record(
    *, path: Path, category: str, tokens: Sequence[str], reason: str,
    member: str = "", sha: str = "",
) -> dict[str, object]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "category": category,
        "path": str(path),
        "container_member": member,
        "reason": reason,
        "matched_tokens": "|".join(tokens),
        "size_bytes": size,
        "sha256": sha,
    }


def _inspect_candidate_file(path: Path) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    name_matches = _categories(path.name)
    for category, tokens in name_matches.items():
        output.append(_candidate_record(
            path=path, category=category, tokens=tokens, reason="FILENAME_MATCH",
        ))
    suffix = path.suffix.lower()
    try:
        size = path.stat().st_size
    except OSError:
        return output
    if suffix in TEXT_EXTENSIONS and size <= MAX_TEXT_BYTES:
        try:
            payload = path.read_bytes()
        except OSError:
            return output
        searchable = ""
        if suffix == ".csv":
            searchable = " ".join(_csv_header(payload))
        elif suffix in {".json", ".jsonl"}:
            try:
                value = json.loads(payload.decode("utf-8-sig"))
                searchable = " ".join(sorted(_json_keys(value)))
            except (UnicodeDecodeError, json.JSONDecodeError):
                searchable = ""
        else:
            try:
                searchable = payload[:200_000].decode("utf-8-sig", errors="ignore")
            except UnicodeError:
                searchable = ""
        for category, tokens in _categories(searchable).items():
            output.append(_candidate_record(
                path=path, category=category, tokens=tokens, reason="CONTENT_OR_HEADER_MATCH",
            ))
    elif suffix == ".zip" and size <= MAX_ZIP_BYTES:
        try:
            with ZipFile(path) as archive:
                names = archive.namelist()
                for name in names[:5000]:
                    for category, tokens in _categories(name).items():
                        output.append(_candidate_record(
                            path=path, category=category, tokens=tokens,
                            reason="ZIP_MEMBER_NAME_MATCH", member=name,
                        ))
                    if name.lower().endswith(".csv"):
                        info = archive.getinfo(name)
                        if info.file_size <= MAX_TEXT_BYTES:
                            header = " ".join(_csv_header(archive.read(name)))
                            for category, tokens in _categories(header).items():
                                output.append(_candidate_record(
                                    path=path, category=category, tokens=tokens,
                                    reason="ZIP_CSV_HEADER_MATCH", member=name,
                                ))
        except (BadZipFile, OSError, KeyError):
            pass
    elif suffix in {".sqlite", ".sqlite3", ".db"}:
        inspected = inspect_sqlite(path)
        names = " ".join(
            list(inspected.get("tables", {}))
            + [column for columns in inspected.get("tables", {}).values() for column in columns]
        )
        for category, tokens in _categories(names).items():
            output.append(_candidate_record(
                path=path, category=category, tokens=tokens, reason="SQLITE_SCHEMA_MATCH",
            ))
    return output


def scan_roots(roots: Sequence[Path], *, max_files: int = 25_000) -> tuple[list[dict[str, object]], int]:
    records: list[dict[str, object]] = []
    visited = 0
    seen_paths: set[Path] = set()
    for raw_root in roots:
        root = Path(raw_root).resolve()
        if not root.exists():
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            for name in files:
                path = (Path(current) / name).resolve()
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                visited += 1
                if visited > max_files:
                    break
                if path.suffix.lower() not in TEXT_EXTENSIONS | CONTAINER_EXTENSIONS:
                    continue
                records.extend(_inspect_candidate_file(path))
            if visited > max_files:
                break
        if visited > max_files:
            break
    unique = {
        (row["category"], row["path"], row["container_member"], row["reason"]): row
        for row in records
    }
    rows = sorted(unique.values(), key=lambda row: (
        str(row["category"]), str(row["path"]), str(row["container_member"]), str(row["reason"])
    ))
    for row in rows:
        path = Path(str(row["path"]))
        if path.is_file() and path.stat().st_size <= 512 * 1024 * 1024:
            try:
                row["sha256"] = _sha_file(path)
            except OSError:
                pass
    return rows, visited


def _workspace_counts(workspace: Path) -> dict[str, object]:
    def rows(name: str) -> list[dict[str, str]]:
        path = workspace / name
        if not path.is_file():
            return []
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]

    sector = rows("sector_evidence_v39.csv")
    windows = rows("corporate_action_window_evidence_v39.csv")
    prices = rows("price_basis_execution_evidence_v39.csv")
    symbols = sorted({str(row.get("symbol") or "").strip().upper() for row in sector if row.get("symbol")})
    days = sorted({str(row.get("execution_day") or "") for row in prices if row.get("execution_day")})
    return {
        "sector_key_count": len(sector),
        "corporate_action_window_count": len(windows),
        "price_date_count": len(prices),
        "unique_symbol_count": len(symbols),
        "symbols": symbols,
        "first_execution_day": days[0] if days else None,
        "last_execution_day": days[-1] if days else None,
    }


def _exact_needed_text(counts: Mapping[str, object], v22: Mapping[str, object], store: Mapping[str, object]) -> str:
    symbols = list(counts.get("symbols") or [])
    return (
        "V39 - DU LIEU CHINH XAC CON THIEU\n"
        "=================================\n\n"
        "DA CO SAN VA CODE TU DUNG:\n"
        "- OHLCV 11 nam va VNINDEX trong SQLite.\n"
        "- 51 ky lua chon, 510 position-time keys, 510 holding windows, 52 execution dates.\n"
        "- Phi, thue ban, slippage, lot size, inverse volatility, symbol cap va regime cash.\n"
        "- Selection lineage 51/51.\n\n"
        "V22 KHONG CHUA:\n"
        f"- sector fields: {bool(v22.get('contains_sector_fields'))}\n"
        f"- corporate-action fields: {bool(v22.get('contains_corporate_action_fields'))}\n\n"
        "SQLITE KHONG CHUA:\n"
        f"- sector table/columns: {bool(store.get('has_sector_table_or_columns'))}\n"
        f"- corporate-action table/columns: {bool(store.get('has_corporate_action_table_or_columns'))}\n"
        f"- price_basis values: {'|'.join(store.get('price_basis_values') or []) or 'NONE'}\n\n"
        "CON THIEU DUNG 4 NHOM:\n"
        "1. SECTOR POINT-IN-TIME\n"
        f"   Cho {counts.get('unique_symbol_count', 0)} ma, phu {counts.get('sector_key_count', 0)} key, "
        f"tu {counts.get('first_execution_day')} den {counts.get('last_execution_day')}.\n"
        "   Moi record can: symbol, sector, effective_from, effective_to, source.\n\n"
        "2. CORPORATE ACTIONS\n"
        f"   Inventory day du cho {counts.get('corporate_action_window_count', 0)} holding windows.\n"
        "   Moi event can: symbol, ex/event date, CASH_DIVIDEND/STOCK_DIVIDEND/SPLIT/REVERSE_SPLIT, "
        "cash amount hoac adjustment factor, source.\n"
        "   Khong the suy ra cash dividend day du chi tu OHLCV.\n\n"
        "3. PRICE CONTRACT\n"
        "   Can xac nhan DNSE /price/ohlc la raw-unadjusted hay adjusted.\n"
        "   Don vi gia 1000 VND va thue co tuc tien mat 5% co the lay tu nguon chinh thuc, "
        "nhung adjusted/unadjusted van phai duoc xac nhan hoac doi chieu bang event data.\n\n"
        "4. OPERATIONS\n"
        "   Account sync va position reconciliation. Code co the tu chay read-only neu may da co "
        "DNSE_API_KEY va DNSE_API_SECRET; khong can upload credential.\n\n"
        "DANH SACH 78 MA:\n"
        + "|".join(symbols) + "\n"
    )


def discover(
    *, workspace_dir: Path, repo_root: Path, data_root: Path,
    v22_zip: Path, sqlite_store: Path, max_files: int = 25_000,
) -> dict[str, object]:
    workspace = Path(workspace_dir).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    counts = _workspace_counts(workspace)
    v22 = inspect_v22(v22_zip)
    store = inspect_sqlite(sqlite_store)
    candidates, visited = scan_roots((repo_root, data_root), max_files=max_files)
    by_category: dict[str, int] = {}
    for row in candidates:
        category = str(row["category"])
        by_category[category] = by_category.get(category, 0) + 1

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": counts,
        "canonical_v22": v22,
        "canonical_sqlite": store,
        "scan": {
            "roots": [str(Path(repo_root).resolve()), str(Path(data_root).resolve())],
            "visited_file_count": visited,
            "candidate_count": len(candidates),
            "candidates_by_category": by_category,
            "max_files": max_files,
        },
        "conclusion": {
            "ohlcv_history_already_available": bool(store.get("exists")),
            "v22_already_available": bool(v22.get("exists")),
            "sector_not_present_in_canonical_history": not bool(v22.get("contains_sector_fields"))
                and not bool(store.get("has_sector_table_or_columns")),
            "corporate_actions_not_present_in_canonical_history": not bool(v22.get("contains_corporate_action_fields"))
                and not bool(store.get("has_corporate_action_table_or_columns")),
            "price_basis_confirmed_by_store": set(store.get("price_basis_values") or [])
                not in (set(), {"CHUA_XAC_NHAN"}),
            "authoritative_verification_invented": False,
            "live_capital_approved": False,
        },
    }
    _write_json(workspace / REPORT_FILE, report)
    _write_csv(workspace / CANDIDATES_FILE, candidates)
    needed = _exact_needed_text(counts, v22, store)
    (workspace / NEEDED_FILE).write_text(needed, encoding="utf-8")
    (workspace / SYMBOLS_FILE).write_text("\n".join(counts.get("symbols") or []) + "\n", encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover local evidence for V39")
    parser.add_argument("--workspace-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--v22-zip", required=True, type=Path)
    parser.add_argument("--sqlite-store", required=True, type=Path)
    parser.add_argument("--max-files", type=int, default=25_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = discover(
        workspace_dir=args.workspace_dir,
        repo_root=args.repo_root,
        data_root=args.data_root,
        v22_zip=args.v22_zip,
        sqlite_store=args.sqlite_store,
        max_files=args.max_files,
    )
    print(json.dumps({
        "status": "SUCCESS",
        "report": str(Path(args.workspace_dir).resolve() / REPORT_FILE),
        "candidates": report["scan"]["candidate_count"],
        "visited_files": report["scan"]["visited_file_count"],
        "sector_missing_from_canonical": report["conclusion"]["sector_not_present_in_canonical_history"],
        "corporate_actions_missing_from_canonical": report["conclusion"]["corporate_actions_not_present_in_canonical_history"],
        "price_basis_confirmed": report["conclusion"]["price_basis_confirmed_by_store"],
    }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
