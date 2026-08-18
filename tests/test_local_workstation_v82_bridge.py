from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import local_workstation_v82_bridge as v82


class V82BridgeTest(unittest.TestCase):
    def test_combines_tactical_paper_profit_without_live_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            system = repo / "vn_quant_local_system"
            system.mkdir()
            profit_path = repo / "tai_lieu_dieu_phoi" / "v81_profit_snapshot_20260818.json"
            profit_path.parent.mkdir()
            profit_path.write_text(json.dumps({
                "status": "AUDITED_POST_SELECTION_DIAGNOSTIC",
                "primary_tactical_paper_challenger": "L15_SWAP50_WORST",
                "policies": [{"policy_id": "L15_SWAP50_WORST", "total_return_uplift_vs_c3": 0.33}],
                "live_orders_allowed": False,
            }), encoding="utf-8")
            obs = repo / "du_lieu" / "v80-tactical-paper-state" / "observations"
            obs.mkdir(parents=True)
            (obs / "x.json").write_text(json.dumps({
                "observation_id": "2026-07-31__2026-08-17",
                "capture_wall_time_vn": "2026-08-18T08:35:00+07:00",
                "execution_floor_date": "2026-08-18",
                "execution_floor_contract": "FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN",
                "target": {"exact_l15_active": True, "leader": "AAA", "swap_out": "BBB"},
                "actions": [{"status": "PENDING_FIRST_EXECUTION"}],
                "outcomes": [],
            }), encoding="utf-8")
            (obs / "x.rows.json").write_text("[]", encoding="utf-8")
            with patch.object(v82, "read_v78_tactical_snapshot", return_value={"status": "SUCCESS"}):
                result = v82.read_v82_dashboard(system)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["paper_v80"]["observation_count"], 1)
            self.assertEqual(result["paper_v80"]["action_count"], 1)
            self.assertTrue(result["paper_v80"]["latest_exact_l15_active"])
            self.assertEqual(result["historical_profit_v81"]["primary_tactical_paper_challenger"], "L15_SWAP50_WORST")
            self.assertFalse(result["live_orders_allowed"])
            self.assertFalse(result["promotion_authorized"])

    def test_missing_paper_state_is_read_only_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            system = repo / "vn_quant_local_system"
            system.mkdir()
            with patch.object(v82, "read_v78_tactical_snapshot", return_value={"status": "NOT_READY"}):
                result = v82.read_v82_dashboard(system)
            self.assertEqual(result["paper_v80"]["status"], "NOT_READY")
            self.assertEqual(result["paper_v80"]["observation_count"], 0)
            self.assertFalse(result["live_orders_allowed"])


if __name__ == "__main__":
    unittest.main()
