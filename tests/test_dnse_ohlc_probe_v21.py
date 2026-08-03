from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unittest

from he_thong_dinh_luong.dnse_ohlc_probe_v21 import probe_ohlc

VN_TZ = timezone(timedelta(hours=7))


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def json(self) -> object:
        return self.payload


class _Client:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = list(payloads)
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    def get(self, path: str, **kwargs: object) -> _Response:
        params = kwargs.get("params")
        if not isinstance(params, dict):
            raise AssertionError("params missing")
        self.calls.append((path, dict(params)))
        return _Response(self.payloads.pop(0))

    def close(self) -> None:
        self.closed = True


def _ts(day: date, hour: int = 0) -> int:
    return int(
        datetime(day.year, day.month, day.day, hour, tzinfo=VN_TZ).timestamp()
    )


class DnseOhlcProbeV21Tests(unittest.TestCase):
    def test_conflicting_duplicate_same_day_is_preserved_for_diagnosis(self) -> None:
        day = date(2022, 12, 27)
        client = _Client(
            [
                {
                    "t": [_ts(day), _ts(day, 13)],
                    "o": [10.0, 10.0],
                    "h": [11.0, 12.0],
                    "l": [9.0, 9.0],
                    "c": [10.5, 11.5],
                    "v": [1000, 2000],
                    "nextTime": 0,
                }
            ]
        )
        result = probe_ohlc(
            symbol="aaa",
            start=day,
            end=day,
            client=client,
        )
        self.assertEqual(result["status"], "CONFLICTING_DUPLICATE_DAY_FOUND")
        self.assertEqual(result["symbol"], "AAA")
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(len(result["conflicting_days"][day.isoformat()]), 2)
        text = str(result)
        self.assertNotIn("api-secret", text)
        self.assertFalse(result["credentials_recorded"])

    def test_identical_duplicate_is_distinguished_from_conflict(self) -> None:
        day = date(2022, 12, 27)
        client = _Client(
            [
                {
                    "t": [_ts(day), _ts(day, 13)],
                    "o": [10.0, 10.0],
                    "h": [11.0, 11.0],
                    "l": [9.0, 9.0],
                    "c": [10.5, 10.5],
                    "v": [1000, 1000],
                    "nextTime": 0,
                }
            ]
        )
        result = probe_ohlc(
            symbol="AAA",
            start=day,
            end=day,
            client=client,
        )
        self.assertEqual(result["status"], "IDENTICAL_DUPLICATE_DAY_FOUND")
        self.assertEqual(result["conflicting_days"], {})

    def test_probe_records_raw_and_normalized_pagination_cursor(self) -> None:
        first = date(2022, 12, 27)
        second = date(2022, 12, 28)
        raw_next = _ts(first, 13)
        client = _Client(
            [
                {
                    "t": [_ts(first)],
                    "o": [10.0],
                    "h": [11.0],
                    "l": [9.0],
                    "c": [10.5],
                    "v": [1000],
                    "nextTime": raw_next,
                },
                {
                    "t": [_ts(second)],
                    "o": [11.0],
                    "h": [12.0],
                    "l": [10.0],
                    "c": [11.5],
                    "v": [2000],
                    "nextTime": 0,
                },
            ]
        )
        result = probe_ohlc(
            symbol="AAA",
            start=first,
            end=second,
            client=client,
        )
        self.assertEqual(result["status"], "NO_DUPLICATE_DAY_FOUND")
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["pages"][0]["raw_next_time"], raw_next)
        self.assertEqual(
            result["pages"][0]["normalized_next_from"],
            _ts(second),
        )
        self.assertEqual(client.calls[1][1]["from"], _ts(second))


if __name__ == "__main__":
    unittest.main()
