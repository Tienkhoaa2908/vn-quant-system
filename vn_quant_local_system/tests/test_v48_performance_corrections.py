from __future__ import annotations

import json
import unittest

from vn_quant_local.performance_corrections import (
    _effective_event_rows_from,
    correction_index,
    normalize_fill_price,
    valuation_info,
)


class V48PerformanceCorrectionTests(unittest.TestCase):
    def test_thousand_vnd_price_is_normalized(self) -> None:
        self.assertEqual(normalize_fill_price(72, "THOUSAND_VND"), 72_000)

    def test_suspicious_low_vnd_price_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "SUSPICIOUS_LOW"):
            normalize_fill_price(72, "VND")

    def test_future_event_is_pending_valuation(self) -> None:
        info = valuation_info(
            {"event_type": "ACTUAL_FILL", "event_day": "2026-08-04"},
            ["2026-08-03"],
        )
        self.assertEqual(info["status"], "PENDING_VALUATION")
        self.assertIsNone(info["valuation_day"])

    def test_non_session_cashflow_moves_to_next_session(self) -> None:
        info = valuation_info(
            {"event_type": "ACTUAL_CASHFLOW", "event_day": "2026-08-02"},
            ["2026-07-31", "2026-08-03"],
        )
        self.assertEqual(info["status"], "APPLIED_NEXT_SESSION")
        self.assertEqual(info["valuation_day"], "2026-08-03")

    def test_non_session_fill_is_invalid_after_market_data_exists(self) -> None:
        info = valuation_info(
            {"event_type": "ACTUAL_FILL", "event_day": "2026-08-02"},
            ["2026-07-31", "2026-08-03"],
        )
        self.assertEqual(info["status"], "INVALID_MARKET_DAY")

    def test_replacement_keeps_audit_and_only_new_event_is_effective(self) -> None:
        original = {
            "event_id": "old",
            "event_time": "2026-08-04T01:00:00+00:00",
            "event_day": "2026-08-04",
            "event_type": "ACTUAL_FILL",
            "source": "USER_CONFIRMED_DNSE_FILL",
            "side": "BUY",
            "symbol": "FPT",
            "quantity": 1,
            "price_vnd": 72,
            "details_json": "{}",
        }
        replacement = {
            "event_id": "new",
            "event_time": "2026-08-04T02:00:00+00:00",
            "event_day": "2026-08-04",
            "event_type": "ACTUAL_FILL",
            "source": "USER_CONFIRMED_CORRECTION",
            "side": "BUY",
            "symbol": "FPT",
            "quantity": 1,
            "price_vnd": 72_000,
            "details_json": json.dumps(
                {"effective_event_time": "2026-08-04T01:00:00+00:00"}
            ),
        }
        correction = {
            "event_id": "correction",
            "event_time": "2026-08-04T02:00:01+00:00",
            "event_day": "2026-08-04",
            "event_type": "EVENT_REPLACEMENT",
            "source": "USER_CORRECTION",
            "details_json": json.dumps(
                {
                    "target_event_id": "old",
                    "replacement_event_id": "new",
                    "reason": "Sai đơn vị giá",
                }
            ),
        }
        index = correction_index([original, replacement, correction])
        self.assertEqual(index["old"]["status"], "REPLACED")
        effective = _effective_event_rows_from(
            [original, replacement, correction],
            market_days=["2026-08-04"],
        )
        self.assertEqual([row["event_id"] for row in effective], ["new"])
        self.assertEqual(effective[0]["price_vnd"], 72_000)

    def test_void_removes_event_from_effective_ledger(self) -> None:
        original = {
            "event_id": "cash",
            "event_time": "2026-08-04T01:00:00+00:00",
            "event_day": "2026-08-04",
            "event_type": "ACTUAL_CASHFLOW",
            "source": "USER_CONFIRMED",
            "amount_vnd": 250_000,
            "details_json": json.dumps({"flow_type": "DEPOSIT"}),
        }
        correction = {
            "event_id": "void",
            "event_time": "2026-08-04T02:00:00+00:00",
            "event_day": "2026-08-04",
            "event_type": "EVENT_VOID",
            "source": "USER_CORRECTION",
            "details_json": json.dumps(
                {"target_event_id": "cash", "reason": "Nhập thử"}
            ),
        }
        effective = _effective_event_rows_from(
            [original, correction],
            market_days=["2026-08-04"],
        )
        self.assertEqual(effective, [])


if __name__ == "__main__":
    unittest.main()
