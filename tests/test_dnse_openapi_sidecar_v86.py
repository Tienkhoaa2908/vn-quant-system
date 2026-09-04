from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import dnse_openapi_sidecar_v86 as v86


class _Conn:
    is_connected = True


class _Client:
    def __init__(self):
        self._connection = _Conn()
        self._is_authenticated = True
        self._subscriptions = {"tick.G1.msgpack": {"symbols": ["VPI"]}}
        self._last_pong_time = time.time()
        self.heartbeat_interval = 25.0

    @property
    def is_healthy(self):
        return True


class _Trade:
    symbol = "VPI"
    price = 63700
    volume = 100


class V86SidecarTest(unittest.TestCase):
    def test_runtime_contract_pins_new_distribution_and_api_date(self):
        with patch.object(v86, "_dist_version", side_effect=lambda name: "1.4.6" if name == "dnse-sdk-openapi" else None):
            result = v86.runtime_contract()
        self.assertTrue(result["sdk_version_ok"])
        self.assertFalse(result["legacy_dnse_distribution_present"])
        self.assertEqual(result["api_version"], "2026-05-07")
        self.assertEqual(result["ws_base"], "wss://ws-openapi.dnse.com.vn")

    def test_symbols_are_uppercase_deduplicated_and_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "symbols.json"
            path.write_text(json.dumps({"symbols": ["vpi", "VPI", "msb", "", "a*b"]}), encoding="utf-8")
            self.assertEqual(v86._symbols(path), ["VPI", "MSB"])

    def test_state_is_healthy_only_with_transport_auth_subscription_heartbeat_and_fresh_tick(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = v86.State(Path(tmp) / "state.json", ["VPI"], "msgpack")
            state.client = _Client()
            state.on_trade(_Trade())
            during_market = datetime(2026, 9, 1, 10, 0, tzinfo=v86.VN_TZ)
            with patch.object(v86, "_market_window_vn", return_value=True):
                snap = state.snapshot()
            self.assertEqual(snap["status"], "HEALTHY")
            self.assertTrue(snap["transport_connected"])
            self.assertTrue(snap["authenticated"])
            self.assertTrue(snap["subscriptions_active"])
            self.assertTrue(snap["heartbeat_healthy"])
            self.assertLess(snap["last_tick_age_sec"], 1.0)
            self.assertFalse(snap["live_order_ready"])
            self.assertFalse(snap["trading_token_requested"])
            self.assertFalse(snap["orders_sent"])
            self.assertIsNotNone(during_market)  # documents intended session context

    def test_stale_tick_is_degraded_inside_market_but_idle_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = v86.State(Path(tmp) / "state.json", ["VPI"], "msgpack")
            state.client = _Client()
            state.last_tick_epoch = time.time() - 60
            with patch.object(v86, "_market_window_vn", return_value=True):
                self.assertEqual(state.snapshot()["status"], "DEGRADED_STALE_TICK")
            with patch.object(v86, "_market_window_vn", return_value=False):
                self.assertEqual(state.snapshot()["status"], "IDLE_MARKET_CLOSED")

    def test_atomic_state_never_contains_credentials_or_live_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = v86.State(path, ["VPI"], "msgpack")
            state.persist(final_status="STOPPED")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("api_secret", text.lower())
            self.assertNotIn("api_key", text.lower())
            data = json.loads(text)
            self.assertFalse(data["live_order_ready"])
            self.assertFalse(data["private_order_stream_subscribed"])
            self.assertFalse(data["private_position_stream_subscribed"])


if __name__ == "__main__":
    unittest.main()
