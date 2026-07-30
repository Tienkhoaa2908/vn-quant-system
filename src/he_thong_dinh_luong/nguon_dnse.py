"""Nguon OHLC EOD tu DNSE OpenAPI, doc credential chi tu moi truong local."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from importlib import metadata
import os
from typing import Any, Protocol

from .eod_hang_ngay import EodRow

DNSE_SDK_VERSION = "0.5.0"
DNSE_BASE_URL = "https://openapi.dnse.com.vn"
DNSE_RESOLUTION = "1D"
VN_TZ = timezone(timedelta(hours=7))
MAX_PAGES = 100


class _JsonResponse(Protocol):
    def json(self) -> object: ...


class _DnseClient(Protocol):
    def get(self, path: str, **kwargs: Any) -> _JsonResponse: ...
    def close(self) -> None: ...


ClientFactory = Callable[[str, str, str, float], _DnseClient]
VersionReader = Callable[[str], str]


def _default_client_factory(
    api_key: str,
    api_secret: str,
    base_url: str,
    timeout: float,
) -> _DnseClient:
    try:
        from dnse import DnseClient
    except ImportError as exc:
        raise RuntimeError(f"DNSE_SDK_NOT_INSTALLED:{DNSE_SDK_VERSION}") from exc
    return DnseClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url=base_url,
        timeout=timeout,
    )


def _epoch_start(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=VN_TZ).timestamp())


def _epoch_end(day: date) -> int:
    return int(
        (datetime.combine(day + timedelta(days=1), time.min, tzinfo=VN_TZ)
         - timedelta(seconds=1)).timestamp()
    )


def _numeric(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(code)
    result = float(value)
    if result <= 0:
        raise ValueError(code)
    return result


def _volume(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("DNSE_VOLUME_INVALID")
    result = float(value)
    if result < 0 or not result.is_integer():
        raise ValueError("DNSE_VOLUME_INVALID")
    return int(result)


def _array(payload: Mapping[str, object], name: str) -> Sequence[object]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise ValueError(f"DNSE_OHLC_ARRAY_MISSING:{name}")
    return value


def _parse_page(
    *,
    payload: object,
    symbol: str,
    source: str,
    version: str,
) -> tuple[tuple[EodRow, ...], int]:
    if not isinstance(payload, Mapping):
        raise ValueError("DNSE_OHLC_RESPONSE_INVALID")
    arrays = {name: _array(payload, name) for name in ("t", "o", "h", "l", "c", "v")}
    lengths = {len(values) for values in arrays.values()}
    if len(lengths) != 1:
        raise ValueError("DNSE_OHLC_ARRAY_LENGTH_MISMATCH")

    rows: list[EodRow] = []
    for index in range(next(iter(lengths), 0)):
        timestamp = arrays["t"][index]
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("DNSE_TIMESTAMP_INVALID")
        timestamp_float = float(timestamp)
        if not timestamp_float.is_integer() or timestamp_float <= 0:
            raise ValueError("DNSE_TIMESTAMP_INVALID")
        day = datetime.fromtimestamp(int(timestamp_float), tz=VN_TZ).date()
        rows.append(EodRow(
            symbol=symbol,
            day=day,
            open=_numeric(arrays["o"][index], "DNSE_OPEN_INVALID"),
            high=_numeric(arrays["h"][index], "DNSE_HIGH_INVALID"),
            low=_numeric(arrays["l"][index], "DNSE_LOW_INVALID"),
            close=_numeric(arrays["c"][index], "DNSE_CLOSE_INVALID"),
            volume=_volume(arrays["v"][index]),
            source=source,
            version=version,
        ))

    raw_next = payload.get("nextTime", 0)
    if raw_next is None:
        raw_next = 0
    if isinstance(raw_next, bool) or not isinstance(raw_next, (int, float)):
        raise ValueError("DNSE_NEXT_TIME_INVALID")
    next_float = float(raw_next)
    if not next_float.is_integer() or next_float < 0:
        raise ValueError("DNSE_NEXT_TIME_INVALID")
    return tuple(rows), int(next_float)


class DnseRestSource:
    """Adapter EOD DNSE dung SDK chinh thuc ``dnse==0.5.0``."""

    name = "dnse_openapi"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str = DNSE_BASE_URL,
        timeout: float = 30.0,
        client_factory: ClientFactory = _default_client_factory,
        version_reader: VersionReader = metadata.version,
    ) -> None:
        if not api_key.strip() or not api_secret.strip():
            raise ValueError("DNSE_CREDENTIALS_MISSING")
        if timeout <= 0:
            raise ValueError("DNSE_TIMEOUT_INVALID")
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout)
        self._client_factory = client_factory
        self._client_instance: _DnseClient | None = None
        self.version = version_reader("dnse")
        if self.version != DNSE_SDK_VERSION:
            raise RuntimeError(
                f"DNSE_SDK_VERSION_MISMATCH:{self.version}!={DNSE_SDK_VERSION}"
            )

    @classmethod
    def from_env(cls, **kwargs: object) -> "DnseRestSource":
        return cls(
            os.environ.get("DNSE_API_KEY", ""),
            os.environ.get("DNSE_API_SECRET", ""),
            **kwargs,
        )

    def __repr__(self) -> str:
        return f"DnseRestSource(name={self.name!r}, version={self.version!r})"

    def _client(self) -> _DnseClient:
        if self._client_instance is None:
            self._client_instance = self._client_factory(
                self._api_key,
                self._api_secret,
                self._base_url,
                self._timeout,
            )
        return self._client_instance

    def close(self) -> None:
        if self._client_instance is not None:
            self._client_instance.close()
            self._client_instance = None

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        is_index: bool = False,
    ) -> Sequence[EodRow]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("DNSE_SYMBOL_INVALID")
        if start > end:
            raise ValueError("DNSE_DATE_RANGE_INVALID")

        current_from = _epoch_start(start)
        final_to = _epoch_end(end)
        rows: list[EodRow] = []
        for _ in range(MAX_PAGES):
            response = self._client().get(
                "/price/ohlc",
                params={
                    "symbol": symbol,
                    "type": "INDEX" if is_index else "STOCK",
                    "resolution": DNSE_RESOLUTION,
                    "from": current_from,
                    "to": final_to,
                },
            )
            page_rows, next_time = _parse_page(
                payload=response.json(),
                symbol=symbol,
                source=self.name,
                version=self.version,
            )
            rows.extend(row for row in page_rows if start <= row.day <= end)
            if next_time == 0 or next_time > final_to:
                break
            if next_time <= current_from:
                raise ValueError("DNSE_PAGINATION_NOT_MONOTONIC")
            current_from = next_time
        else:
            raise ValueError("DNSE_PAGINATION_LIMIT_EXCEEDED")

        keys = [(row.symbol, row.day) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError(f"DNSE_DUPLICATE_DAY:{symbol}")
        return tuple(sorted(rows, key=lambda row: row.day))
