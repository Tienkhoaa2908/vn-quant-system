from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from he_thong_dinh_luong.du_lieu_thi_truong.luu_tru import kho_luu_tru
from he_thong_dinh_luong.du_lieu_thi_truong.mo_hinh import bang_du_lieu_nguon
from he_thong_dinh_luong.du_lieu_thi_truong.nguon_gia_lap import nguon_gia_lap
from he_thong_dinh_luong.du_lieu_thi_truong.tham_so_vnstock import SO_NEN_MAC_DINH
from he_thong_dinh_luong.tai_du_lieu import chay, tao_bo_phan_tich


class ket_qua_gia_lap:
    trang_thai_tung_ma = (SimpleNamespace(ma="FPT", trang_thai="thanh_cong"),)

    def thanh_tu_dien(self) -> dict[str, object]:
        return {
            "ma_lan_chay": "gia_lap",
            "so_nen_yeu_cau": 321,
            "trang_thai_tung_ma": [],
        }


def _bang_vnstock_gia_lap() -> bang_du_lieu_nguon:
    cac_cot = ("time", "open", "high", "low", "close", "volume")
    return bang_du_lieu_nguon(
        ma="FPT",
        cac_cot=cac_cot,
        kieu_du_lieu={
            "time": "datetime64[ns]",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "int64",
        },
        cac_dong=(
            {
                "time": datetime(2026, 7, 23),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1234,
            },
        ),
        anh_xa_cot={
            "time": "ngay",
            "open": "gia_mo_cua",
            "high": "gia_cao_nhat",
            "low": "gia_thap_nhat",
            "close": "gia_dong_cua",
            "volume": "khoi_luong",
        },
        don_vi_gia="nghin_dong",
        ghi_chu_khoi_luong="So luong co phieu gia lap.",
    )


class kiem_tra_cli_tai_du_lieu(unittest.TestCase):
    def _tham_so_bat_buoc(self) -> list[str]:
        return [
            "--ma",
            "FPT",
            "--ngay_bat_dau",
            "2025-06-01",
            "--ngay_ket_thuc",
            "2026-07-24",
            "--ngay_kiem_tra",
            "2026-07-25",
        ]

    def test_mac_dinh_so_nen_duoc_ghi_ro_la_400(self) -> None:
        bo = tao_bo_phan_tich()
        tham_so = bo.parse_args(self._tham_so_bat_buoc())
        self.assertEqual(tham_so.so_nen, SO_NEN_MAC_DINH)
        self.assertEqual(SO_NEN_MAC_DINH, 400)
        self.assertIn("(default: 400)", bo.format_help())

    def test_cli_truyen_so_nen_vao_adapter_va_quy_trinh(self) -> None:
        argv = ["tai_du_lieu", *self._tham_so_bat_buoc(), "--so_nen", "321"]
        nguon = SimpleNamespace()
        with (
            patch.object(sys, "argv", argv),
            patch(
                "he_thong_dinh_luong.tai_du_lieu.nguon_vnstock",
                return_value=nguon,
            ) as tao_nguon,
            patch(
                "he_thong_dinh_luong.tai_du_lieu.chay_quy_trinh",
                return_value=ket_qua_gia_lap(),
            ) as chay_quy_trinh,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(chay(), 0)
        tao_nguon.assert_called_once_with(so_nen=321)
        self.assertIs(chay_quy_trinh.call_args.args[0], nguon)
        self.assertEqual(
            chay_quy_trinh.call_args.kwargs["cau_hinh_lan_chay"],
            {"so_nen_yeu_cau": 321},
        )

    def test_tong_hop_va_stdout_cung_luu_so_nen_400_bat_bien(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            argv = [
                "tai_du_lieu",
                *self._tham_so_bat_buoc(),
                "--so_nen",
                "400",
                "--thu_muc_du_lieu",
                thu_muc,
            ]
            dau_ra = io.StringIO()
            nguon = nguon_gia_lap({"FPT": _bang_vnstock_gia_lap()})
            with (
                patch.object(sys, "argv", argv),
                patch(
                    "he_thong_dinh_luong.tai_du_lieu.nguon_vnstock",
                    return_value=nguon,
                ),
                redirect_stdout(dau_ra),
            ):
                self.assertEqual(chay(), 0)

            bao_cao_terminal = json.loads(dau_ra.getvalue())
            duong_dan_tong_hop = Path(bao_cao_terminal["duong_dan_nhat_ky"])
            bao_cao_da_luu = json.loads(
                duong_dan_tong_hop.read_text(encoding="utf-8")
            )

            self.assertEqual(bao_cao_terminal["so_nen_yeu_cau"], 400)
            self.assertEqual(bao_cao_da_luu["so_nen_yeu_cau"], 400)
            self.assertEqual(
                bao_cao_terminal["trang_thai_tung_ma"],
                bao_cao_da_luu["trang_thai_tung_ma"],
            )
            self.assertEqual(
                bao_cao_da_luu["trang_thai_tung_ma"][0]["trang_thai"],
                "thanh_cong",
            )

            noi_dung_cu = duong_dan_tong_hop.read_bytes()
            with self.assertRaises(FileExistsError):
                kho_luu_tru(thu_muc).ghi_json(
                    "nhat_ky",
                    bao_cao_terminal["ma_lan_chay"],
                    "tong_hop.json",
                    {"so_nen_yeu_cau": 999},
                )
            self.assertEqual(duong_dan_tong_hop.read_bytes(), noi_dung_cu)

    def test_cli_tu_choi_so_nen_khong_duong(self) -> None:
        bo = tao_bo_phan_tich()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bo.parse_args([*self._tham_so_bat_buoc(), "--so_nen", "0"])


if __name__ == "__main__":
    unittest.main()
