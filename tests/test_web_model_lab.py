from __future__ import annotations

import importlib
from pathlib import Path
import unittest


class WebModelLabIntegrationTests(unittest.TestCase):
    def test_entrypoint_loads_v6_without_importing_nicegui(self):
        module = importlib.import_module("he_thong_dinh_luong.giao_dien_web")
        self.assertEqual(module.NICEGUI_VERSION, "3.14.0")
        self.assertTrue(callable(module.main))
        self.assertTrue(callable(module.build_app))

    def test_model_lab_page_has_no_credential_arguments(self):
        source = Path("src/he_thong_dinh_luong/web_model_lab.py").read_text(encoding="utf-8")
        self.assertIn('"/model-lab"', source)
        self.assertIn("he_thong_dinh_luong.model_lab", source)
        self.assertNotIn("DNSE_API_SECRET", source)
        self.assertNotIn("--api-secret", source)
        self.assertNotIn("--api-key", source)

    def test_model_lab_command_pins_optional_workstation_dependencies(self):
        source = Path("src/he_thong_dinh_luong/web_model_lab.py").read_text(encoding="utf-8")
        self.assertIn('"lightgbm==4.7.0"', source)
        self.assertIn('"xgboost==3.3.0"', source)
        self.assertIn('"torch==2.12.1"', source)


if __name__ == "__main__":
    unittest.main()
