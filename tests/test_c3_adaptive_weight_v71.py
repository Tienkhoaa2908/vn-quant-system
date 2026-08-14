from __future__ import annotations

from datetime import date, timedelta
import csv
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import c3_adaptive_weight_v71 as v71
from he_thong_dinh_luong import c3_adaptive_weight_v71_safe as v71safe
from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70


def weekdays(start: date, count: int) -> list[date]:
    result = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def build_store(path: Path, count: int = 1300) -> None:
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
                ("INDEX", "VNINDEX", day.isoformat(), index_close * 0.999, index_close, 0, "synthetic", "1", "CHUA_XAC_NHAN", "batch-a"),
            )
            for j, symbol in enumerate(symbols):
                cycle = 0.8 * math.sin(i / (9.0 + j * 0.25))
                base = 28.0 + j * 2.1 + (0.02 + j * 0.00065) * i + cycle
                open_price, close_price, fetched = base * 0.999, base, "batch-a"
                if symbol == "S00" and i == 850:
                    open_price, close_price, fetched = base * 0.50, base * 0.51, "batch-b"
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("STOCK", symbol, day.isoformat(), open_price, close_price, 500000 + j * 15000, "synthetic", "1", "CHUA_XAC_NHAN", fetched),
                )
        db.commit()
    finally:
        db.close()


class TestAdaptiveWeightsV71(unittest.TestCase):
    def test_frozen_raw_cap_then_renormalize_is_preserved(self):
        weights = v71._weights_from_means(
            {"low_volatility": 0.0, "relative_strength_120": 1.0, "high_52_week": 0.0}
        )
        self.assertAlmostEqual(weights["relative_strength_120"], 0.60, places=12)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=12)

    def test_future_label_end_cannot_change_weights(self):
        history = [
            v71.ICMonth(date(2020, month, 1), date(2020, month, 20), {
                "low_volatility": 0.2,
                "relative_strength_120": 0.1,
                "high_52_week": 0.15,
            })
            for month in range(1, 13)
        ]
        signal = date(2021, 2, 1)
        clean, count = v71.adaptive_weights(history, signal_day=signal, candidate=v71.CANDIDATES[1])
        poisoned = history + [v71.ICMonth(date(2021, 1, 1), date(2021, 3, 1), {
            "low_volatility": -1.0,
            "relative_strength_120": 1.0,
            "high_52_week": -1.0,
        })]
        after, after_count = v71.adaptive_weights(poisoned, signal_day=signal, candidate=v71.CANDIDATES[1])
        self.assertEqual(count, after_count)
        self.assertEqual(clean, after)

    def test_2026_returns_do_not_enter_candidate_inference(self):
        rows = []
        current = date(2023, 1, 31)
        months = []
        for _ in range(42):
            months.append(current)
            year = current.year + (current.month // 12)
            month = current.month % 12 + 1
            current = date(year, month, 28)
        for index, end in enumerate(months):
            period_start = (end - timedelta(days=25)).isoformat()
            baseline = 0.005 + 0.001 * math.sin(index)
            candidate = baseline + 0.001
            for candidate_id, ret in ((v71.CHAMPION_MODEL, baseline), ("C3_IC_EWMA_HL24", candidate)):
                rows.append({
                    "variant_id": "TEST",
                    "allocator": "EQUAL",
                    "candidate_id": candidate_id,
                    "cost_scenario": "BASE_DNSE",
                    "period_start_day": period_start,
                    "period_end_day": end.isoformat(),
                    "strategy_return": ret,
                })
        first = v71.candidate_inference(rows, signflip_samples=200, bootstrap_samples=200)
        for row in rows:
            if str(row["period_end_day"]).startswith("2026-") and row["candidate_id"] != v71.CHAMPION_MODEL:
                row["strategy_return"] = -0.90
        second = v71.candidate_inference(rows, signflip_samples=200, bootstrap_samples=200)
        self.assertAlmostEqual(float(first[0]["mean_monthly_return_delta"]), float(second[0]["mean_monthly_return_delta"]), places=15)
        self.assertAlmostEqual(float(first[0]["signflip_two_sided_p"]), float(second[0]["signflip_two_sided_p"]), places=15)
        self.assertFalse(bool(first[0]["year_2026_used_for_selection"]))

    def test_end_to_end_reconstructs_frozen_c3_and_writes_profit_equity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out = root / "v68"
            v70_out = root / "v70"
            v71_out = root / "v71"
            build_store(store)
            report68 = v68.run_consolidated(
                store=store,
                output_dir=v68_out,
                search_roots=[],
                allow_network=False,
                bootstrap_samples=50,
            )
            self.assertEqual(report68["status"], "SUCCESS")
            report70 = v70.analyze(v68_output=v68_out, store=store, output_dir=v70_out)
            self.assertEqual(report70["status"], "SUCCESS")
            report71 = v71safe.analyze(
                v68_output=v68_out,
                v70_output=v70_out,
                store=store,
                output_dir=v71_out,
                signflip_samples=200,
                bootstrap_samples=200,
            )
            self.assertEqual(report71["status"], "SUCCESS")
            self.assertEqual(report71["champion_model"], v71.CHAMPION_MODEL)
            self.assertFalse(report71["champion_replaced"])
            self.assertFalse(report71["year_2026_used_for_candidate_selection"])
            self.assertFalse(report71["promotion_authorized"])
            self.assertEqual(report71["historical_component_provenance"], "V67_FROZEN_TRAINING_ROWS")
            for audit in report71["frozen_reconstruction_audit"].values():
                self.assertLessEqual(float(audit["max_frozen_weight_reconstruction_error"]), 1e-10)
                self.assertLessEqual(float(audit["max_frozen_score_reconstruction_error"]), 1e-10)
                self.assertEqual(int(audit["frozen_rank_mismatch_count"]), 0)
                self.assertGreater(int(audit["raw_factor_crosscheck_count"]), 0)
            required = (
                "v71_component_ic_history.csv",
                "v71_weight_history.csv",
                "v71_rankings.csv.gz",
                "v71_top10_overlap.csv",
                "v71_predictive_proxy.csv",
                "v71_backtest_summary.csv",
                "v71_monthly_returns.csv",
                "v71_annual_returns.csv",
                "v71_candidate_inference.csv",
                "v71_2026_shadow.csv",
                "v71_cost_drag.csv",
                "v71_capital_sensitivity.csv",
                "v71_trade_ledger_base.csv.gz",
                "v71_daily_equity_base.csv.gz",
                "v71_report.json",
            )
            for name in required:
                self.assertTrue((v71_out / name).is_file(), name)
            self.assertTrue(report71["profit_reporting"]["base_cost_profit_table"])
            with (v71_out / "v71_candidate_inference.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                inference = list(csv.DictReader(handle))
            self.assertTrue(inference)
            self.assertTrue(all(row["selection_period_end"] == "2025-12-31" for row in inference))


if __name__ == "__main__":
    unittest.main()
