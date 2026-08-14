"""Resource-safe V68 workstation entrypoint.

V68 originally inherited three ``with sqlite3.connect(...)`` call paths.  A
sqlite3.Connection context manager manages commit/rollback but does not own the
lifetime of the file handle.  That is observable on Windows when temporary
SQLite variants are deleted immediately after research.

This module installs explicit-closing implementations for every SQLite path
used by the consolidated workstation run, then delegates all research logic to
``c3_hose_consolidated_v68``.  It does not change C3 semantics, universe
contracts, data gates, bootstrap logic, or research outputs.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Sequence

from . import c3_hose_consolidated_v68 as base
from . import c3_hose_native_v67 as core


def _safe_store_stock_symbols(store: Path) -> list[str]:
    uri = store.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        cols = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        if not {"symbol", "asset_type"}.issubset(cols):
            raise ValueError("V68_BARS_SYMBOL_ASSET_COLUMNS_MISSING")
        sql = (
            f"SELECT DISTINCT {base._q(cols['symbol'])} FROM bars "
            f"WHERE UPPER(COALESCE({base._q(cols['asset_type'])},''))='STOCK' ORDER BY 1"
        )
        return [str(row[0]).strip().upper() for row in db.execute(sql) if str(row[0] or "").strip()]


def _safe_create_diagnostic_store(source: Path, dest: Path, symbols: Sequence[str]) -> None:
    """Create a temporary variant and release both DB handles before returning."""
    wanted = {str(symbol).upper() for symbol in symbols}
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as src, closing(sqlite3.connect(dest)) as dst:
        cols = {str(r[1]).lower(): str(r[1]) for r in src.execute('PRAGMA table_info("bars")')}
        required = {"symbol", "day", "open", "close", "volume", "asset_type"}
        if not required.issubset(cols):
            raise ValueError("V68_BARS_REQUIRED_COLUMNS_MISSING")
        dst.execute(
            "CREATE TABLE bars(symbol TEXT, day TEXT, open REAL, close REAL, "
            "volume INTEGER, asset_type TEXT, exchange TEXT)"
        )
        selected = [cols[key] for key in ("symbol", "day", "open", "close", "volume", "asset_type")]
        sql = f"SELECT {','.join(base._q(col) for col in selected)} FROM bars ORDER BY {base._q(cols['day'])},{base._q(cols['symbol'])}"
        batch: list[tuple[object, ...]] = []
        for symbol, day, open_price, close_price, volume, asset_type in src.execute(sql):
            sym = str(symbol or "").strip().upper()
            asset = str(asset_type or "").strip().upper()
            is_index = asset == "INDEX" and sym in {"VNINDEX", "VN-INDEX", "VN_INDEX"}
            if not is_index and not (asset == "STOCK" and sym in wanted):
                continue
            batch.append((sym, day, open_price, close_price, volume, asset, "" if is_index else "HOSE_DIAGNOSTIC"))
            if len(batch) >= 10000:
                dst.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", batch)
                batch.clear()
        if batch:
            dst.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", batch)
        dst.execute("CREATE INDEX idx_v68_bars_symbol_day ON bars(symbol,day)")
        dst.commit()


def _safe_load_market(path: Path, *, price_multiplier: float) -> core.Market:
    """V67 market loader with explicit SQLite lifetime ownership."""
    with closing(sqlite3.connect(Path(path))) as db:
        db.row_factory = sqlite3.Row
        source = core.resolve_venue_source(db)
        intervals = core._membership_intervals(db, source)
        schema = core.inspect_schema(db)
        cols = schema["bars"]
        by_lower = {core._norm(col): col for col in cols}
        required = {"symbol", "day", "open", "close", "volume"}
        if not required.issubset(by_lower):
            raise ValueError("V67_BARS_REQUIRED_COLUMNS_MISSING")
        asset_col = by_lower.get("asset_type")
        select = [by_lower["symbol"], by_lower["day"], by_lower["open"], by_lower["close"], by_lower["volume"]]
        if asset_col:
            select.append(asset_col)
        if source.mode == "BAR_LEVEL":
            select.append(source.venue_col)
        sql = f"SELECT {','.join(core._quote(col) for col in select)} FROM bars ORDER BY day,symbol"
        index_open: dict = {}
        index_close: dict = {}
        stock_open: dict = {}
        stock_close: dict = {}
        stock_volume: dict = {}
        symbols: set[str] = set()
        for row in db.execute(sql):
            symbol = str(row[0] or "").strip().upper()
            day = core._date_or_none(row[1])
            if not symbol or day is None:
                continue
            try:
                open_price = float(row[2])
                close_price = float(row[3])
                volume = int(row[4])
            except (TypeError, ValueError):
                continue
            asset = str(row[5] or "").strip().upper() if asset_col else ""
            venue_index = 6 if asset_col and source.mode == "BAR_LEVEL" else 5 if source.mode == "BAR_LEVEL" else None
            bar_venue = row[venue_index] if venue_index is not None else None
            is_index = asset == "INDEX" or symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}
            if is_index and symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
                if open_price > 0 and close_price > 0:
                    index_open[day] = open_price
                    index_close[day] = close_price
                continue
            if asset_col and asset not in {"", "STOCK", "EQUITY"}:
                continue
            if not core._is_hose_at(symbol, day, source, intervals, bar_venue):
                continue
            if open_price <= 0 or close_price <= 0 or volume < 0:
                continue
            stock_open[(symbol, day)] = open_price * price_multiplier
            stock_close[(symbol, day)] = close_price * price_multiplier
            stock_volume[(symbol, day)] = volume
            symbols.add(symbol)
    if not index_close or not stock_close:
        raise ValueError("V67_STORE_REQUIRES_HOSE_STOCKS_AND_VNINDEX")
    calendar = tuple(sorted(index_close))
    return core.Market(
        calendar,
        index_open,
        index_close,
        stock_open,
        stock_close,
        stock_volume,
        tuple(sorted(symbols)),
        source,
    )


def install_resource_safe_sqlite_paths() -> None:
    """Install only lifetime fixes; research semantics stay in frozen V67/V68."""
    base._store_stock_symbols = _safe_store_stock_symbols
    base._create_diagnostic_store = _safe_create_diagnostic_store
    core.load_market = _safe_load_market


def run_consolidated(*args, **kwargs):
    install_resource_safe_sqlite_paths()
    return base.run_consolidated(*args, **kwargs)


def main(argv=None) -> int:
    install_resource_safe_sqlite_paths()
    return base.main(argv)


# Re-export the pure contract helper used by regression tests.
_variant_contract = base._variant_contract
CHAMPION_MODEL = base.CHAMPION_MODEL
SCHEMA_VERSION = base.SCHEMA_VERSION


if __name__ == "__main__":
    raise SystemExit(main())
