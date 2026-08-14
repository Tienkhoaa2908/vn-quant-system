"""Credential-free Vnstock fallback for V41 HNX cross-market validation.

This module is used only when DNSE market-data credentials are unavailable.
It stores Vnstock Free OHLCV in the same immutable SQLite schema, marks the
source explicitly, and delegates evaluation to the frozen V41 engine. It never
upgrades the result to strict/live eligibility.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from importlib import metadata
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .eod_hang_ngay import EodRow
from .dnse_historical_store_v20 import DnseHistoricalStore
from . import hnx_cross_market_validation_v41 as v41

SCHEMA_VERSION = "hnx_cross_market_validation_v41_vnstock_fallback"
VNSTOCK_MAX_DAILY_HISTORY_DAYS = 8 * 366
INDEX_SYMBOLS = ("HNXINDEX", "HNX30")


def _records(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            raw = value.to_dict("records")
            if isinstance(raw, list):
                return [dict(row) for row in raw if isinstance(row, Mapping)]
        except Exception:
            pass
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _market_class():
    errors: list[str] = []
    for module_name, attr in (
        ("vnstock.ui", "Market"),
        ("vnstock", "Market"),
        ("vnstock_data", "Market"),
    ):
        try:
            module = __import__(module_name, fromlist=[attr])
            return getattr(module, attr), module_name
        except Exception as exc:
            errors.append(f"{module_name}.{attr}:{type(exc).__name__}")
    raise RuntimeError("V41_VNSTOCK_MARKET_IMPORT_FAILED:" + "|".join(errors))


def _date_value(value: object) -> date:
    if hasattr(value, "date") and callable(getattr(value, "date")):
        try:
            result = value.date()
            if isinstance(result, date):
                return result
        except Exception:
            pass
    text = str(value or "").strip()
    if not text:
        raise ValueError("V41_VNSTOCK_DATE_MISSING")
    return date.fromisoformat(text[:10])


def _number(row: Mapping[str, object], names: Sequence[str], code: str) -> float:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            number = float(value)
            if math.isfinite(number) and number > 0.0:
                return number
    raise ValueError(code)


def _volume(row: Mapping[str, object]) -> int:
    for name in ("volume", "match_volume", "total_volume", "khoi_luong"):
        value = row.get(name)
        if value not in (None, ""):
            number = float(value)
            if math.isfinite(number) and number >= 0.0:
                return int(round(number))
    return 0


class VnstockFreeSource:
    name = "vnstock_free_unified_ui"

    def __init__(self, market: object | None = None) -> None:
        if market is None:
            cls, import_source = _market_class()
            market = cls()
            self.import_source = import_source
        else:
            self.import_source = type(market).__module__
        self.market = market
        try:
            self.version = metadata.version("vnstock")
        except metadata.PackageNotFoundError:
            self.version = "unknown"

    def _asset(self, symbol: str, is_index: bool) -> object:
        factory = getattr(self.market, "index" if is_index else "equity", None)
        if not callable(factory):
            raise RuntimeError("V41_VNSTOCK_MARKET_FACTORY_MISSING")
        return factory(symbol)

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        is_index: bool = False,
    ) -> Sequence[EodRow]:
        asset = self._asset(symbol, is_index)
        getter = getattr(asset, "ohlcv", None)
        if not callable(getter):
            raise RuntimeError(f"V41_VNSTOCK_OHLCV_MISSING:{symbol}")
        kwargs = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "interval": "1D",
        }
        try:
            raw = getter(**kwargs)
        except TypeError:
            kwargs.pop("interval")
            raw = getter(**kwargs)
        rows: list[EodRow] = []
        for record in _records(raw):
            day_raw = next(
                (
                    record.get(name)
                    for name in ("time", "date", "trading_date", "day", "ngay")
                    if record.get(name) not in (None, "")
                ),
                None,
            )
            day = _date_value(day_raw)
            if not start <= day <= end:
                continue
            rows.append(
                EodRow(
                    symbol=symbol,
                    day=day,
                    open=_number(record, ("open", "open_price", "gia_mo_cua"), "V41_VNSTOCK_OPEN_INVALID"),
                    high=_number(record, ("high", "high_price", "gia_cao_nhat"), "V41_VNSTOCK_HIGH_INVALID"),
                    low=_number(record, ("low", "low_price", "gia_thap_nhat"), "V41_VNSTOCK_LOW_INVALID"),
                    close=_number(record, ("close", "close_price", "gia_dong_cua"), "V41_VNSTOCK_CLOSE_INVALID"),
                    volume=_volume(record),
                    source=self.name,
                    version=self.version,
                )
            )
        unique = {(row.day, row.open, row.high, row.low, row.close, row.volume): row for row in rows}
        return tuple(sorted(unique.values(), key=lambda row: row.day))

    def close(self) -> None:
        return None


def sync_vnstock_store(
    *,
    store_path: Path,
    symbols: Sequence[str],
    start: date,
    end: date,
    source: VnstockFreeSource | None = None,
) -> dict[str, object]:
    source_start = max(start, end - timedelta(days=VNSTOCK_MAX_DAILY_HISTORY_DAYS))
    store = DnseHistoricalStore(store_path)
    own_source = source is None
    source = source or VnstockFreeSource()
    details: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    inserted = 0
    try:
        for asset_type, symbol in [
            *(("STOCK", value) for value in symbols),
            *(("INDEX", value) for value in INDEX_SYMBOLS),
        ]:
            windows = store.plan(
                asset_type,
                symbol,
                source_start,
                end,
                chunk_days=VNSTOCK_MAX_DAILY_HISTORY_DAYS,
                force=False,
            )
            for window in windows:
                try:
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
                        fetched_at=datetime.now(v41.VN_TZ).isoformat(),
                        source_name=source.name,
                        source_version=source.version,
                    )
                    inserted += added
                    details.append(
                        {
                            "asset_type": asset_type,
                            "symbol": symbol,
                            "start": window.start.isoformat(),
                            "end": window.end.isoformat(),
                            "returned": len(rows),
                            "inserted": added,
                            "existing_identical": same,
                        }
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "asset_type": asset_type,
                            "symbol": symbol,
                            "error": f"{type(exc).__name__}:{str(exc)[:220]}",
                        }
                    )
    finally:
        if own_source:
            source.close()
    coverage = store.status()
    index_symbols = [
        str(row.get("symbol"))
        for row in details
        if row.get("asset_type") == "INDEX" and int(row.get("returned", 0)) > 0
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS_WITH_ERRORS" if errors else "SUCCESS",
        "data_source": source.name,
        "source_version": source.version,
        "source_import": source.import_source,
        "requested_start": start.isoformat(),
        "effective_start_due_to_free_history_limit": source_start.isoformat(),
        "requested_end": end.isoformat(),
        "inserted_row_count": inserted,
        "detail_count": len(details),
        "error_count": len(errors),
        "errors": errors,
        "index_symbols_with_data": sorted(set(index_symbols)),
        "coverage": coverage,
        "strict_source": False,
        "secondary_research_source": True,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.hnx_cross_market_validation_v41_fallback"
    )
    parser.add_argument("--v22-input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2015, 6, 29))
    parser.add_argument("--end", type=date.fromisoformat, default=datetime.now(v41.VN_TZ).date())
    parser.add_argument("--universe-size", type=int, default=v41.DEFAULT_UNIVERSE_SIZE)
    parser.add_argument("--top-k", type=int, default=v41.DEFAULT_TOP_K)
    parser.add_argument("--price-multiplier", type=float, default=v41.DEFAULT_PRICE_MULTIPLIER)
    parser.add_argument("--initial-capital", type=int, default=v41.DEFAULT_INITIAL_CAPITAL)
    parser.add_argument("--max-adv-share", type=float, default=v41.DEFAULT_MAX_ADV_SHARE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        symbol_rows, discovery = v41.discover_hnx_symbols()
        symbol_names = [str(row["symbol"]) for row in symbol_rows]
        sync_audit = sync_vnstock_store(
            store_path=args.store,
            symbols=symbol_names,
            start=args.start,
            end=args.end,
        )
        sync_audit["discovery"] = discovery
        report = v41.run_v41(
            v22_input_zip=args.v22_input_zip,
            store_path=args.store,
            output_dir=args.output_dir,
            symbol_rows=symbol_rows,
            sync_audit=sync_audit,
            universe_size=args.universe_size,
            top_k=args.top_k,
            price_multiplier=args.price_multiplier,
            initial_capital=args.initial_capital,
            max_adv_share=args.max_adv_share,
            strict_instrument_history_complete=False,
        )
        v41.package_output(args.output_dir, args.output_zip)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "data_source": sync_audit["data_source"],
                    "performance_gate_passed": report["gate"]["performance_gate_passed"],
                    "strict_gate_passed": False,
                    "output_zip": str(args.output_zip.resolve()),
                    "live_capital_approved": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        v41._write_json(
            args.output_dir.with_name(args.output_dir.name + "-fallback-failure.json"),
            failure,
        )
        print(json.dumps(failure, ensure_ascii=True, sort_keys=True))
        return 2


__all__ = [
    "VnstockFreeSource",
    "sync_vnstock_store",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
