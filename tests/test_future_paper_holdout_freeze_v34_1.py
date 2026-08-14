from __future__ import annotations

from datetime import datetime, timezone, timedelta
import unittest

from src.he_thong_dinh_luong import future_paper_holdout_freeze_v34 as base
from src.he_thong_dinh_luong import future_paper_holdout_freeze_v34_1 as v34_1


class FuturePaperHoldoutFreezeV341Tests(unittest.TestCase):
    def test_policy_core_ignores_local_artifact_path(self) -> None:
        common = {
            "artifact_zip_sha256": "abc123",
            "report_sha256": "def456",
        }
        source_a = {
            **common,
            "artifact_zip": r"C:\first\place\v33.zip",
        }
        source_b = {
            **common,
            "artifact_zip": r"D:\other\place\renamed.zip",
        }
        kwargs = {
            "evidence": {
                "summary": {"base_relative_total_return": 0.4},
                "paired_vs_nested": {
                    "bootstrap_probability_delta_positive": 0.96
                },
            },
            "report": {
                "source_v32_1_outer_test_last_date": "2026-06-30",
                "recommendation": base.EXPECTED_RECOMMENDATION,
            },
            "freeze_timestamp": datetime(
                2026,
                8,
                3,
                9,
                22,
                tzinfo=timezone(timedelta(hours=7)),
            ),
            "exclude_signal_through": datetime(2026, 7, 31).date(),
        }
        left = v34_1._stable_policy_core(source=source_a, **kwargs)
        right = v34_1._stable_policy_core(source=source_b, **kwargs)
        self.assertEqual(left, right)
        self.assertNotIn("artifact_zip", left["source"])

    def test_stable_core_keeps_cryptographic_source_hashes(self) -> None:
        core = v34_1._stable_policy_core(
            source={
                "artifact_zip": r"C:\local\v33.zip",
                "artifact_zip_sha256": "abc123",
                "report_sha256": "def456",
            },
            evidence={
                "summary": {"base_relative_total_return": 0.4},
                "paired_vs_nested": {
                    "bootstrap_probability_delta_positive": 0.96
                },
            },
            report={
                "source_v32_1_outer_test_last_date": "2026-06-30",
                "recommendation": base.EXPECTED_RECOMMENDATION,
            },
            freeze_timestamp=datetime(
                2026,
                8,
                3,
                9,
                22,
                tzinfo=timezone(timedelta(hours=7)),
            ),
            exclude_signal_through=datetime(2026, 7, 31).date(),
        )
        self.assertEqual(
            core["source"]["artifact_zip_sha256"],
            "abc123",
        )
        self.assertEqual(core["source"]["report_sha256"], "def456")


if __name__ == "__main__":
    unittest.main()
