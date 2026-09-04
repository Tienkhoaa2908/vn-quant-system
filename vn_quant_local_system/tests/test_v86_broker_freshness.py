from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_SRC = REPO_ROOT / "src"
WORKSTATION_SRC = REPO_ROOT / "vn_quant_local_system" / "src"
for source_path in (REPO_SRC, WORKSTATION_SRC):
    if str(source_path) not in sys.path:
        sys.path.insert(0, str(source_path))

from vn_quant_local import v86_broker_freshness as v86  # noqa: E402


class V86BrokerFreshnessTests(unittest.TestCase):
    def test_market_hours_empty_after_nonempty_fails_closed(self) -> None:
        selected = {
            "raw_position_count": 0,
            "open_position_count": 0,
        }
        now = datetime.fromisoformat("2026-09-04T10:15:00+07:00")
        with self.assertRaisesRegex(
            ValueError,
            "DNSE_POSITIONS_EMPTY_DURING_MARKET_HOURS_PRESERVE_LAST_GOOD",
        ):
            v86._validate_selected_account(
                selected,
                previous_position_count=7,
                now_vn=now,
            )

    def test_empty_after_nonempty_is_allowed_outside_market_hours(self) -> None:
        selected = {
            "raw_position_count": 0,
            "open_position_count": 0,
        }
        now = datetime.fromisoformat("2026-09-04T20:15:00+07:00")
        result = v86._validate_selected_account(
            selected,
            previous_position_count=7,
            now_vn=now,
        )
        self.assertEqual(result["open_position_count"], 0)

    def test_old_eod_is_degraded_even_when_capture_is_fresh(self) -> None:
        now = datetime.fromisoformat("2026-09-04T13:45:40+07:00")
        result = v86.broker_freshness_summary(
            {
                "captured_at": "2026-09-04T13:45:37+07:00",
                "market_day": "2026-08-21",
                "position_count": 7,
            },
            {"status": "SUCCESS", "attempted_at": "2026-09-04T13:45:35+07:00"},
            now_vn=now,
        )
        self.assertEqual(result["status"], "DEGRADED")
        self.assertIn("EOD_VALUATION_ABSOLUTELY_STALE", result["flags"])
        self.assertNotIn("HOLDINGS_CAPTURE_STALE_DURING_MARKET_HOURS", result["flags"])
        self.assertEqual(result["valuation_age_calendar_days"], 14)

    def test_old_holdings_capture_during_market_hours_is_degraded(self) -> None:
        now = datetime.fromisoformat("2026-09-04T13:45:40+07:00")
        result = v86.broker_freshness_summary(
            {
                "captured_at": "2026-09-04T13:00:00+07:00",
                "market_day": "2026-09-03",
                "position_count": 7,
            },
            {"status": "SUCCESS"},
            now_vn=now,
        )
        self.assertIn("HOLDINGS_CAPTURE_STALE_DURING_MARKET_HOURS", result["flags"])

    def test_health_file_never_needs_broker_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health.json"
            v86._atomic_json(path, {"status": "FAILED", "error_code": "TimeoutError"})
            data = path.read_text(encoding="utf-8")
            self.assertIn("TimeoutError", data)
            self.assertNotIn("api_secret", data)
            self.assertNotIn("api_key", data)

    def test_sync_failure_is_recorded_and_re_raised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            health_path = Path(tmp) / "health.json"
            with patch.object(v86, "HEALTH_PATH", health_path), patch.object(
                v86,
                "_latest_raw_snapshot",
                return_value={
                    "snapshot_id": "broker-old",
                    "captured_at": "2026-09-04T12:00:00+07:00",
                    "position_count": 7,
                },
            ):
                old = v86._ORIGINAL_SYNC
                v86._ORIGINAL_SYNC = lambda: (_ for _ in ()).throw(TimeoutError("network"))
                try:
                    with self.assertRaises(TimeoutError):
                        v86._sync_broker_portfolio_v86()
                finally:
                    v86._ORIGINAL_SYNC = old
                state = v86._read_health(health_path)
                self.assertEqual(state["status"], "FAILED")
                self.assertEqual(state["error_code"], "TimeoutError")
                self.assertEqual(state["previous_position_count"], 7)


if __name__ == "__main__":
    unittest.main()
