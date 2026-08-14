from __future__ import annotations
import unittest
from he_thong_dinh_luong import c3_multisignal_robustness_v65 as v65

class V65RobustnessTests(unittest.TestCase):
    def test_bh_adjust_monotone(self):
        rows=[{"cohort_id":"A","p_value":0.001},{"cohort_id":"B","p_value":0.02},{"cohort_id":"C","p_value":0.5}]
        q=v65.bh_adjust(rows)
        self.assertLessEqual(q["A"],q["B"])
        self.assertLessEqual(q["B"],q["C"])

    def test_canonical_freshness_flags_two_month_gap(self):
        out=v65.canonical_freshness([{"evaluation_day":"2026-08-07","canonical_day":"2026-06-30"},{"evaluation_day":"2026-07-31","canonical_day":"2026-06-30"}])
        by_day={row["evaluation_day"]:row for row in out}
        self.assertTrue(by_day["2026-08-07"]["canonical_stale_for_monthly_context"])
        self.assertFalse(by_day["2026-07-31"]["canonical_stale_for_monthly_context"])

    def test_cluster_bootstrap_positive_constant(self):
        rows=[{"kind":"LEADER","evaluation_day":"2020-01-01","forward_excess_return":"0.02","forward_return":"0.02"},{"kind":"LEADER","evaluation_day":"2020-01-08","forward_excess_return":"0.01","forward_return":"0.01"}]
        ci=v65.cluster_bootstrap(rows,cluster_field="evaluation_day",reps=100,seed=1)
        self.assertGreater(ci["mean_low"],0.0)

    def test_research_safety_flags_are_false(self):
        self.assertFalse(v65.LIVE_MODEL_CHANGE_AUTHORIZED)
        self.assertFalse(v65.AUTOMATIC_LIVE_ORDERS_ALLOWED)
        self.assertGreaterEqual(v65.BOOTSTRAP_REPS_DEFAULT,10000)

if __name__=="__main__": unittest.main()
