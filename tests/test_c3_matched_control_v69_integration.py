from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import c3_matched_control_v69 as v69
from he_thong_dinh_luong import c3_portfolio_profit_v69 as profit


def weekdays(start: date, count: int) -> list[date]:
    result = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


class TestC3MatchedControlV69Integration(unittest.TestCase):
    def test_real_v68_output_is_consumed_by_v69_and_profit_report(self):
        days = weekdays(date(2018, 1, 2), 900)
        symbols = [f"S{i:02d}" for i in range(16)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out = root / "v68"
            v69_out = root / "v69"
            db = sqlite3.connect(store)
            try:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, "
                    "volume INTEGER, source TEXT, source_version TEXT, price_basis TEXT, fetched_at TEXT)"
                )
                for i, day in enumerate(days):
                    index_close = 900.0 + 0.16 * i + 2.0 * math.sin(i / 19.0)
                    db.execute(
                        "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                        ("INDEX", "VNINDEX", day.isoformat(), index_close * 0.999, index_close, 0, "synthetic", "1", "CHUA_XAC_NHAN", "batch-a"),
                    )
                    for j, symbol in enumerate(symbols):
                        base = 28.0 + j * 2.2 + (0.02 + j * 0.0007) * i + 0.7 * math.sin(i / (9.0 + j * 0.2))
                        open_price, close_price, fetched = base * 0.999, base, "batch-a"
                        if symbol == "S00" and i == 600:
                            open_price, close_price, fetched = base * 0.50, base * 0.51, "batch-b"
                        db.execute(
                            "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("STOCK", symbol, day.isoformat(), open_price, close_price, 450000 + j * 12000, "synthetic", "1", "CHUA_XAC_NHAN", fetched),
                        )
                db.commit()
            finally:
                db.close()

            v68_report = v68.run_consolidated(
                store=store,
                output_dir=v68_out,
                search_roots=[],
                allow_network=False,
                bootstrap_samples=100,
            )
            self.assertEqual(v68_report["status"], "SUCCESS")
            report = v69.analyze(
                v68_output=v68_out,
                store=store,
                output_dir=v69_out,
                signflip_samples=1000,
                bootstrap_samples=1000,
            )
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["champion_model"], "C3_STABLE_3_PAST_IC_SHRUNK")
            self.assertFalse(report["champion_replaced"])
            self.assertFalse(report["cohort_thresholds_changed"])
            self.assertFalse(report["promotion_authorized"])
            self.assertTrue((v69_out / "v69_leader_matched_control.csv").is_file())
            self.assertTrue((v69_out / "v69_risk_matched_control.csv").is_file())
            self.assertTrue((v69_out / "v69_report.json").is_file())

            profit_report = profit.analyze(v68_output=v68_out, store=store, output_dir=v69_out)
            self.assertIn(profit_report["status"], {"SUCCESS", "SUCCESS_WITH_MISSING_PRICE_PERIODS"})
            self.assertEqual(profit_report["champion_model"], "C3_STABLE_3_PAST_IC_SHRUNK")
            self.assertTrue(profit_report["gross_only"])
            self.assertFalse(profit_report["costs_included"])
            self.assertTrue((v69_out / "v69_portfolio_equity_curve.csv").is_file())
            self.assertTrue((v69_out / "v69_portfolio_annual_returns.csv").is_file())
            self.assertTrue((v69_out / "v69_portfolio_profit_summary.csv").is_file())
            self.assertTrue((v69_out / "v69_profit_report.json").is_file())
            self.assertGreater(len(profit_report["summary"]), 0)


if __name__ == "__main__":
    unittest.main()
