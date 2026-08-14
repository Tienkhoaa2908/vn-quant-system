from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from he_thong_dinh_luong import paper_oos_data_lineage_v77 as core
from he_thong_dinh_luong import paper_oos_data_lineage_v77_driver as driver


class TestV77CausalExecutionFloor(unittest.TestCase):
    def _make_store(self, root: Path, days: list[date]) -> Path:
        path = root / "market.sqlite3"
        db = sqlite3.connect(path)
        db.execute(
            "CREATE TABLE bars(asset_type TEXT,symbol TEXT,day TEXT,open REAL,close REAL,volume INTEGER,price_basis TEXT)"
        )
        for i, day in enumerate(days):
            db.execute(
                "INSERT INTO bars VALUES(?,?,?,?,?,?,?)",
                ("INDEX", "VNINDEX", day.isoformat(), 1000.0 + i, 1001.0 + i, 0, "CHUA_XAC_NHAN"),
            )
            for s in range(10):
                symbol = f"S{s:02d}"
                px = 20.0 + s + i * 0.1
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?)",
                    ("STOCK", symbol, day.isoformat(), px, px * 1.002, 500_000, "CHUA_XAC_NHAN"),
                )
        db.commit()
        db.close()
        return path

    def _seed_signal(self, state: Path, captured_at: datetime) -> None:
        state.mkdir(parents=True, exist_ok=True)
        (state / "freeze_manifest.json").write_text(
            json.dumps({"freeze_market_day": "2026-08-13"}), encoding="utf-8"
        )
        ranking = [
            {"symbol": f"S{i:02d}", "rank": i + 1, "score": 1.0 - i / 20.0}
            for i in range(10)
        ]
        core._record_model_signal(
            state_dir=state,
            model_id=core.CHAMPION_MODEL,
            capture_day=date(2026, 8, 13),
            source_day=date(2026, 7, 31),
            captured_at=captured_at,
            ranking=ranking,
            risk_on=False,
            git_head="freeze-head",
            store_sha="0" * 64,
        )

    def test_floor_is_day_after_vietnam_capture_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            # 12:49 UTC = 19:49 Vietnam on 2026-08-14.
            self._seed_signal(state, datetime(2026, 8, 14, 12, 49, tzinfo=timezone.utc))
            floors = driver._execution_floor_by_signal_day(state, core.CHAMPION_MODEL)
            self.assertEqual(floors[date(2026, 8, 13)], date(2026, 8, 15))

    def test_replay_skips_session_that_occurred_before_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            out = root / "out"
            store = self._make_store(
                root,
                [date(2026, 8, 13), date(2026, 8, 14), date(2026, 8, 17)],
            )
            self._seed_signal(state, datetime(2026, 8, 14, 12, 49, tzinfo=timezone.utc))
            replay = driver._guarded_replay(core._replay_model)
            result = replay(state, store, core.CHAMPION_MODEL, out)
            self.assertEqual(result["earliest_execution_floor_date"], "2026-08-15")
            self.assertEqual(result["retroactive_fill_count"], 0)
            self.assertEqual(result["fresh_oos_session_count"], 1)
            self.assertEqual(result["fill_count"], 10)
            with (out / "v77_c3_stable_3_past_ic_shrunk_orders.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                orders = list(csv.DictReader(handle))
            self.assertEqual({row["execution_date"] for row in orders}, {"2026-08-17"})
            self.assertEqual(
                {row["causal_execution_floor_date"] for row in orders}, {"2026-08-15"}
            )

    def test_replay_remains_pending_when_only_retroactive_session_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            out = root / "out"
            store = self._make_store(root, [date(2026, 8, 13), date(2026, 8, 14)])
            self._seed_signal(state, datetime(2026, 8, 14, 12, 49, tzinfo=timezone.utc))
            replay = driver._guarded_replay(core._replay_model)
            result = replay(state, store, core.CHAMPION_MODEL, out)
            self.assertEqual(result["fill_count"], 0)
            self.assertEqual(result["fresh_oos_session_count"], 0)
            self.assertEqual(result["pending_order_count"], 10)
            with (out / "v77_c3_stable_3_past_ic_shrunk_orders.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                orders = list(csv.DictReader(handle))
            self.assertEqual({row["status"] for row in orders}, {"PENDING_NEXT_SESSION"})
            self.assertEqual(
                {row["reason"] for row in orders}, {"CAUSAL_EXECUTION_FLOOR_NOT_REACHED"}
            )


if __name__ == "__main__":
    unittest.main()
