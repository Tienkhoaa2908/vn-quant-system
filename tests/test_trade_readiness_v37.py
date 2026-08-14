from __future__ import annotations

import unittest

from he_thong_dinh_luong import trade_readiness_v37 as v37


class TradeReadinessV37Tests(unittest.TestCase):
    def _v36(self, *, ledger: bool = False, data: bool = False) -> dict[str, object]:
        return {
            "policy_id": v37.EXPECTED_POLICY_ID,
            "frozen_policy_unchanged": True,
            "selection_lineage": {"exact_match": True, "period_count": 51},
            "ledger_status": "SUCCESS" if ledger else "NOT_RUN_BLOCKED",
            "exact_cash_ledger_pnl_computed": ledger,
            "exact_vnindex_comparison_computed": ledger,
            "data_assurance": {"valid": data},
            "automatic_reference_preparation": {},
            "blockers": [] if data else ["POINT_IN_TIME_SECTOR_MASTER_MISSING"],
        }

    def _paper(self, count: int, *, positive: bool = True) -> list[dict[str, object]]:
        value = 0.01 if positive else -0.01
        return [
            {
                "signal_date": f"2027-{index + 1:02d}-28",
                "label_end": f"2027-{index + 2:02d}-28",
                "contract_ok": True,
                "net_return": value,
                "benchmark_return": 0.0,
                "net_excess_return": value,
                "drawdown": -0.05,
            }
            for index in range(count)
        ]

    def _ops(self, passed: bool) -> dict[str, object]:
        return {key: passed for key in v37.OPS_KEYS}

    def test_current_state_is_data_blocked(self) -> None:
        report = v37.evaluate_trade_readiness(self._v36(), [], self._ops(False))
        self.assertEqual(report["capital_stage"], "DATA_BLOCKED")
        self.assertFalse(report["manual_micro_live_review_eligible"])
        self.assertEqual(report["readiness_score_percent"], 30.0)

    def test_exact_ledger_without_holdout_is_paper_only(self) -> None:
        report = v37.evaluate_trade_readiness(
            self._v36(ledger=True, data=True),
            self._paper(3),
            self._ops(True),
        )
        self.assertEqual(report["capital_stage"], "PAPER_ONLY")
        self.assertFalse(report["manual_micro_live_review_eligible"])

    def test_twelve_good_observations_and_ops_allow_manual_review_only(self) -> None:
        report = v37.evaluate_trade_readiness(
            self._v36(ledger=True, data=True),
            self._paper(12),
            self._ops(True),
        )
        self.assertEqual(report["capital_stage"], "MANUAL_MICRO_LIVE_REVIEW_ELIGIBLE")
        self.assertTrue(report["manual_micro_live_review_eligible"])
        self.assertFalse(report["live_capital_approved"])
        self.assertFalse(report["automatic_live_orders_allowed"])
        self.assertEqual(report["readiness_score_percent"], 100.0)

    def test_bad_future_quality_never_passes(self) -> None:
        report = v37.evaluate_trade_readiness(
            self._v36(ledger=True, data=True),
            self._paper(12, positive=False),
            self._ops(True),
        )
        self.assertEqual(report["capital_stage"], "PAPER_ONLY")
        self.assertFalse(report["manual_micro_live_review_eligible"])


if __name__ == "__main__":
    unittest.main()
