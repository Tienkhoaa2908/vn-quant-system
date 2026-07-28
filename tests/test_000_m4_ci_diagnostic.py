from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest


class TestM4CIDiagnostic(unittest.TestCase):
    def test_ghi_failure_vao_artifact_tam(self) -> None:
        if os.environ.get("M4_DIAG_INNER") == "1":
            self.skipTest("inner diagnostic")
        env = dict(os.environ)
        env["M4_DIAG_INNER"] = "1"
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        suffix = "windows" if platform.system() == "Windows" else "ubuntu"
        artifact = Path(f"phien-ban-ci-{suffix}.txt")
        with artifact.open("a", encoding="utf-8") as handle:
            handle.write("\n===== M4 DIAGNOSTIC BEGIN =====\n")
            handle.write(completed.stdout)
            handle.write(completed.stderr)
            handle.write("\n===== M4 DIAGNOSTIC END =====\n")
        self.assertEqual(completed.returncode, 0, "inner suite failed; xem artifact phien-ban-ci")


if __name__ == "__main__":
    unittest.main()
