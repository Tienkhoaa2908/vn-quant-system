from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import component_breadth_ablation_v27_runner as v27
from he_thong_dinh_luong import portfolio_ablation_v30 as core
from he_thong_dinh_luong import portfolio_ablation_v30_runner as runner
from he_thong_dinh_luong.model_lab_core import ENSEMBLE_MODEL


def _policy_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for day, returns in (
        ("2025-01-31", (0.02, 0.01)),
        ("2025-02-28", (0.01, -0.01)),
    ):
        for rank, (symbol, stock_return) in enumerate(
            zip(("AAA", "BBB"), returns),
            start=1,
        ):
            rows.append({
                "model": ENSEMBLE_MODEL,
                "test_date": day,
                "symbol": symbol,
                "rank": rank,
                "stock_return": stock_return,
                "benchmark_return": 0.005,
                "label_end": day,
            })
    return rows


def _outer_row(
    *,
    breadth: int,
    day: str,
    available: int,
    capped: bool,
    net_return: float,
) -> dict[str, object]:
    return {
        "breadth": breadth,
        "model": core.CHALLENGER_MODEL,
        "signal_date": day,
        "available_symbol_count": available,
        "realized_selected_count": min(breadth, available),
        "invested_fraction": min(breadth, available) / breadth,
        "availability_cap_applied": str(capped).lower(),
        "net_return": net_return,
        "net_excess_return": net_return - 0.005,
    }


def _portfolio_row(*, breadth: int, net_total: float) -> dict[str, object]:
    return {
        "breadth": breadth,
        "model": core.CHALLENGER_MODEL,
        "base_net_total_return": net_total,
        "base_benchmark_total_return": 0.010025,
        "base_relative_total_return": (1.0 + net_total) / 1.010025 - 1.0,
        "stress_net_total_return": net_total - 0.002,
        "stress_relative_total_return": (
            (1.0 + net_total - 0.002) / 1.010025 - 1.0
        ),
    }


class PortfolioAblationV30RunnerTests(unittest.TestCase):
    def test_sparse_compatibility_is_applied_and_restored(self) -> None:
        original_periods = core.v15.v13.v12.corrected_turnover_capped_periods
        original_dynamic = core.v15.v14._dynamic_outer_periods
        with runner._sparse_universe_compatibility():
            self.assertIs(
                core.v15.v13.v12.corrected_turnover_capped_periods,
                v27._availability_capped_periods,
            )
            self.assertIs(
                core.v15.v14._dynamic_outer_periods,
                v27._availability_capped_dynamic_outer_periods,
            )
            periods = core.v15.v13.v12.corrected_turnover_capped_periods(
                _policy_rows(),
                top_k=3,
                max_voluntary_replacements=1,
                buy_fee_bps=2.7,
                sell_fee_bps=3.0,
                sell_tax_bps=10.0,
                slippage_bps=5.0,
            )
            self.assertEqual(len(periods), 2)
            self.assertEqual(periods[0]["cash_slot_count"], 1)
            self.assertEqual(periods[0]["invested_fraction"], 2 / 3)
        self.assertIs(
            core.v15.v13.v12.corrected_turnover_capped_periods,
            original_periods,
        )
        self.assertIs(core.v15.v14._dynamic_outer_periods, original_dynamic)

    def test_availability_summary_keeps_top10_and_flags_sparse_top15(self) -> None:
        rows = [
            _outer_row(
                breadth=10,
                day="2025-01-31",
                available=13,
                capped=False,
                net_return=0.01,
            ),
            _outer_row(
                breadth=15,
                day="2025-01-31",
                available=13,
                capped=True,
                net_return=0.01,
            ),
        ]
        summaries = {
            int(row["breadth"]): row
            for row in runner._availability_summary(rows)
        }
        self.assertTrue(summaries[10]["fixed_breadth_fully_feasible"])
        self.assertFalse(summaries[15]["fixed_breadth_fully_feasible"])
        self.assertEqual(
            summaries[15]["availability_capped_outer_period_count"],
            1,
        )
        self.assertEqual(summaries[15]["minimum_available_symbol_count"], 13)

    def test_performance_status_reports_profit_loss_and_duration(self) -> None:
        outer = [
            _outer_row(
                breadth=10,
                day="2025-01-31",
                available=20,
                capped=False,
                net_return=0.02,
            ),
            _outer_row(
                breadth=10,
                day="2025-02-28",
                available=20,
                capped=False,
                net_return=-0.01,
            ),
        ]
        rows = runner._performance_rows(
            [_portfolio_row(breadth=10, net_total=0.0098)],
            outer,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["profit_loss_status"], "PROFIT")
        self.assertEqual(rows[0]["observed_outer_months"], 2)
        self.assertEqual(rows[0]["calendar_month_span"], 2)
        description = str(rows[0]["performance_description_vi"])
        self.assertIn("Lãi", description)
        self.assertIn("2 tháng OOS", description)
        self.assertIn("2025-01-31 đến 2025-02-28", description)

    def test_postprocess_fails_sparse_breadth_without_relaxing_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            outer = [
                _outer_row(
                    breadth=10,
                    day="2025-01-31",
                    available=20,
                    capped=False,
                    net_return=0.02,
                ),
                _outer_row(
                    breadth=10,
                    day="2025-02-28",
                    available=20,
                    capped=False,
                    net_return=0.01,
                ),
                _outer_row(
                    breadth=15,
                    day="2025-01-31",
                    available=13,
                    capped=True,
                    net_return=0.015,
                ),
                _outer_row(
                    breadth=15,
                    day="2025-02-28",
                    available=20,
                    capped=False,
                    net_return=0.01,
                ),
            ]
            portfolio = [
                _portfolio_row(breadth=10, net_total=0.0302),
                _portfolio_row(breadth=15, net_total=0.02515),
            ]
            decisions = [
                {
                    "breadth": 10,
                    "v30_portfolio_gate_passed": True,
                    "failed_v30_gates": "",
                },
                {
                    "breadth": 15,
                    "v30_portfolio_gate_passed": True,
                    "failed_v30_gates": "",
                },
            ]
            core._write_csv(output / "outer_test_periods_v30.csv", outer)
            core._write_csv(
                output / "portfolio_comparison_v30.csv",
                portfolio,
            )
            core._write_csv(output / "decision_gates_v30.csv", decisions)
            core._write_json(output / core.REPORT_FILE, {
                "schema_version": core.SCHEMA_VERSION,
                "status": "SUCCESS",
                "breadths": [10, 15],
                "portfolio_results": {"10": {}, "15": {}},
                "decision_rows": [dict(row) for row in decisions],
                "passing_breadths": [10, 15],
                "adjacent_passing_breadth_pairs": [[10, 15]],
                "recommendation": (
                    "FREEZE_V29_LOGIT_POLICY_FOR_FUTURE_HOLDOUT"
                ),
            })

            result = runner._postprocess(output, {"status": "SUCCESS"})
            self.assertEqual(result["passing_breadths"], [10])
            self.assertEqual(
                result["recommendation"],
                "KEEP_SINGLE_V30_POLICY_AS_PAPER_DIAGNOSTIC_ONLY",
            )
            self.assertTrue(
                result["availability_cash_slot_compatibility_applied"]
            )
            self.assertFalse(result["fixed_breadth_gate_relaxed"])
            typed = {
                int(row["breadth"]): row for row in result["decision_rows"]
            }
            self.assertTrue(typed[10]["v30_portfolio_gate_passed"])
            self.assertFalse(typed[15]["v30_portfolio_gate_passed"])
            self.assertIn(
                "fixed_breadth_fully_feasible",
                typed[15]["failed_v30_gates"],
            )
            self.assertTrue((output / "breadth_availability_v30.csv").is_file())
            self.assertTrue((output / "performance_status_v30.csv").is_file())
            with (output / "performance_status_v30.csv").open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                performance = list(csv.DictReader(stream))
            self.assertEqual(len(performance), 2)
            self.assertIn("tháng OOS", performance[0]["performance_description_vi"])


if __name__ == "__main__":
    unittest.main()
