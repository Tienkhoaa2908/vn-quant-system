from __future__ import annotations

import unittest

from he_thong_dinh_luong.model_lab_upgrade_v7 import (
    normalize_deployment_status,
)


class ModelLabUpgradeV7Tests(unittest.TestCase):
    def test_string_deployment_status_is_adapted_without_character_dict_error(self) -> None:
        status, structured = normalize_deployment_status("NO_MODEL_APPROVED")
        self.assertEqual(status, "NO_MODEL_APPROVED")
        self.assertEqual(structured, {"status": "NO_MODEL_APPROVED"})

    def test_structured_deployment_status_preserves_fields(self) -> None:
        status, structured = normalize_deployment_status({
            "status": "PAPER_ONLY",
            "v6_posthoc_policy_blocked": True,
        })
        self.assertEqual(status, "PAPER_ONLY")
        self.assertTrue(structured["v6_posthoc_policy_blocked"])

    def test_missing_deployment_status_fails_closed(self) -> None:
        status, structured = normalize_deployment_status(None)
        self.assertEqual(status, "NO_MODEL_APPROVED")
        self.assertEqual(structured["status"], "NO_MODEL_APPROVED")


if __name__ == "__main__":
    unittest.main()
