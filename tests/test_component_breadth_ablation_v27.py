from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import component_breadth_ablation_v27 as v27


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
    label_end: date,
    relative_return: float,
    index: int,
) -> v27.ResearchRow:
    features = dict(FEATURE_TEMPLATE)
    features.update(
        {
            "dong_luong_12_1": float(index),
            "bien_dong_60": 0.50 - index * 0.05,
            "suc_manh_tuong_doi_120": float(index),
            "khoang_cach_ma60": float(index) / 10.0,
            "khoang_cach_ma120": float(index) / 10.0,
            "khoang_cach_ma250": float(index) / 10.0,
            "loi_nhuan_20": 1.0 if index >= 2 else -1.0,
            "loi_nhuan_60": 1.0 if index >= 2 else -1.0,
            "loi_nhuan_120": 1.0 if index >= 2 else -1.0,
            "loi_nhuan_250": 1.0 if index >= 2 else -1.0,
            "ty_le_dinh_52_tuan": float(index),
        }
    )
    return v27.ResearchRow(
        signal_day=signal_day,
        symbol=symbol,
        label_end=label_end,
        stock_return=relative_return + 0.01,
        benchmark_return=0.01,
        relative_return=relative_return,
        features=features,
    )


class ComponentBreadthAblationV27Tests(unittest.TestCase):
    def test_average_percentile_handles_ties(self) -> None:
        self.assertEqual(v27.average_percentile([1.0, 1.0, 3.0]), [0.25, 0.25, 1.0])

    def test_shrunk_weights_are_normalized_and_capped(self) -> None:
        rows: list[v27.ResearchRow] = []
        for month in range(1, 5):
            signal_day = date(2020, month, 1)
            label_end = date(2020, month, 20)
            for index in range(5):
                rows.append(
                    make_row(
                        signal_day,
                        f"S{index}",
                        label_end=label_end,
                        relative_return=float(index),
                        index=index,
                    )
                )
        weights = v27.shrunk_component_weights(rows)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertTrue(all(0.0 < value <= 0.50 for value in weights.values()))
        self.assertEqual(set(weights), set(v27.STABLE_THREE))

    def test_build_folds_purges_unfinished_labels(self) -> None:
        rows: list[v27.ResearchRow] = []
        dates = [date(2020 + index // 12, index % 12 + 1, 1) for index in range(18)]
        for position, signal_day in enumerate(dates):
            if position == 12:
                label_end = dates[14]
            else:
                label_end = date(signal_day.year, signal_day.month, 20)
            for index in range(5):
                rows.append(
                    make_row(
                        signal_day,
                        f"S{index}",
                        label_end=label_end,
                        relative_return=float(index),
                        index=index,
                    )
                )
        folds = v27.build_folds(
            rows,
            evaluation_months=6,
            minimum_train_months=12,
            inner_validation_months=1,
        )
        self.assertGreaterEqual(len(folds), 3)
        for fold in folds:
            validation_start = min(row.signal_day for row in fold.validation_rows)
            self.assertTrue(
                all(row.label_end < validation_start for row in fold.train_rows)
            )
            self.assertTrue(
                all(row.label_end < fold.test_day for row in fold.validation_rows)
            )

    def test_adaptive_weights_never_receive_test_rows(self) -> None:
        train = tuple(
            make_row(
                date(2020, 1, 1),
                f"T{index}",
                label_end=date(2020, 1, 20),
                relative_return=float(index),
                index=index,
            )
            for index in range(5)
        )
        validation = tuple(
            make_row(
                date(2020, 2, 1),
                f"V{index}",
                label_end=date(2020, 2, 20),
                relative_return=float(index),
                index=index,
            )
            for index in range(5)
        )
        test = tuple(
            make_row(
                date(2020, 3, 1),
                f"X{index}",
                label_end=date(2020, 3, 20),
                relative_return=float(index),
                index=index,
            )
            for index in range(5)
        )
        fold = v27.Fold(
            test_day=date(2020, 3, 1),
            train_rows=train,
            validation_rows=validation,
            test_rows=test,
        )
        observed: list[v27.ResearchRow] = []

        def fake_weights(rows, **_kwargs):
            observed.extend(rows)
            return {
                "low_volatility": 1.0 / 3.0,
                "relative_strength_120": 1.0 / 3.0,
                "high_52_week": 1.0 / 3.0,
            }

        with patch.object(v27, "shrunk_component_weights", side_effect=fake_weights):
            candidate_rows, _, _ = v27.build_predictions([fold])

        self.assertEqual(
            [id(row) for row in observed],
            [id(row) for row in train + validation],
        )
        observed_ids = {id(row) for row in observed}
        self.assertTrue(all(id(row) not in observed_ids for row in test))
        self.assertEqual(
            {str(row["model"]) for row in candidate_rows},
            set(v27.CANDIDATE_MODELS),
        )

    def test_invalid_breadth_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "V27_INVALID_BREADTHS"):
            v27._normalize_breadths((3, 10))


if __name__ == "__main__":
    unittest.main()
