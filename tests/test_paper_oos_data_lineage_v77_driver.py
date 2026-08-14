from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
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
        self.assertEqual(result["wall_date_contract"], "ASIA_HO_CHI_MINH")


if __name__ == "__main__":
    unittest.main()
