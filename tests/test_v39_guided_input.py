from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from he_thong_dinh_luong import v39_guided_input as guided


class V39GuidedInputTests(unittest.TestCase):
    def _write_csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_missing_workspace(self):
        with TemporaryDirectory() as temporary:
            report = guided.inspect_workspace(Path(temporary) / "missing")
            self.assertEqual(report["status"], "WORKSPACE_MISSING")

    def test_empty_workspace_is_detected_and_guide_created(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / guided.SOURCE_DIR).mkdir()
            for name in guided.COMPACT_FILES:
                self._write_csv(root / name, ["value"], [])
            self._write_csv(root / guided.EVENT_FILE, ["symbol", "event_date"], [])
            (root / guided.CONTRACT_FILE).write_text('{"verified": false}\n', encoding="utf-8")
            (root / guided.OPS_FILE).write_text(
                json.dumps({
                    "account_sync_verified": False,
                    "position_reconciliation_verified": False,
                }),
                encoding="utf-8",
            )
            report = guided.inspect_workspace(root)
            self.assertEqual(report["status"], "INPUT_EMPTY")
            self.assertTrue((root / guided.GUIDE_FILE).is_file())

    def test_any_real_input_allows_pipeline_attempt(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / guided.SOURCE_DIR).mkdir()
            for index, name in enumerate(guided.COMPACT_FILES):
                rows = [{"value": "x"}] if index == 0 else []
                self._write_csv(root / name, ["value"], rows)
            self._write_csv(root / guided.EVENT_FILE, ["symbol", "event_date"], [])
            (root / guided.CONTRACT_FILE).write_text('{"verified": false}\n', encoding="utf-8")
            (root / guided.OPS_FILE).write_text('{}\n', encoding="utf-8")
            report = guided.inspect_workspace(root)
            self.assertEqual(report["status"], "INPUT_PRESENT")


if __name__ == "__main__":
    unittest.main()
