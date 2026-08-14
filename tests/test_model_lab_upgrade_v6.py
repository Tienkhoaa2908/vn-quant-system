from __future__ import annotations

from datetime import date, timedelta
import unittest

from he_thong_dinh_luong.model_lab_upgrade_v6 import (
    MINIMUM_FUTURE_PREDICTIVE_FOLDS,
    _continuous_rank_target,
    _predict_ridge_v6,
    _ridge_matrix_v6,
    future_predictive_holdout_rows,
    polarity_ensemble_scores,
    polarity_online_weights,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    REGIME_FEATURES,
    STOCK_RANK_FEATURES,
    Row,
)


def _features(
    strength: float,
    *,
    risk_on: bool,
    market_momentum: float = 0.05,
) -> dict[str, float]:
    values = {
        name: strength + index * 0.001
        for index, name in enumerate(STOCK_RANK_FEATURES)
    }
    values.update({
        "gia_tren_ma250": 1.0 if strength >= 0.0 else 0.0,
        "vnindex_tren_ma250": 1.0 if risk_on else 0.0,
        "vnindex_momentum_60": market_momentum,
        "vnindex_bien_dong_20": 0.02,
        "vnindex_bien_dong_60": 0.03,
    })
    assert set(REGIME_FEATURES).issubset(values)
    return values


def _row(
    day: date,
    symbol: str,
    strength: float,
    relative_return: float,
    *,
    risk_on: bool,
) -> Row:
    return Row(
        ngay=day,
        ma=symbol,
        features=_features(strength, risk_on=risk_on),
        relative_return=relative_return,
        label_end=day + timedelta(days=20),
    )


class ModelLabUpgradeV6Tests(unittest.TestCase):
    def test_continuous_target_is_ranked_inside_each_day(self) -> None:
        first = date(2025, 1, 31)
        second = date(2025, 2, 28)
        rows = [
            _row(first, "AAA", -1.0, -0.10, risk_on=True),
            _row(first, "BBB", 1.0, 0.20, risk_on=True),
            _row(second, "AAA", -1.0, 0.30, risk_on=False),
            _row(second, "BBB", 1.0, 0.10, risk_on=False),
        ]
        target = list(_continuous_rank_target(rows))
        self.assertEqual(target, [0.0, 1.0, 1.0, 0.0])

    def test_regime_interaction_can_change_cross_sectional_linear_effect(self) -> None:
        first = date(2025, 1, 31)
        second = date(2025, 2, 28)
        rows = [
            _row(first, "AAA", -1.0, -0.10, risk_on=True),
            _row(first, "BBB", 1.0, 0.20, risk_on=True),
            _row(second, "AAA", -1.0, 0.30, risk_on=False),
            _row(second, "BBB", 1.0, 0.10, risk_on=False),
        ]
        matrix, names = _ridge_matrix_v6(
            rows,
            include_regime_interactions=True,
        )
        interaction = "rank_loi_nhuan_20__x__vnindex_tren_ma250"
        column = names.index(interaction)
        self.assertLess(matrix[0, column], matrix[1, column])
        self.assertGreater(matrix[2, column], matrix[3, column])

    def test_ridge_v6_returns_nondegenerate_scores(self) -> None:
        days = [
            date(2024, 1, 31) + timedelta(days=31 * index)
            for index in range(8)
        ]
        train: list[Row] = []
        for day_index, day in enumerate(days[:5]):
            risk_on = day_index % 2 == 0
            train.extend([
                _row(day, "AAA", -2.0, -0.08 if risk_on else 0.09, risk_on=risk_on),
                _row(day, "BBB", -0.5, -0.01 if risk_on else 0.03, risk_on=risk_on),
                _row(day, "CCC", 0.5, 0.03 if risk_on else -0.01, risk_on=risk_on),
                _row(day, "DDD", 2.0, 0.10 if risk_on else -0.08, risk_on=risk_on),
            ])
        validation = [
            _row(days[5], "AAA", -2.0, -0.08, risk_on=True),
            _row(days[5], "BBB", -0.5, -0.01, risk_on=True),
            _row(days[5], "CCC", 0.5, 0.03, risk_on=True),
            _row(days[5], "DDD", 2.0, 0.10, risk_on=True),
        ]
        test = [
            _row(days[6], "AAA", -2.0, 0.0, risk_on=False),
            _row(days[6], "BBB", -0.5, 0.0, risk_on=False),
            _row(days[6], "CCC", 0.5, 0.0, risk_on=False),
            _row(days[6], "DDD", 2.0, 0.0, risk_on=False),
        ]
        scores = _predict_ridge_v6(train, validation, test, seed=1)
        self.assertEqual(len(scores), len(test))
        self.assertGreater(max(scores) - min(scores), 1e-12)

    def test_polarity_weights_invert_only_persistent_negative_history(self) -> None:
        weights = polarity_online_weights(
            {
                "ridge_ranker": [0.08, 0.06, 0.10, 0.07, 0.09, 0.05],
                "xgboost_ranker": [-0.08, -0.06, -0.10, -0.07, -0.09, -0.05],
                "hist_gradient_boosting_ranker": [
                    0.10, -0.10, 0.10, -0.10, 0.10, -0.10,
                ],
            },
            [
                "ridge_ranker",
                "xgboost_ranker",
                "hist_gradient_boosting_ranker",
            ],
        )
        self.assertGreater(weights["ridge_ranker"], 0.0)
        self.assertLess(weights["xgboost_ranker"], 0.0)
        self.assertNotIn("hist_gradient_boosting_ranker", weights)
        self.assertAlmostEqual(
            sum(abs(value) for value in weights.values()),
            1.0,
        )

    def test_polarity_ensemble_inverts_negative_rank(self) -> None:
        scores = polarity_ensemble_scores(
            {"xgboost_ranker": [1.0, 2.0, 3.0]},
            {"xgboost_ranker": -1.0},
        )
        self.assertEqual(scores, [1.0, 0.5, 0.0])

    def test_no_history_fallback_is_regularized_ridge(self) -> None:
        weights = polarity_online_weights(
            {},
            ["momentum_baseline", "ridge_ranker"],
        )
        self.assertEqual(weights, {"ridge_ranker": 1.0})

    def test_future_holdout_is_strictly_after_freeze_and_can_support(self) -> None:
        predictions: list[dict[str, object]] = []
        periods: list[dict[str, object]] = []
        freeze = date(2026, 7, 30)
        for offset in range(0, MINIMUM_FUTURE_PREDICTIVE_FOLDS + 1):
            day = freeze + timedelta(days=31 * offset)
            day_text = day.isoformat()
            for rank, symbol in enumerate(("AAA", "BBB", "CCC"), start=1):
                predictions.append({
                    "model": "online_rank_ensemble_v1",
                    "test_date": day_text,
                    "symbol": symbol,
                    "score": float(4 - rank),
                    "relative_return": float(4 - rank) / 100.0,
                })
            periods.append({
                "model": "online_rank_ensemble_v1",
                "signal_date": day_text,
                "net_return": 0.02,
                "benchmark_return": 0.01,
                "turnover": 0.50,
            })
        rows = future_predictive_holdout_rows(
            predictions,
            periods,
            freeze_date=freeze.isoformat(),
        )
        ensemble = next(
            row for row in rows
            if row["model"] == "online_rank_ensemble_v1"
        )
        self.assertEqual(
            ensemble["future_fold_count"],
            MINIMUM_FUTURE_PREDICTIVE_FOLDS,
        )
        self.assertEqual(
            ensemble["status"],
            "FUTURE_HOLDOUT_SUPPORTS_PREDICTIVE_REFERENCE",
        )
        self.assertEqual(ensemble["actionable"], "false")


if __name__ == "__main__":
    unittest.main()
