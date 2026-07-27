from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from he_thong_dinh_luong.nghien_cuu_moc_4 import cong_bo


class TestCongBoPortability(unittest.TestCase):
    def payload(self) -> dict[str, str]:
        return {
            name: ("{}\n" if name.endswith(".json") else "a,b\n")
            for name in cong_bo.TEN_SAN_PHAM
        }

    def metadata(self) -> dict[str, object]:
        return {
            "git_commit": "a" * 40,
            "ma_lan_chay": "fixture-portability",
            "thoi_diem_utc": "2026-07-27T00:00:00Z",
            "python_version": "3.12.13",
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

    def publish(self, destination: Path, payload: dict[str, str] | None = None) -> Path:
        return cong_bo.cong_bo_san_pham(
            destination,
            payload or self.payload(),
            metadata=self.metadata(),
            dau_vao={"fixture.csv": b"a,b\n1,2\n"},
        )

    def test_fsync_file_duoc_goi_cho_16_san_pham_va_manifest(self) -> None:
        real_fsync = os.fsync
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run"
            with (
                patch.object(cong_bo, "_fsync_dir", return_value=True),
                patch.object(cong_bo.os, "fsync", wraps=real_fsync) as fsync,
            ):
                self.publish(destination)
        self.assertEqual(fsync.call_count, len(cong_bo.TEN_SAN_PHAM) + 1)

    @unittest.skipIf(os.name == "nt", "Chi ap dung cho POSIX.")
    def test_posix_fsync_dir_dung_o_directory_va_dong_fd(self) -> None:
        path = Path("/tmp")
        expected_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            expected_flags |= os.O_DIRECTORY
        with (
            patch.object(cong_bo.os, "open", return_value=41) as open_mock,
            patch.object(cong_bo.os, "fsync") as fsync_mock,
            patch.object(cong_bo.os, "close") as close_mock,
        ):
            supported = cong_bo._fsync_dir(path)
        self.assertTrue(supported)
        open_mock.assert_called_once_with(path, expected_flags)
        fsync_mock.assert_called_once_with(41)
        close_mock.assert_called_once_with(41)

    @unittest.skipIf(os.name == "nt", "Chi ap dung cho POSIX.")
    def test_posix_loi_os_open_duoc_propagate(self) -> None:
        with patch.object(cong_bo.os, "open", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                cong_bo._fsync_dir(Path("/tmp"))

    @unittest.skipIf(os.name == "nt", "Chi ap dung cho POSIX.")
    def test_posix_loi_os_fsync_duoc_propagate_va_fd_van_dong(self) -> None:
        with (
            patch.object(cong_bo.os, "open", return_value=42),
            patch.object(cong_bo.os, "fsync", side_effect=OSError("disk")),
            patch.object(cong_bo.os, "close") as close_mock,
        ):
            with self.assertRaises(OSError):
                cong_bo._fsync_dir(Path("/tmp"))
        close_mock.assert_called_once_with(42)

    @unittest.skipUnless(os.name == "nt", "Chi ap dung cho Windows.")
    def test_windows_fsync_dir_khong_goi_os_open_va_tra_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with patch.object(cong_bo.os, "open") as open_mock:
                supported = cong_bo._fsync_dir(path)
        self.assertFalse(supported)
        open_mock.assert_not_called()

    def test_publication_tao_17_tep_va_manifest_hash_dung(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run"
            payload = self.payload()
            self.publish(destination, payload)
            self.assertEqual(sorted(path.name for path in destination.iterdir()), sorted((*cong_bo.TEN_SAN_PHAM, "manifest.json")))
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            expected = hashlib.sha256(payload["cau_hinh.json"].encode("utf-8")).hexdigest()
            self.assertEqual(manifest["files"]["cau_hinh.json"]["sha256"], expected)

    def test_destination_khong_bi_ghi_de(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run"
            destination.mkdir()
            marker = destination / "marker.txt"
            marker.write_text("giu-nguyen", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.publish(destination)
            self.assertEqual(marker.read_text(encoding="utf-8"), "giu-nguyen")

    def test_rollback_xoa_staging_khi_replace_loi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            destination = parent / "run"
            with patch.object(cong_bo.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    self.publish(destination)
            self.assertFalse(destination.exists())
            self.assertFalse(any("staging" in path.name for path in parent.iterdir()))

    def test_os_replace_goi_mot_lan_va_staging_cung_parent(self) -> None:
        real_replace = os.replace
        calls: list[tuple[Path, Path]] = []

        def replace(source: os.PathLike[str] | str, destination: os.PathLike[str] | str) -> None:
            source_path = Path(source)
            destination_path = Path(destination)
            calls.append((source_path, destination_path))
            real_replace(source_path, destination_path)

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run"
            with patch.object(cong_bo.os, "replace", side_effect=replace) as replace_mock:
                self.publish(destination)
        self.assertEqual(replace_mock.call_count, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].parent, calls[0][1].parent)

    def test_hai_destination_cho_manifest_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            first = parent / "run-1"
            second = parent / "run-2"
            self.publish(first)
            self.publish(second)
            self.assertEqual((first / "manifest.json").read_bytes(), (second / "manifest.json").read_bytes())

    def test_khong_con_staging_sau_thanh_cong(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            self.publish(parent / "run")
            self.assertFalse(any("staging" in path.name for path in parent.iterdir()))

    @unittest.skipUnless(os.name == "nt", "Chi xac minh publication thuc tren Windows.")
    def test_windows_publication_thuc_te_khong_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run-windows"
            self.publish(destination)
            self.assertTrue(destination.is_dir())
            self.assertEqual(len(list(destination.iterdir())), 17)


if __name__ == "__main__":
    unittest.main()
