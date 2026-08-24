from __future__ import annotations

from datetime import date, timedelta
import unittest

from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong import frozen_tactical_historical_audit_v81 as v81
from he_thong_dinh_luong import tactical_capital_policy_v79 as v79
from he_thong_dinh_luong import weekly_overlay_backtest_v72 as v72


def _calendar(start: date, n: int) -> list[date]:
    out = []
    day = start
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def _market() -> v70.Market:
    cal = _calendar(date(2025, 1, 2), 100)
    io = {d: 1000.0 + i for i, d in enumerate(cal)}
    ic = {d: 1001.0 + i for i, d in enumerate(cal)}
    so = {}; sc = {}; vol = {}
    for symbol, slope in (("AAA", 0.2), ("BBB", 2.0), ("CCC", 0.8)):
        for i, d in enumerate(cal):
            so[symbol, d] = 10000.0 + slope * i * 100.0
            sc[symbol, d] = 10020.0 + slope * i * 100.0
            vol[symbol, d] = 1_000_000
    return v70.Market(cal, io, ic, so, sc, vol)


def _l15_row(symbol: str, *, rank: int = 3, prior: int = 4, rel: float = 0.03, volume: float = 1.2):
    return {
        "symbol": symbol,
        "canonical_rank": 15,
        "preview_rank": rank,
        "prior_preview_rank": prior,
        "preview_score": 1.0,
        "relative_5": rel,
        "volume_ratio_5_20": volume,
        "eligible_now": True,
    }


class TestFrozenTacticalHistoricalAuditV81(unittest.TestCase):
    def test_policy_surface_is_exactly_frozen_v80_set(self):
        self.assertEqual(v81.FROZEN_POLICY_IDS, (
            "NO_OVERLAY", "L15_SWAP25_WORST", "L15_SWAP50_WORST", "L15_CASH_ADD25_SLOT"
        ))
        for policy_id in v81.FROZEN_POLICY_IDS:
            self.assertIn(policy_id, v79._POLICY_BY_ID)

    def test_l15_is_delegated_not_redefined(self):
        passing = _l15_row("BBB")
        failing_volume = _l15_row("BBB", volume=0.99)
        self.assertTrue(v79._l15(passing))
        self.assertTrue(v72.trigger_matches("L15_PERSIST_REL", passing))
        self.assertFalse(v79._l15(failing_volume))

    def test_signal_event_uses_exact_gate_and_actionable_first_event(self):
        market = _market()
        canonical = market.cal[20]
        next_canonical = market.cal[45]
        snaps = [v70.Snap(canonical, ("AAA", "CCC"), True), v70.Snap(next_canonical, ("AAA", "CCC"), True),
                 v70.Snap(market.cal[70], ("AAA", "CCC"), True)]
        eval1 = market.cal[25]; eval2 = market.cal[30]
        rows1 = {"AAA": {"symbol": "AAA", "canonical_rank": 1, "preview_rank": 20, "preview_score": 0.1},
                 "BBB": _l15_row("BBB")}
        rows2 = {"AAA": {"symbol": "AAA", "canonical_rank": 1, "preview_rank": 20, "preview_score": 0.1},
                 "BBB": _l15_row("BBB")}
        events = v81.build_signal_event_ledger(market, snaps,
            [v72.WeeklySignal(eval1, canonical, rows1), v72.WeeklySignal(eval2, canonical, rows2)], "TEST")
        self.assertEqual(len(events), 2)
        self.assertTrue(events[0]["selected_actionable_event"])
        self.assertFalse(events[1]["selected_actionable_event"])
        self.assertEqual(events[0]["selected_leader"], "BBB")
        self.assertFalse(events[0]["threshold_search_reopened"])

    def test_near_miss_volume_is_not_an_event(self):
        market = _market(); canonical = market.cal[20]
        snaps = [v70.Snap(canonical, ("AAA",), True), v70.Snap(market.cal[45], ("AAA",), True), v70.Snap(market.cal[70], ("AAA",), True)]
        signal = v72.WeeklySignal(market.cal[25], canonical, {"BBB": _l15_row("BBB", volume=0.999)})
        self.assertEqual(v81.build_signal_event_ledger(market, snaps, [signal], "TEST"), [])

    def test_action_pair_normalization_handles_v72_and_v79_shapes(self):
        self.assertEqual(v81.normalize_action_pair({"action": "SWAP_WORST_TO_LEADER", "symbol": "BBB", "paired_symbol": "AAA"}), ("AAA", "BBB"))
        self.assertEqual(v81.normalize_action_pair({"action": "L15_SWAP_WORST", "symbol": "AAA", "paired_symbol": "BBB"}), ("AAA", "BBB"))
        self.assertEqual(v81.normalize_action_pair({"action": "ADD_L15_FROM_IDLE_CASH", "symbol": "BBB", "paired_symbol": ""}), ("", "BBB"))

    def test_replacement_regret_sign_uses_leader_minus_incumbent(self):
        market = _market(); canonical = market.cal[20]
        snaps = {"TEST": [v70.Snap(canonical, ("AAA",), True), v70.Snap(market.cal[60], ("AAA",), True), v70.Snap(market.cal[80], ("AAA",), True)]}
        eval_day = market.cal[25]; trade_day = market.cal[26]
        weekly = {"TEST": [v72.WeeklySignal(eval_day, canonical, {"BBB": _l15_row("BBB")})]}
        actions = [{"variant_id": "TEST", "allocator": "EQUAL", "policy_id": "L15_SWAP25_WORST",
                    "cost_scenario": "BASE_DNSE", "signal_day": eval_day.isoformat(), "trade_day": trade_day.isoformat(),
                    "action": "L15_SWAP_WORST", "symbol": "AAA", "paired_symbol": "BBB"}]
        rows = v81.build_action_horizons(market, snaps, weekly, actions)
        h5 = next(row for row in rows if row["horizon"] == "H5")
        self.assertGreater(h5["leader_minus_incumbent"], 0)
        self.assertFalse(h5["replacement_regret"])

    def test_contribution_share_is_concentration_not_selection_gate(self):
        self.assertAlmostEqual(v81._contribution_share([5.0, 3.0, 2.0, -4.0], 1, True), 0.5)
        self.assertAlmostEqual(v81._contribution_share([5.0, -4.0, -1.0], 1, False), 0.8)


if __name__ == "__main__":
    unittest.main()
