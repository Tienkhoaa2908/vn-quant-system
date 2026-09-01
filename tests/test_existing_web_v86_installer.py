from __future__ import annotations

from pathlib import Path
import unittest

from he_thong_dinh_luong import existing_web_v84_installer as v84
from he_thong_dinh_luong import existing_web_v86_installer as v86


class V86InstallerTest(unittest.TestCase):
    def test_index_patch_is_additive_and_idempotent(self):
        text = Path("vn_quant_local_system/web/index.html").read_text(encoding="utf-8")
        once = v86.patch_index(text)
        twice = v86.patch_index(once)
        self.assertEqual(once, twice)
        self.assertIn("V84_MAIN_DAILY_OPERATING_DASHBOARD", once)
        self.assertIn("V86_DNSE_OPENAPI_REALTIME_HEALTH", once)
        self.assertIn('/realtime_v86.js', once)
        self.assertIn('/realtime_v86.css', once)

    def test_webapp_replaces_legacy_realtime_get_route_and_keeps_read_only_alias(self):
        raw = Path("vn_quant_local_system/src/vn_quant_local/webapp.py").read_text(encoding="utf-8")
        base = v84.patch_webapp(raw)
        anchor = '            elif path == "/api/docs":\n'
        self.assertEqual(base.count(anchor), 1)
        legacy = (
            '            elif path == "/api/realtime":\n'
            '                self._send_json({"status": "LEGACY_THREAD_RUNNING"})\n'
        )
        base = base.replace(anchor, legacy + anchor, 1)
        once, replaced = v86.patch_webapp(base)
        twice, _ = v86.patch_webapp(once)
        self.assertTrue(replaced)
        self.assertEqual(once, twice)
        self.assertNotIn("LEGACY_THREAD_RUNNING", once)
        self.assertIn('elif path == "/api/realtime":', once)
        self.assertIn('elif path == "/api/realtime-v86":', once)
        self.assertGreaterEqual(once.count("read_v86_realtime_status(SYSTEM_ROOT)"), 2)
        self.assertIn('"/realtime_v86.js"', once)
        self.assertIn('"/realtime_v86.css"', once)

    def test_repo_without_legacy_route_gets_v86_alias_without_starting_websocket(self):
        raw = Path("vn_quant_local_system/src/vn_quant_local/webapp.py").read_text(encoding="utf-8")
        once, replaced = v86.patch_webapp(raw)
        self.assertFalse(replaced)
        self.assertIn('/api/realtime-v86', once)
        self.assertIn('read_v86_realtime_status', once)
        self.assertNotIn('start_market_realtime_v59', once)

    def test_frontend_is_health_only_and_no_order_mutation(self):
        js = Path("web_extensions/v86/realtime_v86.js").read_text(encoding="utf-8")
        self.assertIn('/api/realtime-v86', js)
        self.assertIn('HTTP 200', js)
        self.assertIn('BLOCKED', js)
        lowered = js.lower()
        for forbidden in (
            "post_order", "place_order", "cancel_order", "replace_order",
            "trading-token", "send_email_otp", "create_trading_token",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
