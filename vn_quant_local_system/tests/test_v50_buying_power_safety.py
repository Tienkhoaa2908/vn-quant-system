from __future__ import annotations

import unittest

from vn_quant_local import buying_power_v50 as v50
from vn_quant_local.buying_power_safety_v50 import (
    authoritative_shared_ppse,
    safe_planned_buying_power,
)


class V50BuyingPowerSafetyTests(unittest.TestCase):
    def test_authoritative_ppse_can_be_lower_than_available_cash(self) -> None:
        value = authoritative_shared_ppse(
            status="SUCCESS",
            items=[
                {"status": "SUCCESS", "ppse_vnd": 50000.0},
                {"status": "SUCCESS", "ppse_vnd": 70000.0},
            ],
            available_cash_vnd=100000.0,
        )
        self.assertEqual(value, 50000.0)

    def test_unavailable_ppse_falls_back_to_cash(self) -> None:
        value = authoritative_shared_ppse(
            status="UNAVAILABLE",
            items=[],
            available_cash_vnd=100000.0,
        )
        self.assertEqual(value, 100000.0)

    def test_safe_planner_does_not_raise_ppse_back_to_cash(self) -> None:
        original = v50._current_effective_buying_power
        v50._current_effective_buying_power = lambda: {
            "status": "SUCCESS",
            "conservative_buying_power_vnd": 50000.0,
        }
        try:
            self.assertEqual(safe_planned_buying_power(100000.0, 0.0), 50000.0)
            self.assertEqual(safe_planned_buying_power(100000.0, 25000.0), 75000.0)
        finally:
            v50._current_effective_buying_power = original


if __name__ == "__main__":
    unittest.main()
