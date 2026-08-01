from __future__ import annotations

import importlib
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.model_lab_job import run_job
from he_thong_dinh_luong.model_lab_web_state import load_model_lab_state


class ModelLabVisibleJobTests(unittest.TestCase):
    def test_missing_input_still_creates_visible_failed_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "model-lab-live" / "runs" / "run-1"
            with self.assertRaises(FileNotFoundError):
                run_job(
                    repo_root=root,
                    data_root=root,
                    input_zip=root / "missing.zip",
                    output_dir=output,
                    models=("momentum_baseline",),
                    evaluation_months=24,
                    top_k=10,
                )
            status_path = output / "run_status.json"
            self.assertTrue(status_path.is_file())
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "FAILED")
            self.assertEqual(status["phase"], "PREFLIGHT")
            self.assertFalse(status["credentials_recorded"])

    def test_web_state_reads_running_run_without_final_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "model-lab-live" / "runs" / "run-1"
            run.mkdir(parents=True)
            (run / "run_status.json").write_text(
                json.dumps({
                    "status": "RUNNING",
                    "phase": "WALK_FORWARD_BACKTEST",
                    "progress": 0.4,
                    "message": "running",
                    "artifacts_dir": str(run / "artifacts"),
                }),
                encoding="utf-8",
            )
            state = load_model_lab_state(root)
            self.assertTrue(state["available"])
            self.assertEqual(state["status"], "RUNNING")
            self.assertEqual(state["phase"], "WALK_FORWARD_BACKTEST")
            self.assertEqual(state["leaderboard"], [])


class UnifiedTerminalSourceTests(unittest.TestCase):
    def test_entrypoint_loads_current_terminal(self):
        source = Path("src/he_thong_dinh_luong/giao_dien_web.py").read_text(encoding="utf-8")
        self.assertIn("web_console_app_v9", source)
        module = importlib.import_module("he_thong_dinh_luong.giao_dien_web")
        self.assertTrue(callable(module.main))

    def test_main_interface_owns_model_lab_workflow(self):
        source = Path("src/he_thong_dinh_luong/web_console_app_v8.py").read_text(encoding="utf-8")
        self.assertIn("CẬP NHẬT TOÀN BỘ", source)
        self.assertIn("load_handoff", source)
        self.assertIn("research_input_path", source)
        self.assertIn("model-lab-live", source)
        self.assertNotIn('str(config.data_root / "prediction_input.zip")', source)
        self.assertNotIn('"uv", "run"', source)

    def test_v9_adds_frozen_reference_contribution_planner(self):
        source = Path("src/he_thong_dinh_luong/web_console_app_v9.py").read_text(encoding="utf-8")
        self.assertIn("GÓP VỐN ĐỊNH KỲ", source)
        self.assertIn("load_latest_reference_target", source)
        self.assertIn("ContributionPlanRequest", source)
        self.assertIn("buy_fee_bps=Decimal(\"2.7\")", source)
        self.assertIn("slippage_bps=Decimal(\"5\")", source)
        self.assertIn("trading_enabled", source)


if __name__ == "__main__":
    unittest.main()
