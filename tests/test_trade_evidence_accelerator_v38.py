from __future__ import annotations

import unittest

from he_thong_dinh_luong import trade_evidence_accelerator_v38 as v38


class TradeEvidenceAcceleratorV38Tests(unittest.TestCase):
    def _selection_rows(self):
        rows = []
        for index in range(51):
            rows.append(
                {
                    "signal_date": f"2022-{(index % 12) + 1:02d}-{(index % 27) + 1:02d}",
                    "rebuilt_selected_symbols": "|".join(
                        f"S{offset:02d}" for offset in range(10)
                    ),
                    "exact_order_match": "True",
                }
            )
        rows.sort(key=lambda row: row["signal_date"])
        return rows

    def _benchmark_rows(self):
        return [
            {
                "day": f"2022-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}",
                "required": "True",
                "covered": "True",
            }
            for index in range(52)
        ]

    def test_decision_surface_has_510_position_time_keys(self):
        surface = v38.build_decision_surface(
            self._selection_rows(),
            self._benchmark_rows(),
        )
        self.assertEqual(surface["period_count"], 51)
        self.assertEqual(surface["position_time_key_count"], 510)
        self.assertEqual(surface["holding_window_count"], 510)
        self.assertEqual(surface["execution_date_count"], 52)

    def test_selection_mismatch_fails_closed(self):
        rows = self._selection_rows()
        rows[0]["exact_order_match"] = "False"
        with self.assertRaisesRegex(ValueError, "V38_SELECTION_LINEAGE_NOT_EXACT"):
            v38.build_decision_surface(rows, self._benchmark_rows())

    def test_operational_dry_run_passes_seven_of_nine(self):
        result = v38.run_operational_dry_run()
        self.assertEqual(result["passed_count"], 7)
        self.assertEqual(result["total_count"], 9)
        self.assertEqual(
            result["remaining_workstation_controls"],
            ["account_sync_verified", "position_reconciliation_verified"],
        )
        self.assertFalse(result["live_capital_approved"])

    def test_source_registry_never_counts_as_assurance(self):
        registry = v38.authoritative_source_registry()
        self.assertEqual(
            registry["status"],
            "SOURCE_REGISTRY_ONLY_NOT_COMPLETENESS_PROOF",
        )
        self.assertTrue(
            registry["governance"]["source_registry_is_not_assurance"]
        )


if __name__ == "__main__":
    unittest.main()
