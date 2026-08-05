from __future__ import annotations

import unittest

from vn_quant_local.v51_integrity import (
    build_cycle_catalog,
    reconcile_intents,
    validate_cash_contract,
)


def plan(
    plan_id: str,
    created_at: str,
    symbol: str,
    quantity: int,
    *,
    cycle_id: str,
    execution_day: str = "2026-08-06",
):
    return {
        "plan_id": plan_id,
        "week_key": f"CYCLE:{cycle_id}",
        "created_at": created_at,
        "execution_day": execution_day,
        "status": "SELECTED",
        "planned_contribution_vnd": 0.0,
        "details": {
            "cycle_id": cycle_id,
            "buy_orders": [
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "price_vnd": 10_000.0,
                    "estimated_cost_vnd": quantity * 10_000.0,
                }
            ],
            "exit_candidates": [],
        },
    }


def fill(
    event_id: str,
    symbol: str,
    quantity: int,
    price: float,
    *,
    event_time: str,
    plan_id: str | None = None,
):
    return {
        "event_id": event_id,
        "event_time": event_time,
        "event_day": event_time[:10],
        "event_type": "ACTUAL_FILL",
        "side": "BUY",
        "symbol": symbol,
        "quantity": quantity,
        "price_vnd": price,
        "fees_vnd": 0.0,
        "taxes_vnd": 0.0,
        "plan_id": plan_id,
    }


class V51CashIntegrityTests(unittest.TestCase):
    def test_available_above_total_is_rejected(self) -> None:
        result = validate_cash_contract(
            total_cash_vnd=147_123,
            available_cash_vnd=585_945,
            withdrawable_cash_vnd=176_531,
        )
        self.assertEqual(result["status"], "REJECT_AVAILABLE_EXCEEDS_TOTAL_CASH")
        self.assertEqual(result["planner_cash_vnd"], 147_123)
        self.assertEqual(result["validated_withdrawable_cash_vnd"], 147_123)

    def test_valid_available_below_total_is_used(self) -> None:
        result = validate_cash_contract(
            total_cash_vnd=200_000,
            available_cash_vnd=150_000,
            withdrawable_cash_vnd=120_000,
        )
        self.assertEqual(result["status"], "AVAILABLE_WITHIN_TOTAL_CASH")
        self.assertEqual(result["planner_cash_vnd"], 150_000)


class V51IntentReconciliationTests(unittest.TestCase):
    def test_actual_before_shadow_is_matched_pending(self) -> None:
        plans = [
            plan(
                "plan-a",
                "2026-08-05T07:03:29+00:00",
                "MSB",
                4,
                cycle_id="cycle-a",
            )
        ]
        rows = reconcile_intents(
            plans=plans,
            shadow_trades=[],
            actual_fills=[
                fill(
                    "fill-a",
                    "MSB",
                    4,
                    16_175,
                    event_time="2026-08-05T07:10:00+00:00",
                    plan_id="plan-a",
                )
            ],
            latest_market_day="2026-08-05",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "MATCHED_COMPLETE_SHADOW_PENDING")
        self.assertEqual(rows[0]["actual_quantity"], 4)
        self.assertTrue(rows[0]["shadow_pending"])

    def test_multiple_fills_are_aggregated_to_vwap(self) -> None:
        plans = [
            plan(
                "plan-a",
                "2026-08-05T07:03:29+00:00",
                "MSB",
                4,
                cycle_id="cycle-a",
            )
        ]
        rows = reconcile_intents(
            plans=plans,
            shadow_trades=[],
            actual_fills=[
                fill("fill-1", "MSB", 2, 16_150, event_time="2026-08-05T07:10:00+00:00", plan_id="plan-a"),
                fill("fill-2", "MSB", 2, 16_200, event_time="2026-08-05T07:11:00+00:00", plan_id="plan-a"),
            ],
            latest_market_day="2026-08-05",
        )
        self.assertEqual(rows[0]["actual_quantity"], 4)
        self.assertEqual(rows[0]["actual_vwap_vnd"], 16_175)
        self.assertEqual(len(rows[0]["actual_event_ids"]), 2)

    def test_auto_match_uses_newest_open_intent(self) -> None:
        plans = [
            plan("plan-old", "2026-08-05T05:00:00+00:00", "VPI", 1, cycle_id="cycle-old"),
            plan("plan-new", "2026-08-05T07:00:00+00:00", "VPI", 1, cycle_id="cycle-new"),
        ]
        rows = reconcile_intents(
            plans=plans,
            shadow_trades=[],
            actual_fills=[
                fill("fill-vpi", "VPI", 1, 63_500, event_time="2026-08-05T07:30:00+00:00")
            ],
            latest_market_day="2026-08-05",
        )
        by_plan = {row.get("plan_id"): row for row in rows if row.get("intent_id")}
        self.assertEqual(by_plan["plan-new"]["actual_quantity"], 1)
        self.assertEqual(by_plan["plan-new"]["match_method"], "AUTO_NEWEST_OPEN_INTENT")
        self.assertEqual(by_plan["plan-old"]["actual_quantity"], 0)

    def test_no_intent_is_confirmed_outside_plan(self) -> None:
        rows = reconcile_intents(
            plans=[],
            shadow_trades=[],
            actual_fills=[
                fill("fill-baf", "BAF", 2, 31_350, event_time="2026-08-05T07:30:00+00:00")
            ],
            latest_market_day="2026-08-05",
        )
        self.assertEqual(rows[0]["status"], "OUTSIDE_PLAN_CONFIRMED")
        self.assertEqual(rows[0]["unmatched_reason"], "NO_ELIGIBLE_PLAN_INTENT")

    def test_cycle_catalog_marks_newest_and_remaining(self) -> None:
        plans = [
            plan("plan-old", "2026-08-05T05:00:00+00:00", "VPI", 1, cycle_id="cycle-old"),
            plan("plan-new", "2026-08-05T07:00:00+00:00", "MSB", 4, cycle_id="cycle-new"),
        ]
        reconciliation = reconcile_intents(
            plans=plans,
            shadow_trades=[],
            actual_fills=[],
            latest_market_day="2026-08-05",
        )
        catalog = build_cycle_catalog(plans, reconciliation)
        self.assertTrue(catalog[0]["newest"])
        self.assertEqual(catalog[0]["plan_id"], "plan-new")
        self.assertEqual(catalog[0]["remaining_quantity"], 4)
        self.assertIn("MỚI NHẤT", catalog[0]["display_label"])
        self.assertIn("CŨ", catalog[1]["display_label"])


if __name__ == "__main__":
    unittest.main()
