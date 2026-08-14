from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong import c3_adaptive_portfolio_v61 as v61
from he_thong_dinh_luong import weekly_micro_capital_v43 as v43


class V61AdaptivePortfolioTests(unittest.TestCase):
    def snapshot(self) -> v43.SignalSnapshot:
        ranking = tuple(f"S{i:02d}" for i in range(1, 31))
        return v43.SignalSnapshot(
            day=date(2026, 6, 30),
            ranking=ranking,
            weights={
                "low_volatility": 1 / 3,
                "relative_strength_120": 1 / 3,
                "high_52_week": 1 / 3,
            },
            volatility={symbol: 0.02 for symbol in ranking},
            risk_on=True,
        )

    def preview(self, *, ranks=None, prior=None, volume=None, return5=None, distance=None):
        ranks = ranks or {f"S{i:02d}": i for i in range(1, 31)}
        ranking = tuple(symbol for symbol, _ in sorted(ranks.items(), key=lambda item: item[1]))
        return v61.PreviewState(
            observation_day=date(2026, 7, 10),
            canonical_day=date(2026, 6, 30),
            ranking=ranking,
            rank_by_symbol=dict(ranks),
            score_by_symbol={symbol: 1.0 / rank for symbol, rank in ranks.items()},
            volume_ratio_5_20=volume or {},
            return_5=return5 or {},
            distance_ma20=distance or {},
            prior_rank_by_symbol=prior or {},
        )

    def test_latest_preview_is_strictly_before_trade_day(self):
        state1 = self.preview()
        state2 = v61.PreviewState(**{**state1.__dict__, "observation_day": date(2026, 7, 13)})
        states = {state1.observation_day: state1, state2.observation_day: state2}
        chosen = v61._latest_preview_before(date(2026, 7, 13), sorted(states), states)
        self.assertEqual(chosen.observation_day, date(2026, 7, 10))

    def test_route_confirmed_only_uses_preview_top10(self):
        snapshot = self.snapshot()
        ranks = {f"S{i:02d}": i for i in range(1, 31)}
        ranks["S01"] = 25
        ranks["S02"] = 15
        preview = self.preview(ranks=ranks)
        targets = v61._route_targets(
            policy=v61.POLICY_BY_ID["ROUTE_CONFIRMED10"],
            canonical_targets=list(snapshot.ranking[:10]),
            preview=preview,
            snapshot=snapshot,
        )
        self.assertNotIn("S01", targets)
        self.assertNotIn("S02", targets)
        self.assertIn("S03", targets)

    def test_noadd_breakdown_keeps_weakening_but_blocks_over20(self):
        snapshot = self.snapshot()
        ranks = {f"S{i:02d}": i for i in range(1, 31)}
        ranks["S01"] = 25
        ranks["S02"] = 15
        preview = self.preview(ranks=ranks)
        targets = v61._route_targets(
            policy=v61.POLICY_BY_ID["NOADD_BREAKDOWN20"],
            canonical_targets=list(snapshot.ranking[:10]),
            preview=preview,
            snapshot=snapshot,
        )
        self.assertNotIn("S01", targets)
        self.assertIn("S02", targets)

    def test_mismatched_preview_never_changes_core_routing(self):
        snapshot = self.snapshot()
        preview = self.preview()
        preview = v61.PreviewState(**{**preview.__dict__, "canonical_day": date(2026, 5, 29)})
        targets = v61._route_targets(
            policy=v61.POLICY_BY_ID["ROUTE_CONFIRMED10"],
            canonical_targets=list(snapshot.ranking[:10]),
            preview=preview,
            snapshot=snapshot,
        )
        self.assertEqual(targets, list(snapshot.ranking[:10]))

    def test_combo_tactical_requires_new_top5_persistence_volume_and_no_extension(self):
        snapshot = self.snapshot()
        ranks = {f"S{i:02d}": i + 5 for i in range(1, 31)}
        ranks["NEW"] = 2
        preview = self.preview(
            ranks=ranks,
            prior={"NEW": 4},
            volume={"NEW": 1.30},
            return5={"NEW": 0.06},
            distance={"NEW": 0.05},
        )
        candidate = v61.tactical_candidate(
            policy=v61.POLICY_BY_ID["TACT_COMBO5_F05_H10"],
            preview=preview,
            snapshot=snapshot,
            held_symbols=set(),
        )
        self.assertEqual(candidate, "NEW")

    def test_combo_tactical_rejects_overextended_new_leader(self):
        snapshot = self.snapshot()
        ranks = {f"S{i:02d}": i + 5 for i in range(1, 31)}
        ranks["NEW"] = 2
        preview = self.preview(
            ranks=ranks,
            prior={"NEW": 4},
            volume={"NEW": 1.30},
            return5={"NEW": 0.15},
            distance={"NEW": 0.12},
        )
        candidate = v61.tactical_candidate(
            policy=v61.POLICY_BY_ID["TACT_COMBO5_F05_H10"],
            preview=preview,
            snapshot=snapshot,
            held_symbols=set(),
        )
        self.assertIsNone(candidate)

    def test_tactical_never_buys_existing_canonical_top10(self):
        snapshot = self.snapshot()
        preview = self.preview(
            prior={"S01": 1},
            volume={"S01": 1.5},
            return5={"S01": 0.01},
            distance={"S01": 0.01},
        )
        candidate = v61.tactical_candidate(
            policy=v61.POLICY_BY_ID["TACT_COMBO5_F05_H10"],
            preview=preview,
            snapshot=snapshot,
            held_symbols=set(),
        )
        self.assertIsNone(candidate)

    def test_policy_matrix_contains_risk_and_opportunity_directions(self):
        ids = set(v61.POLICY_BY_ID)
        self.assertIn("TRIM25_BREAK2", ids)
        self.assertIn("ROTATE25_BREAK2", ids)
        self.assertIn("TACT_COMBO5_F05_H10", ids)
        self.assertIn("ADAPTIVE_ROTATE25_TACT5", ids)
        self.assertEqual(v61.POLICY_BY_ID["BASELINE_P1"].trim_fraction, 0.0)


if __name__ == "__main__":
    unittest.main()
