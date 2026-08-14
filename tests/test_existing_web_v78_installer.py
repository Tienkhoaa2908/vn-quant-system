from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from he_thong_dinh_luong import existing_web_v78_installer as installer
from he_thong_dinh_luong.local_workstation_v78_bridge import read_v78_tactical_snapshot


INDEX_FIXTURE = '''<!doctype html>
<html><head>
  <link rel="stylesheet" href="/performance_v51.css">
</head><body>
  <script src="/performance_v51.js"></script>
</body></html>
'''

WEBAPP_FIXTURE = '''from __future__ import annotations
from urllib.parse import parse_qs, urlparse

from .core import SYSTEM_ROOT

def _refresh_market_signals() -> dict[str, object]:
    market_sync = {}
    canonical = {}
    preview = {}
    return {
        "status": "SUCCESS",
        "market_sync": market_sync,
        "canonical": canonical,
        "preview": {
            key: preview.get(key)
            for key in ("status",)
        },
    }

class Handler:
    def do_GET(self):
        path = ""
        if path in {
                "/performance_v51.css",
        }:
            pass
        elif path == "/api/status":
            value = {}
            value["signal_refresh"] = signal_refresh_status()
            self._send_json(value)
        elif path == "/api/performance":
            self._send_json(performance_status())

    def do_POST(self):
        actions = {
                "/api/performance/refresh": refresh_performance,
        }
'''


class TestExistingWebV78Installer(unittest.TestCase):
    def _root(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp) / "vn_quant_local_system"
        (root / "web").mkdir(parents=True)
        (root / "src" / "vn_quant_local").mkdir(parents=True)
        (root / "data" / "state").mkdir(parents=True)
        (root / "validation").mkdir(parents=True)
        (root / "web" / "index.html").write_text(INDEX_FIXTURE, encoding="utf-8")
        (root / "src" / "vn_quant_local" / "webapp.py").write_text(WEBAPP_FIXTURE, encoding="utf-8")
        secret = root / "data" / "state" / "dnse_credentials.json"
        secret.write_text('{"secret":"DO_NOT_TOUCH"}', encoding="utf-8")
        assets = Path(tmp) / "assets"
        assets.mkdir()
        (assets / "tactical_v78.js").write_text("window.V78_TEST=true;\n", encoding="utf-8")
        (assets / "tactical_v78.css").write_text(".v78-test{}\n", encoding="utf-8")
        return root, assets

    def test_additive_install_is_idempotent_and_preserves_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, assets = self._root(tmp)
            secret = root / "data" / "state" / "dnse_credentials.json"
            before_secret = secret.read_bytes()
            first = installer.install(root, assets)
            self.assertTrue(first["changed"])
            self.assertFalse(first["existing_layout_replaced"])
            self.assertFalse(first["credentials_or_state_touched"])
            self.assertEqual(secret.read_bytes(), before_secret)
            self.assertTrue((root / "web" / "tactical_v78.js").is_file())
            self.assertTrue((root / "web" / "tactical_v78.css").is_file())
            index = (root / "web" / "index.html").read_text(encoding="utf-8")
            webapp = (root / "src" / "vn_quant_local" / "webapp.py").read_text(encoding="utf-8")
            self.assertIn("V78_TACTICAL_EXISTING_WEB", index)
            self.assertIn('/api/tactical-v78', webapp)
            self.assertIn('/api/actions/tactical-v78', webapp)
            second = installer.install(root, assets)
            self.assertFalse(second["changed"])
            self.assertEqual(secret.read_bytes(), before_secret)

    def test_bridge_reads_stable_snapshot_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            system = Path(tmp) / "vn_quant_local_system"
            live = system / "data" / "v78-c3-tactical"
            live.mkdir(parents=True)
            report = {
                "status": "SUCCESS",
                "operational_champion": "C3_STABLE_3_PAST_IC_SHRUNK",
                "secondary_model": "V76_RIDGE_RANK",
                "capture_day": "2026-08-13",
                "source_monthly_signal_day": "2026-07-31",
                "risk_on": False,
                "live_orders_allowed": False,
            }
            (live / "LATEST.json").write_text(json.dumps(report), encoding="utf-8")
            (live / "v78_tactical_rows.csv").write_text("symbol,canonical_rank\nMSB,2\n", encoding="utf-8")
            (live / "v78_incumbent_health.csv").write_text("symbol\nVPI\n", encoding="utf-8")
            (live / "v78_emerging_radar.csv").write_text("symbol\nTLG\n", encoding="utf-8")
            payload = read_v78_tactical_snapshot(system)
            self.assertEqual(payload["status"], "SUCCESS")
            self.assertEqual(payload["operational_champion"], "C3_STABLE_3_PAST_IC_SHRUNK")
            self.assertFalse(payload["live_orders_allowed"])
            self.assertEqual(payload["tactical_rows"][0]["symbol"], "MSB")
            self.assertEqual(payload["incumbent_health"][0]["symbol"], "VPI")
            self.assertEqual(payload["emerging_radar"][0]["symbol"], "TLG")


if __name__ == "__main__":
    unittest.main()
