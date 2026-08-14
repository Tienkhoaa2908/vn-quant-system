from __future__ import annotations

from datetime import date
import sqlite3
import unittest

from vn_quant_local import c3_model, weekly_plan
from vn_quant_local.model_safety import completed_month_signal_days, robust_signal_days
from vn_quant_local.signal_refresh import _ensure_schema, purchase_guard_map


class V47SignalRefreshTests(unittest.TestCase):
    def test_runtime_calendar_guards_are_active(self) -> None:
        self.assertIs(c3_model._signal_days, robust_signal_days)
        self.assertIs(weekly_plan._completed_month_signal_days, completed_month_signal_days)

    def test_latest_month_is_completed_after_calendar_turn(self) -> None:
        canonical, preview = robust_signal_days(
            [date(2026, 6, 30), date(2026, 7, 31)],
            today=date(2026, 8, 4),
        )
        self.assertEqual(canonical, date(2026, 7, 31))
        self.assertEqual(preview, date(2026, 7, 31))

    def test_current_month_is_not_canonical(self) -> None:
        canonical, preview = robust_signal_days(
            [date(2026, 6, 30), date(2026, 7, 31), date(2026, 8, 4)],
            today=date(2026, 8, 4),
        )
        self.assertEqual(canonical, date(2026, 7, 31))
        self.assertEqual(preview, date(2026, 8, 4))

    def test_preview_schema_is_idempotent(self) -> None:
        db = sqlite3.connect(":memory:")
        try:
            _ensure_schema(db)
            _ensure_schema(db)
            columns = {row[1] for row in db.execute("PRAGMA table_info(preview_snapshots)").fetchall()}
        finally:
            db.close()
        self.assertTrue({"snapshot_id", "signature", "market_day", "audit_json"}.issubset(columns))

    def test_purchase_guard(self) -> None:
        canonical = [
            {"symbol": "AAA", "rank": 1},
            {"symbol": "BBB", "rank": 2},
            {"symbol": "CCC", "rank": 3},
        ]
        preview = {
            "audit": {
                "AAA": {"rank": 5, "eligible": True, "reasons": [], "above_ma250": True},
                "BBB": {"rank": 24, "eligible": True, "reasons": [], "above_ma250": True},
                "CCC": {"rank": None, "eligible": False, "reasons": ["BELOW_MA250"], "above_ma250": False},
            }
        }
        guard = purchase_guard_map(canonical, preview)
        self.assertTrue(guard["AAA"]["allowed_to_buy"])
        self.assertFalse(guard["BBB"]["allowed_to_buy"])
        self.assertFalse(guard["CCC"]["allowed_to_buy"])


if __name__ == "__main__":
    unittest.main()
