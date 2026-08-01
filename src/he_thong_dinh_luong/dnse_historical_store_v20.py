"""Kho OHLCV lich su DNSE: backfill mot lan, sau do chi lay khoang chua co.

Module nay tach biet khoi web va API tai khoan. No chi dung market-data endpoint
``GET /price/ohlc`` thong qua ``DnseRestSource``. Credential chi doc tu bien moi
truong local va khong duoc ghi vao SQLite, JSON, CSV hay log.

Price basis cua OHLC DNSE chua duoc module nay tu khang dinh la adjusted hay
unadjusted. Vi vay san pham export mac dinh chi la input ky thuat cho den khi co
corporate-actions PIT hoac xac nhan adjusted-price contract.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Iterable, Mapping, Protocol, Sequence

from .eod_hang_ngay import EodRow

SCHEMA_VERSION = "dnse_historical_store_v20"
DEFAULT_START_DATE = date(2015, 6, 29)
DEFAULT_CHUNK_DAYS = 366
VN_TZ = timezone(timedelta(hours=7))
PRICE_BASIS = "CHUA_XAC_NHAN"
SOURCE_ENDPOINT = "/price/ohlc"
SOURCE_RESOLUTION = "1D"

STOCK_FIELDS = (
    "ma",
    "ngay",
    "gia_mo_cua",
    "gia_cao_nhat",
    "gia_thap_nhat",
    "gia_dong_cua",
    "khoi_luong",
    "nguon",
    "phien_ban",
    "co_so_gia",
)
BENCHMARK_FIELDS = (
    "ma",
    "ngay",
    "gia_dong_cua",
    "nguon",
    "phien_ban",
    "co_so_gia",
)


class HistoricalSource(Protocol):
    name: str
    version: str

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        is_index: bool = False,
    ) -> Sequence[EodRow]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class FetchRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("DNSE_STORE_FETCH_RANGE_INVALID")


@dataclass(frozen=True)
class ApplyResult:
    inserted: int
    existing_identical: int
    fetched_rows: int


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _csv_bytes(rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8-sig")


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _format_number(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else format(number, ".15g")


def _normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not symbol or not symbol.replace(".", "").replace("_", "").isalnum():
        raise ValueError(f"DNSE_STORE_SYMBOL_INVALID:{value}")
    return symbol


def _bar_tuple(row: EodRow) -> tuple[object, ...]:
    return (
        row.symbol,
        row.day.isoformat(),
        float(row.open),
        float(row.high) if row.high is not None else None,
        float(row.low) if row.low is not None else None,
        float(row.close),
        int(row.volume),
        row.source,
        row.version,
    )


def _bar_hash(row: EodRow) -> str:
    return _sha_bytes(_json_bytes(_bar_tuple(row)))


def _chunk_range(start: date, end: date, chunk_days: int) -> list[FetchRange]:
    if chunk_days <= 0:
        raise ValueError("DNSE_STORE_CHUNK_DAYS_INVALID")
    output: list[FetchRange] = []
    current = start
    while current <= end:
        chunk_end = min(end, current + timedelta(days=chunk_days - 1))
        output.append(FetchRange(current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return output


def _merge_ranges(ranges: Sequence[FetchRange]) -> list[FetchRange]:
    merged: list[FetchRange] = []
    for item in sorted(ranges, key=lambda value: (value.start, value.end)):
        if not merged or item.start > merged[-1].end + timedelta(days=1):
            merged.append(item)
            continue
        merged[-1] = FetchRange(merged[-1].start, max(merged[-1].end, item.end))
    return merged


def _subtract_covered(
    start: date,
    end: date,
    covered: Sequence[FetchRange],
) -> list[FetchRange]:
    clipped = [
        FetchRange(max(start, item.start), min(end, item.end))
        for item in covered
        if item.end >= start and item.start <= end
    ]
    merged = _merge_ranges(clipped)
    gaps: list[FetchRange] = []
    cursor = start
    for item in merged:
        if cursor < item.start:
            gaps.append(FetchRange(cursor, item.start - timedelta(days=1)))
        cursor = max(cursor, item.end + timedelta(days=1))
    if cursor <= end:
        gaps.append(FetchRange(cursor, end))
    return gaps


class DnseHistoricalStore:
    """SQLite store voi conflict detection va fetched-range coverage."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bars (
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    day TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    price_basis TEXT NOT NULL,
                    normalized_sha256 TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (asset_type, symbol, day)
                );
                CREATE TABLE IF NOT EXISTS fetched_ranges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    start_day TEXT NOT NULL,
                    end_day TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    returned_row_count INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_version TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS fetched_ranges_lookup
                    ON fetched_ranges(asset_type, symbol, start_day, end_day);
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    day TEXT NOT NULL,
                    existing_json TEXT NOT NULL,
                    incoming_json TEXT NOT NULL,
                    detected_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    requested_start TEXT NOT NULL,
                    requested_end TEXT NOT NULL,
                    symbol_count INTEGER NOT NULL,
                    fetched_range_count INTEGER NOT NULL DEFAULT 0,
                    inserted_row_count INTEGER NOT NULL DEFAULT 0,
                    existing_row_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                """
            )
            existing = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if existing is not None and existing["value"] != SCHEMA_VERSION:
                raise ValueError(
                    f"DNSE_STORE_SCHEMA_MISMATCH:{existing['value']}!={SCHEMA_VERSION}"
                )
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "source_endpoint": SOURCE_ENDPOINT,
                "source_resolution": SOURCE_RESOLUTION,
                "price_basis": PRICE_BASIS,
                "credentials_recorded": "false",
                "automatic_live_orders_allowed": "false",
                "live_capital_approved": "false",
            }
            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                sorted(metadata.items()),
            )

    def covered_ranges(self, asset_type: str, symbol: str) -> list[FetchRange]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT start_day, end_day
                FROM fetched_ranges
                WHERE asset_type = ? AND symbol = ?
                ORDER BY start_day, end_day
                """,
                (asset_type, symbol),
            ).fetchall()
        return _merge_ranges(
            [
                FetchRange(date.fromisoformat(row["start_day"]), date.fromisoformat(row["end_day"]))
                for row in rows
            ]
        )

    def uncovered_ranges(
        self,
        asset_type: str,
        symbol: str,
        start: date,
        end: date,
        *,
        chunk_days: int,
        force_refresh: bool = False,
    ) -> list[FetchRange]:
        base = [FetchRange(start, end)] if force_refresh else _subtract_covered(
            start,
            end,
            self.covered_ranges(asset_type, symbol),
        )
        output: list[FetchRange] = []
        for item in base:
            output.extend(_chunk_range(item.start, item.end, chunk_days))
        return output

    def begin_run(
        self,
        run_id: str,
        *,
        start: date,
        end: date,
        symbol_count: int,
        started_at: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_runs(
                    run_id, started_at, status, requested_start, requested_end,
                    symbol_count
                ) VALUES (?, ?, 'RUNNING', ?, ?, ?)
                """,
                (run_id, started_at, start.isoformat(), end.isoformat(), symbol_count),
            )

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: str,
        fetched_ranges: int,
        inserted: int,
        existing: int,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?, status = ?, fetched_range_count = ?,
                    inserted_row_count = ?, existing_row_count = ?, error = ?
                WHERE run_id = ?
                """,
                (
                    finished_at,
                    status,
                    fetched_ranges,
                    inserted,
                    existing,
                    error,
                    run_id,
                ),
            )

    def apply_fetch(
        self,
        *,
        asset_type: str,
        symbol: str,
        requested: FetchRange,
        rows: Sequence[EodRow],
        fetched_at: str,
        source_name: str,
        source_version: str,
    ) -> ApplyResult:
        normalized = sorted(rows, key=lambda row: row.day)
        seen_days: set[date] = set()
        for row in normalized:
            if row.symbol != symbol:
                raise ValueError("DNSE_STORE_FETCH_SYMBOL_MISMATCH")
            if not requested.start <= row.day <= requested.end:
                raise ValueError("DNSE_STORE_FETCH_DAY_OUTSIDE_REQUEST")
            if row.high is None or row.low is None:
                raise ValueError("DNSE_STORE_HIGH_LOW_REQUIRED")
            if row.day in seen_days:
                raise ValueError("DNSE_STORE_DUPLICATE_INCOMING_DAY")
            seen_days.add(row.day)

        to_insert: list[EodRow] = []
        existing_count = 0
        conflicts: list[tuple[EodRow, sqlite3.Row]] = []
        with self._connect() as connection:
            for row in normalized:
                current = connection.execute(
                    """
                    SELECT * FROM bars
                    WHERE asset_type = ? AND symbol = ? AND day = ?
                    """,
                    (asset_type, symbol, row.day.isoformat()),
                ).fetchone()
                if current is None:
                    to_insert.append(row)
                    continue
                incoming = (
                    float(row.open),
                    float(row.high),
                    float(row.low),
                    float(row.close),
                    int(row.volume),
                )
                stored = (
                    float(current["open"]),
                    float(current["high"]),
                    float(current["low"]),
                    float(current["close"]),
                    int(current["volume"]),
                )
                if incoming == stored:
                    existing_count += 1
                else:
                    conflicts.append((row, current))

        if conflicts:
            with self._connect() as connection:
                for row, current in conflicts:
                    existing_payload = {
                        key: current[key]
                        for key in ("open", "high", "low", "close", "volume", "source", "source_version")
                    }
                    incoming_payload = {
                        "open": row.open,
                        "high": row.high,
                        "low": row.low,
                        "close": row.close,
                        "volume": row.volume,
                        "source": row.source,
                        "source_version": row.version,
                    }
                    connection.execute(
                        """
                        INSERT INTO conflicts(
                            asset_type, symbol, day, existing_json,
                            incoming_json, detected_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            asset_type,
                            symbol,
                            row.day.isoformat(),
                            json.dumps(existing_payload, ensure_ascii=False, sort_keys=True),
                            json.dumps(incoming_payload, ensure_ascii=False, sort_keys=True),
                            fetched_at,
                        ),
                    )
            first = conflicts[0][0]
            raise ValueError(
                f"DNSE_STORE_HISTORICAL_CONFLICT:{asset_type}:{symbol}:{first.day}"
            )

        with self._connect() as connection:
            for row in to_insert:
                connection.execute(
                    """
                    INSERT INTO bars(
                        asset_type, symbol, day, open, high, low, close,
                        volume, source, source_version, price_basis,
                        normalized_sha256, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset_type,
                        symbol,
                        row.day.isoformat(),
                        float(row.open),
                        float(row.high),
                        float(row.low),
                        float(row.close),
                        int(row.volume),
                        row.source,
                        row.version,
                        PRICE_BASIS,
                        _bar_hash(row),
                        fetched_at,
                    ),
                )
            connection.execute(
                """
                INSERT INTO fetched_ranges(
                    asset_type, symbol, start_day, end_day, fetched_at,
                    returned_row_count, source, source_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_type,
                    symbol,
                    requested.start.isoformat(),
                    requested.end.isoformat(),
                    fetched_at,
                    len(normalized),
                    source_name,
                    source_version,
                ),
            )
        return ApplyResult(len(to_insert), existing_count, len(normalized))

    def bars(
        self,
        *,
        asset_type: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["asset_type = ?"]
        params: list[object] = [asset_type]
        if start is not None:
            clauses.append("day >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("day <= ?")
            params.append(end.isoformat())
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM bars WHERE {' AND '.join(clauses)} ORDER BY day, symbol",
                params,
            ).fetchall()

    def status(self) -> dict[str, object]:
        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT asset_type, COUNT(*) AS row_count,
                       COUNT(DISTINCT symbol) AS symbol_count,
                       MIN(day) AS first_day, MAX(day) AS last_day
                FROM bars GROUP BY asset_type ORDER BY asset_type
                """
            ).fetchall()
            conflicts = int(
                connection.execute("SELECT COUNT(*) AS value FROM conflicts").fetchone()["value"]
            )
            last_run = connection.execute(
                "SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "READY" if totals else "EMPTY",
            "store_path": str(self.path.resolve()),
            "price_basis": PRICE_BASIS,
            "research_eligible": False,
            "technical_validation_only": True,
            "conflict_count": conflicts,
            "coverage": [dict(row) for row in totals],
            "latest_sync_run": dict(last_run) if last_run is not None else None,
            "credentials_recorded": False,
            "automatic_live_orders_allowed": False,
            "live_capital_approved": False,
        }


def load_symbols(path: Path) -> tuple[str, ...]:
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        column = "ma" if "ma" in fields else "symbol" if "symbol" in fields else None
        if column is None:
            raise ValueError("DNSE_STORE_SYMBOL_FILE_REQUIRES_MA_OR_SYMBOL")
        symbols = tuple(
            dict.fromkeys(
                _normalize_symbol(str(row.get(column) or ""))
                for row in reader
                if str(row.get(column) or "").strip()
            )
        )
    if not symbols:
        raise ValueError("DNSE_STORE_SYMBOL_FILE_EMPTY")
    return symbols


def sync_historical_store(
    *,
    store_path: Path,
    symbols: Sequence[str],
    start: date,
    end: date,
    include_vnindex: bool = True,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
    force_refresh: bool = False,
    source: HistoricalSource | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    if start > end:
        raise ValueError("DNSE_STORE_DATE_RANGE_INVALID")
    normalized_symbols = tuple(
        symbol for symbol in dict.fromkeys(_normalize_symbol(value) for value in symbols)
        if symbol != "VNINDEX"
    )
    assets = [*(('INDEX', 'VNINDEX'),) if include_vnindex else (), *[("STOCK", value) for value in normalized_symbols]]
    if not assets:
        raise ValueError("DNSE_STORE_NO_ASSETS")

    store = DnseHistoricalStore(Path(store_path))
    current = now or datetime.now(VN_TZ)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("DNSE_STORE_NOW_TIMEZONE_REQUIRED")
    timestamp = current.astimezone(VN_TZ).isoformat()
    run_id = current.astimezone(VN_TZ).strftime("%Y%m%dT%H%M%S%f%z")
    store.begin_run(
        run_id,
        start=start,
        end=end,
        symbol_count=len(assets),
        started_at=timestamp,
    )

    close_source = source is None
    if source is None:
        from .nguon_dnse import DnseRestSource

        source = DnseRestSource.from_env()

    fetched_range_count = 0
    inserted = 0
    existing = 0
    details: list[dict[str, object]] = []
    try:
        for asset_type, symbol in assets:
            planned = store.uncovered_ranges(
                asset_type,
                symbol,
                start,
                end,
                chunk_days=chunk_days,
                force_refresh=force_refresh,
            )
            symbol_inserted = 0
            symbol_existing = 0
            symbol_fetched = 0
            for window in planned:
                fetched_rows = tuple(
                    source.fetch(
                        symbol,
                        window.start,
                        window.end,
                        is_index=asset_type == "INDEX",
                    )
                )
                applied = store.apply_fetch(
                    asset_type=asset_type,
                    symbol=symbol,
                    requested=window,
                    rows=fetched_rows,
                    fetched_at=timestamp,
                    source_name=str(source.name),
                    source_version=str(source.version),
                )
                fetched_range_count += 1
                inserted += applied.inserted
                existing += applied.existing_identical
                symbol_inserted += applied.inserted
                symbol_existing += applied.existing_identical
                symbol_fetched += applied.fetched_rows
            details.append(
                {
                    "asset_type": asset_type,
                    "symbol": symbol,
                    "planned_fetch_range_count": len(planned),
                    "fetched_row_count": symbol_fetched,
                    "inserted_row_count": symbol_inserted,
                    "existing_identical_row_count": symbol_existing,
                }
            )
    except Exception as exc:
        store.finish_run(
            run_id,
            status="FAILED",
            finished_at=datetime.now(VN_TZ).isoformat(),
            fetched_ranges=fetched_range_count,
            inserted=inserted,
            existing=existing,
            error=f"{type(exc).__name__}:{exc}",
        )
        raise
    finally:
        if close_source:
            source.close()

    store.finish_run(
        run_id,
        status="SUCCESS",
        finished_at=datetime.now(VN_TZ).isoformat(),
        fetched_ranges=fetched_range_count,
        inserted=inserted,
        existing=existing,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "store_path": str(Path(store_path).resolve()),
        "run_id": run_id,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "fetched_range_count": fetched_range_count,
        "inserted_row_count": inserted,
        "existing_identical_row_count": existing,
        "assets": details,
        "price_basis": PRICE_BASIS,
        "research_eligible": False,
        "technical_validation_only": True,
        "credentials_recorded": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }


def export_historical_store(
    *,
    store_path: Path,
    output_dir: Path,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, object]:
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"DNSE_STORE_EXPORT_EXISTS:{destination}")
    store = DnseHistoricalStore(Path(store_path))
    stock_rows = store.bars(asset_type="STOCK", start=start, end=end)
    index_rows = store.bars(asset_type="INDEX", start=start, end=end)
    if not stock_rows:
        raise ValueError("DNSE_STORE_EXPORT_STOCKS_EMPTY")
    if not index_rows:
        raise ValueError("DNSE_STORE_EXPORT_VNINDEX_EMPTY")

    stock_payload = _csv_bytes(
        (
            {
                "ma": row["symbol"],
                "ngay": row["day"],
                "gia_mo_cua": _format_number(row["open"]),
                "gia_cao_nhat": _format_number(row["high"]),
                "gia_thap_nhat": _format_number(row["low"]),
                "gia_dong_cua": _format_number(row["close"]),
                "khoi_luong": str(int(row["volume"])),
                "nguon": row["source"],
                "phien_ban": row["source_version"],
                "co_so_gia": row["price_basis"],
            }
            for row in stock_rows
        ),
        STOCK_FIELDS,
    )
    benchmark_payload = _csv_bytes(
        (
            {
                "ma": "VNINDEX",
                "ngay": row["day"],
                "gia_dong_cua": _format_number(row["close"]),
                "nguon": row["source"],
                "phien_ban": row["source_version"],
                "co_so_gia": row["price_basis"],
            }
            for row in index_rows
        ),
        BENCHMARK_FIELDS,
    )
    calendar_payload = _csv_bytes(
        ({"ngay": row["day"]} for row in index_rows),
        ("ngay",),
    )
    coverage = store.status()
    coverage.update(
        {
            "export_start": start.isoformat() if start else None,
            "export_end": end.isoformat() if end else None,
            "stock_export_row_count": len(stock_rows),
            "benchmark_export_row_count": len(index_rows),
            "required_next_contract": (
                "CONFIRM_ADJUSTED_PRICE_OR_SUPPLY_POINT_IN_TIME_CORPORATE_ACTIONS"
            ),
        }
    )
    coverage_payload = _json_bytes(coverage)
    files = {
        "ohlcv_stocks_dnse.csv": stock_payload,
        "vnindex_close_dnse.csv": benchmark_payload,
        "lich_vnindex_dnse.csv": calendar_payload,
        "coverage.json": coverage_payload,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "source_store": str(Path(store_path).resolve()),
        "source_endpoint": SOURCE_ENDPOINT,
        "source_resolution": SOURCE_RESOLUTION,
        "price_basis": PRICE_BASIS,
        "research_eligible": False,
        "technical_validation_only": True,
        "credentials_recorded": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
        "files": {
            name: {"sha256": _sha_bytes(payload), "size": len(payload)}
            for name, payload in files.items()
        },
    }
    files["manifest.json"] = _json_bytes(manifest)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        for name, payload in sorted(files.items()):
            (staging / name).write_bytes(payload)
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "output_dir": str(destination.resolve()),
        "stock_row_count": len(stock_rows),
        "benchmark_row_count": len(index_rows),
        "research_eligible": False,
        "technical_validation_only": True,
        "live_capital_approved": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.dnse_historical_store_v20"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync")
    sync.add_argument("--store", type=Path, required=True)
    sync.add_argument("--symbols-file", type=Path, required=True)
    sync.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START_DATE)
    sync.add_argument("--end", type=date.fromisoformat)
    sync.add_argument("--chunk-days", type=int, default=DEFAULT_CHUNK_DAYS)
    sync.add_argument("--without-vnindex", action="store_true")
    sync.add_argument("--force-refresh", action="store_true")
    sync.add_argument("--output-json", type=Path)

    status = sub.add_parser("status")
    status.add_argument("--store", type=Path, required=True)
    status.add_argument("--output-json", type=Path)

    export = sub.add_parser("export")
    export.add_argument("--store", type=Path, required=True)
    export.add_argument("--output-dir", type=Path, required=True)
    export.add_argument("--start", type=date.fromisoformat)
    export.add_argument("--end", type=date.fromisoformat)
    return parser


def _write_optional(path: Path | None, value: object) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "sync":
            end = args.end or datetime.now(VN_TZ).date()
            result = sync_historical_store(
                store_path=args.store,
                symbols=load_symbols(args.symbols_file),
                start=args.start,
                end=end,
                include_vnindex=not args.without_vnindex,
                chunk_days=args.chunk_days,
                force_refresh=args.force_refresh,
            )
            _write_optional(args.output_json, result)
        elif args.command == "status":
            result = DnseHistoricalStore(args.store).status()
            _write_optional(args.output_json, result)
        else:
            result = export_historical_store(
                store_path=args.store,
                output_dir=args.output_dir,
                start=args.start,
                end=args.end,
            )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_START_DATE",
    "DnseHistoricalStore",
    "FetchRange",
    "export_historical_store",
    "load_symbols",
    "sync_historical_store",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
