from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong import c3_exposure_bridge_v62 as v62
from he_thong_dinh_luong import c3_adaptive_portfolio_v61 as v61
from he_thong_dinh_luong import weekly_micro_capital_v43 as v43


class V62ExposureBridgeTests(unittest.TestCase):
    def _snapshot(self) -> v43.SignalSnapshot:
        ranking = tuple(f"S{i}" for i in range(1, 11))
        return v43.SignalSnapshot(
            day=date(2026, 7, 31),
            ranking=ranking,
            weights={},
            volatility={symbol: 0.20 for symbol in ranking},
            risk_on=True,
        )

    def _preview(
        self,
        *,
        symbol: str = "NEW",
        previous_rank: int = 8,
        volume_ratio: float = 1.10,
        return_5: float = 0.05,
        distance_ma20: float = 0.04,
        canonical_day: date | None = None,
    ) -> v61.PreviewState:
        day = canonical_day or date(2026, 7, 31)
        ranking = (symbol, "X2", "X3", "X4", "X5")
        return v61.PreviewState(
            observation_day=date(2026, 8, 7),
            canonical_day=day,
            ranking=ranking,
            rank_by_symbol={name: idx for idx, name in enumerate(ranking, start=1)},
            score_by_symbol={name: 1.0 for name in ranking},
            volume_ratio_5_20={symbol: volume_ratio},
            return_5={symbol: return_5},
            distance_ma20={symbol: distance_ma20},
            prior_rank_by_symbol={symbol: previous_rank},
        )

    def test_bridge_accepts_persistent_or_velocity_new_leader(self) -> None:
        policy = v62.POLICY_BY_ID["RECYCLE_BRIDGE3"]
        snapshot = self._snapshot()
        persistent = v62.bridge_candidates(
            policy=policy,
            preview=self._preview(previous_rank=8),
            snapshot=snapshot,
            held_symbols=set(),
        )
        velocity = v62.bridge_candidates(
            policy=policy,
            preview=self._preview(previous_rank=12),
            snapshot=snapshot,
            held_symbols=set(),
        )
        self.assertEqual(persistent, ["NEW"])
        self.assertEqual(velocity, ["NEW"])

    def test_bridge_rejects_overextended_or_mismatched_preview(self) -> None:
        policy = v62.POLICY_BY_ID["RECYCLE_BRIDGE3"]
        snapshot = self._snapshot()
        overextended = v62.bridge_candidates(
            policy=policy,
            preview=self._preview(return_5=0.11),
            snapshot=snapshot,
            held_symbols=set(),
        )
        mismatched = v62.bridge_candidates(
            policy=policy,
            preview=self._preview(canonical_day=date(2026, 6, 30)),
            snapshot=snapshot,
            held_symbols=set(),
        )
        self.assertEqual(overextended, [])
        self.assertEqual(mismatched, [])

    def test_bridge_never_targets_existing_canonical_or_held_symbol(self) -> None:
        policy = v62.POLICY_BY_ID["RECYCLE_BRIDGE3"]
        snapshot = self._snapshot()
        canonical_preview = self._preview(symbol="S1")
        held_preview = self._preview(symbol="NEW")
        self.assertEqual(
            v62.bridge_candidates(
                policy=policy,
                preview=canonical_preview,
                snapshot=snapshot,
                held_symbols=set(),
            ),
            [],
        )
        self.assertEqual(
            v62.bridge_candidates(
                policy=policy,
                preview=held_preview,
                snapshot=snapshot,
                held_symbols={"NEW"},
            ),
            [],
        )

    def test_guarded_one_share_floor_solves_v61_affordability_starvation(self) -> None:
        policy = v62.POLICY_BY_ID["RECYCLE_BRIDGE3"]
        budget, quantity, used_floor = v62.bridge_budget_quantity(
            raw_price=40_000.0,
            cash=100_000.0,
            account_value=1_000_000.0,
            current_symbol_quantity=0,
            tactical_market_value=0.0,
            policy=policy,
            slippage_bps=20.0,
        )
        self.assertGreater(budget, 0.0)
        self.assertEqual(quantity, 1)
        self.assertTrue(used_floor)

    def test_one_share_floor_respects_five_percent_nav_and_aggregate_cap(self) -> None:
        policy = v62.POLICY_BY_ID["RECYCLE_BRIDGE3"]
        _, too_large, floor_large = v62.bridge_budget_quantity(
            raw_price=40_000.0,
            cash=100_000.0,
            account_value=700_000.0,
            current_symbol_quantity=0,
            tactical_market_value=0.0,
            policy=policy,
            slippage_bps=20.0,
        )
        _, no_room, floor_room = v62.bridge_budget_quantity(
            raw_price=40_000.0,
            cash=100_000.0,
            account_value=1_000_000.0,
            current_symbol_quantity=0,
            tactical_market_value=95_000.0,
            policy=policy,
            slippage_bps=20.0,
        )
        self.assertEqual(too_large, 0)
        self.assertFalse(floor_large)
        self.assertEqual(no_room, 0)
        self.assertFalse(floor_room)

    def test_target_weights_scale_to_regime_stock_fraction(self) -> None:
        snapshot = self._snapshot()
        weights = v62._target_weights(
            snapshot=snapshot,
            target_symbols=snapshot.ranking,
            stock_fraction=0.50,
        )
        self.assertAlmostEqual(sum(weights.values()), 0.50, places=9)
        self.assertTrue(all(value <= 0.075000001 for value in weights.values()))

    def test_policy_matrix_contains_safety_opportunity_and_combination(self) -> None:
        ids = {policy.policy_id for policy in v62.POLICIES}
        self.assertIn("RECYCLE_AGE10_TRIM25_BREAK2", ids)
        self.assertIn("RECYCLE_BRIDGE3", ids)
        self.assertIn("RECYCLE_AGE10_TRIM25_BRIDGE3", ids)
        self.assertEqual(v62.MATURE_MIN_WEEK, 13)
        self.assertEqual(v62.MATURE_MIN_POSITIONS, 5)

    def test_risk_off_stock_fraction_is_half_without_live_authorization(self) -> None:
        policy = v62.POLICY_BY_ID["RECYCLE_BASELINE"]
        self.assertEqual(v62._stock_fraction(policy, True), 1.0)
        self.assertEqual(v62._stock_fraction(policy, False), 0.5)


if __name__ == "__main__":
    unittest.main()
