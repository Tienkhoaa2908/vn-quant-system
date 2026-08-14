from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import c3_factor_health_regime_v73 as v73
from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong import c3_adaptive_weight_v71 as v71
from tests.test_weekly_overlay_backtest_v72 import build_store


class TestC3FactorHealthRegimeV73(unittest.TestCase):
    def _ic(self, signal: date, label_end: date, rs: float, h52: float) -> v71.ICMonth:
        return v71.ICMonth(signal, label_end, {
            "low_volatility": 0.01,
            "relative_strength_120": rs,
            "high_52_week": h52,
        })

    def test_gate_uses_only_completed_label_end_before_signal(self):
        current = date(2025, 1, 31)
        rows = []
        start = date(2023, 1, 31)
        for i in range(12):
            signal = start + timedelta(days=30 * i)
            rows.append(self._ic(signal, signal + timedelta(days=20), 0.05, 0.04))
        # This row would flip the 3-month RS gate if leaked, but label_end is
        # current signal day and therefore MUST be excluded.
        rows.append(self._ic(current - timedelta(days=10), current, -2.0, -2.0))
        spec = next(item for item in v73.GATES if item.policy_id == "FH_RS3_SOFT50")
        state = v73.gate_state(rows, current, spec)
        self.assertFalse(state["gate_active"])
        self.assertEqual(state["completed_ic_history_count"], 12)

    def test_sign_zero_thresholds_are_frozen(self):
        current = date(2025, 1, 31)
        rows = []
        for i in range(12):
            signal = date(2023, 1, 1) + timedelta(days=30 * i)
            rows.append(self._ic(signal, signal + timedelta(days=10), 0.05, 0.05))
        # Force the latest three completed RS ICs negative while high52 stays positive.
        for offset, rs in zip((90, 60, 30), (-0.02, -0.03, -0.01)):
            signal = current - timedelta(days=offset)
            rows.append(self._ic(signal, signal + timedelta(days=5), rs, 0.08))
        rs_spec = next(item for item in v73.GATES if item.policy_id == "FH_RS3_SOFT50")
        mom_spec = next(item for item in v73.GATES if item.policy_id == "FH_MOM3_AVG_SOFT50")
        self.assertTrue(v73.gate_state(rows, current, rs_spec)["gate_active"])
        self.assertFalse(v73.gate_state(rows, current, mom_spec)["gate_active"])
        self.assertEqual(v73.SOFT_EXPOSURE, 0.50)

    def test_2026_does_not_enter_candidate_inference(self):
        monthly = []
        daily = []
        current = date(2023, 1, 31)
        policies = (v73.BASE_POLICY, "FH_RS3_SOFT50")
        for index in range(42):
            end = current
            start = end - timedelta(days=25)
            base = 0.005 + 0.001 * math.sin(index)
            candidate = base + 0.0005
            for policy, value in ((policies[0], base), (policies[1], candidate)):
                monthly.append({
                    "variant_id": "TEST", "allocator": "EQUAL", "policy_id": policy,
                    "cost_scenario": "BASE_DNSE", "settlement_mode": "IMMEDIATE",
                    "initial_capital_vnd": 1_000_000_000.0,
                    "period_start_day": start.isoformat(), "period_end_day": end.isoformat(),
                    "strategy_return": value, "benchmark_return": 0.0,
                })
                daily.append({
                    "variant_id": "TEST", "allocator": "EQUAL", "policy_id": policy,
                    "cost_scenario": "BASE_DNSE", "settlement_mode": "IMMEDIATE",
                    "initial_capital_vnd": 1_000_000_000.0,
                    "day": end.isoformat(), "nav_close_vnd": 1_000_000_000.0 * (1 + index * 0.01),
                })
            year = current.year + (current.month // 12)
            month = current.month % 12 + 1
            current = date(year, month, 28)
        first = v73.candidate_inference(monthly, daily, signflip_samples=200, bootstrap_samples=200)
        for row in monthly:
            if str(row["period_end_day"]).startswith("2026-") and row["policy_id"] != v73.BASE_POLICY:
                row["strategy_return"] = -0.90
        second = v73.candidate_inference(monthly, daily, signflip_samples=200, bootstrap_samples=200)
        self.assertAlmostEqual(float(first[0]["mean_monthly_return_delta"]), float(second[0]["mean_monthly_return_delta"]), places=15)
        self.assertAlmostEqual(float(first[0]["signflip_two_sided_p"]), float(second[0]["signflip_two_sided_p"]), places=15)
        self.assertFalse(first[0]["year_2026_used_for_selection"])

    def test_end_to_end_reconstructs_v70_and_writes_profit_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out, v70_out, v73_out = root / "v68", root / "v70", root / "v73"
            build_store(store, count=1300)
            report68 = v68.run_consolidated(
                store=store, output_dir=v68_out, search_roots=[], allow_network=False, bootstrap_samples=20
            )
            self.assertEqual(report68["status"], "SUCCESS")
            report70 = v70.analyze(v68_output=v68_out, store=store, output_dir=v70_out)
            self.assertEqual(report70["status"], "SUCCESS")
            report73 = v73.analyze(
                v68_output=v68_out, v70_output=v70_out, store=store, output_dir=v73_out,
                signflip_samples=100, bootstrap_samples=100,
            )
            self.assertEqual(report73["status"], "SUCCESS")
            self.assertEqual(report73["champion_model"], v73.CHAMPION_MODEL)
            self.assertFalse(report73["champion_replaced"])
            self.assertFalse(report73["year_2026_used_for_candidate_selection"])
            self.assertFalse(report73["promotion_authorized"])
            audit = report73["baseline_reconstruction_audit"]
            self.assertLessEqual(float(audit["max_total_return_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_cagr_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_mdd_error"]), 1e-10)
            for name in (
                "v73_factor_health_state.csv", "v73_backtest_summary.csv", "v73_monthly_returns.csv",
                "v73_annual_returns.csv", "v73_rolling_alpha.csv", "v73_candidate_inference.csv",
                "v73_2026_shadow.csv", "v73_cost_drag.csv", "v73_capital_sensitivity.csv",
                "v73_trade_ledger_base.csv.gz", "v73_daily_equity_base.csv.gz", "v73_report.json",
            ):
                self.assertTrue((v73_out / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
