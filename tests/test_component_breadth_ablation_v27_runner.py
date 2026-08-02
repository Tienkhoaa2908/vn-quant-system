from __future__ import annotations

import unittest
from unittest.mock import patch

from he_thong_dinh_luong import component_breadth_ablation_v27 as base
from he_thong_dinh_luong import component_breadth_ablation_v27_runner as runner


class ComponentBreadthAblationV27RunnerTests(unittest.TestCase):
    def test_v22_boolean_values_are_converted_strictly(self) -> None:
        original = base._finite
        base._ORIGINAL_V27_FINITE = original
        try:
            self.assertEqual(
                runner._finite_with_v22_boolean(
                    "true",
                    name="vnindex_tren_ma250",
                ),
                1.0,
            )
            self.assertEqual(
                runner._finite_with_v22_boolean(
                    "false",
                    name="vnindex_tren_ma250",
                ),
                0.0,
            )
            with self.assertRaisesRegex(ValueError, "V27_INVALID_BOOLEAN"):
                runner._finite_with_v22_boolean(
                    "unknown",
                    name="vnindex_tren_ma250",
                )
        finally:
            delattr(base, "_ORIGINAL_V27_FINITE")

    def test_compatibility_patch_is_restored_after_run(self) -> None:
        original = base._finite
        with patch.object(base, "run_v27", return_value={"status": "SUCCESS"}) as call:
            result = runner.run_v27_compatible("input", "model", "output")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIs(base._finite, original)
        self.assertFalse(hasattr(base, "_ORIGINAL_V27_FINITE"))
        call.assert_called_once_with("input", "model", "output")


if __name__ == "__main__":
    unittest.main()
