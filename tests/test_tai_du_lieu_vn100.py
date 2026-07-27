from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from he_thong_dinh_luong.tai_du_lieu_vn100 import (
    CauHinhTaiVN100,
    NguonGioiHanTocDo,
    chay_tai_hang_loat,
    doc_danh_sach_ma,
)


class NguonGiaLap:
    ten_nguon = "gia_lap"
    phien_ban = "4.0.4"

    def __init__(self) -> None:
        self.cac_lan_goi: list[str] = []

    def lay_du_lieu(self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str):
        self.cac_lan_goi.append(ma)
        return {"ma": ma}


class TrangThaiGiaLap:
    def __init__(self, ma: str, raw: Path, ma_bam: str, *, loi: str | None = None):
        self.ma = ma
        self.trang_thai = "that_bai" if loi else "thanh_cong"
        self.duong_dan_tho = str(raw) if not loi else None
        self.ma_sha256 = ma_bam if not loi else None
        self.loi = loi

    def thanh_tu_dien(self):
        return {
            "ma": self.ma,
            "trang_thai": self.trang_thai,
            "duong_dan_tho": self.duong_dan_tho,
            "ma_sha256": self.ma_sha256,
            "loi": self.loi,
        }


def ghi_danh_sach(path: Path, *cac_ma: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as tep:
        bo_ghi = csv.DictWriter(tep, fieldnames=["ma"])
        bo_ghi.writeheader()
        for ma in cac_ma:
            bo_ghi.writerow({"ma": ma})


class KiemTraTaiVN100(unittest.TestCase):
    def tao_cau_hinh(self, thu_muc: str, *cac_ma: str) -> CauHinhTaiVN100:
        root = Path(thu_muc)
        danh_sach = root / "ma.csv"
        ghi_danh_sach(danh_sach, *cac_ma)
        return CauHinhTaiVN100(
            danh_sach_ma=danh_sach,
            ngay_bat_dau="2016-01-01",
            ngay_ket_thuc="2026-07-24",
            ngay_kiem_tra=date(2026, 7, 24),
            thu_muc_du_lieu=root / "du_lieu",
            ma_lan_chay="lan_1",
            yeu_cau_moi_phut=18,
        )

    def test_doc_danh_sach_ma_chuan_hoa_va_bo_trung(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            path = Path(thu_muc) / "ma.csv"
            ghi_danh_sach(path, "fpt", " FPT ", "HPG")
            self.assertEqual(doc_danh_sach_ma(path), ("FPT", "HPG"))

    def test_gioi_han_toc_do_ap_dung_moi_lan_goi(self) -> None:
        nguon = NguonGiaLap()
        thoi_gian = [0.0]
        cac_lan_cho: list[float] = []

        def dong_ho() -> float:
            return thoi_gian[0]

        def cho(giay: float) -> None:
            cac_lan_cho.append(giay)
            thoi_gian[0] += giay

        boc = NguonGioiHanTocDo(
            nguon, yeu_cau_moi_phut=20, ham_dong_ho=dong_ho, ham_cho=cho
        )
        boc.lay_du_lieu("FPT", "2026-01-01", "2026-01-02")
        boc.lay_du_lieu("HPG", "2026-01-01", "2026-01-02")
        self.assertEqual(cac_lan_cho, [3.0])

    def test_loi_mot_ma_khong_chan_ma_khac_va_ghi_nhat_ky(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            cau_hinh = self.tao_cau_hinh(thu_muc, "FPT", "HPG")

            def chay_gia_lap(_nguon, cac_ma, *_args, **_kwargs):
                ma = tuple(cac_ma)[0]
                if ma == "FPT":
                    raise RuntimeError("loi FPT")
                raw = Path(thu_muc) / f"{ma}.json"
                raw.write_text('{"ok":true}\n', encoding="utf-8")
                ma_bam = hashlib.sha256(raw.read_bytes()).hexdigest()
                return SimpleNamespace(
                    trang_thai_tung_ma=(TrangThaiGiaLap(ma, raw, ma_bam),)
                )

            ket_qua = chay_tai_hang_loat(
                cau_hinh,
                ham_tao_nguon=lambda _so_nen: NguonGiaLap(),
                ham_chay_quy_trinh=chay_gia_lap,
                ham_cho=lambda _giay: None,
            )
            self.assertEqual(ket_qua["that_bai_trong_lan_nay"], 1)
            self.assertEqual(ket_qua["tai_thanh_cong_trong_lan_nay"], 1)
            loi = Path(ket_qua["nhat_ky_loi"]).read_text(encoding="utf-8")
            self.assertIn("FPT", loi)

    def test_tiep_tuc_chi_bo_qua_khi_hash_raw_con_khop(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            cau_hinh = self.tao_cau_hinh(thu_muc, "FPT")
            so_lan_chay = 0

            def chay_gia_lap(_nguon, cac_ma, *_args, **_kwargs):
                nonlocal so_lan_chay
                so_lan_chay += 1
                ma = tuple(cac_ma)[0]
                raw = Path(thu_muc) / f"{ma}.json"
                raw.write_text(f'{{"lan":{so_lan_chay}}}\n', encoding="utf-8")
                ma_bam = hashlib.sha256(raw.read_bytes()).hexdigest()
                return SimpleNamespace(
                    trang_thai_tung_ma=(TrangThaiGiaLap(ma, raw, ma_bam),)
                )

            lan_1 = chay_tai_hang_loat(
                cau_hinh,
                ham_tao_nguon=lambda _so_nen: NguonGiaLap(),
                ham_chay_quy_trinh=chay_gia_lap,
                ham_cho=lambda _giay: None,
            )
            self.assertEqual(lan_1["tai_thanh_cong_trong_lan_nay"], 1)
            lan_2 = chay_tai_hang_loat(
                cau_hinh,
                ham_tao_nguon=lambda _so_nen: NguonGiaLap(),
                ham_chay_quy_trinh=chay_gia_lap,
                ham_cho=lambda _giay: None,
            )
            self.assertEqual(lan_2["bo_qua_do_hash_checkpoint_hop_le"], 1)
            self.assertEqual(so_lan_chay, 1)

            raw = Path(thu_muc) / "FPT.json"
            raw.write_text('{"da_bi_sua":true}\n', encoding="utf-8")
            lan_3 = chay_tai_hang_loat(
                cau_hinh,
                ham_tao_nguon=lambda _so_nen: NguonGiaLap(),
                ham_chay_quy_trinh=chay_gia_lap,
                ham_cho=lambda _giay: None,
            )
            self.assertEqual(lan_3["tai_thanh_cong_trong_lan_nay"], 1)
            self.assertEqual(so_lan_chay, 2)


if __name__ == "__main__":
    unittest.main()
