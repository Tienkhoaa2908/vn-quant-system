from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.local_workstation_v86_bridge import read_v86_realtime_status


class V86BridgeTest(unittest.TestCase):
    def test_missing_state_is_not_healthy_and_never_live_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = read_v86_realtime_status(Path(tmp))
        self.assertEqual(result["status"], "NOT_INSTALLED_OR_NOT_STARTED")
        self.assertFalse(result["process_alive"])
        self.assertFalse(result["live_order_ready"])

    def test_fresh_healthy_state_passes_semantic_status_but_live_orders_stay_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "data/state/dnse_realtime_v86.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "status": "HEALTHY",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "process_alive": True,
                "transport_connected": True,
                "authenticated": True,
                "subscriptions_active": True,
                "heartbeat_healthy": True,
                "live_order_ready": True,
                "trading_token_requested": True,
                "orders_sent": True,
            }), encoding="utf-8")
            result = read_v86_realtime_status(root)
        self.assertEqual(result["status"], "HEALTHY")
        self.assertTrue(result["transport_connected"])
        self.assertFalse(result["live_order_ready"])
        self.assertFalse(result["trading_token_requested"])
        self.assertFalse(result["orders_sent"])

    def test_stale_process_claim_fails_closed_even_if_file_says_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "data/state/dnse_realtime_v86.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "status": "HEALTHY",
                "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(),
                "process_alive": True,
                "transport_connected": True,
                "authenticated": True,
                "subscriptions_active": True,
                "heartbeat_healthy": True,
            }), encoding="utf-8")
            result = read_v86_realtime_status(root)
        self.assertEqual(result["status"], "DEGRADED_STALE_PROCESS_STATE")
        self.assertFalse(result["process_alive"])
        self.assertFalse(result["transport_connected"])
        self.assertFalse(result["authenticated"])
        self.assertFalse(result["subscriptions_active"])
        self.assertFalse(result["heartbeat_healthy"])
        self.assertFalse(result["live_order_ready"])


if __name__ == "__main__":
    unittest.main()
