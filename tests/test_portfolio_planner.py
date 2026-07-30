from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.portfolio_planner import (
    Holding,
    PlanRequest,
    PortfolioStore,
    build_incremental_plan,
    latest_price_map,
    market_snapshot,
)


class TestPortfolioStore(unittest.TestCase):
    def test_luu_vi_the_tien_mat_va_lich_su_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PortfolioStore(Path(tmp) / "portfolio.sqlite3")
            store.upsert_holding(Holding("hpg", 1000, Decimal("20500")))
            store.set_current_cash(50_000_000)
            self.assertEqual(store.list_holdings()[0].symbol, "HPG")
            self.assertEqual(store.get_current_cash(), 50_000_000)
            plan_id = store.record_plan({
                "signal_date": "2026-07-30",
                "allocator": "target_gap_lot_aware_v1",
                "extra_cash_vnd": 10_000_000,
                "rows": [],
            })
            self.assertEqual(store.recent_plans()[0]["id"], plan_id)
            store.delete_holding("HPG")
            self.assertEqual(store.list_holdings(), [])


class TestIncrementalPlanner(unittest.TestCase):
    def setUp(self) -> None:
        self.predictions = [
            {
                "signal_date": "2026-07-30", "symbol": "HPG", "champion_rank": "1",
                "selected_top_k": "true", "above_ma250": "true", "momentum_12_1": "0.5",
            },
            {
                "signal_date": "2026-07-30", "symbol": "BSR", "champion_rank": "2",
                "selected_top_k": "true", "above_ma250": "true", "momentum_12_1": "0.4",
            },
        ]
        self.allocation = [
            {"symbol": "HPG", "rank": "1", "target_weight_pct": "10"},
            {"symbol": "BSR", "rank": "2", "target_weight_pct": "10"},
        ]
        self.model = {
            "signal_date": "2026-07-30", "market_regime": "RISK_OFF",
            "capital_budget_pct": 25, "champion_model": "momentum_baseline",
            "momentum_validation": {"mean_rank_ic": -0.05},
            "lightgbm_validation": {"mean_rank_ic": -0.07},
            "research_eligible": False,
        }

    def test_ke_hoach_ton_trong_lot_tien_moi_va_khong_mua_them_ma_thua(self) -> None:
        plan = build_incremental_plan(
            holdings=[
                Holding("HPG", 1000, Decimal("20000")),
                Holding("VIC", 100, Decimal("100000")),
            ],
            price_vnd={"HPG": Decimal("21800"), "BSR": Decimal("25000"), "VIC": Decimal("180000")},
            allocation_rows=self.allocation,
            predictions=self.predictions,
            model=self.model,
            request=PlanRequest(extra_cash_vnd=50_000_000, lot_size=100),
        )
        self.assertLessEqual(plan["estimated_spend_vnd"], 50_000_000)
        self.assertEqual(plan["estimated_spend_vnd"] + plan["estimated_remaining_vnd"], 50_000_000)
        by_symbol = {row["symbol"]: row for row in plan["rows"]}
        self.assertEqual(by_symbol["HPG"]["recommended_buy_quantity"], 0)
        self.assertEqual(by_symbol["HPG"]["status"], "OVER_TARGET_REVIEW")
        self.assertEqual(by_symbol["BSR"]["recommended_buy_quantity"] % 100, 0)
        self.assertIn("VIC", {row["symbol"] for row in plan["outside_target_holdings"]})
        self.assertIn("sector_cap_not_enforced_without_trusted_sector_master", plan["limitations"])

    def test_gia_publication_nghin_dong_duoc_chuyen_sang_vnd(self) -> None:
        prices, day = latest_price_map([
            {"ma": "HPG", "ngay": "2026-07-29", "gia_dong_cua": "21.65"},
            {"ma": "HPG", "ngay": "2026-07-30", "gia_dong_cua": "21.8"},
        ])
        self.assertEqual(prices["HPG"], Decimal("21800.0"))
        self.assertEqual(day, "2026-07-30")

    def test_market_snapshot_breadth(self) -> None:
        snapshot = market_snapshot(self.predictions, self.model)
        self.assertEqual(snapshot["breadth_above_ma250"], 1.0)
        self.assertEqual(snapshot["market_regime"], "RISK_OFF")
        self.assertFalse(snapshot["research_eligible"])


if __name__ == "__main__":
    unittest.main()
