from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.dnse_historical_store_v20 import (
    DnseHistoricalStore,
    export_historical_store,
    sync_historical_store,
)
from he_thong_dinh_luong.eod_hang_ngay import EodRow

VN_TZ = timezone(timedelta(hours=7))


class _FakeSource:
    name = "dnse_openapi"
    version = "0.5.0"

    def __init__(self, values: dict[tuple[str, date], float] | None = None) -> None:
        self.values = dict(values or {})
        self.calls: list[tuple[str, date, date, bool]] = []
        self.closed = False

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        is_index: bool = False,
    ) -> tuple[EodRow, ...]:
        self.calls.append((symbol, start, end, is_index))
        rows = []
        for (row_symbol, day), close in sorted(self.values.items()):
            if row_symbol == symbol and start <= day <= end:
                rows.append(
                    EodRow(
                        symbol=symbol,
                        day=day,
                        open=close - 0.5,
                        high=close + 1.0,
                        low=close - 1.0,
                        close=close,
                        volume=1000,
                        source=self.name,
                        version=self.version,
                    )
                )
        return tuple(rows)

    def close(self) -> None:
        self.closed = True


class DnseHistoricalStoreV20Tests(unittest.TestCase):
    def test_second_sync_only_requests_uncovered_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "dnse.sqlite3"
            first_source = _FakeSource({
                ("VNINDEX", date(2026, 1, 2)): 1200.0,
                ("AAA", date(2026, 1, 2)): 10.0,
            })
            first = sync_historical_store(
                store_path=store,
                symbols=("AAA",),
                start=date(2026, 1, 1),
                end=date(2026, 1, 3),
                source=first_source,
                now=datetime(2026, 1, 3, 18, tzinfo=VN_TZ),
            )
            self.assertEqual(first["api_range_count"], 2)

            second_source = _FakeSource({
                ("VNINDEX", date(2026, 1, 5)): 1210.0,
                ("AAA", date(2026, 1, 5)): 11.0,
            })
            second = sync_historical_store(
                store_path=store,
                symbols=("AAA",),
                start=date(2026, 1, 1),
                end=date(2026, 1, 5),
                source=second_source,
                now=datetime(2026, 1, 5, 18, tzinfo=VN_TZ),
            )
            self.assertEqual(second["api_range_count"], 2)
            self.assertEqual(
                [(call[1], call[2]) for call in second_source.calls],
                [(date(2026, 1, 4), date(2026, 1, 5))] * 2,
            )
            status = DnseHistoricalStore(store).status()
            self.assertEqual(status["conflict_count"], 0)
            self.assertFalse(status["credentials_recorded"])

    def test_successful_empty_range_is_not_fetched_again(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "dnse.sqlite3"
            first_source = _FakeSource()
            sync_historical_store(
                store_path=store,
                symbols=("NEW",),
                start=date(2015, 1, 1),
                end=date(2015, 12, 31),
                include_vnindex=False,
                source=first_source,
                now=datetime(2026, 1, 1, tzinfo=VN_TZ),
            )
            self.assertEqual(len(first_source.calls), 1)

            second_source = _FakeSource()
            result = sync_historical_store(
                store_path=store,
                symbols=("NEW",),
                start=date(2015, 1, 1),
                end=date(2015, 12, 31),
                include_vnindex=False,
                source=second_source,
                now=datetime(2026, 1, 2, tzinfo=VN_TZ),
            )
            self.assertEqual(result["api_range_count"], 0)
            self.assertEqual(second_source.calls, [])

    def test_conflicting_historical_revision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store_path = Path(temp) / "dnse.sqlite3"
            day = date(2026, 1, 2)
            sync_historical_store(
                store_path=store_path,
                symbols=("AAA",),
                start=day,
                end=day,
                include_vnindex=False,
                source=_FakeSource({("AAA", day): 10.0}),
                now=datetime(2026, 1, 3, tzinfo=VN_TZ),
            )
            with self.assertRaisesRegex(ValueError, "DNSE_STORE_HISTORICAL_CONFLICT"):
                sync_historical_store(
                    store_path=store_path,
                    symbols=("AAA",),
                    start=day,
                    end=day,
                    include_vnindex=False,
                    force_refresh=True,
                    source=_FakeSource({("AAA", day): 99.0}),
                    now=datetime(2026, 1, 4, tzinfo=VN_TZ),
                )
            store = DnseHistoricalStore(store_path)
            self.assertEqual(float(store.rows("STOCK")[0]["close"]), 10.0)
            self.assertEqual(store.status()["conflict_count"], 1)

    def test_export_matches_model_input_contract_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "dnse.sqlite3"
            day = date(2026, 1, 2)
            sync_historical_store(
                store_path=store,
                symbols=("AAA",),
                start=day,
                end=day,
                source=_FakeSource({
                    ("VNINDEX", day): 1200.0,
                    ("AAA", day): 10.0,
                }),
                now=datetime(2026, 1, 3, tzinfo=VN_TZ),
            )
            output = root / "export"
            result = export_historical_store(
                store_path=store,
                output_dir=output,
            )
            self.assertEqual(result["stock_rows"], 1)
            self.assertEqual(result["benchmark_rows"], 1)
            self.assertTrue((output / "ohlcv_stocks_dnse.csv").is_file())
            self.assertTrue((output / "vnindex_close_dnse.csv").is_file())
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertFalse(manifest["research_eligible"])
            self.assertEqual(manifest["source_endpoint"], "/price/ohlc")
            self.assertFalse(manifest["credentials_recorded"])


if __name__ == "__main__":
    unittest.main()
