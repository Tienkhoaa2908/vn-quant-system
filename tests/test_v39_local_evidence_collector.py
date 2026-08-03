from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from he_thong_dinh_luong import v39_local_evidence_collector as collector


class V39LocalEvidenceCollectorTests(unittest.TestCase):
    def _write_candidates(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=(
                    "category", "path", "container_member", "reason",
                    "matched_tokens", "size_bytes", "sha256",
                ),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_collects_research_and_only_latest_operations_snapshot(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            research = root / "m4_tier_a_exec_20260727" / "04_corporate_action_audit"
            old_ops = root / "dnse-portfolio-live" / "snapshots" / "20260731_150000"
            new_ops = root / "dnse-portfolio-live" / "snapshots" / "20260731_170000"
            for directory in (research, old_ops, new_ops):
                directory.mkdir(parents=True)
            inventory = research / "corporate_action_inventory.csv"
            inventory.write_text("symbol,event_date\nHPG,2022-06-20\n", encoding="utf-8")
            (old_ops / "portfolio_summary.json").write_text('{"masked_account":"***1234"}\n', encoding="utf-8")
            latest = new_ops / "portfolio_summary.json"
            latest.write_text('{"masked_account":"***1234"}\n', encoding="utf-8")
            candidates = root / "candidates.csv"
            self._write_candidates(candidates, [
                {"category": "CORPORATE_ACTION", "path": str(inventory)},
                {"category": "ACCOUNT_POSITION", "path": str(old_ops / "portfolio_summary.json")},
                {"category": "ACCOUNT_POSITION", "path": str(latest)},
            ])
            output = root / "collected"
            report = collector.collect_local_evidence(
                candidates_csv=candidates,
                output_dir=output,
            )
            self.assertEqual(report["status"], "EVIDENCE_COLLECTED")
            sources = {item["source_path"] for item in report["copied_files"]}
            self.assertIn(str(inventory), sources)
            self.assertIn(str(latest), sources)
            self.assertNotIn(str(old_ops / "portfolio_summary.json"), sources)
            self.assertTrue((output / collector.MANIFEST_FILE).is_file())

    def test_unrelated_and_sensitive_files_are_not_collected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit = root / "m4_tier_a_exec_20260727" / "05_price_basis_audit"
            audit.mkdir(parents=True)
            unrelated = audit / "random.csv"
            unrelated.write_text("sector\nBANK\n", encoding="utf-8")
            sensitive = audit / "price_basis_audit.json"
            sensitive.write_text('{"password":"abcdefgh"}\n', encoding="utf-8")
            candidates = root / "candidates.csv"
            self._write_candidates(candidates, [
                {"category": "SECTOR", "path": str(unrelated)},
                {"category": "PRICE_BASIS", "path": str(sensitive)},
            ])
            output = root / "collected"
            report = collector.collect_local_evidence(
                candidates_csv=candidates,
                output_dir=output,
            )
            self.assertEqual(report["copied_file_count"], 0)
            self.assertEqual(report["status"], "NO_ELIGIBLE_EVIDENCE")
            self.assertEqual(report["skipped_files"][0]["reason"], "LIKELY_SECRET_CONTENT")


if __name__ == "__main__":
    unittest.main()
