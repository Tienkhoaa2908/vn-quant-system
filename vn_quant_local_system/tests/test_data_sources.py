from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vn_quant_local.data_sources import (
    clear_credentials,
    parse_manual_csv,
    save_credentials,
)


class DataSourceTests(unittest.TestCase):
    def test_credentials_are_masked_and_secret_not_returned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            with patch.dict(
                os.environ,
                {"DNSE_API_KEY": "", "DNSE_API_SECRET": ""},
                clear=False,
            ):
                result = save_credentials(
                    "abcd1234EFGH5678",
                    "secret-value",
                    secret_path=path,
                )
                self.assertTrue(result["configured"])
                self.assertNotIn("secret-value", str(result))
                self.assertIn("abcd", str(result["api_key_masked"]))
                cleared = clear_credentials(secret_path=path)
                self.assertFalse(cleared["configured"])

    def test_empty_credentials_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            with self.assertRaisesRegex(ValueError, "DNSE_CREDENTIALS_MISSING"):
                save_credentials("", "", secret_path=path)

    def test_manual_csv_accepts_vietnamese_columns(self) -> None:
        content = (
            "ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong\n"
            "FPT,2026-08-03,100,105,99,104,123456\n"
        )
        rows = parse_manual_csv(content)
        self.assertEqual(rows[0]["asset_type"], "STOCK")
        self.assertEqual(rows[0]["symbol"], "FPT")
        self.assertEqual(rows[0]["close"], 104.0)

    def test_manual_csv_converts_vnd_for_stocks_but_not_index(self) -> None:
        content = (
            "asset_type,symbol,day,open,high,low,close,volume\n"
            "STOCK,FPT,2026-08-03,100000,105000,99000,104000,1000\n"
            "INDEX,VNINDEX,2026-08-03,1500,1510,1490,1505,0\n"
        )
        rows = parse_manual_csv(content, price_unit="VND")
        by_symbol = {str(row["symbol"]): row for row in rows}
        self.assertEqual(by_symbol["VNINDEX"]["close"], 1505.0)
        self.assertEqual(by_symbol["FPT"]["close"], 104.0)

    def test_manual_csv_rejects_ohlc_inconsistency(self) -> None:
        content = (
            "symbol,day,open,high,low,close,volume\n"
            "FPT,2026-08-03,100,99,98,101,1000\n"
        )
        with self.assertRaisesRegex(ValueError, "MANUAL_CSV_OHLC_INVALID"):
            parse_manual_csv(content)


if __name__ == "__main__":
    unittest.main()
