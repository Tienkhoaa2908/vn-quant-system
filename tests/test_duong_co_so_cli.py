from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from he_thong_dinh_luong.duong_co_so.dong_lenh import _lam_sach_loi, main


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


class kiem_tra_cli(unittest.TestCase):
    def _ghi_dau_vao(self, thu_muc: Path) -> tuple[Path, Path]:
        du_lieu = thu_muc / "san_sang.csv"
        with du_lieu.open("w", encoding="utf-8", newline="") as tep:
            bo_ghi = csv.DictWriter(
                tep,
                fieldnames=(
                    "ma",
                    "ngay",
                    "gia_mo_cua",
                    "gia_cao_nhat",
                    "gia_thap_nhat",
                    "gia_dong_cua",
                    "khoi_luong",
                ),
                lineterminator="\n",
            )
            bo_ghi.writeheader()
            bo_ghi.writerow(dong("AAA", "2026-01-01", 10, 100))
        tap = thu_muc / "tap.csv"
        tap.write_text(
            "ngay_hieu_luc,ma,nguon,phien_ban\n"
            "2026-01-01,AAA,gia_lap,v1\n",
            encoding="utf-8",
        )
        return du_lieu, tap

    def _argv(self, du_lieu: Path, tap: Path, dau_ra: Path) -> list[str]:
        return [
            "--du_lieu_san_sang",
            str(du_lieu),
            "--anh_chup_tap_co_phieu",
            str(tap),
            "--ngay_danh_gia",
            "2026-01-01",
            "--cua_so_thanh_khoan",
            "1",
            "--so_quan_sat_toi_thieu",
            "1",
            "--nguong_thanh_khoan",
            "1000",
            "--cua_so_dong_luong",
            "1",
            "--thu_muc_dau_ra",
            str(dau_ra),
        ]

    def test_cli_tao_csv_va_bao_cao_json(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            goc = Path(thu_muc)
            du_lieu, tap = self._ghi_dau_vao(goc)
            dau_ra = goc / "dau_ra"
            self.assertEqual(main(self._argv(du_lieu, tap, dau_ra)), 0)
            self.assertTrue((dau_ra / "duong_co_so.csv").exists())
            bao_cao = json.loads(
                (dau_ra / "bao_cao.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                bao_cao["don_vi"]["gia_tri_giao_dich"], "nghin_dong"
            )
            trang_thai = bao_cao["trang_thai_tung_ma"][0]
            self.assertEqual(trang_thai["ma"], "AAA")
            self.assertEqual(trang_thai["so_phien"], 1)
            self.assertEqual(trang_thai["ngay_dau"], "2026-01-01")
            self.assertEqual(trang_thai["ngay_cuoi"], "2026-01-01")

    def test_cli_khong_ghi_de_san_pham(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            goc = Path(thu_muc)
            du_lieu, tap = self._ghi_dau_vao(goc)
            dau_ra = goc / "dau_ra"
            argv = self._argv(du_lieu, tap, dau_ra)
            self.assertEqual(main(argv), 0)
            noi_dung_cu = (dau_ra / "duong_co_so.csv").read_text(encoding="utf-8")
            self.assertNotEqual(main(argv), 0)
            self.assertEqual(
                (dau_ra / "duong_co_so.csv").read_text(encoding="utf-8"),
                noi_dung_cu,
            )

    def test_cli_dau_vao_khong_hop_le_tra_ma_khac_0_va_bao_cao_loi_sach(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            goc = Path(thu_muc)
            du_lieu, tap = self._ghi_dau_vao(goc)
            tap.write_text(
                "ngay_hieu_luc,ma,nguon,phien_ban\n"
                "2026-02-01,AAA,api_key=BI_MAT,v1\n",
                encoding="utf-8",
            )
            dau_ra = goc / "dau_ra"
            self.assertNotEqual(main(self._argv(du_lieu, tap, dau_ra)), 0)
            bao_cao = json.loads(
                (dau_ra / "bao_cao_loi.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("BI_MAT", bao_cao["loi"])

    def test_ham_lam_sach_loi_an_thong_tin_nhay_cam(self) -> None:
        noi_dung = _lam_sach_loi(
            ValueError("api_key=BI_MAT bearer abc.def")
        )
        self.assertNotIn("BI_MAT", noi_dung)
        self.assertNotIn("abc.def", noi_dung)
        self.assertIn("[DA_AN]", noi_dung)


if __name__ == "__main__":
    unittest.main()
