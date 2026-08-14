from __future__ import annotations

import unittest

from he_thong_dinh_luong.model_lab_upgrade_v10 import (
    FIXED_POSITIVE_TREE_COMPONENTS,
    latest_weight_contract,
    positive_diversified_tree_weights,
)


class ModelLabUpgradeV10Tests(unittest.TestCase):
    def test_fixed_tree_blend_is_positive_and_ignores_negative_prior_ic(self):
        weights = positive_diversified_tree_weights(
            {
                "hist_gradient_boosting_ranker": [-0.2] * 12,
                "lightgbm_ranker": [-0.1] * 12,
                "xgboost_ranker": [-0.3] * 12,
            },
            (
                "ridge_ranker",
                *FIXED_POSITIVE_TREE_COMPONENTS,
                "online_rank_ensemble_v1",
            ),
        )
        self.assertEqual(set(weights), set(FIXED_POSITIVE_TREE_COMPONENTS))
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertTrue(all(value > 0.0 for value in weights.values()))
        self.assertTrue(
            all(abs(value - 1.0 / 3.0) < 1e-12 for value in weights.values())
        )

    def test_missing_optional_tree_uses_available_positive_components(self):
        weights = positive_diversified_tree_weights(
            {},
            ("hist_gradient_boosting_ranker", "lightgbm_ranker"),
        )
        self.assertEqual(
            weights,
            {
                "hist_gradient_boosting_ranker": 0.5,
                "lightgbm_ranker": 0.5,
            },
        )

    def test_no_tree_falls_back_to_one_nonensemble_model(self):
        weights = positive_diversified_tree_weights(
            {},
            ("online_rank_ensemble_v1", "ridge_ranker"),
        )
        self.assertEqual(weights, {"ridge_ranker": 1.0})

    def test_latest_contract_uses_actual_latest_fold_weights(self):
        contract = latest_weight_contract(
            [
                {
                    "test_date": "2026-04-29",
                    "base_model": "ridge_ranker",
                    "weight": -1.0,
                },
                {
                    "test_date": "2026-05-29",
                    "base_model": "hist_gradient_boosting_ranker",
                    "weight": 1.0 / 3.0,
                },
                {
                    "test_date": "2026-05-29",
                    "base_model": "lightgbm_ranker",
                    "weight": 1.0 / 3.0,
                },
                {
                    "test_date": "2026-05-29",
                    "base_model": "xgboost_ranker",
                    "weight": 1.0 / 3.0,
                },
            ]
        )
        self.assertEqual(contract["latest_test_date"], "2026-05-29")
        self.assertEqual(contract["positive_component_count"], 3)
        self.assertEqual(contract["negative_component_count"], 0)
        self.assertTrue(contract["no_negative_weights"])
        self.assertAlmostEqual(float(contract["weights_sum"]), 1.0)
        self.assertAlmostEqual(float(contract["absolute_weights_sum"]), 1.0)

    def test_latest_contract_rejects_negative_weight(self):
        contract = latest_weight_contract(
            [
                {
                    "test_date": "2026-05-29",
                    "base_model": "lightgbm_ranker",
                    "weight": 0.55,
                },
                {
                    "test_date": "2026-05-29",
                    "base_model": "ridge_ranker",
                    "weight": -0.45,
                },
            ]
        )
        self.assertEqual(contract["positive_component_count"], 1)
        self.assertEqual(contract["negative_component_count"], 1)
        self.assertFalse(contract["no_negative_weights"])


if __name__ == "__main__":
    unittest.main()
