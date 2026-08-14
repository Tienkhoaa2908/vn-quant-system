from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import component_breadth_ablation_v27 as base
from he_thong_dinh_luong import component_breadth_ablation_v27_runner as runner
from he_thong_dinh_luong.model_lab_core import ENSEMBLE_MODEL


def prediction_row(
    model: str,
    symbol: str,
    rank: int,
    stock_return: float,
) -> dict[str, object]:
    return {
        "model": model,
        "test_date": "2026-01-30",
        "symbol": symbol,
        "rank": rank,
        "stock_return": stock_return,
        "benchmark_return": 0.01,
        "label_end": "2026-02-27",
    }


class ComponentBreadthAblationV27RunnerTests(unittest.TestCase):
    def test_v22_boolean_values_are_converted_strictly(self) -> None:
        original = base._finite
        base._ORIGINAL_V27_FINITE = original
        try:
            self.assertEqual(
                runner._finite_with_v22_boolean(
                    "true",
                    name="vnindex_tren_ma250",
                ),
                1.0,
            )
            self.assertEqual(
                runner._finite_with_v22_boolean(
                    "false",
                    name="vnindex_tren_ma250",
                ),
                0.0,
            )
            with self.assertRaisesRegex(ValueError, "V27_INVALID_BOOLEAN"):
                runner._finite_with_v22_boolean(
                    "unknown",
                    name="vnindex_tren_ma250",
                )
        finally:
            delattr(base, "_ORIGINAL_V27_FINITE")

    def test_sparse_period_holds_missing_slots_as_cash(self) -> None:
        rows = [
            prediction_row(ENSEMBLE_MODEL, "AAA", 1, 0.10),
            prediction_row(ENSEMBLE_MODEL, "BBB", 2, 0.20),
            prediction_row(ENSEMBLE_MODEL, "CCC", 3, 0.30),
        ]
        periods = runner._availability_capped_periods(
            rows,
            top_k=5,
            max_voluntary_replacements=2,
            buy_fee_bps=0.0,
            sell_fee_bps=0.0,
            sell_tax_bps=0.0,
            slippage_bps=0.0,
        )
        self.assertEqual(len(periods), 1)
        period = periods[0]
        self.assertEqual(period["available_symbol_count"], 3)
        self.assertEqual(period["realized_selected_count"], 3)
        self.assertEqual(period["cash_slot_count"], 2)
        self.assertAlmostEqual(float(period["invested_fraction"]), 0.60)
        self.assertAlmostEqual(float(period["gross_return"]), 0.12)
        self.assertEqual(period["availability_cap_applied"], "true")
        self.assertFalse(bool(period["actionable"] == "true"))

    def test_sparse_outer_period_uses_same_cash_slot_contract(self) -> None:
        rows = [
            prediction_row("CANDIDATE", "AAA", 1, 0.10),
            prediction_row("CANDIDATE", "BBB", 2, 0.20),
            prediction_row("CANDIDATE", "CCC", 3, 0.30),
        ]
        decisions = {
            "2026-01-30": {
                "outer_fold": "outer_01",
                "selected_model": "CANDIDATE",
                "selected_replacement_cap": 2,
            }
        }
        cost = SimpleNamespace(
            combined_buy_fee_bps=0.0,
            combined_sell_fee_bps=0.0,
            sell_tax_bps=0.0,
            slippage_bps=0.0,
            stress_slippage_bps=0.0,
        )
        base_rows, stress_rows = (
            runner._availability_capped_dynamic_outer_periods(
                rows,
                decisions=decisions,
                top_k=5,
                cost=cost,
            )
        )
        self.assertEqual(len(base_rows), 1)
        self.assertEqual(len(stress_rows), 1)
        self.assertEqual(base_rows[0]["cash_slot_count"], 2)
        self.assertEqual(base_rows[0]["availability_cap_applied"], "true")
        self.assertAlmostEqual(float(base_rows[0]["gross_return"]), 0.12)
        self.assertAlmostEqual(
            float(stress_rows[0]["gross_return"]),
            0.12,
        )

    def test_compatibility_patches_are_restored_after_run(self) -> None:
        original_finite = base._finite
        original_periods = base.v15.v13.v12.corrected_turnover_capped_periods
        original_dynamic = base.v15.v14._dynamic_outer_periods
        with patch.object(
            base,
            "run_v27",
            return_value={"status": "SUCCESS"},
        ) as call:
            result = runner.run_v27_compatible(
                "input",
                "model",
                "output-does-not-exist",
            )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIs(base._finite, original_finite)
        self.assertIs(
            base.v15.v13.v12.corrected_turnover_capped_periods,
            original_periods,
        )
        self.assertIs(base.v15.v14._dynamic_outer_periods, original_dynamic)
        self.assertFalse(hasattr(base, "_ORIGINAL_V27_FINITE"))
        call.assert_called_once_with("input", "model", "output-does-not-exist")


if __name__ == "__main__":
    unittest.main()
