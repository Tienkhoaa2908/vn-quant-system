from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.hnx_cross_market_validation_v41_fallback import (
    VnstockFreeSource,
    _date_value,
    _records,
    sync_vnstock_store,
)


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class FakeAsset:
    def __init__(self, rows):
        self.rows = rows

    def ohlcv(self, **kwargs):
        return FakeFrame(self.rows)


class FakeMarket:
    def __init__(self):
        self.rows = {
            "AAA": [
                {"time": "2024-01-02 07:00:00", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000},
                {"time": "2024-01-03 07:00:00", "open": 10.5, "high": 12, "low": 10, "close": 11.5, "volume": 1200},
            ],
            "HNXINDEX": [
                {"time": "2024-01-02", "open": 220, "high": 222, "low": 219, "close": 221, "volume": 1},
            ],
            "HNX30": [
                {"time": "2024-01-02", "open": 440, "high": 444, "low": 438, "close": 442, "volume": 1},
            ],
        }

    def equity(self, symbol):
        return FakeAsset(self.rows.get(symbol, []))

    def index(self, symbol):
        return FakeAsset(self.rows.get(symbol, []))


class V41FallbackTests(unittest.TestCase):
    def test_records_accepts_dataframe_like(self):
        self.assertEqual(_records(FakeFrame([{"x": 1}])), [{"x": 1}])

    def test_date_value_accepts_datetime_text(self):
        self.assertEqual(_date_value("2024-01-02 07:00:00"), date(2024, 1, 2))

    def test_fetch_maps_ohlcv(self):
        source = VnstockFreeSource(FakeMarket())
        rows = source.fetch("AAA", date(2024, 1, 1), date(2024, 1, 5))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].symbol, "AAA")
        self.assertEqual(rows[0].volume, 1000)

    def test_sync_writes_stock_and_index_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = VnstockFreeSource(FakeMarket())
            report = sync_vnstock_store(
                store_path=Path(tmp) / "hnx.sqlite3",
                symbols=["AAA"],
                start=date(2024, 1, 1),
                end=date(2024, 1, 5),
                source=source,
            )
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["inserted_row_count"], 4)
            self.assertEqual(set(report["index_symbols_with_data"]), {"HNXINDEX", "HNX30"})


if __name__ == "__main__":
    unittest.main()
