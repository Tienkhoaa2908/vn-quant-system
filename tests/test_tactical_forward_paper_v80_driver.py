from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import tactical_forward_paper_v80 as core
from he_thong_dinh_luong.tactical_forward_paper_v80_driver import run
from tests.test_tactical_forward_paper_v80 import VN, _make_store, _report, _rows


class TestTacticalForwardPaperV80Driver(unittest.TestCase):
    def test_full_run_twice_ignores_frozen_rows_json_as_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = root / "market.sqlite3"
            _make_store(store, __import__("datetime").date(2026, 8, 31))
            report_path = root / "v78_report.json"
            rows_path = root / "v78_tactical_rows.csv"
            report_path.write_text(core._json_text(_report(True)), encoding="utf-8")
            core._write_csv(rows_path, _rows(True))
            state = root / "state"

            first = run(
                store=store,
                v78_report=report_path,
                v78_tactical_rows=rows_path,
                state_dir=state,
                output_dir=root / "out1",
                wall_time=datetime(2026, 8, 15, 11, 0, tzinfo=VN),
            )
            first_wall = first["current_capture_wall_time_vn"]
            self.assertEqual(first["observation_count"], 1)
            observation_files = sorted((state / "observations").glob("*.json"))
            self.assertTrue(any(path.name.endswith(".rows.json") for path in observation_files))

            second = run(
                store=store,
                v78_report=report_path,
                v78_tactical_rows=rows_path,
                state_dir=state,
                output_dir=root / "out2",
                wall_time=datetime(2026, 8, 15, 18, 0, tzinfo=VN),
            )
            self.assertEqual(second["observation_count"], 1)
            self.assertEqual(second["current_capture_wall_time_vn"], first_wall)
            self.assertEqual(second["current_observation_id"], first["current_observation_id"])
            self.assertEqual(second["action_status_counts"], first["action_status_counts"])

    def test_record_enumerator_excludes_rows_snapshot(self):
        from he_thong_dinh_luong.tactical_forward_paper_v80_driver import _observation_record_paths
        with tempfile.TemporaryDirectory() as temp_dir:
            obs = Path(temp_dir) / "observations"
            obs.mkdir()
            (obs / "a.json").write_text("{}", encoding="utf-8")
            (obs / "a.rows.json").write_text("[]", encoding="utf-8")
            (obs / "b.json").write_text("{}", encoding="utf-8")
            self.assertEqual([path.name for path in _observation_record_paths(Path(temp_dir))], ["a.json", "b.json"])


if __name__ == "__main__":
    unittest.main()
