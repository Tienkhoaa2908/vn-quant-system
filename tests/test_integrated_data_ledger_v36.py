from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import integrated_data_ledger_v36 as v36


class IntegratedDataLedgerV36Tests(unittest.TestCase):
    def test_rebuild_cap3_matches_v11_retention_rule(self) -> None:
        symbols = [f"S{i:02d}" for i in range(1, 14)]
        rows = []
        for rank, symbol in enumerate(symbols, start=1):
            rows.append(
                {"test_date": "2024-01-31", "symbol": symbol, "rank": rank}
            )
        second = [
            "S11",
            "S12",
            "S13",
            "S01",
            "S02",
            "S03",
            "S04",
            "S05",
            "S06",
            "S07",
            "S08",
            "S09",
            "S10",
        ]
        for rank, symbol in enumerate(second, start=1):
            rows.append(
                {"test_date": "2024-02-29", "symbol": symbol, "rank": rank}
            )
        rebuilt = v36.rebuild_cap3_selections(
            rows,
            ["2024-01-31", "2024-02-29"],
        )
        self.assertEqual(rebuilt[0]["selected_symbols"], symbols[:10])
        self.assertEqual(
            rebuilt[1]["selected_symbols"],
            [
                "S01",
                "S02",
                "S03",
                "S04",
                "S05",
                "S06",
                "S07",
                "S11",
                "S12",
                "S13",
            ],
        )
        self.assertEqual(rebuilt[1]["voluntary_replacement_count"], 3)

    def test_invalid_ohlcv_rows_are_exportable_and_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bars.sqlite3"
            connection = sqlite3.connect(db)
            connection.execute(
                "CREATE TABLE bars(day TEXT, symbol TEXT, open REAL, "
                "high REAL, low REAL, close REAL, volume REAL)"
            )
            connection.executemany(
                "INSERT INTO bars VALUES(?,?,?,?,?,?,?)",
                [
                    ("2024-01-01", "AAA", 10, 11, 9, 10.5, 1000),
                    ("2024-01-02", "AAA", 0, 11, 9, 10, 1000),
                    ("2024-01-03", "AAA", 10, 9, 8, 10, 1000),
                ],
            )
            connection.commit()
            connection.close()
            resolved = {
                name: name
                for name in (
                    "day",
                    "symbol",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                )
            }
            rows = v36.extract_invalid_ohlcv(db, resolved)
            self.assertEqual(len(rows), 2)
            categories = {row["category"] for row in rows}
            self.assertIn("PARTIAL_NONPOSITIVE_PRICE", categories)
            self.assertIn("OHLC_RANGE_INCONSISTENT", categories)
            self.assertTrue(all(row["quarantine_required"] for row in rows))
            self.assertTrue(
                all(not row["automatic_correction_allowed"] for row in rows)
            )

    def test_constrained_inverse_volatility_respects_caps(self) -> None:
        symbols = [f"S{i:02d}" for i in range(10)]
        vol = {
            symbol: 0.01 + index * 0.001
            for index, symbol in enumerate(symbols)
        }
        sectors = {
            symbol: f"SEC{index // 2}"
            for index, symbol in enumerate(symbols)
        }
        weights = v36.constrained_inverse_vol_weights(
            symbols,
            vol,
            sectors,
            1.0,
        )
        self.assertLessEqual(sum(weights.values()), 1.0 + 1e-9)
        self.assertGreater(sum(weights.values()), 0.99)
        self.assertTrue(
            all(value <= 0.15 + 1e-9 for value in weights.values())
        )
        for sector in set(sectors.values()):
            total = sum(
                weights[symbol]
                for symbol in symbols
                if sectors[symbol] == sector
            )
            self.assertLessEqual(total, 0.25 + 1e-9)

    def test_exact_ledger_runs_base_stress_and_liquidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "bars.sqlite3"
            connection = sqlite3.connect(db)
            connection.execute(
                "CREATE TABLE bars(day TEXT, symbol TEXT, open REAL, "
                "high REAL, low REAL, close REAL, volume REAL)"
            )
            start = date(2024, 1, 1)
            days = [
                (start + timedelta(days=index)).isoformat()
                for index in range(110)
            ]
            symbols = [f"S{i:02d}" for i in range(10)]
            rows = []
            for symbol_index, symbol in enumerate(symbols):
                for day_index, day in enumerate(days):
                    price = (
                        10.0
                        + symbol_index * 0.3
                        + day_index * (0.005 + symbol_index * 0.0001)
                    )
                    rows.append(
                        (
                            day,
                            symbol,
                            price,
                            price * 1.01,
                            price * 0.99,
                            price * 1.001,
                            100000,
                        )
                    )
            connection.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", rows)
            connection.commit()
            connection.close()

            sector = root / "sector.csv"
            with sector.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "symbol",
                        "sector",
                        "effective_from",
                        "effective_to",
                    ],
                )
                writer.writeheader()
                for index, symbol in enumerate(symbols):
                    writer.writerow(
                        {
                            "symbol": symbol,
                            "sector": f"SEC{index // 2}",
                            "effective_from": "2020-01-01",
                            "effective_to": "",
                        }
                    )
            actions = root / "actions.csv"
            with actions.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "source_event_id",
                        "symbol",
                        "event_date",
                        "event_type",
                        "adjustment_factor",
                        "cash_amount_vnd",
                    ],
                )
                writer.writeheader()

            selections = [
                {"signal_date": days[70], "selected_symbols": symbols},
                {"signal_date": days[85], "selected_symbols": symbols},
            ]
            periods = [
                {
                    "signal_date": days[70],
                    "label_end": days[85],
                    "benchmark_return": "0.01",
                },
                {
                    "signal_date": days[85],
                    "label_end": days[100],
                    "benchmark_return": "0.02",
                },
            ]
            regime = {days[70]: True, days[85]: False}
            period_rows, trade_rows, holding_rows, summaries = (
                v36.run_exact_ledgers(
                    sqlite_store=db,
                    selections=selections,
                    v33_periods=periods,
                    sector_master=sector,
                    corporate_actions=actions,
                    regime_by_day=regime,
                    price_multiplier=1000.0,
                    dividend_tax_bps=500.0,
                    initial_capital_vnd=100_000_000,
                )
            )
            self.assertEqual(len(summaries), 4)
            self.assertEqual(len(period_rows), 8)
            self.assertTrue(
                all(
                    summary["exact_cash_ledger_pnl_computed"]
                    for summary in summaries
                )
            )
            self.assertTrue(
                all(int(row["quantity"]) % 100 == 0 for row in trade_rows)
            )
            self.assertTrue(
                any(
                    row["side"] == "SELL"
                    and row["execution_day"] == days[101]
                    for row in trade_rows
                )
            )
            self.assertTrue(
                all(
                    summary["final_cash_vnd"] == summary["final_nav_vnd"]
                    for summary in summaries
                )
            )
            self.assertGreater(len(holding_rows), 0)


if __name__ == "__main__":
    unittest.main()
