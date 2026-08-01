from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import eod_hang_ngay_cli as eod

VN_TZ = timezone(timedelta(hours=7))


def _timestamp(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=VN_TZ).timestamp())


def _intraday_timestamp(day: date, hour: int) -> int:
    return int(
        datetime(day.year, day.month, day.day, hour, tzinfo=VN_TZ).timestamp()
    )


def _payload(
    days: list[date],
    *,
    next_time: int = 0,
) -> dict[str, object]:
    count = len(days)
    return {
        "t": [_timestamp(day) for day in days],
        "o": [10.0 + index for index in range(count)],
        "h": [11.0 + index for index in range(count)],
        "l": [9.0 + index for index in range(count)],
        "c": [10.5 + index for index in range(count)],
        "v": [1000 + index for index in range(count)],
        "nextTime": next_time,
    }


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload


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


class TestNguonDnse(unittest.TestCase):
    def test_thieu_credential_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "DNSE_CREDENTIALS_MISSING"):
            eod.DnseRestSource("", "", version_reader=lambda _: "0.5.0")

    def test_khoa_phien_ban_sdk(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "DNSE_SDK_VERSION_MISMATCH"):
            eod.DnseRestSource("key", "secret", version_reader=lambda _: "0.4.0")

    def test_doc_stock_1d_va_khong_lo_secret(self) -> None:
        day = date(2026, 7, 30)
        client = _Client([_payload([day])])
        captured: dict[str, object] = {}

        def factory(key: str, secret: str, base_url: str, timeout: float) -> _Client:
            captured.update({
                "key": key,
                "secret": secret,
                "base_url": base_url,
                "timeout": timeout,
            })
            return client

        source = eod.DnseRestSource(
            "private-key",
            "private-secret",
            client_factory=factory,
            version_reader=lambda _: "0.5.0",
        )
        self.assertNotIn("private-key", repr(source))
        self.assertNotIn("private-secret", repr(source))
        rows = source.fetch("hpg", day, day)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].symbol, "HPG")
        self.assertEqual(rows[0].day, day)
        self.assertEqual(rows[0].source, "dnse_openapi")
        self.assertEqual(rows[0].volume, 1000)
        self.assertEqual(client.calls[0][0], "/price/ohlc")
        params = client.calls[0][1]
        self.assertEqual(params["type"], "STOCK")
        self.assertEqual(params["resolution"], "1D")
        self.assertEqual(params["symbol"], "HPG")
        self.assertEqual(captured["key"], "private-key")
        source.close()
        self.assertTrue(client.closed)

    def test_index_va_phan_trang_next_time(self) -> None:
        first = date(2026, 7, 29)
        second = date(2026, 7, 30)
        second_timestamp = _timestamp(second)
        client = _Client([
            _payload([first], next_time=second_timestamp),
            _payload([second]),
        ])
        source = eod.DnseRestSource(
            "key",
            "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        rows = source.fetch("VNINDEX", first, second, is_index=True)
        self.assertEqual([row.day for row in rows], [first, second])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0][1]["type"], "INDEX")
        self.assertEqual(client.calls[1][1]["from"], second_timestamp)

    def test_cursor_1d_duoc_day_sang_ngay_sau_nen_cuoi(self) -> None:
        first = date(2022, 12, 26)
        second = date(2022, 12, 27)
        third = date(2022, 12, 28)
        client = _Client([
            _payload(
                [first, second],
                next_time=_intraday_timestamp(second, 14),
            ),
            _payload([third]),
        ])
        source = eod.DnseRestSource(
            "key",
            "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        rows = source.fetch("AAA", first, third)
        self.assertEqual([row.day for row in rows], [first, second, third])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[1][1]["from"], _timestamp(third))

    def test_duplicate_bat_thuong_chon_timestamp_anchor_cua_cac_ngay_lan_can(self) -> None:
        first = date(2022, 12, 26)
        duplicate = date(2022, 12, 27)
        third = date(2022, 12, 28)
        payload = {
            "t": [
                _intraday_timestamp(first, 9),
                _intraday_timestamp(duplicate, 7),
                _intraday_timestamp(duplicate, 9),
                _intraday_timestamp(third, 9),
            ],
            "o": [6.62, 6.16, 6.19, 6.37],
            "h": [6.62, 6.26, 6.34, 6.41],
            "l": [6.14, 6.15, 6.16, 6.29],
            "c": [6.14, 6.19, 6.33, 6.37],
            "v": [1757100, 1196500, 1606700, 1152100],
            "nextTime": 0,
        }
        client = _Client([payload])
        source = eod.DnseRestSource(
            "key",
            "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        rows = source.fetch("AAA", first, third)
        self.assertEqual([row.day for row in rows], [first, duplicate, third])
        self.assertEqual(rows[1].close, 6.33)
        self.assertEqual(rows[1].volume, 1606700)
        self.assertEqual(source.last_fetch_diagnostics["duplicate_day_count"], 1)
        self.assertEqual(
            source.last_fetch_diagnostics["discarded_duplicate_record_count"],
            1,
        )
        page = source.last_fetch_diagnostics["pages"][0]
        self.assertEqual(page["canonical_anchor_local_time"], "09:00:00")

    def test_duplicate_xung_dot_khong_co_anchor_ro_rang_van_fail_closed(self) -> None:
        day = date(2022, 12, 27)
        payload = {
            "t": [
                _intraday_timestamp(day, 7),
                _intraday_timestamp(day, 9),
            ],
            "o": [6.16, 6.19],
            "h": [6.26, 6.34],
            "l": [6.15, 6.16],
            "c": [6.19, 6.33],
            "v": [1196500, 1606700],
            "nextTime": 0,
        }
        client = _Client([payload])
        source = eod.DnseRestSource(
            "key",
            "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        with self.assertRaisesRegex(
            ValueError,
            "DNSE_DUPLICATE_DAY_ANCHOR_AMBIGUOUS:AAA:2022-12-27",
        ):
            source.fetch("AAA", day, day)

    def test_cursor_dung_yen_dung_an_toan_va_giu_trang_hop_le(self) -> None:
        first = date(2026, 7, 29)
        second = date(2026, 7, 30)
        stalled = _timestamp(first)
        client = _Client([_payload([first, second], next_time=stalled)])
        source = eod.DnseRestSource(
            "key", "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        rows = source.fetch("BCG", first, second)
        self.assertEqual([row.day for row in rows], [first, second])
        self.assertEqual(len(client.calls), 1)

    def test_trang_chong_lan_giong_nhau_duoc_khu_trung(self) -> None:
        first = date(2026, 7, 29)
        second = date(2026, 7, 30)
        second_timestamp = _timestamp(second)
        duplicate = _payload([second])
        duplicate["o"] = [11.0]
        duplicate["h"] = [12.0]
        duplicate["l"] = [10.0]
        duplicate["c"] = [11.5]
        duplicate["v"] = [1001]
        client = _Client([
            _payload([first, second], next_time=second_timestamp),
            duplicate,
        ])
        source = eod.DnseRestSource(
            "key",
            "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        rows = source.fetch("ITA", first, second)
        self.assertEqual([row.day for row in rows], [first, second])
        self.assertEqual(len(client.calls), 1)

    def test_mang_ohlc_lech_do_dai_bi_chan(self) -> None:
        day = date(2026, 7, 30)
        payload = _payload([day])
        payload["v"] = []
        client = _Client([payload])
        source = eod.DnseRestSource(
            "key",
            "secret",
            client_factory=lambda *_: client,
            version_reader=lambda _: "0.5.0",
        )
        with self.assertRaisesRegex(ValueError, "ARRAY_LENGTH_MISMATCH"):
            source.fetch("HPG", day, day)

    def test_from_env_khong_can_truyen_secret_vao_cli(self) -> None:
        client = _Client([_payload([])])
        with patch.dict(os.environ, {
            "DNSE_API_KEY": "local-key",
            "DNSE_API_SECRET": "local-secret",
        }, clear=False):
            source = eod.DnseRestSource.from_env(
                client_factory=lambda *_: client,
                version_reader=lambda _: "0.5.0",
            )
        self.assertEqual(source.fetch("HPG", date(2026, 7, 30), date(2026, 7, 30)), ())


if __name__ == "__main__":
    unittest.main()
