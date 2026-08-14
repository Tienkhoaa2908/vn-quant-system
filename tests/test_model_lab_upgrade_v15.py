from __future__ import annotations

from copy import deepcopy
import unittest

from he_thong_dinh_luong.model_lab_upgrade_v13 import DnseCashCostConfig
from he_thong_dinh_luong.model_lab_upgrade_v15 import (
    model_wise_nested_evaluation,
)


SYMBOLS = tuple("ABCDEFGHIJKL")
DATES = (
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


def prediction_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for day in DATES:
        returns = {
            symbol: 0.04 - index * 0.003
            for index, symbol in enumerate(SYMBOLS)
        }
        for model in ("ridge_ranker", "momentum_baseline"):
            ordered = (
                SYMBOLS
                if model == "ridge_ranker"
                else tuple(reversed(SYMBOLS))
            )
            ranks = {
                symbol: index + 1
                for index, symbol in enumerate(ordered)
            }
            for symbol in SYMBOLS:
                rank = ranks[symbol]
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


class ModelLabUpgradeV15Tests(unittest.TestCase):
    def test_each_model_is_evaluated_independently(self):
        result = model_wise_nested_evaluation(
            prediction_rows(),
            top_k=10,
            replacement_caps=(0, 1, 2, 3),
            candidate_models=("ridge_ranker", "momentum_baseline"),
            validation_months=3,
            test_months=3,
            minimum_outer_test_periods=6,
            cost=DnseCashCostConfig(),
        )
        details = result["model_details"]
        self.assertEqual(set(details), {"ridge_ranker", "momentum_baseline"})
        self.assertEqual(details["ridge_ranker"]["outer_test_period_count"], 9)
        self.assertEqual(details["momentum_baseline"]["outer_test_period_count"], 9)
        self.assertTrue(details["ridge_ranker"]["gate_passed"])
        self.assertFalse(details["momentum_baseline"]["gate_passed"])
        self.assertEqual(result["historical_reference_model"], "ridge_ranker")
        self.assertEqual(result["status"], "HISTORICALLY_VALIDATED_REFERENCE")
        self.assertTrue(result["model_fixed_across_outer_blocks"])
        self.assertTrue(result["cap_selected_only_from_prior_validation"])

    def test_outer_rows_never_switch_model_inside_one_evaluation(self):
        result = model_wise_nested_evaluation(
            prediction_rows(),
            top_k=10,
            replacement_caps=(0, 1, 2, 3),
            candidate_models=("ridge_ranker", "momentum_baseline"),
            validation_months=3,
            test_months=3,
            minimum_outer_test_periods=6,
            cost=DnseCashCostConfig(),
        )
        by_model: dict[str, set[str]] = {}
        for row in result["outer_rows"]:
            by_model.setdefault(str(row["model"]), set()).add(
                str(row["selected_model"])
            )
        self.assertEqual(by_model["ridge_ranker"], {"ridge_ranker"})
        self.assertEqual(
            by_model["momentum_baseline"],
            {"momentum_baseline"},
        )

    def test_first_cap_selection_does_not_use_first_outer_test_labels(self):
        original = prediction_rows()
        mutated = deepcopy(original)
        first_test = {"2025-04-30", "2025-05-30", "2025-06-30"}
        for row in mutated:
            if row["test_date"] in first_test:
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
        left = model_wise_nested_evaluation(original, **kwargs)
        right = model_wise_nested_evaluation(mutated, **kwargs)
        for model in ("ridge_ranker", "momentum_baseline"):
            left_first = next(
                row for row in left["selection_rows"]
                if row["model"] == model and row["outer_fold"] == "outer_01"
            )
            right_first = next(
                row for row in right["selection_rows"]
                if row["model"] == model and row["outer_fold"] == "outer_01"
            )
            self.assertEqual(
                left_first["selected_replacement_cap"],
                right_first["selected_replacement_cap"],
            )

    def test_invalid_replacement_cap_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "MODEL_LAB_V15_INVALID_REPLACEMENT_CAPS",
        ):
            model_wise_nested_evaluation(
                prediction_rows(),
                top_k=10,
                replacement_caps=(11,),
                validation_months=3,
                test_months=3,
                minimum_outer_test_periods=6,
                cost=DnseCashCostConfig(),
            )


if __name__ == "__main__":
    unittest.main()
