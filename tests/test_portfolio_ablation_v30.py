from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from he_thong_dinh_luong import portfolio_ablation_v30 as v30


class PortfolioAblationV30Tests(unittest.TestCase):
    def _artifact(self, root: Path, *, passing_models=None) -> Path:
        passing = passing_models or [v30.CHALLENGER_MODEL]
        report = {
            "schema_version": "predictive_target_lab_v29",
            "status": "SUCCESS",
            "recommendation": (
                "PROMOTE_PASSING_CHALLENGER_TO_V30_PORTFOLIO_ABLATION"
            ),
            "passing_models": passing,
            "frozen_v28_candidate_modified": False,
            "future_holdout_clock_reset": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
            "input_zip_sha256": "a" * 64,
            "walk_forward_fold_count": 3,
            "data_blockers_unchanged": ["PRICE_BASIS_CHUA_XAC_NHAN"],
        }
        fields = (
            "model",
            "fold",
            "test_date",
            "symbol",
            "score",
            "percentile",
            "rank",
            "selected_top_k",
            "label_end",
            "stock_return",
            "benchmark_return",
            "relative_return",
        )
        prediction_buffer = StringIO(newline="")
        writer = csv.DictWriter(
            prediction_buffer,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        days = ("2026-01-30", "2026-02-27", "2026-03-31")
        symbols = ("AAA", "BBB", "CCC", "DDD", "EEE")
        for day_index, day in enumerate(days):
            for model in (v30.FROZEN_MODEL, v30.CHALLENGER_MODEL):
                for index, symbol in enumerate(symbols):
                    writer.writerow({
                        "model": model,
                        "fold": f"wf_{day}",
                        "test_date": day,
                        "symbol": symbol,
                        "score": index + day_index / 10.0,
                        "percentile": index / 4.0,
                        "rank": 5 - index,
                        "selected_top_k": "false",
                        "label_end": day,
                        "stock_return": 0.01 * index,
                        "benchmark_return": 0.01,
                        "relative_return": 0.01 * index - 0.01,
                    })
        decision_buffer = StringIO(newline="")
        writer = csv.DictWriter(
            decision_buffer,
            fieldnames=("model", "predictive_challenger_gate_passed"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow({
            "model": v30.CHALLENGER_MODEL,
            "predictive_challenger_gate_passed": "true",
        })
        selection_buffer = StringIO(newline="")
        writer = csv.DictWriter(
            selection_buffer,
            fieldnames=(
                "test_date",
                "model",
                "validation_mean_rank_ic",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow({
            "test_date": "2026-01-30",
            "model": v30.CHALLENGER_MODEL,
            "validation_mean_rank_ic": 0.02,
        })
        artifact = root / "v29.zip"
        with ZipFile(artifact, "w", compression=ZIP_DEFLATED) as archive:
            prefix = "predictive-target-lab-v29\\"
            archive.writestr(
                prefix + "predictive_target_lab_v29.json",
                json.dumps(report),
            )
            archive.writestr(
                prefix + "predictions_v29.csv",
                prediction_buffer.getvalue(),
            )
            archive.writestr(
                prefix + "decision_gates_v29.csv",
                decision_buffer.getvalue(),
            )
            archive.writestr(
                prefix + "hyperparameter_selection_v29.csv",
                selection_buffer.getvalue(),
            )
        return artifact

    def test_loads_windows_member_paths_and_discloses_metadata_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self._artifact(Path(temporary))
            report, predictions, selections, metadata = (
                v30._load_v29_artifact(
                    artifact,
                    expected_input_sha256="a" * 64,
                )
            )
        self.assertEqual(
            report["passing_models"],
            [v30.CHALLENGER_MODEL],
        )
        self.assertEqual(len(predictions), 30)
        self.assertEqual(len(selections), 1)
        self.assertFalse(
            metadata["hyperparameter_selection_audit_complete"]
        )
        self.assertEqual(
            metadata["missing_logit_hyperparameter_columns"],
            ["selected_c", "validation_bottom20_recall"],
        )

    def test_unexpected_passing_model_set_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = self._artifact(
                Path(temporary),
                passing_models=[v30.CHALLENGER_MODEL, "OTHER_MODEL"],
            )
            with self.assertRaisesRegex(
                ValueError,
                "V30_V29_PASSING_MODEL_SET_UNEXPECTED",
            ):
                v30._load_v29_artifact(artifact)

    def test_paired_delta_statistics_are_deterministic(self) -> None:
        challenger = {
            f"2026-{month:02d}-28": {
                "net_excess_return": 0.02 + month / 1000.0
            }
            for month in range(1, 13)
        }
        baseline = {
            day: {"net_excess_return": 0.01}
            for day in challenger
        }
        first = v30._paired_delta_stats(
            challenger,
            baseline,
            repetitions=200,
            block_months=3,
            seed=7,
        )
        second = v30._paired_delta_stats(
            challenger,
            baseline,
            repetitions=200,
            block_months=3,
            seed=7,
        )
        self.assertEqual(first, second)
        self.assertGreater(first["mean_net_excess_delta"], 0.0)
        self.assertGreater(
            first["bootstrap_probability_delta_positive"],
            0.90,
        )

    def test_freeze_requires_adjacent_passing_breadths(self) -> None:
        summaries = []
        for breadth in v30.DEFAULT_BREADTHS:
            summaries.append({
                "breadth": breadth,
                "model": v30.FROZEN_MODEL,
                "gate_passed": True,
                "base_relative_total_return": 0.10,
                "stress_relative_total_return": 0.08,
                "base_positive_net_excess_ratio": 0.55,
                "base_mean_turnover": 0.40,
                "base_leave_best_period_out_relative_total_return": 0.03,
            })
            strong = breadth in {10, 15}
            summaries.append({
                "breadth": breadth,
                "model": v30.CHALLENGER_MODEL,
                "gate_passed": strong,
                "base_relative_total_return": 0.13 if strong else 0.01,
                "stress_relative_total_return": 0.11 if strong else -0.01,
                "base_positive_net_excess_ratio": 0.60,
                "base_mean_turnover": 0.45,
                "base_leave_best_period_out_relative_total_return": 0.04,
            })
        comparisons = []
        for breadth in v30.DEFAULT_BREADTHS:
            strong = breadth in {10, 15}
            for comparison in (
                "SAME_BREADTH_C3",
                "FROZEN_C3_TOP10",
            ):
                comparisons.append({
                    "challenger_breadth": breadth,
                    "comparison": comparison,
                    "bootstrap_probability_delta_positive": (
                        0.80 if strong else 0.50
                    ),
                    "leave_best_3_mean_net_excess_delta": (
                        0.01 if strong else -0.01
                    ),
                })
        rows, recommendation, passing, adjacent = v30._decision_rows(
            summaries,
            comparisons,
            breadths=v30.DEFAULT_BREADTHS,
        )
        self.assertEqual(passing, [10, 15])
        self.assertEqual(adjacent, [(10, 15)])
        self.assertEqual(
            recommendation,
            "FREEZE_V29_LOGIT_POLICY_FOR_FUTURE_HOLDOUT",
        )
        self.assertTrue(
            all(row["live_capital_approved"] is False for row in rows)
        )

    def test_csv_writer_keeps_union_of_heterogeneous_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rows.csv"
            v30._write_csv(path, [{"a": 1}, {"b": 2, "a": 3}])
            with path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(list(rows[0]), ["a", "b"])
        self.assertEqual(rows[1]["b"], "2")


if __name__ == "__main__":
    unittest.main()
