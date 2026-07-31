from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.model_lab_runner_v2 import score_diagnostics
from he_thong_dinh_luong.workflow_handoff import (
    latest_final_research_input,
    load_handoff,
    research_input_signal_date,
    write_handoff,
)


def _research_zip(path: Path, signal: str) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "feature_raw.csv",
            "ngay,ma,hop_le\n2026-07-24,AAA,true\n" + f"{signal},BBB,true\n",
        )


class ScoreQualityGateTests(unittest.TestCase):
    def test_constant_and_near_constant_scores_are_degenerate(self):
        self.assertTrue(score_diagnostics([0.1, 0.1, 0.1])["degenerate"])
        self.assertTrue(score_diagnostics([1.0, 1.0 + 1e-14, 1.0])["degenerate"])
        self.assertFalse(score_diagnostics([0.1, 0.2, 0.3])["degenerate"])


class ResearchHandoffTests(unittest.TestCase):
    def test_discovers_latest_final_package_not_static_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _research_zip(root / "prediction_input.zip", "2026-07-31")
            with self.assertRaises(FileNotFoundError):
                latest_final_research_input(root)

            old = root / "eod-old"
            new = root / "eod-new"
            old.mkdir()
            new.mkdir()
            _research_zip(old / "daily_prediction_input.zip", "2026-07-29")
            _research_zip(new / "daily_prediction_input.zip", "2026-07-30")
            for folder in (old, new):
                (folder / "manifest.json").write_text(
                    json.dumps({"status": "SUCCESS"}), encoding="utf-8"
                )
            selected = latest_final_research_input(root)
            self.assertEqual(selected, (new / "daily_prediction_input.zip").resolve())
            self.assertEqual(research_input_signal_date(selected), date(2026, 7, 30))

    def test_handoff_validates_hash_and_signal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "market-output"
            source = root / "daily_prediction_input.zip"
            _research_zip(source, "2026-07-30")
            write_handoff(
                output_dir=output,
                resolved_mode="final",
                research_input=source,
                market_session=date(2026, 7, 30),
                research_scope="CURRENT_FINAL_EOD",
            )
            loaded = load_handoff(output)
            self.assertEqual(loaded["research_input_signal_date"], "2026-07-30")
            self.assertFalse(loaded["static_prediction_input_fallback_used"])
            source.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                load_handoff(output)

    def test_final_signal_mismatch_is_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "daily_prediction_input.zip"
            _research_zip(source, "2026-07-29")
            with self.assertRaises(ValueError):
                write_handoff(
                    output_dir=root / "out",
                    resolved_mode="final",
                    research_input=source,
                    market_session=date(2026, 7, 30),
                    research_scope="CURRENT_FINAL_EOD",
                )


class TerminalV8ContractTests(unittest.TestCase):
    def test_entrypoint_uses_v8_and_v8_uses_handoff(self):
        import he_thong_dinh_luong.giao_dien_web as entrypoint
        import he_thong_dinh_luong.web_console_app_v8 as terminal

        self.assertIs(entrypoint.build_app, terminal.build_app)
        source = Path(terminal.__file__).read_text(encoding="utf-8")
        self.assertIn("load_handoff", source)
        self.assertIn("research_input_path", source)
        self.assertNotIn('str(config.data_root / "prediction_input.zip")', source)


if __name__ == "__main__":
    unittest.main()
