from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from vn_quant_local import v52_commands
from vn_quant_local import v52_cycle_management as v52
from vn_quant_local import v52_discard_safety
from vn_quant_local import v52_status_safety


class V52ActionIndexTests(unittest.TestCase):
    def test_latest_restore_reactivates_cycle(self) -> None:
        rows = [
            {
                "action_time": "2026-08-05T09:00:00+00:00",
                "action_id": "a",
                "action_type": "DISCARD",
                "plan_id": "plan-1",
            },
            {
                "action_time": "2026-08-05T09:01:00+00:00",
                "action_id": "b",
                "action_type": "RESTORE",
                "plan_id": "plan-1",
            },
        ]
        index = v52.latest_cycle_action_index(rows)
        self.assertEqual(index["plan-1"]["action_type"], "RESTORE")

    def test_loader_excludes_discarded_plan_and_shadow(self) -> None:
        original = v52._ORIGINAL_LOAD_RECONCILIATION_INPUTS
        try:
            v52._ORIGINAL_LOAD_RECONCILIATION_INPUTS = lambda: (
                [
                    {"plan_id": "discarded"},
                    {"plan_id": "active"},
                ],
                [
                    {"plan_id": "discarded", "trade_id": "s1"},
                    {"plan_id": "active", "trade_id": "s2"},
                ],
                [{"event_id": "fill"}],
                "2026-08-05",
            )
            with patch.object(
                v52,
                "discarded_plan_ids",
                return_value={"discarded"},
            ):
                plans, shadow, actual, latest_day = (
                    v52._load_reconciliation_inputs_v52()
                )
            self.assertEqual([row["plan_id"] for row in plans], ["active"])
            self.assertEqual([row["trade_id"] for row in shadow], ["s2"])
            self.assertEqual(actual[0]["event_id"], "fill")
            self.assertEqual(latest_day, "2026-08-05")
        finally:
            v52._ORIGINAL_LOAD_RECONCILIATION_INPUTS = original


class V52DiscardSafetyTests(unittest.TestCase):
    def test_cycle_with_actual_fill_cannot_be_discarded(self) -> None:
        with patch.object(
            v52,
            "_plan_row",
            return_value={"plan_id": "plan-1"},
        ), patch.object(
            v52,
            "latest_cycle_action_index",
            return_value={},
        ), patch.object(
            v52,
            "_actual_quantity_for_plan",
            return_value=2,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "PERFORMANCE_CYCLE_HAS_ACTUAL_FILL",
            ):
                v52.discard_cycle(
                    plan_id="plan-1",
                    reason="Không thực hiện",
                )

    def test_executed_shadow_cannot_be_discarded(self) -> None:
        original = v52_discard_safety._ORIGINAL_DISCARD_CYCLE
        v52_discard_safety._ORIGINAL_DISCARD_CYCLE = lambda **kwargs: kwargs
        try:
            with patch.object(
                v52,
                "_plan_row",
                return_value={
                    "plan_id": "plan-1",
                    "status": "PENDING_MARKET_DATA",
                    "execution_day": "2026-08-05",
                },
            ), patch(
                "vn_quant_local.v52_discard_safety.performance._latest_market_day",
                return_value="2026-08-05",
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "PERFORMANCE_CYCLE_SHADOW_ALREADY_EXECUTED",
                ):
                    v52_discard_safety.discard_cycle_safe(
                        plan_id="plan-1",
                        reason="Không thực hiện",
                    )
        finally:
            v52_discard_safety._ORIGINAL_DISCARD_CYCLE = original

    def test_executed_shadow_cannot_be_restored(self) -> None:
        original = v52_discard_safety._ORIGINAL_RESTORE_CYCLE
        v52_discard_safety._ORIGINAL_RESTORE_CYCLE = lambda **kwargs: kwargs
        try:
            with patch.object(
                v52,
                "_plan_row",
                return_value={
                    "plan_id": "plan-1",
                    "status": "DISCARDED",
                    "execution_day": "2026-08-05",
                },
            ), patch(
                "vn_quant_local.v52_discard_safety.performance._latest_market_day",
                return_value="2026-08-05",
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "PERFORMANCE_CYCLE_SHADOW_ALREADY_EXECUTED",
                ):
                    v52_discard_safety.restore_cycle_safe(
                        plan_id="plan-1",
                        reason="Khôi phục muộn",
                    )
        finally:
            v52_discard_safety._ORIGINAL_RESTORE_CYCLE = original

    def test_pending_cycle_can_reach_discard_engine(self) -> None:
        original = v52_discard_safety._ORIGINAL_DISCARD_CYCLE
        v52_discard_safety._ORIGINAL_DISCARD_CYCLE = lambda **kwargs: {
            "status": "SUCCESS",
            **kwargs,
        }
        try:
            with patch.object(
                v52,
                "_plan_row",
                return_value={
                    "plan_id": "plan-1",
                    "status": "PENDING_MARKET_DATA",
                    "execution_day": "2026-08-06",
                },
            ), patch(
                "vn_quant_local.v52_discard_safety.performance._latest_market_day",
                return_value="2026-08-05",
            ):
                result = v52_discard_safety.discard_cycle_safe(
                    plan_id="plan-1",
                    reason="Không thực hiện",
                )
            self.assertEqual(result["status"], "SUCCESS")
        finally:
            v52_discard_safety._ORIGINAL_DISCARD_CYCLE = original


class V52StatusSafetyTests(unittest.TestCase):
    def test_legacy_shadow_plan_selector_hides_discarded_cycles(self) -> None:
        original = v52_status_safety._ORIGINAL_PERFORMANCE_STATUS
        v52_status_safety._ORIGINAL_PERFORMANCE_STATUS = lambda: {
            "status": "ACTIVE",
            "shadow_plans": [
                {"plan_id": "discarded"},
                {"plan_id": "active"},
            ],
            "discarded_cycle_catalog": [{"plan_id": "discarded"}],
        }
        try:
            with patch.object(
                v52_status_safety,
                "discarded_plan_ids",
                return_value={"discarded"},
            ):
                result = (
                    v52_status_safety.performance_status_active_cycles_only()
                )
            self.assertEqual(
                [row["plan_id"] for row in result["shadow_plans"]],
                ["active"],
            )
            self.assertEqual(result["active_shadow_plan_count"], 1)
            self.assertEqual(result["discarded_shadow_plan_count"], 1)
        finally:
            v52_status_safety._ORIGINAL_PERFORMANCE_STATUS = original


class V52CommandTests(unittest.TestCase):
    def test_discard_command_uses_existing_performance_endpoint(self) -> None:
        note = json.dumps({"plan_id": "plan-1", "reason": "Chỉ xem"})
        with patch.object(
            v52_commands.cycle_management,
            "discard_cycle",
            return_value={"status": "SUCCESS", "plan_id": "plan-1"},
        ) as mocked:
            result = v52_commands.add_actual_cashflow_v52(
                flow_type="DISCARD_CYCLE",
                amount_vnd=0.0,
                event_day="2026-08-05",
                note=note,
            )
        self.assertEqual(result["plan_id"], "plan-1")
        mocked.assert_called_once_with(plan_id="plan-1", reason="Chỉ xem")

    def test_fill_cannot_reference_discarded_cycle(self) -> None:
        with patch.object(
            v52,
            "discarded_plan_ids",
            return_value={"plan-1"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "PERFORMANCE_FILL_REFERENCES_DISCARDED_CYCLE",
            ):
                v52.add_actual_fill_v52(
                    side="BUY",
                    symbol="MSB",
                    quantity=1,
                    price_vnd=16_000,
                    event_day="2026-08-05",
                    plan_id="plan-1",
                )


if __name__ == "__main__":
    unittest.main()
