from __future__ import annotations

from datetime import date, timedelta
import unittest

from he_thong_dinh_luong.eod_hang_ngay import EodRow
from he_thong_dinh_luong.historical_source_probe_v19 import probe_sources


class _FakeSource:
    def __init__(self, name: str, start: date, end: date) -> None:
        self.name = name
        self.version = "test"
        self._start = start
        self._end = end
        self.closed = False

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        is_index: bool = False,
    ) -> tuple[EodRow, ...]:
        days = []
        day = self._start
        while day <= self._end:
            days.append(day)
            day += timedelta(days=31)
        if not days or days[-1] != self._end:
            days.append(self._end)
        return tuple(
            EodRow(
                symbol=symbol,
                day=value,
                open=10.0,
                high=10.5,
                low=9.5,
                close=10.0,
                volume=1000,
                source=self.name,
                version=self.version,
            )
            for value in sorted(set(days))
        )

    def close(self) -> None:
        self.closed = True


class HistoricalSourceProbeV19Tests(unittest.TestCase):
    def test_one_provider_with_full_coverage_is_enough(self) -> None:
        start = date(2015, 7, 31)
        end = date(2026, 7, 31)
        created: dict[str, _FakeSource] = {}

        def factory(provider: str) -> _FakeSource:
            source = (
                _FakeSource(provider, start, end)
                if provider == "kbs"
                else _FakeSource(provider, date(2020, 1, 1), end)
            )
            created[provider] = source
            return source

        result = probe_sources(
            providers=("kbs", "vci"),
            symbols=("VNINDEX", "VCB"),
            start=start,
            end=end,
            source_factory=factory,
        )
        self.assertEqual(result["status"], "SOURCE_FOUND")
        self.assertTrue(
            result["provider_summary"]["kbs"][
                "all_symbols_have_full_requested_coverage"
            ]
        )
        self.assertFalse(
            result["provider_summary"]["vci"][
                "all_symbols_have_full_requested_coverage"
            ]
        )
        self.assertTrue(created["kbs"].closed)
        self.assertTrue(created["vci"].closed)
        self.assertFalse(result["dnse_account_api_used"])
        self.assertFalse(result["credentials_recorded"])

    def test_missing_credentials_is_reported_without_crashing_other_sources(self) -> None:
        start = date(2015, 7, 31)
        end = date(2026, 7, 31)

        def factory(provider: str) -> _FakeSource:
            if provider == "dnse":
                raise ValueError("DNSE_CREDENTIALS_MISSING")
            return _FakeSource(provider, start, end)

        result = probe_sources(
            providers=("kbs", "dnse"),
            symbols=("VNINDEX",),
            start=start,
            end=end,
            source_factory=factory,
        )
        self.assertEqual(result["status"], "SOURCE_FOUND")
        dnse = next(row for row in result["results"] if row["provider"] == "dnse")
        self.assertEqual(dnse["status"], "SOURCE_INIT_FAILED")
        self.assertIn("DNSE_CREDENTIALS_MISSING", dnse["error"])

    def test_invalid_range_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "DATE_RANGE_INVALID"):
            probe_sources(
                providers=("kbs",),
                symbols=("VCB",),
                start=date(2026, 1, 1),
                end=date(2026, 1, 1),
                source_factory=lambda _: _FakeSource(
                    "kbs", date(2026, 1, 1), date(2026, 1, 2)
                ),
            )


if __name__ == "__main__":
    unittest.main()
