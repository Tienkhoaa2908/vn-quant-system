from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from he_thong_dinh_luong import upload_handoff_bundle_v39 as handoff


class UploadHandoffBundleV39Tests(unittest.TestCase):
    def _artifact(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "trade-reference-pack-v39/test/trade_reference_pack_v39.json",
                json.dumps({
                    "status": "SUCCESS",
                    "decision": "REFERENCE_DATA_BLOCKED",
                    "reference_pack_ready": False,
                    "gap_count": 3,
                    "live_capital_approved": False,
                }),
            )

    def test_builds_one_manifested_zip(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "upload-handoff-v39-test"
            (staging / "artifacts").mkdir(parents=True)
            (staging / "workspace" / "source_documents").mkdir(parents=True)
            (staging / "metadata").mkdir(parents=True)
            self._artifact(staging / "artifacts" / "v39.zip")
            (staging / "workspace" / "sector_intervals_import_v39.csv").write_text(
                "symbol,sector\n", encoding="utf-8"
            )
            (staging / "metadata" / "console.log").write_text(
                "REFERENCE_DATA_BLOCKED\n", encoding="utf-8"
            )
            output = root / "UPLOAD_THIS_v39-test.zip"
            result = handoff.build_handoff(staging, output)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = {Path(name).name for name in archive.namelist()}
                self.assertIn(handoff.MANIFEST_FILE, names)
                self.assertIn(handoff.SUMMARY_FILE, names)
                summary_name = next(
                    name for name in archive.namelist()
                    if Path(name).name == handoff.SUMMARY_FILE
                )
                summary = json.loads(archive.read(summary_name).decode("utf-8"))
                self.assertEqual(summary["artifact_count"], 1)
                self.assertFalse(summary["live_capital_approved"])

    def test_rejects_likely_credentials(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            staging.mkdir()
            (staging / ".env").write_text("API_SECRET=do-not-upload-this\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "V39_HANDOFF_SENSITIVE_CONTENT"):
                handoff.build_handoff(staging, root / "blocked.zip")


if __name__ == "__main__":
    unittest.main()
