from __future__ import annotations

import unittest
from datetime import date, timedelta

from he_thong_dinh_luong.duong_co_so.chi_bao import cau_hinh_duong_co_so
from he_thong_dinh_luong.duong_co_so.dong_lenh import _bao_cao


class kiem_tra_canh_bao_lich_su_moc_2(unittest.TestCase):
    def _canh_bao(self, so_phien: int) -> str:
        ngay_dau = date(2025, 1, 1)
        dau_vao = [
            {"ma": "AAA", "ngay": (ngay_dau + timedelta(days=chi_so)).isoformat()}
            for chi_so in range(so_phien)
        ]
        cau_hinh = cau_hinh_duong_co_so(
            cua_so_thanh_khoan=20,
            so_quan_sat_toi_thieu=20,
            nguong_thanh_khoan=0,
            cua_so_dong_luong=20,
        )
        bao_cao = _bao_cao(dau_vao, [], cau_hinh, ngay_dau, ngay_dau)
        return " ".join(bao_cao["trang_thai_tung_ma"][0]["canh_bao"])

    def test_duoi_250_canh_bao_ca_ma250_va_nguong_xac_minh(self) -> None:
        canh_bao = self._canh_bao(249)
        self.assertIn("it nhat 250 phien de tinh MA250", canh_bao)
        self.assertIn("toi thieu 260 phien", canh_bao)

    def test_tu_250_den_259_chi_canh_bao_nguong_xac_minh(self) -> None:
        canh_bao = self._canh_bao(255)
        self.assertNotIn("it nhat 250 phien de tinh MA250", canh_bao)
        self.assertIn("toi thieu 260 phien", canh_bao)


if __name__ == "__main__":
    unittest.main()
