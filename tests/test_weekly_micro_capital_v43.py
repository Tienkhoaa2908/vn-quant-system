from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong import weekly_micro_capital_v43 as v43


class WeeklyMicroCapitalV43Tests(unittest.TestCase):
    def test_average_percentile_preserves_ties(self) -> None:
        result = v43.average_percentile([3.0, 1.0, 1.0, 5.0])
        self.assertEqual(result[1], result[2])
        self.assertLess(result[1], result[0])
        self.assertLess(result[0], result[3])

    def test_shrunk_weights_normalized_and_capped(self) -> None:
        rows = []
        for month in range(12):
            signal_day = date(2020 + month // 12, month % 12 + 1, 1)
            for index in range(6):
                rows.append(
                    v43.ResearchRow(
                        signal_day=signal_day,
                        label_end=signal_day,
                        symbol=f"S{index}",
                        relative_return=float(index),
                        volatility_60=0.01 + index / 1000,
                        risk_on=True,
                        components={
                            "low_volatility": float(index),
                            "relative_strength_120": float(index),
                            "high_52_week": float(index),
                        },
                    )
                )
        weights = v43.shrunk_component_weights(rows)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertLessEqual(max(weights.values()), 0.5 + 1e-12)

    def test_exit_buffer_requires_consecutive_months(self) -> None:
        holdings = {"AAA": 2}
        counts: dict[str, int] = {}
        first = v43.compute_exit_symbols(
            holdings,
            {"AAA": 21},
            counts,
            exit_rank=20,
            exit_months=2,
        )
        second = v43.compute_exit_symbols(
            holdings,
            {"AAA": 22},
            counts,
            exit_rank=20,
            exit_months=2,
        )
        self.assertEqual(first, [])
        self.assertEqual(second, ["AAA"])

    def test_affordable_quantity_uses_odd_lot_unit(self) -> None:
        quantity = v43.affordable_quantity(250_000.0, 70_000.0, 20.0)
        self.assertEqual(quantity, 3)

    def test_capped_inverse_vol_weights(self) -> None:
        ranking = [f"S{i}" for i in range(10)]
        volatility = {
            symbol: 0.01 + index / 1000
            for index, symbol in enumerate(ranking)
        }
        weights = v43.capped_inverse_vol_weights(
            ranking,
            volatility,
            target_count=10,
            symbol_cap=0.15,
        )
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)
        self.assertLessEqual(max(weights.values()), 0.15 + 1e-12)

    def test_xirr_one_year_double(self) -> None:
        value = v43.xirr(
            [
                (date(2020, 1, 1), -100.0),
                (date(2021, 1, 1), 200.0),
            ]
        )
        self.assertIsNotNone(value)
        self.assertAlmostEqual(float(value), 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
