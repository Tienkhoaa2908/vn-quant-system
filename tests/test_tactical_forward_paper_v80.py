from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zoneinfo import ZoneInfo

from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70
from he_thong_dinh_luong.tactical_forward_paper_v80 import (
    FROZEN_POLICY_IDS,
    build_target,
    process_record,
    register_observation,
)

VN = ZoneInfo("Asia/Ho_Chi_Minh")
SYMBOLS = list("ABCDEFGHIJ")
LEADER = "Z"


def _business_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _make_store(path: Path, end: date) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE bars(asset_type TEXT,symbol TEXT,day TEXT,open REAL,close REAL,volume INTEGER)")
        rows = []
        start = date(2025, 3, 3)
        for idx, day in enumerate(_business_days(start, end)):
            index_open = 1000.0 + idx * 0.1
            rows.append(("INDEX", "VNINDEX", day.isoformat(), index_open, index_open * 1.001, 0))
            for pos, symbol in enumerate(SYMBOLS + [LEADER]):
                raw = 100.0 + pos
                close = raw * (1.0 + 0.0005 * ((idx + pos) % 5))
                rows.append(("STOCK", symbol, day.isoformat(), raw, close, 2_000_000))
        db.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?)", rows)
        db.commit()


def _rows(exact_l15: bool = True, drag_only: bool = False):
    rows = []
    for rank, symbol in enumerate(SYMBOLS, start=1):
        rows.append({
            "symbol": symbol,
            "canonical_rank": rank,
            "preview_rank": 20 if symbol == "A" else rank,
            "prior_preview_rank": 18 if symbol == "A" else rank,
            "preview_score": 0.2 if symbol == "A" else 1.0 - rank / 100,
            "relative_5": -0.04 if symbol == "A" else 0.01,
            "drawdown_20": -0.09 if symbol == "A" else -0.01,
            "drawdown_60": -0.13 if symbol == "A" else -0.02,
            "eligible_now": True,
            "volume_ratio_5_20": 1.0,
            "dragging_current_period": symbol == "A" and drag_only,
        })
    rows.append({
        "symbol": LEADER,
        "canonical_rank": 11,
        "preview_rank": 3,
        "prior_preview_rank": 5 if exact_l15 else None,
        "preview_score": 1.5,
        "relative_5": 0.05,
        "drawdown_20": 0.0,
        "drawdown_60": 0.0,
        "eligible_now": True,
        "volume_ratio_5_20": 1.4,
    })
    return rows


def _report(exact_l15: bool = True, *, capture: str = "2026-08-14", source: str = "2026-07-31", risk_on: bool = True):
    pair = {"active": False, "leader": None, "swap_out": None, "advisory_only": True}
    if exact_l15:
        pair = {"active": True, "leader": LEADER, "swap_out": "A", "fraction": 0.50, "advisory_only": True}
    return {
        "status": "SUCCESS",
        "operational_champion": "C3_STABLE_3_PAST_IC_SHRUNK",
        "live_orders_allowed": False,
        "source_monthly_signal_day": source,
        "capture_day": capture,
        "risk_on": risk_on,
        "monthly_top10": SYMBOLS,
        "l15_swap_pair": pair,
        "tactical_semantics": {"l15_exact_trigger_required_for_swap_advice": True},
    }


class TestTacticalForwardPaperV80(unittest.TestCase):
    def test_no_l15_means_no_action_even_with_dragging_incumbent(self):
        target = build_target(_report(False), _rows(False, drag_only=True))
        self.assertFalse(target["exact_l15_active"])
        self.assertFalse(target["incumbent_health_can_trigger_trade"])
        with tempfile.TemporaryDirectory() as temp_dir:
            record = register_observation(Path(temp_dir), target, datetime(2026, 8, 15, 11, 0, tzinfo=VN))
            self.assertEqual({a["status"] for a in record["actions"]}, {"NO_ACTION_NO_EXACT_L15"})

    def test_exact_l15_reuses_v72_semantics_and_weakest_incumbent(self):
        target = build_target(_report(True), _rows(True))
        self.assertTrue(target["exact_l15_active"])
        self.assertEqual(target["leader"], LEADER)
        self.assertEqual(target["swap_out"], "A")
        self.assertEqual(tuple(target["frozen_policies"]), FROZEN_POLICY_IDS)

    def test_same_observation_is_idempotent_and_target_drift_fails(self):
        target = build_target(_report(True), _rows(True))
        wall = datetime(2026, 8, 15, 11, 0, tzinfo=VN)
        with tempfile.TemporaryDirectory() as temp_dir:
            state = Path(temp_dir)
            first = register_observation(state, target, wall)
            second = register_observation(state, target, wall + timedelta(hours=2))
            self.assertEqual(first, second)
            altered = dict(target); altered["leader"] = "Y"
            with self.assertRaisesRegex(ValueError, "V80_TARGET_DRIFT"):
                register_observation(state, altered, wall)

    def test_capture_wall_floor_prevents_retroactive_fill_and_fills_once(self):
        target = build_target(_report(True), _rows(True))
        wall = datetime(2026, 8, 15, 11, 0, tzinfo=VN)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); state_dir = root / "state"; store = root / "market.sqlite3"
            _make_store(store, date(2026, 8, 31))
            record = register_observation(state_dir, target, wall)
            self.assertEqual(record["execution_floor_date"], "2026-08-16")
            market = v70.load_market(store, SYMBOLS + [LEADER])
            once = process_record(record, market, _rows(True))
            swaps = [a for a in once["actions"] if a["policy_id"].startswith("L15_SWAP")]
            self.assertTrue(all(a["fill"]["trade_day"] == "2026-08-17" for a in swaps))
            first_fill_hash = json.dumps([a.get("fill") for a in once["actions"]], sort_keys=True)
            twice = process_record(once, market, _rows(True))
            second_fill_hash = json.dumps([a.get("fill") for a in twice["actions"]], sort_keys=True)
            self.assertEqual(first_fill_hash, second_fill_hash)

    def test_swap_fraction_is_fraction_of_incumbent_position_not_nav(self):
        target = build_target(_report(True), _rows(True))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); store = root / "market.sqlite3"
            _make_store(store, date(2026, 8, 31))
            record = register_observation(root / "state", target, datetime(2026, 8, 15, 11, 0, tzinfo=VN))
            market = v70.load_market(store, SYMBOLS + [LEADER])
            done = process_record(record, market, _rows(True))
            by_id = {a["policy_id"]: a for a in done["actions"]}
            for policy_id, requested in (("L15_SWAP25_WORST", 0.25), ("L15_SWAP50_WORST", 0.50)):
                action = by_id[policy_id]
                before = action["incumbent_shares_before"]
                after = action["incumbent_shares_after"]
                sold = before - after
                expected = int(before * requested) // v70.LOT_SIZE * v70.LOT_SIZE
                self.assertEqual(sold, expected)
                self.assertLessEqual(action["executed_incumbent_fraction_of_position"], requested + 1e-12)

    def test_cash_add_never_exceeds_real_simulated_idle_cash(self):
        target = build_target(_report(True, risk_on=True), _rows(True))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); store = root / "market.sqlite3"
            _make_store(store, date(2026, 8, 31))
            record = register_observation(root / "state", target, datetime(2026, 8, 15, 11, 0, tzinfo=VN))
            market = v70.load_market(store, SYMBOLS + [LEADER])
            done = process_record(record, market, _rows(True))
            action = next(a for a in done["actions"] if a["policy_id"] == "L15_CASH_ADD25_SLOT")
            if action["status"] == "FILLED_PAPER":
                ledger = action["fill"]["tactical_trade_ledger"]
                spent = sum(float(r["notional_vnd"]) + float(r["fee_vnd"]) for r in ledger if r["side"] == "BUY")
                self.assertLessEqual(spent, float(action["idle_cash_before_vnd"]) + 1e-6)
                self.assertLessEqual(spent, 26_000_000.0)
            else:
                self.assertEqual(action["status"], "NO_IDLE_CASH_CAPACITY_AT_EXECUTION")

    def test_risk_off_blocks_cash_add_but_not_swap_challengers(self):
        target = build_target(_report(True, risk_on=False), _rows(True))
        with tempfile.TemporaryDirectory() as temp_dir:
            record = register_observation(Path(temp_dir), target, datetime(2026, 8, 15, 11, 0, tzinfo=VN))
            by_id = {a["policy_id"]: a for a in record["actions"]}
            self.assertEqual(by_id["L15_CASH_ADD25_SLOT"]["status"], "INELIGIBLE_RISK_OFF")
            self.assertEqual(by_id["L15_SWAP25_WORST"]["status"], "PENDING_FIRST_EXECUTION")

    def test_monthly_rebalance_precedence_cancels_unfilled_action(self):
        target = build_target(_report(True, capture="2026-08-31", source="2026-07-31"), _rows(True))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); store = root / "market.sqlite3"
            _make_store(store, date(2026, 9, 10))
            record = register_observation(root / "state", target, datetime(2026, 8, 31, 20, 0, tzinfo=VN))
            market = v70.load_market(store, SYMBOLS + [LEADER])
            done = process_record(record, market, _rows(True))
            statuses = {a["status"] for a in done["actions"] if a["policy_id"].startswith("L15_SWAP")}
            self.assertEqual(statuses, {"CANCELLED_MONTHLY_REBALANCE_PRECEDENCE"})


if __name__ == "__main__":
    unittest.main()
