from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from vn_quant_local import v53_cycle_cleanup as v53


def status_for(*, actual: int, remaining: int, match_method: str | None):
    return {
        "status": "ACTIVE",
        "latest_market_day_for_cycle_lock": "2026-08-05",
        "shadow_plans": [
            {
                "plan_id": "plan-1",
                "status": "PENDING_MARKET_DATA",
                "execution_day": "2026-08-06",
            }
        ],
        "cycle_catalog": [
            {
                "plan_id": "plan-1",
                "cycle_id": "cycle-1",
                "planned_quantity": 4,
                "actual_quantity": actual,
                "remaining_quantity": remaining,
                "intents": [],
            }
        ],
        "reconciliation": [
            {
                "intent_id": "plan-1:BUY:MSB",
                "plan_id": "plan-1",
                "side": "BUY",
                "symbol": "MSB",
                "planned_quantity": 4,
                "actual_quantity": actual,
                "remaining_quantity": remaining,
                "match_method": match_method,
                "actual_event_ids": ["fill-1"] if actual else [],
                "status": "MATCHED_PARTIAL_SHADOW_PENDING" if actual else "PLANNED_SHADOW_PENDING",
                "shadow_pending": True,
                "shadow_execution_day": "2026-08-06",
                "shadow_quantity": 0,
            }
        ],
    }


class V53CyclePolicyTests(unittest.TestCase):
    def test_partial_auto_match_cycle_is_discardable(self) -> None:
        row = v53._cycle_policy_rows(
            status_for(
                actual=2,
                remaining=2,
                match_method="AUTO_NEWEST_OPEN_INTENT",
            )
        )[0]
        self.assertTrue(row["discardable"])
        self.assertTrue(row["discard_reassigns_auto_fills"])
        self.assertTrue(row["auto_match_only"])
        self.assertEqual(row["intents"][0]["actual_quantity"], 2)

    def test_explicit_plan_binding_locks_partial_cycle(self) -> None:
        row = v53._cycle_policy_rows(
            status_for(
                actual=2,
                remaining=2,
                match_method="EXPLICIT_PLAN_ID",
            )
        )[0]
        self.assertFalse(row["discardable"])
        self.assertEqual(row["discard_lock_reason"], "EXPLICIT_PLAN_BINDING")

    def test_complete_cycle_is_locked(self) -> None:
        row = v53._cycle_policy_rows(
            status_for(
                actual=4,
                remaining=0,
                match_method="AUTO_NEWEST_OPEN_INTENT",
            )
        )[0]
        self.assertFalse(row["discardable"])
        self.assertEqual(row["discard_lock_reason"], "ACTUAL_COMPLETE")

    def test_observed_shadow_locks_empty_cycle(self) -> None:
        value = status_for(actual=0, remaining=4, match_method=None)
        value["shadow_plans"][0]["status"] = "EXECUTED"
        value["shadow_plans"][0]["execution_day"] = "2026-08-05"
        row = v53._cycle_policy_rows(value)[0]
        self.assertFalse(row["discardable"])
        self.assertEqual(
            row["discard_lock_reason"],
            "SHADOW_EXECUTION_ALREADY_OBSERVED",
        )


class V53CommandTests(unittest.TestCase):
    def test_bulk_command_routes_all_plan_ids_once(self) -> None:
        note = json.dumps(
            {
                "plan_ids": ["plan-1", "plan-2"],
                "reason": "Chỉ xem",
            }
        )
        with patch.object(
            v53,
            "discard_cycles",
            return_value={"status": "SUCCESS", "discarded_count": 2},
        ) as mocked:
            result = v53.add_actual_cashflow_v53(
                flow_type="DISCARD_CYCLES",
                amount_vnd=0,
                event_day="2026-08-05",
                note=note,
            )
        self.assertEqual(result["discarded_count"], 2)
        mocked.assert_called_once_with(
            plan_ids=["plan-1", "plan-2"],
            reason="Chỉ xem",
        )

    def test_single_command_uses_same_bulk_engine(self) -> None:
        note = json.dumps({"plan_id": "plan-1", "reason": "Không làm"})
        with patch.object(
            v53,
            "discard_cycles",
            return_value={"status": "SUCCESS", "discarded_count": 1},
        ) as mocked:
            v53.add_actual_cashflow_v53(
                flow_type="DISCARD_CYCLE",
                amount_vnd=0,
                event_day="2026-08-05",
                note=note,
            )
        mocked.assert_called_once_with(
            plan_ids=["plan-1"],
            reason="Không làm",
        )


if __name__ == "__main__":
    unittest.main()
