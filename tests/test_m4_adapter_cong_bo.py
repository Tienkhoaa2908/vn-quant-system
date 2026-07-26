from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from datetime import date

from he_thong_dinh_luong.nghien_cuu_moc_4.adapter_mo_phong import chay_backtest_oos_lien_tuc, chuyen_ty_trong_test
from he_thong_dinh_luong.nghien_cuu_moc_4.cong_bo import TEN_SAN_PHAM, cong_bo_san_pham
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import DongXepHang

D1 = date(2026,1,30)


def rank(symbol="AAA", weight=.5):
    return DongXepHang("f","m",D1,symbol,.9,1,True,weight,1,.1)


class TestAdapterM4(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._old_pkg = sys.modules.get("he_thong_dinh_luong.mo_phong")
        self._old_model = sys.modules.get("he_thong_dinh_luong.mo_phong.mo_hinh")
        pkg = ModuleType("he_thong_dinh_luong.mo_phong")
        model = ModuleType("he_thong_dinh_luong.mo_phong.mo_hinh")
        class Target:
            def __init__(self, **kwargs): self.__dict__.update(kwargs)
        def engine(*args): self.calls.append(args); return "ok"
        model.ty_trong_muc_tieu = Target
        pkg.chay_mo_phong = engine
        sys.modules["he_thong_dinh_luong.mo_phong"] = pkg
        sys.modules["he_thong_dinh_luong.mo_phong.mo_hinh"] = model

    def tearDown(self):
        if self._old_pkg is None:
            sys.modules.pop("he_thong_dinh_luong.mo_phong", None)
        else:
            sys.modules["he_thong_dinh_luong.mo_phong"] = self._old_pkg
        if self._old_model is None:
            sys.modules.pop("he_thong_dinh_luong.mo_phong.mo_hinh", None)
        else:
            sys.modules["he_thong_dinh_luong.mo_phong.mo_hinh"] = self._old_model

    def test_chuyen_target_weight_co_thu_tu(self):
        targets = chuyen_ty_trong_test([rank("BBB"), rank("AAA")])
        self.assertEqual([x.ma for x in targets], ["AAA","BBB"])

    def test_duplicate_target_bi_tu_choi(self):
        row = rank()
        with self.assertRaisesRegex(ValueError, "Trung khoa"):
            chuyen_ty_trong_test([row,row])

    def test_engine_duoc_goi_mot_lan_cho_chuoi_oos(self):
        result = chay_backtest_oos_lien_tuc(rankings=[rank()], du_lieu_gia=[1], cau_hinh_mo_phong=SimpleNamespace(che_do_ma_khong_xuat_hien="muc_tieu_bang_0"))
        self.assertEqual(result, "ok")
        self.assertEqual(len(self.calls), 1)


class TestCongBoM4(unittest.TestCase):
    def payload(self):
        return {name: ("{}\n" if name.endswith(".json") else "a,b\n") for name in TEN_SAN_PHAM}

    def metadata(self):
        return {
            "git_commit": "a" * 40,
            "ma_lan_chay": "fixture",
            "thoi_diem_utc": "2026-07-26T00:00:00Z",
            "python_version": "3.12.10",
            "uv_version": "uv 0.11.32",
            "scikit_learn_version": "1.9.0",
            "nguon_ohlcv": "fixture",
            "phien_ban_ohlcv": "1",
            "nguon_universe": "fixture",
            "phien_ban_universe": "1",
            "nguon_benchmark": "fixture",
            "phien_ban_benchmark": "1",
            "co_so_gia": "gia_dieu_chinh",
            "muc_dich_lan_chay": "kiem_tra_ky_thuat",
            "cau_hinh_feature": {"lich": "benchmark"},
            "cau_hinh_label": {"horizon": 20},
            "cau_hinh_fold": {"expanding": True},
            "cau_hinh_model": {"solver": "lbfgs"},
            "cau_hinh_ranking": {"top_k": 2},
            "canh_bao": [],
            "gioi_han": ["fixture"],
        }

    def publish(self, dest, payload=None, metadata=None):
        return cong_bo_san_pham(
            dest, payload or self.payload(), metadata=metadata or self.metadata(),
            dau_vao={"fixture.csv": b"a,b\n1,2\n"},
        )

    def test_cong_bo_day_du_17_tep(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run-1"
            self.publish(dest)
            self.assertTrue(dest.exists())
            self.assertEqual(len(list(dest.iterdir())), 17)

    def test_manifest_sha256_dung(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run-1"; payload = self.payload()
            self.publish(dest, payload)
            manifest = json.loads((dest/"manifest.json").read_text())
            expected = hashlib.sha256(payload["cau_hinh.json"].encode()).hexdigest()
            self.assertEqual(manifest["files"]["cau_hinh.json"]["sha256"], expected)

    def test_khong_ghi_de(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run-1"; dest.mkdir()
            with self.assertRaises(FileExistsError):
                self.publish(dest)

    def test_thieu_san_pham_bi_tu_choi(self):
        payload = self.payload(); del payload["du_doan.csv"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "sai hop dong"):
                self.publish(Path(tmp)/"run", payload)

    def test_rollback_khi_loi(self):
        payload = self.payload(); payload["du_doan.csv"] = object()  # type: ignore[assignment]
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run"
            with self.assertRaises(Exception):
                self.publish(dest, payload)
            self.assertFalse(dest.exists())
            self.assertFalse(any("staging" in x.name for x in Path(tmp).iterdir()))

    def test_reproducibility_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); payload = self.payload(); metadata=self.metadata()
            d1=p/"r1"; d2=p/"r2"
            self.publish(d1,payload,metadata); self.publish(d2,payload,metadata)
            self.assertEqual((d1/"manifest.json").read_bytes(), (d2/"manifest.json").read_bytes())
