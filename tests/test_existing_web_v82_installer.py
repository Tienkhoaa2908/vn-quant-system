from __future__ import annotations

from pathlib import Path
import unittest

from he_thong_dinh_luong import existing_web_v82_installer as v82


class V82InstallerPatchTest(unittest.TestCase):
    def test_patch_index_is_additive_and_idempotent(self):
        text = (
            '  <link rel="stylesheet" href="/performance_v51.css">\n'
            '  <script src="/performance_v51.js"></script>\n'
        )
        first = v82.patch_index(text)
        second = v82.patch_index(first)
        self.assertEqual(first, second)
        self.assertIn('V78_TACTICAL_EXISTING_WEB', first)
        self.assertIn('V82_PROFIT_PAPER_EXISTING_WEB', first)
        self.assertIn('/tactical_v78.js', first)
        self.assertIn('/tactical_profit_v82.js', first)

    def test_patch_repo_approved_index_contract(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'vn_quant_local_system' / 'web' / 'index.html').read_text(encoding='utf-8')
        patched = v82.patch_index(source)
        self.assertIn('V78_TACTICAL_EXISTING_WEB', patched)
        self.assertIn('V82_PROFIT_PAPER_EXISTING_WEB', patched)
        self.assertEqual(patched, v82.patch_index(patched))

    def test_patch_webapp_adds_read_only_endpoint_and_no_order_surface(self):
        text = (
            'from urllib.parse import parse_qs, urlparse\n'
            '\ndef _refresh_market_signals() -> dict[str, object]:\n'
            '    return {}\n'
            '        "market_sync": market_sync,\n'
            '        "canonical": canonical,\n'
            '        "preview": {\n'
            '                "/performance_v51.css",\n'
            'value["signal_refresh"] = signal_refresh_status()\n'
            '            elif path == "/api/performance":\n'
            '                self._send_json(performance_status())\n'
            '                "/api/performance/refresh": refresh_performance,\n'
        )
        first = v82.patch_webapp(text)
        second = v82.patch_webapp(first)
        self.assertEqual(first, second)
        self.assertIn('V82_PROFIT_PAPER_BRIDGE_IMPORT', first)
        self.assertIn('elif path == "/api/dashboard-v82":', first)
        self.assertIn('read_v82_dashboard(SYSTEM_ROOT)', first)
        self.assertNotIn('send_order', first.lower())
        self.assertNotIn('place_order', first.lower())


if __name__ == "__main__":
    unittest.main()
