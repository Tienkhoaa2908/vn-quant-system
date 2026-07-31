from __future__ import annotations

import unittest

from he_thong_dinh_luong import model_lab_upgrade_v5 as v5


def _period(
    day: str,
    *,
    model: str = "robust_technical_ensemble_v1",
    net_return: float,
    turnover: float,
) -> dict[str, object]:
    return {
        "model": model,
        "signal_date": day,
        "net_return": net_return,
        "turnover": turnover,
    }


class ModelLabUpgradeV5Tests(unittest.TestCase):
    def test_historical_oos_before_freeze_is_not_future_holdout(self) -> None:
        buffered = [
            _period("2026-05-29", net_return=0.20, turnover=0.10),
            _period("2026-07-30", net_return=0.20, turnover=0.10),
        ]
        baseline = [
            _period("2026-05-29", net_return=-0.10, turnover=0.80),
            _period("2026-07-30", net_return=-0.10, turnover=0.80),
        ]
        rows = v5.future_holdout_rows(buffered, baseline)
        self.assertEqual(rows[0]["future_fold_count"], 0)
        self.assertEqual(rows[0]["status"], "INSUFFICIENT_FUTURE_HOLDOUT")
        self.assertEqual(rows[0]["actionable"], "false")

    def test_twelve_strictly_future_folds_can_support_policy_candidate(self) -> None:
        buffered = [
            _period(f"2026-08-{day:02d}", net_return=0.02, turnover=0.20)
            for day in range(1, 13)
        ]
        baseline = [
            _period(f"2026-08-{day:02d}", net_return=0.01, turnover=0.40)
            for day in range(1, 13)
        ]
        rows = v5.future_holdout_rows(buffered, baseline)
        self.assertEqual(rows[0]["future_fold_count"], 12)
        self.assertEqual(
            rows[0]["status"],
            "FUTURE_HOLDOUT_SUPPORTS_POLICY_CANDIDATE",
        )
        self.assertEqual(
            rows[0]["base_model_research_gate_still_required"],
            "true",
        )
        self.assertEqual(rows[0]["actionable"], "false")

    def test_future_holdout_can_reject_policy(self) -> None:
        buffered = [
            _period(f"2026-09-{day:02d}", net_return=-0.01, turnover=0.50)
            for day in range(1, 13)
        ]
        baseline = [
            _period(f"2026-09-{day:02d}", net_return=0.01, turnover=0.40)
            for day in range(1, 13)
        ]
        rows = v5.future_holdout_rows(buffered, baseline)
        self.assertEqual(
            rows[0]["status"],
            "FUTURE_HOLDOUT_DOES_NOT_SUPPORT_POLICY",
        )

    def test_minimum_future_folds_must_be_positive(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "MODEL_LAB_HOLDOUT_MINIMUM_NONPOSITIVE",
        ):
            v5.future_holdout_rows([], [], minimum_folds=0)

    def test_v5_inherits_ten_bps_tax_default(self) -> None:
        args = v5._parser().parse_args([
            "--input-zip", "input.zip",
            "--output-dir", "output",
        ])
        self.assertEqual(args.sell_tax_bps, 10.0)


if __name__ == "__main__":
    unittest.main()
