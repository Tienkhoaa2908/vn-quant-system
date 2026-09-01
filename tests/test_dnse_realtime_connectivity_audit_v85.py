from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from he_thong_dinh_luong import dnse_realtime_connectivity_audit_v85 as v85


class V85SignatureTest(unittest.TestCase):
    def test_detects_legacy_nonce_and_reconnect_without_close_reset(self):
        files = {
            "stream/_stream_auth.py": '''\ndef build_auth_message():\n    nonce = int(time.time() * 1_000_000)\n    return {"nonce": nonce}\n''',
            "stream/_base_stream.py": '''\nasync def _reconnect(self):\n    for attempt in range(3):\n        try:\n            await self._connect()\n        except Exception as exc:\n            logger.warning("Reconnect attempt %d failed: %s", attempt, exc)\n''',
        }
        result = v85.detect_legacy_stream_signatures(files)
        self.assertTrue(result["nonce_integer_signature"])
        self.assertFalse(result["nonce_string_signature"])
        self.assertTrue(result["reconnect_missing_close_reset_signature"])
        self.assertTrue(result["reconnect_warning_signature"])
        self.assertTrue(result["legacy_sdk_reconnect_bug_signature"])

    def test_new_style_nonce_and_reconnect_cleanup_do_not_match_legacy_bug(self):
        files = {
            "websocket/auth.py": '''\ndef create_auth_message():\n    nonce = str(int(time.time() * 1000000))\n    return {"nonce": nonce}\n''',
            "websocket/connection.py": '''\nasync def _reconnect(self):\n    if self._ws:\n        await self._ws.close()\n    self._ws = None\n    await self._connect()\n''',
        }
        result = v85.detect_legacy_stream_signatures(files)
        self.assertFalse(result["nonce_integer_signature"])
        self.assertTrue(result["nonce_string_signature"])
        self.assertTrue(result["reconnect_closes_old_socket_before_connect"])
        self.assertTrue(result["reconnect_resets_old_socket_before_connect"])
        self.assertFalse(result["reconnect_missing_close_reset_signature"])
        self.assertFalse(result["legacy_sdk_reconnect_bug_signature"])


class V85LocalScanTest(unittest.TestCase):
    def test_local_dirty_api_realtime_is_detected_without_source_exfiltration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/he_thong_dinh_luong").mkdir(parents=True)
            system = root / "vn_quant_local_system"
            local_src = system / "src/vn_quant_local"
            web = system / "web"
            local_src.mkdir(parents=True)
            web.mkdir(parents=True)
            target = local_src / "webapp.py"
            target.write_text(
                'API_SECRET="must-not-appear"\nif path == "/api/realtime":\n    return realtime()\n',
                encoding="utf-8",
            )
            with mock.patch.object(v85, "_is_tracked", return_value=True), mock.patch.object(v85, "_is_dirty", return_value=True):
                matches = v85.scan_local_realtime(root, system)
            hit = next(x for x in matches if x.path.endswith("webapp.py"))
            payload = json.dumps(v85.asdict(hit), ensure_ascii=False)
            self.assertIn("API_REALTIME", payload)
            self.assertTrue(hit.dirty)
            self.assertNotIn("must-not-appear", payload)
            self.assertEqual(hit.marker_lines["API_REALTIME"], [2])


class V85ConclusionTest(unittest.TestCase):
    def test_rest_ok_plus_legacy_signature_requires_migration_but_never_live_ready(self):
        runtime = {
            "signatures": {"legacy_sdk_reconnect_bug_signature": True},
            "dnse_distribution_version": "0.5.0",
        }
        match = v85.SourceMatch(
            path="vn_quant_local_system/src/vn_quant_local/webapp.py",
            sha256="a" * 64,
            tracked=True,
            dirty=True,
            marker_lines={"API_REALTIME": [100]},
        )
        endpoint = [{"http_status": 200, "safe_payload": {"status": "CONNECTED"}}]
        rest = {"status": "SUCCESS"}
        with mock.patch.object(v85, "inspect_dnse_runtime", return_value=runtime), \
             mock.patch.object(v85, "scan_local_realtime", return_value=[match]), \
             mock.patch.object(v85, "sample_realtime_endpoint", return_value=endpoint), \
             mock.patch.object(v85, "run_rest_smoke", return_value=rest):
            report = v85.build_audit(Path("."), Path("."), realtime_url="http://127.0.0.1/api/realtime", endpoint_samples=1, probe_rest=True)
        conclusion = report["conclusion"]
        self.assertTrue(conclusion["localhost_realtime_http_alive"])
        self.assertTrue(conclusion["rest_connectivity_ok"])
        self.assertTrue(conclusion["legacy_sdk_reconnect_bug_signature"])
        self.assertTrue(conclusion["local_realtime_implementation_untracked_or_dirty"])
        self.assertTrue(conclusion["migration_recommended"])
        self.assertFalse(conclusion["live_order_ready"])
        self.assertFalse(report["safety"]["orders_sent"])

    def test_endpoint_error_state_is_not_hidden_by_http_200(self):
        samples = [{"http_status": 200, "safe_payload": {"status": "RECONNECTING", "error": "closed"}}]
        self.assertTrue(v85._endpoint_has_unhealthy_state(samples))


if __name__ == "__main__":
    unittest.main()
