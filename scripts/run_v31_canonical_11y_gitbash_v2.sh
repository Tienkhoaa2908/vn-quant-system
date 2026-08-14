#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
STORE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
INPUT_ZIP_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
V22_REPORT_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/historical_research_input_v22.json"

EXPECTED_STORE_SHA256="7b6f2274d43c12a311f83aa71952ef2abcfca04e2f5204c2f0e9a36a6c144549"
EXPECTED_INPUT_SHA256="66f4dd6699026289501b260949237772f832ac716e700fa686f8b0b8accd38e5"
EXPECTED_REPORT_SHA256="bb6d882444211005b7b0c47323ec2c17266c1ad97efcfa4a6665d7c86682f9a1"

keep_open() {
    echo
    echo "Git Bash duoc giu mo."
    exec bash
}

fail() {
    echo "FAILED: $*" >&2
    keep_open
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi

if ! command -v cygpath >/dev/null 2>&1; then
    fail "khong tim thay cygpath"
fi

echo "===== DONG BO CODE ====="
if ! git fetch origin \
  || ! git switch "$BRANCH" \
  || ! git pull --ff-only origin "$BRANCH"; then
    fail "khong dong bo duoc branch $BRANCH"
fi

export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

for file in "$STORE_POSIX" "$INPUT_ZIP_POSIX" "$V22_REPORT_POSIX"; do
    [[ -f "$file" ]] || fail "khong tim thay file: $file"
done

actual_store_sha="$(sha256sum "$STORE_POSIX" | awk '{print $1}')"
actual_input_sha="$(sha256sum "$INPUT_ZIP_POSIX" | awk '{print $1}')"
actual_report_sha="$(sha256sum "$V22_REPORT_POSIX" | awk '{print $1}')"

[[ "$actual_store_sha" == "$EXPECTED_STORE_SHA256" ]] \
    || fail "SQLite hash da thay doi: $actual_store_sha"
[[ "$actual_input_sha" == "$EXPECTED_INPUT_SHA256" ]] \
    || fail "V22 ZIP hash khong khop: $actual_input_sha"
[[ "$actual_report_sha" == "$EXPECTED_REPORT_SHA256" ]] \
    || fail "V22 report hash khong khop: $actual_report_sha"

STORE_WIN="$(cygpath -w "$STORE_POSIX")"
INPUT_ZIP_WIN="$(cygpath -w "$INPUT_ZIP_POSIX")"
V22_REPORT_WIN="$(cygpath -w "$V22_REPORT_POSIX")"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_ROOT_POSIX="$PWD/artifacts"
mkdir -p "$ARTIFACT_ROOT_POSIX"
OUTPUT_DIR_POSIX="$ARTIFACT_ROOT_POSIX/all-history-protocol-v31-canonical-11y-v2-$RUN_ID"
PREFLIGHT_POSIX="$ARTIFACT_ROOT_POSIX/.canonical-11y-preflight-v31-$RUN_ID.json"

[[ ! -e "$OUTPUT_DIR_POSIX" ]] || fail "output da ton tai: $OUTPUT_DIR_POSIX"
[[ ! -e "$PREFLIGHT_POSIX" ]] || fail "preflight da ton tai: $PREFLIGHT_POSIX"

OUTPUT_DIR_WIN="$(cygpath -w "$OUTPUT_DIR_POSIX")"
PREFLIGHT_WIN="$(cygpath -w "$PREFLIGHT_POSIX")"

echo
echo "===== PREFLIGHT SQLITE + V22 ZIP ====="
python - \
    "$STORE_WIN" \
    "$INPUT_ZIP_WIN" \
    "$V22_REPORT_WIN" \
    "$PREFLIGHT_WIN" <<'PY'
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote

from he_thong_dinh_luong.all_history_protocol_v31_compat_runner import (
    _load_all_history_zip_compatible,
)

store = Path(sys.argv[1]).resolve()
input_zip = Path(sys.argv[2]).resolve()
report_path = Path(sys.argv[3]).resolve()
preflight_path = Path(sys.argv[4]).resolve()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


uri = f"file:{quote(store.as_posix())}?mode=ro"
connection = sqlite3.connect(uri, uri=True)
connection.row_factory = sqlite3.Row
try:
    bars = connection.execute(
        """
        SELECT COUNT(*) AS row_count,
               MIN(day) AS first_day,
               MAX(day) AS last_day,
               COUNT(DISTINCT day) AS distinct_days,
               COUNT(DISTINCT symbol) AS distinct_symbols
        FROM bars
        """
    ).fetchone()
    conflicts = connection.execute(
        "SELECT COUNT(*) AS row_count FROM conflicts"
    ).fetchone()["row_count"]
finally:
    connection.close()

actual_sqlite = {
    "row_count": int(bars["row_count"]),
    "first_day": str(bars["first_day"]),
    "last_day": str(bars["last_day"]),
    "distinct_days": int(bars["distinct_days"]),
    "distinct_symbols": int(bars["distinct_symbols"]),
    "conflict_row_count": int(conflicts),
}
expected_sqlite = {
    "row_count": 299466,
    "first_day": "2015-06-29",
    "last_day": "2026-07-31",
    "distinct_days": 2775,
    "distinct_symbols": 122,
    "conflict_row_count": 0,
}
if actual_sqlite != expected_sqlite:
    raise SystemExit(
        "CANONICAL_SQLITE_CONTRACT_MISMATCH:"
        + json.dumps(
            {"expected": expected_sqlite, "actual": actual_sqlite},
            ensure_ascii=True,
            sort_keys=True,
        )
    )

rows, input_manifest, coverage = _load_all_history_zip_compatible(input_zip)
v22_report = json.loads(report_path.read_text(encoding="utf-8-sig"))

payload = {
    "status": "PASS",
    "schema_version": "canonical_11y_preflight_v31_v2",
    "fix": "V22_BOOLEAN_FEATURE_TRUE_FALSE_PARSED_AS_1_0",
    "canonical_store": {
        "path": str(store),
        "sha256": file_sha256(store),
        **actual_sqlite,
    },
    "canonical_input_zip": {
        "path": str(input_zip),
        "sha256": file_sha256(input_zip),
    },
    "canonical_v22_report": {
        "path": str(report_path),
        "sha256": file_sha256(report_path),
        "top_level_keys": (
            sorted(v22_report) if isinstance(v22_report, dict) else []
        ),
    },
    "v31_input_coverage": coverage,
    "v31_model_trainable_row_count_crosscheck": len(rows),
    "input_manifest_schema": (
        input_manifest.get("schema_version")
        or input_manifest.get("contract_version")
        or input_manifest.get("schema")
    ),
    "portfolio_pnl_after_costs_computed": False,
    "research_eligible": False,
    "live_capital_approved": False,
}
preflight_path.write_text(
    json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
PY

PREFLIGHT_STATUS=$?
if [[ $PREFLIGHT_STATUS -ne 0 ]]; then
    fail "preflight data that bai; model chua duoc chay"
fi

echo
echo "===== CHAY MODEL V31 BOOLEAN-COMPAT ====="
echo "INPUT_ZIP=$INPUT_ZIP_POSIX"
echo "OUTPUT_DIR=$OUTPUT_DIR_POSIX"

python -m he_thong_dinh_luong.all_history_protocol_v31_compat_runner \
    --input-zip "$INPUT_ZIP_WIN" \
    --output-dir "$OUTPUT_DIR_WIN" \
    --evaluation-months 132 \
    --minimum-train-months 60 \
    --inner-validation-months 3 \
    --pooled-block-months 7 \
    --pooled-test-slot 7 \
    --pooled-validation-slot 6 \
    --bootstrap-repetitions 2000 \
    --bootstrap-block-months 3 \
    --effective-trials 32 \
    --seed 20260802

MODEL_STATUS=$?

if [[ -d "$OUTPUT_DIR_POSIX" ]]; then
    cp "$PREFLIGHT_POSIX" "$OUTPUT_DIR_POSIX/canonical_11y_preflight_v31.json"
    python - "$OUTPUT_DIR_WIN" "$MODEL_STATUS" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import sys

from he_thong_dinh_luong.all_history_protocol_v31_safe_runner import (
    _create_analysis_bundle,
)

output_dir = Path(sys.argv[1]).resolve()
status_code = int(sys.argv[2])
status = "SUCCESS" if status_code == 0 else "FAILED"
summary = {
    "compatibility_fix": "V22_BOOLEAN_FEATURE_TRUE_FALSE_PARSED_AS_1_0",
    "preflight_file": "canonical_11y_preflight_v31.json",
    "portfolio_pnl_after_costs_computed": False,
}
report_path = output_dir / "all_history_protocol_v31.json"
if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    summary["recommendation"] = report.get("recommendation")
bundle, digest = _create_analysis_bundle(
    output_dir,
    status=status,
    summary=summary,
)
print(f"REBUNDLED_ARTIFACT={bundle}")
print(f"REBUNDLED_SHA256={digest}")
PY
fi

rm -f "$PREFLIGHT_POSIX"

echo
echo "===== TOM TAT OUTPUT ====="
python - "$OUTPUT_DIR_WIN" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import sys

output_dir = Path(sys.argv[1]).resolve()
coverage_path = output_dir / "training_coverage_audit_v31.json"
report_path = output_dir / "all_history_protocol_v31.json"
failure_path = output_dir / "run_failure_v31.json"

if failure_path.is_file():
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR_TYPE=", failure.get("error_type"))
    print("ERROR=", failure.get("error"))

if coverage_path.is_file():
    coverage = json.loads(coverage_path.read_text(encoding="utf-8-sig"))
    print("RAW_FIRST_LAST=", coverage.get("raw_first_signal_date"), coverage.get("raw_last_signal_date"))
    print("RAW_SIGNAL_MONTH_COUNT=", coverage.get("raw_signal_month_count"))
    print("MODEL_TRAINABLE_FIRST_LAST=", coverage.get("model_trainable_first_signal_date"), coverage.get("model_trainable_last_signal_date"))
    print("MODEL_TRAINABLE_SIGNAL_MONTH_COUNT=", coverage.get("model_trainable_signal_month_count"))
    print("MODEL_TRAINABLE_ROWS=", coverage.get("model_trainable_row_count"))
    print("BELOW_MA250_TRAINABLE_ROWS=", coverage.get("below_or_not_above_ma250_trainable_row_count"))
    print("EXCLUSIONS=", json.dumps(coverage.get("exclusion_reason_counts", {}), ensure_ascii=True, sort_keys=True))
    print("INVALID_FIELDS=", json.dumps(coverage.get("invalid_model_field_counts", {}), ensure_ascii=True, sort_keys=True))

if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    primary = report.get("primary_protocol", {})
    pooled = report.get("pooled_seven_month_protocol", {})
    print("STATUS=", report.get("status"))
    print("PRIMARY_FOLD_COUNT=", primary.get("fold_count"))
    print("PRIMARY_FIRST_LAST_TEST=", primary.get("first_test_date"), primary.get("last_test_date"))
    print("POOLED_LOCKED_TEST_MONTHS=", pooled.get("locked_test_month_count"))
    print("RECOMMENDATION=", report.get("recommendation"))
    print("PORTFOLIO_PNL_AFTER_COSTS_COMPUTED=false")
PY

ZIP_POSIX="${OUTPUT_DIR_POSIX}.zip"
echo
echo "MODEL_EXIT_CODE=$MODEL_STATUS"
if [[ -f "$ZIP_POSIX" ]]; then
    echo "ARTIFACT_ZIP=$ZIP_POSIX"
    sha256sum "$ZIP_POSIX"
else
    echo "WARNING: khong tim thay ZIP tai $ZIP_POSIX"
fi

keep_open
