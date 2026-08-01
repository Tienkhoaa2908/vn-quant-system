from __future__ import annotations

import unittest

from he_thong_dinh_luong import model_lab
from he_thong_dinh_luong.model_lab_core import ENSEMBLE_MODEL
from he_thong_dinh_luong.model_lab_upgrade_v11 import capped_policy_metrics
from he_thong_dinh_luong.model_lab_upgrade_v12 import (
    corrected_turnover_capped_periods,
)


def prediction_rows(day: str, symbols: list[str]) -> list[dict[str, object]]:
    return [
        {
            "model": ENSEMBLE_MODEL,
            "fold": f"wf_{day}",
            "test_date": day,
            "symbol": symbol,
            "score": float(len(symbols) - index),
            "percentile": 1.0 - index / len(symbols),
            "rank": index + 1,
            "selected_top_k": str(index < 10).lower(),
            "label_end": day,
            "stock_return": 0.01 + index / 10_000.0,
            "benchmark_return": 0.0,
            "relative_return": 0.01 + index / 10_000.0,
        }
        for index, symbol in enumerate(symbols)
    ]


class ModelLabUpgradeV11Tests(unittest.TestCase):
    def test_three_replacement_cap_retains_seven_available_holdings(self):
        rows = [
            *prediction_rows("2026-01-30", list("ABCDEFGHIJKL")),
            *prediction_rows(
                "2026-02-27",
                [
                    "K", "L", "M", "A", "B", "C", "D",
                    "E", "F", "G", "H", "I", "J",
                ],
            ),
        ]
        periods = corrected_turnover_capped_periods(
            rows,
            top_k=10,
            max_voluntary_replacements=3,
            buy_fee_bps=15.0,
            sell_fee_bps=15.0,
            sell_tax_bps=10.0,
            slippage_bps=10.0,
        )
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0]["voluntary_replacement_count"], 0)
        self.assertEqual(periods[1]["voluntary_replacement_count"], 3)
        self.assertEqual(periods[1]["forced_exit_count"], 0)
        self.assertEqual(
            periods[1]["voluntary_replacement_cap_respected"],
            "true",
        )
        selected = set(str(periods[1]["selected_symbols"]).split("|"))
        self.assertEqual(
            selected,
            {"A", "B", "C", "D", "E", "F", "G", "K", "L", "M"},
        )
        self.assertAlmostEqual(float(periods[1]["turnover"]), 0.3)

    def test_forced_exits_do_not_consume_voluntary_budget(self):
        rows = [
            *prediction_rows("2026-01-30", list("ABCDEFGHIJKL")),
            *prediction_rows(
                "2026-02-27",
                [
                    "K", "L", "M", "N", "O", "A",
                    "B", "C", "D", "E", "P", "Q",
                ],
            ),
        ]
        periods = corrected_turnover_capped_periods(
            rows,
            top_k=10,
            max_voluntary_replacements=3,
            buy_fee_bps=15.0,
            sell_fee_bps=15.0,
            sell_tax_bps=10.0,
            slippage_bps=10.0,
        )
        second = periods[1]
        self.assertEqual(second["forced_exit_count"], 5)
        self.assertEqual(second["voluntary_replacement_count"], 0)
        self.assertEqual(
            second["voluntary_replacement_cap_respected"],
            "true",
        )
        selected = set(str(second["selected_symbols"]).split("|"))
        self.assertTrue({"A", "B", "C", "D", "E"}.issubset(selected))
        self.assertAlmostEqual(float(second["turnover"]), 0.5)

    def test_invalid_replacement_cap_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "MODEL_LAB_V11_REPLACEMENT_CAP_OUT_OF_RANGE",
        ):
            corrected_turnover_capped_periods(
                prediction_rows("2026-01-30", list("ABCDEFGHIJKL")),
                top_k=10,
                max_voluntary_replacements=11,
                buy_fee_bps=15.0,
                sell_fee_bps=15.0,
                sell_tax_bps=10.0,
                slippage_bps=10.0,
            )

    def test_metrics_include_subperiod_and_concentration_checks(self):
        rows = [
            {
                "gross_return": 0.03,
                "benchmark_return": 0.01,
                "gross_excess_return": 0.02,
                "net_return": 0.028,
                "net_excess_return": 0.018,
                "turnover": 0.3,
            },
            {
                "gross_return": 0.02,
                "benchmark_return": 0.01,
                "gross_excess_return": 0.01,
                "net_return": 0.018,
                "net_excess_return": 0.008,
                "turnover": 0.3,
            },
            {
                "gross_return": 0.025,
                "benchmark_return": 0.01,
                "gross_excess_return": 0.015,
                "net_return": 0.023,
                "net_excess_return": 0.013,
                "turnover": 0.3,
            },
            {
                "gross_return": 0.02,
                "benchmark_return": 0.01,
                "gross_excess_return": 0.01,
                "net_return": 0.018,
                "net_excess_return": 0.008,
                "turnover": 0.3,
            },
        ]
        metrics = capped_policy_metrics(rows)
        self.assertEqual(metrics["period_count"], 4)
        self.assertGreater(metrics["relative_total_return"], 0.0)
        self.assertGreater(metrics["first_half_average_net_excess"], 0.0)
        self.assertGreater(metrics["second_half_average_net_excess"], 0.0)
        self.assertGreater(
            metrics["leave_best_period_out_relative_total_return"],
            0.0,
        )
        self.assertLessEqual(
            metrics["best_positive_excess_contribution_share"],
            0.50,
        )

    def test_stable_entrypoint_routes_through_v14(self):
        self.assertEqual(
            model_lab.run_model_lab.__module__,
            "he_thong_dinh_luong.model_lab_upgrade_v14",
        )


if __name__ == "__main__":
    unittest.main()
