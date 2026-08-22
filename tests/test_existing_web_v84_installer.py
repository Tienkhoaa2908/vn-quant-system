from __future__ import annotations

import unittest
from pathlib import Path

from he_thong_dinh_luong import existing_web_v84_installer as v84


class V84InstallerTest(unittest.TestCase):
    def test_patch_repo_approved_index_is_additive_and_idempotent(self):
        text = Path("vn_quant_local_system/web/index.html").read_text(encoding="utf-8")
        once = v84.patch_index(text)
        twice = v84.patch_index(once)
        self.assertEqual(once, twice)
        self.assertIn("V84_MAIN_DAILY_OPERATING_DASHBOARD", once)
        self.assertIn('/main_operating_v84.js', once)
        self.assertIn('/main_operating_v84.css', once)
        self.assertIn('/capital_discipline_v83.js', once)

    def test_patch_webapp_adds_static_only_and_no_new_api(self):
        text = Path("vn_quant_local_system/src/vn_quant_local/webapp.py").read_text(encoding="utf-8")
        once = v84.patch_webapp(text)
        twice = v84.patch_webapp(once)
        self.assertEqual(once, twice)
        self.assertIn('"/main_operating_v84.js"', once)
        self.assertIn('"/main_operating_v84.css"', once)
        self.assertNotIn('/api/dashboard-v84', once)
        self.assertIn('/api/dashboard-v83', once)

    def test_frontend_contract_is_advisory_and_joins_existing_read_only_surfaces(self):
        js = Path("web_extensions/v84/main_operating_v84.js").read_text(encoding="utf-8")
        self.assertIn("/api/status", js)
        self.assertIn("/api/dashboard-v83", js)
        self.assertIn("/api/tactical-v78", js)
        self.assertIn("CẢNH BÁO TĂNG VỐN", js)
        self.assertIn("ADVISORY ONLY", js)
        self.assertIn("PLAN CONFLICT", js)
        lowered = js.lower()
        for forbidden in ("place_order", "submit_order", "send_order", "broker_order"):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
