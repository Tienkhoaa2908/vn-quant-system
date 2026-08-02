from __future__ import annotations

import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
import zipfile

from he_thong_dinh_luong.ai_review_bundle_v1 import build_review_bundle


class AIReviewBundleV1Tests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _fixture(self, root: Path) -> dict[str, Path]:
        repo = root / "repo"
        repo.mkdir()
        self._git(repo, "init")
        self._git(repo, "config", "user.email", "test@example.com")
        self._git(repo, "config", "user.name", "Test")
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._git(repo, "add", "README.md")
        self._git(repo, "commit", "-m", "fixture")
        self._git(repo, "remote", "add", "origin", "https://github.com/example/repo.git")

        historical = root / "historical"
        historical.mkdir()
        (historical / "historical_research_input_v22.json").write_text(
            json.dumps({"status": "SUCCESS", "research_eligible": False}),
            encoding="utf-8",
        )
        (historical / "manifest.json").write_text(
            json.dumps({"schema_version": "historical_research_input_v22"}),
            encoding="utf-8",
        )
        with zipfile.ZipFile(historical / "daily_prediction_input.zip", "w") as archive:
            archive.writestr("manifest.json", "{}")

        model = root / "model"
        model.mkdir()
        (model / "model_lab_summary.json").write_text(
            json.dumps({"status": "SUCCESS_NO_MODEL_APPROVED"}),
            encoding="utf-8",
        )

        v27 = root / "v27"
        v27.mkdir()
        (v27 / "component_breadth_ablation_v27.json").write_text(
            json.dumps(
                {
                    "status": "SUCCESS",
                    "experiment": "COMPONENT_STABILITY_AND_FIXED_BREADTH_ABLATION",
                    "walk_forward_fold_count": 57,
                    "walk_forward_first_test_date": "2021-10-29",
                    "walk_forward_last_test_date": "2026-06-30",
                    "recommendation": "RUN_V28_FULL_WALK_FORWARD",
                    "sensitivity_analysis_only": True,
                    "independent_holdout": False,
                    "research_eligible": False,
                    "live_capital_approved": False,
                }
            ),
            encoding="utf-8",
        )
        csv_names = (
            "breadth_availability_v27.csv",
            "signal_gates_v27.csv",
            "portfolio_comparison_v27.csv",
            "factor_summary_v27.csv",
            "factor_quantiles_v27.csv",
            "quantile_shape_v27.csv",
            "component_correlation_v27.csv",
            "regime_summary_v27.csv",
            "adaptive_component_weights_v27.csv",
        )
        for name in csv_names:
            (v27 / name).write_text("key,value\na,b\n", encoding="utf-8")
        with (v27 / "decision_gates_v27.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=(
                    "model",
                    "breadth",
                    "v27_decision_gate_passed",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "model": "C3_STABLE_3_PAST_IC_SHRUNK",
                    "breadth": 10,
                    "v27_decision_gate_passed": "true",
                }
            )

        store = root / "store.sqlite3"
        with sqlite3.connect(store) as connection:
            connection.execute(
                "CREATE TABLE bars(symbol TEXT, day TEXT, close REAL)"
            )
            connection.execute(
                "INSERT INTO bars VALUES ('AAA', '2026-01-02', 10.5)"
            )
            connection.commit()

        return {
            "repo": repo,
            "historical": historical,
            "model": model,
            "v27": v27,
            "store": store,
        }

    def test_bundle_contains_source_data_evidence_prompt_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            output = root / "review"
            result = build_review_bundle(
                repo_root=fixture["repo"],
                historical_input_dir=fixture["historical"],
                model_output=fixture["model"],
                v27_output_dir=fixture["v27"],
                output_dir=output,
                store=fixture["store"],
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue(Path(result["bundle_zip"]).is_file())
            self.assertTrue((output / "source" / "source_snapshot.zip").is_file())
            self.assertTrue((output / "research_input" / "daily_prediction_input.zip").is_file())
            self.assertTrue((output / "data_inventory" / "sqlite_inventory.json").is_file())
            self.assertFalse((output / fixture["store"].name).exists())
            prompt = (output / "PROMPT_FOR_EXTERNAL_AI.md").read_text(encoding="utf-8")
            self.assertIn("selection bias", prompt)
            self.assertIn("Do not use T+1", prompt)
            report = json.loads((output / "ai_review_bundle_v1.json").read_text(encoding="utf-8"))
            self.assertFalse(report["full_sqlite_store_included"])
            self.assertFalse(report["security_contract"]["live_capital_approved"])
            manifest = json.loads((output / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertGreater(manifest["file_count"], 10)

    def test_dirty_repo_is_rejected_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            (fixture["repo"] / "dirty.txt").write_text("dirty", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "AI_REVIEW_DIRTY_WORKTREE"):
                build_review_bundle(
                    repo_root=fixture["repo"],
                    historical_input_dir=fixture["historical"],
                    model_output=fixture["model"],
                    v27_output_dir=fixture["v27"],
                    output_dir=root / "review",
                )


if __name__ == "__main__":
    unittest.main()
