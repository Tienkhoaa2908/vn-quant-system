from __future__ import annotations

import unittest
from unittest.mock import patch
from datetime import date

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


if __name__ == "__main__":
    unittest.main()
