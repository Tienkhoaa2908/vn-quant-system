from __future__ import annotations

from copy import deepcopy
import unittest

from he_thong_dinh_luong import model_lab
from he_thong_dinh_luong.model_lab_core import ENSEMBLE_MODEL
from he_thong_dinh_luong.model_lab_upgrade_v13 import DnseCashCostConfig
from he_thong_dinh_luong.model_lab_upgrade_v14 import (
    nested_outer_test_evaluation,
)


SYMBOLS = tuple("ABCDEFGHIJKL")


def prediction_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    dates = (
        "2025-01-31",
        "2025-02-28",
        "2025-03-31",
        "2025-04-30",
        "2025-05-30",
        "2025-06-30",
        "2025-07-31",
        "2025-08-29",
        "2025-09-30",
        "2025-10-31",
        "2025-11-28",
        "2025-12-31",
    )
    models = ("ridge_ranker", "momentum_baseline", ENSEMBLE_MODEL)
    for day in dates:
        returns = {
            symbol: 0.03 - index * 0.003
            for index, symbol in enumerate(SYMBOLS)
        }
        for model in models:
            ordered = (
                SYMBOLS
                if model != "momentum_baseline"
                else tuple(reversed(SYMBOLS))
            )
            rank_by_symbol = {
                symbol: index + 1
                for index, symbol in enumerate(ordered)
            }
            for symbol in SYMBOLS:
                rank = rank_by_symbol[symbol]
                rows.append({
                    "model": model,
                    "fold": f"wf_{day}",
                    "test_date": day,
                    "symbol": symbol,
                    "score": float(len(SYMBOLS) - rank),
                    "percentile": 1.0 - (rank - 1) / len(SYMBOLS),
                    "rank": rank,
                    "selected_top_k": str(rank <= 10).lower(),
                    "label_end": day,
                    "stock_return": returns[symbol],
                    "benchmark_return": 0.0,
                    "relative_return": returns[symbol],
                })
    return rows


class ModelLabUpgradeV13Tests(unittest.TestCase):
    def test_dnse_cost_contract_is_decomposed(self):
        cost = DnseCashCostConfig()
        self.assertAlmostEqual(cost.combined_buy_fee_bps, 2.7)
        self.assertAlmostEqual(cost.transfer_fee_bps_equivalent, 0.3)
        self.assertAlmostEqual(cost.combined_sell_fee_bps, 3.0)
        contract = cost.as_contract()
        self.assertFalse(contract["exchange_field_available"])
        self.assertFalse(contract["exact_execution_cost_claimed"])

    def test_nested_validation_selects_model_and_policy_before_outer_test(self):
        result = nested_outer_test_evaluation(
            prediction_rows(),
            top_k=10,
            replacement_caps=(0, 1, 2, 3),
            candidate_models=("ridge_ranker", "momentum_baseline"),
            validation_months=3,
            test_months=3,
            minimum_outer_test_periods=6,
            cost=DnseCashCostConfig(),
        )
        summary = result["summary"]
        selections = result["selection_rows"]
        periods = result["outer_rows"]
        self.assertEqual(summary["outer_test_period_count"], 9)
        self.assertEqual(len(selections), 3)
        self.assertTrue(summary["outer_test_blocks_non_overlapping"])
        self.assertTrue(summary["continuous_holdings_across_outer_blocks"])
        self.assertTrue(summary["model_switch_turnover_charged"])
        self.assertTrue(
            summary["model_and_policy_selected_only_from_prior_validation"]
        )
        self.assertEqual(selections[0]["selected_model"], "ridge_ranker")
        self.assertEqual(selections[0]["selected_replacement_cap"], 0)
        self.assertLess(
            selections[0]["validation_end"],
            selections[0]["test_start"],
        )
        self.assertEqual(periods[0]["turnover"], 1.0)
        self.assertTrue(summary["gate_passed"])
        self.assertEqual(summary["status"], "HISTORICALLY_VALIDATED")

    def test_first_outer_selection_does_not_use_first_outer_test_returns(self):
        original = prediction_rows()
        mutated = deepcopy(original)
        first_test_dates = {"2025-04-30", "2025-05-30", "2025-06-30"}
        for row in mutated:
            if row["test_date"] in first_test_dates:
                row["stock_return"] = -float(row["stock_return"])
                row["relative_return"] = -float(row["relative_return"])
        kwargs = {
            "top_k": 10,
            "replacement_caps": (0, 1, 2, 3),
            "candidate_models": ("ridge_ranker", "momentum_baseline"),
            "validation_months": 3,
            "test_months": 3,
            "minimum_outer_test_periods": 6,
            "cost": DnseCashCostConfig(),
        }
        left = nested_outer_test_evaluation(original, **kwargs)
        right = nested_outer_test_evaluation(mutated, **kwargs)
        self.assertEqual(
            left["selection_rows"][0]["selected_model"],
            right["selection_rows"][0]["selected_model"],
        )
        self.assertEqual(
            left["selection_rows"][0]["selected_replacement_cap"],
            right["selection_rows"][0]["selected_replacement_cap"],
        )

    def test_stress_cost_must_not_be_below_base(self):
        with self.assertRaisesRegex(
            ValueError,
            "MODEL_LAB_V13_STRESS_SLIPPAGE_BELOW_BASE",
        ):
            DnseCashCostConfig(
                slippage_bps=10.0,
                stress_slippage_bps=5.0,
            )

    def test_stable_entrypoint_routes_through_v15(self):
        self.assertEqual(
            model_lab.run_model_lab.__module__,
            "he_thong_dinh_luong.model_lab_upgrade_v15",
        )


if __name__ == "__main__":
    unittest.main()
