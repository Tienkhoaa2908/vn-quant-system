from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from he_thong_dinh_luong.tai_du_lieu_vn100 import (
    COT_HOP_DONG_RUT_GON,
    chuyen_doi_hop_dong_rut_gon_vn100,
)

def ghi_danh_sach(path: Path, *cac_ma: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as tep:
        writer = csv.DictWriter(tep, fieldnames=["ma"], lineterminator="\n")
        writer.writeheader()
        for ma in cac_ma:
            writer.writerow({"ma": ma})


def dong(ngay: str, *, open_=10, high=11, low=9, close=10.5, volume=1000):
    return {"time": ngay, "open": open_, "high": high, "low": low, "close": close, "volume": volume}


def ghi_raw(root: Path, prefix: str, ma: str, rows, *, lan_tai=1) -> Path:
    folder = root / f"{prefix}_{ma}_{lan_tai:03d}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ma}.json"
    payload = {
        "ma": ma, "nguon": "vnstock_kbs", "phien_ban": "4.0.4",
        "cac_cot": ["time", "open", "high", "low", "close", "volume"],
        "kieu_du_lieu": {}, "du_lieu": rows,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def ghi_bao_cao_kiem_toan(path: Path, raws: dict[str, Path]) -> None:
    states = {}
    for symbol, raw in sorted(raws.items()):
        digest = hashlib.sha256(raw.read_bytes()).hexdigest()
        states[symbol] = {"ma_sha256": digest, "ma_sha256_da_kiem_tra_lai": digest}
    path.write_text(json.dumps({"trang_thai_tung_ma": states}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def doc_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as tep:
        return list(csv.DictReader(tep))


class KiemTraHopDongRutGon(unittest.TestCase):
    def tao_nen(self, thu_muc: str, symbols: list[str]):
        root = Path(thu_muc)
        ds = root / "ma.csv"
        ghi_danh_sach(ds, *symbols)
        return root, ds, root / "tho", root / "audit.json"

    def chuyen(self, root: Path, ds: Path, raw_root: Path, audit: Path, out: str):
        return chuyen_doi_hop_dong_rut_gon_vn100(
            danh_sach_ma=ds,
            thu_muc_tho=raw_root,
            tien_to_lan_chay="run",
            bao_cao_kiem_toan=audit,
            thu_muc_san_pham=root / out,
            ma_lan_chay="rut_gon_test",
        )

    def test_121_raw_hop_le_va_manifest_truy_raw_sha(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            symbols = [f"A{i:03d}" for i in range(121)]
            root, ds, raw_root, audit = self.tao_nen(thu_muc, symbols)
            raws = {
                symbol: ghi_raw(raw_root, "run", symbol, [dong("2026-07-20")])
                for symbol in symbols
            }
            ghi_bao_cao_kiem_toan(audit, raws)
            result = self.chuyen(root, ds, raw_root, audit, "out")
            self.assertEqual(result["so_raw"], 121)
            self.assertEqual(result["so_ma_dat"], 121)
            self.assertEqual(result["so_ma_bi_loai"], 0)
            self.assertEqual(result["tong_so_dong"], 121)
            rows = doc_csv(root / "out" / "du_lieu_gia_mo_dong_khoi_luong.csv")
            self.assertEqual(tuple(rows[0]), COT_HOP_DONG_RUT_GON)
            manifest = json.loads((root / "out" / "manifest.json").read_text(encoding="utf-8"))
            by_symbol = {x["ma"]: x for x in manifest["raw"]}
            for symbol, raw in raws.items():
                self.assertEqual(
                    by_symbol[symbol]["raw_sha256"],
                    hashlib.sha256(raw.read_bytes()).hexdigest(),
                )

    def test_high_low_sai_khong_chan_va_khong_di_vao_csv(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            root, ds, raw_root, audit = self.tao_nen(thu_muc, ["FPT"])
            raw = ghi_raw(raw_root, "run", "FPT", [
                dong("2026-07-20", open_=10, high=1, low=99, close=11, volume=100)
            ])
            ghi_bao_cao_kiem_toan(audit, {"FPT": raw})
            result = self.chuyen(root, ds, raw_root, audit, "out")
            self.assertEqual(result["so_ma_dat"], 1)
            rows = doc_csv(root / "out" / "du_lieu_gia_mo_dong_khoi_luong.csv")
            self.assertNotIn("high", rows[0])
            self.assertNotIn("low", rows[0])

    def test_open_close_volume_ngay_va_hash_sai_deu_chan(self) -> None:
        cases = {
            "OPEN": [dong("2026-07-20", open_=0)],
            "CLOSE": [dong("2026-07-20", close=0)],
            "VOLUME": [dong("2026-07-20", volume=-1)],
            "DUP": [dong("2026-07-20"), dong("2026-07-20")],
        }
        for name, rows in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as thu_muc:
                root, ds, raw_root, audit = self.tao_nen(thu_muc, ["FPT"])
                raw = ghi_raw(raw_root, "run", "FPT", rows)
                ghi_bao_cao_kiem_toan(audit, {"FPT": raw})
                result = self.chuyen(root, ds, raw_root, audit, "out")
                self.assertEqual(result["so_ma_bi_loai"], 1)
        with tempfile.TemporaryDirectory() as thu_muc:
            root, ds, raw_root, audit = self.tao_nen(thu_muc, ["FPT"])
            raw = ghi_raw(raw_root, "run", "FPT", [dong("2026-07-20")])
            ghi_bao_cao_kiem_toan(audit, {"FPT": raw})
            data = json.loads(audit.read_text(encoding="utf-8"))
            data["trang_thai_tung_ma"]["FPT"]["ma_sha256"] = "0" * 64
            data["trang_thai_tung_ma"]["FPT"]["ma_sha256_da_kiem_tra_lai"] = "0" * 64
            audit.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = self.chuyen(root, ds, raw_root, audit, "out")
            self.assertEqual(result["so_ma_bi_loai"], 1)

    def test_raw_khong_doi_khong_goi_mang_thu_tu_va_hai_lan_cung_byte(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            root, ds, raw_root, audit = self.tao_nen(thu_muc, ["MBB", "FPT"])
            raws = {
                "MBB": ghi_raw(raw_root, "run", "MBB", [
                    dong("2026-07-21"), dong("2026-07-22")
                ]),
                "FPT": ghi_raw(raw_root, "run", "FPT", [
                    dong("2026-07-20"), dong("2026-07-21")
                ]),
            }
            before = {s: p.read_bytes() for s, p in raws.items()}
            ghi_bao_cao_kiem_toan(audit, raws)
            with patch(
                "he_thong_dinh_luong.tai_du_lieu_vn100.nguon_vnstock",
                side_effect=AssertionError("khong duoc goi mang"),
            ):
                self.chuyen(root, ds, raw_root, audit, "out1")
            self.chuyen(root, ds, raw_root, audit, "out2")
            for symbol, path in raws.items():
                self.assertEqual(path.read_bytes(), before[symbol])
            rows = doc_csv(root / "out1" / "du_lieu_gia_mo_dong_khoi_luong.csv")
            self.assertEqual(
                [(r["ma"], r["ngay"]) for r in rows],
                sorted((r["ma"], r["ngay"]) for r in rows),
            )
            for name in (
                "du_lieu_gia_mo_dong_khoi_luong.csv",
                "bao_cao_do_phu_hop_dong_rut_gon.json",
                "bao_cao_ma_bi_loai.json",
                "manifest.json",
                "sha256.txt",
            ):
                self.assertEqual((root / "out1" / name).read_bytes(), (root / "out2" / name).read_bytes())
            with self.assertRaises(FileExistsError):
                self.chuyen(root, ds, raw_root, audit, "out1")

    def test_bien_hinh_high_low_chi_lam_doi_provenance_hash(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            root = Path(thu_muc)
            business_rows = []
            hashes = []
            for suffix, high, low in (("a", 11, 9), ("b", 1, 99)):
                sub = root / suffix
                sub.mkdir()
                ds = sub / "ma.csv"
                ghi_danh_sach(ds, "FPT")
                raw_root = sub / "tho"
                raw = ghi_raw(raw_root, "run", "FPT", [
                    dong("2026-07-20", open_=10, high=high, low=low, close=10.5, volume=100)
                ])
                audit = sub / "audit.json"
                ghi_bao_cao_kiem_toan(audit, {"FPT": raw})
                chuyen_doi_hop_dong_rut_gon_vn100(
                    danh_sach_ma=ds, thu_muc_tho=raw_root,
                    tien_to_lan_chay="run", bao_cao_kiem_toan=audit,
                    thu_muc_san_pham=sub / "out", ma_lan_chay="same",
                )
                row = doc_csv(sub / "out" / "du_lieu_gia_mo_dong_khoi_luong.csv")[0]
                hashes.append(row.pop("raw_sha256"))
                business_rows.append(row)
            self.assertEqual(business_rows[0], business_rows[1])
            self.assertNotEqual(hashes[0], hashes[1])


if __name__ == "__main__":
    unittest.main()
