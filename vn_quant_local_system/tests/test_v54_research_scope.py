from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from vn_quant_local import v54_research_scope as v54


class V54SellabilityTests(unittest.TestCase):
    def test_explicit_zero_sellable_is_not_executable(self) -> None:
        requested, executable, source = v54._sellability(
            {"quantity": 15, "sellable_quantity": 0},
            snapshot_sellable=15,
        )
        self.assertEqual(requested, 15)
        self.assertEqual(executable, 0)
        self.assertEqual(source, "PLAN_EXPLICIT_SELLABLE_QUANTITY")

    def test_wait_sellable_action_overrides_legacy_quantity(self) -> None:
        requested, executable, source = v54._sellability(
            {
                "quantity": 15,
                "sellable_quantity": 15,
                "action": "WAIT_SELLABLE",
            },
            snapshot_sellable=15,
        )
        self.assertEqual(requested, 15)
        self.assertEqual(executable, 0)
        self.assertEqual(source, "PLAN_CLASSIFIED_WAIT_SELLABLE")

    def test_plan_snapshot_limits_sell_when_plan_has_no_sellable_field(self) -> None:
        requested, executable, source = v54._sellability(
            {"quantity": 15},
            snapshot_sellable=4,
        )
        self.assertEqual(requested, 15)
        self.assertEqual(executable, 4)
        self.assertEqual(source, "BROKER_SNAPSHOT_AT_PLAN")

    def test_shadow_plan_sanitizer_removes_non_sellable_order(self) -> None:
        original = v54._ORIGINAL_ACTIVE_SHADOW_PLANS
        v54._ORIGINAL_ACTIVE_SHADOW_PLANS = lambda: (
            [
                {
                    "plan_id": "plan-1",
                    "details_json": json.dumps(
                        {
                            "exit_candidates": [
                                {
                                    "symbol": "MBB",
                                    "quantity": 15,
                                    "sellable_quantity": 0,
                                }
                            ],
                            "buy_orders": [],
                        }
                    ),
                }
            ],
            set(),
        )
        try:
            with patch.object(v54, "_sell_rows_for_plan", return_value=([], [])):
                plans, excluded = v54._active_shadow_plans_v54()
        finally:
            v54._ORIGINAL_ACTIVE_SHADOW_PLANS = original
        self.assertEqual(excluded, set())
        details = json.loads(plans[0]["details_json"])
        self.assertEqual(details["exit_candidates"], [])


class V54ScopePresentationTests(unittest.TestCase):
    def _base_status(self) -> dict[str, object]:
        return {
            "status": "ACTIVE",
            "latest_market_day_for_cycle_lock": "2026-08-05",
            "cycle_catalog": [
                {
                    "plan_id": "plan-old",
                    "created_at_vn": "04/08/2026 22:27:26",
                    "execution_day": "2026-08-05",
                    "shadow_status": "EXECUTED",
                    "planned_quantity": 9,
                    "actual_quantity": 2,
                    "remaining_quantity": 7,
                    "actual_complete": False,
                    "intents": [],
                },
                {
                    "plan_id": "plan-complete",
                    "execution_day": "2026-08-05",
                    "shadow_status": "EXECUTED",
                    "planned_quantity": 3,
                    "actual_quantity": 3,
                    "remaining_quantity": 0,
                    "actual_complete": True,
                    "intents": [],
                },
            ],
            "limitations": {},
        }

    def test_observed_but_incomplete_cycle_can_be_reclassified(self) -> None:
        original = v54._ORIGINAL_PERFORMANCE_STATUS
        v54._ORIGINAL_PERFORMANCE_STATUS = self._base_status
        blocked = {
            "side": "SELL",
            "symbol": "MBB",
            "planned_quantity": 15,
            "actual_quantity": 0,
            "remaining_quantity": 0,
            "status": "WAIT_SELLABLE_AT_PLAN",
            "compliance_eligible": False,
            "excluded_from_compliance": True,
        }
        plans = [
            {"plan_id": "plan-old", "details_json": "{}"},
            {"plan_id": "plan-complete", "details_json": "{}"},
        ]
        try:
            with patch.object(v54, "_all_plan_rows", return_value=plans), patch.object(
                v54,
                "_sell_rows_for_plan",
                side_effect=[([], [blocked]), ([], [])],
            ), patch.object(v54, "_research_catalog", return_value=[]), patch.object(
                v54, "research_only_plan_ids", return_value=set()
            ), patch.object(v54, "_scope_action_rows", return_value=[]):
                result = v54.performance_status_v54()
        finally:
            v54._ORIGINAL_PERFORMANCE_STATUS = original

        rows = {row["plan_id"]: row for row in result["cycle_catalog"]}
        self.assertTrue(rows["plan-old"]["research_scope_eligible"])
        self.assertTrue(rows["plan-old"]["research_scope_retroactive"])
        self.assertEqual(rows["plan-old"]["wait_sellable_quantity"], 15)
        self.assertEqual(rows["plan-old"]["compliance_planned_quantity"], 9)
        self.assertFalse(rows["plan-complete"]["research_scope_eligible"])
        self.assertEqual(
            rows["plan-complete"]["research_scope_lock_reason"],
            "ACTUAL_COMPLETE",
        )
        json.dumps(result, ensure_ascii=False)

    def test_retroactive_research_scope_is_visibly_curated(self) -> None:
        original = v54._ORIGINAL_PERFORMANCE_STATUS
        v54._ORIGINAL_PERFORMANCE_STATUS = lambda: {
            "status": "ACTIVE",
            "cycle_catalog": [],
            "limitations": {},
        }
        try:
            with patch.object(v54, "_all_plan_rows", return_value=[]), patch.object(
                v54,
                "_research_catalog",
                return_value=[{"plan_id": "plan-old", "retroactive": True}],
            ), patch.object(
                v54, "research_only_plan_ids", return_value={"plan-old"}
            ), patch.object(v54, "_scope_action_rows", return_value=[]):
                result = v54.performance_status_v54()
        finally:
            v54._ORIGINAL_PERFORMANCE_STATUS = original
        self.assertTrue(result["operational_scope_curated"])
        self.assertEqual(result["retroactive_research_only_count"], 1)


if __name__ == "__main__":
    unittest.main()
