from __future__ import annotations

import unittest

from vn_quant_local.weekly_plan import planned_buying_power


class WeeklyContributionSemanticsTests(unittest.TestCase):
    def test_weekly_contribution_is_added_to_dnse_cash(self) -> None:
        self.assertEqual(planned_buying_power(945, 250_000), 250_945)

    def test_zero_contribution_can_use_existing_dnse_cash(self) -> None:
        self.assertEqual(planned_buying_power(125_000, 0), 125_000)

    def test_negative_contribution_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            planned_buying_power(100_000, -1)


if __name__ == "__main__":
    unittest.main()
