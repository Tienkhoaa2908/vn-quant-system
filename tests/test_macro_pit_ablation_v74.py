from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong import macro_pit_ablation_v74 as v74


def weekdays(start: date, count: int) -> list[date]:
    output = []
    current = start
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current)
        current += timedelta(days=1)
    return output


def build_store(path: Path, count: int = 1400) -> None:
    days = weekdays(date(2018, 1, 2), count)
    symbols = [f"S{i:02d}" for i in range(16)]
    db = sqlite3.connect(path)
    try:
        db.execute(
            "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, "
            "volume INTEGER, source TEXT, source_version TEXT, price_basis TEXT, fetched_at TEXT)"
        )
        for i, day in enumerate(days):
            index_close = 900.0 + 0.16 * i + 3.0 * math.sin(i / 23.0)
            db.execute(
                "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("INDEX", "VNINDEX", day.isoformat(), index_close * 0.999, index_close, 0,
                 "synthetic", "1", "CHUA_XAC_NHAN", "batch-a"),
            )
            for j, symbol in enumerate(symbols):
                cycle = 0.8 * math.sin(i / (9.0 + j * 0.25))
                base = 28.0 + j * 2.1 + (0.02 + j * 0.00065) * i + cycle
                open_price, close_price, fetched = base * 0.999, base, "batch-a"
                if symbol == "S00" and i == 650:
                    open_price, close_price, fetched = base * 0.50, base * 0.51, "batch-b"
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("STOCK", symbol, day.isoformat(), open_price, close_price, 500000 + j * 15000,
                     "synthetic", "1", "CHUA_XAC_NHAN", fetched),
                )
        db.commit()
    finally:
        db.close()


def add_month(day: date, months: int = 1) -> date:
    total = day.year * 12 + day.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def synthetic_macro() -> list[v74.MacroRelease]:
    rows = []
    ref = date(2016, 1, 1)
    for i in range(132):
        issue_month = add_month(ref, 1)
        issue = date(issue_month.year, issue_month.month, 6)
        cpi = 3.0 + 0.6 * math.sin(i / 5.0)
        iip = 7.0 + 2.0 * math.sin(i / 7.0 + 0.8)
        for series, value in (("CPI", cpi), ("IIP", iip)):
            rows.append(v74.MacroRelease(
                series, ref, issue, value,
                f"https://www.nso.gov.vn/en/data-and-statistics/{issue.year}/{issue.month:02d}/{series.lower()}-{ref.year}-{ref.month}/",
                f"sha-{series}-{i}", "fixture", "synthetic",
            ))
        ref = add_month(ref, 1)
    return rows


class TestMacroPITAblationV74(unittest.TestCase):
    def test_parse_english_cpi_and_iip_release(self):
        cpi = b"""<h1>Consumer Price Index in May 2026</h1><p>The Consumer Price Index (CPI) in May 2026 increased by 0.29% compared to the previous month. Compared to December 2025, the CPI in May increased by 3.61% and by 5.6% compared to the same period last year.</p><p>Reference period: May 5/2026</p><p>Date of issue: 03/06/2026</p>"""
        # Explicit numeric reference metadata is the authoritative parser path.
        cpi = cpi.replace(b"Reference period: May 5/2026", b"Reference period: 5/2026")
        row = v74.parse_release_html(series="CPI", url="https://www.nso.gov.vn/en/data-and-statistics/2026/06/cpi/", raw=cpi, language="en")
        self.assertIsNotNone(row)
        self.assertEqual(row.reference_month, date(2026, 5, 1))
        self.assertEqual(row.issue_day, date(2026, 6, 3))
        self.assertAlmostEqual(row.yoy_pct, 5.6)

        iip = b"""<h1>Index of industrial production in February of 2026</h1><p>The industrial production index (IIP) in February is estimated to have decreased by 18.4% compared to the previous month and increased by 1.0% compared to the same period last year.</p><p>Reference period: 2/2026</p><p>Date of issue: 06/03/2026</p>"""
        row2 = v74.parse_release_html(series="IIP", url="https://www.nso.gov.vn/en/data-and-statistics/2026/03/iip/", raw=iip, language="en")
        self.assertIsNotNone(row2)
        self.assertEqual(row2.reference_month, date(2026, 2, 1))
        self.assertAlmostEqual(row2.yoy_pct, 1.0)

    def test_parse_vietnamese_fallback(self):
        raw = """<h1>Chỉ số sản xuất công nghiệp tháng Năm năm 2025</h1><p>Chỉ số sản xuất toàn ngành công nghiệp (IIP) tháng 5/2025 ước tính tăng 4,3% so với tháng trước và tăng 9,4% so với cùng kỳ năm trước.</p><p>Kỳ tham chiếu: 5/2025</p><p>Ngày đăng: 06/06/2025</p>""".encode("utf-8")
        row = v74.parse_release_html(series="IIP", url="https://www.nso.gov.vn/du-lieu-va-so-lieu-thong-ke/2025/06/iip/", raw=raw, language="vi")
        self.assertIsNotNone(row)
        self.assertEqual(row.issue_day, date(2025, 6, 6))
        self.assertAlmostEqual(row.yoy_pct, 9.4)

    def test_only_official_nso_https_is_allowed(self):
        self.assertEqual(v74._safe_url("https://www.nso.gov.vn/en/cpi/"), "https://www.nso.gov.vn/en/cpi/")
        with self.assertRaisesRegex(ValueError, "V74_UNAPPROVED_MACRO_URL"):
            v74._safe_url("https://example.com/cpi")
        with self.assertRaisesRegex(ValueError, "V74_UNAPPROVED_MACRO_URL"):
            v74._safe_url("http://www.nso.gov.vn/en/cpi/")

    def test_publication_date_pit_blocks_future_release(self):
        rows = synthetic_macro()
        spec = next(item for item in v74.GATES if item.policy_id == "MACRO_IIP3_DECEL_SOFT50")
        signal = date(2025, 3, 31)
        before = v74.macro_state(rows, signal, spec)
        future = v74.MacroRelease("IIP", date(2025, 3, 1), date(2025, 4, 6), -50.0,
                                  "https://www.nso.gov.vn/en/data-and-statistics/2025/04/future/", "future", "fixture", "future")
        after = v74.macro_state(rows + [future], signal, spec)
        self.assertEqual(before["latest_iip_reference_month"], after["latest_iip_reference_month"])
        self.assertAlmostEqual(float(before["iip_impulse_pp"]), float(after["iip_impulse_pp"]), places=15)
        self.assertTrue(before["publication_date_pit_enforced"])

    def test_2026_never_enters_candidate_inference(self):
        rows = []
        daily = []
        current = date(2023, 1, 31)
        for index in range(42):
            end = current
            start = end - timedelta(days=25)
            base_return = 0.004 + 0.001 * math.sin(index)
            candidate_return = base_return + 0.0005
            for policy, value in ((v74.BASE_POLICY, base_return), ("MACRO_IIP3_DECEL_SOFT50", candidate_return)):
                rows.append({"variant_id":"TEST","allocator":"EQUAL","policy_id":policy,
                             "cost_scenario":"BASE_DNSE","settlement_mode":"IMMEDIATE","initial_capital_vnd":1_000_000_000.0,
                             "period_start_day":start.isoformat(),"period_end_day":end.isoformat(),"strategy_return":value})
                daily.append({"variant_id":"TEST","allocator":"EQUAL","policy_id":policy,
                              "cost_scenario":"BASE_DNSE","settlement_mode":"IMMEDIATE","initial_capital_vnd":1_000_000_000.0,
                              "day":end.isoformat(),"nav_close_vnd":1_000_000_000.0*(1+index*0.01)})
            current = add_month(date(current.year, current.month, 1), 1) + timedelta(days=27)
        first = v74.candidate_inference(rows, daily, signflip_samples=200, bootstrap_samples=200)
        for row in rows:
            if row["period_end_day"].startswith("2026-") and row["policy_id"] != v74.BASE_POLICY:
                row["strategy_return"] = -0.90
        second = v74.candidate_inference(rows, daily, signflip_samples=200, bootstrap_samples=200)
        self.assertAlmostEqual(float(first[0]["mean_monthly_return_delta"]), float(second[0]["mean_monthly_return_delta"]), places=15)
        self.assertFalse(first[0]["year_2026_used_for_selection"])

    def test_end_to_end_reconstructs_v70_and_writes_profit_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out, v70_out, v74_out = root / "v68", root / "v70", root / "v74"
            build_store(store)
            report68 = v68.run_consolidated(store=store, output_dir=v68_out, search_roots=[], allow_network=False, bootstrap_samples=30)
            self.assertEqual(report68["status"], "SUCCESS")
            report70 = v70.analyze(v68_output=v68_out, store=store, output_dir=v70_out)
            self.assertEqual(report70["status"], "SUCCESS")
            report74 = v74.analyze(v68_output=v68_out, v70_output=v70_out, store=store, output_dir=v74_out,
                                   macro_releases=synthetic_macro(), signflip_samples=100, bootstrap_samples=100)
            self.assertEqual(report74["status"], "SUCCESS")
            self.assertEqual(report74["champion_model"], v74.CHAMPION_MODEL)
            self.assertFalse(report74["champion_replaced"])
            self.assertTrue(report74["publication_date_pit_enforced"])
            self.assertFalse(report74["year_2026_used_for_candidate_selection"])
            audit = report74["baseline_reconstruction_audit"]
            self.assertLessEqual(float(audit["max_total_return_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_cagr_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_mdd_error"]), 1e-10)
            for name in (
                "v74_macro_release_history.csv", "v74_macro_state.csv", "v74_backtest_summary.csv",
                "v74_monthly_returns.csv", "v74_annual_returns.csv", "v74_rolling_alpha.csv",
                "v74_candidate_inference.csv", "v74_2026_shadow.csv", "v74_cost_drag.csv",
                "v74_capital_sensitivity.csv", "v74_daily_equity_base.csv.gz", "v74_trade_ledger_base.csv.gz",
                "v74_report.json",
            ):
                self.assertTrue((v74_out / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
