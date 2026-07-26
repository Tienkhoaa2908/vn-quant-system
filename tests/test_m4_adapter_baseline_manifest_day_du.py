from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.adapter_mo_phong import (
    chay_backtest_oos_lien_tuc,
    chuyen_ty_trong_test,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.baseline import (
    du_doan_baseline_test,
    metric_baseline_test,
    xep_hang_baseline_test,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.cong_bo import (
    METADATA_BAT_BUOC,
    TEN_SAN_PHAM,
    cong_bo_san_pham,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import DongXepHang, MauMoHinh
from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong, thanh_gia

D1 = date(2026, 1, 30)
D1X = date(2026, 2, 2)
D2 = date(2026, 2, 27)
D2X = date(2026, 3, 2)


def ranking(day: date, symbol: str, rank: int = 1, weight: float = 0.5) -> DongXepHang:
    return DongXepHang("f1", "m1", day, symbol, 0.9 - rank / 100, rank, True, weight, 1, 0.1)


def config(mode: str = "muc_tieu_bang_0") -> cau_hinh_mo_phong:
    return cau_hinh_mo_phong(
        Decimal("100000"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        1, 252, Decimal("0"), mode, True, "khong_dieu_chinh", "dong", "dong",
    )


def prices() -> list[thanh_gia]:
    rows = []
    for symbol, base in (("AAA", 10), ("BBB", 20), ("CCC", 30)):
        for day, price in ((D1, base), (D1X, base + 1), (D2, base + 2), (D2X, base + 3)):
            rows.append(thanh_gia(symbol, day, Decimal(price), Decimal(price), 1000, True, True))
    return rows


class TestAdapterTienMatM4(unittest.TestCase):
    def target_map(self, rows):
        return {(x.ngay_tin_hieu, x.ma): x.ty_trong for x in rows}

    def test_thang_1_chon_a_thang_2_rong_ban_ve_tien_mat(self):
        targets = chuyen_ty_trong_test(
            [ranking(D1, "AAA")],
            ngay_tai_can_bang=[D1, D2], cac_ma_lien_quan=["AAA"],
        )
        mapping = self.target_map(targets)
        self.assertEqual(mapping[(D1, "AAA")], Decimal("0.5"))
        self.assertEqual(mapping[(D2, "AAA")], Decimal("0.0"))
        result = chay_backtest_oos_lien_tuc(
            rankings=[ranking(D1, "AAA")], du_lieu_gia=prices(), cau_hinh_mo_phong=config(),
            ngay_tai_can_bang=[D1, D2], cac_ma_lien_quan=["AAA"],
        )
        self.assertEqual(result.so_lan_tai_can_bang, 2)
        self.assertEqual([x.chieu for x in result.khop_lenh], ["MUA", "BAN"])
        self.assertEqual(result.khop_lenh[-1].ngay_khop, D2X)

    def test_thang_1_a_thang_2_b_a_target_0(self):
        rows = [ranking(D1, "AAA"), ranking(D2, "BBB")]
        mapping = self.target_map(chuyen_ty_trong_test(
            rows, ngay_tai_can_bang=[D1, D2], cac_ma_lien_quan=["AAA", "BBB"],
        ))
        self.assertEqual(mapping[(D2, "AAA")], Decimal("0.0"))
        self.assertEqual(mapping[(D2, "BBB")], Decimal("0.5"))

    def test_chi_du_m_nho_hon_top_k_tong_m_tren_top_k(self):
        rows = [ranking(D2, "AAA", weight=0.25), ranking(D2, "BBB", rank=2, weight=0.25)]
        targets = chuyen_ty_trong_test(
            rows, ngay_tai_can_bang=[D2], cac_ma_lien_quan=["AAA", "BBB", "CCC"],
        )
        self.assertEqual(sum((x.ty_trong for x in targets), Decimal("0")), Decimal("0.50"))

    def test_adapter_tu_choi_giu_nguyen(self):
        with self.assertRaisesRegex(ValueError, "muc_tieu_bang_0"):
            chay_backtest_oos_lien_tuc(
                rankings=[], du_lieu_gia=prices(), cau_hinh_mo_phong=config("giu_nguyen"),
                ngay_tai_can_bang=[D1], cac_ma_lien_quan=["AAA"],
            )

    def test_backtest_lien_tuc_von_khoi_tao_mot_lan(self):
        result = chay_backtest_oos_lien_tuc(
            rankings=[ranking(D1, "AAA"), ranking(D2, "BBB")],
            du_lieu_gia=prices(), cau_hinh_mo_phong=config(),
            ngay_tai_can_bang=[D1, D2], cac_ma_lien_quan=["AAA", "BBB"],
        )
        self.assertEqual(result.cau_hinh.von_ban_dau, Decimal("100000"))
        self.assertEqual(result.so_lan_tai_can_bang, 2)
        self.assertEqual(len(result.nav), 4)


class TestMomentumBaselineOOSM4(unittest.TestCase):
    def test_baseline_dung_cung_test_date_eligibility_top_k(self):
        samples = [
            MauMoHinh(D1, "AAA", (1.0,), 1, D2, 0.2),
            MauMoHinh(D1, "BBB", (2.0,), 0, D2, -0.1),
            MauMoHinh(D1, "CCC", (3.0,), 1, D2, 0.05),
        ]
        momentum = {(D1, "AAA"): 0.3, (D1, "BBB"): -0.2}  # CCC khong eligible cho baseline.
        predictions = du_doan_baseline_test(fold="f1", samples=samples, momentum_theo_khoa=momentum)
        self.assertEqual({x.ngay for x in predictions}, {D1})
        self.assertEqual({x.ma for x in predictions}, {"AAA", "BBB"})
        rankings, cash = xep_hang_baseline_test(predictions, top_k=3)
        self.assertEqual([x.ma for x in rankings if x.duoc_chon], ["AAA", "BBB"])
        self.assertAlmostEqual(cash[D1], 1 / 3)
        self.assertTrue(all(x.ty_trong_muc_tieu == 1 / 3 for x in rankings))
        metrics = metric_baseline_test(predictions)
        self.assertEqual(metrics["so_quan_sat"], 2)


class TestManifestDayDuM4(unittest.TestCase):
    def products(self):
        return {name: ("{}\n" if name.endswith(".json") else "a,b\n") for name in TEN_SAN_PHAM}

    def metadata(self):
        return {
            "git_commit": "b" * 40,
            "ma_lan_chay": "run-fixture",
            "thoi_diem_utc": "2026-07-26T00:00:00Z",
            "python_version": "3.12.10",
            "uv_version": "uv 0.11.32",
            "scikit_learn_version": "1.9.0",
            "nguon_ohlcv": "fixture-stock",
            "phien_ban_ohlcv": "v1",
            "nguon_universe": "fixture-universe",
            "phien_ban_universe": "v1",
            "nguon_benchmark": "fixture-index",
            "phien_ban_benchmark": "v1",
            "co_so_gia": "gia_dieu_chinh",
            "muc_dich_lan_chay": "kiem_tra_ky_thuat",
            "cau_hinh_feature": {"calendar": "official"},
            "cau_hinh_label": {"horizon": 20},
            "cau_hinh_fold": {"purge": 20},
            "cau_hinh_model": {"solver": "lbfgs"},
            "cau_hinh_ranking": {"top_k": 3},
            "canh_bao": ["technical-only"],
            "gioi_han": ["no-real-data"],
        }

    def test_metadata_rong_bi_tu_choi(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Metadata manifest thieu"):
                cong_bo_san_pham(
                    Path(tmp) / "run", self.products(), metadata={}, dau_vao={"input": b"x"},
                )

    def test_thieu_tung_metadata_bat_buoc_bi_tu_choi(self):
        for key in sorted(METADATA_BAT_BUOC):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                metadata = self.metadata(); metadata.pop(key)
                with self.assertRaisesRegex(ValueError, "Metadata manifest thieu"):
                    cong_bo_san_pham(
                        Path(tmp) / "run", self.products(), metadata=metadata,
                        dau_vao={"input": b"fixture"},
                    )

    def test_manifest_tu_tinh_hash_input_va_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); input_path = root / "input.csv"; input_path.write_bytes(b"a,b\n1,2\n")
            destination = root / "run"
            products = self.products()
            cong_bo_san_pham(
                destination, products, metadata=self.metadata(), dau_vao={"ohlcv": input_path},
            )
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["inputs"]["ohlcv"]["sha256"], hashlib.sha256(input_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                manifest["files"]["cau_hinh.json"]["sha256"], hashlib.sha256(products["cau_hinh.json"].encode()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
