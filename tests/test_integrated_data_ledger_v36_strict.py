from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import integrated_data_ledger_v36 as base
from he_thong_dinh_luong import integrated_data_ledger_v36_strict as strict


class IntegratedDataLedgerV36StrictTests(unittest.TestCase):
    def test_missing_benchmark_is_blocked(self) -> None:
        audit = strict.audit_benchmark(None, ["2024-01-02", "2024-02-01"])
        self.assertFalse(audit["valid"])
        self.assertEqual(audit["covered_date_count"], 0)
        self.assertEqual(audit["blocker"], "V36_VNINDEX_NEXT_OPEN_SERIES_MISSING")

    def test_benchmark_requires_unique_complete_positive_opens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "vnindex.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["symbol", "day", "open"])
                writer.writeheader()
                writer.writerow({"symbol": "VNINDEX", "day": "2024-01-02", "open": 1100})
                writer.writerow({"symbol": "VNINDEX", "day": "2024-02-01", "open": 1120})
            audit = strict.audit_benchmark(source, ["2024-01-02", "2024-02-01"])
            self.assertTrue(audit["valid"])
            self.assertEqual(audit["covered_date_count"], 2)

    def test_assurance_binds_vnindex_hash_and_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark = root / "vnindex.csv"
            benchmark.write_text("symbol,day,open\nVNINDEX,2024-01-02,1100\n", encoding="utf-8")
            audit = strict.audit_benchmark(benchmark, ["2024-01-02"])
            assurance = root / "assurance.json"
            assurance.write_text(
                json.dumps(
                    {
                        "vnindex_ohlcv_sha256": audit["sha256"],
                        "vnindex_next_open_complete": True,
                    }
                ),
                encoding="utf-8",
            )
            result = strict._benchmark_assurance(assurance, audit)
            self.assertTrue(result["valid"])
            value = json.loads(assurance.read_text(encoding="utf-8"))
            value["vnindex_ohlcv_sha256"] = "0" * 64
            assurance.write_text(json.dumps(value), encoding="utf-8")
            self.assertFalse(strict._benchmark_assurance(assurance, audit)["valid"])

    def test_patch_metrics_uses_next_open_to_next_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            period_rows = [
                {
                    "strategy": "FROZEN",
                    "scenario": "BASE",
                    "signal_date": "2024-01-01",
                    "execution_day": "2024-01-02",
                    "period_end_execution_day": "2024-02-01",
                    "period_net_return": 0.10,
                    "benchmark_return": 0.99,
                    "net_excess_return": -0.89,
                    "benchmark_nav": 1.99,
                },
                {
                    "strategy": "FROZEN",
                    "scenario": "BASE",
                    "signal_date": "2024-02-01",
                    "execution_day": "2024-02-02",
                    "period_end_execution_day": "2024-03-01",
                    "period_net_return": 0.05,
                    "benchmark_return": 0.99,
                    "net_excess_return": -0.94,
                    "benchmark_nav": 3.96,
                },
            ]
            summary_rows = [
                {
                    "strategy": "FROZEN",
                    "scenario": "BASE",
                    "net_total_return": 0.155,
                    "benchmark_total_return": 2.0,
                    "relative_total_return": -0.6,
                    "positive_net_excess_ratio": 0.0,
                    "average_net_excess_return": -0.9,
                }
            ]
            base._write_csv(out / base.LEDGER_PERIODS_FILE, period_rows, tuple(period_rows[0]))
            base._write_csv(out / base.LEDGER_SUMMARY_FILE, summary_rows, tuple(summary_rows[0]))
            patched = strict._patch_benchmark_metrics(
                out,
                {
                    "open_by_day": {
                        "2024-01-02": 1000.0,
                        "2024-02-01": 1010.0,
                        "2024-02-02": 1012.0,
                        "2024-03-01": 1022.12,
                    }
                },
            )
            self.assertEqual(len(patched), 1)
            self.assertAlmostEqual(float(patched[0]["benchmark_total_return"]), 0.0201)
            self.assertEqual(
                patched[0]["benchmark_execution_basis"],
                "VNINDEX_NEXT_OPEN_TO_NEXT_OPEN",
            )


if __name__ == "__main__":
    unittest.main()
