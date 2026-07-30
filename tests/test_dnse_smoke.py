from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from he_thong_dinh_luong import dnse_smoke
from he_thong_dinh_luong import eod_hang_ngay_cli as eod


class _Source:
    name = "dnse_openapi"
    version = "0.5.0"

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        is_index: bool = False,
    ) -> tuple[eod.EodRow, ...]:
        return (
            eod.EodRow(
                symbol=symbol,
                day=end,
                open=10.0,
                high=11.0,
                low=9.0,
                close=10.5,
                volume=1000,
                source=self.name,
                version=self.version,
            ),
        )

    def close(self) -> None:
        return None


class TestDnseSmoke(unittest.TestCase):
    def test_smoke_khong_ghi_credential_va_zip_khong_co_raw_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            with patch.object(dnse_smoke.DnseRestSource, "from_env", return_value=_Source()):
                result = dnse_smoke.run(
                    output_dir=output,
                    start=date(2026, 7, 29),
                    end=date(2026, 7, 30),
                )
            self.assertEqual(result["status"], "SUCCESS")
            evidence = json.loads(
                (output / "dnse_smoke_evidence.json").read_text(encoding="utf-8")
            )
            self.assertFalse(evidence["credentials_recorded"])
            self.assertFalse(evidence["pipeline_called"])
            with ZipFile(output / "dnse_smoke_evidence.zip") as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"dnse_smoke_evidence.json", "sha256.txt"},
                )
                payload = archive.read("dnse_smoke_evidence.json")
            self.assertNotIn(b"API_SECRET", payload)
            self.assertNotIn(b"API_KEY", payload)

    def test_runbook_khong_con_lenh_dong_git_bash(self) -> None:
        text = Path("tai_lieu/runbook_eod_hang_ngay.md").read_text(encoding="utf-8")
        self.assertNotIn("exit $STATUS", text)
        self.assertIn('read -r -p "Nhan Enter de dong cua so..."', text)
        self.assertIn("--with dnse==0.5.0", text)
        self.assertIn("--primary-source dnse", text)
        self.assertIn(".env.dnse", text)


if __name__ == "__main__":
    unittest.main()
