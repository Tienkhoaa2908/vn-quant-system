from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from he_thong_dinh_luong.du_lieu_thi_truong.tham_so_vnstock import SO_NEN_MAC_DINH
from he_thong_dinh_luong.tai_du_lieu import chay, tao_bo_phan_tich


class ket_qua_gia_lap:
    trang_thai_tung_ma = (SimpleNamespace(ma="FPT", trang_thai="thanh_cong"),)

    def thanh_tu_dien(self) -> dict[str, object]:
        return {"ma_lan_chay": "gia_lap", "trang_thai_tung_ma": []}


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

    def test_cli_truyen_so_nen_vao_adapter(self) -> None:
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

    def test_cli_tu_choi_so_nen_khong_duong(self) -> None:
        bo = tao_bo_phan_tich()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bo.parse_args([*self._tham_so_bat_buoc(), "--so_nen", "0"])


if __name__ == "__main__":
    unittest.main()
