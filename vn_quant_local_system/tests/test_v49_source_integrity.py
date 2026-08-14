from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
import sqlite3
import unittest
from unittest.mock import patch

from vn_quant_local.source_integrity_v49 import (
    _choose_account,
    _ensure_market_schema_v49,
    _first_present,
    _upsert_market_row,
    expected_final_session,
    normalize_position_v49,
)


class V49PositionParserTests(unittest.TestCase):
    def test_zero_is_present_not_missing(self) -> None:
        payload = {"openQuantity": 0, "accumulateQuantity": 15}
        self.assertEqual(
            _first_present(payload, ("openQuantity", "accumulateQuantity")),
            0,
        )

    def test_closed_position_is_not_resurrected_from_accumulate_quantity(self) -> None:
        row = normalize_position_v49(
            {
                "symbol": "FPT",
                "status": "OPEN",
                "openQuantity": 0,
                "accumulateQuantity": 15,
                "closedQuantity": 15,
                "tradeQuantity": 0,
            }
        )
        self.assertIsNone(row)

    def test_zero_sellable_quantity_is_preserved(self) -> None:
        row = normalize_position_v49(
            {
                "symbol": "FPT",
                "status": "OPEN",
                "openQuantity": 4,
                "accumulateQuantity": 4,
                "tradeQuantity": 0,
                "costPrice": 72.0,
                "marketPrice": 73.0,
            }
        )
        assert row is not None
        self.assertEqual(row["quantity"], 4)
        self.assertEqual(row["sellable_quantity"], 0)


class V49AccountSelectionTests(unittest.TestCase):
    def test_multiple_ambiguous_accounts_require_selection(self) -> None:
        rows = [
            {
                "readable": True,
                "selection_token": "a",
                "open_position_count": 1,
                "masked_account": "••••0001",
            },
            {
                "readable": True,
                "selection_token": "b",
                "open_position_count": 1,
                "masked_account": "••••0002",
            },
        ]
        with patch(
            "vn_quant_local.source_integrity_v49._read_account_selection",
            return_value=None,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "DNSE_ACCOUNT_SELECTION_REQUIRED",
            ):
                _choose_account(rows)


class V49MarketFreshnessTests(unittest.TestCase):
    def test_current_session_is_final_only_after_cutoff(self) -> None:
        sessions = [date(2026, 8, 3), date(2026, 8, 4)]
        before = expected_final_session(
            now_vn=datetime.fromisoformat("2026-08-04T14:00:00+07:00"),
            working_dates=sessions,
        )
        after = expected_final_session(
            now_vn=datetime.fromisoformat("2026-08-04T16:00:00+07:00"),
            working_dates=sessions,
        )
        self.assertEqual(before, date(2026, 8, 3))
        self.assertEqual(after, date(2026, 8, 4))

    def test_recent_bar_can_be_inserted_and_revised(self) -> None:
        db = sqlite3.connect(":memory:")
        db.execute(
            """
            CREATE TABLE bars(
                asset_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                day TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                source TEXT NOT NULL,
                source_version TEXT NOT NULL,
                price_basis TEXT NOT NULL,
                normalized_sha256 TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY(asset_type,symbol,day)
            )
            """
        )
        _ensure_market_schema_v49(db)
        first = SimpleNamespace(
            symbol="VNINDEX",
            day=date(2026, 8, 4),
            open=1600.0,
            high=1610.0,
            low=1590.0,
            close=1605.0,
            volume=100,
            source="dnse_openapi",
            version="0.5.0",
        )
        revised = SimpleNamespace(
            **{**first.__dict__, "close": 1607.0, "volume": 120}
        )
        self.assertEqual(
            _upsert_market_row(
                db,
                asset_type="INDEX",
                row=first,
                mutable_from=date(2026, 7, 25),
                fetched_at="2026-08-04T09:00:00Z",
            ),
            "INSERTED",
        )
        self.assertEqual(
            _upsert_market_row(
                db,
                asset_type="INDEX",
                row=first,
                mutable_from=date(2026, 7, 25),
                fetched_at="2026-08-04T09:01:00Z",
            ),
            "IDENTICAL",
        )
        self.assertEqual(
            _upsert_market_row(
                db,
                asset_type="INDEX",
                row=revised,
                mutable_from=date(2026, 7, 25),
                fetched_at="2026-08-04T09:02:00Z",
            ),
            "REVISED",
        )
        close = db.execute(
            "SELECT close FROM bars WHERE symbol='VNINDEX'"
        ).fetchone()[0]
        revision_count = db.execute(
            "SELECT COUNT(*) FROM market_source_revisions_v49"
        ).fetchone()[0]
        self.assertEqual(close, 1607.0)
        self.assertEqual(revision_count, 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
