"""Incremental, conflict-safe DNSE OHLCV store.

Only the market-data endpoint is used. Account endpoints and the web terminal are
not dependencies. API credentials are read by ``DnseRestSource.from_env`` and
are never persisted.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import shutil
import sqlite3
from typing import TYPE_CHECKING, Iterable, Mapping, Protocol, Sequence

if TYPE_CHECKING:
    from .eod_hang_ngay import EodRow

SCHEMA_VERSION = "dnse_historical_store_v20"
DEFAULT_START_DATE = date(2015, 6, 29)
DEFAULT_CHUNK_DAYS = 366
VN_TZ = timezone(timedelta(hours=7))
PRICE_BASIS = "CHUA_XAC_NHAN"
SOURCE_ENDPOINT = "/price/ohlc"
SOURCE_RESOLUTION = "1D"

STOCK_FIELDS = (
    "ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat",
    "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia",
)
BENCHMARK_FIELDS = (
    "ma", "ngay", "gia_dong_cua", "nguon", "phien_ban", "co_so_gia",
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


def _csv_bytes(
    rows: Iterable[Mapping[str, object]], fields: Sequence[str]
) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(fields),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8-sig")


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _number(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else format(number, ".15g")


def _symbol(value: str) -> str:
    result = value.strip().upper()
    compact = result.replace(".", "").replace("_", "")
    if not compact or not compact.isalnum():
        raise ValueError(f"DNSE_STORE_SYMBOL_INVALID:{value}")
    return result


def _chunks(start: date, end: date, days: int) -> list[FetchRange]:
    if days <= 0:
        raise ValueError("DNSE_STORE_CHUNK_DAYS_INVALID")
    result: list[FetchRange] = []
    cursor = start
    while cursor <= end:
        last = min(end, cursor + timedelta(days=days - 1))
        result.append(FetchRange(cursor, last))
        cursor = last + timedelta(days=1)
    return result


def _merge(ranges: Sequence[FetchRange]) -> list[FetchRange]:
    result: list[FetchRange] = []
    for item in sorted(ranges, key=lambda value: (value.start, value.end)):
        if not result or item.start > result[-1].end + timedelta(days=1):
            result.append(item)
        else:
            result[-1] = FetchRange(
                result[-1].start,
                max(result[-1].end, item.end),
            )
    return result


def _missing(
    start: date,
    end: date,
    covered: Sequence[FetchRange],
) -> list[FetchRange]:
    relevant = [
        FetchRange(max(start, item.start), min(end, item.end))
        for item in covered
        if item.end >= start and item.start <= end
    ]
    result: list[FetchRange] = []
    cursor = start
    for item in _merge(relevant):
        if cursor < item.start:
            result.append(FetchRange(cursor, item.start - timedelta(days=1)))
        cursor = max(cursor, item.end + timedelta(days=1))
    if cursor <= end:
        result.append(FetchRange(cursor, end))
    return result


class DnseHistoricalStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 30000")
        return db

    def _init(self) -> None:
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bars(
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
                    PRIMARY KEY(asset_type, symbol, day)
                );
                CREATE TABLE IF NOT EXISTS fetched_ranges(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    start_day TEXT NOT NULL,
                    end_day TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    returned_rows INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conflicts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    day TEXT NOT NULL,
                    existing_json TEXT NOT NULL,
                    incoming_json TEXT NOT NULL,
                    detected_at TEXT NOT NULL
                );
                """
            )
            found = db.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            if found is not None and found["value"] != SCHEMA_VERSION:
                raise ValueError(
                    f"DNSE_STORE_SCHEMA_MISMATCH:{found['value']}"
                )
            values = {
                "schema_version": SCHEMA_VERSION,
                "source_endpoint": SOURCE_ENDPOINT,
                "source_resolution": SOURCE_RESOLUTION,
                "price_basis": PRICE_BASIS,
                "credentials_recorded": "false",
            }
            db.executemany(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)",
                sorted(values.items()),
            )

    def covered(self, asset_type: str, symbol: str) -> list[FetchRange]:
        with self._db() as db:
            rows = db.execute(
                """
                SELECT start_day,end_day
                FROM fetched_ranges
                WHERE asset_type=? AND symbol=?
                ORDER BY start_day,end_day
                """,
                (asset_type, symbol),
            ).fetchall()
        return _merge(
            [
                FetchRange(
                    date.fromisoformat(row["start_day"]),
                    date.fromisoformat(row["end_day"]),
                )
                for row in rows
            ]
        )

    def plan(
        self,
        asset_type: str,
        symbol: str,
        start: date,
        end: date,
        *,
        chunk_days: int,
        force: bool,
    ) -> list[FetchRange]:
        base = (
            [FetchRange(start, end)]
            if force
            else _missing(start, end, self.covered(asset_type, symbol))
        )
        return [
            chunk
            for item in base
            for chunk in _chunks(item.start, item.end, chunk_days)
        ]

    def apply(
        self,
        asset_type: str,
        symbol: str,
        window: FetchRange,
        rows: Sequence[EodRow],
        *,
        fetched_at: str,
        source_name: str,
        source_version: str,
    ) -> tuple[int, int]:
        ordered = sorted(rows, key=lambda row: row.day)
        seen: set[date] = set()
        for row in ordered:
            if row.symbol != symbol or not window.start <= row.day <= window.end:
                raise ValueError(
                    "DNSE_STORE_FETCH_IDENTITY_OR_RANGE_INVALID"
                )
            if row.high is None or row.low is None or row.day in seen:
                raise ValueError("DNSE_STORE_FETCH_BAR_INVALID")
            seen.add(row.day)

        inserts: list[EodRow] = []
        identical = 0
        conflicts: list[tuple[EodRow, sqlite3.Row]] = []
        with self._db() as db:
            for row in ordered:
                current = db.execute(
                    """
                    SELECT * FROM bars
                    WHERE asset_type=? AND symbol=? AND day=?
                    """,
                    (asset_type, symbol, row.day.isoformat()),
                ).fetchone()
                if current is None:
                    inserts.append(row)
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
                    identical += 1
                else:
                    conflicts.append((row, current))

        if conflicts:
            with self._db() as db:
                for row, current in conflicts:
                    existing = {
                        key: current[key]
                        for key in ("open", "high", "low", "close", "volume")
                    }
                    incoming = {
                        "open": row.open,
                        "high": row.high,
                        "low": row.low,
                        "close": row.close,
                        "volume": row.volume,
                    }
                    db.execute(
                        """
                        INSERT INTO conflicts(
                            asset_type,symbol,day,existing_json,
                            incoming_json,detected_at
                        ) VALUES (?,?,?,?,?,?)
                        """,
                        (
                            asset_type,
                            symbol,
                            row.day.isoformat(),
                            json.dumps(existing, sort_keys=True),
                            json.dumps(incoming, sort_keys=True),
                            fetched_at,
                        ),
                    )
            raise ValueError(
                f"DNSE_STORE_HISTORICAL_CONFLICT:"
                f"{symbol}:{conflicts[0][0].day}"
            )

        with self._db() as db:
            for row in inserts:
                normalized = (
                    row.symbol,
                    row.day.isoformat(),
                    row.open,
                    row.high,
                    row.low,
                    row.close,
                    row.volume,
                )
                db.execute(
                    "INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                        _sha(_json_bytes(normalized)),
                        fetched_at,
                    ),
                )
            db.execute(
                """
                INSERT INTO fetched_ranges(
                    asset_type,symbol,start_day,end_day,fetched_at,
                    returned_rows,source,source_version
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    asset_type,
                    symbol,
                    window.start.isoformat(),
                    window.end.isoformat(),
                    fetched_at,
                    len(ordered),
                    source_name,
                    source_version,
                ),
            )
        return len(inserts), identical

    def rows(
        self,
        asset_type: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[sqlite3.Row]:
        where = ["asset_type=?"]
        params: list[object] = [asset_type]
        if start:
            where.append("day>=?")
            params.append(start.isoformat())
        if end:
            where.append("day<=?")
            params.append(end.isoformat())
        with self._db() as db:
            return db.execute(
                f"SELECT * FROM bars WHERE {' AND '.join(where)} "
                "ORDER BY day,symbol",
                params,
            ).fetchall()

    def status(self) -> dict[str, object]:
        with self._db() as db:
            coverage = [
                dict(row)
                for row in db.execute(
                    """
                    SELECT asset_type,
                           COUNT(*) row_count,
                           COUNT(DISTINCT symbol) symbol_count,
                           MIN(day) first_day,
                           MAX(day) last_day
                    FROM bars
                    GROUP BY asset_type
                    ORDER BY asset_type
                    """
                ).fetchall()
            ]
            conflicts = int(
                db.execute("SELECT COUNT(*) n FROM conflicts").fetchone()["n"]
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "READY" if coverage else "EMPTY",
            "store_path": str(self.path.resolve()),
            "coverage": coverage,
            "conflict_count": conflicts,
            "price_basis": PRICE_BASIS,
            "research_eligible": False,
            "technical_validation_only": True,
            "credentials_recorded": False,
            "automatic_live_orders_allowed": False,
            "live_capital_approved": False,
        }


def load_symbols(path: Path) -> tuple[str, ...]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        column = (
            "ma"
            if "ma" in fields
            else "symbol"
            if "symbol" in fields
            else None
        )
        if column is None:
            raise ValueError("DNSE_STORE_SYMBOL_FILE_REQUIRES_MA_OR_SYMBOL")
        result = tuple(
            dict.fromkeys(
                _symbol(str(row.get(column) or ""))
                for row in reader
                if str(row.get(column) or "").strip()
            )
        )
    if not result:
        raise ValueError("DNSE_STORE_SYMBOL_FILE_EMPTY")
    return result


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
    assets: list[tuple[str, str]] = []
    if include_vnindex:
        assets.append(("INDEX", "VNINDEX"))
    assets.extend(
        ("STOCK", symbol)
        for symbol in dict.fromkeys(_symbol(value) for value in symbols)
        if symbol != "VNINDEX"
    )
    if not assets:
        raise ValueError("DNSE_STORE_NO_ASSETS")

    current = now or datetime.now(VN_TZ)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("DNSE_STORE_NOW_TIMEZONE_REQUIRED")
    timestamp = current.astimezone(VN_TZ).isoformat()
    store = DnseHistoricalStore(store_path)
    own_source = source is None
    if source is None:
        from .nguon_dnse import DnseRestSource

        source = DnseRestSource.from_env()

    inserted = 0
    identical = 0
    requests = 0
    details: list[dict[str, object]] = []
    try:
        for asset_type, symbol in assets:
            planned = store.plan(
                asset_type,
                symbol,
                start,
                end,
                chunk_days=chunk_days,
                force=force_refresh,
            )
            symbol_inserted = 0
            symbol_identical = 0
            for window in planned:
                rows = source.fetch(
                    symbol,
                    window.start,
                    window.end,
                    is_index=asset_type == "INDEX",
                )
                added, same = store.apply(
                    asset_type,
                    symbol,
                    window,
                    rows,
                    fetched_at=timestamp,
                    source_name=source.name,
                    source_version=source.version,
                )
                requests += 1
                inserted += added
                identical += same
                symbol_inserted += added
                symbol_identical += same
            details.append(
                {
                    "asset_type": asset_type,
                    "symbol": symbol,
                    "api_range_count": len(planned),
                    "inserted": symbol_inserted,
                    "existing_identical": symbol_identical,
                }
            )
    finally:
        if own_source:
            source.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "store_path": str(Path(store_path).resolve()),
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "api_range_count": requests,
        "inserted_row_count": inserted,
        "existing_identical_row_count": identical,
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
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"DNSE_STORE_EXPORT_EXISTS:{output}")
    store = DnseHistoricalStore(store_path)
    stocks = store.rows("STOCK", start, end)
    index = store.rows("INDEX", start, end)
    if not stocks or not index:
        raise ValueError("DNSE_STORE_EXPORT_REQUIRES_STOCKS_AND_VNINDEX")

    files = {
        "ohlcv_stocks_dnse.csv": _csv_bytes(
            (
                {
                    "ma": row["symbol"],
                    "ngay": row["day"],
                    "gia_mo_cua": _number(row["open"]),
                    "gia_cao_nhat": _number(row["high"]),
                    "gia_thap_nhat": _number(row["low"]),
                    "gia_dong_cua": _number(row["close"]),
                    "khoi_luong": str(int(row["volume"])),
                    "nguon": row["source"],
                    "phien_ban": row["source_version"],
                    "co_so_gia": row["price_basis"],
                }
                for row in stocks
            ),
            STOCK_FIELDS,
        ),
        "vnindex_close_dnse.csv": _csv_bytes(
            (
                {
                    "ma": "VNINDEX",
                    "ngay": row["day"],
                    "gia_dong_cua": _number(row["close"]),
                    "nguon": row["source"],
                    "phien_ban": row["source_version"],
                    "co_so_gia": row["price_basis"],
                }
                for row in index
            ),
            BENCHMARK_FIELDS,
        ),
        "lich_vnindex_dnse.csv": _csv_bytes(
            ({"ngay": row["day"]} for row in index),
            ("ngay",),
        ),
        "coverage.json": _json_bytes(store.status()),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "source_endpoint": SOURCE_ENDPOINT,
        "source_resolution": SOURCE_RESOLUTION,
        "price_basis": PRICE_BASIS,
        "research_eligible": False,
        "technical_validation_only": True,
        "credentials_recorded": False,
        "files": {
            name: {"sha256": _sha(payload), "size": len(payload)}
            for name, payload in files.items()
        },
    }
    files["manifest.json"] = _json_bytes(manifest)

    staging = output.with_name(f".{output.name}.staging")
    output.parent.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        for name, payload in sorted(files.items()):
            (staging / name).write_bytes(payload)
        staging.replace(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "output_dir": str(output.resolve()),
        "stock_rows": len(stocks),
        "benchmark_rows": len(index),
        "research_eligible": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.dnse_historical_store_v20"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync")
    sync.add_argument("--store", type=Path, required=True)
    sync.add_argument("--symbols-file", type=Path, required=True)
    sync.add_argument(
        "--start",
        type=date.fromisoformat,
        default=DEFAULT_START_DATE,
    )
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "sync":
            result = sync_historical_store(
                store_path=args.store,
                symbols=load_symbols(args.symbols_file),
                start=args.start,
                end=args.end or datetime.now(VN_TZ).date(),
                include_vnindex=not args.without_vnindex,
                chunk_days=args.chunk_days,
                force_refresh=args.force_refresh,
            )
            if args.output_json:
                args.output_json.parent.mkdir(parents=True, exist_ok=True)
                args.output_json.write_bytes(_json_bytes(result))
        elif args.command == "status":
            result = DnseHistoricalStore(args.store).status()
            if args.output_json:
                args.output_json.parent.mkdir(parents=True, exist_ok=True)
                args.output_json.write_bytes(_json_bytes(result))
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
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
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
