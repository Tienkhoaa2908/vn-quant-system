import unittest

from he_thong_dinh_luong.capital_deployment_v57 import _allocate


class CapitalDeploymentV57Tests(unittest.TestCase):
    def rows(self):
        return [
            {"symbol":"AAA","rank":1,"one_share":50.0,"target_gap":60.0,"cap_gap":200.0},
            {"symbol":"BBB","rank":2,"one_share":40.0,"target_gap":45.0,"cap_gap":160.0},
            {"symbol":"CCC","rank":3,"one_share":30.0,"target_gap":35.0,"cap_gap":120.0},
        ]

    def test_target_gap_can_leave_affordable_cash_idle(self):
        orders, remaining = _allocate(rows=self.rows(), budget=250.0, max_orders=3, staged=False)
        self.assertGreaterEqual(remaining, 80.0)
        self.assertTrue(all(float(row["estimated_cost_vnd"]) <= max(float(row["target_gap_vnd"]), {"AAA":50,"BBB":40,"CCC":30}[row["symbol"]]) + 1e-9 for row in orders))

    def test_staged_redeploys_residual_to_strongest_names(self):
        orders, remaining = _allocate(rows=self.rows(), budget=250.0, max_orders=3, staged=True)
        self.assertLess(remaining, 50.0)
        by_symbol = {row["symbol"]: row for row in orders}
        self.assertGreater(int(by_symbol["AAA"]["quantity"]), 1)

    def test_max_order_count_is_respected(self):
        orders, _ = _allocate(rows=self.rows(), budget=250.0, max_orders=2, staged=True)
        self.assertLessEqual(len(orders), 2)

    def test_cap_gap_is_never_exceeded(self):
        orders, _ = _allocate(rows=self.rows(), budget=1000.0, max_orders=3, staged=True)
        for row in orders:
            self.assertLessEqual(float(row["estimated_cost_vnd"]), float(row["cap_gap_vnd"]) + 1e-9)


if __name__ == "__main__":
    unittest.main()
