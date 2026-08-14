"""Probe historical market-data coverage before a costly deep backfill.

The probe is deliberately independent from DNSE account/portfolio APIs.  KBS
and VCI can be checked without brokerage credentials.  DNSE OpenAPI is optional
and is only used when explicitly requested and local API-key credentials exist.
No credential value is written to output.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from .eod_hang_ngay import EodRow, VnstockSource
from .nguon_dnse import DnseRestSource

SCHEMA_VERSION = "historical_source_probe_v19"
DEFAULT_SYMBOLS = ("VNINDEX", "VCB", "MBB", "FPT")


class ProbeSource(Protocol):
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


SourceFactory = Callable[[str], object]


def _month_count(rows: Sequence[EodRow]) -> int:
    return len({(row.day.year, row.day.month) for row in rows})


def _probe_one(
    source: object,
    *,
    provider: str,
    symbol: str,
    start: date,
    end: date,
) -> dict[str, object]:
    try:
        if isinstance(source, DnseRestSource):
            rows = tuple(source.fetch(symbol, start, end))
        else:
            rows = tuple(
                source.fetch(
                    symbol,
                    start,
                    end,
                    is_index=symbol == "VNINDEX",
                )
            )
    except Exception as exc:
        return {
            "provider": provider,
            "symbol": symbol,
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "row_count": 0,
            "monthly_coverage_count": 0,
            "first_date": None,
            "last_date": None,
            "covers_requested_start": False,
            "covers_requested_end": False,
        }
    ordered = sorted(rows, key=lambda row: row.day)
    first = ordered[0].day if ordered else None
    last = ordered[-1].day if ordered else None
    return {
        "provider": provider,
        "symbol": symbol,
        "status": "SUCCESS" if ordered else "EMPTY",
        "source_name": str(getattr(source, "name", provider)),
        "source_version": str(getattr(source, "version", "")),
        "row_count": len(ordered),
        "monthly_coverage_count": _month_count(ordered),
        "first_date": first.isoformat() if first else None,
        "last_date": last.isoformat() if last else None,
        "covers_requested_start": bool(first and first <= start),
        "covers_requested_end": bool(last and last >= end),
    }


def probe_sources(
    *,
    providers: Sequence[str],
    symbols: Sequence[str],
    start: date,
    end: date,
    source_factory: SourceFactory | None = None,
) -> dict[str, object]:
    """Return deterministic coverage facts without persisting raw market data."""
    if start >= end:
        raise ValueError("HISTORICAL_SOURCE_PROBE_DATE_RANGE_INVALID")
    normalized_providers = tuple(
        dict.fromkeys(value.strip().lower() for value in providers if value.strip())
    )
    normalized_symbols = tuple(
        dict.fromkeys(value.strip().upper() for value in symbols if value.strip())
    )
    if not normalized_providers or not normalized_symbols:
        raise ValueError("HISTORICAL_SOURCE_PROBE_EMPTY_SELECTION")
    unsupported = sorted(set(normalized_providers) - {"kbs", "vci", "dnse"})
    if unsupported:
        raise ValueError(
            "HISTORICAL_SOURCE_PROBE_PROVIDER_UNSUPPORTED:"
            + "|".join(unsupported)
        )

    def default_factory(provider: str) -> object:
        if provider in {"kbs", "vci"}:
            return VnstockSource(provider)
        return DnseRestSource.from_env()

    factory = source_factory or default_factory
    rows: list[dict[str, object]] = []
    for provider in normalized_providers:
        try:
            source = factory(provider)
        except Exception as exc:
            for symbol in normalized_symbols:
                rows.append({
                    "provider": provider,
                    "symbol": symbol,
                    "status": "SOURCE_INIT_FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                    "row_count": 0,
                    "monthly_coverage_count": 0,
                    "first_date": None,
                    "last_date": None,
                    "covers_requested_start": False,
                    "covers_requested_end": False,
                })
            continue
        try:
            for symbol in normalized_symbols:
                rows.append(
                    _probe_one(
                        source,
                        provider=provider,
                        symbol=symbol,
                        start=start,
                        end=end,
                    )
                )
        finally:
            close = getattr(source, "close", None)
            if callable(close):
                close()

    provider_summary: dict[str, object] = {}
    for provider in normalized_providers:
        selected = [row for row in rows if row["provider"] == provider]
        full = [
            row
            for row in selected
            if row.get("status") == "SUCCESS"
            and row.get("covers_requested_start") is True
            and row.get("covers_requested_end") is True
        ]
        provider_summary[provider] = {
            "symbols_requested": len(selected),
            "symbols_with_full_requested_coverage": len(full),
            "all_symbols_have_full_requested_coverage": len(full) == len(selected),
        }

    ready = any(
        isinstance(value, Mapping)
        and value.get("all_symbols_have_full_requested_coverage") is True
        for value in provider_summary.values()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SOURCE_FOUND" if ready else "NO_SOURCE_WITH_FULL_PROBE_COVERAGE",
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "providers": list(normalized_providers),
        "symbols": list(normalized_symbols),
        "provider_summary": provider_summary,
        "results": rows,
        "dnse_account_api_used": False,
        "credentials_recorded": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.historical_source_probe_v19"
    )
    parser.add_argument("--providers", default="kbs,vci")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    providers = tuple(
        value.strip() for value in str(args.providers).split(",") if value.strip()
    )
    symbols = tuple(
        value.strip() for value in str(args.symbols).split(",") if value.strip()
    )
    try:
        result = probe_sources(
            providers=providers,
            symbols=symbols,
            start=args.start,
            end=args.end,
        )
        _write_json(args.output_json, result)
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
    return 0 if result.get("status") == "SOURCE_FOUND" else 2


__all__ = ["SCHEMA_VERSION", "probe_sources", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
