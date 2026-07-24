from __future__ import annotations

import unittest
from datetime import datetime

from he_thong_dinh_luong.du_lieu_thi_truong.mo_hinh import (
    khong_co_du_lieu,
    loi_nguon_du_lieu,
)
from he_thong_dinh_luong.du_lieu_thi_truong.nguon_vnstock import nguon_vnstock


class cot_gia_lap:
    def __init__(self, kieu: str) -> None:
        self.dtype = kieu


class bang_gia_lap:
    def __init__(
        self,
        cac_dong: list[dict[str, object]],
        kieu: dict[str, str] | None = None,
    ) -> None:
        self._cac_dong = cac_dong
        self.columns = list(cac_dong[0]) if cac_dong else [
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        self._kieu = kieu or {
            "time": "datetime64[ns]",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "int64",
        }
        self.empty = not cac_dong

    def __getitem__(self, cot: str) -> cot_gia_lap:
        return cot_gia_lap(self._kieu[cot])

    def to_dict(self, *, orient: str):
        if orient != "records":
            raise AssertionError(orient)
        return list(self._cac_dong)


class bo_doc_gia_lap:
    def __init__(
        self,
        bang: bang_gia_lap | None = None,
        loi: BaseException | None = None,
    ) -> None:
        self.bang = bang
        self.loi = loi
        self.tham_so: dict[str, object] | None = None

    def ohlcv(self, **tham_so):
        self.tham_so = tham_so
        if self.loi is not None:
            raise self.loi
        return self.bang


class thi_truong_gia_lap:
    def __init__(self, bo_doc: bo_doc_gia_lap) -> None:
        self.bo_doc = bo_doc
        self.loai: str | None = None
        self.ma: str | None = None

    def equity(self, *, symbol: str):
        self.loai = "equity"
        self.ma = symbol
        return self.bo_doc

    def index(self, *, symbol: str):
        self.loai = "index"
        self.ma = symbol
        return self.bo_doc


def dong_hop_le() -> dict[str, object]:
    return {
        "time": datetime(2026, 7, 1),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1234,
    }


class kiem_tra_nguon_vnstock(unittest.TestCase):
    def tao_nguon(
        self, thi_truong: thi_truong_gia_lap, *, so_nen: int = 321
    ) -> nguon_vnstock:
        return nguon_vnstock(
            so_nen=so_nen,
            ham_tao_thi_truong=lambda: thi_truong,
            ham_lay_phien_ban=lambda _: "4.0.4",
        )

    def test_co_phieu_truyen_count_dung_cho_vnstock_va_anh_xa(self) -> None:
        bo_doc = bo_doc_gia_lap(bang_gia_lap([dong_hop_le()]))
        thi_truong = thi_truong_gia_lap(bo_doc)
        bang = self.tao_nguon(thi_truong, so_nen=321).lay_du_lieu(
            "fpt", "2026-07-01", "2026-07-02"
        )
        self.assertEqual(thi_truong.loai, "equity")
        self.assertEqual(thi_truong.ma, "FPT")
        self.assertEqual(
            bo_doc.tham_so,
            {
                "start": "2026-07-01",
                "end": "2026-07-02",
                "interval": "1D",
                "source": "kbs",
                "count": 321,
            },
        )
        self.assertEqual(
            bang.cac_cot,
            ("time", "open", "high", "low", "close", "volume"),
        )
        self.assertEqual(bang.kieu_du_lieu["volume"], "int64")
        self.assertEqual(bang.don_vi_gia, "nghin_dong")
        self.assertIsNone(bang.tham_so_gia)

    def test_vnindex_dung_giao_dien_chi_so_va_don_vi_diem(self) -> None:
        bo_doc = bo_doc_gia_lap(bang_gia_lap([dong_hop_le()]))
        thi_truong = thi_truong_gia_lap(bo_doc)
        bang = self.tao_nguon(thi_truong).lay_du_lieu(
            "VNINDEX", "2026-07-01", "2026-07-02"
        )
        self.assertEqual(thi_truong.loai, "index")
        self.assertEqual(bang.don_vi_gia, "diem")
        self.assertIn("can doi chieu log that", bang.ghi_chu_khoi_luong)

    def test_so_nen_khong_duong_bi_tu_choi_tai_adapter(self) -> None:
        with self.assertRaises(ValueError):
            nguon_vnstock(
                so_nen=0,
                ham_tao_thi_truong=lambda: None,
                ham_lay_phien_ban=lambda _: "4.0.4",
            )

    def test_khong_co_du_lieu_duoc_phan_loai_rieng(self) -> None:
        thi_truong = thi_truong_gia_lap(bo_doc_gia_lap(bang_gia_lap([])))
        with self.assertRaises(khong_co_du_lieu):
            self.tao_nguon(thi_truong).lay_du_lieu(
                "FPT", "2026-07-01", "2026-07-02"
            )

    def test_thieu_cot_bi_tu_choi(self) -> None:
        du_lieu = dong_hop_le()
        del du_lieu["volume"]
        thi_truong = thi_truong_gia_lap(bo_doc_gia_lap(bang_gia_lap([du_lieu])))
        with self.assertRaises(loi_nguon_du_lieu):
            self.tao_nguon(thi_truong).lay_du_lieu(
                "FPT", "2026-07-01", "2026-07-02"
            )

    def test_loi_mang_duoc_danh_dau_tam_thoi(self) -> None:
        thi_truong = thi_truong_gia_lap(
            bo_doc_gia_lap(loi=TimeoutError("network timeout"))
        )
        with self.assertRaises(loi_nguon_du_lieu) as boi_canh:
            self.tao_nguon(thi_truong).lay_du_lieu(
                "FPT", "2026-07-01", "2026-07-02"
            )
        self.assertTrue(boi_canh.exception.tam_thoi)

    def test_sai_phien_ban_bi_tu_choi(self) -> None:
        with self.assertRaises(RuntimeError):
            nguon_vnstock(
                so_nen=400,
                ham_tao_thi_truong=lambda: None,
                ham_lay_phien_ban=lambda _: "4.0.5",
            )


if __name__ == "__main__":
    unittest.main()
