from __future__ import annotations

import unittest
from unittest.mock import patch

from vn_quant_local import v52_status_safety


class V52CycleLockPresentationTests(unittest.TestCase):
    def test_pending_zero_fill_cycle_is_discardable(self) -> None:
        original = v52_status_safety._ORIGINAL_PERFORMANCE_STATUS
        v52_status_safety._ORIGINAL_PERFORMANCE_STATUS = lambda: {
            "status": "ACTIVE",
            "shadow_plans": [
                {
                    "plan_id": "plan-pending",
                    "status": "PENDING_MARKET_DATA",
                    "execution_day": "2026-08-06",
                }
            ],
            "cycle_catalog": [
                {
                    "plan_id": "plan-pending",
                    "actual_quantity": 0,
                }
            ],
            "discarded_cycle_catalog": [],
        }
        try:
            with patch.object(
                v52_status_safety,
                "discarded_plan_ids",
                return_value=set(),
            ), patch(
                "vn_quant_local.v52_status_safety.performance._latest_market_day",
                return_value="2026-08-05",
            ):
                result = (
                    v52_status_safety.performance_status_active_cycles_only()
                )
        finally:
            v52_status_safety._ORIGINAL_PERFORMANCE_STATUS = original
        self.assertTrue(result["cycle_catalog"][0]["discardable"])
        self.assertIsNone(
            result["cycle_catalog"][0]["discard_lock_reason"]
        )

    def test_fill_or_observed_shadow_locks_discard(self) -> None:
        original = v52_status_safety._ORIGINAL_PERFORMANCE_STATUS
        v52_status_safety._ORIGINAL_PERFORMANCE_STATUS = lambda: {
            "status": "ACTIVE",
            "shadow_plans": [
                {
                    "plan_id": "with-fill",
                    "status": "PENDING_MARKET_DATA",
                    "execution_day": "2026-08-06",
                },
                {
                    "plan_id": "observed",
                    "status": "EXECUTED",
                    "execution_day": "2026-08-05",
                },
            ],
            "cycle_catalog": [
                {"plan_id": "with-fill", "actual_quantity": 1},
                {"plan_id": "observed", "actual_quantity": 0},
            ],
            "discarded_cycle_catalog": [],
        }
        try:
            with patch.object(
                v52_status_safety,
                "discarded_plan_ids",
                return_value=set(),
            ), patch(
                "vn_quant_local.v52_status_safety.performance._latest_market_day",
                return_value="2026-08-05",
            ):
                result = (
                    v52_status_safety.performance_status_active_cycles_only()
                )
        finally:
            v52_status_safety._ORIGINAL_PERFORMANCE_STATUS = original
        rows = {row["plan_id"]: row for row in result["cycle_catalog"]}
        self.assertFalse(rows["with-fill"]["discardable"])
        self.assertEqual(
            rows["with-fill"]["discard_lock_reason"],
            "ACTUAL_FILL_EXISTS",
        )
        self.assertFalse(rows["observed"]["discardable"])
        self.assertEqual(
            rows["observed"]["discard_lock_reason"],
            "SHADOW_EXECUTION_ALREADY_OBSERVED",
        )


if __name__ == "__main__":
    unittest.main()
