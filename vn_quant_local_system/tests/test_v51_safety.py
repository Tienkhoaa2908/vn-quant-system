from __future__ import annotations

import unittest

from vn_quant_local import core
from vn_quant_local import v51_integrity as v51
from vn_quant_local import v51_safety


class V51SafetyTests(unittest.TestCase):
    def test_top_level_cash_fields_win_over_nested_values(self) -> None:
        payload = {
            "totalCash": 147_123,
            "availableCash": 140_000,
            "withdrawableCash": 130_000,
            "nested": {
                "availableCash": 585_945,
                "withdrawableCash": 176_531,
            },
        }
        result = v51_safety.extract_cash_fields(payload)
        self.assertEqual(result["field_source"], "TOP_LEVEL_DNSE_BALANCE_FIELDS")
        self.assertEqual(result["total_cash_vnd"], 147_123)
        self.assertEqual(result["available_cash_vnd"], 140_000)
        self.assertEqual(result["withdrawable_cash_vnd"], 130_000)

    def test_annotated_broker_preserves_v49_version(self) -> None:
        original = v51_safety._ORIGINAL_ANNOTATE
        v51_safety._ORIGINAL_ANNOTATE = lambda payload: {
            **dict(payload),
            "version": v51.V51_VERSION,
        }
        try:
            result = v51_safety.annotate_preserve_v49_version(
                {
                    "version": "V49_DNSE_SOURCE_INTEGRITY",
                    "details": {"version": "V49_DNSE_SOURCE_INTEGRITY"},
                }
            )
        finally:
            v51_safety._ORIGINAL_ANNOTATE = original
        self.assertIsNotNone(result)
        self.assertEqual(result["version"], "V49_DNSE_SOURCE_INTEGRITY")
        self.assertEqual(result["v51_version"], v51.V51_VERSION)

    def test_workstation_status_defaults_new_capital_to_zero(self) -> None:
        original = v51_safety._ORIGINAL_WORKSTATION_STATUS
        v51_safety._ORIGINAL_WORKSTATION_STATUS = lambda: {
            "account": {
                "account": {
                    "cash_vnd": 147_123,
                    "weekly_contribution_vnd": 1,
                },
                "holdings": [],
            }
        }
        try:
            result = v51_safety.workstation_status_zero_new_capital()
        finally:
            v51_safety._ORIGINAL_WORKSTATION_STATUS = original
        self.assertEqual(
            result["account"]["account"]["weekly_contribution_vnd"],
            0.0,
        )

    def test_runtime_safety_is_active(self) -> None:
        self.assertIs(
            core.workstation_status,
            v51_safety.workstation_status_zero_new_capital,
        )


if __name__ == "__main__":
    unittest.main()
