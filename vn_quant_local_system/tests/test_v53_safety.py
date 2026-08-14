from __future__ import annotations

import json
import unittest

from vn_quant_local import v53_cycle_cleanup as v53
from vn_quant_local import v53_safety


class V53SerializationSafetyTests(unittest.TestCase):
    def test_unclassified_actual_match_stays_json_serializable(self) -> None:
        status = {
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
                    "planned_quantity": 4,
                    "actual_quantity": 1,
                    "remaining_quantity": 3,
                }
            ],
            "reconciliation": [
                {
                    "intent_id": "plan-1:BUY:MSB",
                    "plan_id": "plan-1",
                    "side": "BUY",
                    "symbol": "MSB",
                    "planned_quantity": 4,
                    "actual_quantity": 1,
                    "remaining_quantity": 3,
                    "actual_event_ids": ["fill-1"],
                    "match_method": None,
                    "status": "MATCHED_PARTIAL_SHADOW_PENDING",
                    "shadow_pending": True,
                }
            ],
        }
        rows = v53._cycle_policy_rows(status)
        self.assertIs(v53._cycle_policy_rows, v53_safety.cycle_policy_rows_json_safe)
        self.assertIs(rows[0]["auto_match_only"], False)
        self.assertEqual(rows[0]["discard_lock_reason"], "UNCLASSIFIED_ACTUAL_MATCH")
        json.dumps(rows, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
