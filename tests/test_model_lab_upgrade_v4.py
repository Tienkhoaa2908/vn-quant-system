from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from he_thong_dinh_luong import model_lab_upgrade_v4 as v4
from he_thong_dinh_luong.model_lab_core import BacktestConfig


def _row(
    day: str,
    symbol: str,
    rank: int,
    stock_return: float = 0.01,
    benchmark_return: float = 0.0,
) -> dict[str, object]:
    return {
        "model": "ridge_ranker",
        "test_date": day,
        "symbol": symbol,
        "rank": rank,
        "label_end": day,
        "stock_return": stock_return,
        "benchmark_return": benchmark_return,
    }


class ModelLabUpgradeV4Tests(unittest.TestCase):
    def test_core_default_sell_tax_is_ten_bps(self) -> None:
        self.assertEqual(BacktestConfig().sell_tax_bps, 10.0)

    def test_cli_default_sell_tax_is_ten_bps(self) -> None:
        args = v4._parser().parse_args([
            "--input-zip", "input.zip",
            "--output-dir", "output",
        ])
        self.assertEqual(args.sell_tax_bps, 10.0)
        self.assertIsNone(args.turnover_buffer)

    def test_wrapper_injects_cost_default_and_structural_buffer(self) -> None:
        with (
            patch.object(v4.v3, "run_model_lab", return_value={"status": "SUCCESS"}) as base,
            patch.object(
                v4,
                "publish_v4_diagnostics",
                return_value={"turnover_buffer_status": "REFERENCE_ONLY"},
            ) as diagnostics,
        ):
            result = v4.run_model_lab(
                input_zip=Path("input.zip"),
                output_dir=Path("output"),
                top_k=10,
            )
        self.assertEqual(base.call_args.kwargs["sell_tax_bps"], 10.0)
        self.assertEqual(diagnostics.call_args.kwargs["hold_buffer"], 5)
        self.assertEqual(result["turnover_buffer_status"], "REFERENCE_ONLY")

    def test_buffer_retains_prior_holdings_inside_rank_band(self) -> None:
        rows = [
            _row("2026-01-30", "A", 1),
            _row("2026-01-30", "B", 2),
            _row("2026-01-30", "C", 3),
            _row("2026-01-30", "D", 4),
            _row("2026-02-27", "C", 1),
            _row("2026-02-27", "D", 2),
            _row("2026-02-27", "A", 3),
            _row("2026-02-27", "B", 4),
        ]
        metrics, periods = v4.buffered_top_k_periods(
            rows,
            top_k=2,
            hold_buffer=2,
            buy_fee_bps=15.0,
            sell_fee_bps=15.0,
            sell_tax_bps=10.0,
            slippage_bps=10.0,
        )
        self.assertEqual(periods[0]["selected_symbols"], "A|B")
        self.assertEqual(periods[1]["selected_symbols"], "A|B")
        self.assertEqual(periods[1]["turnover"], 0.0)
        self.assertFalse(metrics["selection_uses_realized_returns"])
        self.assertTrue(metrics["research_gate_unchanged"])
        self.assertFalse(metrics["actionable"])

    def test_negative_buffer_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MODEL_LAB_BUFFER_NEGATIVE"):
            v4.buffered_top_k_periods(
                [_row("2026-01-30", "A", 1)],
                top_k=1,
                hold_buffer=-1,
                buy_fee_bps=15.0,
                sell_fee_bps=15.0,
                sell_tax_bps=10.0,
                slippage_bps=10.0,
            )


if __name__ == "__main__":
    unittest.main()
