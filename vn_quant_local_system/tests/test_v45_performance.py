from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vn_quant_local.performance import (
    _ensure_schema,
    _event_hash,
    _week_key,
    _xirr,
    start_observatory,
)


class V45PerformanceTests(unittest.TestCase):
    def test_schema_is_additive_and_idempotent(self) -> None:
        db = sqlite3.connect(":memory:")
        try:
            _ensure_schema(db)
            _ensure_schema(db)
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            db.close()
        self.assertIn("performance_config", tables)
        self.assertIn("performance_events", tables)
        self.assertIn("performance_nav", tables)
        self.assertIn("performance_shadow_trades", tables)

    def test_event_hash_is_stable_and_sensitive(self) -> None:
        left = _event_hash({"type": "DEPOSIT", "amount": 250_000})
        right = _event_hash({"amount": 250_000, "type": "DEPOSIT"})
        changed = _event_hash({"type": "DEPOSIT", "amount": 300_000})
        self.assertEqual(left, right)
        self.assertNotEqual(left, changed)

    def test_first_plan_week_key(self) -> None:
        self.assertEqual(
            _week_key("2026-08-04T09:00:00+07:00"),
            "2026-W32",
        )

    def test_xirr_for_one_year_double(self) -> None:
        value = _xirr(
            [
                (date(2025, 1, 1), -100.0),
                (date(2026, 1, 1), 200.0),
            ]
        )
        self.assertIsNotNone(value)
        self.assertAlmostEqual(float(value), 1.0, places=5)

    def test_start_writes_full_config_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "state.sqlite3"

            @contextmanager
            def temporary_state_db():
                db = sqlite3.connect(db_path)
                db.row_factory = sqlite3.Row
                try:
                    yield db
                    db.commit()
                finally:
                    db.close()

            broker = {
                "snapshot_id": "broker-test",
                "market_day": "2026-08-04",
                "planner_cash_vnd": 945.0,
                "net_asset_value_vnd": 1_000_000.0,
                "positions": [
                    {
                        "symbol": "MBB",
                        "quantity": 15,
                        "valuation_price_vnd": 25_000.0,
                        "average_cost_vnd": 22_000.0,
                    }
                ],
            }
            with (
                patch(
                    "vn_quant_local.performance.state_db",
                    temporary_state_db,
                ),
                patch(
                    "vn_quant_local.performance.latest_broker_portfolio",
                    return_value=broker,
                ),
                patch(
                    "vn_quant_local.performance._market_days",
                    return_value=["2026-08-04"],
                ),
                patch(
                    "vn_quant_local.performance.load_config",
                    return_value={
                        "performance": {
                            "shadow_cost_bps": 50.0,
                            "sell_tax_bps": 10.0,
                        }
                    },
                ),
                patch(
                    "vn_quant_local.performance.refresh_performance",
                    return_value={"status": "ACTIVE"},
                ),
                patch(
                    "vn_quant_local.performance.performance_status",
                    return_value={"status": "ACTIVE"},
                ),
            ):
                result = start_observatory(
                    classifications={"MBB": "LEGACY_EXCLUDED"},
                    start_day="2026-08-04",
                )
            self.assertEqual(result["status"], "ACTIVE")
            db = sqlite3.connect(db_path)
            try:
                config = db.execute(
                    "SELECT * FROM performance_config"
                ).fetchone()
                opening = db.execute(
                    """
                    SELECT symbol,classification
                    FROM performance_opening_positions
                    """
                ).fetchone()
            finally:
                db.close()
            self.assertIsNotNone(config)
            self.assertEqual(config[4], "2026-08-04")
            self.assertEqual(config[6], 945.0)
            self.assertEqual(opening, ("MBB", "LEGACY_EXCLUDED"))


if __name__ == "__main__":
    unittest.main()
