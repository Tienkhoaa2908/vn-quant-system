from __future__ import annotations

import unittest

from he_thong_dinh_luong import portfolio_ablation_v32 as v32
from he_thong_dinh_luong import portfolio_ablation_v32_1 as v32_1


class PortfolioAblationV321Tests(unittest.TestCase):
    def _rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for day, count in (("2021-10-29", 13), ("2021-11-30", 20)):
            for index in range(count):
                rows.append(
                    {
                        "model": v32.FROZEN_MODEL,
                        "test_date": day,
                        "symbol": f"S{index:03d}",
                    }
                )
        return rows

    def test_only_full_horizon_breadths_are_evaluated(self) -> None:
        feasible, infeasible, audit = v32_1._breadth_feasibility(
            self._rows(),
            (10, 15, 20, 30),
        )
        self.assertEqual(feasible, (10,))
        self.assertEqual(infeasible, (15, 20, 30))
        by_breadth = {int(row["breadth"]): row for row in audit}
        self.assertEqual(by_breadth[10]["status"], "FULL_HORIZON_FEASIBLE")
        self.assertEqual(by_breadth[15]["status"], "INFEASIBLE_FULL_HORIZON")
        self.assertEqual(by_breadth[15]["insufficient_month_count"], 1)
        self.assertEqual(by_breadth[15]["months_dropped"], 0)
        self.assertFalse(bool(by_breadth[15]["breadth_shrunk_dynamically"]))

    def test_top10_must_remain_feasible(self) -> None:
        rows = [
            {
                "model": v32.FROZEN_MODEL,
                "test_date": "2021-10-29",
                "symbol": f"S{index:03d}",
            }
            for index in range(9)
        ]
        with self.assertRaisesRegex(ValueError, "V32_1_TOP10_NOT_FEASIBLE"):
            v32_1._breadth_feasibility(rows, (10, 15))

    def test_duplicate_month_symbol_is_rejected(self) -> None:
        row = {
            "model": v32.FROZEN_MODEL,
            "test_date": "2021-10-29",
            "symbol": "AAA",
        }
        with self.assertRaisesRegex(ValueError, "V32_1_DUPLICATE_ELIGIBLE_KEY"):
            v32_1._breadth_feasibility([row, dict(row)], (10,))


if __name__ == "__main__":
    unittest.main()
