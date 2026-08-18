from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest

# Import the synthetic V80 fixture first: on bare Windows CPython it installs
# a process-local UTC+07 fallback for Asia/Ho_Chi_Minh before production V80
# modules are imported. The workstation runtime itself still uses real ZoneInfo
# with pinned tzdata when needed.
from tests.test_tactical_forward_paper_v80 import VN, _make_store, _report, _rows
from he_thong_dinh_luong import tactical_forward_paper_v80 as core
from he_thong_dinh_luong.tactical_forward_paper_v80_driver import (
    PAPER_OPEN_TIME_VN,
    SESSION_AWARE_EXECUTION_CONTRACT,
    _execution_floor_for_wall,
    run,
)


class TestTacticalForwardPaperV80Driver(unittest.TestCase):
    def _fixture(self, root: Path, *, exact_l15: bool = True):
        store = root / "market.sqlite3"
        _make_store(store, date(2026, 8, 31))
        report_path = root / "v78_report.json"
        rows_path = root / "v78_tactical_rows.csv"
        report_path.write_text(core._json_text(_report(exact_l15)), encoding="utf-8")
        core._write_csv(rows_path, _rows(exact_l15))
        return store, report_path, rows_path

    def test_full_run_twice_ignores_frozen_rows_json_as_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store, report_path, rows_path = self._fixture(root)
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

    def test_preopen_capture_can_use_same_day_future_open(self):
        wall = datetime(2026, 8, 18, 8, 6, tzinfo=VN)
        self.assertEqual(PAPER_OPEN_TIME_VN.isoformat(), "09:00:00")
        self.assertEqual(_execution_floor_for_wall(wall), date(2026, 8, 18))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store, report_path, rows_path = self._fixture(root)
            result = run(
                store=store,
                v78_report=report_path,
                v78_tactical_rows=rows_path,
                state_dir=root / "state",
                output_dir=root / "out",
                wall_time=wall,
            )
            self.assertEqual(result["current_execution_floor_date"], "2026-08-18")
            self.assertEqual(result["current_execution_floor_contract"], SESSION_AWARE_EXECUTION_CONTRACT)
            self.assertEqual(result["paper_open_time_vn"], "09:00:00")
            actions = core._read_csv(root / "out" / "v80_actions.csv")
            swap_days = {
                row["trade_day"] for row in actions
                if row["policy_id"].startswith("L15_SWAP")
            }
            self.assertEqual(swap_days, {"2026-08-18"})

    def test_at_or_after_open_defers_execution_floor(self):
        for hour, minute in ((9, 0), (11, 30), (18, 0)):
            with self.subTest(hour=hour, minute=minute):
                wall = datetime(2026, 8, 18, hour, minute, tzinfo=VN)
                self.assertEqual(_execution_floor_for_wall(wall), date(2026, 8, 19))

    def test_existing_observation_floor_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store, report_path, rows_path = self._fixture(root)
            state = root / "state"
            first = run(
                store=store,
                v78_report=report_path,
                v78_tactical_rows=rows_path,
                state_dir=state,
                output_dir=root / "out1",
                wall_time=datetime(2026, 8, 18, 10, 0, tzinfo=VN),
            )
            self.assertEqual(first["current_execution_floor_date"], "2026-08-19")
            second = run(
                store=store,
                v78_report=report_path,
                v78_tactical_rows=rows_path,
                state_dir=state,
                output_dir=root / "out2",
                wall_time=datetime(2026, 8, 18, 8, 0, tzinfo=VN),
            )
            self.assertEqual(second["current_execution_floor_date"], "2026-08-19")
            self.assertEqual(second["current_capture_wall_time_vn"], first["current_capture_wall_time_vn"])

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