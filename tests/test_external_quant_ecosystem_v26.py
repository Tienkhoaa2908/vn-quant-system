from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import external_quant_ecosystem_v26 as ecosystem
from he_thong_dinh_luong.factor_diagnostics_v26 import (
    analyze_predictions,
    run_factor_diagnostics,
)
from he_thong_dinh_luong.portfolio_optimizer_adapter_v26 import (
    capped_inverse_volatility_weights,
)


class ExternalQuantEcosystemV26Tests(unittest.TestCase):
    def test_catalog_is_unique_and_default_selection_excludes_restricted(self) -> None:
        slugs = [spec.slug for spec in ecosystem.CATALOG]
        self.assertEqual(len(slugs), len(set(slugs)))
        selected = ecosystem.select_repositories("all")
        self.assertTrue(selected)
        self.assertTrue(all(
            spec.expected_license not in ecosystem.RESTRICTED_LICENSES
            for spec in selected
        ))
        restricted = ecosystem.select_repositories(
            "backtrader,mlfinlab",
            include_restricted=True,
        )
        self.assertEqual(
            {spec.slug for spec in restricted},
            {"backtrader", "mlfinlab"},
        )

    def test_clone_root_inside_main_repository_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "V26_EXTERNAL_ROOT_MUST_BE_OUTSIDE_MAIN_REPOSITORY",
        ):
            ecosystem.validate_clone_root(
                ecosystem._repo_root() / "external-research"
            )

    def test_catalog_payload_never_approves_live_capital(self) -> None:
        payload = ecosystem.catalog_payload()
        self.assertFalse(payload["third_party_code_vendored"])
        self.assertFalse(payload["third_party_code_executed"])
        self.assertFalse(payload["research_eligible"])
        self.assertFalse(payload["live_capital_approved"])
        self.assertFalse(payload["automatic_live_orders_allowed"])


class FactorDiagnosticsV26Tests(unittest.TestCase):
    @staticmethod
    def _rows() -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for month in range(1, 13):
            day = f"2025-{month:02d}-28"
            for index in range(10):
                score = float(index)
                relative = (index - 4.5) / 100.0
                rows.append({
                    "model": "test_model",
                    "test_date": day,
                    "symbol": f"S{index:02d}",
                    "score": score,
                    "rank": 10 - index,
                    "stock_return": relative + 0.01,
                    "benchmark_return": 0.01,
                    "relative_return": relative,
                    "label_end": day,
                })
        return rows

    def test_factor_diagnostics_compute_ic_quantiles_and_turnover(self) -> None:
        result = analyze_predictions(
            self._rows(),
            quantiles=5,
            top_k=3,
            rolling_months=6,
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["model_count"], 1)
        summary = result["summary_rows"][0]
        self.assertAlmostEqual(float(summary["mean_rank_ic"]), 1.0)
        self.assertAlmostEqual(float(summary["positive_rank_ic_ratio"]), 1.0)
        self.assertGreater(float(summary["mean_top_minus_bottom_return"]), 0.0)
        self.assertAlmostEqual(float(summary["mean_top_k_turnover"]), 1.0 / 12.0)
        self.assertEqual(summary["sector_analysis_status"], "SECTOR_COLUMN_NOT_AVAILABLE")
        self.assertFalse(result["historical_reference_gate_modified"])

    def test_factor_runner_publishes_safe_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "oos_predictions.csv"
            rows = self._rows()
            fields = list(rows[0])
            import csv
            with source.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            output = root / "factor-output"
            report = run_factor_diagnostics(
                source,
                output,
                quantiles=5,
                top_k=3,
                rolling_months=6,
            )
            self.assertTrue((output / "factor_diagnostics_v26.json").is_file())
            self.assertTrue((output / "factor_summary_v26.csv").is_file())
            persisted = json.loads(
                (output / "factor_diagnostics_v26.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            self.assertEqual(persisted["status"], "SUCCESS")
            self.assertFalse(report["live_capital_approved"])
            self.assertFalse(report["automatic_live_orders_allowed"])


class PortfolioOptimizerAdapterV26Tests(unittest.TestCase):
    def test_capped_inverse_volatility_is_normalized_and_respects_cap(self) -> None:
        weights = capped_inverse_volatility_weights(
            {
                "AAA": [0.01, -0.01, 0.02, -0.02, 0.01],
                "BBB": [0.02, -0.02, 0.04, -0.04, 0.02],
                "CCC": [0.03, -0.03, 0.06, -0.06, 0.03],
            },
            max_symbol_weight=0.40,
        )
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertLessEqual(max(weights.values()), 0.40 + 1e-12)
        self.assertGreater(weights["AAA"], weights["BBB"])
        self.assertGreater(weights["BBB"], weights["CCC"])

    def test_infeasible_symbol_cap_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "V26_SYMBOL_CAP_INFEASIBLE"):
            capped_inverse_volatility_weights(
                {
                    "AAA": [0.01, -0.01, 0.02],
                    "BBB": [0.02, -0.02, 0.04],
                },
                max_symbol_weight=0.40,
            )


if __name__ == "__main__":
    unittest.main()
