from __future__ import annotations

import csv
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.model_policy_ablation_v25 import (
    build_walk_forward_folds_v25,
    rescore_existing_model_output,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row


class ModelPolicyAblationV25Tests(unittest.TestCase):
    def _rows(self, months: int = 84) -> list[Row]:
        result: list[Row] = []
        start = date(2018, 1, 31)
        for index in range(months):
            day = start + timedelta(days=30 * index)
            label_end = day + timedelta(days=20)
            for symbol in ("AAA", "BBB", "CCC"):
                result.append(
                    Row(
                        ngay=day,
                        ma=symbol,
                        features={"x": float(index)},
                        relative_return=0.01,
                        label_end=label_end,
                    )
                )
        return result

    def test_rolling_window_keeps_only_latest_train_months(self) -> None:
        rows = self._rows()
        expanding = build_walk_forward_folds_v25(
            rows,
            evaluation_months=12,
            minimum_train_months=24,
            inner_validation_months=3,
            train_window_months=None,
        )
        rolling = build_walk_forward_folds_v25(
            rows,
            evaluation_months=12,
            minimum_train_months=24,
            inner_validation_months=3,
            train_window_months=24,
        )
        self.assertEqual(
            [fold.test_day for fold in expanding],
            [fold.test_day for fold in rolling],
        )
        self.assertGreater(
            len({row.ngay for row in expanding[-1].train_rows}),
            24,
        )
        self.assertEqual(
            len({row.ngay for row in rolling[-1].train_rows}),
            24,
        )
        self.assertLess(
            min(row.ngay for row in expanding[-1].train_rows),
            min(row.ngay for row in rolling[-1].train_rows),
        )

    def test_train_window_below_minimum_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "V25_TRAIN_WINDOW_BELOW_MINIMUM_TRAIN",
        ):
            build_walk_forward_folds_v25(
                self._rows(),
                evaluation_months=12,
                minimum_train_months=24,
                inner_validation_months=3,
                train_window_months=23,
            )

    def _write_existing_output(self, root: Path) -> None:
        summary = {
            "backtest_contract": {"top_k": 2},
            "dnse_cash_cost_contract_v13": {
                "broker_buy_fee_bps": 0.0,
                "broker_sell_fee_bps": 0.0,
                "exchange_buy_fee_bps": 2.7,
                "exchange_sell_fee_bps": 2.7,
                "sell_tax_bps": 10.0,
                "transfer_fee_vnd_per_share": 0.3,
                "transfer_reference_price_vnd": 10000.0,
                "base_slippage_bps_each_side": 5.0,
                "stress_slippage_bps_each_side": 10.0,
            },
        }
        (root / "model_lab_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        fields = [
            "model",
            "test_date",
            "symbol",
            "rank",
            "score",
            "label_end",
            "stock_return",
            "benchmark_return",
            "relative_return",
        ]
        rows: list[dict[str, object]] = []
        for month in range(1, 11):
            day = date(2025, month, 28)
            label_end = day + timedelta(days=28)
            for rank, symbol in enumerate(("AAA", "BBB", "CCC"), start=1):
                stock_return = 0.03 - rank * 0.005
                benchmark_return = 0.01
                rows.append(
                    {
                        "model": "robust_technical_ensemble_v1",
                        "test_date": day.isoformat(),
                        "symbol": symbol,
                        "rank": rank,
                        "score": 4 - rank,
                        "label_end": label_end.isoformat(),
                        "stock_return": stock_return,
                        "benchmark_return": benchmark_return,
                        "relative_return": stock_return - benchmark_return,
                    }
                )
        with (root / "oos_predictions.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_existing_oos_is_rescored_with_one_month_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_output = root / "model-output"
            destination = root / "ablation"
            model_output.mkdir()
            self._write_existing_output(model_output)
            report = rescore_existing_model_output(
                model_output,
                destination,
                validation_months=6,
                test_months=1,
                minimum_outer_test_periods=3,
                replacement_caps=(0, 1, 2),
            )
            result = report["result"]
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["policy_test_months"], 1)
            self.assertTrue(report["training_reused"])
            self.assertFalse(report["independent_holdout"])
            self.assertEqual(result["test_months"], 1)
            diagnostics = result["candidate_diagnostics"]
            self.assertEqual(len(diagnostics), 1)
            self.assertEqual(diagnostics[0]["outer_test_period_count"], 4)
            self.assertTrue((destination / "model_comparison_v25.csv").is_file())
            self.assertTrue((destination / "model_policy_ablation_v25.json").is_file())


if __name__ == "__main__":
    unittest.main()
