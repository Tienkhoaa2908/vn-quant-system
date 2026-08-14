from __future__ import annotations

from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from he_thong_dinh_luong import v39_one_shot_external_resolution as resolver


class V39OneShotExternalResolutionTests(unittest.TestCase):
    def test_search_parser_keeps_only_official_domains(self):
        html = b"""
        <html><body>
          <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fvsd.vn%2Fvi%2Fad%2F123">VSDC</a>
          <a href="https://www.hnx.vn/vi-vn/chi-tiet-chung-khoan.html">HNX</a>
          <a href="https://example.com/not-official">Other</a>
        </body></html>
        """
        links = resolver.extract_official_search_links(html)
        self.assertEqual(
            links,
            [
                "https://vsd.vn/vi/ad/123",
                "https://www.hnx.vn/vi-vn/chi-tiet-chung-khoan.html",
            ],
        )

    def test_event_window_is_half_open_at_start_and_closed_at_end(self):
        windows = [{
            "symbol": "AAA",
            "holding_start": "2024-01-02",
            "holding_end": "2024-02-01",
        }]
        self.assertFalse(resolver._event_inside_any_window("AAA", "2024-01-02", windows))
        self.assertTrue(resolver._event_inside_any_window("AAA", "2024-01-03", windows))
        self.assertTrue(resolver._event_inside_any_window("AAA", "2024-02-01", windows))
        self.assertFalse(resolver._event_inside_any_window("AAA", "2024-02-02", windows))

    def test_empirical_price_basis_never_claims_vendor_contract(self):
        with TemporaryDirectory() as temporary:
            store = Path(temporary) / "market.sqlite3"
            db = sqlite3.connect(store)
            try:
                db.execute(
                    "CREATE TABLE bars(asset_type TEXT, symbol TEXT, day TEXT, open REAL, close REAL, price_basis TEXT)"
                )
                db.executemany(
                    "INSERT INTO bars VALUES (?,?,?,?,?,?)",
                    [
                        ("STOCK", "AAA", "2024-01-02", 10.0, 10.0, "CHUA_XAC_NHAN"),
                        ("STOCK", "AAA", "2024-01-03", 9.0, 9.5, "CHUA_XAC_NHAN"),
                    ],
                )
                db.commit()
            finally:
                db.close()
            report = resolver.empirical_price_basis(
                store,
                [{
                    "symbol": "AAA",
                    "event_date": "2024-01-03",
                    "event_type": "CASH_DIVIDEND",
                    "inside_required_window": True,
                    "official_page_date_match": True,
                }],
            )
            self.assertEqual(report["event_observation_count"], 1)
            self.assertFalse(report["strict_price_basis_confirmed"])
            self.assertIn("CANNOT", report["reason"])

    def test_normalize_date_accepts_vietnamese_day_first(self):
        self.assertEqual(resolver._normalize_date("03/08/2026"), "2026-08-03")
        self.assertEqual(resolver._normalize_date("2026-08-03"), "2026-08-03")
        self.assertEqual(resolver._normalize_date("not-a-date"), "")


if __name__ == "__main__":
    unittest.main()
