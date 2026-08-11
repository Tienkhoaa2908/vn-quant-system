import unittest

from he_thong_dinh_luong.capital_deployment_v58 import VARIANTS, _allocate


class CapitalDeploymentV58Tests(unittest.TestCase):
    def rows(self):
        return [
            {"symbol": "AAA", "rank": 1, "one_share": 50.0, "target_gap": 60.0, "cap_gap": 200.0},
            {"symbol": "BBB", "rank": 2, "one_share": 40.0, "target_gap": 45.0, "cap_gap": 160.0},
            {"symbol": "CCC", "rank": 3, "one_share": 30.0, "target_gap": 35.0, "cap_gap": 120.0},
            {"symbol": "DDD", "rank": 4, "one_share": 35.0, "target_gap": 40.0, "cap_gap": 120.0},
            {"symbol": "EEE", "rank": 5, "one_share": 25.0, "target_gap": 30.0, "cap_gap": 100.0},
        ]

    def test_v58_contains_target_gap_4_and_5(self):
        ids = {spec.variant_id for spec in VARIANTS}
        self.assertIn("TARGET_GAP_4", ids)
        self.assertIn("TARGET_GAP_5", ids)

    def test_more_underweight_names_reduce_residual_cash(self):
        rows = self.rows()
        _, remaining_3 = _allocate(rows=rows, budget=250.0, max_orders=3, staged=False)
        _, remaining_4 = _allocate(rows=rows, budget=250.0, max_orders=4, staged=False)
        _, remaining_5 = _allocate(rows=rows, budget=250.0, max_orders=5, staged=False)
        self.assertLess(remaining_4, remaining_3)
        self.assertLess(remaining_5, remaining_4)

    def test_target_gap_5_never_spills_above_target_except_one_share_bootstrap(self):
        rows = self.rows()
        one_share = {row["symbol"]: row["one_share"] for row in rows}
        orders, _ = _allocate(rows=rows, budget=1000.0, max_orders=5, staged=False)
        for order in orders:
            ceiling = max(float(order["target_gap_vnd"]), float(one_share[order["symbol"]]))
            self.assertLessEqual(float(order["estimated_cost_vnd"]), ceiling + 1e-9)

    def test_target_gap_5_respects_five_order_limit(self):
        orders, _ = _allocate(rows=self.rows(), budget=1000.0, max_orders=5, staged=False)
        self.assertLessEqual(len(orders), 5)


if __name__ == "__main__":
    unittest.main()
