from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import c3_hose_consolidated_v68_safe as v68
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong import weekly_overlay_backtest_v72 as v72


def weekdays(start: date, count: int) -> list[date]:
    output = []
    current = start
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current)
        current += timedelta(days=1)
    return output


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
                if symbol == "S00" and i == 950:
                    open_price, close_price, fetched = base * 0.50, base * 0.51, "batch-b"
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("STOCK", symbol, day.isoformat(), open_price, close_price, 500000 + j * 15000, "synthetic", "1", "CHUA_XAC_NHAN", fetched),
                )
        db.commit()
    finally:
        db.close()


class TestWeeklyOverlayBacktestV72(unittest.TestCase):
    def test_frozen_trigger_contracts(self):
        r07 = {"canonical_rank": 4, "drawdown_20": -0.081}
        self.assertTrue(v72.trigger_matches("R07_DD20_08", r07))
        self.assertFalse(v72.trigger_matches("R07_DD20_08", {**r07, "drawdown_20": -0.079}))
        r08 = {"canonical_rank": 8, "drawdown_60": -0.13}
        self.assertTrue(v72.trigger_matches("R08_DD60_12", r08))
        l15 = {
            "canonical_rank": 11,
            "preview_rank": 3,
            "prior_preview_rank": 8,
            "relative_5": 0.025,
            "volume_ratio_5_20": 1.1,
        }
        self.assertTrue(v72.trigger_matches("L15_PERSIST_REL", l15))
        self.assertFalse(v72.trigger_matches("L15_PERSIST_REL", {**l15, "prior_preview_rank": 11}))

    def test_r07_trim_is_once_per_monthly_cycle_and_leaves_cash(self):
        d0, d1 = date(2025, 1, 3), date(2025, 1, 6)
        market = v70.Market([d0, d1], {d0: 1000.0, d1: 1000.0}, {d0: 1000.0, d1: 1000.0},
                            {("AAA", d1): 100_000.0}, {("AAA", d1): 100_000.0}, {("AAA", d1): 1000})
        state = v70.State(0.0, {"AAA": 1000}, [], {"AAA": 100_000.0}, {"AAA": 1000})
        signal = v72.WeeklySignal(d0, d0, {"AAA": {"symbol": "AAA", "canonical_rank": 1, "drawdown_20": -0.10}})
        policy = next(item for item in v72.POLICIES if item.policy_id == "R07_TRIM50_CASH")
        acted, ledger, missing, actions = set(), [], [], []
        v72._apply_risk_trim(state=state, market=market, signal=signal, policy=policy, trade_day=d1,
                             cost=v70.COSTS[0], settlement="IMMEDIATE", acted_in_cycle=acted,
                             ledger=ledger, missing=missing, actions=actions)
        self.assertEqual(state.shares["AAA"], 500)
        self.assertEqual(state.desired["AAA"], 500)
        self.assertAlmostEqual(state.cash, 50_000_000.0, places=6)
        self.assertEqual(len(actions), 1)
        v72._apply_risk_trim(state=state, market=market, signal=signal, policy=policy, trade_day=d1,
                             cost=v70.COSTS[0], settlement="IMMEDIATE", acted_in_cycle=acted,
                             ledger=ledger, missing=missing, actions=actions)
        self.assertEqual(state.shares["AAA"], 500)
        self.assertEqual(len(actions), 1)

    def test_l15_swap_respects_single_name_cap(self):
        d0, d1 = date(2025, 1, 3), date(2025, 1, 6)
        opens = {("AAA", d1): 100_000.0, ("BBB", d1): 100_000.0}
        closes = dict(opens)
        market = v70.Market([d0, d1], {d0: 1000.0, d1: 1000.0}, {d0: 1000.0, d1: 1000.0}, opens, closes, {})
        state = v70.State(0.0, {"AAA": 1000}, [], {"AAA": 100_000.0}, {"AAA": 1000})
        signal = v72.WeeklySignal(d0, d0, {
            "AAA": {"symbol": "AAA", "canonical_rank": 1, "preview_rank": 20, "preview_score": 0.2},
            "BBB": {"symbol": "BBB", "canonical_rank": 12, "preview_rank": 2, "prior_preview_rank": 5,
                    "preview_score": 0.9, "relative_5": 0.03, "volume_ratio_5_20": 1.2},
        })
        policy = next(item for item in v72.POLICIES if item.policy_id == "L15_SWAP50_WORST")
        ledger, missing, actions = [], [], []
        v72._apply_leader_swap(state=state, market=market, signal=signal, policy=policy, trade_day=d1,
                               cost=v70.COSTS[0], settlement="IMMEDIATE", ledger=ledger,
                               missing=missing, actions=actions)
        # NAV is 100m; 15% cap at 100k/share is 100 shares after lot rounding.
        self.assertEqual(state.shares.get("BBB"), 100)
        self.assertEqual(state.shares.get("AAA"), 500)
        self.assertLessEqual(state.shares["BBB"] * 100_000.0, 0.15 * 100_000_000.0 + 1e-6)
        self.assertEqual(len(actions), 1)

    def test_2026_does_not_enter_policy_inference(self):
        rows = []
        daily = []
        current = date(2023, 1, 31)
        for index in range(42):
            end = current
            period_start = end - timedelta(days=25)
            base_return = 0.005 + 0.001 * math.sin(index)
            candidate_return = base_return + 0.0005
            for policy, value in (("NO_OVERLAY", base_return), ("L15_SWAP50_WORST", candidate_return)):
                rows.append({
                    "variant_id": "TEST",
                    "allocator": "EQUAL",
                    "policy_id": policy,
                    "cost_scenario": "BASE_DNSE",
                    "settlement_mode": "IMMEDIATE",
                    "period_start_day": period_start.isoformat(),
                    "period_end_day": end.isoformat(),
                    "strategy_return": value,
                    "benchmark_return": 0.0,
                })
                daily.append({
                    "variant_id": "TEST", "allocator": "EQUAL", "policy_id": policy,
                    "cost_scenario": "BASE_DNSE", "settlement_mode": "IMMEDIATE",
                    "day": end.isoformat(), "nav_close_vnd": 1_000_000_000.0 * (1.0 + index * 0.01),
                })
            year = current.year + (current.month // 12)
            month = current.month % 12 + 1
            current = date(year, month, 28)
        first = v72.policy_inference(rows, daily, signflip_samples=200, bootstrap_samples=200)
        for row in rows:
            if str(row["period_end_day"]).startswith("2026-") and row["policy_id"] != "NO_OVERLAY":
                row["strategy_return"] = -0.90
        second = v72.policy_inference(rows, daily, signflip_samples=200, bootstrap_samples=200)
        self.assertAlmostEqual(float(first[0]["mean_monthly_return_delta"]), float(second[0]["mean_monthly_return_delta"]), places=15)
        self.assertAlmostEqual(float(first[0]["signflip_two_sided_p"]), float(second[0]["signflip_two_sided_p"]), places=15)
        self.assertFalse(first[0]["year_2026_used_for_selection"])

    def test_end_to_end_no_overlay_reconstructs_v70_and_writes_profit_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"
            v68_out, v70_out, v72_out = root / "v68", root / "v70", root / "v72"
            build_store(store)
            report68 = v68.run_consolidated(store=store, output_dir=v68_out, search_roots=[], allow_network=False, bootstrap_samples=30)
            self.assertEqual(report68["status"], "SUCCESS")
            report70 = v70.analyze(v68_output=v68_out, store=store, output_dir=v70_out)
            self.assertEqual(report70["status"], "SUCCESS")
            report72 = v72.analyze(v68_output=v68_out, v70_output=v70_out, store=store, output_dir=v72_out,
                                   signflip_samples=100, bootstrap_samples=100)
            self.assertEqual(report72["status"], "SUCCESS")
            self.assertEqual(report72["champion_model"], v72.CHAMPION_MODEL)
            self.assertFalse(report72["champion_replaced"])
            self.assertFalse(report72["year_2026_used_for_candidate_selection"])
            self.assertFalse(report72["promotion_authorized"])
            audit = report72["baseline_reconstruction_audit"]
            self.assertLessEqual(float(audit["max_total_return_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_cagr_error"]), 1e-10)
            self.assertLessEqual(float(audit["max_mdd_error"]), 1e-10)
            for name in (
                "v72_backtest_summary.csv", "v72_monthly_returns.csv", "v72_annual_returns.csv",
                "v72_rolling_alpha.csv", "v72_policy_inference.csv", "v72_2026_shadow.csv",
                "v72_cost_drag.csv", "v72_capital_sensitivity.csv", "v72_overlay_actions.csv",
                "v72_trade_ledger_base.csv.gz", "v72_daily_equity_base.csv.gz", "v72_report.json",
            ):
                self.assertTrue((v72_out / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
