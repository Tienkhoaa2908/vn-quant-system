from __future__ import annotations

from datetime import date
import csv
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.paper_scenario import run as run_scenario
from he_thong_dinh_luong.web_local_core import (
    DailyPipelineRequest,
    JobStore,
    LocalWebConfig,
    build_daily_pipeline,
    discover_eod_runs,
    latest_successful_eod,
    read_csv_rows,
)


class TestJobStore(unittest.TestCase):
    def test_chi_mot_job_active_va_khoi_dong_lai_danh_dau_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root / "jobs.sqlite3")
            first = store.create_job(
                kind="daily_pipeline",
                output_dir=root / "out1",
                log_path=root / "one.log",
                parameters={"target": "2026-07-30"},
            )
            with self.assertRaisesRegex(ValueError, "JOB_ALREADY_ACTIVE"):
                store.create_job(
                    kind="paper_scenario",
                    output_dir=root / "out2",
                    log_path=root / "two.log",
                    parameters={},
                )
            self.assertEqual(store.active()["id"], first)
            self.assertEqual(store.interrupt_stale_jobs(), 1)
            self.assertEqual(store.get(first)["status"], "INTERRUPTED")

    def test_update_job_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(root / "jobs.sqlite3")
            job = store.create_job(
                kind="x", output_dir=root / "out", log_path=root / "x.log", parameters={}
            )
            store.update(job, status="RUNNING", stage="step", started=True)
            store.update(job, status="SUCCESS", stage="completed", finished=True, return_code=0)
            row = store.get(job)
            self.assertEqual(row["status"], "SUCCESS")
            self.assertEqual(row["return_code"], 0)
            self.assertIsNone(store.active())


class TestPipelineContract(unittest.TestCase):
    def test_command_khong_chua_credential_va_dung_hai_buoc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = LocalWebConfig(repo_root=root / "repo", data_root=root / "data")
            request = DailyPipelineRequest(
                target_date=date(2026, 7, 30), secondary_source="vci"
            )
            output, steps = build_daily_pipeline(config, request, run_id="fixed")
            self.assertEqual(output.name, "eod-web-fixed")
            self.assertEqual(len(steps), 2)
            joined = " ".join(arg for step in steps for arg in step.command)
            self.assertIn("eod_hang_ngay_cli", joined)
            self.assertIn("paper_trading_daily", joined)
            self.assertIn("--target-date 2026-07-30", joined)
            self.assertNotIn("API_KEY", joined)
            self.assertNotIn("API_SECRET", joined)

    def test_localhost_only_config_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "WEB_PORT_INVALID"):
                LocalWebConfig(repo_root=root, data_root=root, port=70000)


class TestArtifactDiscovery(unittest.TestCase):
    def _run(self, root: Path, name: str, session: str, success: bool = True) -> Path:
        path = root / name
        (path / "updated_publication").mkdir(parents=True)
        manifest = {
            "status": "SUCCESS" if success else "FAILED",
            "session_date": session,
            "primary_coverage": 0.98,
        }
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (path / "daily_quant_output.zip").write_bytes(b"zip")
        (path / "updated_publication" / "du_lieu_gia_mo_dong_khoi_luong.csv").write_text(
            "ma,ngay,gia_mo_cua,gia_dong_cua,khoi_luong\nHPG,2026-07-30,21,22,1000\n",
            encoding="utf-8",
        )
        return path

    def test_chon_run_thanh_cong_moi_nhat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = self._run(root, "eod-dnse-20260729_190000", "2026-07-29")
            new = self._run(root, "eod-web-20260730_190000", "2026-07-30")
            old.touch()
            new.touch()
            rows = discover_eod_runs(root)
            self.assertEqual({row["name"] for row in rows}, {old.name, new.name})
            self.assertEqual(latest_successful_eod(root), new.resolve())

    def test_doc_csv_tail_va_loc_ma(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=("ma", "ngay", "close"))
                writer.writeheader()
                writer.writerows([
                    {"ma": "HPG", "ngay": "2026-07-28", "close": "20"},
                    {"ma": "VIC", "ngay": "2026-07-28", "close": "100"},
                    {"ma": "HPG", "ngay": "2026-07-29", "close": "21"},
                    {"ma": "HPG", "ngay": "2026-07-30", "close": "22"},
                ])
            rows = read_csv_rows(path, symbol="hpg", limit=2, tail=True)
            self.assertEqual([row["ngay"] for row in rows], ["2026-07-29", "2026-07-30"])


class TestPaperScenario(unittest.TestCase):
    def test_replay_tin_hieu_da_ghi_nhan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "paper"
            signals = state / "signals"
            signals.mkdir(parents=True)
            (signals / "2026-07-29_test.csv").write_text(
                "signal_date,symbol,champion_model,rank,target_weight_pct,status,source_zip_sha256\n"
                "2026-07-29,HPG,momentum_baseline,1,25,SELECTED,abc\n",
                encoding="utf-8",
            )
            publication = root / "publication"
            publication.mkdir()
            (publication / "du_lieu_gia_mo_dong_khoi_luong.csv").write_text(
                "ma,ngay,gia_mo_cua,gia_dong_cua,khoi_luong\n"
                "HPG,2026-07-29,20,20,1000000\n"
                "HPG,2026-07-30,21,22,1000000\n",
                encoding="utf-8",
            )
            output = root / "scenario"
            result = run_scenario(
                state_dir=state,
                publication_dir=publication,
                output_dir=output,
                initial_capital_vnd=1_000_000_000,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertGreater(result["fill_count"], 0)
            self.assertTrue((output / "paper_scenario.zip").is_file())
            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["signal_date_count"], 1)
            self.assertEqual(metrics["latest_market_date"], "2026-07-30")
            self.assertFalse(metrics["research_eligible"])


class TestUiModuleImport(unittest.TestCase):
    def test_import_khong_can_nicegui(self) -> None:
        from he_thong_dinh_luong import giao_dien_web
        self.assertEqual(giao_dien_web.NICEGUI_VERSION, "3.14.0")


if __name__ == "__main__":
    unittest.main()
