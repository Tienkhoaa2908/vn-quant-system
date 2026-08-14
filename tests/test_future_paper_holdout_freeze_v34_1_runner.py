from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.he_thong_dinh_luong import future_paper_holdout_freeze_v34 as base
from src.he_thong_dinh_luong import future_paper_holdout_freeze_v34_1 as compat


class FuturePaperHoldoutFreezeV341RunnerTests(unittest.TestCase):
    def test_captured_original_prevents_safe_runner_recursion(self) -> None:
        original_base_freeze = base.freeze_policy
        original_captured = compat._ORIGINAL_FREEZE_POLICY
        original_core = base._policy_core
        calls: list[bool] = []
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"

            def fake_original(**kwargs: object) -> dict[str, object]:
                calls.append(base._policy_core is compat._stable_policy_core)
                output.mkdir()
                base._write_json(
                    output / base.REPORT_FILE,
                    {"schema_version": base.SCHEMA_VERSION},
                )
                return {
                    "status": "SUCCESS",
                    "output_dir": str(output),
                    "policy_id": "test-policy",
                }

            try:
                compat._ORIGINAL_FREEZE_POLICY = fake_original
                base.freeze_policy = compat.freeze_policy
                result = compat.freeze_policy()
            finally:
                base.freeze_policy = original_base_freeze
                compat._ORIGINAL_FREEZE_POLICY = original_captured
                base._policy_core = original_core

        self.assertEqual(calls, [True])
        self.assertEqual(result["policy_id"], "test-policy")
        self.assertTrue(result["policy_id_path_independent"])
        self.assertIs(base._policy_core, original_core)


if __name__ == "__main__":
    unittest.main()
