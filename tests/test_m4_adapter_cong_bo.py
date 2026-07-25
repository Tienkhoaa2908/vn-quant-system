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
        result = chay_backtest_oos_lien_tuc(rankings=[rank()], du_lieu_gia=[1], cau_hinh_mo_phong=object())
        self.assertEqual(result, "ok")
        self.assertEqual(len(self.calls), 1)


class TestCongBoM4(unittest.TestCase):
    def payload(self):
        return {name: ("{}\n" if name.endswith(".json") else "a,b\n") for name in TEN_SAN_PHAM}

    def test_cong_bo_day_du_17_tep(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run-1"
            cong_bo_san_pham(dest, self.payload(), metadata={"git_commit":"abc"})
            self.assertTrue(dest.exists())
            self.assertEqual(len(list(dest.iterdir())), 17)

    def test_manifest_sha256_dung(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run-1"; payload = self.payload()
            cong_bo_san_pham(dest, payload, metadata={"git_commit":"abc"})
            manifest = json.loads((dest/"manifest.json").read_text())
            expected = hashlib.sha256(payload["cau_hinh.json"].encode()).hexdigest()
            self.assertEqual(manifest["files"]["cau_hinh.json"]["sha256"], expected)

    def test_khong_ghi_de(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run-1"; dest.mkdir()
            with self.assertRaises(FileExistsError):
                cong_bo_san_pham(dest, self.payload(), metadata={})

    def test_thieu_san_pham_bi_tu_choi(self):
        payload = self.payload(); del payload["du_doan.csv"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "sai hop dong"):
                cong_bo_san_pham(Path(tmp)/"run", payload, metadata={})

    def test_rollback_khi_loi(self):
        payload = self.payload(); payload["du_doan.csv"] = object()  # type: ignore[assignment]
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"run"
            with self.assertRaises(Exception):
                cong_bo_san_pham(dest, payload, metadata={})
            self.assertFalse(dest.exists())
            self.assertFalse(any("staging" in x.name for x in Path(tmp).iterdir()))

    def test_reproducibility_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); payload = self.payload(); metadata={"git_commit":"abc","python":"3.12"}
            d1=p/"r1"; d2=p/"r2"
            cong_bo_san_pham(d1,payload,metadata=metadata); cong_bo_san_pham(d2,payload,metadata=metadata)
            self.assertEqual((d1/"manifest.json").read_bytes(), (d2/"manifest.json").read_bytes())
