from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from he_thong_dinh_luong.du_lieu_thi_truong.chuan_hoa import chuan_hoa_bang
from he_thong_dinh_luong.du_lieu_thi_truong.luu_tru import kho_luu_tru
from he_thong_dinh_luong.du_lieu_thi_truong.mo_hinh import (
    bang_du_lieu_nguon,
    khong_co_du_lieu,
    loi_nguon_du_lieu,
)
from he_thong_dinh_luong.du_lieu_thi_truong.nguon_gia_lap import nguon_gia_lap
from he_thong_dinh_luong.du_lieu_thi_truong.quy_trinh import chay_quy_trinh


ANH_XA = {
    "ticker_date": "ngay",
    "open_price": "gia_mo_cua",
    "high_price": "gia_cao_nhat",
    "low_price": "gia_thap_nhat",
    "close_price": "gia_dong_cua",
    "total_volume": "khoi_luong",
}


def tao_bang(ma: str, cac_dong: list[dict[str, object]]) -> bang_du_lieu_nguon:
    cac_cot = tuple(cac_dong[0].keys()) if cac_dong else tuple(ANH_XA)
    return bang_du_lieu_nguon(
        ma=ma,
        cac_cot=cac_cot,
        kieu_du_lieu={cot: "object" for cot in cac_cot},
        cac_dong=tuple(cac_dong),
        anh_xa_cot=ANH_XA,
        don_vi_gia="nghin_dong",
        ghi_chu_khoi_luong="Khoi luong khop lenh",
    )


def dong(ngay: str, **thay_doi: object) -> dict[str, object]:
    ket_qua: dict[str, object] = {
        "ticker_date": ngay,
        "open_price": "10.0",
        "high_price": 11.0,
        "low_price": 9.0,
        "close_price": 10.5,
        "total_volume": 1000.0,
    }
    ket_qua.update(thay_doi)
    return ket_qua


class kiem_tra_chuan_hoa_du_lieu(unittest.TestCase):
    def test_chuan_hoa_ten_cot_kieu_du_lieu_va_thu_tu_ngay(self) -> None:
        bang = tao_bang("fpt", [dong("2026-07-02"), dong("2026-07-01")])
        ket_qua = chuan_hoa_bang(bang)
        self.assertEqual(list(ket_qua[0]), [
            "ma", "ngay", "gia_mo_cua", "gia_cao_nhat",
            "gia_thap_nhat", "gia_dong_cua", "khoi_luong",
        ])
        self.assertEqual([muc["ngay"] for muc in ket_qua], ["2026-07-01", "2026-07-02"])
        self.assertIsInstance(ket_qua[0]["gia_mo_cua"], float)
        self.assertIsInstance(ket_qua[0]["khoi_luong"], int)
        self.assertEqual(ket_qua[0]["ma"], "FPT")


class kiem_tra_luu_tru_du_lieu(unittest.TestCase):
    def test_ghi_du_lieu_tho_va_khong_ghi_de(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            kho = kho_luu_tru(thu_muc)
            duong_dan, ma_bam = kho.ghi_json("tho", "lan_1", "FPT.json", {"du_lieu": [1]})
            self.assertEqual(hashlib.sha256(duong_dan.read_bytes()).hexdigest(), ma_bam)
            with self.assertRaises(FileExistsError):
                kho.ghi_json("tho", "lan_1", "FPT.json", {"du_lieu": [2]})


class kiem_tra_quy_trinh_du_lieu(unittest.TestCase):
    def chay(self, nguon: nguon_gia_lap, *cac_ma: str):
        self.thu_muc_tam = tempfile.TemporaryDirectory()
        self.addCleanup(self.thu_muc_tam.cleanup)
        return chay_quy_trinh(
            nguon,
            cac_ma,
            "2026-07-01",
            "2026-07-24",
            self.thu_muc_tam.name,
            date(2026, 7, 24),
            ham_cho=lambda _: None,
            ma_lan_chay="lan_kiem_thu",
        )

    def test_nguon_gia_lap_hop_le_tao_du_cac_dau_ra(self) -> None:
        nguon = nguon_gia_lap({"FPT": tao_bang("FPT", [dong("2026-07-02"), dong("2026-07-01")])})
        ket_qua = self.chay(nguon, "FPT")
        trang_thai = ket_qua.trang_thai_tung_ma[0]
        self.assertEqual(trang_thai.trang_thai, "thanh_cong")
        for duong_dan in (
            trang_thai.duong_dan_tho,
            trang_thai.duong_dan_chuan_hoa,
            trang_thai.duong_dan_san_sang,
            trang_thai.duong_dan_bao_cao,
            trang_thai.duong_dan_nhat_ky,
            ket_qua.duong_dan_nhat_ky,
        ):
            self.assertTrue(Path(duong_dan).exists())
        du_lieu_tho = json.loads(Path(trang_thai.duong_dan_tho).read_text(encoding="utf-8"))
        self.assertIn("ticker_date", du_lieu_tho["du_lieu"][0])
        with Path(trang_thai.duong_dan_chuan_hoa).open(encoding="utf-8", newline="") as tep:
            cac_dong = list(csv.DictReader(tep))
        self.assertEqual([muc["ngay"] for muc in cac_dong], ["2026-07-01", "2026-07-02"])

    def test_nguon_khong_tra_du_lieu_khong_tao_tep_tho(self) -> None:
        nguon = nguon_gia_lap(
            {"FPT": tao_bang("FPT", [])},
            {"FPT": khong_co_du_lieu("khong co du lieu")},
        )
        ket_qua = self.chay(nguon, "FPT")
        trang_thai = ket_qua.trang_thai_tung_ma[0]
        self.assertEqual(trang_thai.trang_thai, "that_bai")
        self.assertIsNone(trang_thai.duong_dan_tho)
        self.assertFalse(list(Path(self.thu_muc_tam.name).glob("tho/**/*")))

    def test_tung_ma_co_trang_thai_doc_lap(self) -> None:
        nguon = nguon_gia_lap(
            {
                "FPT": tao_bang("FPT", [dong("2026-07-01")]),
                "HPG": tao_bang("HPG", [dong("2026-07-01")]),
            },
            {"HPG": khong_co_du_lieu("HPG tam khong co du lieu")},
        )
        ket_qua = self.chay(nguon, "FPT", "HPG")
        trang_thai = {muc.ma: muc for muc in ket_qua.trang_thai_tung_ma}
        self.assertEqual(trang_thai["FPT"].trang_thai, "thanh_cong")
        self.assertEqual(trang_thai["HPG"].trang_thai, "that_bai")
        self.assertTrue(Path(trang_thai["FPT"].duong_dan_san_sang).exists())
        self.assertIsNone(trang_thai["HPG"].duong_dan_tho)

    def test_du_lieu_trung_khong_tao_tep_san_sang(self) -> None:
        nguon = nguon_gia_lap({"FPT": tao_bang("FPT", [dong("2026-07-01"), dong("2026-07-01")])})
        trang_thai = self.chay(nguon, "FPT").trang_thai_tung_ma[0]
        self.assertEqual(trang_thai.trang_thai, "that_bai")
        self.assertIsNone(trang_thai.duong_dan_san_sang)
        bao_cao = json.loads(Path(trang_thai.duong_dan_bao_cao).read_text(encoding="utf-8"))
        self.assertIn("trung_ma_va_ngay", {muc["quy_tac"] for muc in bao_cao["loi"]})

    def test_ngay_tuong_lai_khong_tao_tep_san_sang(self) -> None:
        nguon = nguon_gia_lap({"FPT": tao_bang("FPT", [dong("2026-07-25")])})
        trang_thai = self.chay(nguon, "FPT").trang_thai_tung_ma[0]
        bao_cao = json.loads(Path(trang_thai.duong_dan_bao_cao).read_text(encoding="utf-8"))
        self.assertIn("ngay_sau_ngay_kiem_tra", {muc["quy_tac"] for muc in bao_cao["loi"]})
        self.assertIsNone(trang_thai.duong_dan_san_sang)

    def test_loi_gia_va_khoi_luong_ke_thua_moc_0(self) -> None:
        nguon = nguon_gia_lap({
            "FPT": tao_bang("FPT", [dong("2026-07-01", open_price=0, total_volume=-1)])
        })
        trang_thai = self.chay(nguon, "FPT").trang_thai_tung_ma[0]
        bao_cao = json.loads(Path(trang_thai.duong_dan_bao_cao).read_text(encoding="utf-8"))
        quy_tac = {muc["quy_tac"] for muc in bao_cao["loi"]}
        self.assertIn("gia_khong_duong", quy_tac)
        self.assertIn("khoi_luong_am", quy_tac)

    def test_canh_bao_khoang_ngay_khong_chan_dau_ra(self) -> None:
        nguon = nguon_gia_lap({
            "FPT": tao_bang("FPT", [dong("2026-07-01"), dong("2026-07-20")])
        })
        trang_thai = self.chay(nguon, "FPT").trang_thai_tung_ma[0]
        self.assertEqual(trang_thai.trang_thai, "thanh_cong")
        self.assertTrue(trang_thai.canh_bao)
        self.assertTrue(Path(trang_thai.duong_dan_san_sang).exists())

    def test_thu_lai_loi_tam_thoi(self) -> None:
        nguon = nguon_gia_lap(
            {"FPT": tao_bang("FPT", [dong("2026-07-01")])},
            {"FPT": [loi_nguon_du_lieu("tam thoi", tam_thoi=True)]},
        )
        trang_thai = self.chay(nguon, "FPT").trang_thai_tung_ma[0]
        self.assertEqual(trang_thai.trang_thai, "thanh_cong")
        self.assertEqual(trang_thai.so_lan_thu, 2)

    def test_loi_duoc_lam_sach_trong_nhat_ky(self) -> None:
        nguon = nguon_gia_lap(
            {"FPT": tao_bang("FPT", [])},
            {"FPT": khong_co_du_lieu("api_key=vnstock_BI_MAT")},
        )
        trang_thai = self.chay(nguon, "FPT").trang_thai_tung_ma[0]
        self.assertNotIn("BI_MAT", trang_thai.loi)


if __name__ == "__main__":
    unittest.main()
