from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from he_thong_dinh_luong import paper_oos_data_lineage_v77 as core
from he_thong_dinh_luong import paper_oos_data_lineage_v77_driver as driver


class TestV77Driver(unittest.TestCase):
    def test_vietnam_date_not_utc_date_controls_month_boundary(self):
        # 2026-09-01 00:30 in Vietnam is still 2026-08-31 UTC.
        captured = datetime.fromisoformat("2026-09-01T00:30:00+07:00")
        seen = {}

        def fake_core_run(**kwargs):
            seen["analysis_end"] = core._analysis_end_for_capture(
                datetime.fromisoformat("2026-08-31T00:00:00+00:00").date(),
                captured.astimezone(timezone.utc).date(),
                False,
            )
            return {
                "status": "SUCCESS",
                "capture_market_day": "2026-08-31",
                "source_signal_day": "2026-08-31",
                "signals_appended": {},
                "paper_results": {core.CHAMPION_MODEL: {}, core.SHADOW_MODEL: {}},
                "data_lineage": {"blockers": []},
            }

        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "run", side_effect=fake_core_run):
            out = Path(tmp)
            result = driver.run(
                store=out / "unused.sqlite3",
                state_dir=out / "state",
                output_dir=out,
                captured_at=captured,
            )
        self.assertEqual(seen["analysis_end"].isoformat(), "2026-09-01")
        self.assertEqual(result["capture_wall_date_vn"], "2026-09-01")
        self.assertEqual(result["wall_date_contract"], "ASIA_HO_CHI_MINH_UTC_PLUS_07")

    def test_existing_pit_membership_interval_v2_is_recognized_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "membership_coverage.json"
            record = {
                "contract_version": "pit_membership_interval_v2",
                "range_start": "2020-01-01",
                "range_end": "2030-01-01",
                "complete": True,
                "gaps": [],
                "conflicts": [],
                "research_eligible": True,
                "is_fixture": False,
                "source_document_ids": ["official-1"],
            }
            path.write_text(json.dumps(record), encoding="utf-8")
            result = driver._scan_evidence_once(
                [root], target_day=date(2026, 8, 14), store_sha="0" * 64
            )
            self.assertTrue(result["passes"]["pit_hose_membership"])
            record["is_fixture"] = True
            path.write_text(json.dumps(record), encoding="utf-8")
            result = driver._scan_evidence_once(
                [root], target_day=date(2026, 8, 14), store_sha="0" * 64
            )
            self.assertFalse(result["passes"]["pit_hose_membership"])

    def test_existing_freeze_model_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            freeze = {
                "schema_version": core.FREEZE_SCHEMA,
                "champion_model": "WRONG_MODEL",
                "shadow_model": core.SHADOW_MODEL,
                "primary_variant": core.PRIMARY_VARIANT,
                "primary_allocator": core.PRIMARY_ALLOCATOR,
                "paper_cost_contract": core.PAPER_COST_CONTRACT,
                "future_model_mutation_allowed": False,
                "capital_authorized": False,
                "variant_symbols": [f"S{i:02d}" for i in range(12)],
            }
            (state / "freeze_manifest.json").write_text(json.dumps(freeze), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "V77_EXISTING_FREEZE_DEFINITION_DRIFT:champion_model"):
                driver._validate_existing_freeze(state)


if __name__ == "__main__":
    unittest.main()
