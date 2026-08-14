from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong import component_breadth_ablation_v27 as v27
from he_thong_dinh_luong import predictive_target_lab_v29 as v29


FEATURE_TEMPLATE = {
    "dong_luong_12_1": 0.0,
    "bien_dong_60": 0.1,
    "suc_manh_tuong_doi_120": 0.0,
    "khoang_cach_ma60": 0.0,
    "khoang_cach_ma120": 0.0,
    "khoang_cach_ma250": 0.0,
    "loi_nhuan_20": 0.0,
    "loi_nhuan_60": 0.0,
    "loi_nhuan_120": 0.0,
    "loi_nhuan_250": 0.0,
    "ty_le_dinh_52_tuan": 0.0,
    "vnindex_tren_ma250": 1.0,
}


def make_row(
    signal_day: date,
    symbol: str,
    *,
    index: int,
    regime: float = 1.0,
    reverse: bool = False,
) -> v27.ResearchRow:
    features = dict(FEATURE_TEMPLATE)
    direction = -1.0 if reverse else 1.0
    features.update({
        "dong_luong_12_1": direction * index,
        "bien_dong_60": 0.50 - index * 0.02,
        "suc_manh_tuong_doi_120": direction * index,
        "khoang_cach_ma60": direction * index / 10.0,
        "khoang_cach_ma120": direction * index / 10.0,
        "khoang_cach_ma250": direction * index / 10.0,
        "loi_nhuan_20": 1.0 if index >= 5 else -1.0,
        "loi_nhuan_60": 1.0 if index >= 5 else -1.0,
        "loi_nhuan_120": 1.0 if index >= 5 else -1.0,
        "loi_nhuan_250": 1.0 if index >= 5 else -1.0,
        "ty_le_dinh_52_tuan": direction * index,
        "vnindex_tren_ma250": regime,
    })
    relative = direction * (index - 4.5) / 100.0
    return v27.ResearchRow(
        signal_day=signal_day,
        symbol=symbol,
        label_end=date(signal_day.year, signal_day.month, 20),
        stock_return=relative + 0.01,
        benchmark_return=0.01,
        relative_return=relative,
        features=features,
    )


def month_rows(year: int, month: int, *, regime: float = 1.0, reverse: bool = False):
    day = date(year, month, 1)
    return tuple(
        make_row(
            day,
            f"S{index:02d}",
            index=index,
            regime=regime,
            reverse=reverse,
        )
        for index in range(10)
    )


class PredictiveTargetLabV29Tests(unittest.TestCase):
    def test_monthly_rank_targets_are_cross_sectional(self) -> None:
        rows = month_rows(2020, 1) + month_rows(2020, 2, reverse=True)
        targets = v29._monthly_rank_targets(rows)
        self.assertEqual(len(targets), 20)
        self.assertAlmostEqual(min(targets[:10]), 0.0)
        self.assertAlmostEqual(max(targets[:10]), 1.0)
        self.assertAlmostEqual(min(targets[10:]), 0.0)
        self.assertAlmostEqual(max(targets[10:]), 1.0)

    def test_design_matrix_regime_interactions_add_columns(self) -> None:
        rows = month_rows(2020, 1, regime=0.0)
        plain = v29._design_matrix(rows, regime_interactions=False)
        interacted = v29._design_matrix(rows, regime_interactions=True)
        self.assertEqual(len(plain[0]), len(v29.FEATURE_NAMES))
        self.assertEqual(
            len(interacted[0]),
            len(v29.FEATURE_NAMES) * 2 + 1,
        )
        self.assertTrue(all(value == 0.0 for value in interacted[0][8:]))

    def test_fold_scores_use_prior_train_and_validation(self) -> None:
        train = tuple(
            row
            for month in range(1, 7)
            for row in month_rows(2020, month, regime=1.0)
        )
        validation = month_rows(2020, 7, regime=0.0) + month_rows(
            2020,
            8,
            regime=0.0,
            reverse=True,
        )
        test = month_rows(2020, 9, regime=0.0)
        fold = v27.Fold(
            test_day=date(2020, 9, 1),
            train_rows=train,
            validation_rows=validation,
            test_rows=test,
        )
        scores, metadata = v29._fold_scores(fold)
        self.assertEqual(set(scores), set(v29.MODEL_NAMES))
        self.assertTrue(all(len(values) == len(test) for values in scores.values()))
        self.assertEqual(len(metadata), 4)
        self.assertTrue(all(row["uses_test_labels"] is False for row in metadata))

    def test_newey_west_and_bootstrap_are_deterministic(self) -> None:
        values = [0.01, 0.02, -0.01, 0.03, 0.02, 0.00] * 3
        nw = v29._newey_west_mean(values, lag=3)
        first = v29._moving_block_bootstrap(
            values,
            block_length=3,
            repetitions=200,
            seed=7,
        )
        second = v29._moving_block_bootstrap(
            values,
            block_length=3,
            repetitions=200,
            seed=7,
        )
        self.assertGreater(nw["mean"], 0.0)
        self.assertGreaterEqual(nw["standard_error"], 0.0)
        self.assertEqual(first, second)
        self.assertGreater(first["probability_mean_positive"], 0.5)

    def test_decision_gate_requires_paired_improvement(self) -> None:
        base = {
            "model": v29.FROZEN_MODEL,
            "mean_rank_ic": 0.03,
            "positive_rank_ic_ratio": 0.58,
            "second_half_mean_rank_ic": 0.04,
            "leave_best_3_mean_rank_ic": 0.02,
            "risk_off_mean_rank_ic": -0.01,
        }
        statistical = [base]
        comparisons = []
        for model in v29.MODEL_NAMES:
            if model == v29.FROZEN_MODEL:
                continue
            statistical.append({
                "model": model,
                "mean_rank_ic": 0.04,
                "positive_rank_ic_ratio": 0.60,
                "second_half_mean_rank_ic": 0.05,
                "leave_best_3_mean_rank_ic": 0.02,
                "risk_off_mean_rank_ic": 0.00,
            })
            comparisons.append({
                "challenger": model,
                "delta_bootstrap_probability_positive": 0.90,
            })
        rows, recommendation = v29._decision_rows(statistical, comparisons)
        self.assertTrue(all(row["predictive_challenger_gate_passed"] for row in rows))
        self.assertEqual(
            recommendation,
            "PROMOTE_PASSING_CHALLENGER_TO_V30_PORTFOLIO_ABLATION",
        )


if __name__ == "__main__":
    unittest.main()
