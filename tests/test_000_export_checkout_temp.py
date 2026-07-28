from __future__ import annotations

import base64
from io import BytesIO
import os
from pathlib import Path
import platform
import unittest
import zipfile


class TestExportCheckoutTemp(unittest.TestCase):
    def test_export_checkout_vao_artifact_ubuntu(self) -> None:
        if os.environ.get("GITHUB_ACTIONS") != "true" or platform.system() != "Linux":
            self.skipTest("chi xuat checkout tren Ubuntu GitHub Actions")
        root = Path.cwd()
        memory = BytesIO()
        excluded_parts = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
        with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or any(part in excluded_parts for part in path.parts):
                    continue
                if path.name.startswith("phien-ban-ci-"):
                    continue
                archive.write(path, path.relative_to(root).as_posix())
        payload = base64.b64encode(memory.getvalue()).decode("ascii")
        with (root / "phien-ban-ci-ubuntu.txt").open("a", encoding="utf-8") as handle:
            handle.write("CHECKOUT_ZIP_BASE64_BEGIN\n")
            handle.write(payload + "\n")
            handle.write("CHECKOUT_ZIP_BASE64_END\n")
        self.assertGreater(len(payload), 1000)


if __name__ == "__main__":
    unittest.main()
