from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from he_thong_dinh_luong.tai_du_lieu_vn100 import (
    CAC_LOAI_VI_PHAM,
    CauHinhTaiVN100,
    NguonGioiHanTocDo,
    RAW_NOT_PRESERVED,
    TAI_NGUON_THANH_CONG_KIEM_TRA_DAT,
    TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI,
    TAI_NGUON_THAT_BAI,
    chay_tai_hang_loat,
    doc_danh_sach_ma,
    kiem_toan_raw_vn100,
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
    def __init__(
        self,
        ma: str,
        raw: Path | None,
        ma_bam: str | None,
        *,
        loi: str | None = None,
        so_dong: int = 1,
    ) -> None:
        self.ma = ma
        self.trang_thai = "that_bai" if loi else "thanh_cong"
        self.duong_dan_tho = str(raw) if raw else None
        self.ma_sha256 = ma_bam
        self.loi = loi
        self.so_dong = so_dong
        self.ngay_dau = "2026-07-20" if raw else None
        self.ngay_cuoi = "2026-07-24" if raw else None
        self.ten_cot_nguon = ("time", "open", "high", "low", "close", "volume")
        self.kieu_du_lieu = {"open": "float64", "volume": "int64"}

    def thanh_tu_dien(self):
        return {
            "ma": self.ma,
            "trang_thai": self.trang_thai,
            "duong_dan_tho": self.duong_dan_tho,
            "ma_sha256": self.ma_sha256,
            "so_dong": self.so_dong,
            "ngay_dau": self.ngay_dau,
            "ngay_cuoi": self.ngay_cuoi,
            "ten_cot_nguon": self.ten_cot_nguon,
            "kieu_du_lieu": self.kieu_du_lieu,
            "loi": self.loi,
        }


def ghi_danh_sach(path: Path, *cac_ma: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as tep:
        bo_ghi = csv.DictWriter(tep, fieldnames=["ma"])
        bo_ghi.writeheader()
        for ma in cac_ma:
            bo_ghi.writerow({"ma": ma})


def ghi_raw(
    root: Path,
    run_prefix: str,
    ma: str,
    cac_dong: list[dict[str, object]],
    *,
    lan_tai: int = 1,
) -> Path:
    thu_muc = root / f"{run_prefix}_{ma}_{lan_tai:03d}"
    thu_muc.mkdir(parents=True, exist_ok=True)
    path = thu_muc / f"{ma}.json"
    payload = {
        "ma": ma,
        "nguon": "vnstock_kbs",
        "phien_ban": "4.0.4",
        "cac_cot": ["time", "open", "high", "low", "close", "volume"],
        "kieu_du_lieu": {
            "time": "datetime64[ns]",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "int64",
        },
        "du_lieu": cac_dong,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def dong(
    ngay: str,
    *,
    open_: object = 10,
    high: object = 11,
    low: object = 9,
    close: object = 10.5,
    volume: object = 1000,
) -> dict[str, object]:
    return {
        "time": ngay,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


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

    def test_checkpoint_phan_loai_ba_tang_va_giu_raw_khi_kiem_tra_that_bai(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            cau_hinh = self.tao_cau_hinh(thu_muc, "FPT", "HPG", "MBB")
            raw_hpg: Path | None = None

            def chay_gia_lap(_nguon, cac_ma, *_args, **_kwargs):
                nonlocal raw_hpg
                ma = tuple(cac_ma)[0]
                if ma == "MBB":
                    return SimpleNamespace(
                        trang_thai_tung_ma=(
                            TrangThaiGiaLap(ma, None, None, loi="loi mang"),
                        )
                    )
                raw = Path(thu_muc) / f"{ma}.json"
                raw.write_text('{"raw":true}\n', encoding="utf-8")
                ma_bam = hashlib.sha256(raw.read_bytes()).hexdigest()
                if ma == "HPG":
                    raw_hpg = raw
                    trang_thai = TrangThaiGiaLap(
                        ma, raw, ma_bam, loi="HIGH_LT_OPEN", so_dong=7
                    )
                else:
                    trang_thai = TrangThaiGiaLap(ma, raw, ma_bam, so_dong=9)
                return SimpleNamespace(trang_thai_tung_ma=(trang_thai,))

            ket_qua = chay_tai_hang_loat(
                cau_hinh,
                ham_tao_nguon=lambda _so_nen: NguonGiaLap(),
                ham_chay_quy_trinh=chay_gia_lap,
                ham_cho=lambda _giay: None,
            )
            checkpoint = json.loads(Path(ket_qua["checkpoint"]).read_text(encoding="utf-8"))
            self.assertEqual(
                checkpoint["trang_thai_tung_ma"]["FPT"]["trang_thai"],
                TAI_NGUON_THANH_CONG_KIEM_TRA_DAT,
            )
            hpg = checkpoint["trang_thai_tung_ma"]["HPG"]
            self.assertEqual(hpg["trang_thai"], TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI)
            self.assertEqual(hpg["so_dong_nguon"], 7)
            self.assertEqual(hpg["phien_ban_nguon"], "4.0.4")
            self.assertEqual(hpg["ma_sha256"], hashlib.sha256(raw_hpg.read_bytes()).hexdigest())
            self.assertEqual(
                checkpoint["trang_thai_tung_ma"]["MBB"]["trang_thai"],
                TAI_NGUON_THAT_BAI,
            )
            self.assertEqual(
                checkpoint["trang_thai_tung_ma"]["MBB"]["trang_thai_raw"],
                RAW_NOT_PRESERVED,
            )
            self.assertTrue(raw_hpg.exists())
            self.assertEqual(
                ket_qua["tai_nguon_thanh_cong_kiem_tra_that_bai_trong_lan_nay"], 1
            )

    def test_tiep_tuc_chi_bo_qua_khi_kiem_tra_dat_va_hash_raw_con_khop(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            cau_hinh = self.tao_cau_hinh(thu_muc, "FPT")
            so_lan_chay = 0

            def chay_gia_lap(_nguon, cac_ma, *_args, **_kwargs):
                nonlocal so_lan_chay
                so_lan_chay += 1
                ma = tuple(cac_ma)[0]
                raw = Path(thu_muc) / f"{ma}_{so_lan_chay}.json"
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

            Path(thu_muc, "FPT_1.json").write_text('{"sua":true}\n', encoding="utf-8")
            lan_3 = chay_tai_hang_loat(
                cau_hinh,
                ham_tao_nguon=lambda _so_nen: NguonGiaLap(),
                ham_chay_quy_trinh=chay_gia_lap,
                ham_cho=lambda _giay: None,
            )
            self.assertEqual(lan_3["tai_thanh_cong_trong_lan_nay"], 1)
            self.assertEqual(so_lan_chay, 2)


class KiemTraKiemToanRaw(unittest.TestCase):
    def tao_du_lieu(self, thu_muc: str, *cac_ma: str):
        root = Path(thu_muc)
        danh_sach = root / "ma.csv"
        ghi_danh_sach(danh_sach, *cac_ma)
        raw_root = root / "tho"
        bao_cao = root / "bao_cao"
        return danh_sach, raw_root, bao_cao

    def test_bao_cao_dung_ngay_gia_tri_va_mot_dong_nhieu_loi(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            danh_sach, raw_root, bao_cao = self.tao_du_lieu(thu_muc, "FPT")
            ghi_raw(
                raw_root,
                "vn100_full_windows_20260724_eeca1708",
                "FPT",
                [dong("2026-07-21", open_=10, high=8, low=12, close=11, volume=-1)],
            )
            ket_qua = kiem_toan_raw_vn100(
                danh_sach_ma=danh_sach,
                thu_muc_tho=raw_root,
                tien_to_lan_chay="vn100_full_windows_20260724_eeca1708",
                thu_muc_bao_cao=bao_cao,
            )
            with Path(ket_qua["bao_cao_bat_thuong_ohlc"]).open(
                encoding="utf-8", newline=""
            ) as tep:
                rows = list(csv.DictReader(tep))
            self.assertEqual({r["ngay"] for r in rows}, {"2026-07-21"})
            self.assertEqual({r["open"] for r in rows}, {"10"})
            self.assertEqual(
                {r["loai_vi_pham"] for r in rows},
                {
                    "HIGH_LT_OPEN",
                    "HIGH_LT_CLOSE",
                    "LOW_GT_OPEN",
                    "LOW_GT_CLOSE",
                    "NEGATIVE_VOLUME",
                },
            )
            self.assertEqual(ket_qua["tong_so_ngay_vi_pham_duy_nhat"], 1)
            self.assertEqual(ket_qua["so_ma_co_loi_open_close_volume_doc_lap"], 1)

    def test_non_finite_non_positive_duplicate_va_dem_xac_dinh(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            danh_sach, raw_root, bao_cao = self.tao_du_lieu(thu_muc, "FPT")
            ghi_raw(
                raw_root,
                "run",
                "FPT",
                [
                    dong("2026-07-20", open_=0, high="nan", low=9, close=10, volume=1),
                    dong("2026-07-20", open_=10, high=11, low=9, close=10, volume=1),
                ],
            )
            ket_qua = kiem_toan_raw_vn100(
                danh_sach_ma=danh_sach,
                thu_muc_tho=raw_root,
                tien_to_lan_chay="run",
                thu_muc_bao_cao=bao_cao,
            )
            self.assertEqual(ket_qua["so_loi_theo_loai"]["NON_FINITE"], 1)
            self.assertEqual(ket_qua["so_loi_theo_loai"]["NON_POSITIVE_PRICE"], 1)
            self.assertEqual(ket_qua["so_loi_theo_loai"]["DUPLICATE_DATE"], 2)
            self.assertEqual(tuple(ket_qua["so_loi_theo_loai"]), CAC_LOAI_VI_PHAM)

    def test_chi_loi_high_low_duoc_tach_khoi_loi_ocv_doc_lap(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            danh_sach, raw_root, bao_cao = self.tao_du_lieu(thu_muc, "FPT", "HPG")
            ghi_raw(raw_root, "run", "FPT", [dong("2026-07-20", high=9, open_=10)])
            ghi_raw(raw_root, "run", "HPG", [dong("2026-07-20", open_=0)])
            ket_qua = kiem_toan_raw_vn100(
                danh_sach_ma=danh_sach,
                thu_muc_tho=raw_root,
                tien_to_lan_chay="run",
                thu_muc_bao_cao=bao_cao,
            )
            self.assertEqual(
                ket_qua["so_ma_chi_loi_high_low_nhung_open_close_volume_hop_le"], 1
            )
            self.assertEqual(ket_qua["so_ma_co_loi_open_close_volume_doc_lap"], 1)
            self.assertEqual(ket_qua["so_ma_open_close_volume_hop_le"], 1)
            self.assertEqual(ket_qua["so_ma_khong_the_dung_hop_dong_rut_gon"], 1)

    def test_kiem_toan_khong_goi_mang_raw_khong_doi_va_ket_qua_xac_dinh(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            danh_sach, raw_root, bao_cao = self.tao_du_lieu(thu_muc, "FPT", "MBB")
            raw = ghi_raw(raw_root, "run", "FPT", [dong("2026-07-20")])
            raw_truoc = raw.read_bytes()
            checkpoint = Path(thu_muc) / "checkpoint.json"

            with patch(
                "he_thong_dinh_luong.tai_du_lieu_vn100.nguon_vnstock",
                side_effect=AssertionError("khong duoc goi mang"),
            ):
                lan_1 = kiem_toan_raw_vn100(
                    danh_sach_ma=danh_sach,
                    thu_muc_tho=raw_root,
                    tien_to_lan_chay="run",
                    thu_muc_bao_cao=bao_cao,
                    checkpoint_path=checkpoint,
                )
            csv_1 = Path(lan_1["bao_cao_bat_thuong_ohlc"]).read_bytes()
            json_1 = Path(lan_1["bao_cao_phan_loai_121_ma"]).read_bytes()
            lan_2 = kiem_toan_raw_vn100(
                danh_sach_ma=danh_sach,
                thu_muc_tho=raw_root,
                tien_to_lan_chay="run",
                thu_muc_bao_cao=bao_cao,
                checkpoint_path=checkpoint,
            )
            self.assertEqual(raw.read_bytes(), raw_truoc)
            self.assertEqual(Path(lan_2["bao_cao_bat_thuong_ohlc"]).read_bytes(), csv_1)
            self.assertEqual(Path(lan_2["bao_cao_phan_loai_121_ma"]).read_bytes(), json_1)
            cp = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(
                cp["trang_thai_tung_ma"]["FPT"]["trang_thai"],
                TAI_NGUON_THANH_CONG_KIEM_TRA_DAT,
            )
            self.assertEqual(cp["trang_thai_tung_ma"]["MBB"]["trang_thai_raw"], RAW_NOT_PRESERVED)

    def test_chon_lan_tai_moi_nhat_theo_ma(self) -> None:
        with tempfile.TemporaryDirectory() as thu_muc:
            danh_sach, raw_root, bao_cao = self.tao_du_lieu(thu_muc, "BCM")
            ghi_raw(raw_root, "run", "BCM", [dong("2026-07-20", high=8)], lan_tai=1)
            raw_moi = ghi_raw(raw_root, "run", "BCM", [dong("2026-07-20")], lan_tai=2)
            ket_qua = kiem_toan_raw_vn100(
                danh_sach_ma=danh_sach,
                thu_muc_tho=raw_root,
                tien_to_lan_chay="run",
                thu_muc_bao_cao=bao_cao,
            )
            self.assertEqual(ket_qua["so_raw_file_thuc_te_tim_thay"], 2)
            self.assertEqual(ket_qua["so_ma_kiem_tra_dat"], 1)
            self.assertEqual(
                ket_qua["trang_thai_tung_ma"]["BCM"]["duong_dan_tho"], str(raw_moi)
            )


if __name__ == "__main__":
    unittest.main()
