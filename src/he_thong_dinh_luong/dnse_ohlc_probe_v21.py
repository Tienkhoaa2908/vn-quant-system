"""Probe read-only de chan doan payload OHLC trung ngay tu DNSE OpenAPI.

Credential chi doc tu environment va khong duoc ghi vao output. Module nay
khong ghi vao historical store, khong goi API tai khoan va khong dat lenh.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from importlib import metadata
import json
import os
from pathlib import Path
from typing import Any, Protocol

DNSE_SDK_VERSION = "0.5.0"
DNSE_BASE_URL = "https://openapi.dnse.com.vn"
DNSE_ENDPOINT = "/price/ohlc"
DNSE_RESOLUTION = "1D"
VN_TZ = timezone(timedelta(hours=7))
UTC = timezone.utc
DEFAULT_MAX_PAGES = 20
SCHEMA_VERSION = "dnse_ohlc_probe_v21"


class _JsonResponse(Protocol):
    def json(self) -> object: ...


class _Client(Protocol):
    def get(self, path: str, **kwargs: Any) -> _JsonResponse: ...
    def close(self) -> None: ...


def _epoch_start(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=VN_TZ).timestamp())


def _epoch_end(day: date) -> int:
    return int(
        (
            datetime.combine(day + timedelta(days=1), time.min, tzinfo=VN_TZ)
            - timedelta(seconds=1)
        ).timestamp()
    )


def _integer(value: object, code: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(code)
    number = float(value)
    if not number.is_integer() or number < minimum:
        raise ValueError(code)
    return int(number)


def _array(payload: Mapping[str, object], name: str) -> list[object]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise ValueError(f"DNSE_PROBE_ARRAY_MISSING:{name}")
    return value


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _client_from_env() -> _Client:
    api_key = os.environ.get("DNSE_API_KEY", "").strip()
    api_secret = os.environ.get("DNSE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise ValueError("DNSE_CREDENTIALS_MISSING")
    try:
        from dnse import DnseClient
    except ImportError as exc:
        raise RuntimeError(f"DNSE_SDK_NOT_INSTALLED:{DNSE_SDK_VERSION}") from exc
    version = metadata.version("dnse")
    if version != DNSE_SDK_VERSION:
        raise RuntimeError(
            f"DNSE_SDK_VERSION_MISMATCH:{version}!={DNSE_SDK_VERSION}"
        )
    return DnseClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url=DNSE_BASE_URL,
        timeout=30.0,
    )


def probe_ohlc(
    *,
    symbol: str,
    start: date,
    end: date,
    asset_type: str = "STOCK",
    max_pages: int = DEFAULT_MAX_PAGES,
    client: _Client | None = None,
) -> dict[str, object]:
    normalized_symbol = symbol.strip().upper()
    normalized_type = asset_type.strip().upper()
    if not normalized_symbol:
        raise ValueError("DNSE_PROBE_SYMBOL_INVALID")
    if normalized_type not in {"STOCK", "INDEX"}:
        raise ValueError("DNSE_PROBE_ASSET_TYPE_INVALID")
    if start > end:
        raise ValueError("DNSE_PROBE_DATE_RANGE_INVALID")
    if max_pages <= 0:
        raise ValueError("DNSE_PROBE_MAX_PAGES_INVALID")

    own_client = client is None
    if client is None:
        client = _client_from_env()

    current_from = _epoch_start(start)
    final_to = _epoch_end(end)
    seen_cursors = {current_from}
    pages: list[dict[str, object]] = []
    records: list[dict[str, object]] = []

    try:
        for page_index in range(max_pages):
            request_params = {
                "symbol": normalized_symbol,
                "type": normalized_type,
                "resolution": DNSE_RESOLUTION,
                "from": current_from,
                "to": final_to,
            }
            response = client.get(DNSE_ENDPOINT, params=request_params)
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("DNSE_PROBE_RESPONSE_INVALID")

            arrays = {
                name: _array(payload, name)
                for name in ("t", "o", "h", "l", "c", "v")
            }
            lengths = {len(values) for values in arrays.values()}
            if len(lengths) != 1:
                raise ValueError("DNSE_PROBE_ARRAY_LENGTH_MISMATCH")

            page_records: list[dict[str, object]] = []
            for record_index in range(next(iter(lengths), 0)):
                timestamp = _integer(
                    arrays["t"][record_index],
                    "DNSE_PROBE_TIMESTAMP_INVALID",
                    minimum=1,
                )
                utc_dt = datetime.fromtimestamp(timestamp, tz=UTC)
                vn_dt = datetime.fromtimestamp(timestamp, tz=VN_TZ)
                record = {
                    "page_index": page_index,
                    "record_index": record_index,
                    "timestamp": timestamp,
                    "utc_datetime": utc_dt.isoformat(),
                    "vn_datetime": vn_dt.isoformat(),
                    "vn_day": vn_dt.date().isoformat(),
                    "open": arrays["o"][record_index],
                    "high": arrays["h"][record_index],
                    "low": arrays["l"][record_index],
                    "close": arrays["c"][record_index],
                    "volume": arrays["v"][record_index],
                }
                page_records.append(record)
                records.append(record)

            raw_next = payload.get("nextTime", 0)
            if raw_next is None:
                raw_next = 0
            next_time = _integer(
                raw_next,
                "DNSE_PROBE_NEXT_TIME_INVALID",
                minimum=0,
            )
            proposed_next_from = next_time
            if page_records:
                last_day = max(
                    date.fromisoformat(str(item["vn_day"]))
                    for item in page_records
                )
                proposed_next_from = max(
                    proposed_next_from,
                    _epoch_start(last_day + timedelta(days=1)),
                )

            pages.append(
                {
                    "page_index": page_index,
                    "request": request_params,
                    "record_count": len(page_records),
                    "raw_next_time": next_time,
                    "raw_next_utc_datetime": (
                        datetime.fromtimestamp(next_time, tz=UTC).isoformat()
                        if next_time
                        else None
                    ),
                    "raw_next_vn_datetime": (
                        datetime.fromtimestamp(next_time, tz=VN_TZ).isoformat()
                        if next_time
                        else None
                    ),
                    "normalized_next_from": proposed_next_from,
                    "records": page_records,
                }
            )

            if next_time == 0 or proposed_next_from > final_to:
                break
            if proposed_next_from <= current_from or proposed_next_from in seen_cursors:
                break
            seen_cursors.add(proposed_next_from)
            current_from = proposed_next_from
        else:
            raise ValueError("DNSE_PROBE_PAGINATION_LIMIT_EXCEEDED")
    finally:
        if own_client:
            client.close()

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[str(record["vn_day"])].append(record)
    duplicate_days = {
        day: items
        for day, items in sorted(grouped.items())
        if len(items) > 1
    }
    conflicting_days = {
        day: items
        for day, items in duplicate_days.items()
        if len(
            {
                (
                    json.dumps(item["open"], sort_keys=True),
                    json.dumps(item["high"], sort_keys=True),
                    json.dumps(item["low"], sort_keys=True),
                    json.dumps(item["close"], sort_keys=True),
                    json.dumps(item["volume"], sort_keys=True),
                )
                for item in items
            }
        )
        > 1
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "CONFLICTING_DUPLICATE_DAY_FOUND"
            if conflicting_days
            else "IDENTICAL_DUPLICATE_DAY_FOUND"
            if duplicate_days
            else "NO_DUPLICATE_DAY_FOUND"
        ),
        "endpoint": DNSE_ENDPOINT,
        "resolution": DNSE_RESOLUTION,
        "symbol": normalized_symbol,
        "asset_type": normalized_type,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "page_count": len(pages),
        "record_count": len(records),
        "duplicate_days": duplicate_days,
        "conflicting_days": conflicting_days,
        "pages": pages,
        "credentials_recorded": False,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.dnse_ohlc_probe_v21"
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--asset-type",
        choices=("STOCK", "INDEX"),
        default="STOCK",
    )
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_ohlc(
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            asset_type=args.asset_type,
            max_pages=args.max_pages,
        )
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_bytes(_json_bytes(result))
    except Exception as exc:
        failure = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "credentials_recorded": False,
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_bytes(_json_bytes(failure))
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
