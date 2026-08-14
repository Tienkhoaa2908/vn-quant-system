from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import hose_lineage_price_probe_v67 as probe


def weekdays(start: date, count: int) -> list[date]:
    result: list[date] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


class TestHoseLineagePriceProbeV67(unittest.TestCase):
    def test_hsx_date_is_vietnamese_day_month_year(self) -> None:
        self.assertEqual(probe._parse_hsx_date("06/10/2016"), date(2016, 10, 6))

    def test_transfer_gap_is_provisional(self) -> None:
        calendar = weekdays(date(2016, 10, 3), 50)
        positions = {day: i for i, day in enumerate(calendar)}
        rows = []
        for day in calendar:
            if day <= date(2016, 11, 17) or day >= date(2016, 11, 25):
                rows.append((day, 10.0, 10.0))
        result = probe.infer_transfer_candidate(
            listing_effective_day=date(2016, 10, 6),
            rows=rows,
            calendar_positions=positions,
        )
        self.assertEqual(result["candidate_first_hose_trade_day"], "2016-11-25")
        self.assertEqual(result["classification"], "TRANSFER_GAP_HEURISTIC")
        self.assertTrue(result["needs_official_first_trade_confirmation"])

    def test_new_listing_local_start_is_accepted_as_candidate(self) -> None:
        calendar = weekdays(date(2020, 1, 1), 20)
        rows = [(day, 10.0, 10.0) for day in calendar[5:]]
        result = probe.infer_transfer_candidate(
            listing_effective_day=calendar[3],
            rows=rows,
            calendar_positions={day: i for i, day in enumerate(calendar)},
        )
        self.assertEqual(result["candidate_first_hose_trade_day"], calendar[5].isoformat())
        self.assertFalse(result["needs_official_first_trade_confirmation"])

    def test_price_gap_audit_flags_large_consecutive_session_reset(self) -> None:
        calendar = weekdays(date(2026, 1, 2), 5)
        by_symbol = {
            "AAA": [
                (calendar[0], 100.0, 100.0),
                (calendar[1], 50.0, 52.0),
                (calendar[2], 52.0, 53.0),
            ]
        }
        report = probe.audit_price_gaps(by_symbol=by_symbol, calendar=calendar)
        self.assertEqual(report["event_count_by_threshold"]["0.18"], 1)
        self.assertEqual(report["event_count_by_threshold"]["0.4"], 1)
        self.assertEqual(report["events"][0]["symbol"], "AAA")

    def test_build_report_never_authorizes_c3_from_probe(self) -> None:
        days = weekdays(date(2026, 1, 2), 10)
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "market.sqlite3"
            db = sqlite3.connect(store)
            try:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL)"
                )
                for day in days:
                    db.execute(
                        "INSERT INTO bars VALUES(?,?,?,?,?)",
                        ("INDEX", "VNINDEX", day.isoformat(), 1000.0, 1000.0),
                    )
                    db.execute(
                        "INSERT INTO bars VALUES(?,?,?,?,?)",
                        ("STOCK", "AAA", day.isoformat(), 10.0, 10.0),
                    )
                db.commit()
            finally:
                db.close()
            report = probe.build_report(store, allow_network=False)
            self.assertFalse(report["research_gate"]["c3_training_authorized"])
            self.assertFalse(report["research_gate"]["price_basis_gate_closed"])
            self.assertEqual(report["lineage_summary"]["unmatched_current_hsx_symbols"], ["AAA"])

    def test_official_rows_do_not_make_transfer_history_pit_accepted(self) -> None:
        days = weekdays(date(2016, 10, 3), 50)
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "market.sqlite3"
            db = sqlite3.connect(store)
            try:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL)"
                )
                for day in days:
                    db.execute(
                        "INSERT INTO bars VALUES(?,?,?,?,?)",
                        ("INDEX", "VNINDEX", day.isoformat(), 1000.0, 1000.0),
                    )
                    if day <= date(2016, 11, 17) or day >= date(2016, 11, 25):
                        db.execute(
                            "INSERT INTO bars VALUES(?,?,?,?,?)",
                            ("STOCK", "AAA", day.isoformat(), 10.0, 10.0),
                        )
                db.commit()
            finally:
                db.close()

            official = {
                "source": "HOSE_OFFICIAL_LEGACY_SYMBOL_LIST",
                "url": probe.HSX_SYMBOL_LIST_URL,
                "http_status": 200,
                "content_type": "application/json",
                "response_sha256": "abc",
                "language_change_error": None,
                "raw_row_count": 1,
                "parsed_row_count": 1,
                "rows": [
                    {
                        "id": 624,
                        "symbol": "AAA",
                        "isin": "VN000000AAA4",
                        "figi": "",
                        "name": "AAA",
                        "listing_effective_date": "2016-10-06",
                        "listing_effective_date_raw": "06/10/2016",
                    }
                ],
            }
            with patch.object(probe, "fetch_hsx_current_listing", return_value=official):
                report = probe.build_report(store, allow_network=True)
            row = report["symbol_lineage_rows"][0]
            self.assertEqual(row["candidate_first_hose_trade_day"], "2016-11-25")
            self.assertTrue(row["needs_official_first_trade_confirmation"])
            self.assertFalse(row["pit_accepted_for_research"])
            self.assertFalse(report["research_gate"]["hose_pit_gate_closed"])


if __name__ == "__main__":
    unittest.main()
