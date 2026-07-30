from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong import eod_hang_ngay_cli as eod


def _row(symbol: str, day: date, close: float, source: str) -> eod.EodRow:
    return eod.EodRow(
        symbol=symbol,
        day=day,
        open=close - 0.1,
        high=close + 0.1,
        low=close - 0.2,
        close=close,
        volume=1000,
        source=source,
        version="test",
    )


class TestEodAdvisoryCrosscheck(unittest.TestCase):
    def test_primary_du_phien_duoc_chap_nhan_khong_can_secondary(self) -> None:
        first = date(2026, 7, 29)
        second = date(2026, 7, 30)
        accepted, reasons = eod._primary_incremental_rows(
            symbol="AAA",
            primary_rows=(
                _row("AAA", first, 10.0, "dnse_openapi"),
                _row("AAA", second, 10.5, "dnse_openapi"),
            ),
            required_sessions=(first, second),
        )
        self.assertEqual(reasons, ())
        self.assertEqual(tuple(row.day for row in accepted), (first, second))

    def test_primary_thieu_phien_van_bi_chan(self) -> None:
        first = date(2026, 7, 29)
        second = date(2026, 7, 30)
        accepted, reasons = eod._primary_incremental_rows(
            symbol="AAA",
            primary_rows=(_row("AAA", second, 10.5, "dnse_openapi"),),
            required_sessions=(first, second),
        )
        self.assertEqual(accepted, ())
        self.assertIn("PRIMARY_MISSING_SESSION:2026-07-29", reasons)

    def test_advisory_lay_mau_deu_va_deterministic(self) -> None:
        symbols = tuple(f"S{index:03d}" for index in range(121))
        sample = eod._crosscheck_symbols(
            symbols,
            policy="advisory",
            sample_size=20,
        )
        self.assertEqual(len(sample), 20)
        self.assertEqual(sample[0], "S000")
        self.assertEqual(sample[-1], "S120")
        self.assertEqual(
            sample,
            eod._crosscheck_symbols(
                symbols,
                policy="advisory",
                sample_size=20,
            ),
        )

    def test_strict_luon_doi_chieu_toan_bo(self) -> None:
        symbols = ("AAA", "BBB", "CCC")
        self.assertEqual(
            eod._crosscheck_symbols(symbols, policy="strict", sample_size=1),
            symbols,
        )

    def test_benchmark_diagnostics_ghi_nhan_nguon_phu_cham(self) -> None:
        first = date(2026, 7, 29)
        second = date(2026, 7, 30)
        diagnostics = eod._benchmark_diagnostics(
            (
                _row("VNINDEX", first, 1700.0, "dnse_openapi"),
                _row("VNINDEX", second, 1744.0, "dnse_openapi"),
            ),
            (_row("VNINDEX", first, 1700.0, "vnstock_vci"),),
            price_tolerance_bps=10.0,
            secondary_error=None,
        )
        self.assertEqual(diagnostics["primary_latest_session"], "2026-07-30")
        self.assertEqual(diagnostics["secondary_latest_session"], "2026-07-29")
        self.assertEqual(diagnostics["common_session_count"], 1)


if __name__ == "__main__":
    unittest.main()
