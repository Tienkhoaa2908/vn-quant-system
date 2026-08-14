from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from he_thong_dinh_luong import c3_tactical_terminal_v78 as v78


class TestC3TacticalTerminalV78(unittest.TestCase):
    def _row(self, symbol: str, canonical: int, preview: int, **kwargs):
        row = {
            "symbol": symbol,
            "canonical_rank": canonical,
            "preview_rank": preview,
            "preview_score": 1.0 / max(1, preview),
            "relative_5": 0.0,
            "drawdown_20": 0.0,
            "drawdown_60": 0.0,
            "volume_ratio_5_20": 1.0,
            "eligible_now": True,
            "ridge_monthly_top10": False,
        }
        row.update(kwargs)
        return row

    def test_exact_l15_requires_persistence_relative_and_volume(self):
        rows = [self._row(f"H{i}", i, i + 8) for i in range(1, 11)]
        rows += [self._row("NEW", 18, 2, relative_5=0.031, volume_ratio_5_20=1.20)]
        decorated, pair = v78.classify_tactical_rows(rows, prior_preview_rank={"NEW": 7})
        by = {row["symbol"]: row for row in decorated}
        self.assertEqual(by["NEW"]["action"], "L15_SWAP_IN_CANDIDATE")
        self.assertTrue(pair["active"])
        self.assertEqual(pair["leader"], "NEW")
        self.assertEqual(pair["swap_out"], "H10")
        self.assertEqual(by["H10"]["action"], "L15_SWAP_OUT_CANDIDATE")
        self.assertTrue(pair["advisory_only"])

    def test_emerging_without_prior_week_is_watch_not_swap(self):
        rows = [self._row(f"H{i}", i, i) for i in range(1, 11)]
        rows += [self._row("NEW", 20, 1, relative_5=0.04, volume_ratio_5_20=1.5)]
        decorated, pair = v78.classify_tactical_rows(rows, prior_preview_rank={})
        by = {row["symbol"]: row for row in decorated}
        self.assertEqual(by["NEW"]["action"], "WATCH_EMERGING")
        self.assertFalse(by["NEW"]["l15_trigger"])
        self.assertFalse(pair["active"])

    def test_prior_month_top10_r08_is_alert_not_auto_sell(self):
        rows = [self._row("OLD", 3, 24, drawdown_60=-0.15, drawdown_20=-0.06)]
        decorated, pair = v78.classify_tactical_rows(rows)
        self.assertEqual(decorated[0]["action"], "RISK_ALERT_R08")
        self.assertTrue(decorated[0]["r08_trigger"])
        self.assertFalse(pair["active"])

    def test_recent_windows_are_fixed_and_compounded(self):
        rows = []
        for i in range(1, 19):
            end = date(2025 + (i - 1) // 12, ((i - 1) % 12) + 1, 28)
            start = date(end.year, end.month, 1)
            for policy, ret in (("NO_OVERLAY", 0.01), ("L15_SWAP50_WORST", 0.02)):
                rows.append({
                    "policy_id": policy,
                    "period_start_day": start.isoformat(),
                    "period_end_day": end.isoformat(),
                    "strategy_return": ret,
                    "benchmark_return": 0.005,
                })
        out = v78.recent_window_summary(
            rows,
            policy_field="policy_id",
            baseline_id="NO_OVERLAY",
            candidate_ids=("L15_SWAP50_WORST",),
        )
        self.assertEqual({row["window_months"] for row in out}, {6, 12, 18})
        for row in out:
            self.assertGreater(row["candidate_minus_baseline"], 0)
            self.assertEqual(row["selection_role"], "RECENT_REGIME_EVIDENCE_ONLY")

    def test_prior_preview_comes_from_prior_iso_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            preview_dir = state / "previews"; preview_dir.mkdir()
            v78._write_csv(preview_dir / "2026-08-10.csv", [{"symbol": "AAA", "preview_rank": 3}])
            v78._write_csv(preview_dir / "2026-08-11.csv", [{"symbol": "AAA", "preview_rank": 2}])
            v78._write_csv(preview_dir / "2026-08-07.csv", [{"symbol": "AAA", "preview_rank": 8}])
            prior = v78._prior_week_preview(state, date(2026, 8, 13))
            self.assertEqual(prior["AAA"], 8)


if __name__ == "__main__":
    unittest.main()
