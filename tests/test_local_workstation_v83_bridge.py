from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from he_thong_dinh_luong import local_workstation_v83_bridge as v83


class V83BridgeTest(unittest.TestCase):
    def test_cut_watch_requires_persistent_severe_drag(self):
        row={
            "canonical_rank":"4","preview_rank":"17","prior_preview_rank":"16",
            "dragging_current_period":"true","relative_5":"-0.03",
            "drawdown_20":"-0.09","drawdown_60":"-0.13","eligible_now":"true",
        }
        self.assertTrue(v83._cut_watch(row))
        row["preview_rank"]="10"
        self.assertFalse(v83._cut_watch(row))

    def test_dashboard_makes_capital_discipline_primary_and_no_live_authority(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td); system=repo/"vn_quant_local_system"; system.mkdir()
            fake={
                "status":"SUCCESS",
                "tactical_v78":{
                    "capture_day":"2026-08-21",
                    "report":{"monthly_top10":["VPI"],"source_monthly_signal_day":"2026-07-31","period_execution_start_day":"2026-08-03"},
                    "tactical_rows":[{
                        "symbol":"VIC","canonical_rank":"4","preview_rank":"17","prior_preview_rank":"16",
                        "period_return":"-0.05","period_relative_return":"-0.06","relative_5":"-0.03",
                        "drawdown_20":"-0.09","drawdown_60":"-0.13","dragging_current_period":"true",
                        "eligible_now":"true","r07_trigger":"true","r08_trigger":"true","action":"RISK_ALERT_R08",
                    }],
                },
                "paper_v80":{},"historical_profit_v81":{},
            }
            with patch.object(v83,"read_v82_dashboard",return_value=fake), patch.object(v83,"_entry_gaps",return_value=[]):
                out=v83.read_v83_dashboard(system)
            self.assertEqual(out["primary_product_focus"],"CAPITAL_DISCIPLINE")
            self.assertEqual([x["symbol"] for x in out["no_add_now"]],["VIC"])
            self.assertEqual([x["symbol"] for x in out["cut_watch_now"]],["VIC"])
            self.assertFalse(out["research_policy"]["new_leader_research_reopened"])
            self.assertFalse(out["live_orders_allowed"])


if __name__ == "__main__":
    unittest.main()
