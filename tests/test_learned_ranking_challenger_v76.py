from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong import learned_ranking_challenger_v76 as v76
from tests.test_macro_pit_ablation_v74 import build_store


class TestLearnedRankingChallengerV76(unittest.TestCase):
    def test_split_excludes_labels_not_completed_before_test(self):
        rows = []
        start = date(2023, 1, 31)
        for i in range(20):
            day = start + timedelta(days=31 * i)
            rows.append(v76.PanelRow(
                signal_day=day,
                label_end=day + timedelta(days=20),
                symbol=f"S{i % 8}",
                risk_on=True,
                features=tuple(0.5 for _ in v76.FEATURE_NAMES),
                target_relative=0.01,
                target_rank=0.6,
            ))
        # A row whose signal is old enough but whose label completes after the test
        # must never enter train or validation.
        test_day = date(2025, 1, 31)
        future = v76.PanelRow(
            signal_day=date(2024, 12, 1),
            label_end=date(2025, 2, 10),
            symbol="FUTURE",
            risk_on=True,
            features=tuple(0.9 for _ in v76.FEATURE_NAMES),
            target_relative=9.0,
            target_rank=1.0,
        )
        split = v76._split_safe_history(rows + [future], test_day)
        self.assertIsNotNone(split)
        train, validation = split
        self.assertNotIn("FUTURE", {row.symbol for row in train + validation})
        self.assertTrue(all(row.label_end < test_day for row in train + validation))

    def test_context_ignores_unfinished_future_ic(self):
        rows = []
        for month in range(1, 5):
            rows.append({
                "signal_day": date(2024, month, 20).isoformat(),
                "label_end": date(2024, month + 1, 15).isoformat(),
                "ic_relative_strength_120": 0.10 * month,
                "ic_high_52_week": 0.05 * month,
            })
        signal = date(2024, 6, 30)
        before = v76._context(rows, signal)
        rows.append({
            "signal_day": date(2024, 6, 1).isoformat(),
            "label_end": date(2024, 7, 20).isoformat(),
            "ic_relative_strength_120": -0.99,
            "ic_high_52_week": -0.99,
        })
        self.assertEqual(before, v76._context(rows, signal))

    def test_close_to_close_label_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "market.sqlite3"
            build_store(store, count=500)
            market = v70.load_market(store, {"S01"})
            day = market.cal[300]
            label = v76._label(market, "S01", day, 20)
            self.assertIsNotNone(label)
            end, relative = label
            expected = (
                market.sc[("S01", end)] / market.sc[("S01", day)]
                - market.ic[end] / market.ic[day]
            )
            self.assertAlmostEqual(relative, expected, places=15)

    def test_end_to_end_reconstructs_frozen_and_runs_all_challengers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out, v70_out, v76_out = root / "v68", root / "v70", root / "v76"
            build_store(store, count=1400)
            r68 = v68.run_consolidated(
                store=store,
                output_dir=v68_out,
                search_roots=[],
                allow_network=False,
                bootstrap_samples=20,
            )
            self.assertEqual(r68["status"], "SUCCESS")
            r70 = v70.analyze(v68_output=v68_out, store=store, output_dir=v70_out)
            self.assertEqual(r70["status"], "SUCCESS")

            old_ridge, old_logit, old_hgb = v76.RIDGE_ALPHAS, v76.LOGISTIC_CS, v76.HGB_L2
            try:
                # Structural CI exercises every challenger while keeping synthetic
                # runtime short. Production runner uses the full preregistered grids.
                v76.RIDGE_ALPHAS = (10.0,)
                v76.LOGISTIC_CS = (1.0,)
                v76.HGB_L2 = (10.0,)
                r76 = v76.analyze(
                    v68_output=v68_out,
                    v70_output=v70_out,
                    store=store,
                    output_dir=v76_out,
                    signflip_samples=50,
                    bootstrap_samples=50,
                )
            finally:
                v76.RIDGE_ALPHAS, v76.LOGISTIC_CS, v76.HGB_L2 = old_ridge, old_logit, old_hgb

            self.assertEqual(r76["status"], "SUCCESS")
            self.assertEqual(r76["champion_model"], v76.CHAMPION_MODEL)
            self.assertFalse(r76["champion_replaced"])
            self.assertFalse(r76["year_2026_used_for_candidate_selection"])
            self.assertTrue(r76["model_trainable_history_separate_from_portfolio_eligibility"])
            self.assertTrue(r76["deep_backtest_completed"])
            self.assertFalse(r76["promotion_authorized"])
            audit = r76["baseline_reconstruction_audit"]
            self.assertLessEqual(float(audit["max_total_return_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_cagr_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_mdd_error"]), 1e-10)

            fit_rows = v76._read_csv(v76_out / "v76_model_fit_history.csv")
            fitted = {
                row["policy_id"] for row in fit_rows
                if str(row.get("model_fitted", "")).lower() == "true"
            }
            for policy in v76.MODEL_POLICIES[1:]:
                self.assertIn(policy, fitted)

            coverage = v76._read_csv(v76_out / "v76_training_coverage.csv")
            self.assertTrue(coverage)
            self.assertTrue(all(str(row["portfolio_eligibility_used_as_training_filter"]).lower() == "false" for row in coverage))
            for name in (
                "v76_training_coverage.csv",
                "v76_model_fit_history.csv",
                "v76_candidate_rankings.csv.gz",
                "v76_rank_ic_summary.csv",
                "v76_winner_capture_summary.csv",
                "v76_backtest_summary.csv",
                "v76_monthly_returns.csv",
                "v76_annual_returns.csv",
                "v76_candidate_inference.csv",
                "v76_2026_shadow.csv",
                "v76_focus_rank_audit_2026.csv",
                "v76_daily_equity_base.csv.gz",
                "v76_trade_ledger_base.csv.gz",
                "v76_report.json",
            ):
                self.assertTrue((v76_out / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()