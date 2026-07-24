from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from he_thong_dinh_luong.duong_co_so.tap_co_phieu import (
    chi_muc_tap_co_phieu,
    doc_anh_chup_csv,
    thanh_vien_tap_co_phieu,
)


def thanh_vien(
    ngay: str,
    ma: str,
    nguon: str = "gia_lap",
    phien_ban: str = "v1",
) -> thanh_vien_tap_co_phieu:
    return thanh_vien_tap_co_phieu(date.fromisoformat(ngay), ma, nguon, phien_ban)


class kiem_tra_tap_co_phieu(unittest.TestCase):
    def test_chon_anh_chup_gan_nhat_truoc_hoac_tai_ngay_danh_gia(self) -> None:
        tap = chi_muc_tap_co_phieu(
            [
                thanh_vien("2026-01-01", "AAA"),
                thanh_vien("2026-02-01", "BBB"),
            ]
        )
        ket_qua = tap.chon(date(2026, 2, 15))
        self.assertEqual(ket_qua.ngay_hieu_luc, date(2026, 2, 1))
        self.assertEqual(ket_qua.cac_ma, ("BBB",))

    def test_khong_chon_anh_chup_tuong_lai(self) -> None:
        tap = chi_muc_tap_co_phieu(
            [
                thanh_vien("2026-01-01", "AAA"),
                thanh_vien("2026-03-01", "BBB"),
            ]
        )
        self.assertEqual(tap.chon(date(2026, 2, 1)).cac_ma, ("AAA",))

    def test_loi_khi_chua_co_anh_chup_hop_le(self) -> None:
        tap = chi_muc_tap_co_phieu([thanh_vien("2026-03-01", "AAA")])
        with self.assertRaisesRegex(ValueError, "khong lon hon"):
            tap.chon(date(2026, 2, 1))

    def test_phat_hien_thanh_vien_trung(self) -> None:
        with self.assertRaisesRegex(ValueError, "Trung thanh vien"):
            chi_muc_tap_co_phieu(
                [
                    thanh_vien("2026-01-01", "AAA"),
                    thanh_vien("2026-01-01", "aaa"),
                ]
            )

    def test_doc_csv_va_sap_xep_on_dinh(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            tep = Path(thu_muc) / "tap.csv"
            tep.write_text(
                "ngay_hieu_luc,ma,nguon,phien_ban\n"
                "2026-01-01,BBB,gia_lap,v1\n"
                "2026-01-01,AAA,gia_lap,v1\n",
                encoding="utf-8",
            )
            ket_qua = doc_anh_chup_csv(tep).chon(date(2026, 1, 1))
            self.assertEqual(ket_qua.cac_ma, ("AAA", "BBB"))


if __name__ == "__main__":
    unittest.main()
