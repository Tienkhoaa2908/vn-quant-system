from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import c3_consolidated_selection_v75 as v75
from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from tests.test_macro_pit_ablation_v74 import build_store


class TestC3ConsolidatedSelectionV75(unittest.TestCase):
    def test_predeclared_candidates_keep_frozen_c3_anchor(self):
        rows = [
            v75.FeatureRow(date(2024, 1, 31), "AAA", 1, 0.90, True, {name: (0.1 if name == "relative_20" else 0.0) for name in v75.AUX_FEATURES}),
            v75.FeatureRow(date(2024, 1, 31), "BBB", 2, 0.80, True, {name: (0.9 if name == "relative_20" else 0.0) for name in v75.AUX_FEATURES}),
            v75.FeatureRow(date(2024, 1, 31), "CCC", 3, 0.70, True, {name: 0.0 for name in v75.AUX_FEATURES}),
        ]
        snaps, ranking, _ = v75.build_candidate_rankings(rows, [])
        self.assertEqual(snaps[v75.BASE_POLICY][0].symbols, ("AAA", "BBB", "CCC"))
        self.assertEqual(next(r for r in ranking if r["policy_id"] == v75.BASE_POLICY and r["rank"] == 1)["symbol"], "AAA")
        fast = [r for r in ranking if r["policy_id"] == "C3_FAST_REL20_25"]
        self.assertEqual(len(fast), 3)

    def test_aux_weights_never_use_unfinished_or_future_labels(self):
        rows = []
        for i in range(15):
            sd = date(2023, 1, 1) + timedelta(days=31 * i)
            rows.append({
                "signal_day": sd.isoformat(),
                "label_end": (sd + timedelta(days=25)).isoformat(),
                **{f"ic_{name}": 0.10 for name in v75.AUX_FEATURES},
            })
        signal = date(2024, 6, 30)
        base = v75._aux_weights(rows, signal)
        rows.append({
            "signal_day": date(2024, 6, 1).isoformat(),
            "label_end": date(2024, 7, 10).isoformat(),
            **{f"ic_{name}": -0.99 for name in v75.AUX_FEATURES},
        })
        changed = v75._aux_weights(rows, signal)
        self.assertEqual(base, changed)
        self.assertTrue(base)

    def test_2026_is_excluded_from_candidate_inference(self):
        monthly = []
        daily = []
        current = date(2023, 1, 31)
        for i in range(42):
            end = current
            start = end - timedelta(days=25)
            base = 0.004
            candidate = base + 0.0005
            for policy, ret in ((v75.BASE_POLICY, base), ("C3_FAST_REL20_25", candidate)):
                monthly.append({"variant_id":"TEST","allocator":"EQUAL","policy_id":policy,"cost_scenario":"BASE_DNSE","settlement_mode":"IMMEDIATE","initial_capital_vnd":1_000_000_000.0,"period_start_day":start.isoformat(),"period_end_day":end.isoformat(),"strategy_return":ret})
                daily.append({"variant_id":"TEST","allocator":"EQUAL","policy_id":policy,"cost_scenario":"BASE_DNSE","settlement_mode":"IMMEDIATE","initial_capital_vnd":1_000_000_000.0,"day":end.isoformat(),"nav_close_vnd":1_000_000_000.0 * (1 + i * 0.01)})
            month = current.month + 1
            year = current.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            current = date(year, month, 28)
        first = v75.candidate_inference(monthly, daily, {}, signflip_samples=100, bootstrap_samples=100)
        for row in monthly:
            if row["period_end_day"].startswith("2026-") and row["policy_id"] != v75.BASE_POLICY:
                row["strategy_return"] = -0.9
        second = v75.candidate_inference(monthly, daily, {}, signflip_samples=100, bootstrap_samples=100)
        self.assertAlmostEqual(float(first[0]["mean_monthly_return_delta"]), float(second[0]["mean_monthly_return_delta"]), places=15)
        self.assertFalse(first[0]["year_2026_used_for_selection"])

    def test_consolidated_end_to_end_without_macro_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out, v70_out, v75_out = root / "v68", root / "v70", root / "v75"
            build_store(store, count=1400)
            r68 = v68.run_consolidated(store=store, output_dir=v68_out, search_roots=[], allow_network=False, bootstrap_samples=20)
            self.assertEqual(r68["status"], "SUCCESS")
            r70 = v70.analyze(v68_output=v68_out, store=store, output_dir=v70_out)
            self.assertEqual(r70["status"], "SUCCESS")
            r75 = v75.analyze(v68_output=v68_out, v70_output=v70_out, store=store, output_dir=v75_out, allow_macro_network=False, signflip_samples=50, bootstrap_samples=50)
            self.assertEqual(r75["status"], "SUCCESS")
            self.assertEqual(r75["champion_model"], v75.CHAMPION_MODEL)
            self.assertFalse(r75["champion_replaced"])
            self.assertFalse(r75["year_2026_used_for_candidate_selection"])
            self.assertEqual(r75["macro_status"]["status"], "MACRO_NETWORK_DISABLED")
            audit = r75["baseline_reconstruction_audit"]
            self.assertLessEqual(float(audit["max_total_return_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_cagr_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_mdd_error"]), 1e-10)
            for name in (
                "v75_candidate_rankings.csv", "v75_aux_feature_ic_history.csv", "v75_winner_capture_summary.csv",
                "v75_backtest_summary.csv", "v75_monthly_returns.csv", "v75_annual_returns.csv",
                "v75_candidate_inference.csv", "v75_2026_shadow.csv", "v75_daily_equity_base.csv.gz",
                "v75_trade_ledger_base.csv.gz", "v75_macro_coverage.json", "v75_report.json",
            ):
                self.assertTrue((v75_out / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
