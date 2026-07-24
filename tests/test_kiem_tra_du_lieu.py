from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from he_thong_dinh_luong.kiem_tra_du_lieu import kiem_tra_cac_dong, kiem_tra_tep

NGAY_KIEM_TRA = date(2026, 7, 24)
THU_MUC_DU_LIEU = Path(__file__).parent / "du_lieu"


def tao_dong(**thay_doi: str) -> dict[str, str]:
    dong = {
        "ma": "AAA",
        "ngay": "2026-07-20",
        "gia_mo_cua": "10",
        "gia_cao_nhat": "11",
        "gia_thap_nhat": "9",
        "gia_dong_cua": "10.5",
        "khoi_luong": "1000",
    }
    dong.update(thay_doi)
    return dong


class kiem_tra_du_lieu_gia(unittest.TestCase):
    def quy_tac(self, *cac_dong: dict[str, str]) -> set[str]:
        bao_cao = kiem_tra_cac_dong(cac_dong, NGAY_KIEM_TRA)
        return {loi.quy_tac for loi in bao_cao.loi}

    def test_phat_hien_trung_ma_va_ngay(self) -> None:
        self.assertIn("trung_ma_va_ngay", self.quy_tac(tao_dong(), tao_dong()))

    def test_phat_hien_gia_cao_nhat_nho_hon_gia_mo_cua(self) -> None:
        self.assertIn("gia_cao_nhat_khong_hop_le", self.quy_tac(tao_dong(gia_cao_nhat="9")))

    def test_phat_hien_gia_cao_nhat_nho_hon_gia_dong_cua(self) -> None:
        self.assertIn("gia_cao_nhat_khong_hop_le", self.quy_tac(tao_dong(gia_cao_nhat="10")))

    def test_phat_hien_gia_thap_nhat_lon_hon_gia_mo_cua(self) -> None:
        self.assertIn("gia_thap_nhat_khong_hop_le", self.quy_tac(tao_dong(gia_thap_nhat="10.2")))

    def test_phat_hien_gia_thap_nhat_lon_hon_gia_dong_cua(self) -> None:
        self.assertIn(
            "gia_thap_nhat_khong_hop_le",
            self.quy_tac(tao_dong(gia_mo_cua="11", gia_dong_cua="10", gia_thap_nhat="10.2")),
        )

    def test_phat_hien_gia_bang_0(self) -> None:
        self.assertIn("gia_khong_duong", self.quy_tac(tao_dong(gia_mo_cua="0")))

    def test_phat_hien_gia_am(self) -> None:
        self.assertIn("gia_khong_duong", self.quy_tac(tao_dong(gia_dong_cua="-1")))

    def test_phat_hien_khoi_luong_am(self) -> None:
        self.assertIn("khoi_luong_am", self.quy_tac(tao_dong(khoi_luong="-1")))

    def test_cho_phep_khoi_luong_bang_0(self) -> None:
        self.assertNotIn("khoi_luong_am", self.quy_tac(tao_dong(khoi_luong="0")))

    def test_phat_hien_ngay_sau_ngay_kiem_tra(self) -> None:
        self.assertIn("ngay_sau_ngay_kiem_tra", self.quy_tac(tao_dong(ngay="2026-07-25")))

    def test_canh_bao_khoang_ngay_khong_chan_du_lieu(self) -> None:
        bao_cao = kiem_tra_cac_dong(
            [tao_dong(ngay="2026-07-01"), tao_dong(ngay="2026-07-20")],
            NGAY_KIEM_TRA,
        )
        self.assertTrue(bao_cao.hop_le)
        self.assertEqual(bao_cao.canh_bao[0].quy_tac, "khoang_ngay_bat_thuong")

    def test_tep_gia_lap_hop_le(self) -> None:
        bao_cao = kiem_tra_tep(THU_MUC_DU_LIEU / "gia_lap_hop_le.csv", NGAY_KIEM_TRA)
        self.assertTrue(bao_cao.hop_le)
        self.assertEqual(bao_cao.so_loi, 0)

    def test_tep_gia_lap_co_loi(self) -> None:
        bao_cao = kiem_tra_tep(THU_MUC_DU_LIEU / "gia_lap_co_loi.csv", NGAY_KIEM_TRA)
        self.assertFalse(bao_cao.hop_le)
        self.assertGreaterEqual(bao_cao.so_loi, 6)


if __name__ == "__main__":
    unittest.main()
