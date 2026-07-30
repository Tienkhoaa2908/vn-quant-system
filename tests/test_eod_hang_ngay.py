from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from he_thong_dinh_luong import eod_hang_ngay as eod


def _publication(root: Path) -> None:
    directory = root / "publication"
    directory.mkdir()
    rows = [
        {
            "ma": "AAA", "ngay": "2026-07-24", "gia_mo_cua": "10",
            "gia_dong_cua": "11", "khoi_luong": "1000",
            "nguon": "vnstock_kbs", "phien_ban": "4.0.4",
            "co_so_gia": "CHUA_XAC_NHAN", "raw_sha256": "a" * 64,
        },
        {
            "ma": "BBB", "ngay": "2026-07-24", "gia_mo_cua": "20",
            "gia_dong_cua": "21", "khoi_luong": "2000",
            "nguon": "vnstock_kbs", "phien_ban": "4.0.4",
            "co_so_gia": "CHUA_XAC_NHAN", "raw_sha256": "b" * 64,
        },
    ]
    csv_payload = eod._csv_bytes(rows, eod.PUB_FIELDS)
    coverage = eod._json_bytes({"so_ma_dat": 2})
    excluded = eod._json_bytes({"so_ma_bi_loai": 0})
    manifest = eod._json_bytes({
        "san_pham_sha256": {
            eod.PUB_FILES[0]: eod._sha_bytes(csv_payload),
            eod.PUB_FILES[1]: eod._sha_bytes(coverage),
            eod.PUB_FILES[2]: eod._sha_bytes(excluded),
        },
        "raw": [{"ma": "AAA"}, {"ma": "BBB"}],
    })
    payloads = (csv_payload, coverage, excluded, manifest, b"placeholder\n")
    for name, payload in zip(eod.PUB_FILES, payloads, strict=True):
        (directory / name).write_bytes(payload)


def _prediction_input(root: Path) -> Path:
    path = root / "prediction_input.zip"
    fields = eod.FEATURE_PREFIX + ("x",)
    feature = eod._csv_bytes([
        {
            "ngay": "2026-06-30", "ma": symbol, "hop_le": "true",
            "ly_do": "", "eligible": "true", "ly_do_eligibility": "",
            "gtgd_tb_20_eligibility": "1", "T1": "",
            "open_t1_hop_le": "false", "x": "1",
        }
        for symbol in ("AAA", "BBB")
    ], fields)
    blobs = {
        "feature_raw.csv": feature,
        "cau_hinh.json": b'{"moc_4":{"feature_order":["x"]}}',
        "nhan.csv": b"ngay,ma\n",
        "chi_so_mo_hinh.json": b"{}",
    }
    manifest = {
        "files": {
            name: {"sha256": eod._sha_bytes(payload), "size": len(payload)}
            for name, payload in blobs.items()
        }
    }
    blobs["manifest.json"] = eod._json_bytes(manifest)
    with ZipFile(path, "w") as archive:
        for name, payload in blobs.items():
            archive.writestr(name, payload)
    return path


def _row(symbol: str, day: date, open_price: float, close: float, volume: int, source: str) -> eod.EodRow:
    return eod.EodRow(
        symbol=symbol, day=day, open=open_price, close=close,
        volume=volume, source=source, version="4.0.4",
    )


class _FakeSource:
    def __init__(self, name: str, rows: dict[str, tuple[eod.EodRow, ...]]) -> None:
        self.name = name
        self.version = "4.0.4"
        self.rows = rows

    def fetch(
        self, symbol: str, start: date, end: date, *, is_index: bool = False
    ) -> tuple[eod.EodRow, ...]:
        return self.rows.get(symbol, ())


class TestEodHangNgay(unittest.TestCase):
    def test_crosscheck_bo_qua_high_low(self) -> None:
        day = date(2026, 7, 30)
        left = eod.EodRow("AAA", day, 10, 11, 100, "kbs", "1", high=99, low=1)
        right = eod.EodRow("AAA", day, 10, 11, 100, "vci", "1", high=12, low=9)
        self.assertEqual(eod._crosscheck(left, right, 1, 0.01), ())

    def test_chay_dau_cuoi_khong_goi_mang(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _publication(root)
            _prediction_input(root)
            day = date(2026, 7, 30)
            primary = _FakeSource("vnstock_kbs", {
                "VNINDEX": (_row("VNINDEX", day, 1000, 1010, 1_000_000, "vnstock_kbs"),),
                "AAA": (_row("AAA", day, 11, 12, 1100, "vnstock_kbs"),),
                "BBB": (_row("BBB", day, 21, 22, 2100, "vnstock_kbs"),),
            })
            secondary = _FakeSource("vnstock_vci", {
                "VNINDEX": (_row("VNINDEX", day, 1000, 1010, 1_000_000, "vnstock_vci"),),
                "AAA": (_row("AAA", day, 11, 12, 1100, "vnstock_vci"),),
                "BBB": (_row("BBB", day, 21, 22, 2100, "vnstock_vci"),),
            })
            fake_features = ([
                {
                    "ngay": day.isoformat(), "ma": symbol, "hop_le": "true",
                    "ly_do": "", "eligible": "true",
                    "ly_do_eligibility": "", "gtgd_tb_20_eligibility": "1",
                    "T1": "", "open_t1_hop_le": "false", "x": "2",
                }
                for symbol in ("AAA", "BBB")
            ], {})

            def forward_runner(**kwargs: object) -> dict[str, object]:
                output = Path(kwargs["output_dir"])
                output.mkdir()
                (output / "latest_prediction.csv").write_text(
                    "signal_date,symbol,champion_model,champion_rank,selected_top_k,technical_weight_pct\n"
                    f"{day},AAA,momentum_baseline,1,true,12.5\n"
                    f"{day},BBB,momentum_baseline,2,true,12.5\n",
                    encoding="utf-8",
                )
                (output / "model_comparison.json").write_text("{}", encoding="utf-8")
                (output / "manifest.json").write_text("{}", encoding="utf-8")
                return {
                    "champion_model": "momentum_baseline",
                    "market_regime": "RISK_OFF",
                    "capital_budget_pct": 25,
                    "top_symbols": ["AAA", "BBB"],
                }

            with patch.object(eod, "_feature_rows", return_value=fake_features):
                result = eod.run(
                    data_root=root,
                    output_dir=root / "out",
                    target_date=day,
                    primary=primary,
                    secondary=secondary,
                    min_coverage=1.0,
                    now=datetime(2026, 7, 30, 19, tzinfo=eod.VN_TZ),
                    forward_runner=forward_runner,
                )
            self.assertEqual(result["status"], "SUCCESS")
            with ZipFile(root / "out" / "daily_quant_output.zip") as archive:
                names = set(archive.namelist())
            self.assertIn("latest_prediction.csv", names)
            self.assertNotIn("kbs.json", names)
            self.assertNotIn("vci.json", names)
            self.assertTrue((root / "out" / "updated_publication" / "manifest.json").is_file())

    def test_chan_chay_truoc_18_gio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _publication(root)
            _prediction_input(root)
            with self.assertRaisesRegex(ValueError, "MARKET_NOT_FINAL"):
                eod.run(
                    data_root=root,
                    output_dir=root / "out",
                    target_date=date(2026, 7, 30),
                    primary=_FakeSource("kbs", {}),
                    secondary=_FakeSource("vci", {}),
                    now=datetime(2026, 7, 30, 14, tzinfo=eod.VN_TZ),
                )

    def test_khoa_phien_ban_vnstock(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "VERSION_MISMATCH"):
            eod.VnstockSource("kbs", version_reader=lambda _: "4.0.3")


if __name__ == "__main__":
    unittest.main()
