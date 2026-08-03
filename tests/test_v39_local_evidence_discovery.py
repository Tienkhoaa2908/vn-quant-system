from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong import v39_local_evidence_discovery as discovery


def _csv_bytes(fields: list[str], rows: list[dict[str, object]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


class V39LocalEvidenceDiscoveryTests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "sector_evidence_v39.csv").write_bytes(_csv_bytes(
            ["signal_date", "execution_day", "symbol"],
            [
                {"signal_date": "2024-01-31", "execution_day": "2024-02-01", "symbol": "AAA"},
                {"signal_date": "2024-02-29", "execution_day": "2024-03-01", "symbol": "BBB"},
            ],
        ))
        (workspace / "corporate_action_window_evidence_v39.csv").write_bytes(_csv_bytes(
            ["signal_date", "holding_start", "holding_end", "symbol"],
            [
                {"signal_date": "2024-01-31", "holding_start": "2024-02-01", "holding_end": "2024-03-01", "symbol": "AAA"},
                {"signal_date": "2024-02-29", "holding_start": "2024-03-01", "holding_end": "2024-04-01", "symbol": "BBB"},
            ],
        ))
        (workspace / "price_basis_execution_evidence_v39.csv").write_bytes(_csv_bytes(
            ["execution_day"],
            [{"execution_day": "2024-02-01"}, {"execution_day": "2024-03-01"}],
        ))
        return workspace

    def _v22(self, root: Path) -> Path:
        path = root / "daily_prediction_input.zip"
        feature = _csv_bytes(
            ["ngay", "ma", "hop_le", "eligible", "T1", "loi_nhuan_20"],
            [{"ngay": "2024-01-31", "ma": "AAA", "hop_le": "true", "eligible": "true", "T1": "2024-02-01", "loi_nhuan_20": "0.1"}],
        )
        labels = _csv_bytes(
            ["ngay", "ma", "ngay_ket_thuc_nhan", "loi_nhuan_tuong_doi"],
            [{"ngay": "2024-01-31", "ma": "AAA", "ngay_ket_thuc_nhan": "2024-03-01", "loi_nhuan_tuong_doi": "0.02"}],
        )
        config = json.dumps({
            "moc_4": {
                "stock_price_basis": "CHUA_XAC_NHAN",
                "stock_price_basis_confirmed": False,
                "corporate_actions_day_du": False,
                "candidate_union_is_point_in_time": False,
            }
        }).encode()
        with ZipFile(path, "w") as archive:
            archive.writestr("feature_raw.csv", feature)
            archive.writestr("nhan.csv", labels)
            archive.writestr("cau_hinh.json", config)
            archive.writestr("manifest.json", b"{}")
            archive.writestr("chi_so_mo_hinh.json", b"{}")
        return path

    def _sqlite(self, root: Path) -> Path:
        path = root / "market.sqlite3"
        db = sqlite3.connect(path)
        try:
            db.executescript(
                """
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE bars(
                    asset_type TEXT, symbol TEXT, day TEXT, open REAL, high REAL,
                    low REAL, close REAL, volume INTEGER, source TEXT,
                    source_version TEXT, price_basis TEXT, normalized_sha256 TEXT,
                    fetched_at TEXT
                );
                CREATE TABLE fetched_ranges(id INTEGER PRIMARY KEY);
                CREATE TABLE conflicts(id INTEGER PRIMARY KEY);
                """
            )
            db.execute("INSERT INTO metadata VALUES ('price_basis','CHUA_XAC_NHAN')")
            db.execute(
                "INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("STOCK", "AAA", "2024-02-01", 10, 11, 9, 10.5, 1000,
                 "dnse_openapi", "0.5.0", "CHUA_XAC_NHAN", "x", "2024-02-02"),
            )
            db.commit()
        finally:
            db.close()
        return path

    def test_canonical_history_does_not_invent_sector_or_actions(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = self._workspace(root)
            v22 = self._v22(root)
            store = self._sqlite(root)
            report = discovery.discover(
                workspace_dir=workspace,
                repo_root=root / "repo",
                data_root=root / "data",
                v22_zip=v22,
                sqlite_store=store,
            )
            self.assertTrue(report["conclusion"]["sector_not_present_in_canonical_history"])
            self.assertTrue(report["conclusion"]["corporate_actions_not_present_in_canonical_history"])
            self.assertFalse(report["conclusion"]["price_basis_confirmed_by_store"])
            needed = (workspace / discovery.NEEDED_FILE).read_text(encoding="utf-8")
            self.assertIn("CON THIEU DUNG 4 NHOM", needed)
            self.assertIn("AAA|BBB", needed)

    def test_scanner_finds_likely_local_sector_file(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = self._workspace(root)
            v22 = self._v22(root)
            store = self._sqlite(root)
            repo = root / "repo"
            data = root / "data"
            repo.mkdir()
            data.mkdir()
            candidate = data / "official_sector_master.csv"
            candidate.write_bytes(_csv_bytes(
                ["symbol", "sector", "effective_from", "effective_to"],
                [{"symbol": "AAA", "sector": "BANK", "effective_from": "2024-01-01", "effective_to": "2024-12-31"}],
            ))
            report = discovery.discover(
                workspace_dir=workspace,
                repo_root=repo,
                data_root=data,
                v22_zip=v22,
                sqlite_store=store,
            )
            self.assertGreater(report["scan"]["candidate_count"], 0)
            with (workspace / discovery.CANDIDATES_FILE).open(
                "r", encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(any(row["category"] == "SECTOR" and row["path"] == str(candidate) for row in rows))

    def test_output_files_are_created(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = self._workspace(root)
            report = discovery.discover(
                workspace_dir=workspace,
                repo_root=root,
                data_root=root,
                v22_zip=self._v22(root),
                sqlite_store=self._sqlite(root),
                max_files=100,
            )
            self.assertEqual(report["workspace"]["unique_symbol_count"], 2)
            for name in (
                discovery.REPORT_FILE,
                discovery.CANDIDATES_FILE,
                discovery.NEEDED_FILE,
                discovery.SYMBOLS_FILE,
            ):
                self.assertTrue((workspace / name).is_file())


if __name__ == "__main__":
    unittest.main()
