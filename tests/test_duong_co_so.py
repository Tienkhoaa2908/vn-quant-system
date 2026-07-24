from __future__ import annotations

import unittest
from datetime import date, timedelta

from he_thong_dinh_luong.duong_co_so.chi_bao import (
    cau_hinh_duong_co_so,
    tinh_duong_co_so,
)
from he_thong_dinh_luong.duong_co_so.tap_co_phieu import (
    chi_muc_tap_co_phieu,
    thanh_vien_tap_co_phieu,
)


def thanh_vien(
    ngay: str,
    ma: str,
    nguon: str = "gia_lap",
    phien_ban: str = "v1",
) -> thanh_vien_tap_co_phieu:
    return thanh_vien_tap_co_phieu(date.fromisoformat(ngay), ma, nguon, phien_ban)


def tap_mac_dinh(*ma: str) -> chi_muc_tap_co_phieu:
    return chi_muc_tap_co_phieu(
        [thanh_vien("2020-01-01", muc) for muc in ma]
    )


def dong(
    ma: str,
    ngay: date | str,
    gia: float,
    khoi_luong: int = 1,
) -> dict[str, object]:
    ngay_chuoi = ngay.isoformat() if isinstance(ngay, date) else ngay
    return {
        "ma": ma,
        "ngay": ngay_chuoi,
        "gia_mo_cua": gia,
        "gia_cao_nhat": gia,
        "gia_thap_nhat": gia,
        "gia_dong_cua": gia,
        "khoi_luong": khoi_luong,
    }


def cau_hinh(
    *,
    cua_so_thanh_khoan: int = 3,
    so_quan_sat_toi_thieu: int = 1,
    nguong_thanh_khoan: float = 0,
    cua_so_dong_luong: int = 2,
) -> cau_hinh_duong_co_so:
    return cau_hinh_duong_co_so(
        cua_so_thanh_khoan,
        so_quan_sat_toi_thieu,
        nguong_thanh_khoan,
        cua_so_dong_luong,
    )


class kiem_tra_chi_bao(unittest.TestCase):
    def test_tinh_gia_tri_giao_dich_dung(self) -> None:
        ket_qua = tinh_duong_co_so(
            [dong("AAA", "2026-01-01", 10.5, 2000)],
            tap_mac_dinh("AAA"),
            cau_hinh(),
        )
        self.assertEqual(ket_qua[0]["gia_tri_giao_dich"], 21000.0)

    def test_cua_so_thanh_khoan_khong_nhin_truoc(self) -> None:
        cac_dong = [
            dong("AAA", "2026-01-01", 10, 1),
            dong("AAA", "2026-01-02", 20, 1),
            dong("AAA", "2026-01-03", 1000, 1),
        ]
        ket_qua = tinh_duong_co_so(
            cac_dong,
            tap_mac_dinh("AAA"),
            cau_hinh(cua_so_thanh_khoan=2, so_quan_sat_toi_thieu=1),
        )
        self.assertEqual(ket_qua[0]["gia_tri_giao_dich_trung_binh"], 10.0)
        self.assertEqual(ket_qua[1]["gia_tri_giao_dich_trung_binh"], 15.0)
        self.assertEqual(ket_qua[2]["gia_tri_giao_dich_trung_binh"], 510.0)

    def test_nguong_thanh_khoan_tai_dung_gia_tri_bien(self) -> None:
        ket_qua = tinh_duong_co_so(
            [dong("AAA", "2026-01-01", 10, 100)],
            tap_mac_dinh("AAA"),
            cau_hinh(nguong_thanh_khoan=1000),
        )
        self.assertIs(ket_qua[0]["dat_thanh_khoan"], True)

    def test_thieu_lich_su_thanh_khoan_co_trang_thai_ro_rang(self) -> None:
        ket_qua = tinh_duong_co_so(
            [dong("AAA", "2026-01-01", 10, 100)],
            tap_mac_dinh("AAA"),
            cau_hinh(cua_so_thanh_khoan=3, so_quan_sat_toi_thieu=2),
        )
        self.assertIsNone(ket_qua[0]["gia_tri_giao_dich_trung_binh"])
        self.assertIsNone(ket_qua[0]["dat_thanh_khoan"])
        self.assertIn(
            "thanh_khoan=thieu", ket_qua[0]["trang_thai_lich_su"]
        )

    def test_ma250_tai_phien_249_250_251(self) -> None:
        bat_dau = date(2025, 1, 1)
        cac_dong = [
            dong("AAA", bat_dau + timedelta(days=i), i + 1)
            for i in range(251)
        ]
        ket_qua = tinh_duong_co_so(
            cac_dong, tap_mac_dinh("AAA"), cau_hinh()
        )
        self.assertIsNone(ket_qua[248]["ma250"])
        self.assertAlmostEqual(ket_qua[249]["ma250"], 125.5)
        self.assertAlmostEqual(ket_qua[250]["ma250"], 126.5)

    def test_ma250_khong_tron_ma(self) -> None:
        bat_dau = date(2025, 1, 1)
        cac_dong = [
            dong("AAA", bat_dau + timedelta(days=i), 10) for i in range(249)
        ]
        cac_dong += [
            dong("BBB", bat_dau + timedelta(days=i), 100) for i in range(250)
        ]
        ket_qua = tinh_duong_co_so(
            cac_dong, tap_mac_dinh("AAA", "BBB"), cau_hinh()
        )
        aaa_cuoi = [muc for muc in ket_qua if muc["ma"] == "AAA"][-1]
        bbb_cuoi = [muc for muc in ket_qua if muc["ma"] == "BBB"][-1]
        self.assertIsNone(aaa_cuoi["ma250"])
        self.assertEqual(bbb_cuoi["ma250"], 100.0)

    def test_dong_luong_dung_cong_thuc_tinh_tay(self) -> None:
        ket_qua = tinh_duong_co_so(
            [
                dong("AAA", "2026-01-01", 100),
                dong("AAA", "2026-01-02", 110),
                dong("AAA", "2026-01-03", 121),
            ],
            tap_mac_dinh("AAA"),
            cau_hinh(cua_so_dong_luong=2),
        )
        self.assertAlmostEqual(ket_qua[-1]["dong_luong"], 0.21)

    def test_dong_luong_thieu_lich_su(self) -> None:
        ket_qua = tinh_duong_co_so(
            [
                dong("AAA", "2026-01-01", 100),
                dong("AAA", "2026-01-02", 110),
            ],
            tap_mac_dinh("AAA"),
            cau_hinh(cua_so_dong_luong=2),
        )
        self.assertIsNone(ket_qua[-1]["dong_luong"])
        self.assertIn("dong_luong=thieu", ket_qua[-1]["trang_thai_lich_su"])

    def test_du_lieu_dau_vao_khong_sap_xep_van_tinh_theo_ngay(self) -> None:
        ket_qua = tinh_duong_co_so(
            [
                dong("AAA", "2026-01-03", 121),
                dong("AAA", "2026-01-01", 100),
                dong("AAA", "2026-01-02", 110),
            ],
            tap_mac_dinh("AAA"),
            cau_hinh(cua_so_dong_luong=2),
        )
        self.assertEqual(
            [muc["ngay"] for muc in ket_qua],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
        )
        self.assertAlmostEqual(ket_qua[-1]["dong_luong"], 0.21)

    def test_ngay_trung_bi_tu_choi(self) -> None:
        with self.assertRaisesRegex(ValueError, "Trung ma va ngay"):
            tinh_duong_co_so(
                [
                    dong("AAA", "2026-01-01", 10),
                    dong("AAA", "2026-01-01", 11),
                ],
                tap_mac_dinh("AAA"),
                cau_hinh(),
            )

    def test_gia_hoac_khoi_luong_khong_hop_le_bi_tu_choi(self) -> None:
        for dong_loi in (
            dong("AAA", "2026-01-01", 0),
            dong("AAA", "2026-01-01", 10, -1),
        ):
            with self.subTest(dong=dong_loi):
                with self.assertRaises(ValueError):
                    tinh_duong_co_so(
                        [dong_loi], tap_mac_dinh("AAA"), cau_hinh()
                    )

    def test_ket_qua_co_thu_tu_on_dinh(self) -> None:
        ket_qua = tinh_duong_co_so(
            [
                dong("BBB", "2026-01-02", 10),
                dong("AAA", "2026-01-02", 10),
                dong("AAA", "2026-01-01", 10),
            ],
            tap_mac_dinh("AAA", "BBB"),
            cau_hinh(),
        )
        self.assertEqual(
            [(muc["ma"], muc["ngay"]) for muc in ket_qua],
            [
                ("AAA", "2026-01-01"),
                ("AAA", "2026-01-02"),
                ("BBB", "2026-01-02"),
            ],
        )

    def test_thanh_vien_duoc_xac_dinh_theo_ngay_cua_tung_dong(self) -> None:
        tap = chi_muc_tap_co_phieu(
            [
                thanh_vien("2026-01-01", "AAA"),
                thanh_vien("2026-01-03", "BBB"),
            ]
        )
        ket_qua = tinh_duong_co_so(
            [
                dong("AAA", "2026-01-02", 10),
                dong("AAA", "2026-01-04", 10),
            ],
            tap,
            cau_hinh(),
        )
        self.assertIs(ket_qua[0]["thuoc_tap_co_phieu"], True)
        self.assertIs(ket_qua[1]["thuoc_tap_co_phieu"], False)
        self.assertEqual(
            ket_qua[1]["ngay_hieu_luc_tap_co_phieu"], "2026-01-03"
        )


if __name__ == "__main__":
    unittest.main()
