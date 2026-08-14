from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

from he_thong_dinh_luong import portfolio_ablation_v30_safe_runner as runner


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_emit_json_is_ascii_safe(monkeypatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    runner._emit_json({"message": "lợi nhuận cơ sở"})

    output = stream.getvalue()
    output.encode("ascii")
    assert "\\u01a1" in output
    assert json.loads(output)["message"] == "lợi nhuận cơ sở"


def test_create_analysis_bundle_contains_every_output_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "portfolio-ablation-v30-run"
    output_dir.mkdir()
    (output_dir / "portfolio_ablation_v30.json").write_text(
        '{"status":"SUCCESS"}\n',
        encoding="utf-8",
    )
    (output_dir / "performance_status_v30.csv").write_text(
        "model,base_net_total_return\nC3,0.25\n",
        encoding="utf-8",
    )
    nested = output_dir / "diagnostics"
    nested.mkdir()
    (nested / "trace.txt").write_text("ok\n", encoding="utf-8")

    bundle_path, bundle_sha = runner._create_analysis_bundle(
        output_dir,
        status="SUCCESS",
        summary={"recommendation": "KEEP"},
    )

    assert bundle_path == tmp_path / "portfolio-ablation-v30-run.zip"
    assert bundle_sha == _sha256(bundle_path)
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        prefix = "portfolio-ablation-v30-run/"
        assert prefix + "portfolio_ablation_v30.json" in names
        assert prefix + "performance_status_v30.csv" in names
        assert prefix + "diagnostics/trace.txt" in names
        assert prefix + runner.BUNDLE_MANIFEST_FILE in names
        manifest = json.loads(
            archive.read(prefix + runner.BUNDLE_MANIFEST_FILE).decode("utf-8")
        )
    assert manifest["status"] == "SUCCESS"
    assert manifest["file_count_excluding_manifest"] == 3
    assert {row["path"] for row in manifest["files"]} == {
        "portfolio_ablation_v30.json",
        "performance_status_v30.csv",
        "diagnostics/trace.txt",
    }
    assert manifest["live_capital_approved"] is False
    assert manifest["actionable"] is False


def test_create_analysis_bundle_replaces_existing_zip(tmp_path: Path) -> None:
    output_dir = tmp_path / "portfolio-ablation-v30-run"
    output_dir.mkdir()
    source = output_dir / "result.csv"
    source.write_text("value\n1\n", encoding="utf-8")

    first_path, first_sha = runner._create_analysis_bundle(
        output_dir,
        status="SUCCESS",
    )
    source.write_text("value\n2\n", encoding="utf-8")
    second_path, second_sha = runner._create_analysis_bundle(
        output_dir,
        status="SUCCESS",
    )

    assert first_path == second_path
    assert first_sha != second_sha
    with zipfile.ZipFile(second_path) as archive:
        assert archive.read(
            "portfolio-ablation-v30-run/result.csv"
        ).decode("utf-8") == "value\n2\n"
