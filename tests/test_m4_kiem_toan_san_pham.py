from __future__ import annotations

import ast
import builtins
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from he_thong_dinh_luong.nghien_cuu_moc_4 import kiem_toan_san_pham as auditor_module
from he_thong_dinh_luong.nghien_cuu_moc_4.kiem_toan_san_pham import kiem_toan_san_pham
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from ho_tro_m4_reduced import tao_dau_vao_runner


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        return list(reader.fieldnames), [dict(row) for row in reader]


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8")


def _rehash(product: Path, name: str) -> None:
    manifest_path = product / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = (product / name).read_bytes()
    manifest["files"][name] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    manifest_path.write_bytes(_json_bytes(manifest))


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class TestKiemToanSanPhamM4(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._class_tmp = tempfile.TemporaryDirectory()
        root = Path(cls._class_tmp.name)
        paths = tao_dau_vao_runner(root / "fixture")
        cls.baseline = chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=paths["cau_hinh"],
            thu_muc_publication_gia_rut_gon=paths["publication"],
            duong_dan_benchmark=paths["benchmark"],
            duong_dan_lich_benchmark=paths["lich_benchmark"],
            duong_dan_corporate_actions=paths["corporate_actions"],
            thu_muc_dau_ra=root / "out",
            ma_lan_chay="fixture_audit",
            git_commit="b" * 40,
            thoi_diem_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
        ).thu_muc_san_pham

    @classmethod
    def tearDownClass(cls) -> None:
        cls._class_tmp.cleanup()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.product = self.root / "product"
        shutil.copytree(self.baseline, self.product)
        self.audit_index = 0

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def audit(self, *, name: str = "audit") -> tuple[bool, dict[str, object], Path]:
        self.audit_index += 1
        destination = self.root / f"{name}_{self.audit_index}"
        valid, published = kiem_toan_san_pham(
            thu_muc_san_pham=self.product,
            thu_muc_bao_cao=destination,
            ma_kiem_toan=name,
        )
        report = json.loads((published / "bao_cao_kiem_toan_doc_lap.json").read_text())
        return valid, report, published

    def assertAuditError(self, code: str) -> dict[str, object]:
        valid, report, _ = self.audit(name="negative")
        self.assertFalse(valid)
        self.assertTrue(
            any(item == code or item.startswith(code + ":") for item in report["loi"]),
            report["loi"],
        )
        return report

    def mutate_csv(self, name: str, mutate: object) -> None:
        path = self.product / name
        fields, rows = _read_csv(path)
        mutate(rows)
        _write_csv(path, fields, rows)
        _rehash(self.product, name)

    def test_01_hai_lan_audit_cung_byte_va_sha256(self) -> None:
        ok1, report1, audit1 = self.audit(name="audit_fixture")
        ok2, report2, audit2 = self.audit(name="audit_fixture")
        self.assertTrue(ok1, report1["loi"])
        self.assertTrue(ok2, report2["loi"])
        self.assertEqual(report1["reconciliation_tolerance"], "1E-18")
        for name in ("bao_cao_kiem_toan_doc_lap.json", "doi_soat_nav.csv", "sha256.txt"):
            self.assertEqual((audit1 / name).read_bytes(), (audit2 / name).read_bytes())
        self.assertEqual(
            hashlib.sha256((audit1 / "sha256.txt").read_bytes()).hexdigest(),
            hashlib.sha256((audit2 / "sha256.txt").read_bytes()).hexdigest(),
        )

    def test_02_thieu_san_pham(self) -> None:
        (self.product / "nhan.csv").unlink()
        self.assertAuditError("PRODUCT_MISSING:nhan.csv")

    def test_03_thua_san_pham(self) -> None:
        (self.product / "ngoai_hop_dong.txt").write_text("x", encoding="utf-8")
        self.assertAuditError("PRODUCT_DIRECTORY_SET")

    def test_04_hash_sai(self) -> None:
        with (self.product / "feature_raw.csv").open("a", encoding="utf-8") as handle:
            handle.write("tamper\n")
        self.assertAuditError("PRODUCT_SHA256:feature_raw.csv")

    def test_05_fold_chronology_sai(self) -> None:
        def mutate(rows: list[dict[str, str]]) -> None:
            rows[0]["validation_tu"] = rows[0]["train_den"]
        self.mutate_csv("folds.csv", mutate)
        self.assertAuditError("FOLD_CHRONOLOGY")

    def test_06_purge_sai(self) -> None:
        self.mutate_csv("folds.csv", lambda rows: rows[0].__setitem__("so_phien_purge", "19"))
        self.assertAuditError("FOLD_PURGE")

    def test_07_embargo_sai(self) -> None:
        self.mutate_csv("folds.csv", lambda rows: rows[0].__setitem__("so_phien_embargo", "1"))
        self.assertAuditError("FOLD_EMBARGO")

    def test_08_du_doan_trung(self) -> None:
        self.mutate_csv("du_doan.csv", lambda rows: rows.append(dict(rows[0])))
        self.assertAuditError("PREDICTION_DUPLICATE")

    def test_09_xac_suat_ngoai_khoang(self) -> None:
        self.mutate_csv("du_doan.csv", lambda rows: rows[0].__setitem__("xac_suat_nhan_1", "1.0001"))
        self.assertAuditError("PREDICTION_PROBABILITY_RANGE")

    def test_10_ranking_sai_thu_tu(self) -> None:
        def mutate(rows: list[dict[str, str]]) -> None:
            rows[0]["thu_hang"], rows[1]["thu_hang"] = rows[1]["thu_hang"], rows[0]["thu_hang"]
        self.mutate_csv("xep_hang.csv", mutate)
        self.assertAuditError("RANK_ORDER")

    def test_11_tie_break_sai(self) -> None:
        def mutate(rows: list[dict[str, str]]) -> None:
            first, second = rows[0], rows[1]
            second["diem"] = first["diem"]
            if first["ma"] < second["ma"]:
                first["thu_hang"], second["thu_hang"] = "2", "1"
            else:
                first["thu_hang"], second["thu_hang"] = "1", "2"
        self.mutate_csv("xep_hang.csv", mutate)
        self.assertAuditError("RANK_TIE_BREAK")

    def test_12_top_k_sai(self) -> None:
        def mutate(rows: list[dict[str, str]]) -> None:
            rows[2]["duoc_chon"] = "true"
            rows[2]["ty_trong_muc_tieu"] = "0.5"
        self.mutate_csv("xep_hang.csv", mutate)
        self.assertAuditError("RANK_TOP_K")

    def test_13_trong_so_sai(self) -> None:
        self.mutate_csv("xep_hang.csv", lambda rows: rows[0].__setitem__("ty_trong_muc_tieu", "0.4"))
        self.assertAuditError("RANK_WEIGHT")

    def test_14_t1_sai(self) -> None:
        self.mutate_csv("lenh.csv", lambda rows: rows[0].__setitem__("ngay_thuc_thi", rows[0]["ngay_tin_hieu"]))
        self.assertAuditError("ORDER_NOT_EXACT_T1")

    def test_15_tien_mat_am(self) -> None:
        self.mutate_csv("nav.csv", lambda rows: rows[0].__setitem__("tien_mat", "-1"))
        self.assertAuditError("CASH_NEGATIVE")

    def test_16_vi_the_am(self) -> None:
        self.mutate_csv("vi_the.csv", lambda rows: rows[0].__setitem__("so_luong", "-1"))
        self.assertAuditError("POSITION_NEGATIVE")

    def test_17_nav_va_so_cai_khong_khop(self) -> None:
        def mutate(rows: list[dict[str, str]]) -> None:
            rows[0]["nav"] = str(Decimal(rows[0]["nav"]) + Decimal("1"))
        self.mutate_csv("so_cai.csv", mutate)
        self.assertAuditError("NAV_LEDGER_MISMATCH")

    def test_18_chenh_lech_doi_soat_vuot_nguong(self) -> None:
        self.mutate_csv("so_cai.csv", lambda rows: rows[0].__setitem__("chenh_lech_doi_soat", "0.000000000000000002"))
        self.assertAuditError("RECONCILIATION_TOLERANCE_EXCEEDED")

    def test_19_research_gate_sai(self) -> None:
        manifest_path = self.product / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["metadata"]["research_gate"] = "PASS"
        manifest_path.write_bytes(_json_bytes(manifest))
        self.assertAuditError("METADATA:research_gate")

    def test_20_destination_da_ton_tai(self) -> None:
        destination = self.root / "existing"
        destination.mkdir()
        with self.assertRaises(FileExistsError):
            kiem_toan_san_pham(
                thu_muc_san_pham=self.product,
                thu_muc_bao_cao=destination,
                ma_kiem_toan="existing",
            )

    def test_21_loi_kiem_toan_khong_sua_san_pham(self) -> None:
        with (self.product / "feature_raw.csv").open("a", encoding="utf-8") as handle:
            handle.write("tamper\n")
        before = _snapshot(self.product)
        self.assertAuditError("PRODUCT_SHA256:feature_raw.csv")
        self.assertEqual(before, _snapshot(self.product))

    def test_22_auditor_khong_import_pipeline_trainer_backtest(self) -> None:
        source_path = Path(auditor_module.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        project_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                project_imports.extend(alias.name for alias in node.names if alias.name.startswith("he_thong_dinh_luong"))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("he_thong_dinh_luong"):
                project_imports.append(node.module or "")
        self.assertEqual(project_imports, [])

        forbidden = ("runner", "logistic", "adapter_mo_phong", "mo_phong.engine")
        real_import = builtins.__import__

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            if name.startswith("he_thong_dinh_luong") and any(token in name for token in forbidden):
                raise AssertionError(f"forbidden import: {name}")
            return real_import(name, *args, **kwargs)

        spec = importlib.util.spec_from_file_location("auditor_import_guard", source_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=guarded_import):
            spec.loader.exec_module(module)

    def test_23_auditor_khong_goi_pipeline_trainer_backtest(self) -> None:
        with (
            patch(
                "he_thong_dinh_luong.nghien_cuu_moc_4.runner.chay_nghien_cuu_moc_4",
                side_effect=AssertionError("pipeline bi goi"),
            ),
            patch(
                "he_thong_dinh_luong.nghien_cuu_moc_4.logistic.huan_luyen_logistic",
                side_effect=AssertionError("trainer bi goi"),
            ),
            patch(
                "he_thong_dinh_luong.nghien_cuu_moc_4.adapter_mo_phong.chay_backtest_oos_lien_tuc",
                side_effect=AssertionError("backtest bi goi"),
            ),
        ):
            valid, report, _ = self.audit(name="guard_calls")
        self.assertTrue(valid, report["loi"])
        self.assertFalse(report["pipeline_duoc_goi"])
        self.assertFalse(report["huan_luyen_lai"])
        self.assertFalse(report["san_pham_bi_sua"])


if __name__ == "__main__":
    unittest.main()
