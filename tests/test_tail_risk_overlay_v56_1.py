import unittest
from datetime import date

from he_thong_dinh_luong import tail_risk_overlay_v56 as v56
from he_thong_dinh_luong import tail_risk_overlay_v56_1 as v56_1
from he_thong_dinh_luong import weekly_micro_capital_v43_1 as v43_1


class TailRiskOverlayV561Tests(unittest.TestCase):
    def test_common_terminal_day_is_used_for_parity(self):
        original_new = v56.simulate_overlay
        original_old = v43_1._simulate
        captured = {}

        def fake_new(**kwargs):
            captured["new_analysis_end"] = kwargs["analysis_end"]
            return {"final_value_vnd": 123.0, "xirr": 0.125}, [], []

        def fake_old(**kwargs):
            captured["old_weekly_days"] = list(kwargs["weekly_days"])
            return {"final_value_vnd": 123.0, "xirr": 0.125}, [], []

        v56.simulate_overlay = fake_new
        v43_1._simulate = fake_old
        try:
            days = [date(2026, 7, 20), date(2026, 7, 27)]
            result = v56_1.baseline_parity_same_day(
                summaries=[],
                snapshots=[],
                prices=object(),
                weekly_days=days,
                analysis_end=date(2026, 7, 31),
            )
        finally:
            v56.simulate_overlay = original_new
            v43_1._simulate = original_old

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["comparison_day"], "2026-07-27")
        self.assertEqual(result["study_analysis_end"], "2026-07-31")
        self.assertEqual(captured["new_analysis_end"], date(2026, 7, 27))
        self.assertEqual(captured["old_weekly_days"], days)

    def test_patch_rebinds_v56_parity_guard(self):
        original = v56._baseline_parity
        try:
            v56_1.apply_patch()
            self.assertIs(v56._baseline_parity, v56_1.baseline_parity_same_day)
        finally:
            v56._baseline_parity = original


if __name__ == "__main__":
    unittest.main()
