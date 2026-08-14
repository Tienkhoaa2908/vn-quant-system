from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup_dnse_credentials_windows.ps1"
RUNNER = ROOT / "scripts" / "run_v41_with_dnse_credentials_windows.ps1"
ONE_SHOT = ROOT / "scripts" / "setup_and_run_v41_dnse_gitbash.sh"


class DnseDpapiScriptsV41Test(unittest.TestCase):
    def test_setup_uses_masked_prompt_and_dpapi_outside_repository(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("Read-Host $Prompt -AsSecureString", text)
        self.assertIn("ConvertFrom-SecureString", text)
        self.assertIn("$env:LOCALAPPDATA", text)
        self.assertIn("Set-PrivateAcl", text)
        self.assertNotIn("SetEnvironmentVariable", text)
        self.assertIsNone(re.search(r"Set-Content[^\n]*\.env(?:\s|$)", text, re.IGNORECASE))
        self.assertNotIn("setx", text.lower())

    def test_runner_scopes_plaintext_to_child_process_and_cleans_environment(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("ConvertTo-SecureString", text)
        self.assertIn("$env:DNSE_API_KEY = $apiKeyPlain", text)
        self.assertIn("$env:DNSE_API_SECRET = $apiSecretPlain", text)
        self.assertIn("Remove-Item Env:DNSE_API_KEY", text)
        self.assertIn("Remove-Item Env:DNSE_API_SECRET", text)
        self.assertIn("ZeroFreeBSTR", text)
        self.assertNotIn("Write-Host $apiKeyPlain", text)
        self.assertNotIn("Write-Host $apiSecretPlain", text)
        self.assertNotIn("Start-Process", text)

    def test_one_shot_never_reads_or_echoes_secret_in_bash(self) -> None:
        text = ONE_SHOT.read_text(encoding="utf-8")
        self.assertIn("setup_dnse_credentials_windows.ps1", text)
        self.assertIn("run_v41_with_dnse_credentials_windows.ps1", text)
        self.assertNotIn("read -s", text)
        self.assertNotIn("DNSE_API_KEY=", text)
        self.assertNotIn("DNSE_API_SECRET=", text)
        self.assertNotIn("setx", text.lower())

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell required")
    def test_powershell_scripts_parse_on_windows(self) -> None:
        for path in (SETUP, RUNNER):
            escaped = str(path).replace("'", "''")
            command = (
                "$tokens=$null;$errors=$null;"
                f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',"
                "[ref]$tokens,[ref]$errors)|Out-Null;"
                "if($errors.Count -gt 0){$errors|ForEach-Object{Write-Error $_};exit 1}"
            )
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"{path.name}: {completed.stdout}\n{completed.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
