from __future__ import annotations

import unittest
from datetime import date

from he_thong_dinh_luong import capital_discipline_audit_v83 as v83
from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70


class V83CapitalDisciplineAuditTest(unittest.TestCase):
    def _market(self):
        cal = [date(2025,1,31), date(2025,2,3), date(2025,2,14), date(2025,2,21), date(2025,2,28), date(2025,3,3), date(2025,3,31), date(2025,4,1)]
        io = {d:1000.0 for d in cal}; ic = {d:1000.0 for d in cal}
        so = {}; sc = {}; vol = {}
        for d in cal:
            for s in ("AAA","BBB","CCC"):
                so[s,d]=100_000.0; sc[s,d]=100_000.0; vol[s,d]=1_000_000
        # AAA deteriorates through February, so a March incremental add must be blocked.
        sc["AAA",date(2025,2,28)] = 80_000.0
        so["AAA",date(2025,3,3)] = 80_000.0
        ic[date(2025,2,28)] = 1050.0
        return v70.Market(cal,io,ic,so,sc,vol)

    def test_cycle_drag_requires_absolute_and_relative_loss(self):
        market=self._market()
        out=v83._cycle_drag(market,"AAA",date(2025,1,31),date(2025,2,28))
        self.assertIsNotNone(out)
        self.assertTrue(out["underwater_and_lagging"])
        self.assertLess(out["stock_return"],0)
        self.assertLess(out["relative_return"],0)

    def test_no_add_blocks_only_incremental_buy(self):
        market=self._market()
        snaps=[
            v70.Snap(date(2025,1,31),("AAA","BBB"),True),
            v70.Snap(date(2025,2,28),("AAA","BBB"),True),
            v70.Snap(date(2025,3,31),("AAA","CCC"),True),
        ]
        result=v83._simulate(market,snaps,[],v83.POLICIES[1],v70.COSTS[0],1_000_000_000.0)
        blocked=[e for e in result["events"] if e["event"]=="BLOCK_INCREMENTAL_ADD" and e["symbol"]=="AAA"]
        self.assertEqual(len(blocked),1)
        self.assertGreater(blocked[0]["blocked_shares"],0)

    def test_policy_surface_is_fixed_and_has_no_leader_add(self):
        self.assertEqual([p.policy_id for p in v83.POLICIES],[
            "C3_BASE","NO_ADD_UNDERWATER","PERSIST2_SEVERE_TRIM50","NO_ADD_PLUS_PERSIST2_TRIM50"
        ])
        self.assertFalse(any("L15" in p.policy_id or "LEADER" in p.policy_id for p in v83.POLICIES))


if __name__ == "__main__":
    unittest.main()
