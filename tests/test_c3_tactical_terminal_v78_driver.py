from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from he_thong_dinh_luong import c3_tactical_terminal_v78_driver as driver


class TestC3TacticalTerminalV78Driver(unittest.TestCase):
    def test_ineligible_incumbent_fallback_remains_visible_and_risk_alerts(self):
        with patch.object(driver.v76, "_raw_features", return_value={
            "relative_5": -0.05,
            "drawdown_20": -0.10,
            "drawdown_60": -0.16,
            "log_volume_ratio_5_20": 0.0,
        }):
            row = driver._incumbent_fallback_row(
                object(),
                symbol="OLD",
                canonical_rank=2,
                capture_day=date(2026, 8, 13),
                ridge_monthly_top10=set(),
            )
        self.assertFalse(row["eligible_now"])
        self.assertIsNone(row["preview_rank"])
        decorated, _ = driver.core.classify_tactical_rows([row])
        self.assertEqual(decorated[0]["action"], "RISK_ALERT_R08")
        self.assertEqual(decorated[0]["symbol"], "OLD")

    def test_period_performance_uses_next_open_to_current_close(self):
        entry = date(2026, 8, 3); current = date(2026, 8, 13)
        market = SimpleNamespace(
            cal=[entry, current],
            so={("AAA", entry): 100.0},
            sc={("AAA", current): 90.0},
            io={entry: 1000.0},
            ic={current: 1020.0},
        )
        perf = driver._period_performance(
            market, "AAA", source_signal_day=date(2026, 7, 31), capture_day=current,
        )
        self.assertEqual(perf["period_entry_day"], "2026-08-03")
        self.assertAlmostEqual(perf["period_return"], -0.10)
        self.assertAlmostEqual(perf["period_benchmark_return"], 0.02)
        self.assertAlmostEqual(perf["period_relative_return"], -0.12)

    def test_end_to_end_preserves_core_and_emits_operational_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "market.sqlite3"; store.write_bytes(b"fixture")
            v77_state = root / "v77"; v77_state.mkdir()
            tactical_state = root / "v78-state"
            output = root / "out"
            symbols = [f"S{i:02d}" for i in range(12)]
            (v77_state / "freeze_manifest.json").write_text(json.dumps({
                "champion_model": driver.core.OPERATIONAL_CHAMPION,
                "shadow_model": driver.core.SECONDARY_MODEL,
                "variant_symbols": symbols,
            }), encoding="utf-8")
            monthly = [{"symbol": symbol, "rank": i + 1, "score": 1 - i / 20} for i, symbol in enumerate(symbols)]
            ridge = [{"symbol": symbol, "rank": i + 1, "score": 2 - i / 20} for i, symbol in enumerate(reversed(symbols))]
            ridge.sort(key=lambda row: row["rank"])
            rank_snapshot = {
                "source_signal_day": "2026-07-31",
                "risk_on": False,
                "c3_weights": {"low_volatility": .24, "relative_strength_120": .37, "high_52_week": .39},
                "rankings": {
                    driver.core.OPERATIONAL_CHAMPION: monthly,
                    driver.core.SECONDARY_MODEL: ridge,
                },
            }
            preview = []
            for i, symbol in enumerate(symbols):
                preview.append({
                    "evaluation_day": "2026-08-13", "symbol": symbol,
                    "canonical_rank": i + 1, "preview_rank": i + 1,
                    "preview_score": 1 - i / 20, "rank_delta": 0,
                    "eligible_now": True, "relative_5": 0.01,
                    "drawdown_20": 0.0, "drawdown_60": 0.0,
                    "volume_ratio_5_20": 1.0, "ridge_monthly_top10": False,
                })
            entry = date(2026, 8, 13)
            fake_market = SimpleNamespace(
                cal=[entry],
                so={(symbol, entry): 100.0 for symbol in symbols},
                sc={(symbol, entry): (90.0 if symbol == "S00" else 101.0) for symbol in symbols},
                io={entry: 1000.0},
                ic={entry: 1005.0},
            )
            with patch.object(driver.v70, "load_market", return_value=fake_market), \
                 patch.object(driver.v77, "_build_rank_snapshot", return_value=rank_snapshot), \
                 patch.object(driver.core, "_build_preview", return_value=preview):
                report = driver.run(
                    store=store,
                    v77_state_dir=v77_state,
                    tactical_state_dir=tactical_state,
                    output_dir=output,
                )
            self.assertEqual(report["operational_champion"], "C3_STABLE_3_PAST_IC_SHRUNK")
            self.assertTrue(report["operational_champion_finalized"])
            self.assertFalse(report["live_orders_allowed"])
            self.assertTrue(report["incumbent_visibility_fail_closed"])
            self.assertIn("S00", report["dragging_incumbents"])
            self.assertTrue((output / "v78_report.json").is_file())
            self.assertTrue((output / "v78_tactical_rows.csv").is_file())
            self.assertTrue((tactical_state / "previews" / "2026-08-13.csv").is_file())


if __name__ == "__main__":
    unittest.main()
