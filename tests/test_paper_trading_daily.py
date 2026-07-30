from __future__ import annotations

import csv
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong import paper_trading_daily as paper


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _daily_zip(path: Path, day: date, weights: dict[str, str]) -> Path:
    rows = [
        {
            "signal_date": day.isoformat(),
            "symbol": symbol,
            "champion_model": "momentum_baseline",
            "rank": rank,
            "target_weight_pct": weight,
            "status": "PENDING_NEXT_SESSION",
        }
        for rank, (symbol, weight) in enumerate(sorted(weights.items()), 1)
    ]
    payload = _csv_bytes(rows, (
        "signal_date", "symbol", "champion_model", "rank",
        "target_weight_pct", "status",
    ))
    manifest = {
        "status": "SUCCESS",
        "files": {
            "paper_portfolio.csv": {
                "sha256": sha256(payload).hexdigest(),
                "size": len(payload),
            }
        },
    }
    with ZipFile(path, "w") as archive:
        archive.writestr("paper_portfolio.csv", payload)
        archive.writestr("manifest.json", json.dumps(manifest))
    return path


def _publication(directory: Path, days: list[date]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for day_index, day in enumerate(days):
        for symbol_index, symbol in enumerate(("AAA", "BBB")):
            price = 10 + day_index + symbol_index
            rows.append({
                "ma": symbol,
                "ngay": day.isoformat(),
                "gia_mo_cua": str(price),
                "gia_dong_cua": str(price),
                "khoi_luong": "100000",
                "nguon": "dnse_openapi",
                "phien_ban": "0.5.0",
                "co_so_gia": "CHUA_XAC_NHAN",
                "raw_sha256": "a" * 64,
            })
    (directory / paper.PUBLICATION_FILE).write_bytes(_csv_bytes(rows, (
        "ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong",
        "nguon", "phien_ban", "co_so_gia", "raw_sha256",
    )))
    return directory


class TestPaperTradingDaily(unittest.TestCase):
    def test_lan_dau_tao_lenh_cho_t1_va_khong_gui_lenh_that(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            day = date(2026, 7, 30)
            daily = _daily_zip(root / "daily.zip", day, {"AAA": "2.5", "BBB": "2.5"})
            publication = _publication(root / "publication", [day])
            state = root / "paper-state"

            result = paper.run(
                daily_output=daily,
                publication_dir=publication,
                state_dir=state,
            )

            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["paper_status"], "PENDING_FIRST_EXECUTION")
            self.assertEqual(result["fill_count"], 0)
            self.assertEqual(result["pending_order_count"], 2)
            snapshot = Path(result["snapshot_dir"])
            self.assertTrue((snapshot / "paper_state.zip").is_file())
            self.assertTrue((state / "LATEST.txt").is_file())
            orders = (snapshot / "orders.csv").read_text(encoding="utf-8")
            self.assertIn("PENDING_NEXT_SESSION", orders)
            self.assertNotIn("API", (snapshot / "paper_status.txt").read_text(encoding="utf-8"))

    def test_phien_ke_tiep_khop_open_va_lap_lai_khong_nhan_doi_tin_hieu(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = date(2026, 7, 30)
            second = date(2026, 7, 31)
            state = root / "paper-state"
            publication = _publication(root / "publication", [first])
            paper.run(
                daily_output=_daily_zip(root / "first.zip", first, {"AAA": "2.5", "BBB": "2.5"}),
                publication_dir=publication,
                state_dir=state,
            )

            publication = _publication(root / "publication2", [first, second])
            second_zip = _daily_zip(root / "second.zip", second, {"AAA": "2.5", "BBB": "2.5"})
            result = paper.run(
                daily_output=second_zip,
                publication_dir=publication,
                state_dir=state,
            )
            repeated = paper.run(
                daily_output=second_zip,
                publication_dir=publication,
                state_dir=state,
            )

            self.assertEqual(result, repeated)
            self.assertEqual(result["fill_count"], 2)
            snapshot = Path(result["snapshot_dir"])
            fills = (snapshot / "fills.csv").read_text(encoding="utf-8")
            self.assertIn(second.isoformat(), fills)
            self.assertEqual(len(list((state / "signals").glob("*.csv"))), 2)
            metrics = json.loads((snapshot / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["initial_capital_vnd"], 1_000_000_000)
            self.assertTrue(metrics["technical_validation_only"])
            self.assertFalse(metrics["research_eligible"])

    def test_cung_ngay_khac_tin_hieu_bi_chan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            day = date(2026, 7, 30)
            state = root / "paper-state"
            publication = _publication(root / "publication", [day])
            paper.run(
                daily_output=_daily_zip(root / "first.zip", day, {"AAA": "2.5"}),
                publication_dir=publication,
                state_dir=state,
            )
            with self.assertRaisesRegex(ValueError, "PAPER_SIGNAL_CONFLICT"):
                paper.run(
                    daily_output=_daily_zip(root / "conflict.zip", day, {"AAA": "5"}),
                    publication_dir=publication,
                    state_dir=state,
                )


if __name__ == "__main__":
    unittest.main()
