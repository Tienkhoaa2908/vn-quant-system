from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

from test_001_m4_doc_export_temp import SECTIONS


BRANCH = "m4-chay-lai-vn100-rong"
DOCS = tuple(SECTIONS)


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


class TestDocWriterTemp(unittest.TestCase):
    def test_commit_bon_tai_lieu_ky_thuat_tu_head_nhanh(self) -> None:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            self.skipTest("chi chay tren GitHub Actions")
        if platform.system() != "Linux":
            self.skipTest("chi Ubuntu duoc phep push commit tai lieu")
        if os.environ.get("GITHUB_HEAD_REF") != BRANCH:
            self.skipTest("khong phai PR cua nhanh muc tieu")

        run_git("fetch", "origin", BRANCH)
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "doc-writer"
            run_git("worktree", "add", "--detach", str(worktree), "FETCH_HEAD")
            try:
                for path_text, section in SECTIONS.items():
                    path = worktree / path_text
                    original = path.read_text(encoding="utf-8")
                    marker = section.strip().splitlines()[0]
                    if marker not in original:
                        path.write_text(original.rstrip() + section + "\n", encoding="utf-8")
                run_git("config", "user.name", "github-actions[bot]", cwd=worktree)
                run_git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=worktree)
                run_git("add", *DOCS, cwd=worktree)
                changed = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=worktree,
                    check=False,
                ).returncode != 0
                if changed:
                    run_git("commit", "-m", "cap nhat tai lieu ky thuat runtime rut gon Moc 4", cwd=worktree)
                    run_git("push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=worktree)
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
        self.assertEqual(DOCS, (
            "DECISIONS.md",
            "README.md",
            "tai_lieu/dac_ta_moc_4.md",
            "tai_lieu/kien_truc_moc_4.md",
        ))


if __name__ == "__main__":
    unittest.main()
