from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.reference_target_v17 import load_reference_target


def csv_payload(rows):
    fields = (
        "signal_date", "symbol", "champion_model", "rank",
        "target_weight_pct", "status", "source_zip_sha256",
    )
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


class ReferenceTargetV17Tests(unittest.TestCase):
    def make_zip(self, root: Path, *, tamper: bool = False) -> Path:
        rows = [
            {
                "signal_date": "2026-07-30",
                "symbol": symbol,
                "champion_model": "online_rank_ensemble_v1",
                "rank": index,
                "target_weight_pct": 10,
                "status": "REFERENCE_PAPER_SIGNAL",
                "source_zip_sha256": "abc",
            }
            for index, symbol in enumerate(("AAA", "BBB", "CCC"), start=1)
        ]
        payload = csv_payload(rows)
        manifest = {
            "schema_version": "model_lab_reference_signal_v16",
            "status": "SUCCESS",
            "signal_date": "2026-07-30",
            "policy_id": "v15-test",
            "champion_model": "online_rank_ensemble_v1",
            "credentials_recorded": False,
            "automatic_live_orders_allowed": False,
            "live_capital_approved": False,
            "files": {
                "paper_portfolio.csv": {
                    "sha256": sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            },
        }
        path = root / "reference-signal.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr("paper_portfolio.csv", payload + (b"x" if tamper else b""))
            archive.writestr("manifest.json", json.dumps(manifest).encode())
        return path

    def test_loads_verified_reference_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_reference_target(self.make_zip(Path(tmp)))
        self.assertEqual(result["champion_model"], "online_rank_ensemble_v1")
        self.assertEqual(result["policy_id"], "v15-test")
        self.assertEqual(len(result["allocation_rows"]), 3)
        self.assertEqual(result["model"]["capital_budget_pct"], 30.0)

    def test_hash_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "REFERENCE_TARGET_HASH_MISMATCH"):
                load_reference_target(self.make_zip(Path(tmp), tamper=True))


if __name__ == "__main__":
    unittest.main()
