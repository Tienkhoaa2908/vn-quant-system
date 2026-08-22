from __future__ import annotations

import unittest
from pathlib import Path

from he_thong_dinh_luong import existing_web_v83_installer as v83


class V83InstallerTest(unittest.TestCase):
    def test_patch_repo_approved_index_is_additive_and_idempotent(self):
        text=Path("vn_quant_local_system/web/index.html").read_text(encoding="utf-8")
        once=v83.patch_index(text); twice=v83.patch_index(once)
        self.assertEqual(once,twice)
        self.assertIn("V83_CAPITAL_DISCIPLINE_EXISTING_WEB",once)
        self.assertIn('/capital_discipline_v83.js',once)
        self.assertIn('/capital_discipline_v83.css',once)

    def test_patch_webapp_adds_read_only_endpoint_without_order_surface(self):
        text=Path("vn_quant_local_system/src/vn_quant_local/webapp.py").read_text(encoding="utf-8")
        once=v83.patch_webapp(text); twice=v83.patch_webapp(once)
        self.assertEqual(once,twice)
        self.assertIn("V83_CAPITAL_DISCIPLINE_BRIDGE_IMPORT",once)
        self.assertIn('elif path == "/api/dashboard-v83":',once)
        lowered=once.lower()
        self.assertNotIn("/api/order-v83",lowered)
        self.assertNotIn("place_order_v83",lowered)


if __name__ == "__main__":
    unittest.main()
