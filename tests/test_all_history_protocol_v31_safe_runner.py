from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

from he_thong_dinh_luong import all_history_protocol_v31_safe_runner as runner


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_emit_json_is_ascii_safe(monkeypatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    runner._emit_json({"message": "tận dụng toàn bộ dữ liệu"})

    output = stream.getvalue()
    output.encode("ascii")
    assert "\\u1eadn" in output
    assert json.loads(output)["message"] == "tận dụng toàn bộ dữ liệu"


def test_bundle_contains_all_v31_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "all-history-v31"
    output_dir.mkdir()
    (output_dir / "all_history_protocol_v31.json").write_text(
        '{"status":"SUCCESS"}\n',
        encoding="utf-8",
    )
    (output_dir / "training_coverage_audit_v31.csv").write_text(
        "metric,value\nrows,100\n",
        encoding="utf-8",
    )

    bundle, digest = runner._create_analysis_bundle(
        output_dir,
        status="SUCCESS",
        summary={"primary_fold_count": 57},
    )

    assert digest == _sha256(bundle)
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        prefix = "all-history-v31/"
        assert prefix + "all_history_protocol_v31.json" in names
        assert prefix + "training_coverage_audit_v31.csv" in names
        assert prefix + runner.BUNDLE_MANIFEST_FILE in names
        manifest = json.loads(
            archive.read(prefix + runner.BUNDLE_MANIFEST_FILE).decode("utf-8")
        )
    assert manifest["status"] == "SUCCESS"
    assert manifest["file_count_excluding_manifest"] == 2
    assert manifest["research_eligible"] is False
    assert manifest["live_capital_approved"] is False


def test_write_csv_union_preserves_model_specific_columns(tmp_path: Path) -> None:
    output = tmp_path / "selection.csv"

    runner._write_csv_union(
        output,
        [
            {"model": "ridge", "selected_alpha": 10.0},
            {"model": "logit", "selected_c": 1.0},
        ],
    )

    import csv
    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert list(rows[0]) == ["model", "selected_alpha", "selected_c"]
    assert rows[0]["selected_alpha"] == "10.0"
    assert rows[1]["selected_c"] == "1.0"
