from __future__ import annotations

from datetime import date, timedelta
import unittest

from he_thong_dinh_luong import hnx_cross_market_validation_v41 as v41


class V41ContractTests(unittest.TestCase):
    def test_average_percentile_preserves_ties(self) -> None:
        values = v41.average_percentile([3.0, 1.0, 1.0, 5.0])
        self.assertEqual(values[1], values[2])
        self.assertLess(values[1], values[0])
        self.assertLess(values[0], values[3])

    def test_shrunk_weights_use_only_completed_past_labels(self) -> None:
        rows = []
        start = date(2020, 1, 31)
        for month in range(18):
            signal = start + timedelta(days=31 * month)
            label_end = signal + timedelta(days=20)
            for index in range(8):
                rows.append(
                    {
                        "signal_day": signal,
                        "label_end": label_end,
                        "symbol": f"S{index}",
                        "relative_return": index / 100.0,
                        "components": {
                            "low_volatility": float(index),
                            "relative_strength_120": float(index),
                            "high_52_week": float(index),
                        },
                    }
                )
        before = start + timedelta(days=31 * 15)
        weights, audit = v41.shrunk_component_weights(rows, before_day=before, minimum_months=12)
        self.assertTrue(audit["uses_rows_with_label_end_before_signal"])
        self.assertGreaterEqual(audit["usable_months"], 12)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertLessEqual(max(weights.values()), 0.50 + 1e-12)

    def test_inverse_vol_weights_respect_symbol_cap(self) -> None:
        rows = [
            {"symbol": f"S{index}", "volatility_60": 0.01 + index * 0.001}
            for index in range(10)
        ]
        weights = v41.inverse_vol_weights(rows)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)
        self.assertLessEqual(max(weights.values()), 0.15 + 1e-12)

    def test_gate_can_be_performance_pass_but_not_strict(self) -> None:
        summaries = []
        for scenario, total, relative in (
            ("BASE", 0.40, 0.20),
            ("STRESS", 0.32, 0.14),
            ("SEVERE", 0.18, 0.05),
        ):
            summaries.append(
                {
                    "protocol": v41.PRIMARY,
                    "scenario": scenario,
                    "period_count": 60,
                    "net_total_return": total,
                    "relative_total_return": relative,
                    "mean_fill_ratio": 0.95,
                }
            )
        summaries.append(
            {
                "protocol": v41.MOMENTUM,
                "scenario": "BASE",
                "period_count": 60,
                "net_total_return": 0.20,
                "relative_total_return": 0.03,
                "mean_fill_ratio": 0.95,
            }
        )
        periods = []
        for index in range(60):
            year = 2020 + index // 12
            periods.append(
                {
                    "protocol": v41.PRIMARY,
                    "scenario": "BASE",
                    "signal_day": f"{year:04d}-{index % 12 + 1:02d}-28",
                    "period_net_return": 0.012,
                    "benchmark_return": 0.005,
                }
            )
        ic_rows = [
            {"protocol": v41.PRIMARY, "rank_ic": 0.05 if index % 3 else -0.01}
            for index in range(60)
        ]
        yearly = [
            {
                "protocol": v41.PRIMARY,
                "scenario": "BASE",
                "year": year,
                "excess_return": 0.08,
            }
            for year in range(2020, 2025)
        ]
        gate = v41.evaluate_gate(
            summaries=summaries,
            period_rows=periods,
            ic_rows=ic_rows,
            yearly_rows=yearly,
            strict_instrument_history_complete=False,
        )
        self.assertTrue(gate["performance_gate_passed"])
        self.assertFalse(gate["strict_cross_market_gate_passed"])
        self.assertEqual(gate["status"], "PROVISIONAL_CROSS_MARKET_EVIDENCE")
        self.assertFalse(gate["live_capital_approved"])
        self.assertFalse(gate["automatic_live_orders_allowed"])

    def test_gate_fails_when_transfer_does_not_beat_benchmark(self) -> None:
        summaries = [
            {
                "protocol": v41.PRIMARY,
                "scenario": scenario,
                "period_count": 40,
                "net_total_return": -0.10,
                "relative_total_return": -0.20,
                "mean_fill_ratio": 0.90,
            }
            for scenario in ("BASE", "STRESS", "SEVERE")
        ]
        summaries.append(
            {
                "protocol": v41.MOMENTUM,
                "scenario": "BASE",
                "period_count": 40,
                "net_total_return": 0.10,
                "relative_total_return": 0.05,
                "mean_fill_ratio": 0.90,
            }
        )
        gate = v41.evaluate_gate(
            summaries=summaries,
            period_rows=[],
            ic_rows=[],
            yearly_rows=[],
            strict_instrument_history_complete=False,
        )
        self.assertFalse(gate["performance_gate_passed"])
        self.assertEqual(gate["status"], "CROSS_MARKET_TRANSFER_FAILED")


if __name__ == "__main__":
    unittest.main()
