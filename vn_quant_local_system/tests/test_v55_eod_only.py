from __future__ import annotations

import unittest

from vn_quant_local import v55_eod_only as v55


class V55OfficialPositionTests(unittest.TestCase):
    def test_local_eod_is_used_even_when_broker_reference_differs(self) -> None:
        result = v55.official_position(
            {
                "symbol": "VPI",
                "quantity": 2,
                "average_cost_vnd": 65_000,
                "local_market_price_vnd": 63_000,
                "broker_market_price_vnd": 65_000,
            }
        )
        self.assertEqual(result["price_vnd"], 63_000)
        self.assertEqual(result["market_value_vnd"], 126_000)
        self.assertEqual(result["pnl_vnd"], -4_000)

    def test_missing_eod_never_falls_back_to_broker_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "V55_FINAL_EOD_PRICE_MISSING:ACB"):
            v55.official_position(
                {
                    "symbol": "ACB",
                    "quantity": 3,
                    "average_cost_vnd": 22_300,
                    "local_market_price_vnd": 0,
                    "broker_market_price_vnd": 22_450,
                }
            )

    def test_public_payload_removes_broker_reference_fields(self) -> None:
        result = v55._public(
            {
                "status": "SUCCESS",
                "snapshot_id": "broker-1",
                "market_day": "2026-08-06",
                "total_cash_vnd": 176_534,
                "broker_nav_vnd": 999_999,
                "broker_stock_value_vnd": 888_888,
                "details": {"planner_cash_source": "V51_VALIDATED_DNSE_CASH_CONTRACT"},
                "positions": [
                    {
                        "symbol": "MSB",
                        "quantity": 4,
                        "sellable_quantity": 0,
                        "average_cost_vnd": 16_150,
                        "local_market_price_vnd": 16_150,
                        "broker_market_price_vnd": 99_999,
                        "broker_market_value_vnd": 399_996,
                    }
                ],
            }
        )
        assert result is not None
        self.assertEqual(result["official_eod_stock_value_vnd"], 64_600)
        self.assertEqual(result["official_eod_nav_vnd"], 241_134)
        self.assertNotIn("broker_nav_vnd", result)
        self.assertNotIn("broker_stock_value_vnd", result)
        self.assertNotIn("broker_market_price_vnd", result["positions"][0])
        self.assertNotIn("broker_market_value_vnd", result["positions"][0])
        self.assertEqual(result["version"], v55.V55_VERSION)


if __name__ == "__main__":
    unittest.main()
