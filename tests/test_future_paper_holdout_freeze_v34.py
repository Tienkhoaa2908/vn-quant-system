from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from src.he_thong_dinh_luong import future_paper_holdout_freeze_v34 as v34


class FuturePaperHoldoutFreezeV34Tests(unittest.TestCase):
    def _policy(self) -> dict[str, object]:
        core = {
            "schema_version": v34.POLICY_SCHEMA_VERSION,
            "status": "FROZEN_FOR_FUTURE_PAPER_HOLDOUT",
            "frozen_at": "2026-08-03T09:22:00+07:00",
            "policy_id": "c3-top10-cap3-test",
            "holdout_contract": {
                "minimum_completed_monthly_observations": 12,
            },
            "kill_switch": dict(v34.DEFAULT_KILL_SWITCH),
        }
        return core

    def _observation(
        self,
        index: int,
        *,
        signal_start: datetime | None = None,
        contract_ok: bool = True,
    ) -> dict[str, object]:
        start = signal_start or datetime(
            2026,
            8,
            31,
            15,
            0,
            tzinfo=timezone(timedelta(hours=7)),
        )
        signal = start + timedelta(days=31 * index)
        label_end = signal.date() + timedelta(days=28)
        recorded = datetime.combine(
            label_end + timedelta(days=1),
            datetime.min.time(),
            tzinfo=signal.tzinfo,
        )
        return {
            "policy_id": "c3-top10-cap3-test",
            "signal_timestamp": signal.isoformat(),
            "label_end": label_end.isoformat(),
            "observation_recorded_at": recorded.isoformat(),
            "rank_ic": 0.05,
            "net_excess_return": 0.01,
            "turnover": 0.30,
            "relative_nav": 1.01 ** (index + 1),
            "contract_ok": contract_ok,
            "data_quality_ok": True,
            "score_hash_match": True,
            "selection_policy_match": True,
            "exact_cash_ledger_pnl_computed": False,
            "notes": "",
        }

    def test_prefreeze_signal_is_rejected(self) -> None:
        row = self._observation(
            0,
            signal_start=datetime(
                2026,
                7,
                31,
                15,
                0,
                tzinfo=timezone(timedelta(hours=7)),
            ),
        )
        with self.assertRaisesRegex(
            ValueError,
            "V34_SIGNAL_NOT_STRICTLY_FUTURE",
        ):
            v34.evaluate_observations([row], policy=self._policy())

    def test_twelve_future_observations_complete_only_technical_holdout(
        self,
    ) -> None:
        rows = [self._observation(index) for index in range(12)]
        result = v34.evaluate_observations(rows, policy=self._policy())
        self.assertEqual(
            result["status"],
            "PAPER_HOLDOUT_COMPLETE_TECHNICAL_ONLY",
        )
        self.assertTrue(result["future_holdout_complete"])
        self.assertFalse(result["research_eligible"])
        self.assertFalse(result["live_capital_approved"])
        self.assertFalse(result["automatic_live_orders_allowed"])

    def test_contract_violation_triggers_review(self) -> None:
        rows = [
            self._observation(index, contract_ok=index != 5)
            for index in range(6)
        ]
        result = v34.evaluate_observations(rows, policy=self._policy())
        self.assertEqual(result["status"], "MODEL_UNDER_REVIEW")
        self.assertTrue(result["block_new_paper_positions"])
        self.assertIn(
            "POLICY_OR_DATA_CONTRACT_VIOLATION",
            result["kill_switch_triggers"],
        )

    def test_policy_core_excludes_july_snapshot_and_locks_cap_three(
        self,
    ) -> None:
        report = {
            "source_v32_1_outer_test_last_date": "2026-06-30",
            "recommendation": v34.EXPECTED_RECOMMENDATION,
        }
        evidence = {
            "summary": {"base_relative_total_return": 0.40},
            "paired_vs_nested": {
                "bootstrap_probability_delta_positive": 0.96
            },
        }
        core = v34._policy_core(
            source={"artifact_zip_sha256": "abc"},
            evidence=evidence,
            report=report,
            freeze_timestamp=datetime(
                2026,
                8,
                3,
                9,
                22,
                tzinfo=timezone(timedelta(hours=7)),
            ),
            exclude_signal_through=datetime(2026, 7, 31).date(),
        )
        self.assertEqual(
            core["policy"]["fixed_voluntary_replacement_cap"],
            3,
        )
        self.assertEqual(
            core["holdout_contract"][
                "known_pre_freeze_signals_excluded_through"
            ],
            "2026-07-31",
        )
        self.assertFalse(
            core["holdout_contract"]["historical_observations_counted"]
        )


if __name__ == "__main__":
    unittest.main()
