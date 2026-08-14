from __future__ import annotations

import json
import math
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from he_thong_dinh_luong import paper_oos_data_lineage_v77 as v77


class TestPaperOosDataLineageV77(unittest.TestCase):
    def _make_store(self, root: Path, *, sessions: int = 40, basis: str = "CHUA_XAC_NHAN", symbols: int = 12) -> Path:
        path = root / "market.sqlite3"
        db = sqlite3.connect(path)
        db.execute(
            "CREATE TABLE bars(asset_type TEXT,symbol TEXT,day TEXT,open REAL,close REAL,volume INTEGER,price_basis TEXT)"
        )
        day = date(2025, 1, 2)
        trading: list[date] = []
        while len(trading) < sessions:
            if day.weekday() < 5:
                trading.append(day)
            day += timedelta(days=1)
        for i, d in enumerate(trading):
            index_close = 1000.0 + i * 1.2 + math.sin(i / 11.0) * 2.0
            db.execute(
                "INSERT INTO bars VALUES(?,?,?,?,?,?,?)",
                ("INDEX", "VNINDEX", d.isoformat(), index_close * 0.999, index_close, 0, basis),
            )
            for s in range(symbols):
                symbol = f"S{s:02d}"
                base = 20.0 + s * 1.3
                close = base * (1.0 + 0.0008 * i + 0.004 * math.sin(i / (7.0 + s / 5.0) + s))
                open_price = close * (1.0 + 0.001 * math.sin(i / 5.0 + s))
                volume = 500_000 + 10_000 * ((i + s) % 7)
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?)",
                    ("STOCK", symbol, d.isoformat(), open_price, close, volume, basis),
                )
        db.commit()
        db.close()
        return path

    def _append_session(self, store: Path) -> date:
        db = sqlite3.connect(store)
        last = date.fromisoformat(db.execute("SELECT MAX(day) FROM bars").fetchone()[0])
        day = last + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        db.execute("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", ("INDEX", "VNINDEX", day.isoformat(), 1050.0, 1052.0, 0, "CHUA_XAC_NHAN"))
        symbols = [row[0] for row in db.execute("SELECT DISTINCT symbol FROM bars WHERE asset_type='STOCK' ORDER BY symbol")]
        for idx, symbol in enumerate(symbols):
            px = 25.0 + idx
            db.execute("INSERT INTO bars VALUES(?,?,?,?,?,?,?)", ("STOCK", symbol, day.isoformat(), px, px * 1.002, 550_000, "CHUA_XAC_NHAN"))
        db.commit()
        db.close()
        return day

    @staticmethod
    def _fake_rank_snapshot(capture_day: date) -> dict[str, object]:
        source = date(capture_day.year, capture_day.month, 1) - timedelta(days=1)
        rows_c3 = [{"symbol": f"S{i:02d}", "rank": i + 1, "score": 1.0 - i / 20.0} for i in range(12)]
        rows_ridge = [{"symbol": f"S{i:02d}", "rank": i + 1, "score": 2.0 - i / 20.0} for i in reversed(range(12))]
        rows_ridge.sort(key=lambda row: row["rank"])
        return {
            "capture_day": capture_day.isoformat(),
            "source_signal_day": source.isoformat(),
            "analysis_end": date(capture_day.year, capture_day.month, 1).isoformat(),
            "risk_on": True,
            "eligible_count": 12,
            "history_months": 20,
            "c3_weights": {"low_volatility": 1 / 3, "relative_strength_120": 1 / 3, "high_52_week": 1 / 3},
            "ridge_fit": {"selected_alpha": 10.0, "uses_only_completed_labels": True},
            "rankings": {v77.CHAMPION_MODEL: rows_c3, v77.SHADOW_MODEL: rows_ridge},
        }

    def test_price_basis_fail_closed_and_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unknown = self._make_store(root / "u", basis="CHUA_XAC_NHAN") if False else None
            # separate roots because SQLite parent must exist
            uroot = root / "u"; uroot.mkdir()
            unknown = self._make_store(uroot, basis="CHUA_XAC_NHAN")
            inv = v77._store_inventory(unknown)
            passed, basis, blockers = v77._price_basis_from_store(inv)
            self.assertFalse(passed)
            self.assertEqual(basis, "UNKNOWN")
            self.assertTrue(any("UNCONFIRMED" in item for item in blockers))

            kroot = root / "k"; kroot.mkdir()
            known = self._make_store(kroot, basis="UNADJUSTED")
            passed, basis, blockers = v77._price_basis_from_store(v77._store_inventory(known))
            self.assertTrue(passed)
            self.assertEqual(basis, "UNADJUSTED")
            self.assertEqual(blockers, [])

    def test_evidence_fixture_rejected_then_real_certificate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = root / "evidence"; data.mkdir()
            store = self._make_store(root, basis="UNADJUSTED")
            target = v77._latest_market_day(store)
            cert = {
                "contract_version": "pit_hose_membership_v1",
                "range_start": "2024-01-01",
                "range_end": "2030-01-01",
                "complete": True,
                "gaps": [],
                "conflicts": [],
                "research_eligible": True,
                "is_fixture": True,
                "source_document_ids": ["fixture"],
            }
            path = data / "hose_membership_certificate.json"
            path.write_text(json.dumps(cert), encoding="utf-8")
            scan = v77._scan_evidence([data], target_day=target, store_sha=v77._sha_file(store))
            self.assertFalse(scan["passes"]["pit_hose_membership"])
            cert["is_fixture"] = False
            path.write_text(json.dumps(cert), encoding="utf-8")
            scan = v77._scan_evidence([data], target_day=target, store_sha=v77._sha_file(store))
            self.assertTrue(scan["passes"]["pit_hose_membership"])

    def test_freeze_manifest_is_immutable_definition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); store = self._make_store(root)
            state = root / "state"
            now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)
            fixed = [f"S{i:02d}" for i in range(12)]
            first = v77._freeze_manifest(state_dir=state, store=store, git_head="abc", captured_at=now, fixed_symbols=fixed)
            second = v77._freeze_manifest(state_dir=state, store=store, git_head="abc", captured_at=now, fixed_symbols=fixed)
            self.assertEqual(first, second)
            with self.assertRaisesRegex(ValueError, "V77_FREEZE_MANIFEST_CONFLICT:variant_symbols"):
                v77._freeze_manifest(state_dir=state, store=store, git_head="abc", captured_at=now, fixed_symbols=fixed[:-1])

    def test_signal_idempotent_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            ranking = [{"symbol": f"S{i:02d}", "rank": i + 1, "score": 1.0 - i / 20} for i in range(12)]
            capture = date(2026, 8, 14); source = date(2026, 7, 31)
            p1, created = v77._record_model_signal(
                state_dir=state, model_id=v77.CHAMPION_MODEL, capture_day=capture, source_day=source,
                captured_at=datetime(2026, 8, 14, 12, tzinfo=timezone.utc), ranking=ranking,
                risk_on=True, git_head="abc", store_sha="0" * 64,
            )
            self.assertTrue(created); self.assertIsNotNone(p1)
            p2, created = v77._record_model_signal(
                state_dir=state, model_id=v77.CHAMPION_MODEL, capture_day=capture + timedelta(days=1), source_day=source,
                captured_at=datetime(2026, 8, 15, 12, tzinfo=timezone.utc), ranking=ranking,
                risk_on=True, git_head="abc", store_sha="0" * 64,
            )
            self.assertFalse(created); self.assertIsNone(p2)

    def test_end_to_end_freeze_then_next_open_fill_without_new_month_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); store = self._make_store(root, sessions=40)
            state = root / "state"; out1 = root / "out1"; out2 = root / "out2"
            latest1 = v77._latest_market_day(store)
            with patch.object(v77, "_build_rank_snapshot", side_effect=lambda **kw: self._fake_rank_snapshot(kw["capture_day"])):
                r1 = v77.run(
                    store=store, state_dir=state, output_dir=out1, search_roots=[root], git_head="head1",
                    captured_at=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
                )
            self.assertEqual(r1["status"], "SUCCESS")
            self.assertEqual(r1["freeze"]["freeze_market_day"], latest1.isoformat())
            self.assertTrue(r1["signals_appended"][v77.CHAMPION_MODEL])
            self.assertEqual(r1["paper_results"][v77.CHAMPION_MODEL]["status"], "PENDING_FIRST_EXECUTION")
            signal_count = len(v77._model_signal_files(state, v77.CHAMPION_MODEL))
            self._append_session(store)
            with patch.object(v77, "_build_rank_snapshot", side_effect=lambda **kw: self._fake_rank_snapshot(kw["capture_day"])):
                r2 = v77.run(
                    store=store, state_dir=state, output_dir=out2, search_roots=[root], git_head="head2",
                    captured_at=datetime(2026, 8, 15, 12, tzinfo=timezone.utc),
                )
            self.assertFalse(r2["signals_appended"][v77.CHAMPION_MODEL])
            self.assertEqual(len(v77._model_signal_files(state, v77.CHAMPION_MODEL)), signal_count)
            self.assertGreater(r2["paper_results"][v77.CHAMPION_MODEL]["fill_count"], 0)
            self.assertGreaterEqual(r2["paper_results"][v77.CHAMPION_MODEL]["fresh_oos_session_count"], 1)
            self.assertFalse(r2["promotion_authorized"])
            self.assertFalse(r2["canonical_data_gates_passed"])

    def test_real_rank_snapshot_uses_completed_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._make_store(root, sessions=760, basis="CHUA_XAC_NHAN", symbols=15)
            capture = v77._latest_market_day(store)
            fixed, _ = v77._gap18_symbols(store, cutoff=capture)
            wall = v77._next_month(capture)
            snap = v77._build_rank_snapshot(
                store=store,
                fixed_symbols=fixed,
                capture_day=capture,
                wall_date=wall,
                month_close_confirmed=False,
            )
            self.assertLessEqual(date.fromisoformat(snap["source_signal_day"]), capture)
            self.assertGreaterEqual(len(snap["rankings"][v77.CHAMPION_MODEL]), 10)
            self.assertGreaterEqual(len(snap["rankings"][v77.SHADOW_MODEL]), 10)
            self.assertTrue(snap["ridge_fit"]["uses_only_completed_labels"])


if __name__ == "__main__":
    unittest.main()
